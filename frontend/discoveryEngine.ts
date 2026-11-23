import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import {
  STAGE_LABELS,
  STAGE_RANK,
  classifyFlipAction,
  computeTargetPriorityScore,
  evaluateMoaConcordance,
  sanitizeDiseaseContext,
  sanitizeGeneSymbol,
  type ClinicalTrialHit,
  type DiscoveryDossier,
  type DrugCandidate,
  type LiteratureHit,
  type TargetDossierItem,
} from "./src/lib/discoveryAudit.ts";

const REPO_ROOT = path.resolve(import.meta.dirname, "..");
const CACHE_DIR = path.join(REPO_ROOT, "outputs", "cache");
fs.mkdirSync(CACHE_DIR, { recursive: true });

const OPENTARGETS_URL = "https://api.platform.opentargets.org/api/v4/graphql";
const PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi";
const PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi";
const CLINICALTRIALS_URL = "https://clinicaltrials.gov/api/v2/studies";
const USER_AGENT = "BioAgent-Lite/2.1 (Research Therapeutic Discovery Workbench)";

async function fetchJsonWithTimeout(url: string, init?: RequestInit, timeoutMs = 8000): Promise<any | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      ...init,
      signal: controller.signal,
      headers: {
        "User-Agent": USER_AGENT,
        Accept: "application/json",
        ...(init?.headers || {}),
      },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

async function queryOpenTargetsBatch(geneSymbols: string[]): Promise<Record<string, any>> {
  if (!geneSymbols.length) return {};

  const mapQuery = `
    query MapTargets($terms: [String!]!) {
      mapIds(queryTerms: $terms, entityNames: ["target"]) {
        mappings {
          term
          hits { id name entity }
        }
      }
    }
  `;
  const mapped = await fetchJsonWithTimeout(
    OPENTARGETS_URL,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: mapQuery, variables: { terms: geneSymbols } }),
    },
    9000
  );
  const mappings: any[] = mapped?.data?.mapIds?.mappings || [];
  const symToEnsg: Record<string, string> = {};
  for (const entry of mappings) {
    const term = String(entry?.term || "").toUpperCase();
    const hits: any[] = entry?.hits || [];
    if (!hits.length) continue;
    const exact = hits.find((h) => String(h?.name || "").toUpperCase() === term) || hits[0];
    if (exact?.id) symToEnsg[term] = exact.id;
  }

  const ensgIds = Array.from(new Set(Object.values(symToEnsg)));
  if (!ensgIds.length) return {};

  const targetsQuery = `
    query TargetDetails($ids: [String!]!) {
      targets(ensemblIds: $ids) {
        id
        approvedSymbol
        approvedName
        isEssential
        tractability { label modality value }
        safetyLiabilities { event }
        associatedDiseases(page: { index: 0, size: 5 }) {
          rows { score disease { id name } }
        }
        drugAndClinicalCandidates {
          count
          rows {
            maxClinicalStage
            drug {
              id
              name
              drugType
              mechanismsOfAction { rows { mechanismOfAction actionType } }
            }
            diseases { disease { id name } }
          }
        }
      }
    }
  `;
  const detail = await fetchJsonWithTimeout(
    OPENTARGETS_URL,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: targetsQuery, variables: { ids: ensgIds } }),
    },
    11000
  );
  const byEnsg: Record<string, any> = {};
  for (const t of detail?.data?.targets || []) {
    if (t?.id) byEnsg[t.id] = t;
  }

  const out: Record<string, any> = {};
  for (const [sym, ensg] of Object.entries(symToEnsg)) {
    if (byEnsg[ensg]) out[sym] = byEnsg[ensg];
  }
  return out;
}

async function queryPubMed(geneSymbol: string, diseaseContext: string, maxResults = 2): Promise<LiteratureHit[]> {
  const qs = new URLSearchParams({
    db: "pubmed",
    term: `(${geneSymbol}[Title/Abstract]) AND (${diseaseContext}[Title/Abstract])`,
    retmax: String(maxResults),
    retmode: "json",
    sort: "relevance",
  });
  const search = await fetchJsonWithTimeout(`${PUBMED_ESEARCH_URL}?${qs.toString()}`, undefined, 6000);
  const pmids: string[] = search?.esearchresult?.idlist || [];
  if (!pmids.length) return [];

  const sumQs = new URLSearchParams({
    db: "pubmed",
    id: pmids.join(","),
    retmode: "json",
  });
  const summary = await fetchJsonWithTimeout(`${PUBMED_ESUMMARY_URL}?${sumQs.toString()}`, undefined, 6000);
  const resBlock = summary?.result || {};
  const hits: LiteratureHit[] = [];
  for (const pmid of pmids) {
    if (!/^\d+$/.test(String(pmid))) continue;
    const item = resBlock[String(pmid)];
    if (!item || typeof item !== "object") continue;
    hits.push({
      pmid: String(pmid),
      gene: geneSymbol,
      title: String(item.title || "").trim().replace(/\.$/, ""),
      journal: String(item.fulljournalname || item.source || ""),
      pub_date: String(item.pubdate || ""),
      url: `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`,
    });
  }
  return hits;
}

async function queryClinicalTrials(geneSymbol: string, diseaseContext: string, maxResults = 2): Promise<ClinicalTrialHit[]> {
  const qs = new URLSearchParams({
    "query.term": `${geneSymbol} ${diseaseContext}`,
    pageSize: String(maxResults),
  });
  const data = await fetchJsonWithTimeout(`${CLINICALTRIALS_URL}?${qs.toString()}`, undefined, 6000);
  const studies: any[] = data?.studies || [];
  const hits: ClinicalTrialHit[] = [];
  for (const s of studies) {
    const proto = s?.protocolSection || {};
    const ident = proto.identificationModule || {};
    const status = proto.statusModule || {};
    const design = proto.designModule || {};
    const nctId = String(ident.nctId || "").trim();
    if (!/^NCT\d+$/.test(nctId)) continue;
    const phases: string[] = design.phases || [];
    hits.push({
      nct_id: nctId,
      query_gene_or_drug: geneSymbol,
      title: String(ident.briefTitle || ident.officialTitle || "").trim(),
      status: String(status.overallStatus || "UNKNOWN"),
      phase: phases.length ? phases.join(", ") : "N/A",
      url: `https://clinicaltrials.gov/study/${nctId}`,
    });
  }
  return hits;
}

export function defaultDiseaseForDataset(dataset: string, requested?: string): string {
  if (requested && requested.trim() && requested.trim().toLowerCase() !== "auto") {
    return sanitizeDiseaseContext(requested);
  }
  const map: Record<string, string> = {
    GSE202768: "triple-negative breast cancer",
    GSE113650: "triple-negative breast cancer",
    GSE95304: "cancer MYC",
    GSE336903: "cancer",
    PDAC_Gemcitabine: "pancreatic ductal adenocarcinoma",
  };
  return map[dataset] || "cancer";
}

export async function runLiveTargetDiscovery(params: {
  topGenes: Array<{ gene: string; log2FC: number; padj?: number | null }>;
  diseaseContext?: string;
  datasetName?: string;
  maxTargets?: number;
}): Promise<DiscoveryDossier> {
  const t0 = Date.now();
  const datasetName = params.datasetName || "dataset";
  const cleanDisease = defaultDiseaseForDataset(datasetName, params.diseaseContext);
  const maxTargets = Math.max(1, Math.min(12, params.maxTargets ?? 10));

  const inputs: Array<{ gene: string; log2FC: number; padj: number | null; direction: "up" | "down" }> = [];
  const seen = new Set<string>();
  for (const g of params.topGenes || []) {
    const sym = sanitizeGeneSymbol(g?.gene);
    if (!sym || seen.has(sym)) continue;
    const lfc = Number(g?.log2FC);
    if (!Number.isFinite(lfc)) continue;
    const padjRaw = g?.padj;
    const padj = padjRaw !== null && padjRaw !== undefined && Number.isFinite(Number(padjRaw)) ? Number(padjRaw) : null;
    seen.add(sym);
    inputs.push({ gene: sym, log2FC: Number(lfc.toFixed(4)), padj, direction: lfc >= 0 ? "up" : "down" });
    if (inputs.length >= maxTargets) break;
  }

  const hash = crypto
    .createHash("sha256")
    .update(
      JSON.stringify({
        v: 3,
        disease: cleanDisease.toLowerCase(),
        genes: inputs.map((x) => [x.gene, Number(x.log2FC.toFixed(2))]),
      })
    )
    .digest("hex")
    .slice(0, 16);

  const cachePath = path.resolve(CACHE_DIR, `discovery_${hash}.json`);
  const cacheBase = path.resolve(CACHE_DIR);
  if (cachePath.startsWith(cacheBase + path.sep) && fs.existsSync(cachePath)) {
    try {
      const cached = JSON.parse(fs.readFileSync(cachePath, "utf-8"));
      return { ...cached, cached: true };
    } catch {
      // fall through to live query
    }
  }

  const otMap = await queryOpenTargetsBatch(inputs.map((x) => x.gene));
  const diseaseTokens = cleanDisease
    .toLowerCase()
    .split(/[\s,/-]+/)
    .filter((tok) => tok.length >= 4);

  const targets: TargetDossierItem[] = [];
  const concordantDrugs: DrugCandidate[] = [];
  const blockedDrugs: DrugCandidate[] = [];
  const neutralDrugs: DrugCandidate[] = [];

  for (const item of inputs) {
    const flip = classifyFlipAction(item.log2FC);
    const ot = otMap[item.gene] || {};
    const ensgId: string | null = ot.id || null;
    const approvedName = String(ot.approvedName || "");
    const isEssential: boolean | null = typeof ot.isEssential === "boolean" ? ot.isEssential : null;
    const safetyEvents: string[] = (ot.safetyLiabilities || [])
      .map((s: any) => String(s?.event || ""))
      .filter(Boolean);
    const tractableModalities: string[] = Array.from(
      new Set(
        (ot.tractability || [])
          .filter((tr: any) => tr?.value === true && tr?.modality)
          .map((tr: any) => String(tr.modality))
      )
    ).sort();

    const assocRows: any[] = ot.associatedDiseases?.rows || [];
    const topDiseases = assocRows
      .slice(0, 4)
      .filter((r) => r?.disease)
      .map((r) => ({
        id: String(r.disease.id || ""),
        name: String(r.disease.name || ""),
        score: Number(Number(r.score || 0).toFixed(3)),
      }));

    let matchingDiseaseScore = 0;
    for (const d of topDiseases) {
      const dl = d.name.toLowerCase();
      if (
        diseaseTokens.some((tok) => dl.includes(tok)) ||
        (cleanDisease.toLowerCase().includes("cancer") &&
          /(carcinoma|cancer|tumor|neoplasm|leukemia|melanoma)/.test(dl))
      ) {
        matchingDiseaseScore = Math.max(matchingDiseaseScore, d.score);
      }
    }
    const effectiveDiseaseScore = matchingDiseaseScore || (topDiseases[0]?.score ?? 0);

    const drugRows: any[] = ot.drugAndClinicalCandidates?.rows || [];
    const seenDrugs = new Set<string>();
    let geneConcordantCount = 0;
    let maxConcordantStageRank = -1;

    for (const dr of drugRows) {
      const drugObj = dr?.drug || {};
      const drugName = String(drugObj.name || "").trim();
      const drugId = String(drugObj.id || "").trim();
      if (!drugName || seenDrugs.has(drugName.toUpperCase())) continue;
      seenDrugs.add(drugName.toUpperCase());

      const stageRaw = String(dr.maxClinicalStage || "UNKNOWN").toUpperCase();
      const stageRank = STAGE_RANK[stageRaw] ?? 0;
      if (stageRank < 0) continue;

      const moaRows: any[] = drugObj.mechanismsOfAction?.rows || [];
      const actionType = String(moaRows[0]?.actionType || "");
      const mechanism = String(moaRows[0]?.mechanismOfAction || "");
      const moaAudit = evaluateMoaConcordance(item.log2FC, actionType, mechanism);

      const seenInd = new Set<string>();
      const indications: string[] = [];
      for (const d of dr.diseases || []) {
        const name = String(d?.disease?.name || "").trim();
        const key = name.toLowerCase();
        if (name && !seenInd.has(key)) {
          seenInd.add(key);
          indications.push(name);
          if (indications.length >= 3) break;
        }
      }

      const rec: DrugCandidate = {
        drug_id: drugId,
        drug_name: drugName,
        drug_type: String(drugObj.drugType || "Small molecule"),
        target_gene: item.gene,
        target_log2FC: item.log2FC,
        recommended_flip: flip.recommended_flip,
        action_type: actionType || "Unspecified",
        mechanism: mechanism || "Recorded in Open Targets / ChEMBL",
        clinical_stage: stageRaw,
        clinical_stage_label: STAGE_LABELS[stageRaw] || stageRaw.replace(/_/g, " "),
        stage_rank: stageRank,
        indications,
        moa_audit_status: moaAudit.status,
        moa_audit_note: moaAudit.note,
        url: drugId ? `https://platform.opentargets.org/drug/${drugId}` : "",
      };

      if (moaAudit.status === "CONCORDANT") {
        concordantDrugs.push(rec);
        geneConcordantCount += 1;
        maxConcordantStageRank = Math.max(maxConcordantStageRank, stageRank);
      } else if (moaAudit.status === "DISCORDANT_BLOCKED") {
        blockedDrugs.push(rec);
      } else {
        neutralDrugs.push(rec);
      }
    }

    const priority = computeTargetPriorityScore({
      log2FC: item.log2FC,
      padj: item.padj,
      topDiseaseScore: effectiveDiseaseScore,
      maxConcordantStageRank,
      tractableModalities,
      isEssential,
      safetyLiabilityCount: safetyEvents.length,
    });

    let safetyWarning: string | null = null;
    if (isEssential === true) {
      safetyWarning =
        "Pan-essential gene in DepMap/Open Targets: systemic inhibition carries healthy-cell toxicity risk.";
    } else if (safetyEvents.length >= 5) {
      safetyWarning = `${safetyEvents.length} recorded safety liabilities in Open Targets; review organ toxicity before translation.`;
    }

    targets.push({
      gene: item.gene,
      ensembl_id: ensgId,
      approved_name: approvedName,
      log2FC: item.log2FC,
      padj: item.padj,
      direction: item.direction,
      recommended_flip: flip.recommended_flip,
      expected_moa_class: flip.expected_moa_class,
      flip_rationale: flip.rationale,
      priority_score: priority.total_score,
      evidence_tier: priority.evidence_tier,
      score_breakdown: priority.breakdown,
      is_essential: isEssential,
      tractable_modalities: tractableModalities,
      safety_liabilities_count: safetyEvents.length,
      safety_events_sample: safetyEvents.slice(0, 4),
      safety_warning: safetyWarning,
      total_known_drugs: Number(ot.drugAndClinicalCandidates?.count || 0),
      concordant_drugs_count: geneConcordantCount,
      associated_diseases: topDiseases,
      opentargets_url: ensgId ? `https://platform.opentargets.org/target/${ensgId}` : "",
    });
  }

  targets.sort((a, b) => b.priority_score - a.priority_score || Math.abs(b.log2FC) - Math.abs(a.log2FC));
  concordantDrugs.sort((a, b) => b.stage_rank - a.stage_rank || Math.abs(b.target_log2FC) - Math.abs(a.target_log2FC));
  blockedDrugs.sort((a, b) => b.stage_rank - a.stage_rank || Math.abs(b.target_log2FC) - Math.abs(a.target_log2FC));

  // Query live PubMed & ClinicalTrials.gov in parallel for top 3 prioritized targets
  const top3 = targets.slice(0, 3);
  const [litArrays, trialArrays] = await Promise.all([
    Promise.all(top3.map((t) => queryPubMed(t.gene, cleanDisease, 2))),
    Promise.all(top3.map((t) => queryClinicalTrials(t.gene, cleanDisease, 2))),
  ]);

  const seenPmid = new Set<string>();
  const literature: LiteratureHit[] = [];
  for (const arr of litArrays) {
    for (const h of arr) {
      if (!seenPmid.has(h.pmid)) {
        seenPmid.add(h.pmid);
        literature.push(h);
      }
    }
  }

  const seenNct = new Set<string>();
  const clinicalTrials: ClinicalTrialHit[] = [];
  for (const arr of trialArrays) {
    for (const c of arr) {
      if (!seenNct.has(c.nct_id)) {
        seenNct.add(c.nct_id);
        clinicalTrials.push(c);
      }
    }
  }

  const topUp = targets.filter((t) => t.log2FC > 0).slice(0, 3);
  const topDown = targets.filter((t) => t.log2FC < 0).slice(0, 2);
  const qpcrPanel = [...topUp, ...topDown].slice(0, 5).map((t) => t.gene);
  const steps: string[] = [];
  if (concordantDrugs.length > 0) {
    const lead = concordantDrugs[0];
    steps.push(
      `Drug Repurposing Viability Screen: Test ${lead.drug_name} (${lead.action_type}, ${lead.clinical_stage_label}) targeting ${lead.target_gene} across a 6-point dose-response assay (72h viability readout) in a ${cleanDisease} model.`
    );
  }
  if (topUp.length > 0) {
    steps.push(
      `Genetic Flip Confirmation (Turn OFF): Perform siRNA or CRISPRi knockdown of ${topUp[0].gene} (log2FC=+${topUp[0].log2FC.toFixed(2)}) to verify phenotype reversal or restored drug sensitivity.`
    );
  }
  if (topDown.length > 0) {
    steps.push(
      `Rescue / Biomarker Tracking (Turn ON): Track expression recovery of suppressed marker ${topDown[0].gene} (log2FC=${topDown[0].log2FC.toFixed(2)}) following perturbation or drug treatment.`
    );
  }
  if (qpcrPanel.length > 0) {
    steps.push(
      `Orthogonal 5-Gene RT-qPCR Validation Panel: Measure ${qpcrPanel.join(", ")} alongside housekeeping controls across >=3 biological replicates.`
    );
  }

  const dossier: DiscoveryDossier = {
    dataset: datasetName,
    disease_context: cleanDisease,
    sources: {
      opentargets_queried: Object.keys(otMap).length > 0,
      targets_mapped: Object.keys(otMap).length,
      targets_evaluated: targets.length,
      pubmed_hits: literature.length,
      clinical_trials_hits: clinicalTrials.length,
    },
    targets,
    concordant_drugs: concordantDrugs.slice(0, 20),
    blocked_drugs: blockedDrugs.slice(0, 10),
    neutral_drugs: neutralDrugs.slice(0, 10),
    literature: literature.slice(0, 8),
    clinical_trials: clinicalTrials.slice(0, 8),
    wetlab_plan: {
      dataset: datasetName,
      disease_context: cleanDisease,
      recommended_qpcr_panel: qpcrPanel,
      priority_targets: targets.slice(0, 3).map((t) => t.gene),
      actionable_steps: steps,
      caution:
        "All wet-lab suggestions are exploratory research hypotheses derived from differential expression, Open Targets, PubMed, and ClinicalTrials.gov—not clinical treatment protocols.",
    },
    moa_audit_summary: {
      concordant_count: concordantDrugs.length,
      discordant_blocked_count: blockedDrugs.length,
      neutral_review_count: neutralDrugs.length,
      guard_status: "ACTIVE — Mechanistically discordant drugs automatically blocked",
    },
    latency_s: Number(((Date.now() - t0) / 1000).toFixed(2)),
    cached: false,
  };

  if (Object.keys(otMap).length > 0 && cachePath.startsWith(cacheBase + path.sep)) {
    try {
      fs.writeFileSync(cachePath, JSON.stringify(dossier, null, 2), "utf-8");
    } catch {
      // non-fatal cache write error
    }
  }

  return dossier;
}
