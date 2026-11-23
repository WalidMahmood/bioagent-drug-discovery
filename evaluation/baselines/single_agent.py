"""Baseline 2: Single Tool-Using Agent (Master #27).
Combines planning, tool calling, and interpretation into a single general-purpose agent.
No specialized agent roles, no separate evidence retriever, and NO verification critic.
Fairness parity fixes:
- Receives the exact same top-25 gene list as the 5-agent BioAgent-Lite system (not [:15]).
- Computes Evidence Support Rate empirically via agents/evidence.py rather than hardcoding 0.50.
"""
import datetime
import json
import os
import sys
from typing import Dict, Any, Optional
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.llm_client import chat, extract_json_safe
from tools.dispatcher import execute_computation
from agents import evidence as EV
from agents.schemas import Interpretation, InterpretationClaim
from evaluation.metrics.calculate_metrics import (
    compute_de_metrics,
    compute_statistical_correctness,
    compute_top_k_overlap,
    compute_evidence_support_rate,
    extract_cited_genes,
)

SYSTEM_PROMPT = """You are a bioinformatics analyst agent. You have been provided with deterministic computational results from differential expression and pathway analysis.
Your task is to synthesize the final analysis report, identifying key genes, pathways, and biological conclusions.

Return ONLY a valid JSON object:
{
  "top_genes": [
    {"gene": "GENE", "log2FC": 1.2, "padj": 0.01, "direction": "up"}
  ],
  "pathways": ["Pathway 1", "Pathway 2"],
  "observations": ["key summary observation"],
  "claims": [
    {"statement": "Gene X is up-regulated with log2FC=...", "type": "observed", "genes": ["Gene X"], "pathways": []}
  ],
  "conclusion": "Summary biological conclusion"
}
"""


def run_single_agent(dataset: str = "GSE202768", question: Optional[str] = None) -> Dict[str, Any]:
    """Run Baseline 2 (Single Tool-Using Agent) with fair top-25 context parity."""
    t0 = datetime.datetime.now(datetime.timezone.utc)
    if not question:
        question = (
            f"Analyze the differential expression response in {dataset} "
            "and identify key regulated genes and biological mechanisms."
        )

    # 1. Direct tool execution (identical top_n_genes=25 panel as 5-agent system)
    comp = execute_computation(dataset, top_n_genes=25)

    genes_text = "\n".join(
        [
            f"- {g.gene}: log2FC={g.log2FC:+.2f}, padj={f'{g.padj:.2e}' if g.padj is not None else 'N/A (FPKM)'}, direction={g.direction}"
            for g in comp.top_genes[:25]
        ]
    )
    pw_text = "\n".join([f"- {p.term} [{p.source}]: FDR={p.adjP:.2e}" for p in comp.sig_pathways[:8]])

    user_prompt = f"""Biological Request: {question}
Computed Tool Output ({comp.dataset}):
Total Significant / Ranked Genes: {comp.n_sig} ({comp.n_up} up, {comp.n_down} down)

Computed Top 25 Differential Genes:
{genes_text}

Computed Significant Pathway Enrichments:
{pw_text}

Synthesize your complete biological report in JSON.
"""

    llm_used = True
    fallback_reason = None
    out = chat(user_prompt, system=SYSTEM_PROMPT, max_tokens=1500)
    try:
        parsed = extract_json_safe(out["text"])
    except Exception as exc:
        llm_used = False
        fallback_reason = str(exc)
        parsed = {
            "top_genes": [g.model_dump() for g in comp.top_genes[:5]],
            "pathways": [p.term for p in comp.sig_pathways[:3]],
            "claims": [{"statement": f"{comp.top_genes[0].gene} is significant", "genes": [comp.top_genes[0].gene]}],
        }

    # Evaluate metrics against the exact reference top-25 significant panel
    ref_sig_set = set(g.gene.upper() for g in comp.top_genes if g.padj is None or g.padj < 0.05)
    reported_genes = [g.get("gene", "") for g in parsed.get("top_genes", []) if isinstance(g, dict)]
    cited_genes = extract_cited_genes(parsed)

    de_metrics = compute_de_metrics(reported_genes, ref_sig_set, comp.n_total_tested)
    cited_metrics = compute_de_metrics(cited_genes, ref_sig_set, comp.n_total_tested)
    top_overlap = compute_top_k_overlap(reported_genes, [g.gene for g in comp.top_genes], k_values=[10, 25])
    ref_df = pd.DataFrame([g.model_dump() for g in comp.top_genes])
    stat_audit = compute_statistical_correctness(parsed.get("claims", []), ref_df)

    # Compute real Evidence Support Rate empirically (never hardcode 0.50)
    claim_objs = []
    for c in parsed.get("claims", []):
        if isinstance(c, dict) and c.get("statement"):
            ctype = c.get("type", "observed")
            if ctype not in ("observed", "supported", "hypothesis"):
                ctype = "observed"
            claim_objs.append(
                InterpretationClaim(
                    statement=str(c["statement"]),
                    type=ctype,
                    genes=c.get("genes", []),
                    pathways=c.get("pathways", []),
                )
            )
    interp_proxy = Interpretation(observations=parsed.get("observations", []), claims=claim_objs)
    ev_records, _ = EV.retrieve(interp_proxy, comp)
    ev_metrics = compute_evidence_support_rate([r.model_dump() for r in ev_records])

    run_id = f"baseline_single_agent_{dataset}_" + t0.strftime("%Y%m%dT%H%M%SZ")
    result = {
        "run_id": run_id,
        "model": "Gemma-3-4B-IT-Q8",
        "system": "Single Tool-Using Agent (Baseline 2)",
        "dataset": dataset,
        "question": question,
        "llm_used": llm_used,
        "fallback_reason": fallback_reason,
        "latency_s": out["latency_s"],
        "tokens": out.get("usage", {}).get("total_tokens", 0),
        "llm_output": parsed,
        "evidence": [r.model_dump() for r in ev_records],
        "metrics": {
            **de_metrics,
            "cited_gene_precision": cited_metrics["precision"],
            "cited_gene_recall": cited_metrics["recall"],
            "cited_gene_f1": cited_metrics["f1"],
            **top_overlap,
            **stat_audit,
            **ev_metrics,
            "hallucination_rate": round(stat_audit["invented_genes"] / max(1, len(reported_genes)), 4),
        },
    }

    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_path = os.path.join(base, "outputs", "traces", f"{run_id}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    return result


if __name__ == "__main__":
    res = run_single_agent("GSE202768")
    print(f"Single-Agent Baseline Result ({res['dataset']}):")
    print(f"  Precision: {res['metrics']['precision']} | Recall: {res['metrics']['recall']} | F1: {res['metrics']['f1']}")
    print(f"  Stat Accuracy: {res['metrics']['statistical_accuracy']} | ESR: {res['metrics']['evidence_support_rate']}")
    print(f"  Trace saved to: outputs/traces/{res['run_id']}.json")
