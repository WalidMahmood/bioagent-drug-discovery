"""Biological Interpreter Agent (Master #15).
Translates structured computational summaries into evidence-supported biological findings.
Enforces strict claim taxonomy (observed / supported / hypothesis), scientific hedging,
dynamic Count-vs-FPKM prompting (no fake FDR claims on descriptive FPKM),
and Critic feedback revision support.
"""
import json
import os
import sys
from typing import Tuple, Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.schemas import Interpretation, InterpretationClaim, ComputationalResult
from tools.llm_client import chat, extract_json_safe

SYSTEM_PROMPT = """You are a rigorous, specialized biological and therapeutic discovery interpreter for transcriptomics research (cancer and general human diseases).
Given structured statistical outputs (top differentially expressed genes, pathway enrichments, and optional Open Targets / PubMed / ClinicalTrials therapeutic discovery records), produce a clear, researcher-friendly, evidence-grounded interpretation.

CRITICAL SCIENTIFIC, THERAPEUTIC & SAFETY RULES:
1. Distinguish strictly between:
   - "observed": Factual numerical results calculated directly in the table (e.g. "Gene X is up-regulated with log2FC=+2.10, padj=1.2e-10").
   - "supported": Biological or drug-target interpretation corroborated by computed pathway enrichments or provided Open Targets/PubMed/ClinicalTrials records.
   - "hypothesis": Proposed biological mechanisms, gene-flipping perturbation strategies, or drug-repurposing ideas. MUST use hedged, probabilistic language ("is consistent with", "suggests potential", "warrants experimental validation").
2. DIRECTION ACCURACY IS MANDATORY: Check the sign of log2FC for EVERY gene before writing "up-regulated" (log2FC > 0) or "down-regulated" (log2FC < 0). Never group positive and negative log2FC genes under a single direction word.
3. THERAPEUTIC MoA CONCORDANCE IS MANDATORY:
   - For upregulated disease/resistance genes (log2FC > 0), only propose inhibition/suppression/antagonists.
   - For downregulated genes (log2FC < 0), only propose restoration/activation/agonists (NEVER recommend inhibiting an already suppressed gene).
   - ONLY cite drugs, PMIDs, or NCT trial IDs explicitly present in the provided Therapeutic Discovery Context. Never invent citations or drugs.
   - Always mention any recorded safety/pan-essentiality caveat if discussing a flagged target.
4. FORBIDDEN WORDS in hypotheses: Never write "proves", "proven", "definitively demonstrates", "cures", or "certainly causes".
5. If padj is "N/A (descriptive FPKM)", NEVER state "FDR < 0.05", "padj < 0.05", or "statistically significant". Describe only fold-change magnitudes.
6. Output MUST be valid JSON where observations, limitations, and uncertainty are JSON arrays of strings:
{
  "observations": ["plain-English summary of key numbers, top targets, and therapeutic findings"],
  "claims": [
    {
      "statement": "Clear, hedged biological or therapeutic hypothesis",
      "type": "observed | supported | hypothesis",
      "genes": ["GENE1", "GENE2"],
      "pathways": ["Pathway Name"],
      "hedged": true
    }
  ],
  "limitations": ["experimental limitations, sample size, bulk RNA-seq resolution, preclinical validation needs"],
  "uncertainty": ["unresolved mechanistic or toxicity questions requiring wet-lab validation"]
}
"""


def interpret(
    comp: ComputationalResult,
    use_llm: bool = True,
    critic_feedback: Optional[List[str]] = None,
    previous_interp: Optional[Interpretation] = None,
    discovery: Optional[Dict[str, Any]] = None,
) -> Tuple[Interpretation, Dict[str, Any]]:
    """Generate (or revise with Critic feedback) biological and therapeutic interpretation."""
    has_inferential = comp.inferential and any(g.padj is not None for g in comp.top_genes)

    genes_txt = "\n".join(
        [
            f"- {g.gene}: log2FC={g.log2FC:+.2f}, padj={f'{g.padj:.2e}' if g.padj is not None else 'N/A (descriptive FPKM)'}, direction={g.direction}"
            for g in comp.top_genes[:25]
        ]
    )
    pw_txt = (
        "\n".join([f"- {p.term} [{p.source}]: FDR={p.adjP:.2e}, overlap={p.overlap}" for p in comp.sig_pathways[:8]])
        if comp.sig_pathways
        else "- No precomputed pathway enrichment table available for this dataset."
    )

    if has_inferential:
        stat_summary_line = (
            f"Statistical Summary: {comp.n_sig} statistically significant genes at FDR < {comp.padj_threshold} "
            f"({comp.n_up} up, {comp.n_down} down) out of {comp.n_total_tested} tested."
        )
    else:
        stat_summary_line = (
            f"Descriptive FPKM Summary (§13 Count Guard Active — NO inferential p-values): "
            f"{comp.n_sig} genes with |log2FC| >= 1.0 ({comp.n_up} higher, {comp.n_down} lower) out of {comp.n_total_tested} expressed. "
            "DO NOT claim FDR < 0.05 or padj < 0.05."
        )

    feedback_block = ""
    if critic_feedback:
        fb_lines = "\n".join(f"- {item}" for item in critic_feedback)
        prev_json = json.dumps(previous_interp.model_dump(), indent=2)[:1500] if previous_interp else ""
        feedback_block = f"""
CRITIC REVISION REQUIRED — FIX EVERY ERROR LISTED BELOW:
{fb_lines}

Previous draft to revise:
{prev_json}

Rewrite the offending statements so every gene direction matches its exact log2FC sign, remove any uncomputed genes, and follow all scientific rules.
"""

    discovery_block = ""
    if discovery:
        top_t = (discovery.get("targets") or [])[:6]
        t_lines = [
            f"- {t['gene']} (log2FC={t['log2FC']:+.2f}, flip='{t['recommended_flip']}', priority={t['priority_score']}/100, tier='{t['evidence_tier']}', essential={t.get('is_essential')}, safety_alerts={t.get('safety_liabilities_count', 0)})"
            for t in top_t
        ]
        conc_d = (discovery.get("concordant_drugs") or [])[:6]
        d_lines = [
            f"- {d['drug_name']} -> {d['target_gene']} ({d['action_type']}, {d['clinical_stage_label']}, MoA=CONCORDANT)"
            for d in conc_d
        ]
        lit_lines = [
            f"- PMID:{h['pmid']} ({h['gene']}): {h['title'][:90]}"
            for h in (discovery.get("literature") or [])[:4]
        ]
        ct_lines = [
            f"- {c['nct_id']} ({c['phase']}, {c['status']}): {c['title'][:90]}"
            for c in (discovery.get("clinical_trials") or [])[:4]
        ]
        discovery_block = f"""
Therapeutic Discovery Context (Open Targets v4 + PubMed + ClinicalTrials.gov — Disease: {discovery.get('disease_context', 'cancer')}):
Prioritized Targets & Gene-Flipping Direction:
{chr(10).join(t_lines) if t_lines else '- None mapped'}

Mechanistically Concordant Drugs (SAFE to reference):
{chr(10).join(d_lines) if d_lines else '- No concordant clinical drugs found; focus on genetic knockdown/rescue hypotheses.'}

Verified PubMed Literature (ONLY cite these PMIDs):
{chr(10).join(lit_lines) if lit_lines else '- None retrieved'}

Verified Clinical Trials (ONLY cite these NCT IDs):
{chr(10).join(ct_lines) if ct_lines else '- None retrieved'}
"""

    user_prompt = f"""Dataset: {comp.dataset} ({comp.data_type})
Biological Contrast: {comp.contrast}
{stat_summary_line}

Top Computed Genes (all up to 25 ranked):
{genes_txt}

Top Computed Enriched Pathways:
{pw_txt}
{discovery_block}
{feedback_block}
Task: Produce a rigorous, evidence-supported biological and therapeutic discovery interpretation adhering strictly to all scientific, MoA concordance, and zero-hallucination citation rules in JSON.
"""

    trace: Dict[str, Any] = {
        "agent": "biological_interpreter",
        "dataset": comp.dataset,
        "contrast": comp.contrast,
        "llm_used": use_llm,
        "is_revision": bool(critic_feedback),
        "inferential_mode": has_inferential,
    }

    if use_llm:
        try:
            out = chat(user_prompt, system=SYSTEM_PROMPT, max_tokens=1600, temperature=0.15)
            parsed = extract_json_safe(out["text"])
            raw_claims = parsed.get("claims", [])
            if isinstance(raw_claims, dict):
                raw_claims = [raw_claims]
            claims = [InterpretationClaim(**c) for c in raw_claims if isinstance(c, dict) and c.get("statement")]
            interp = Interpretation(
                observations=parsed.get("observations", []),
                claims=claims,
                limitations=parsed.get("limitations", []),
                uncertainty=parsed.get("uncertainty", []),
            )
            trace.update(
                {
                    "latency_s": out["latency_s"],
                    "usage": out["usage"],
                    "claims_count": len(interp.claims),
                    "fallback": False,
                    "status": "revised" if critic_feedback else "success",
                }
            )
            return interp, trace
        except Exception as e:
            trace["llm_error"] = str(e)
            trace["fallback_reason"] = str(e)

    # Deterministic dataset-aware fallback (honestly separates inferential vs descriptive FPKM)
    up_genes = [g for g in comp.top_genes if g.log2FC > 0][:3]
    down_genes = [g for g in comp.top_genes if g.log2FC < 0][:3]
    top_gene = comp.top_genes[0] if comp.top_genes else None
    top_pathway = comp.sig_pathways[0].term if comp.sig_pathways else None

    fallback_claims: List[InterpretationClaim] = []

    if up_genes:
        up_desc = ", ".join(f"{g.gene} (log2FC={g.log2FC:+.2f})" for g in up_genes)
        if has_inferential:
            stmt_up = f"Up-regulated transcripts passing FDR < {comp.padj_threshold} in {comp.contrast} include {up_desc}."
        else:
            stmt_up = f"Higher-expression transcripts by descriptive FPKM fold-change (padj=N/A) in {comp.contrast} include {up_desc}."
        fallback_claims.append(
            InterpretationClaim(
                statement=stmt_up,
                type="observed",
                genes=[g.gene for g in up_genes],
                pathways=[],
                hedged=True,
            )
        )

    if down_genes:
        down_desc = ", ".join(f"{g.gene} (log2FC={g.log2FC:+.2f})" for g in down_genes)
        if has_inferential:
            stmt_down = f"Down-regulated transcripts passing FDR < {comp.padj_threshold} in {comp.contrast} include {down_desc}."
        else:
            stmt_down = f"Lower-expression transcripts by descriptive FPKM fold-change (padj=N/A) in {comp.contrast} include {down_desc}."
        fallback_claims.append(
            InterpretationClaim(
                statement=stmt_down,
                type="observed",
                genes=[g.gene for g in down_genes],
                pathways=[],
                hedged=True,
            )
        )

    if top_pathway:
        fallback_claims.append(
            InterpretationClaim(
                statement=f"Computed pathway over-representation highlights {top_pathway}, consistent with coordinated transcriptional remodeling.",
                type="supported",
                genes=[g.gene for g in comp.top_genes[:3]],
                pathways=[top_pathway],
                hedged=True,
            )
        )

    if top_gene:
        fallback_claims.append(
            InterpretationClaim(
                statement=f"Observed fold-change shifts involving {top_gene.gene} are consistent with perturbation-associated pathway modulation in {comp.dataset}.",
                type="hypothesis",
                genes=[top_gene.gene],
                pathways=[top_pathway] if top_pathway else [],
                hedged=True,
            )
        )

    if has_inferential:
        obs_1 = f"{comp.n_sig} genes reached significance at padj < {comp.padj_threshold} ({comp.n_up} up, {comp.n_down} down) in {comp.contrast}."
    else:
        obs_1 = (
            f"Descriptive FPKM ranking (§13 count guard active, no inferential p-values): "
            f"{comp.n_sig} genes exhibited |log2FC| >= 1.0 ({comp.n_up} up, {comp.n_down} down) in {comp.contrast}."
        )

    interp = Interpretation(
        observations=[
            obs_1,
            f"Top ranked transcript: {top_gene.gene} (log2FC={top_gene.log2FC:+.2f})." if top_gene else "No differential transcripts detected.",
        ],
        claims=fallback_claims,
        limitations=[
            "Small replicate count per group; findings require orthogonal biological replication.",
            "Bulk transcriptomics averages heterogeneous cell states and captures steady-state mRNA abundance.",
        ],
        uncertainty=[
            "Direct transcriptional regulation versus downstream secondary cascades cannot be distinguished without kinetic or binding assays."
        ],
    )
    trace.update(
        {
            "llm_used": False,
            "fallback": True,
            "fallback_reason": trace.get("fallback_reason", "use_llm=False"),
            "status": "fallback_applied",
        }
    )
    return interp, trace
