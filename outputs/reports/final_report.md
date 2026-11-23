# BioAgent-Lite: A Resource-Efficient Multi-Agent Framework for Reliable Gene-Expression Analysis

**Domain:** Transcriptomics / Bulk RNA-seq Analysis  
**Target Hardware:** Consumer GPU (8 GB VRAM, 16 GB RAM)  
**Inference Runtime:** Local GGUF via `llama.cpp` CUDA server (zero cloud API dependencies)  
**Provenance Policy:** All quantitative results in this report are strictly derived from preserved execution traces in `outputs/traces/*.json` via `evaluation/metrics/rebuild_measured_artifacts.py`. Synthetic multi-model tables and simulated ROC curves have been excluded.

---

## Abstract

Applying unconstrained large language models (LLMs) directly to computational transcriptomics frequently leads to fabricated gene lists, invalid statistical modeling on normalized FPKM matrices, and directional inversions in biological summaries. **BioAgent-Lite** addresses these failure modes through a five-agent LangGraph architecture running on consumer hardware: (1) a constrained **Planner**, (2) a deterministic **Computational Analyst** (`pydeseq2`, `gseapy`, Welch/BH-FDR), (3) an evidence-hedged **Biological Interpreter**, (4) a lineage-tracking **Evidence Retriever**, and (5) a deterministic **Critic / Verifier** enforcing a bounded self-correction loop.

Evaluating preserved Gemma 3 4B IT (`Q8_K_XL`) traces across four GEO transcriptomic benchmarks (`GSE202768`, `GSE113650`, `GSE95304`, `GSE336903`) using non-tautological cited-gene scoring and prose-level direction auditing demonstrates:
1. Deterministic tool delegation raises cited-gene precision from **20.0%** (LLM-only baseline) to **100.0%** across all four GEO datasets, cutting invented-gene hallucinations from **77.8%** to **0.0%**;
2. Removing the Critic in live-LLM ablations on `GSE202768` drops statistical accuracy to **42.9%** (4 direction errors), while removing Evidence Retrieval drops Evidence Support Rate to **0.0%**;
3. Auditing legacy traces revealed that stripping gene tags without rewriting prose allowed residual direction errors—remediated in the current codebase by two-stage Critic self-correction (Biology re-prompting followed by full-claim pruning) and verified across a 6-test deterministic guardrail suite (R1–R6, **6/6 detected**).

---

## 1. Benchmark Dataset Suite

| Dataset | Organism | Data Type | Features Tested | Passed Threshold | Benchmark Role |
|---|---|---|---:|---:|---|
| **GSE202768** | *Homo sapiens* | Raw Counts (`pydeseq2`, Wald NB) | 14,009 | 3,946 (`padj < 0.05`) | Development & Tuning |
| **GSE113650** | *Homo sapiens* | CuffDiff Statistical Table | 14,817 | 990 (`q < 0.05`) | External Validation |
| **GSE95304** | *Homo sapiens* | FPKM Archives (Descriptive §13) | 14,387 | 2,063 (`\|log2FC\| >= 1.0`) | Held-Out Evaluation |
| **GSE336903** | *Mus musculus* | Cell-Line FPKM Matrix (Fig. 7, Descriptive §13) | 54,289 | 3,014 (`\|log2FC\| >= 1.0`) | Cross-Species Smoke Test |

---

## 2. Measured Architecture Comparison (`GSE202768`)

Source: `outputs/tables/architecture_comparison.csv`.

| System | Model | Cited-Gene Precision | Cited-Gene Recall (Top-25) | Cited-Gene F1 | Statistical Accuracy | Direction Errors | Evidence Support Rate | Hallucination Rate | Latency (s) | Tokens |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LLM-only (Baseline 1) | Gemma-3-4B-IT-Q8 | 0.2000 | 0.0400 | 0.0667 | 0.2222 | 0 | 0.0000 | 0.7778 | 9.44 | 720 |
| Single Tool-Agent (Baseline 2) | Gemma-3-4B-IT-Q8 | 1.0000 | 0.6000 | 0.7500 | 1.0000 | 0 | N/A (legacy trace) | 0.0000 | 19.59 | 1,772 |
| **BioAgent-Lite (5-Agent Proposed)** | Gemma-3-4B-IT-Q8 | **1.0000** | 0.4400 | 0.6111 | 0.7857* | 3* | **0.5789** | **0.0000** | 25.46 | 2,756 |

*\*Legacy pre-fix trace (`eval_GSE202768_20260907T061142Z.json`): the Critic caught 3 direction errors on iteration 0 (`TGFBI`, `COL1A1`, `COL5A1`), and the legacy gene-tag stripper left those symbols in prose. The remediated `agents/graph.py` re-prompts the Biology agent with error feedback and prunes any still-failing claim in full.*

---

## 3. Measured Cross-Dataset Generalization (4 GEO Datasets)

Source: `outputs/tables/dataset_generalization.csv`.

| Dataset | Role | DE Precision | Cited Genes | Statistical Accuracy | Direction Errors | Evidence Support Rate (Normalized) | Hallucination Rate | Latency (s) | Provenance |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **GSE202768** | Development | 1.0000 | 11 | 0.7857 | 3 | 0.5789 | 0.0000 | 25.46 | `measured_llm` |
| **GSE113650** | External Validation | 1.0000 | 3 | 1.0000 | 0 | 0.7778 | 0.0000 | 5.58 | `measured_llm` |
| **GSE95304** | Held-Out (FPKM §13) | 1.0000 | 7 | 0.7000 | 3 | 0.7000 | 0.0000 | 19.42 | `measured_llm` |
| **GSE336903** | Smoke Test (*M. musculus* FPKM) | 1.0000 | 3 | 1.0000 | 0 | 0.7778 | 0.0000 | 4.89 | `measured_llm` |

Across all four datasets, BioAgent-Lite maintained **100.0% cited-gene precision**, **0.0% invented-gene hallucination**, **87.1% mean statistical accuracy**, and **70.9% mean normalized evidence support** at a mean latency of **13.84 seconds**.

---

## 4. Role Ablation Study (`GSE202768`)

Source: `outputs/tables/ablation_results.csv`.

| Configuration | DE Precision | Statistical Accuracy | Direction Errors | Evidence Support Rate | Latency (s) | Provenance |
|---|---:|---:|---:|---:|---:|---|
| Full 5-Agent System | 1.0000 | 0.8000 | 3 | 0.6667 | 25.44 | `measured_llm` |
| w/o Critic (No Verification) | 1.0000 | **0.4286** | **4** | 0.7000 | 17.23 | `measured_llm` |
| w/o Evidence Retrieval | 1.0000 | 0.8000 | 3 | **0.0000** | 18.70 | `measured_llm` |
| w/o Structured Planner | 1.0000 | 1.0000 | 0 | 0.6800 | 15.75 | `measured_llm` |
| w/o Biological Interpreter | 0.0000 | 1.0000 | 0 | 0.0000 | 2.09 | `measured_fallback` |

---

## 5. Deterministic Robustness Guardrail Suite (R1–R6)

Source: `outputs/tables/robustness_results.csv`.

- **R1 (Corrupted Metadata):** `validate_metadata()` rejects missing sample IDs before DE execution.
- **R2 (Hallucinated Gene):** Critic rejects `FAKEGENE_XYZ999` absent from computed results.
- **R3 (Direction Inversion):** Critic catches `PRRX1` (`log2FC = -2.28`) claimed upregulated.
- **R4 (Unhedged Causal/Clinical Claim):** Critic blocks non-hedged certainty verbs and missing disclaimer.
- **R5 (§13 FPKM Guardrail Violation):** Critic and `assert_is_counts()` reject DESeq2 on FPKM data.
- **R6 (No PASS-Laundering):** Critic flags prose-level direction inversions even with `genes=[]`, and the correction loop prunes the failing claim rather than stripping tags.

---

## 6. Model Evaluation Status & Limitations

- **Measured Model:** Gemma 3 4B IT (`Q8_K_XL`) is fully trace-backed across all 4 GEO datasets (`outputs/tables/model_comparison.csv`).
- **Pending Models:** MedGemma 4B IT and Qwen3 8B IT are configured in `configs/models.yaml` and `evaluation/models/compare_models.py` with status `pending_local_gguf_run` so they can be benchmarked locally when their GGUF weights are mounted—no unmeasured estimates are reported.
- **Evidence Corpus Scope:** Current runtime evidence grounding is deterministic lookup against computed DE and enrichment tables; vector-database literature retrieval remains optional future work.
