"""Critic / Verifier Agent (Master #17).
Performs multi-layered scientific, statistical, biological, and safety verification:
1. Plan & Data-Type Guardrail (§13): Forbids count-based models (DESeq2/edgeR) on FPKM/TPM data.
2. Statistical Verification: Gene presence, adjusted p-value significance (padj < 0.05),
   fold-change direction concordance, detection of statistical traps (large LFC with high padj),
   and refusal of fabricated FDR/padj claims on descriptive FPKM runs.
3. Biological Verification: Pathway enrichment confirmation, identification of uncredited pathways.
4. Logical & Scientific Hedging: Hypotheses must use probabilistic language; forbids "proves".
5. Safety Verification: Non-clinical disclaimer presence and group comparison sanity (R2).
Tracks exact failing claim indices so the correction loop can rewrite or prune invalid claims
without laundering false prose into PASS.
"""
import os
import re
import sys
from typing import Tuple, List, Dict, Any, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.schemas import CriticVerdict, Plan, ComputationalResult, Interpretation
from agents.evidence import normalize_pathway_term

STRONG_WORDS = re.compile(r"\b(proves|proven|definitively|certainly causes|undeniably)\b", re.I)
UP_PAT = re.compile(r"\b(up[\s-]?regulat\w*|increas\w*|elevat\w*|overexpress\w*|induc\w*)\b", re.I)
DOWN_PAT = re.compile(r"\b(down[\s-]?regulat\w*|decreas\w*|reduc\w*|suppress\w*|repress\w*|deplet\w*)\b", re.I)
FAKE_SIG_PAT = re.compile(r"\b(padj\s*<|fdr\s*<|q[\s_-]?value\s*<|statistically\s+significant)\b", re.I)
COUNT_MODEL_PAT = re.compile(r"\b(pydeseq2|deseq2|edger|negative[\s-]?binomial)\b", re.I)
FPKM_TYPE_PAT = re.compile(r"\b(fpkm|tpm|rpkm|normalized|cpm)\b", re.I)
INHIBIT_ACTION_PAT = re.compile(r"\b(inhibit\w*|antagonist\w*|block(?:er|ade|ing)?|knockdown|degrader)\b", re.I)
ACTIVATE_ACTION_PAT = re.compile(r"\b(agonist\w*|activat(?:e|or|ing)|stimulat\w*)\b", re.I)
PMID_PAT = re.compile(r"\bPMID\s*[:#]?\s*(\d{5,9})\b", re.I)
NCT_PAT = re.compile(r"\b(NCT\d{8})\b", re.I)


def _norm(s: str) -> str:
    return normalize_pathway_term(s)


def verify(
    plan: Plan,
    comp: ComputationalResult,
    interp: Interpretation,
    padj_thresh: float = 0.05,
    discovery: Dict[str, Any] | None = None,
) -> Tuple[CriticVerdict, Dict[str, Any]]:
    """Execute complete statistical, biological, safety, and therapeutic MoA verification audit."""
    errors: List[str] = []
    warnings: List[str] = []
    corrections: List[str] = []
    failed_claim_indices: Set[int] = set()

    # Map genes from computational result
    gene_map = {g.gene.upper(): g for g in comp.top_genes}

    # Map normalized pathway terms
    pw_terms: Set[str] = {_norm(p.term) for p in comp.sig_pathways if _norm(p.term)}

    # Infer whether computational outputs carry true inferential adjusted p-values
    has_inferential_stats = comp.inferential and any(g.padj is not None for g in comp.top_genes)

    # 1. Comparison Sanity Guard (Robustness R2)
    if plan.comparison.group_a.strip().lower() == plan.comparison.group_b.strip().lower():
        errors.append("Invalid experimental comparison: intervention and control groups are identical (R2)")
        corrections.append("Specify distinct comparison groups in the plan")

    # 2. Data-Type Refusal Guard (§13): Plan must not prescribe DESeq2/edgeR for FPKM/normalized data
    is_fpkm_data = bool(FPKM_TYPE_PAT.search(plan.data_type) or FPKM_TYPE_PAT.search(comp.data_type) or not has_inferential_stats)
    if is_fpkm_data and COUNT_MODEL_PAT.search(plan.de_method) and "refus" not in plan.de_method.lower():
        errors.append(
            f"Data-type guardrail violation (§13): plan proposed count-based method '{plan.de_method}' "
            f"on non-count data ('{comp.data_type}')"
        )
        corrections.append("Replace de_method with descriptive FPKM fold-change ranking; refuse DESeq2/edgeR")

    # 3. Disclaimer & Safety Guard
    if not interp.disclaimer or "clinical" not in interp.disclaimer.lower():
        warnings.append("Missing standard non-clinical research prototype disclaimer")

    # 4. Claims Verification Audit
    for idx, claim in enumerate(interp.claims):
        statement = claim.statement
        claim_has_error = False

        # Descriptive FPKM guard: forbid claiming padj/FDR significance when no p-values exist
        if not has_inferential_stats and FAKE_SIG_PAT.search(statement):
            errors.append(
                f"Claim #{idx+1} asserts inferential significance (FDR/padj) on descriptive FPKM data with padj=N/A (§13 violation)"
            )
            corrections.append(f"Rewrite claim #{idx+1} as descriptive fold-change magnitude without FDR/padj thresholds")
            claim_has_error = True

        # Guard against orphaned direction claims whose genes were stripped
        if not claim.genes and (UP_PAT.search(statement) or DOWN_PAT.search(statement)):
            # Check if statement explicitly names genes from gene_map with inverted direction
            for gene_sym, hit in gene_map.items():
                if len(gene_sym) >= 3 and re.search(rf"\b{re.escape(gene_sym)}\b", statement, re.I):
                    if UP_PAT.search(statement) and not DOWN_PAT.search(statement) and hit.log2FC < 0:
                        errors.append(
                            f"{gene_sym} in claim #{idx+1} text claimed up-regulated but computed log2FC={hit.log2FC:.2f} is negative (wrong direction)"
                        )
                        corrections.append(f"Rewrite claim #{idx+1} to state {gene_sym} is down-regulated")
                        claim_has_error = True
                    elif DOWN_PAT.search(statement) and not UP_PAT.search(statement) and hit.log2FC > 0:
                        errors.append(
                            f"{gene_sym} in claim #{idx+1} text claimed down-regulated but computed log2FC={hit.log2FC:.2f} is positive (wrong direction)"
                        )
                        corrections.append(f"Rewrite claim #{idx+1} to state {gene_sym} is up-regulated")
                        claim_has_error = True

        # Gene checks
        for g in claim.genes:
            g_clean = g.strip().upper()
            if g_clean not in gene_map:
                errors.append(f"{g_clean} reported in claim #{idx+1} but absent from computed top results (invented gene)")
                corrections.append(f"Remove or correct uncomputed gene {g_clean} in claim #{idx+1}")
                claim_has_error = True
            else:
                hit = gene_map[g_clean]
                # Stat Trap Check (padj confusion / R4)
                if hit.padj is not None and (claim.type == "observed" or "significan" in statement.lower()):
                    if hit.padj >= padj_thresh:
                        errors.append(
                            f"{g_clean} claimed significant in claim #{idx+1} but padj={hit.padj:.2g} >= {padj_thresh} (statistical trap / padj confusion)"
                        )
                        corrections.append(f"Remove {g_clean} from significant claims in claim #{idx+1}")
                        claim_has_error = True

                # Direction Check
                if UP_PAT.search(statement) and not DOWN_PAT.search(statement):
                    if hit.log2FC < 0:
                        errors.append(
                            f"{g_clean} claimed up-regulated in claim #{idx+1} but computed log2FC={hit.log2FC:.2f} is negative (wrong direction)"
                        )
                        corrections.append(f"Rewrite claim #{idx+1}: fix direction for {g_clean} to down-regulated")
                        claim_has_error = True

                elif DOWN_PAT.search(statement) and not UP_PAT.search(statement):
                    if hit.log2FC > 0:
                        errors.append(
                            f"{g_clean} claimed down-regulated in claim #{idx+1} but computed log2FC={hit.log2FC:.2f} is positive (wrong direction)"
                        )
                        corrections.append(f"Rewrite claim #{idx+1}: fix direction for {g_clean} to up-regulated")
                        claim_has_error = True

        # Pathway checks
        for p in claim.pathways:
            np_term = _norm(p)
            if not np_term or not any(np_term in t or t in np_term for t in pw_terms):
                warnings.append(f"Pathway '{p}' in claim #{idx+1} is uncredited / absent from significant enrichment results")

        # Scientific Hedging Check
        if claim.type == "hypothesis" and STRONG_WORDS.search(statement):
            errors.append(f"Hypothesis in claim #{idx+1} stated with unscientific certainty ('{statement[:80]}...')")
            corrections.append(f"Rephrase claim #{idx+1} using probabilistic scientific hedging ('suggests', 'is consistent with')")
            claim_has_error = True

        if claim.type in ("observed", "supported") and STRONG_WORDS.search(statement):
            warnings.append(f"Overly strong causal phrasing in empirical claim #{idx+1}: '{statement[:80]}...'")

        # 5. Therapeutic MoA Concordance & Citation Existence Guards (Critic v2)
        if discovery:
            valid_pmids = {str(h.get("pmid", "")) for h in (discovery.get("literature") or []) if h.get("pmid")}
            valid_ncts = {str(c.get("nct_id", "")).upper() for c in (discovery.get("clinical_trials") or []) if c.get("nct_id")}
            blocked_drug_names = {
                str(d.get("drug_name", "")).upper(): d
                for d in (discovery.get("blocked_drugs") or [])
                if d.get("drug_name")
            }

            # T1: Reject recommendations citing a mechanistically discordant (blocked) drug
            for b_name, b_rec in blocked_drug_names.items():
                if len(b_name) >= 4 and re.search(rf"\b{re.escape(b_name)}\b", statement, re.I):
                    if not re.search(r"\b(avoid|block|discordant|contraindicat|do not)\b", statement, re.I):
                        errors.append(
                            f"Therapeutic MoA violation (T1) in claim #{idx+1}: recommended blocked drug '{b_rec['drug_name']}' "
                            f"({b_rec.get('action_type', 'MoA')}) against {b_rec.get('target_gene')} (log2FC={b_rec.get('target_log2FC', 0):+.2f})"
                        )
                        corrections.append(f"Remove discordant drug '{b_rec['drug_name']}' from claim #{idx+1}")
                        claim_has_error = True

            # T1b: Reject explicit drug-action mismatch on single-direction gene claims
            if claim.genes and all(g.strip().upper() in gene_map for g in claim.genes):
                signs = {1 if gene_map[g.strip().upper()].log2FC > 0 else -1 for g in claim.genes}
                if signs == {-1} and INHIBIT_ACTION_PAT.search(statement) and not ACTIVATE_ACTION_PAT.search(statement):
                    if re.search(r"\b(recommend|candidate|target|treat|therap|drug|repurpos|revers)\b", statement, re.I):
                        errors.append(
                            f"Therapeutic MoA violation (T1) in claim #{idx+1}: proposes inhibiting already downregulated gene(s) {claim.genes}"
                        )
                        corrections.append(f"Align therapeutic action in claim #{idx+1} with gene expression sign (restore/activate rather than inhibit)")
                        claim_has_error = True
                elif signs == {1} and ACTIVATE_ACTION_PAT.search(statement) and not INHIBIT_ACTION_PAT.search(statement):
                    if re.search(r"\b(recommend|candidate|target|treat|therap|drug|repurpos|revers)\b", statement, re.I):
                        errors.append(
                            f"Therapeutic MoA violation (T1) in claim #{idx+1}: proposes activating already upregulated gene(s) {claim.genes}"
                        )
                        corrections.append(f"Align therapeutic action in claim #{idx+1} with gene expression sign (inhibit/suppress rather than activate)")
                        claim_has_error = True

            # T2: Reject invented PMIDs or NCT IDs absent from deterministic tool results
            for pmid_match in PMID_PAT.findall(statement):
                if pmid_match not in valid_pmids:
                    errors.append(f"Invented citation (T2) in claim #{idx+1}: PMID:{pmid_match} not found in retrieved PubMed evidence")
                    corrections.append(f"Remove unverified PMID:{pmid_match} from claim #{idx+1}")
                    claim_has_error = True

            for nct_match in NCT_PAT.findall(statement):
                if nct_match.upper() not in valid_ncts:
                    errors.append(f"Invented clinical trial (T2) in claim #{idx+1}: {nct_match} not found in retrieved ClinicalTrials.gov records")
                    corrections.append(f"Remove unverified trial ID {nct_match} from claim #{idx+1}")
                    claim_has_error = True

            # T3: Safety warning check on pan-essential or high-liability targets
            target_by_sym = {str(t.get("gene", "")).upper(): t for t in (discovery.get("targets") or [])}
            for g in claim.genes:
                t_info = target_by_sym.get(g.strip().upper())
                if t_info and t_info.get("safety_warning") and re.search(r"\b(target|drug|inhibit|therap|repurpos)\b", statement, re.I):
                    if not re.search(r"\b(toxic|safety|essential|caution|liabilit)\b", statement, re.I):
                        warnings.append(
                            f"Safety disclosure note (T3) on claim #{idx+1}: {g.upper()} carries a safety caveat ({t_info['safety_warning']})"
                        )

        if claim_has_error:
            failed_claim_indices.add(idx)

    status = "FAIL" if errors else "PASS"
    stat_ok = not any("padj" in e or "direction" in e or "trap" in e or "FDR" in e for e in errors)
    bio_ok = not any("invented" in e.lower() for e in errors)
    safety_ok = not any(
        "Invalid experimental comparison" in e or "Hypothesis" in e or "Data-type guardrail" in e
        for e in errors
    )
    moa_ok = not any("Therapeutic MoA violation" in e or "Invented citation" in e or "Invented clinical trial" in e for e in errors)

    verdict = CriticVerdict(
        status=status,
        errors=errors,
        warnings=warnings,
        corrections=corrections,
        statistical_checks_passed=stat_ok,
        biological_grounding_passed=bio_ok,
        safety_guardrails_passed=safety_ok,
        therapeutic_moa_checks_passed=moa_ok,
        audit_scores={
            "total_claims_audited": len(interp.claims),
            "errors_found": len(errors),
            "warnings_found": len(warnings),
            "corrections_required": len(corrections),
            "failed_claim_indices": sorted(failed_claim_indices),
            "claims_pruned": len(interp.pruned_claims),
            "therapeutic_moa_checks_passed": moa_ok,
        },
    )

    trace = {
        "agent": "critic",
        "dataset": comp.dataset,
        "verdict_status": status,
        "errors_count": len(errors),
        "warnings_count": len(warnings),
        "failed_claim_indices": sorted(failed_claim_indices),
        "claims_pruned": len(interp.pruned_claims),
        "statistical_checks_passed": stat_ok,
        "biological_grounding_passed": bio_ok,
        "safety_guardrails_passed": safety_ok,
        "therapeutic_moa_checks_passed": moa_ok,
    }
    return verdict, trace
