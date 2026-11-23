"""Computational Analyst: DETERMINISTIC tool execution layer (Master #11).
No language model is used for numerical calculations.
Delegates to deterministic tools (pydeseq2, CuffDiff parser, FPKM descriptive stats, gseapy)
and enforces runtime metadata + count-matrix validation guards (§13, R1).
"""
import os
import sys
from typing import Tuple, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.schemas import ComputationalResult, Plan
from tools.dispatcher import execute_computation


def run_computation(
    dataset: str = "GSE202768",
    contrast: Optional[str] = None,
    top_n_genes: int = 25,
    top_n_pathways: int = 5,
    padj_thresh: float = 0.05,
    plan: Optional[Plan] = None,
) -> Tuple[ComputationalResult, Dict[str, Any]]:
    """Execute deterministic computational analysis for target dataset, honoring Planner parameters."""
    target_ds = plan.dataset if plan is not None else dataset
    if contrast is None and plan is not None:
        contrast = f"{plan.comparison.group_a} vs {plan.comparison.group_b}"

    result = execute_computation(
        dataset=target_ds,
        contrast=contrast,
        top_n_genes=top_n_genes,
        top_n_pathways=top_n_pathways,
        padj_thresh=padj_thresh,
        plan=plan,
    )

    trace = {
        "agent": "computational_analyst",
        "llm_used": False,
        "dataset": result.dataset,
        "data_type": result.data_type,
        "inferential": result.inferential,
        "contrast": result.contrast,
        "genes_tested": result.n_total_tested,
        "significant_genes": result.n_sig,
        "up_regulated": result.n_up,
        "down_regulated": result.n_down,
        "execution_log": result.execution_log,
    }
    return result, trace
