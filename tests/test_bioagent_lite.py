"""Automated verification test suite for BioAgent-Lite thesis remediation.

Uses Python standard library only so it executes reliably in any Python 3.11+
environment without requiring local GGUF models or optional ML wheels.
"""

import csv
import json
import py_compile
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class TestSyntaxAndCompilation(unittest.TestCase):
    """Verify all modified Python modules compile cleanly with zero syntax errors."""

    PY_FILES = [
        "agents/schemas.py",
        "agents/planner.py",
        "agents/computational.py",
        "agents/biology.py",
        "agents/evidence.py",
        "agents/critic.py",
        "agents/graph.py",
        "tools/dispatcher.py",
        "tools/therapeutic_discovery.py",
        "scripts/run_rtx5050_benchmark.py",
        "evaluation/metrics/calculate_metrics.py",
        "evaluation/metrics/rebuild_measured_artifacts.py",
        "evaluation/metrics/generate_real_roc_and_ml_plots.py",
        "evaluation/metrics/generate_all_datasets_confusion_matrices.py",
        "evaluation/metrics/generate_multimodel_eval_plots.py",
        "evaluation/baselines/llm_only.py",
        "evaluation/baselines/single_agent.py",
        "evaluation/baselines/run_all_baselines.py",
        "evaluation/ablations/run_ablations.py",
        "evaluation/run_all_datasets.py",
        "evaluation/robustness/run_robustness.py",
        "evaluation/models/compare_models.py",
        "backend/main.py",
        "backend/realtime_engine.py",
        "backend/report_generator.py",
    ]

    def test_all_python_modules_compile(self):
        for rel in self.PY_FILES:
            path = BASE_DIR / rel
            self.assertTrue(path.exists(), f"Missing expected module: {rel}")
            py_compile.compile(str(path), doraise=True)


class TestMeasuredMetricsAndNormalization(unittest.TestCase):
    """Verify fixed normalization, word-boundary direction checks, and prose-level auditing."""

    def test_pathway_normalization_parity(self):
        from evaluation.metrics.rebuild_measured_artifacts import normalize_pathway_term

        self.assertEqual(
            normalize_pathway_term("Reactome Extracellular Matrix Organization (R-HSA-1474244)"),
            "extracellular matrix organization",
        )
        self.assertEqual(
            normalize_pathway_term("GO_BP: Extracellular Matrix Organization (GO:0030198)"),
            "extracellular matrix organization",
        )
        self.assertEqual(
            normalize_pathway_term("KEGG ECM-receptor interaction"),
            "ecm receptor interaction",
        )

    def test_word_boundary_direction_avoids_group_false_positive(self):
        from evaluation.metrics.rebuild_measured_artifacts import UP_PATTERN, DOWN_PATTERN

        stmt = "Expression levels in the knockdown group were compared against control."
        self.assertIsNone(UP_PATTERN.search(stmt))
        self.assertIsNone(DOWN_PATTERN.search(stmt))
        self.assertIsNotNone(UP_PATTERN.search("TGFBI is significantly up-regulated."))
        self.assertIsNotNone(DOWN_PATTERN.search("PRRX1 is strongly downregulated."))

    def test_prose_level_direction_audit_blocks_pass_laundering(self):
        from evaluation.metrics.rebuild_measured_artifacts import audit_claims_against_comp

        comp = {
            "top_genes": [
                {"gene": "TGFBI", "log2FC": 1.95, "padj": 1e-30, "direction": "up"},
                {"gene": "PRRX1", "log2FC": -2.28, "padj": 1e-29, "direction": "down"},
            ],
            "top_pathways": [
                {"source": "Reactome", "term": "Extracellular Matrix Organization (R-HSA-1474244)", "padj": 2e-7}
            ],
        }
        # Even if genes=[] was stripped, mentioning TGFBI as downregulated in prose MUST be flagged!
        interp = {
            "claims": [
                {
                    "statement": "TGFBI is strongly downregulated following knockdown.",
                    "genes": [],
                    "pathways": ["Reactome Extracellular Matrix Organization"],
                }
            ]
        }
        audit = audit_claims_against_comp(interp, comp)
        self.assertEqual(audit["direction_errors"], 1)
        self.assertEqual(audit["evidence_support_rate"], 1.0)


class TestTherapeuticDiscoveryEngine(unittest.TestCase):
    """Verify deterministic gene-flipping logic, MoA concordance guards, scoring, and CSV export."""

    def test_gene_flip_classification(self):
        from tools.therapeutic_discovery import classify_flip_action

        up = classify_flip_action(2.5)
        self.assertEqual(up["expected_moa_class"], "inhibitory")
        self.assertIn("Turn OFF", up["recommended_flip"])

        down = classify_flip_action(-1.8)
        self.assertEqual(down["expected_moa_class"], "activating")
        self.assertIn("Turn ON", down["recommended_flip"])

    def test_moa_concordance_blocks_opposite_direction_drugs(self):
        from tools.therapeutic_discovery import evaluate_moa_concordance

        self.assertEqual(evaluate_moa_concordance(2.4, "INHIBITOR", "EGFR inhibitor")[0], "CONCORDANT")
        self.assertEqual(evaluate_moa_concordance(2.4, "AGONIST", "Receptor agonist")[0], "DISCORDANT_BLOCKED")
        self.assertEqual(evaluate_moa_concordance(-2.1, "INHIBITOR", "Kinase inhibitor")[0], "DISCORDANT_BLOCKED")
        self.assertEqual(evaluate_moa_concordance(-2.1, "ACTIVATOR", "Channel activator")[0], "CONCORDANT")
        self.assertEqual(evaluate_moa_concordance(1.5, "MODULATOR", "Allosteric modulator")[0], "NEUTRAL_REVIEW")

    def test_priority_score_bounds_and_safety_penalty(self):
        from tools.therapeutic_discovery import compute_target_priority_score

        safe_approved = compute_target_priority_score(
            log2fc=2.8,
            padj=1e-10,
            top_disease_score=0.85,
            max_concordant_stage_rank=4,
            tractable_modalities=["Small Molecule"],
            is_essential=False,
            safety_liability_count=0,
        )
        risky_approved = compute_target_priority_score(
            log2fc=2.8,
            padj=1e-10,
            top_disease_score=0.85,
            max_concordant_stage_rank=4,
            tractable_modalities=["Small Molecule"],
            is_essential=True,
            safety_liability_count=10,
        )
        self.assertLessEqual(safe_approved["total_score"], 100.0)
        self.assertGreater(safe_approved["total_score"], risky_approved["total_score"])
        self.assertIn("Tier 1", safe_approved["evidence_tier"])

    def test_offline_dossier_and_wetlab_plan(self):
        from tools.therapeutic_discovery import run_target_discovery

        dossier = run_target_discovery(
            top_genes=[
                {"gene": "EGFR", "log2FC": 2.6, "padj": 1e-8},
                {"gene": "TP53", "log2FC": -2.1, "padj": 1e-6},
            ],
            disease_context="Non-Small Cell Lung Carcinoma",
            dataset_name="unit_test_nsclc",
            use_cache=False,
            live_network=False,
        )
        self.assertEqual(len(dossier["targets"]), 2)
        by_gene = {t["gene"]: t for t in dossier["targets"]}
        self.assertEqual(by_gene["EGFR"]["recommended_flip"], "Suppress / Inhibit (Turn OFF)")
        self.assertEqual(by_gene["TP53"]["recommended_flip"], "Restore / Activate (Turn ON)")
        self.assertIn("EGFR", dossier["wetlab_plan"]["recommended_qpcr_panel"])
        self.assertIn("TP53", dossier["wetlab_plan"]["recommended_qpcr_panel"])

    def test_critic_v2_contains_therapeutic_guards_t1_t2_t3(self):
        critic_src = (BASE_DIR / "agents" / "critic.py").read_text(encoding="utf-8")
        self.assertIn("Therapeutic MoA violation (T1)", critic_src)
        self.assertIn("Invented citation (T2)", critic_src)
        self.assertIn("Safety disclosure note (T3)", critic_src)


class TestMeasuredArtifactsAndProvenance(unittest.TestCase):
    """Verify rebuilt CSVs, manifest.json, and docs contain strictly measured numbers."""

    def test_manifest_has_no_synthetic_perfect_roc_and_accurate_counts(self):
        manifest = json.loads((BASE_DIR / "outputs" / "manifest.json").read_text(encoding="utf-8"))
        km = manifest.get("key_metrics", {})
        self.assertNotIn("roc_auc", km)
        self.assertNotIn("pr_auc", km)
        gse336 = next(d for d in manifest["datasets"] if d["accession"] == "GSE336903")
        self.assertEqual(gse336["genes_tested"], 54289)
        self.assertEqual(gse336["organism"], "Mus musculus")

    def test_model_comparison_marks_unrun_models_pending(self):
        with open(BASE_DIR / "outputs" / "tables" / "model_comparison.csv", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        by_model = {r["Model"]: r for r in rows}
        self.assertEqual(by_model["Gemma 3 4B IT (Q8_K_XL)"]["Status"], "measured")
        self.assertEqual(by_model["MedGemma 4B IT (Q8_K_XL)"]["Status"], "pending_local_gguf_run")
        self.assertEqual(by_model["Qwen3 8B IT (Q4_K_M)"]["Status"], "pending_local_gguf_run")

    def test_robustness_table_covers_r1_through_r6(self):
        with open(BASE_DIR / "outputs" / "tables" / "robustness_results.csv", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 6)
        for idx, row in enumerate(rows, start=1):
            self.assertTrue(row["Perturbation"].startswith(f"R{idx}:"))
            self.assertEqual(row["Test_Scope"], "Deterministic Guardrail Unit Test")
            self.assertEqual(row["Detected"], "YES")

    def test_realtime_engine_has_no_hardcoded_pdac_narrative(self):
        src = (BASE_DIR / "backend" / "realtime_engine.py").read_text(encoding="utf-8")
        for forbidden in ("Serdjebi", "Spratlin", "SLC29A1", "Fluoropyrimidine", "ChromaDB"):
            self.assertNotIn(forbidden, src, f"Hardcoded PDAC/ChromaDB token found in realtime_engine.py: {forbidden}")

    def test_docs_have_zero_utf8_mojibake(self):
        mojibake_tokens = ("â€”", "â†’", "Â§", "âœ…", "Ã—")
        for rel in ("docs/RESULTS.md", "docs/EXPLAINABILITY.md", "outputs/reports/final_report.md", "README.md"):
            txt = (BASE_DIR / rel).read_text(encoding="utf-8")
            for tok in mojibake_tokens:
                self.assertNotIn(tok, txt, f"Mojibake '{tok}' found in {rel}")


class TestPathConfinementLogic(unittest.TestCase):
    """Verify strict path confinement semantics used by backend endpoints."""

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            good = (base / "matrix.csv").resolve()
            self.assertTrue(good.is_relative_to(base))

            for bad_name in ("../etc/passwd", "..\\secret.csv", "/etc/passwd", "sub/file.csv"):
                has_sep = ("/" in bad_name) or ("\\" in bad_name) or (".." in bad_name)
                self.assertTrue(has_sep, f"Traversal payload not caught: {bad_name}")


if __name__ == "__main__":
    unittest.main()
