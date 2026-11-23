"""Evaluation metrics calculator (Master Plan #29-32).
Computes unbiased quantitative benchmark metrics across agent and baseline runs:
- Level 1 & 2: Differential expression precision, recall, F1 against reference ground truth
- Level 2: Top-K gene overlap (K = 10, 25, 50)
- Level 2: Statistical correctness (padj significance, direction of fold-change with log2FC/log2FoldChange parity)
- Level 3: Pathway overlap and FDR concordance
- Level 4: Evidence Support Rate (proportion of factual claims grounded in evidence)
- Level 5: Hallucination rate (invented genes, fabricated statistics, direction errors)
"""
import re
from typing import Dict, List, Set, Any
import pandas as pd

UP_PAT = re.compile(r"\b(up[\s-]?regulat\w*|increas\w*|elevat\w*|overexpress\w*|induc\w*)\b", re.I)
DOWN_PAT = re.compile(r"\b(down[\s-]?regulat\w*|decreas\w*|reduc\w*|suppress\w*|repress\w*|deplet\w*)\b", re.I)


def extract_cited_genes(interp_dict: Dict[str, Any]) -> List[str]:
    """Extract unique gene symbols actually cited by the interpreter in its claims."""
    seen: Set[str] = set()
    ordered: List[str] = []
    for claim in interp_dict.get("claims", []):
        for g in claim.get("genes", []):
            g_clean = str(g).strip().upper()
            if g_clean and g_clean not in seen:
                seen.add(g_clean)
                ordered.append(g_clean)
    return ordered


def compute_de_metrics(
    reported_genes: List[str],
    reference_sig_genes: Set[str],
    total_genes_tested: int,
) -> Dict[str, float]:
    """Calculate Precision, Recall, and F1 for reported significant genes vs reference."""
    reported_set = set(g.strip().upper() for g in reported_genes if str(g).strip())
    ref_set = set(g.strip().upper() for g in reference_sig_genes if str(g).strip())

    tp = len(reported_set.intersection(ref_set))
    fp = len(reported_set - ref_set)
    fn = len(ref_set - reported_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
    }


def compute_top_k_overlap(
    reported_top_genes: List[str],
    reference_top_genes: List[str],
    k_values: List[int] = [10, 25, 50],
) -> Dict[str, float]:
    """Calculate Jaccard overlap between reported and reference top-K ranked genes."""
    overlaps = {}
    rep_clean = [g.strip().upper() for g in reported_top_genes if str(g).strip()]
    ref_clean = [g.strip().upper() for g in reference_top_genes if str(g).strip()]

    for k in k_values:
        rep_k = set(rep_clean[:k])
        ref_k = set(ref_clean[:k])
        intersection = len(rep_k.intersection(ref_k))
        union = len(rep_k.union(ref_k))
        jaccard = intersection / union if union > 0 else 0.0
        overlaps[f"top_{k}_overlap"] = round(intersection / k if k > 0 else 0.0, 4)
        overlaps[f"top_{k}_jaccard"] = round(jaccard, 4)

    return overlaps


def compute_statistical_correctness(
    claims: List[Dict[str, Any]],
    reference_de_df: pd.DataFrame,
    padj_threshold: float = 0.05,
) -> Dict[str, Any]:
    """Audit statistical statements in claims against computed reference values.
    Supports both DESeq2 ('log2FoldChange') and TopGene ('log2FC') column names.
    """
    if reference_de_df.empty:
        return {
            "statistical_accuracy": 0.0,
            "total_gene_claims": 0,
            "correct_gene_claims": 0,
            "direction_errors": 0,
            "padj_stat_trap_errors": 0,
            "invented_genes": 0,
        }

    gene_col = "gene" if "gene" in reference_de_df.columns else reference_de_df.columns[0]
    de_indexed = reference_de_df.set_index(gene_col)
    de_indexed.index = [str(x).strip().upper() for x in de_indexed.index]

    total_claims = 0
    correct_claims = 0
    padj_errors = 0
    direction_errors = 0
    invented_genes = 0

    for c in claims:
        genes = c.get("genes", [])
        stmt = str(c.get("statement", ""))
        is_up_claim = bool(UP_PAT.search(stmt))
        is_down_claim = bool(DOWN_PAT.search(stmt))

        for g in genes:
            g_clean = str(g).strip().upper()
            if not g_clean:
                continue
            total_claims += 1
            if g_clean not in de_indexed.index:
                invented_genes += 1
                continue

            row = de_indexed.loc[g_clean]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]

            # Support both TopGene ('log2FC') and DESeq2 CSV ('log2FoldChange') schemas
            lfc_raw = None
            for col_name in ("log2FoldChange", "log2FC"):
                if col_name in row.index and pd.notna(row[col_name]):
                    lfc_raw = row[col_name]
                    break
            lfc = float(lfc_raw) if lfc_raw is not None else 0.0

            padj_val = row["padj"] if "padj" in row.index else None
            padj = float(padj_val) if (padj_val is not None and pd.notna(padj_val)) else None

            is_stat_trap = (
                (padj is not None)
                and (padj >= padj_threshold)
                and ("significan" in stmt.lower() or c.get("type") == "observed")
            )
            if is_stat_trap:
                padj_errors += 1
                continue

            # Unambiguous single-direction statement check
            if is_up_claim and not is_down_claim and lfc < 0:
                direction_errors += 1
                continue
            if is_down_claim and not is_up_claim and lfc > 0:
                direction_errors += 1
                continue

            correct_claims += 1

    accuracy = correct_claims / total_claims if total_claims > 0 else 1.0
    return {
        "statistical_accuracy": round(accuracy, 4),
        "total_gene_claims": total_claims,
        "correct_gene_claims": correct_claims,
        "direction_errors": direction_errors,
        "padj_stat_trap_errors": padj_errors,
        "invented_genes": invented_genes,
    }


def compute_evidence_support_rate(
    evidence_records: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Calculate the Evidence Support Rate (Master Plan #31)."""
    if not evidence_records:
        return {
            "evidence_support_rate": 0.0,
            "partially_supported_rate": 0.0,
            "unsupported_claim_rate": 0.0,
            "total_evidence_queries": 0,
        }

    supported = sum(1 for r in evidence_records if float(r.get("relevance", 0.0)) >= 0.7)
    partially_supported = sum(1 for r in evidence_records if 0.0 < float(r.get("relevance", 0.0)) < 0.7)
    unsupported = sum(1 for r in evidence_records if float(r.get("relevance", 0.0)) == 0.0)

    total = len(evidence_records)
    return {
        "evidence_support_rate": round(supported / total, 4),
        "partially_supported_rate": round(partially_supported / total, 4),
        "unsupported_claim_rate": round(unsupported / total, 4),
        "total_evidence_queries": total,
    }
