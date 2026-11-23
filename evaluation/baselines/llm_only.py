"""Baseline 1: LLM-Only.
No computational tools, no evidence grounding, no multi-agent verification.
Measures how much can be achieved through ordinary language-model reasoning alone,
and establishes the empirical baseline for statistical hallucination rates.
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
from evaluation.metrics.calculate_metrics import (
    compute_de_metrics,
    compute_statistical_correctness,
    compute_top_k_overlap,
)

SYSTEM_PROMPT = """You are a biomedical AI assistant. Given an experimental transcriptomics scenario, identify the differentially expressed genes, fold changes, significance values, and biological interpretation directly from your internal knowledge.

Return ONLY a JSON object:
{
  "top_genes": [
    {"gene": "GENE_SYMBOL", "log2FC": 1.5, "padj": 0.001, "direction": "up"}
  ],
  "pathways": ["Pathway Name 1", "Pathway Name 2"],
  "interpretation": "Biological summary of response",
  "claims": [
    {"statement": "Gene X is up-regulated...", "genes": ["Gene X"]}
  ]
}
"""


def run_llm_only(
    dataset: str = "GSE202768",
    question: Optional[str] = None,
    model_name: str = "Gemma-3-4B-IT-Q8",
) -> Dict[str, Any]:
    """Run Baseline 1 (LLM-only) and evaluate against reference ground truth."""
    if not question:
        question = (
            f"Perform differential expression analysis on {dataset} "
            "(PRRX1 knockdown vs uninduced control in Hs578 TNBC cells). "
            "Identify the top significant genes, fold changes, adjusted p-values, and biological pathways."
        )

    user_prompt = f"""Experimental Question: {question}
Dataset Accession: {dataset}

Please determine the differential expression results, significant genes with their exact log2 fold changes and adjusted p-values, and enriched pathways.
"""

    t0 = datetime.datetime.now(datetime.timezone.utc)
    llm_used = True
    fallback_reason = None
    out = chat(user_prompt, system=SYSTEM_PROMPT, max_tokens=1200)

    try:
        parsed = extract_json_safe(out["text"])
    except Exception as exc:
        llm_used = False
        fallback_reason = f"LLM-only JSON parse fallback: {exc}"
        parsed = {
            "top_genes": [],
            "pathways": [],
            "claims": [],
            "interpretation": "Failed to parse structured JSON from LLM-only response.",
        }

    # Load reference ground truth for evaluation (handles both inferential padj and descriptive FPKM)
    ref = execute_computation(dataset, top_n_genes=25)
    ref_sig_set = set(
        g.gene.upper()
        for g in ref.top_genes
        if (g.padj is not None and g.padj < 0.05) or (g.padj is None and abs(g.log2FC) >= 1.0)
    )
    reported_genes = [str(g.get("gene", "")).strip() for g in parsed.get("top_genes", []) if g.get("gene")]

    de_metrics = compute_de_metrics(reported_genes, ref_sig_set, ref.n_total_tested)
    top_overlap = compute_top_k_overlap(reported_genes, [g.gene for g in ref.top_genes], k_values=[10, 25])

    ref_df = pd.DataFrame([g.model_dump() for g in ref.top_genes])
    stat_audit = compute_statistical_correctness(parsed.get("claims", []), ref_df)

    # Hallucination rate = fraction of reported/cited genes absent from reference top table
    halluc_denom = max(1, len(reported_genes))
    run_id = f"baseline_llm_only_{dataset}_" + t0.strftime("%Y%m%dT%H%M%SZ")
    result = {
        "run_id": run_id,
        "model": model_name,
        "system": "LLM-only (Baseline 1)",
        "dataset": dataset,
        "question": question,
        "provenance": "measured_llm" if llm_used else "measured_fallback",
        "fallback_reason": fallback_reason,
        "latency_s": out.get("latency_s", 0.0),
        "tokens": out.get("usage", {}).get("total_tokens", 0),
        "llm_output": parsed,
        "metrics": {
            **de_metrics,
            **top_overlap,
            **stat_audit,
            "evidence_support_rate": 0.0,  # Zero external grounding by design
            "hallucination_rate": round(stat_audit["invented_genes"] / halluc_denom, 4),
        },
    }

    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_path = os.path.join(base, "outputs", "traces", f"{run_id}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2)

    return result


if __name__ == "__main__":
    res = run_llm_only("GSE202768")
    print(f"LLM-only Baseline Result ({res['dataset']}):")
    print(f"  Precision: {res['metrics']['precision']} | F1: {res['metrics']['f1']}")
    print(
        f"  Stat Accuracy: {res['metrics']['statistical_accuracy']} | "
        f"Direction Errors: {res['metrics']['direction_errors']} | "
        f"Hallucinated genes: {res['metrics']['invented_genes']}"
    )
    print(f"  Trace saved to: outputs/traces/{res['run_id']}.json")
