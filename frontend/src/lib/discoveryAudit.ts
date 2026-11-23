export interface DrugCandidate {
  drug_id: string;
  drug_name: string;
  drug_type: string;
  target_gene: string;
  target_log2FC: number;
  recommended_flip: string;
  action_type: string;
  mechanism: string;
  clinical_stage: string;
  clinical_stage_label: string;
  stage_rank: number;
  indications: string[];
  moa_audit_status: "CONCORDANT" | "DISCORDANT_BLOCKED" | "NEUTRAL_REVIEW";
  moa_audit_note: string;
  url: string;
}

export interface TargetDossierItem {
  gene: string;
  ensembl_id: string | null;
  approved_name: string;
  log2FC: number;
  padj: number | null;
  direction: "up" | "down";
  recommended_flip: string;
  expected_moa_class: "inhibitory" | "activating";
  flip_rationale: string;
  priority_score: number;
  evidence_tier: string;
  score_breakdown: {
    transcriptomic_0_30: number;
    disease_evidence_0_25: number;
    druggability_0_25: number;
    safety_selectivity_0_20: number;
  };
  is_essential: boolean | null;
  tractable_modalities: string[];
  safety_liabilities_count: number;
  safety_events_sample: string[];
  safety_warning: string | null;
  total_known_drugs: number;
  concordant_drugs_count: number;
  associated_diseases: Array<{ id: string; name: string; score: number }>;
  opentargets_url: string;
}

export interface LiteratureHit {
  pmid: string;
  gene: string;
  title: string;
  journal: string;
  pub_date: string;
  url: string;
}

export interface ClinicalTrialHit {
  nct_id: string;
  query_gene_or_drug: string;
  title: string;
  status: string;
  phase: string;
  url: string;
}

export interface WetLabPlan {
  dataset: string;
  disease_context: string;
  recommended_qpcr_panel: string[];
  priority_targets: string[];
  actionable_steps: string[];
  caution: string;
}

export interface DiscoveryDossier {
  dataset: string;
  disease_context: string;
  sources: {
    opentargets_queried: boolean;
    targets_mapped: number;
    targets_evaluated: number;
    pubmed_hits: number;
    clinical_trials_hits: number;
  };
  targets: TargetDossierItem[];
  concordant_drugs: DrugCandidate[];
  blocked_drugs: DrugCandidate[];
  neutral_drugs: DrugCandidate[];
  literature: LiteratureHit[];
  clinical_trials: ClinicalTrialHit[];
  wetlab_plan: WetLabPlan;
  moa_audit_summary: {
    concordant_count: number;
    discordant_blocked_count: number;
    neutral_review_count: number;
    guard_status: string;
  };
  latency_s: number;
  cached?: boolean;
}

const GENE_SYM_RE = /^[A-Za-z0-9._-]{2,24}$/;

const INHIBITORY_MOA_TOKENS = new Set([
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
]);

const ACTIVATING_MOA_TOKENS = new Set([
  "AGONIST",
  "PARTIAL AGONIST",
  "ACTIVATOR",
  "POSITIVE MODULATOR",
  "POSITIVE ALLOSTERIC MODULATOR",
  "OPENER",
  "STABILISER",
  "RELEASING AGENT",
]);

export const STAGE_RANK: Record<string, number> = {
  APPROVAL: 4,
  PHASE_4: 4,
  PHASE_3: 3,
  PHASE_2_3: 3,
  PHASE_2: 2,
  PHASE_1_2: 2,
  PHASE_1: 1,
  EARLY_PHASE_1: 1,
  PRECLINICAL: 0,
  UNKNOWN: 0,
  WITHDRAWAL: -1,
};

export const STAGE_LABELS: Record<string, string> = {
  APPROVAL: "FDA / Regulatory Approved",
  PHASE_4: "Approved (Phase 4)",
  PHASE_3: "Phase 3 Clinical",
  PHASE_2_3: "Phase 2/3 Clinical",
  PHASE_2: "Phase 2 Clinical",
  PHASE_1_2: "Phase 1/2 Clinical",
  PHASE_1: "Phase 1 Clinical",
  EARLY_PHASE_1: "Early Phase 1",
  PRECLINICAL: "Preclinical",
  WITHDRAWAL: "Withdrawn",
  UNKNOWN: "Investigated",
};

export function sanitizeGeneSymbol(raw: string): string | null {
  const sym = String(raw || "").trim().toUpperCase();
  return GENE_SYM_RE.test(sym) ? sym : null;
}

export function sanitizeDiseaseContext(raw: string): string {
  const cleaned = String(raw || "cancer")
    .replace(/[^A-Za-z0-9\s,\-()/]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return (cleaned || "cancer").slice(0, 100);
}

export function classifyFlipAction(log2FC: number): {
  recommended_flip: string;
  expected_moa_class: "inhibitory" | "activating";
  rationale: string;
} {
  if (log2FC > 0) {
    return {
      recommended_flip: "Suppress / Inhibit (Turn OFF)",
      expected_moa_class: "inhibitory",
      rationale:
        "Elevated expression in disease or resistance state; candidate for inhibition, knockdown, or pathway blockade.",
    };
  }
  return {
    recommended_flip: "Restore / Activate (Turn ON)",
    expected_moa_class: "activating",
    rationale:
      "Suppressed expression in disease or resistance state; candidate for restoration, agonism, or rescue validation.",
  };
}

export function evaluateMoaConcordance(
  log2FC: number,
  actionType?: string | null,
  mechanism?: string | null
): { status: "CONCORDANT" | "DISCORDANT_BLOCKED" | "NEUTRAL_REVIEW"; note: string } {
  const action = String(actionType || "").trim().toUpperCase();
  const mechUpper = String(mechanism || "").trim().toUpperCase();

  const isInhib =
    INHIBITORY_MOA_TOKENS.has(action) ||
    /(INHIBITOR|ANTAGONIST|BLOCKER|DEGRADER|NEGATIVE MODULATOR)/.test(mechUpper);
  const isActiv =
    ACTIVATING_MOA_TOKENS.has(action) ||
    /(AGONIST|ACTIVATOR|POSITIVE MODULATOR|OPENER)/.test(mechUpper);

  if (log2FC > 0) {
    if (isInhib && !isActiv) {
      return {
        status: "CONCORDANT",
        note: `Inhibitory MoA (${action || "inhibitor"}) matches upregulated target (log2FC=${log2FC >= 0 ? "+" : ""}${log2FC.toFixed(2)}).`,
      };
    }
    if (isActiv && !isInhib) {
      return {
        status: "DISCORDANT_BLOCKED",
        note: `Blocked by MoA Guard: activating drug (${action || "agonist"}) would worsen an already upregulated gene (log2FC=+${log2FC.toFixed(2)}).`,
      };
    }
    return {
      status: "NEUTRAL_REVIEW",
      note: `Mechanism (${action || mechanism || "unspecified"}) requires manual pharmacology review.`,
    };
  }

  if (isActiv && !isInhib) {
    return {
      status: "CONCORDANT",
      note: `Activating MoA (${action || "agonist"}) matches downregulated target (log2FC=${log2FC.toFixed(2)}).`,
    };
  }
  if (isInhib && !isActiv) {
    return {
      status: "DISCORDANT_BLOCKED",
      note: `Blocked by MoA Guard: inhibitory drug (${action || "inhibitor"}) conflicts with an already downregulated gene (log2FC=${log2FC.toFixed(2)}).`,
    };
  }
  return {
    status: "NEUTRAL_REVIEW",
    note: `Mechanism (${action || mechanism || "unspecified"}) requires manual pharmacology review.`,
  };
}

export function computeTargetPriorityScore(params: {
  log2FC: number;
  padj: number | null;
  topDiseaseScore: number;
  maxConcordantStageRank: number;
  tractableModalities: string[];
  isEssential: boolean | null;
  safetyLiabilityCount: number;
}): {
  total_score: number;
  evidence_tier: string;
  breakdown: TargetDossierItem["score_breakdown"];
} {
  const lfcComp = Math.min(22.0, Math.abs(params.log2FC) * 8.5);
  const sigComp =
    params.padj !== null && params.padj < 0.05 ? 8.0 : Math.abs(params.log2FC) >= 1.5 ? 4.0 : 2.0;
  const transcriptomic = Number(Math.min(30.0, lfcComp + sigComp).toFixed(1));

  const diseaseEvidence = Number(Math.min(25.0, Math.max(0, params.topDiseaseScore) * 25.0).toFixed(1));

  let druggability = 4.0;
  if (params.maxConcordantStageRank >= 4) druggability = 25.0;
  else if (params.maxConcordantStageRank >= 2) druggability = 21.0;
  else if (params.maxConcordantStageRank === 1) druggability = 17.0;
  else if (params.tractableModalities.length > 0) {
    druggability = Number(Math.min(15.0, 8.0 + params.tractableModalities.length * 2.5).toFixed(1));
  }

  let safety = 20.0;
  if (params.isEssential === true) safety -= 8.0;
  safety -= Math.min(10.0, params.safetyLiabilityCount * 1.25);
  safety = Number(Math.max(2.0, safety).toFixed(1));

  const total = Number(Math.min(100.0, transcriptomic + diseaseEvidence + druggability + safety).toFixed(1));

  let tier = "Tier 3: Novel Genetic Flip Target";
  if (params.maxConcordantStageRank >= 4) tier = "Tier 1: Approved Drug Repurposing";
  else if (params.maxConcordantStageRank >= 1 || params.tractableModalities.length >= 2) {
    tier = "Tier 2: Clinical / Tractable Candidate";
  }

  return {
    total_score: total,
    evidence_tier: tier,
    breakdown: {
      transcriptomic_0_30: transcriptomic,
      disease_evidence_0_25: diseaseEvidence,
      druggability_0_25: druggability,
      safety_selectivity_0_20: safety,
    },
  };
}
