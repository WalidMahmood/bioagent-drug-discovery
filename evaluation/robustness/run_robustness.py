"""Robustness Evaluation Suite (Master #33, #34).
Deterministic guardrail unit tests verifying system resilience against adversarial inputs:
- R1: Missing Metadata (Remove required sample annotations -> expected hard stop)
- R2: Inverted / Identical Comparison Groups (group_a == group_b -> expected flag/rejection)
- R3: Decoy Gene Injection (Fabricated gene not in expression data -> expected rejection)
- R4: Statistical Trap (Large fold-change but non-significant padj -> expected rejection)
- R5: §13 FPKM Count-Model Violation (DESeq2 proposed on FPKM data -> expected Critic FAIL)
- R6: No PASS-Laundering (Inverted direction claim pruned completely rather than gene-stripped)
Outputs summary into outputs/tables/robustness_results.csv.
"""
import os
import sys
from typing import Dict, Any
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agents import computational as CA
from agents import biology as BI
from agents import critic as CR
from agents.graph import _prune_failed_claims
from agents.schemas import Plan, Comparison, ComputationalResult, TopGene, Interpretation, InterpretationClaim
from tools.validation import validate_metadata


def test_r1_missing_metadata() -> Dict[str, Any]:
    """R1: Missing metadata field."""
    corrupt_meta = pd.DataFrame({"sample_id": ["S1", "S2", "S3"], "wrong_column": ["A", "B", "C"]})
    ok, errors, _ = validate_metadata(corrupt_meta, required=("group_dev",))
    detected = not ok and any("missing required metadata field" in e for e in errors)
    return {
        "Perturbation": "R1: Missing Metadata",
        "Test_Scope": "Deterministic Guardrail Unit Test",
        "Description": "Required design column removed from sample metadata",
        "Expected_Behavior": "Halt execution; refuse unannotated analysis",
        "Observed_Behavior": "Halted with validation error" if detected else "Failed to detect",
        "Detected": detected,
        "Safe_Completion": detected,
    }


def test_r2_identical_groups() -> Dict[str, Any]:
    """R2: Identical comparison groups (group_a == group_b)."""
    plan = Plan(
        analysis_goal="Evaluate response",
        dataset="GSE202768",
        comparison=Comparison(group_a="Control", group_b="Control"),
        design="~group",
        de_method="pydeseq2",
    )
    comp, _ = CA.run_computation(dataset="GSE202768")
    interp, _ = BI.interpret(comp, use_llm=False)
    verdict, _ = CR.verify(plan, comp, interp)
    detected = verdict.status == "FAIL" and any("R2" in e or "identical" in e.lower() for e in verdict.errors)
    return {
        "Perturbation": "R2: Identical Groups",
        "Test_Scope": "Deterministic Guardrail Unit Test",
        "Description": "Comparison specified with group_a == group_b",
        "Expected_Behavior": "Critic flags error; refuses circular comparison",
        "Observed_Behavior": "Critic flagged FAIL with comparison error" if detected else "Passed silently (Unsafe)",
        "Detected": detected,
        "Safe_Completion": detected,
    }


def test_r3_decoy_gene() -> Dict[str, Any]:
    """R3: Decoy gene injection."""
    plan = Plan(
        analysis_goal="Evaluate response",
        dataset="GSE202768",
        comparison=Comparison(group_a="KD_DOX", group_b="KD_noDOX"),
        design="~group_dev",
        de_method="pydeseq2",
    )
    comp, _ = CA.run_computation(dataset="GSE202768")
    interp = Interpretation(
        observations=["Analysis completed"],
        claims=[
            InterpretationClaim(
                statement="FABRICATED_DECOY_GENE is significantly up-regulated with high confidence.",
                type="observed",
                genes=["FABRICATED_DECOY_GENE"],
                pathways=[],
                hedged=False,
            )
        ],
        limitations=[],
        uncertainty=[],
    )
    verdict, _ = CR.verify(plan, comp, interp)
    detected = verdict.status == "FAIL" and any("FABRICATED_DECOY_GENE" in e for e in verdict.errors)
    return {
        "Perturbation": "R3: Decoy Gene Injection",
        "Test_Scope": "Deterministic Guardrail Unit Test",
        "Description": "Injected synthetic non-existent gene into claims",
        "Expected_Behavior": "Critic flags invented gene as absent from computation",
        "Observed_Behavior": "Flagged as absent/invented gene" if detected else "Passed hallucinated gene",
        "Detected": detected,
        "Safe_Completion": detected,
    }


def test_r4_statistical_trap() -> Dict[str, Any]:
    """R4: Statistical trap (large fold change but padj = 0.31)."""
    plan = Plan(
        analysis_goal="Evaluate response",
        dataset="GSE202768",
        comparison=Comparison(group_a="KD_DOX", group_b="KD_noDOX"),
        design="~group_dev",
        de_method="pydeseq2",
    )
    comp, _ = CA.run_computation(dataset="GSE202768")
    comp.top_genes.append(TopGene(gene="TRAP_GENE_1", log2FC=3.5, padj=0.31, direction="up"))
    interp = Interpretation(
        observations=["Analysis completed"],
        claims=[
            InterpretationClaim(
                statement="TRAP_GENE_1 is a strongly significant driver with log2FC=3.5.",
                type="observed",
                genes=["TRAP_GENE_1"],
                pathways=[],
                hedged=False,
            )
        ],
        limitations=[],
        uncertainty=[],
    )
    verdict, _ = CR.verify(plan, comp, interp)
    detected = verdict.status == "FAIL" and any(
        "statistical trap" in e.lower() or "padj confusion" in e.lower() for e in verdict.errors
    )
    return {
        "Perturbation": "R4: Statistical Trap",
        "Test_Scope": "Deterministic Guardrail Unit Test",
        "Description": "High log2FC (+3.5) with non-significant padj (0.31)",
        "Expected_Behavior": "Critic flags padj confusion / statistical trap",
        "Observed_Behavior": "Flagged as statistical trap (padj >= 0.05)" if detected else "Accepted false significance",
        "Detected": detected,
        "Safe_Completion": detected,
    }


def test_r5_fpkm_deseq2_violation() -> Dict[str, Any]:
    """R5: §13 Data-type violation (DESeq2 proposed on FPKM descriptive data)."""
    plan = Plan(
        analysis_goal="Analyze FPKM perturbation",
        dataset="GSE95304",
        data_type="fpkm",
        comparison=Comparison(group_a="shMyc", group_b="shSCR"),
        design="shMyc vs shSCR",
        de_method="DESeq2",
    )
    comp = ComputationalResult(
        dataset="GSE95304",
        data_type="FPKM descriptive ranking (no fake p-values)",
        inferential=False,
        contrast="shMyc vs shSCR",
        n_total_tested=100,
        n_sig=10,
        n_up=5,
        n_down=5,
        top_genes=[TopGene(gene="SNORD78", log2FC=11.05, padj=None, direction="up")],
        sig_pathways=[],
    )
    interp = Interpretation(
        observations=["Descriptive ranking complete."],
        claims=[
            InterpretationClaim(
                statement="SNORD78 shows higher expression at FDR < 0.05.",
                type="observed",
                genes=["SNORD78"],
                pathways=[],
                hedged=True,
            )
        ],
    )
    verdict, _ = CR.verify(plan, comp, interp)
    detected = verdict.status == "FAIL" and any("§13" in e for e in verdict.errors)
    return {
        "Perturbation": "R5: §13 FPKM Guardrail Violation",
        "Test_Scope": "Deterministic Guardrail Unit Test",
        "Description": "Planner selects DESeq2 and claim cites FDR < 0.05 on FPKM data",
        "Expected_Behavior": "Critic flags §13 data-type and fake-FDR violations",
        "Observed_Behavior": "Critic flagged FAIL with §13 violation" if detected else "Missed §13 violation",
        "Detected": detected,
        "Safe_Completion": detected,
    }


def test_r6_no_pass_laundering() -> Dict[str, Any]:
    """R6: Direction-inversion claim is pruned completely rather than gene-stripped into false PASS."""
    plan = Plan(
        analysis_goal="Evaluate response",
        dataset="GSE202768",
        comparison=Comparison(group_a="KD_DOX", group_b="KD_noDOX"),
        design="~group_dev",
        de_method="pydeseq2",
    )
    comp = ComputationalResult(
        dataset="GSE202768",
        data_type="counts (pydeseq2)",
        inferential=True,
        contrast="KD_DOX vs KD_noDOX",
        n_total_tested=100,
        n_sig=2,
        n_up=1,
        n_down=1,
        top_genes=[
            TopGene(gene="TGFBI", log2FC=1.95, padj=1e-20, direction="up"),
            TopGene(gene="PRRX1", log2FC=-2.28, padj=1e-25, direction="down"),
        ],
        sig_pathways=[],
    )
    bad_interp = Interpretation(
        observations=["Summary"],
        claims=[
            InterpretationClaim(
                statement="Downregulation of TGFBI is observed.",
                type="observed",
                genes=["TGFBI"],
                pathways=[],
                hedged=True,
            ),
            InterpretationClaim(
                statement="PRRX1 is strongly downregulated (log2FC=-2.28).",
                type="observed",
                genes=["PRRX1"],
                pathways=[],
                hedged=True,
            ),
        ],
    )
    v0, _ = CR.verify(plan, comp, bad_interp)
    pruned_dict, newly_pruned = _prune_failed_claims({"verdict": v0.model_dump(), "interp": bad_interp.model_dump()})
    pruned_interp = Interpretation(**pruned_dict)
    v1, _ = CR.verify(plan, comp, pruned_interp)

    detected = (
        v0.status == "FAIL"
        and len(newly_pruned) == 1
        and all("TGFBI" not in c.statement for c in pruned_interp.claims)
        and v1.status == "PASS"
    )
    return {
        "Perturbation": "R6: No PASS-Laundering",
        "Test_Scope": "Deterministic Guardrail Unit Test",
        "Description": "Inverted direction claim (TGFBI +1.95 claimed down) enters correction loop",
        "Expected_Behavior": "False prose claim pruned completely; surviving valid claim passes",
        "Observed_Behavior": "False claim pruned into pruned_claims; clean claim passed" if detected else "False text survived",
        "Detected": detected,
        "Safe_Completion": detected,
    }


def run_all_robustness() -> pd.DataFrame:
    """Execute complete deterministic robustness test suite (R1-R6)."""
    print("Running Robustness Suite (R1-R6)...")
    tests = [
        test_r1_missing_metadata,
        test_r2_identical_groups,
        test_r3_decoy_gene,
        test_r4_statistical_trap,
        test_r5_fpkm_deseq2_violation,
        test_r6_no_pass_laundering,
    ]

    results = []
    for t in tests:
        res = t()
        print(f"  {res['Perturbation']}: Detected={res['Detected']}")
        results.append(res)

    df = pd.DataFrame(results)
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_csv = os.path.join(base, "outputs", "tables", "robustness_results.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"Robustness results saved to: {out_csv}")
    return df


if __name__ == "__main__":
    df = run_all_robustness()
    print(df.to_string())
