"""LangGraph stateful workflow for BioAgent-Lite (Master #9, #10-17).
Sequential execution: Planner -> Computational -> Biology -> Evidence -> Critic -> PASS/CORRECT.
Bounded self-correction loop (max 2 iterations):
1. Re-prompts the Biological Interpreter LLM with explicit Critic error diagnostics so offending
   prose and gene directions are genuinely rewritten.
2. If specific claims still fail verification (or in deterministic/no-LLM mode), deterministically
   prunes the entire offending claim object into `pruned_claims` rather than stripping gene tags
   while leaving false statements intact.
Preserves full trajectory trace for Master #35 evaluation.
"""
import copy
import operator
import os
import re
import sys
from typing import Any, Dict, List, Tuple
from typing_extensions import Annotated, TypedDict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from langgraph.graph import StateGraph, END

from agents import planner as PL
from agents import computational as CA
from agents import biology as BI
from agents import evidence as EV
from agents import critic as CR
from agents.schemas import Plan, ComputationalResult, Interpretation

MAX_CORRECTIONS = 2

STRONG_WORD_REPLACEMENTS = [
    (re.compile(r"\bdefinitively demonstrates\b", re.I), "is consistent with"),
    (re.compile(r"\bcertainly causes\b", re.I), "may contribute to"),
    (re.compile(r"\bundeniably\b", re.I), "plausibly"),
    (re.compile(r"\bdefinitively\b", re.I), "suggestively"),
    (re.compile(r"\bproves\b", re.I), "is consistent with the observation that"),
    (re.compile(r"\bproven\b", re.I), "supported by current evidence"),
]


class BioState(TypedDict, total=False):
    question: str
    dataset: str
    disease_context: str
    plan: dict
    comp: dict
    discovery: dict
    interp: dict
    evidence: list
    verdict: dict
    traces: Annotated[list, operator.add]
    iterations: int


def _hedge_statement(stmt: str) -> Tuple[str, bool]:
    """Replace absolute causal verbs with hedged scientific phrasing."""
    updated = stmt
    changed = False
    for pat, repl in STRONG_WORD_REPLACEMENTS:
        new_stmt, count = pat.subn(repl, updated)
        if count > 0:
            updated = new_stmt
            changed = True
    return updated, changed


def _prune_failed_claims(state: BioState) -> Tuple[dict, List[str]]:
    """Deterministically drop entire invalid claims (never strip gene tags while keeping false prose)."""
    verdict = state["verdict"]
    interp = copy.deepcopy(state["interp"])
    failed_indices = set(verdict.get("audit_scores", {}).get("failed_claim_indices", []))

    surviving_claims = []
    pruned_statements = list(interp.get("pruned_claims", []))
    newly_pruned: List[str] = []

    for idx, claim in enumerate(interp.get("claims", [])):
        if idx in failed_indices:
            stmt = claim.get("statement", "")
            # Check if the ONLY issue on this claim was unhedged wording (no gene/direction/padj/FPKM error)
            claim_tag = f"claim #{idx+1}"
            claim_errs = [e for e in verdict.get("errors", []) if claim_tag in e.lower()]
            only_hedging = bool(claim_errs) and all("unscientific certainty" in e.lower() for e in claim_errs)
            if only_hedging:
                hedged_stmt, changed = _hedge_statement(stmt)
                if changed:
                    claim["statement"] = hedged_stmt
                    claim["hedged"] = True
                    surviving_claims.append(claim)
                    continue

            # Otherwise drop the entire invalid claim so false prose is never laundered into PASS
            pruned_statements.append(stmt)
            newly_pruned.append(stmt)
        else:
            hedged_stmt, changed = _hedge_statement(claim.get("statement", ""))
            if changed:
                claim["statement"] = hedged_stmt
                claim["hedged"] = True
            surviving_claims.append(claim)

    interp["claims"] = surviving_claims
    interp["pruned_claims"] = pruned_statements
    return interp, newly_pruned


def _apply_correction(state: BioState, use_llm: bool = True) -> Tuple[dict, Dict[str, Any]]:
    """Apply Critic-guided revision: re-prompt Biology LLM first; prune entire invalid claims if still wrong."""
    verdict = state["verdict"]
    current_iter = state.get("iterations", 0)
    feedback = list(verdict.get("errors", [])) + list(verdict.get("corrections", []))

    # Attempt 1: Re-prompt the Biological Interpreter LLM with explicit Critic feedback
    if use_llm and current_iter == 0:
        comp_res = ComputationalResult(**state["comp"])
        prev_interp = Interpretation(**state["interp"])
        revised_interp, bio_trace = BI.interpret(
            comp_res,
            use_llm=True,
            critic_feedback=feedback,
            previous_interp=prev_interp,
            discovery=state.get("discovery"),
        )
        if bio_trace.get("llm_used") and not bio_trace.get("fallback"):
            bio_trace["correction_strategy"] = "llm_reprompt"
            bio_trace["iteration"] = current_iter + 1
            return revised_interp.model_dump(), bio_trace

    # Fallback or final retry pass: deterministically prune entire invalid claims (never strip gene tags)
    pruned_interp, newly_pruned = _prune_failed_claims(state)
    trace = {
        "agent": "critic_correction",
        "correction_strategy": "claim_pruning",
        "iteration": current_iter + 1,
        "claims_pruned_this_step": len(newly_pruned),
        "pruned_statements": newly_pruned,
        "llm_used": False,
    }
    return pruned_interp, trace


def build_graph(use_llm: bool = True, enable_discovery: bool = True):
    g = StateGraph(BioState)

    def n_planner(state: BioState):
        ds = state.get("dataset", "auto")
        plan, t = PL.make_plan(state["question"], dataset=ds, use_llm=use_llm)
        return {"plan": plan.model_dump(), "traces": [t]}

    def n_compute(state: BioState):
        plan = Plan(**state["plan"])
        contrast_str = f"{plan.comparison.group_a} vs {plan.comparison.group_b}"
        comp_res, t = CA.run_computation(
            dataset=plan.dataset,
            contrast=contrast_str,
            top_n_genes=25,
            plan=plan,
        )
        return {"comp": comp_res.model_dump(), "traces": [t]}

    def n_discovery(state: BioState):
        if not enable_discovery:
            return {"discovery": {}, "traces": [{"agent": "therapeutic_discovery", "skipped": True}]}
        from tools.therapeutic_discovery import run_target_discovery

        comp_dict = state["comp"]
        disease_ctx = state.get("disease_context") or "cancer"
        dossier = run_target_discovery(
            top_genes=comp_dict.get("top_genes", []),
            disease_context=disease_ctx,
            dataset_name=comp_dict.get("dataset", "dataset"),
            max_targets=10,
            use_cache=True,
            live_network=True,
        )
        t = {
            "agent": "therapeutic_discovery",
            "dataset": comp_dict.get("dataset", "dataset"),
            "disease_context": disease_ctx,
            "targets_mapped": dossier.get("sources", {}).get("targets_mapped", 0),
            "concordant_drugs": len(dossier.get("concordant_drugs", [])),
            "blocked_drugs": len(dossier.get("blocked_drugs", [])),
            "pubmed_hits": len(dossier.get("literature", [])),
            "clinical_trials_hits": len(dossier.get("clinical_trials", [])),
            "latency_s": dossier.get("latency_s", 0.0),
        }
        return {"discovery": dossier, "traces": [t]}

    def n_biology(state: BioState):
        comp_res = ComputationalResult(**state["comp"])
        interp, t = BI.interpret(comp_res, use_llm=use_llm, discovery=state.get("discovery") or None)
        return {"interp": interp.model_dump(), "traces": [t]}

    def n_evidence(state: BioState):
        interp = Interpretation(**state["interp"])
        comp_res = ComputationalResult(**state["comp"])
        recs, t = EV.retrieve(interp, comp_res)
        return {"evidence": [r.model_dump() for r in recs], "traces": [t]}

    def n_critic(state: BioState):
        plan = Plan(**state["plan"])
        comp_res = ComputationalResult(**state["comp"])
        interp = Interpretation(**state["interp"])
        verdict, t = CR.verify(plan, comp_res, interp, discovery=state.get("discovery") or None)

        t = dict(t)
        t["verdict_snapshot"] = verdict.model_dump()
        t["iteration"] = state.get("iterations", 0)
        return {"verdict": verdict.model_dump(), "traces": [t]}

    def n_correct(state: BioState):
        interp, corr_trace = _apply_correction(state, use_llm=use_llm)
        current_iter = state.get("iterations", 0)
        return {
            "interp": interp,
            "iterations": current_iter + 1,
            "traces": [corr_trace],
        }

    def route_condition(state: BioState):
        if state["verdict"]["status"] == "PASS":
            return "pass"
        if state.get("iterations", 0) >= MAX_CORRECTIONS:
            return "giveup"
        return "correct"

    g.add_node("planner", n_planner)
    g.add_node("compute", n_compute)
    g.add_node("discovery", n_discovery)
    g.add_node("biology", n_biology)
    g.add_node("evidence", n_evidence)
    g.add_node("critic", n_critic)
    g.add_node("correct", n_correct)

    g.set_entry_point("planner")
    g.add_edge("planner", "compute")
    g.add_edge("compute", "discovery")
    g.add_edge("discovery", "biology")
    g.add_edge("biology", "evidence")
    g.add_edge("evidence", "critic")
    g.add_conditional_edges(
        "critic",
        route_condition,
        {"pass": END, "giveup": END, "correct": "correct"},
    )
    g.add_edge("correct", "evidence")

    return g.compile()
