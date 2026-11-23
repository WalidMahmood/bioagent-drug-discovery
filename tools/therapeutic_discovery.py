"""Deterministic Therapeutic Target & Drug Repurposing Discovery Engine.

Queries live, gold-standard public biomedical APIs using Python's standard library
(zero proprietary keys required) with local JSON caching and strict input validation:
1. Open Targets Platform v4 GraphQL API (target tractability, cancer/general disease
   associations, essentiality, safety liabilities, and clinical/approved drugs).
2. NCBI PubMed E-utilities (verified PMIDs, titles, publication years).
3. ClinicalTrials.gov v2 API (verified NCT study IDs, phases, statuses).

Also executes deterministic Gene-Flipping Direction & Mechanism-of-Action (MoA)
concordance analysis so downstream biological synthesis and Critic v2 never recommend
an inhibitor for a downregulated tumor suppressor or an agonist for an upregulated driver.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "outputs" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "BioAgent-Lite/2.1 (Research Therapeutic Discovery Workbench)"
OPENTARGETS_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
CLINICALTRIALS_V2_URL = "https://clinicaltrials.gov/api/v2/studies"

GENE_SYM_RE = re.compile(r"^[A-Za-z0-9._-]{2,24}$")

INHIBITORY_MOA_TOKENS = {
    "INHIBITOR",
    "ANTAGONIST",
    "BLOCKER",
    "NEGATIVE MODULATOR",
    "NEGATIVE ALLOSTERIC MODULATOR",
    "INVERSE AGONIST",
    "DEGRADER",
    "ANTISENSE INHIBITOR",
    "RNAI INHIBITOR",
    "DISRUPTING AGENT",
    "SEQUESTERING AGENT",
    "HYDROLYTIC ENZYME",
    "PROTEOLYTIC ENZYME",
}

ACTIVATING_MOA_TOKENS = {
    "AGONIST",
    "PARTIAL AGONIST",
    "ACTIVATOR",
    "POSITIVE MODULATOR",
    "POSITIVE ALLOSTERIC MODULATOR",
    "OPENER",
    "STABILISER",
    "RELEASING AGENT",
}

STAGE_RANK = {
    "APPROVAL": 4,
    "PHASE_4": 4,
    "PHASE_3": 3,
    "PHASE_2_3": 3,
    "PHASE_2": 2,
    "PHASE_1_2": 2,
    "PHASE_1": 1,
    "EARLY_PHASE_1": 1,
    "PRECLINICAL": 0,
    "UNKNOWN": 0,
    "WITHDRAWAL": -1,
}

STAGE_LABELS = {
    "APPROVAL": "FDA / Regulatory Approved",
    "PHASE_4": "Approved (Phase 4)",
    "PHASE_3": "Phase 3 Clinical",
    "PHASE_2_3": "Phase 2/3 Clinical",
    "PHASE_2": "Phase 2 Clinical",
    "PHASE_1_2": "Phase 1/2 Clinical",
    "PHASE_1": "Phase 1 Clinical",
    "EARLY_PHASE_1": "Early Phase 1",
    "PRECLINICAL": "Preclinical",
    "WITHDRAWAL": "Withdrawn",
    "UNKNOWN": "Investigated",
}


def sanitize_gene_symbol(raw: str) -> Optional[str]:
    sym = str(raw or "").strip().upper()
    if not GENE_SYM_RE.match(sym):
        return None
    return sym


def sanitize_disease_context(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\s,\-()/]", " ", str(raw or "cancer"))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or "cancer")[:100]


def classify_flip_action(log2fc: float) -> Dict[str, str]:
    """Determine recommended therapeutic gene-flipping direction from expression sign."""
    if log2fc > 0:
        return {
            "recommended_flip": "Suppress / Inhibit (Turn OFF)",
            "expected_moa_class": "inhibitory",
            "rationale": "Elevated expression in disease/perturbation state; candidate for inhibition, knockdown, or pathway blockade.",
        }
    return {
        "recommended_flip": "Restore / Activate (Turn ON)",
        "expected_moa_class": "activating",
        "rationale": "Suppressed expression in disease/perturbation state; candidate for restoration, agonism, or synthetic-lethality follow-up.",
    }


def evaluate_moa_concordance(log2fc: float, action_type: Optional[str], mechanism: Optional[str] = None) -> Tuple[str, str]:
    """Deterministically audit whether a drug's mechanism of action matches the required gene flip.

    Returns (status, explanation) where status is one of:
      - 'CONCORDANT'
      - 'DISCORDANT_BLOCKED'
      - 'NEUTRAL_REVIEW'
    """
    action = str(action_type or "").strip().upper()
    mech_upper = str(mechanism or "").strip().upper()

    is_inhib = action in INHIBITORY_MOA_TOKENS or any(
        tok in mech_upper for tok in ("INHIBITOR", "ANTAGONIST", "BLOCKER", "DEGRADER", "NEGATIVE MODULATOR")
    )
    is_activ = action in ACTIVATING_MOA_TOKENS or any(
        tok in mech_upper for tok in ("AGONIST", "ACTIVATOR", "POSITIVE MODULATOR", "OPENER")
    )

    if log2fc > 0:
        if is_inhib and not is_activ:
            return (
                "CONCORDANT",
                f"Inhibitory MoA ({action or 'inhibitor'}) matches upregulated target (log2FC={log2fc:+.2f}).",
            )
        if is_activ and not is_inhib:
            return (
                "DISCORDANT_BLOCKED",
                f"Blocked by MoA Guard: activating drug ({action or 'agonist'}) would worsen an already upregulated gene (log2FC={log2fc:+.2f}).",
            )
        return (
            "NEUTRAL_REVIEW",
            f"Mechanism ({action or mechanism or 'unspecified'}) requires manual pharmacology review for upregulated target.",
        )

    # log2fc <= 0 (downregulated)
    if is_activ and not is_inhib:
        return (
            "CONCORDANT",
            f"Activating MoA ({action or 'agonist'}) matches downregulated target (log2FC={log2fc:+.2f}).",
        )
    if is_inhib and not is_activ:
        return (
            "DISCORDANT_BLOCKED",
            f"Blocked by MoA Guard: inhibitory drug ({action or 'inhibitor'}) conflicts with an already downregulated gene (log2FC={log2fc:+.2f}).",
        )
    return (
        "NEUTRAL_REVIEW",
        f"Mechanism ({action or mechanism or 'unspecified'}) requires manual pharmacology review for downregulated target.",
    )


def compute_target_priority_score(
    log2fc: float,
    padj: Optional[float],
    top_disease_score: float,
    max_concordant_stage_rank: int,
    tractable_modalities: List[str],
    is_essential: Optional[bool],
    safety_liability_count: int,
) -> Dict[str, Any]:
    """Transparent, formula-based Target Priority Score (0-100) with visible sub-scores."""
    # 1. Transcriptomic Effect (0-30)
    lfc_component = min(22.0, abs(log2fc) * 8.5)
    sig_component = 8.0 if (padj is not None and padj < 0.05) else (4.0 if abs(log2fc) >= 1.5 else 2.0)
    transcriptomic_score = round(min(30.0, lfc_component + sig_component), 1)

    # 2. Genetic / Disease Association from Open Targets (0-25)
    disease_score = round(min(25.0, max(0.0, top_disease_score) * 25.0), 1)

    # 3. Druggability & Clinical Tractability (0-25)
    if max_concordant_stage_rank >= 4:
        druggability_score = 25.0
    elif max_concordant_stage_rank >= 2:
        druggability_score = 21.0
    elif max_concordant_stage_rank == 1:
        druggability_score = 17.0
    elif tractable_modalities:
        druggability_score = round(min(15.0, 8.0 + len(tractable_modalities) * 2.5), 1)
    else:
        druggability_score = 4.0

    # 4. Selectivity & Safety Profile (0-20)
    safety_score = 20.0
    if is_essential is True:
        safety_score -= 8.0  # Pan-essential genes carry higher healthy-tissue toxicity risk
    safety_score -= min(10.0, safety_liability_count * 1.25)
    safety_score = round(max(2.0, safety_score), 1)

    total = round(min(100.0, transcriptomic_score + disease_score + druggability_score + safety_score), 1)

    if max_concordant_stage_rank >= 4:
        tier = "Tier 1: Approved Drug Repurposing"
    elif max_concordant_stage_rank >= 1 or len(tractable_modalities) >= 2:
        tier = "Tier 2: Clinical / Tractable Candidate"
    else:
        tier = "Tier 3: Novel Genetic Flip Target"

    return {
        "total_score": total,
        "evidence_tier": tier,
        "breakdown": {
            "transcriptomic_0_30": transcriptomic_score,
            "disease_evidence_0_25": disease_score,
            "druggability_0_25": druggability_score,
            "safety_selectivity_0_20": safety_score,
        },
    }


def _http_json(
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 8.0,
) -> Optional[Dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _query_opentargets_batch(gene_symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """Map gene symbols to Ensembl IDs and fetch full Open Targets v4 target records in 2 GraphQL calls."""
    if not gene_symbols:
        return {}

    map_query = """
    query MapTargets($terms: [String!]!) {
      mapIds(queryTerms: $terms, entityNames: ["target"]) {
        mappings {
          term
          hits {
            id
            name
            entity
          }
        }
      }
    }
    """
    mapped = _http_json(
        OPENTARGETS_GRAPHQL_URL,
        payload={"query": map_query, "variables": {"terms": gene_symbols}},
        timeout=10.0,
    )
    if not mapped or "data" not in mapped:
        return {}

    sym_to_ensg: Dict[str, str] = {}
    for entry in (mapped.get("data", {}).get("mapIds", {}).get("mappings") or []):
        term = str(entry.get("term", "")).upper()
        hits = entry.get("hits") or []
        if not hits:
            continue
        exact = next((h for h in hits if str(h.get("name", "")).upper() == term), hits[0])
        if exact and exact.get("id"):
            sym_to_ensg[term] = exact["id"]

    if not sym_to_ensg:
        return {}

    ensg_ids = list(dict.fromkeys(sym_to_ensg.values()))
    targets_query = """
    query TargetDetails($ids: [String!]!) {
      targets(ensemblIds: $ids) {
        id
        approvedSymbol
        approvedName
        isEssential
        tractability {
          label
          modality
          value
        }
        safetyLiabilities {
          event
        }
        associatedDiseases(page: { index: 0, size: 5 }) {
          rows {
            score
            disease {
              id
              name
            }
          }
        }
        drugAndClinicalCandidates {
          count
          rows {
            maxClinicalStage
            drug {
              id
              name
              drugType
              mechanismsOfAction {
                rows {
                  mechanismOfAction
                  actionType
                }
              }
            }
            diseases {
              disease {
                id
                name
              }
            }
          }
        }
      }
    }
    """
    detail = _http_json(
        OPENTARGETS_GRAPHQL_URL,
        payload={"query": targets_query, "variables": {"ids": ensg_ids}},
        timeout=12.0,
    )
    if not detail or "data" not in detail:
        return {}

    by_ensg: Dict[str, Dict[str, Any]] = {}
    for t in (detail.get("data", {}).get("targets") or []):
        if t and t.get("id"):
            by_ensg[t["id"]] = t

    results: Dict[str, Dict[str, Any]] = {}
    for sym, ensg in sym_to_ensg.items():
        if ensg in by_ensg:
            results[sym] = by_ensg[ensg]
    return results


def _query_pubmed(gene_symbol: str, disease_context: str, max_results: int = 3) -> List[Dict[str, Any]]:
    term = f"({gene_symbol}[Title/Abstract]) AND ({disease_context}[Title/Abstract])"
    params = urllib.parse.urlencode(
        {"db": "pubmed", "term": term, "retmax": str(max_results), "retmode": "json", "sort": "relevance"}
    )
    search_data = _http_json(f"{PUBMED_ESEARCH_URL}?{params}", timeout=6.0)
    pmids = (search_data or {}).get("esearchresult", {}).get("idlist") or []
    if not pmids:
        return []

    sum_params = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(pmids), "retmode": "json"})
    sum_data = _http_json(f"{PUBMED_ESUMMARY_URL}?{sum_params}", timeout=6.0)
    res_block = (sum_data or {}).get("result") or {}
    hits: List[Dict[str, Any]] = []
    for pmid in pmids:
        if not re.match(r"^\d+$", str(pmid)):
            continue
        item = res_block.get(str(pmid))
        if not isinstance(item, dict):
            continue
        hits.append(
            {
                "pmid": str(pmid),
                "gene": gene_symbol,
                "title": str(item.get("title", "")).strip().rstrip("."),
                "journal": str(item.get("fulljournalname") or item.get("source") or ""),
                "pub_date": str(item.get("pubdate", "")),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )
    return hits


def _query_clinical_trials(query_term: str, disease_context: str, max_results: int = 3) -> List[Dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "query.term": f"{query_term} {disease_context}",
            "pageSize": str(max_results),
        }
    )
    data = _http_json(f"{CLINICALTRIALS_V2_URL}?{params}", timeout=6.0)
    studies = (data or {}).get("studies") or []
    hits: List[Dict[str, Any]] = []
    for s in studies:
        proto = s.get("protocolSection") or {}
        ident = proto.get("identificationModule") or {}
        status = proto.get("statusModule") or {}
        design = proto.get("designModule") or {}
        nct_id = str(ident.get("nctId", "")).strip()
        if not re.match(r"^NCT\d+$", nct_id):
            continue
        phases = design.get("phases") or []
        hits.append(
            {
                "nct_id": nct_id,
                "query_gene_or_drug": query_term,
                "title": str(ident.get("briefTitle") or ident.get("officialTitle") or "").strip(),
                "status": str(status.get("overallStatus") or "UNKNOWN"),
                "phase": ", ".join(phases) if phases else "N/A",
                "url": f"https://clinicaltrials.gov/study/{nct_id}",
            }
        )
    return hits


def _build_wetlab_plan(
    dataset_name: str,
    disease_context: str,
    targets: List[Dict[str, Any]],
    concordant_drugs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate a concrete, researcher-friendly next wet-lab validation checklist."""
    top_targets = targets[:3]
    top_up = [t for t in targets if t["log2FC"] > 0][:3]
    top_down = [t for t in targets if t["log2FC"] < 0][:2]
    qpcr_panel = [t["gene"] for t in (top_up + top_down)[:5]]

    steps: List[str] = []
    if concordant_drugs:
        lead = concordant_drugs[0]
        steps.append(
            f"Drug Repurposing Viability Screen: Test {lead['drug_name']} ({lead['action_type'] or lead['mechanism']}, {lead['clinical_stage_label']}) "
            f"targeting {lead['target_gene']} in a 6-point dose-response assay (72h CellTiter-Glo / viability readout) in a {disease_context} cell model."
        )
    if top_up:
        lead_up = top_up[0]
        steps.append(
            f"Genetic Flip Confirmation (Loss-of-Function): Perform siRNA or CRISPRi knockdown of {lead_up['gene']} "
            f"(observed log2FC={lead_up['log2FC']:+.2f}) to confirm whether suppressing this candidate reverses disease phenotype or restores drug sensitivity."
        )
    if top_down:
        lead_down = top_down[0]
        steps.append(
            f"Rescue / Biomarker Tracking: Monitor restoration of suppressed marker {lead_down['gene']} "
            f"(log2FC={lead_down['log2FC']:+.2f}) after perturbation or compound treatment."
        )
    if qpcr_panel:
        steps.append(
            f"Orthogonal 5-Gene RT-qPCR Validation Panel: Quantify {', '.join(qpcr_panel)} alongside housekeeping controls across >=3 biological replicates."
        )

    return {
        "dataset": dataset_name,
        "disease_context": disease_context,
        "recommended_qpcr_panel": qpcr_panel,
        "priority_targets": [t["gene"] for t in top_targets],
        "actionable_steps": steps,
        "caution": (
            "All wet-lab validation suggestions are hypothesis-generating research plans derived from transcriptomic "
            "and Open Targets / PubMed / ClinicalTrials.gov evidence—not clinical treatment protocols."
        ),
    }


def run_target_discovery(
    top_genes: List[Dict[str, Any]],
    disease_context: str = "cancer",
    dataset_name: str = "dataset",
    max_targets: int = 10,
    use_cache: bool = True,
    live_network: bool = True,
) -> Dict[str, Any]:
    """Run deterministic Target Prioritization, Gene-Flipping Drug Repurposing, and Literature/Trial grounding."""
    t0 = time.time()
    clean_disease = sanitize_disease_context(disease_context)

    normalized_inputs: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for g in top_genes:
        sym = sanitize_gene_symbol(g.get("gene", ""))
        if not sym or sym in seen:
            continue
        try:
            lfc = float(g.get("log2FC", 0.0))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(lfc):
            continue
        padj_raw = g.get("padj")
        padj = float(padj_raw) if (padj_raw is not None and math.isfinite(float(padj_raw))) else None
        seen.add(sym)
        normalized_inputs.append(
            {
                "gene": sym,
                "log2FC": round(lfc, 4),
                "padj": padj,
                "direction": "up" if lfc >= 0 else "down",
            }
        )
        if len(normalized_inputs) >= max_targets:
            break

    cache_key = hashlib.sha256(
        json.dumps(
            {
                "v": 3,
                "disease": clean_disease.lower(),
                "genes": [(x["gene"], round(x["log2FC"], 2)) for x in normalized_inputs],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    cache_path = (CACHE_DIR / f"discovery_{cache_key}.json").resolve()
    if use_cache and cache_path.is_relative_to(CACHE_DIR.resolve()) and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached["cached"] = True
            return cached
        except Exception:
            pass

    symbols = [x["gene"] for x in normalized_inputs]
    ot_map = _query_opentargets_batch(symbols) if live_network else {}

    targets: List[Dict[str, Any]] = []
    concordant_drugs: List[Dict[str, Any]] = []
    blocked_drugs: List[Dict[str, Any]] = []
    neutral_drugs: List[Dict[str, Any]] = []
    disease_tokens = [tok for tok in re.split(r"[\s,/-]+", clean_disease.lower()) if len(tok) >= 4]

    for item in normalized_inputs:
        sym = item["gene"]
        lfc = item["log2FC"]
        padj = item["padj"]
        flip = classify_flip_action(lfc)
        ot = ot_map.get(sym) or {}

        ensg_id = ot.get("id")
        approved_name = ot.get("approvedName") or ""
        is_essential = ot.get("isEssential")
        safety_events = [
            str(sl.get("event")) for sl in (ot.get("safetyLiabilities") or []) if sl and sl.get("event")
        ]
        tractable_modalities = sorted(
            {
                str(tr.get("modality"))
                for tr in (ot.get("tractability") or [])
                if tr and tr.get("value") is True and tr.get("modality")
            }
        )
        assoc_rows = (ot.get("associatedDiseases") or {}).get("rows") or []
        top_diseases = [
            {
                "id": str((r.get("disease") or {}).get("id", "")),
                "name": str((r.get("disease") or {}).get("name", "")),
                "score": round(float(r.get("score", 0.0)), 3),
            }
            for r in assoc_rows[:4]
            if r and r.get("disease")
        ]

        # Prioritize matching disease association score if present
        matching_disease_score = 0.0
        for d in top_diseases:
            d_lower = d["name"].lower()
            if any(tok in d_lower for tok in disease_tokens) or ("cancer" in clean_disease.lower() and any(k in d_lower for k in ("carcinoma", "cancer", "tumor", "neoplasm", "leukemia", "melanoma"))):
                matching_disease_score = max(matching_disease_score, d["score"])
        effective_disease_score = matching_disease_score or (top_diseases[0]["score"] if top_diseases else 0.0)

        # Parse real clinical drugs & run deterministic MoA Concordance Audit
        drug_rows = (ot.get("drugAndClinicalCandidates") or {}).get("rows") or []
        seen_drugs_for_gene: set[str] = set()
        gene_concordant_count = 0
        max_concordant_rank = -1

        for dr in drug_rows:
            drug_obj = dr.get("drug") or {}
            drug_name = str(drug_obj.get("name") or "").strip()
            drug_id = str(drug_obj.get("id") or "").strip()
            if not drug_name or drug_name.upper() in seen_drugs_for_gene:
                continue
            seen_drugs_for_gene.add(drug_name.upper())

            stage_raw = str(dr.get("maxClinicalStage") or "UNKNOWN").upper()
            stage_rank = STAGE_RANK.get(stage_raw, 0)
            if stage_rank < 0:
                continue  # skip withdrawn compounds from primary recommendations

            moa_rows = (drug_obj.get("mechanismsOfAction") or {}).get("rows") or []
            action_type = str(moa_rows[0].get("actionType") or "") if moa_rows else ""
            mechanism = str(moa_rows[0].get("mechanismOfAction") or "") if moa_rows else ""

            moa_status, moa_note = evaluate_moa_concordance(lfc, action_type, mechanism)
            seen_ind: set[str] = set()
            indications: List[str] = []
            for d in (dr.get("diseases") or []):
                if not d or not d.get("disease"):
                    continue
                ind_name = str((d.get("disease") or {}).get("name", "")).strip()
                ind_key = ind_name.lower()
                if ind_name and ind_key not in seen_ind:
                    seen_ind.add(ind_key)
                    indications.append(ind_name)
                    if len(indications) >= 3:
                        break

            drug_rec = {
                "drug_id": drug_id,
                "drug_name": drug_name,
                "drug_type": str(drug_obj.get("drugType") or "Small molecule"),
                "target_gene": sym,
                "target_log2FC": lfc,
                "recommended_flip": flip["recommended_flip"],
                "action_type": action_type or "Unspecified",
                "mechanism": mechanism or "Recorded in Open Targets / ChEMBL",
                "clinical_stage": stage_raw,
                "clinical_stage_label": STAGE_LABELS.get(stage_raw, stage_raw.replace("_", " ").title()),
                "stage_rank": stage_rank,
                "indications": indications,
                "moa_audit_status": moa_status,
                "moa_audit_note": moa_note,
                "url": f"https://platform.opentargets.org/drug/{drug_id}" if drug_id else "",
            }

            if moa_status == "CONCORDANT":
                concordant_drugs.append(drug_rec)
                gene_concordant_count += 1
                max_concordant_rank = max(max_concordant_rank, stage_rank)
            elif moa_status == "DISCORDANT_BLOCKED":
                blocked_drugs.append(drug_rec)
            else:
                neutral_drugs.append(drug_rec)

        priority = compute_target_priority_score(
            log2fc=lfc,
            padj=padj,
            top_disease_score=effective_disease_score,
            max_concordant_stage_rank=max_concordant_rank,
            tractable_modalities=tractable_modalities,
            is_essential=is_essential,
            safety_liability_count=len(safety_events),
        )

        safety_warning: Optional[str] = None
        if is_essential is True:
            safety_warning = "Pan-essential gene in DepMap/Open Targets: systemic inhibition carries healthy-cell toxicity risk."
        elif len(safety_events) >= 5:
            safety_warning = f"{len(safety_events)} known safety liabilities recorded in Open Targets; review organ toxicity before wet-lab translation."

        targets.append(
            {
                "gene": sym,
                "ensembl_id": ensg_id,
                "approved_name": approved_name,
                "log2FC": lfc,
                "padj": padj,
                "direction": item["direction"],
                "recommended_flip": flip["recommended_flip"],
                "expected_moa_class": flip["expected_moa_class"],
                "flip_rationale": flip["rationale"],
                "priority_score": priority["total_score"],
                "evidence_tier": priority["evidence_tier"],
                "score_breakdown": priority["breakdown"],
                "is_essential": is_essential,
                "tractable_modalities": tractable_modalities,
                "safety_liabilities_count": len(safety_events),
                "safety_events_sample": safety_events[:4],
                "safety_warning": safety_warning,
                "total_known_drugs": int((ot.get("drugAndClinicalCandidates") or {}).get("count") or 0),
                "concordant_drugs_count": gene_concordant_count,
                "associated_diseases": top_diseases,
                "opentargets_url": f"https://platform.opentargets.org/target/{ensg_id}" if ensg_id else "",
            }
        )

    targets.sort(key=lambda x: (-x["priority_score"], -abs(x["log2FC"])))
    concordant_drugs.sort(key=lambda x: (-x["stage_rank"], -abs(x["target_log2FC"])))
    blocked_drugs.sort(key=lambda x: (-x["stage_rank"], -abs(x["target_log2FC"])))

    # Fetch live PubMed literature & ClinicalTrials.gov for top 3 prioritized targets
    literature_hits: List[Dict[str, Any]] = []
    clinical_trials: List[Dict[str, Any]] = []
    if live_network:
        seen_pmids: set[str] = set()
        seen_ncts: set[str] = set()
        for t in targets[:3]:
            for hit in _query_pubmed(t["gene"], clean_disease, max_results=2):
                if hit["pmid"] not in seen_pmids:
                    seen_pmids.add(hit["pmid"])
                    literature_hits.append(hit)
            for ct in _query_clinical_trials(t["gene"], clean_disease, max_results=2):
                if ct["nct_id"] not in seen_ncts:
                    seen_ncts.add(ct["nct_id"])
                    clinical_trials.append(ct)

    wetlab_plan = _build_wetlab_plan(dataset_name, clean_disease, targets, concordant_drugs)

    dossier = {
        "dataset": dataset_name,
        "disease_context": clean_disease,
        "sources": {
            "opentargets_queried": bool(ot_map),
            "targets_mapped": len(ot_map),
            "targets_evaluated": len(targets),
            "pubmed_hits": len(literature_hits),
            "clinical_trials_hits": len(clinical_trials),
        },
        "targets": targets,
        "concordant_drugs": concordant_drugs[:20],
        "blocked_drugs": blocked_drugs[:10],
        "neutral_drugs": neutral_drugs[:10],
        "literature": literature_hits[:8],
        "clinical_trials": clinical_trials[:8],
        "wetlab_plan": wetlab_plan,
        "moa_audit_summary": {
            "concordant_count": len(concordant_drugs),
            "discordant_blocked_count": len(blocked_drugs),
            "neutral_review_count": len(neutral_drugs),
            "guard_status": "ACTIVE — Mechanistically discordant drugs automatically blocked",
        },
        "latency_s": round(time.time() - t0, 2),
        "cached": False,
    }

    if use_cache and live_network and ot_map and cache_path.is_relative_to(CACHE_DIR.resolve()):
        try:
            cache_path.write_text(json.dumps(dossier, indent=2), encoding="utf-8")
        except Exception:
            pass

    return dossier
