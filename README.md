# BioAgent-Lite: Resource-Efficient Multi-Agent Transcriptomics Analysis

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi.tiangolo&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg?logo=react&logoColor=black)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**BioAgent-Lite** is a local-first, five-agent transcriptomics analysis framework orchestrated with LangGraph. Every numerical calculation (differential expression, FDR adjustment, and pathway over-representation) is executed deterministically in Python (`pydeseq2`, `scipy`, `gseapy`), while local quantized LLMs handle structured planning and biological interpretation under strict schema, data-type (§13), evidence-lineage, and deterministic Critic verification guardrails.

---

## Architecture

1. **Planner Agent (`agents/planner.py`):** Emits a validated JSON execution plan enforcing the **§13 Data-Type Refusal Guard** (forbidding count-based negative-binomial models on normalized FPKM matrices).
2. **Computational Analyst (`agents/computational.py`, `tools/dispatcher.py`):** Runs metadata validation (`R1`), count-matrix checks (`§13`), and deterministic DE/enrichment loading across raw counts, CuffDiff tables, and descriptive FPKM datasets.
3. **Biological Interpreter (`agents/biology.py`):** Produces typed, hedged claims (`observed`, `supported`, `hypothesis`) from top-25 differential genes and enriched pathways, with dynamic count-vs-FPKM prompting and Critic-feedback revision support.
4. **Evidence Retriever (`agents/evidence.py`):** Links every cited gene and normalized pathway term (`GO`/`Reactome`/`KEGG` prefix- and ID-normalized) to exact computed source artifacts (`#ABSENT` stamped when unsupported).
5. **Adversarial Critic & Bounded Self-Correction (`agents/critic.py`, `agents/graph.py`):** Audits comparison validity, §13 data-type compliance, invented genes, statistical traps, prose- and tag-level direction concordance, hedging, and non-clinical disclaimers. On `FAIL`, the graph re-prompts the Biological Interpreter with error feedback and drops any still-failing claim in full into `pruned_claims` (preventing PASS-laundering).

---

## Measured Results (Trace-Backed Only)

All numbers below are computed deterministically from preserved JSON traces in `outputs/traces/` via `python3 evaluation/metrics/rebuild_measured_artifacts.py`. Full audit in [`docs/RESULTS.md`](docs/RESULTS.md).

### Architecture Comparison on GSE202768 (`outputs/tables/architecture_comparison.csv`)

| System | Cited-Gene Precision | Cited-Gene Recall (Top-25) | Statistical Accuracy | Evidence Support Rate | Hallucination Rate | Latency (s) |
|---|---:|---:|---:|---:|---:|---:|
| LLM-Only (Baseline 1) | 20.0% | 4.0% | 22.2% | 0.0% | 77.8% | 9.44 |
| Single Tool-Agent (Baseline 2) | 100.0% | 60.0% | 100.0% | N/A (legacy trace) | 0.0% | 19.59 |
| **BioAgent-Lite (5-Agent)** | **100.0%** | 44.0% | 78.6%* | **57.9%** | **0.0%** | 25.46 |

### Cross-Dataset Generalization (`outputs/tables/dataset_generalization.csv`, Gemma 3 4B IT)

| Dataset | Organism | Data Type | Features Tested | DE Precision | Statistical Accuracy | Evidence Support (Normalized) | Hallucination Rate |
|---|---|---|---:|---:|---:|---:|---:|
| **GSE202768** | *Homo sapiens* | Raw Counts (`pydeseq2`) | 14,009 | 100.0% | 78.6%* | 57.9% | 0.0% |
| **GSE113650** | *Homo sapiens* | CuffDiff (`q < 0.05`) | 14,817 | 100.0% | 100.0% | 77.8% | 0.0% |
| **GSE95304** | *Homo sapiens* | FPKM (Descriptive §13) | 14,387 | 100.0% | 70.0%* | 70.0% | 0.0% |
| **GSE336903** | *Mus musculus* | Cell-Line FPKM (Fig. 7, §13) | 54,289 | 100.0% | 100.0% | 77.8% | 0.0% |

*\*Legacy pre-fix traces recorded before the two-stage Critic revision/pruning fix; re-running with a live local LLM exercises the remediated loop.*

- **Role Ablation (`outputs/tables/ablation_results.csv`):** Removing the Critic lowers live-LLM statistical accuracy on `GSE202768` to **42.9%** (4 direction errors); removing Evidence Retrieval drops Evidence Support Rate to **0.0%**.
- **Deterministic Guardrail Unit Tests (`outputs/tables/robustness_results.csv`):** **6/6 detected** (R1–R6: corrupted metadata, invented gene, direction inversion, unhedged clinical overclaim, §13 FPKM violation, and no PASS-laundering).
- **Multi-Model Policy (`outputs/tables/model_comparison.csv`):** Gemma 3 4B IT is `measured` across all 4 datasets; MedGemma 4B IT and Qwen3 8B IT are explicitly marked `pending_local_gguf_run` until local GGUF traces are recorded.

---

## Quickstart

```bash
pip install -r requirements.txt

# Recompute all measured evaluation tables & manifest from preserved traces (stdlib only)
python3 evaluation/metrics/rebuild_measured_artifacts.py

# Run deterministic unit & guardrail tests
python3 -m unittest discover -s tests -v

# Optional: start local llama.cpp server and run live headless evaluations
python experiments/development/run_dev.py            # or --no-llm for deterministic mode
python evaluation/baselines/run_all_baselines.py
python evaluation/ablations/run_ablations.py --dataset GSE202768
python evaluation/robustness/run_robustness.py
python evaluation/run_all_datasets.py

# Web Workbench (FastAPI backend + React/Vite frontend)
python backend/main.py
cd frontend && npm install && npm run dev
```

### Live CSV/TSV Upload Engine

Uploading any expression matrix in the web UI (or via `POST /api/upload` + `POST /api/run`) executes dataset-agnostic Welch's t-test + Benjamini-Hochberg FDR (or §13 descriptive log2FC ranking when non-integer floats are detected), attempts live GSEApy Enrichr over-representation (falling back transparently to statistical-only mode offline), generates data-driven plots, runs the deterministic Critic over dynamically synthesized claims, and exposes real `/api/genes/{dataset}` CSV, `/api/trace/{dataset}` JSON, and PDF report downloads.

---

## Documentation

- [`docs/RESULTS.md`](docs/RESULTS.md) — Complete measured experiment dossier & trace index
- [`docs/EXPLAINABILITY.md`](docs/EXPLAINABILITY.md) — Epistemic layers, Critic checks, and live/replay provenance ledger
- [`docs/methodology.md`](docs/methodology.md) — Statistical methodology & thresholds
- [`docs/reproducibility.md`](docs/reproducibility.md) — Reproduction commands
- [`outputs/reports/final_report.md`](outputs/reports/final_report.md) — Measured-only thesis report summary

---

## License

MIT — Research and educational use only. Not approved for clinical diagnosis or treatment decisions.
