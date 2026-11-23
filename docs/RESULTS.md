# BioAgent-Lite — Complete Measured Experiment Dossier

**Purpose:** Trace-backed inventory of every measured experiment in BioAgent-Lite, regenerated deterministically from `outputs/traces/*.json` via `python3 evaluation/metrics/rebuild_measured_artifacts.py`. Every table below cites its exact trace file and provenance status (`measured_llm`, `measured_fallback`, or `pending_local_gguf_run`). Zero synthetic curves or hardcoded multi-model constants are included.

---

## 1. Experimental Setup

| Item | Value |
|---|---|
| Target hardware | Consumer GPU (8 GB VRAM, NVIDIA RTX 5050), 16 GB RAM, zero cloud APIs |
| Inference runtime | `llama.cpp` CUDA OpenAI-compatible server on `127.0.0.1:8080` |
| Measured primary model | Google Gemma 3 4B IT (`Q8_K_XL`, 4.81 GB, context 8192) |
| Configured comparison models | MedGemma 4B IT (`Q8_K_XL`), Qwen3 8B IT (`Q4_K_M`) — status `pending_local_gguf_run` until local GGUF traces are collected |
| Deterministic statistics | `pydeseq2` (NB Wald GLM, BH-FDR), `gseapy` (GO/Reactome/KEGG), `scipy` Welch's t-test + BH-FDR for live uploads |
| Frozen thresholds | `padj < 0.05`, strong-effect `|log2FC| >= 1.0`, low-count filter `>= 10`, Critic max 2 correction iterations (`configs/thresholds.yaml`) |

---

## 2. Architecture Comparison on GSE202768 (Measured, Non-Tautological)

Source: `outputs/tables/architecture_comparison.csv` (recomputed from preserved traces using cited-gene DE scoring, word-boundary direction auditing, and normalized pathway matching).

| System | Model | Cited-Gene Precision | Cited-Gene Recall (vs Top-25) | Cited-Gene F1 | Statistical Accuracy | Direction Errors | Evidence Support Rate | Hallucination Rate | Latency (s) | Tokens | Provenance |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| LLM-only (Baseline 1) | Gemma-3-4B-IT-Q8 | 0.2000 | 0.0400 | 0.0667 | 0.2222 | 0 | 0.0000 | 0.7778 | 9.44 | 720 | `measured_llm` (`baseline_llm_only_GSE202768_20260906T181002Z.json`) |
| Single Tool-Agent (Baseline 2) | Gemma-3-4B-IT-Q8 | 1.0000 | 0.6000 | 0.7500 | 1.0000 | 0 | N/A (not logged in legacy trace) | 0.0000 | 19.59 | 1,772 | `measured_llm` (`baseline_single_agent_GSE202768_20260906T181011Z.json`) |
| **BioAgent-Lite (5-Agent Proposed)** | Gemma-3-4B-IT-Q8 | **1.0000** | 0.4400 | 0.6111 | 0.7857* | 3* | **0.5789** | **0.0000** | 25.46 | 2,756 | `measured_llm` (`eval_GSE202768_20260907T061142Z.json`) |

*\*Important remediation note:* Re-auditing the legacy pre-fix trace (`eval_GSE202768_20260907T061142Z.json`) with our fixed prose-level direction checker uncovered 3 direction inversions (`TGFBI`, `COL1A1`, `COL5A1`) that the legacy Critic had caught on iteration 0 and then masked by stripping gene tags instead of revising or dropping the claim. In the updated codebase (`agents/graph.py`, `agents/biology.py`, `agents/critic.py`), the Critic now re-prompts the Biological Interpreter with error feedback and drops the entire offending claim if still wrong—making PASS-laundering impossible on fresh runs.

---

## 3. Cross-Dataset Generalization Across 4 GEO Benchmarks (Measured)

Source: `outputs/tables/dataset_generalization.csv` (strictly derived from the latest `measured_llm` `eval_<DS>_*.json` traces).

| Dataset | Role | Organism | Data Type | Features Tested | Passed Threshold | Cited Genes | DE Precision | DE Recall (Top-25) | Statistical Accuracy | Direction Errors | Evidence Support Rate | Hallucination Rate | Latency (s) | Trace File |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **GSE202768** | Development | *Homo sapiens* | Raw Counts (`pydeseq2`) | 14,009 | 3,946 | 11 | 1.0000 | 0.4400 | 0.7857* | 3* | 0.5789 | 0.0000 | 25.46 | `eval_GSE202768_20260907T061142Z.json` |
| **GSE113650** | External Validation | *Homo sapiens* | CuffDiff (q-values) | 14,817 | 990 | 3 | 1.0000 | 0.1200 | 1.0000 | 0 | 0.7778 | 0.0000 | 5.58 | `eval_GSE113650_20260907T061208Z.json` |
| **GSE95304** | Held-Out Evaluation | *Homo sapiens* | FPKM (Descriptive §13) | 14,387 | 2,063 | 7 | 1.0000 | 0.2800 | 0.7000* | 3* | 0.7000 | 0.0000 | 19.42 | `eval_GSE95304_20260907T061231Z.json` |
| **GSE336903** | Cross-Species Smoke Test | *Mus musculus* | FPKM Cell-Line Matrix (Fig. 7, Descriptive §13) | 54,289 | 3,014 | 3 | 1.0000 | 0.1200 | 1.0000 | 0 | 0.7778 | 0.0000 | 4.89 | `eval_GSE336903_20260907T061251Z.json` |

Key findings:
- **Zero invented genes across all 4 datasets** (`Hallucination Rate = 0.0000`, `DE Precision = 1.0000`).
- **Normalized pathway matching** (`agents/evidence.py::normalize_pathway_term`) strips `GO`/`Reactome`/`KEGG` prefixes and parenthetical IDs, eliminating false `#ABSENT` penalties when an LLM cites a valid enriched pathway with its database prefix.
- **GSE336903 alignment:** Reconciled across `agents/planner.py`, `tools/dispatcher.py`, backend, and frontend as *Mus musculus* Fig. 7 cell-line FPKM (54,289 features; 2 previously hardcoded fake Reactome pathways removed from `dispatcher.py`).

---

## 4. Role Ablation Study on GSE202768 (Measured)

Source: `outputs/tables/ablation_results.csv` (preferring live-LLM traces from `20260907T0737–38Z`, transparently flagging fallback traces).

| Configuration | DE Precision | Cited Genes | Statistical Accuracy | Direction Errors | Evidence Support Rate | Critic Verdict | Latency (s) | Tokens | Provenance |
|---|---:|---:|---:|---:|---:|---|---:|---:|---|
| Full 5-Agent System | 1.0000 | 10 | 0.8000 | 3 | 0.6667 | PASS | 25.44 | 2,735 | `measured_llm` |
| w/o Critic (No Verification) | 1.0000 | 7 | **0.4286** | **4** | 0.7000 | N/A (Ablated) | 17.23 | 2,620 | `measured_llm` |
| w/o Evidence Retrieval | 1.0000 | 13 | 0.8000 | 3 | **0.0000** | FAIL | 18.70 | 2,702 | `measured_llm` |
| w/o Structured Planner | 1.0000 | 14 | 1.0000 | 0 | 0.6800 | FAIL | 15.75 | 2,015 | `measured_llm` |
| w/o Biological Interpreter | 0.0000 | 5 | 1.0000 | 0 | 0.0000 | PASS | 2.09 | 0 | `measured_fallback` |

Key observation: Removing the Critic drops statistical accuracy on the live LLM ablation batch to **42.86%** (4 direction errors), whereas removing Evidence Retrieval collapses Evidence Support Rate to **0.0000**. Re-running `python evaluation/ablations/run_ablations.py --dataset GSE202768` against a live local GGUF server will now exercise the remediated re-prompt/prune loop and top-25 parity.

---

## 5. Deterministic Robustness Guardrail Unit Tests (R1–R6)

Source: `outputs/tables/robustness_results.csv` (`evaluation/robustness/run_robustness.py` — explicitly labeled `Deterministic Guardrail Unit Test`).

| Test | Scenario | Target Component | Result |
|---|---|---|---|
| **R1** | Missing sample in metadata | `tools/validation.py` + `tools/dispatcher.py` | Detected (`ValueError` raised before DE) |
| **R2** | Hallucinated gene citation (`FAKEGENE_XYZ999`) | `agents/critic.py` | Detected (Critic `FAIL`) |
| **R3** | Direction inversion (`PRRX1` claimed up when `log2FC = -2.28`) | `agents/critic.py` | Detected (Critic `FAIL`) |
| **R4** | Unhedged causal & clinical overclaim | `agents/critic.py` | Detected (Critic `FAIL`) |
| **R5** | §13 FPKM guardrail violation (DESeq2 requested on FPKM) | `agents/critic.py` + `tools/validation.py` | Detected (Critic `FAIL` / count refusal) |
| **R6** | No PASS-laundering (untagged direction inversion in prose) | `agents/critic.py` + `agents/graph.py` | Detected (Critic `FAIL`, offending claim pruned) |

---

## 6. Multi-Model Comparison Policy (Measured-Only)

Source: `outputs/tables/model_comparison.csv`.

| Model | Status | Datasets Evaluated | Mean Latency (s) | Mean Stat Accuracy | Mean Evidence Support | Mean Hallucination Rate |
|---|---|---:|---:|---:|---:|---:|
| **Gemma 3 4B IT (Q8_K_XL)** | `measured` | 4 | 13.84 | 0.8714 | 0.7086 | 0.0000 |
| MedGemma 4B IT (Q8_K_XL) | `pending_local_gguf_run` | 0 | N/A | N/A | N/A | N/A |
| Qwen3 8B IT (Q4_K_M) | `pending_local_gguf_run` | 0 | N/A | N/A | N/A | N/A |

All previously hardcoded 24-condition synthetic matrices, synthetic Beta/exponential ROC curves, and unmeasured MedGemma/Qwen3 radar plots have been removed from the tables, manifest, and plot generators. To populate MedGemma and Qwen3 rows with real measurements, start `llama-server` with the corresponding GGUF weights and run `python evaluation/models/compare_models.py`.
