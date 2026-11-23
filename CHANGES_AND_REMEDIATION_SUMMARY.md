# BioAgent-Lite — Full Remediation, Therapeutic Discovery Upgrade & RTX 5050 Guide

This document provides a complete, exact record of every scientific, architectural, security, and UI remediation implemented across **BioAgent-Lite**, followed by the new **Therapeutic Target & Drug Discovery Engine** and a step-by-step **RTX 5050 (8 GB) local model guide**.

---

## Part 1 — Phase 1 Thesis Remediation (Scientific Rigor & Publication Readiness)

### 1. Multi-Agent Core & Closed-Loop Critic Self-Correction
- **`agents/graph.py` & `agents/biology.py`**: Replaced legacy gene-tag stripping (which could strip `"genes": [...]` while leaving inverted prose untouched) with true closed-loop correction:
  1. On Critic failure, re-prompts the Biological Interpreter LLM with explicit error diagnostics (`critic_feedback` + previous draft).
  2. If a claim still fails verification (or in deterministic mode), prunes the entire failing claim object into `interp.pruned_claims` rather than laundering invalid statements into `PASS`.
- **`agents/critic.py` & `agents/evidence.py`**:
  - Added unified `normalize_pathway_term()` stripping `GO_BP:`, `Reactome`, `KEGG` prefixes and parenthetical IDs (`R-HSA-*`, `GO:*`, `hsa*`) so Evidence Retriever and Critic agree identically.
  - Switched direction matching to word-boundary regexes (fixing substring false positives like `"group"` matching `"up"`).
  - Enforced prose-level direction auditing even if `claim.genes` is empty.
  - Added **§13 Descriptive FPKM Guard**: blocks count-based methods (`DESeq2`/`edgeR`) on FPKM/TPM matrices and rejects fabricated `FDR < 0.05` / `padj < 0.05` claims when `padj=N/A`.
- **`agents/schemas.py`**: Added `inferential: bool`, `pruned_claims: List[str]`, and defensive list coercion for compact 4B/8B local LLMs.
- **`tools/dispatcher.py`**: Fixed `run_enrichment()` return signature to return both `(sig_pathways, execution_log)`.

### 2. Measured-Only Evaluation Artifacts & Reproducibility
- **`evaluation/metrics/rebuild_measured_artifacts.py`**: Created a deterministic parser that rebuilds all CSV tables (`outputs/tables/*.csv`) and `outputs/manifest.json` directly from real saved `outputs/traces/*.json` files.
- **Removed Synthetic/Hardcoded Numbers**:
  - Removed synthetic perfect `ROC-AUC = 1.00` / `PR-AUC = 1.00` entries and fabricated `MedGemma 4B` / `Qwen3 8B` scores; unrun local models are transparently labeled `pending_local_gguf_run` until executed on your RTX 5050.
  - Corrected `GSE336903` metadata across tables, manifest, and docs (`54,289` *Mus musculus* Fig. 7 cell-line FPKM features; `3,014` with `|log2FC| >= 1.0`).
  - Labeled `R1–R6` robustness tests accurately as deterministic guardrail unit tests (`6/6`).
- **Fixed Encoding & Documentation Consistency**: Eliminated UTF-8 mojibake and synchronized numbers across `README.md`, `docs/RESULTS.md`, `docs/EXPLAINABILITY.md`, and `outputs/reports/final_report.md`.

### 3. Web App & Backend Integrity
- **Removed Hardcoded PDAC Narratives (`backend/realtime_engine.py`)**: Replaced hardcoded gemcitabine text with dataset-agnostic statistical computation (Welch's t-test + Benjamini-Hochberg FDR for integer counts; §13 descriptive log2FC ranking for continuous FPKM/TPM matrices) and data-driven summaries.
- **Real Downloads & Honest Telemetry (`backend/main.py` & `frontend/apiMiddleware.ts`)**:
  - `/api/genes/{dataset}`, `/api/trace/{dataset}`, and `/api/report/analysis_pdf` serve real computed CSVs, JSON traces, and PDF reports.
  - Added strict path confinement (`safeResolve`), 25 MB upload caps, and `.csv/.tsv/.txt` allowlists.
  - Added root `package.json` and Vite dev/preview API middleware listening on `0.0.0.0:3000` so the web workbench runs cleanly out of the box.

---

## Part 2 — Therapeutic Target & Drug Discovery Engine (Cancer + General Disease)

To move BioAgent-Lite from an RNA-seq summary prototype to a **general-purpose cancer and disease therapeutic discovery workbench**, we added four major capabilities backed by live, free, gold-standard biomedical APIs (zero mock drugs or fabricated citations):

1. **Deterministic Target & Drug Discovery Engine (`tools/therapeutic_discovery.py` + `frontend/apiMiddleware.ts`)**:
   - **Open Targets Platform v4 GraphQL**: Maps top differential genes to Ensembl IDs and retrieves real target tractability (small molecule / antibody / PROTAC), cancer & general-disease genetic associations, DepMap/Open Targets pan-essentiality flags, recorded safety liabilities, and clinical/FDA-approved drugs (`drugAndClinicalCandidates`).
   - **Gene-Flipping Direction Engine**: Classifies every differential target into a concrete perturbation strategy:
     - **Upregulated (`log2FC > 0`)** → `Suppress / Inhibit (Turn OFF)` (expects inhibitory MoAs: inhibitor, antagonist, blocker, degrader).
     - **Downregulated (`log2FC < 0`)** → `Restore / Activate (Turn ON)` (expects activating MoAs: agonist, activator, positive modulator).
   - **Mechanism-of-Action (MoA) Concordance Audit**: Automatically classifies every drug candidate as `CONCORDANT`, `DISCORDANT_BLOCKED`, or `NEUTRAL_REVIEW`, preventing contradictory recommendations (e.g., blocking an inhibitor for an already downregulated tumor suppressor).
   - **Transparent Target Priority Score (0–100)**: Combines four visible sub-scores — Transcriptomic Effect (0–30), Disease Genetic Evidence (0–25), Druggability & Clinical Stage (0–25), and Selectivity/Safety (0–20) — and assigns Evidence Tiers (`Tier 1: Approved Drug Repurposing`, `Tier 2: Clinical / Tractable Candidate`, `Tier 3: Novel Genetic Flip Target`).
   - **Live NCBI PubMed + ClinicalTrials.gov v2 Grounding**: Fetches real, clickable `PMIDs` and `NCT` clinical trial IDs directly for prioritized targets in the selected disease context.
   - **Suggested Next Wet-Lab Validation Plan**: Generates a concrete, researcher-ready checklist (drug viability dose-response, siRNA/CRISPRi flip test, and 5-gene RT-qPCR validation panel).

2. **Adversarial Critic v2 (`agents/critic.py`)**:
   - **T1 MoA Concordance Guard**: Fails claims recommending any blocked discordant drug or proposing opposite-direction pharmacological modulation.
   - **T2 Citation Existence Guard**: Fails claims citing any `PMID` or `NCT` trial ID not present in the deterministic PubMed / ClinicalTrials.gov tool output.
   - **T3 Safety Disclosure Check**: Flags targets that are pan-essential or carry >=5 safety liabilities when recommended without toxicity caveats.

3. **Upgraded Prompts & LangGraph Integration (`agents/biology.py`, `agents/graph.py`, `agents/schemas.py`)**:
   - Biological Interpreter prompt now integrates Open Targets targets, concordant drugs, verified PMIDs, and NCT trial IDs with explicit MoA and citation guardrails for local 4B–8B LLMs.

4. **Researcher-Friendly Web Workbench UI (`frontend/src/components/TherapeuticDossier.tsx`, `ChatMessage.tsx`, `ChatInput.tsx`, `ChatHeader.tsx`)**:
   - **Disease Context Selector**: Switch seamlessly between Cancer presets (*Triple-Negative Breast Cancer*, *Pancreatic Cancer (PDAC)*, *Lung Carcinoma*, *General Oncology*) and General Diseases (*Pulmonary Fibrosis*, *Rheumatoid Arthritis*, *Alzheimer's Disease*) or type any custom disease.
   - **5-Tab Structured Dossier**: *Overview*, *Targets & Gene Flipping*, *Drug Repurposing*, *Literature, Trials & Lab Plan*, and *Critic Audit & Exports* (including downloadable **Target Dossier CSV**).
   - **Plain-English Guide (`How it works`)**: Explains `log2FC`, `padj`, Gene Flipping, MoA Concordance, §13 FPKM protection, and local RTX 5050 model setup for non-coders and wet-lab biologists.

---

## Part 3 — Running Local Models on Your RTX 5050 (8 GB VRAM)

All three configured models fit comfortably inside **8 GB VRAM**:
- `gemma-3-4b` (Q8_K_XL, ~4.9 GB VRAM)
- `medgemma-4b` (Q8_K_XL, ~4.9 GB VRAM — biomedical domain-tuned)
- `qwen-3-8b` (Q4_K_M, ~5.1 GB VRAM)

### Quick-Start Commands (Local Machine)
1. **Start `llama-server` on your RTX 5050:**
   ```bash
   llama-server -m /path/to/medgemma-4b-it-Q8_K_XL.gguf -ngl 99 -c 8192 --port 8080
   ```
2. **Run Retrospective Cancer + General-Disease Drug Rediscovery Benchmark:**
   ```bash
   python scripts/run_rtx5050_benchmark.py --rediscovery-only
   ```
3. **Run Full 4-Dataset + Therapeutic Discovery Benchmark with Your Local Model:**
   ```bash
   python scripts/run_rtx5050_benchmark.py --model medgemma-4b
   python evaluation/metrics/rebuild_measured_artifacts.py
   ```
4. **Analyze Any Custom Cancer or General-Disease CSV Matrix:**
   ```bash
   python scripts/run_rtx5050_benchmark.py --csv data/test_datasets/PDAC_gemcitabine_counts.csv --disease "pancreatic ductal adenocarcinoma"
   ```
5. **Run Automated Verification Suite:**
   ```bash
   python -m unittest discover -s tests -v
   ```
