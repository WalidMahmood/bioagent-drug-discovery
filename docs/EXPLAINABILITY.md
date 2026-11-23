# Explainability — How BioAgent-Lite Shows Its Work

This document explains how every BioAgent-Lite output is grounded, audited, and traceable back to deterministic computational artifacts.

---

## 1. Five Separated Epistemic Layers

Every BioAgent-Lite execution separates its outputs into explicit layers so a reviewer can verify each sentence independently:

| Category | Meaning | Where it lives |
|---|---|---|
| **Computed** | Numbers produced strictly by deterministic Python code (`pydeseq2`, Welch's t-test, BH-FDR, `gseapy`), never by an LLM | `comp.top_genes`, `comp.top_pathways`, `reference/outputs/*.csv`, `outputs/uploads/*_de_results.csv` |
| **Retrieved** | Verbatim claim-to-artifact lineage records with normalized pathway matching | `evidence[].source_id`, `evidence[].snippet`, `evidence[].relevance` |
| **Interpreted** | Structured biological synthesis constrained to `observed`, `supported`, or `hypothesis` claims | `interp.claims[]`, `interp.observations[]` |
| **Hypothesized** | Mechanistic hypotheses requiring explicit scientific hedging | `claim.type == "hypothesis"` and `claim.hedged == true` |
| **Audited / Pruned** | Critic verdict, error list, re-prompted revisions, or pruned offending claims | `verdict`, `interp.pruned_claims[]`, `traces[]` |

---

## 2. Evidence Grounding (`agents/evidence.py`)

The Evidence Retriever runs after the Biological Interpreter and before the Critic:

- **Gene grounding (`relevance = 1.0`):** Exact case-insensitive lookup in `comp.top_genes`.
- **Pathway grounding (`relevance = 0.95`):** Uses `normalize_pathway_term()` to strip `GO`/`GO_BP`/`Reactome`/`KEGG` prefixes and parenthetical identifiers (`(GO:...)`, `(R-HSA-...)`) before matching against `comp.top_pathways`, aligning with the Critic's pathway matcher and preventing false `#ABSENT` scores.
- **Explicit absence (`relevance = 0.0`):** Unmatched genes or pathways are stamped with `#ABSENT` rather than silently omitted.
- **Runtime scope:** Grounding operates deterministically over computed DE and enrichment outputs. ChromaDB/PubMed vector retrieval is a documented roadmap extension (commented in `requirements.txt`), not an active runtime call.

---

## 3. Deterministic Critic & Honest Self-Correction (`agents/critic.py`, `agents/graph.py`)

The Critic audits every run across six deterministic checks:

1. **Comparison sanity:** Blocks identical intervention and control groups (`group_a == group_b`).
2. **Data-type & §13 guardrail check:** Rejects plans requesting DESeq2/edgeR on FPKM/non-inferential data and flags claims citing adjusted p-values/FDR on descriptive FPKM runs.
3. **Invented gene detection:** Rejects any cited gene absent from the computed differential expression results.
4. **Statistical trap detection:** Rejects claims calling a gene statistically significant when `padj >= 0.05`.
5. **Direction concordance (tagged & prose-level):** Uses word-boundary regexes to check both tagged `claim.genes` and untagged gene symbols mentioned in `claim.statement` against the sign of computed `log2FC`.
6. **Hedging & non-clinical disclaimer:** Enforces hedged phrasing on hypothesis claims and requires a non-clinical research-use disclaimer.

### Two-Stage Self-Correction (No PASS-Laundering)

When the Critic issues `FAIL`:
- **Stage 1 (LLM Revision):** On iteration 0 with `use_llm=True`, `agents/graph.py` re-prompts `BiologicalInterpreterAgent.interpret(..., critic_feedback=verdict.errors)` so the model can genuinely rewrite the claim to match computed statistics.
- **Stage 2 (Whole-Claim Pruning):** If deterministic fallback mode is active or a claim still fails on the final retry pass, `_prune_failed_claims()` removes the **entire offending `InterpretationClaim`** (recording it in `interp.pruned_claims`) rather than stripping gene tags while leaving false prose intact. Only hedging-only violations are rewritten in place.

---

## 4. Provenance Ledger (Live vs Replayed vs Measured)

| Component | Status | Behavior |
|---|---|---|
| Uploaded CSV/TSV analysis (`POST /api/upload` + `POST /api/run`) | **Live** | Computes real Welch's t-test + BH-FDR (or §13 descriptive log2FC on FPKM/floats), attempts live Enrichr enrichment (honest statistical-only fallback offline), generates real plots, runs deterministic Critic, saves downloadable DE CSV and trace JSON |
| GEO Benchmark UI runs (`GSE202768`, `GSE113650`, `GSE95304`, `GSE336903`) | **Verified Trace Replay** | Serves actual steps, latencies, tokens, verdicts, genes, and traces directly from `outputs/traces/eval_*.json` |
| Headless evaluation scripts (`evaluation/**`) | **Live** | Executes the full LangGraph pipeline against a local `llama.cpp` server or `--no-llm` deterministic mode |
| Evaluation tables (`outputs/tables/*.csv`) & `outputs/manifest.json` | **Measured** | Rebuilt deterministically from preserved `outputs/traces/*.json` via `evaluation/metrics/rebuild_measured_artifacts.py` |
| MedGemma 4B / Qwen3 8B rows | **Pending Local GGUF Run** | Explicitly labeled `pending_local_gguf_run` until local GGUF traces are generated |
