import React, { useState } from "react";
import {
  Crosshair,
  Pill,
  BookOpen,
  FlaskConical,
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ArrowDownCircle,
  ArrowUpCircle,
  FileSpreadsheet,
  Info,
} from "lucide-react";
import { DiscoveryDossier } from "../lib/discoveryAudit";

interface TherapeuticDossierProps {
  discovery: DiscoveryDossier;
  targetDossierCsvHref?: string;
}

type DossierTab = "targets" | "drugs" | "evidence";

const SAFE_ENSEMBL_RE = /^ENSG\d+$/;
const SAFE_CHEMBL_RE = /^CHEMBL\d+$/;
const SAFE_PMID_RE = /^\d+$/;
const SAFE_NCT_RE = /^NCT\d+$/;

function getSafeTargetUrl(ensemblId: string | null): string | null {
  if (!ensemblId || !SAFE_ENSEMBL_RE.test(ensemblId)) return null;
  return `https://platform.opentargets.org/target/${ensemblId}`;
}

function getSafeDrugUrl(drugId: string): string | null {
  if (!drugId || !SAFE_CHEMBL_RE.test(drugId)) return null;
  return `https://platform.opentargets.org/drug/${drugId}`;
}

function getSafePubMedUrl(pmid: string): string | null {
  if (!pmid || !SAFE_PMID_RE.test(pmid)) return null;
  return `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;
}

function getSafeTrialUrl(nctId: string): string | null {
  if (!nctId || !SAFE_NCT_RE.test(nctId)) return null;
  return `https://clinicaltrials.gov/study/${nctId}`;
}

export const TherapeuticDossier: React.FC<TherapeuticDossierProps> = ({
  discovery,
  targetDossierCsvHref,
}) => {
  const [activeTab, setActiveTab] = useState<DossierTab>("targets");
  const [showBlockedDrugs, setShowBlockedDrugs] = useState<boolean>(true);
  const [showNeutralDrugs, setShowNeutralDrugs] = useState<boolean>(false);

  const targets = discovery.targets || [];
  const concordantDrugs = discovery.concordant_drugs || [];
  const blockedDrugs = discovery.blocked_drugs || [];
  const neutralDrugs = discovery.neutral_drugs || [];
  const literature = discovery.literature || [];
  const trials = discovery.clinical_trials || [];
  const wetlab = discovery.wetlab_plan;

  return (
    <div className="space-y-4">
      {/* Header + Disease Context */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-slate-800/80">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-xs mono-tabular font-semibold uppercase tracking-wider text-emerald-400">
              Therapeutic Target &amp; Drug Discovery Dossier
            </h3>
            <span className="text-[11px] mono-tabular text-slate-400">
              · Context: <span className="text-slate-200">{discovery.disease_context}</span>
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Live Open Targets v4 pharmacology · NCBI PubMed · ClinicalTrials.gov · Deterministic MoA Concordance Guard
          </p>
        </div>

        {targetDossierCsvHref && (
          <a
            href={targetDossierCsvHref}
            download={`${discovery.dataset}_target_dossier.csv`}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#07090E] hover:bg-slate-800 border border-slate-800 text-slate-200 text-xs transition"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
            <span>Export Targets CSV</span>
          </a>
        )}
      </div>

      {/* 4-Metric Dossier Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mono-tabular">
        <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800/80">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider">Targets Mapped</div>
          <div className="text-lg font-bold text-slate-100 mt-0.5">
            {discovery.sources.targets_mapped}
            <span className="text-xs font-normal text-slate-500"> / {discovery.sources.targets_evaluated}</span>
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {discovery.sources.opentargets_queried ? "Open Targets v4 Live" : "Offline Mode"}
          </div>
        </div>

        <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800/80">
          <div className="text-[10px] text-emerald-400 uppercase tracking-wider">Audited Drugs</div>
          <div className="text-lg font-bold text-emerald-400 mt-0.5">{concordantDrugs.length}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">MoA matches flip direction</div>
        </div>

        <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800/80">
          <div className="text-[10px] text-amber-400 uppercase tracking-wider">Blocked by Critic</div>
          <div className="text-lg font-bold text-amber-400 mt-0.5">{blockedDrugs.length}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Discordant MoA filtered out</div>
        </div>

        <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800/80">
          <div className="text-[10px] text-sky-400 uppercase tracking-wider">Verified Evidence</div>
          <div className="text-lg font-bold text-sky-400 mt-0.5">
            {literature.length}
            <span className="text-xs font-normal text-slate-500"> papers · </span>
            {trials.length}
            <span className="text-xs font-normal text-slate-500"> trials</span>
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Clickable PMIDs &amp; NCTs</div>
        </div>
      </div>

      {/* Sub-Tabs */}
      <div
        role="tablist"
        aria-label="Therapeutic discovery sections"
        className="flex items-center gap-1.5 p-1 rounded-lg bg-[#07090E] border border-slate-800/80 overflow-x-auto"
      >
        <button
          role="tab"
          aria-selected={activeTab === "targets"}
          onClick={() => setActiveTab("targets")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition whitespace-nowrap ${
            activeTab === "targets"
              ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
              : "text-slate-400 hover:text-slate-200 border border-transparent"
          }`}
        >
          <Crosshair className="w-3.5 h-3.5" />
          <span>Targets &amp; Gene Flipping ({targets.length})</span>
        </button>

        <button
          role="tab"
          aria-selected={activeTab === "drugs"}
          onClick={() => setActiveTab("drugs")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition whitespace-nowrap ${
            activeTab === "drugs"
              ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
              : "text-slate-400 hover:text-slate-200 border border-transparent"
          }`}
        >
          <Pill className="w-3.5 h-3.5" />
          <span>Drug Repurposing ({concordantDrugs.length})</span>
        </button>

        <button
          role="tab"
          aria-selected={activeTab === "evidence"}
          onClick={() => setActiveTab("evidence")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition whitespace-nowrap ${
            activeTab === "evidence"
              ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
              : "text-slate-400 hover:text-slate-200 border border-transparent"
          }`}
        >
          <FlaskConical className="w-3.5 h-3.5" />
          <span>Literature, Trials &amp; Lab Plan</span>
        </button>
      </div>

      {/* TAB 1: TARGETS & GENE FLIPPING */}
      {activeTab === "targets" && (
        <div className="space-y-3">
          <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-[#07090E] border border-slate-800/80 text-[11px] text-slate-400 leading-relaxed">
            <Info className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
            <span>
              <strong className="text-slate-200">How Gene Flipping Works:</strong> Genes elevated in disease (
              <span className="mono-tabular text-emerald-400">log2FC &gt; 0</span>) are prioritized to{" "}
              <strong className="text-slate-200">Turn OFF (Inhibit / Knock Down)</strong>. Genes lost in disease (
              <span className="mono-tabular text-rose-400">log2FC &lt; 0</span>) are flagged to{" "}
              <strong className="text-slate-200">Turn ON (Restore / Activate)</strong>. Priority scores (0–100) sum Expression (0–30), Disease Association (0–25), Druggability (0–25), and Safety (0–20).
            </span>
          </div>

          {targets.length === 0 ? (
            <div className="p-5 rounded-lg bg-[#07090E] border border-slate-800/80 text-center text-xs text-slate-400">
              No human gene symbols were mappable for this dataset. Upload a dataset with standard HGNC gene symbols (e.g., EGFR, TP53, TNF) to unlock Open Targets druggability scoring.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-800/80 bg-[#07090E]">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-[10px] mono-tabular uppercase tracking-wider text-slate-400">
                    <th className="py-2.5 px-3 font-medium">Gene Target</th>
                    <th className="py-2.5 px-3 font-medium">Observed Change</th>
                    <th className="py-2.5 px-3 font-medium">Gene-Flip Action</th>
                    <th className="py-2.5 px-3 font-medium">Priority Score</th>
                    <th className="py-2.5 px-3 font-medium">Safety &amp; Disease Link</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {targets.map((t) => {
                    const isUp = t.log2FC > 0;
                    const targetUrl = getSafeTargetUrl(t.ensembl_id);
                    const topDisease = t.associated_diseases?.[0];
                    return (
                      <tr key={t.gene} className="hover:bg-slate-900/50 transition-colors align-top">
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-slate-100 mono-tabular">{t.gene}</span>
                            {targetUrl && (
                              <a
                                href={targetUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-slate-500 hover:text-emerald-400 transition"
                                title={`Open ${t.gene} on Open Targets`}
                              >
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-400 mt-0.5 max-w-[200px] leading-snug">
                            {t.approved_name || "Unmapped symbol"}
                          </div>
                          <div className="text-[10px] mono-tabular text-slate-500 mt-1">
                            {t.concordant_drugs_count > 0
                              ? `${t.concordant_drugs_count} audited drug${t.concordant_drugs_count === 1 ? "" : "s"}`
                              : t.tractable_modalities.length > 0
                              ? t.tractable_modalities.slice(0, 2).join(" · ")
                              : "Genetic perturbation target"}
                          </div>
                        </td>

                        <td className="py-3 px-3 mono-tabular whitespace-nowrap">
                          <div className={`font-semibold ${isUp ? "text-emerald-400" : "text-rose-400"}`}>
                            {isUp ? "+" : ""}
                            {t.log2FC.toFixed(2)} log2FC
                          </div>
                          <div className="text-[10px] text-slate-500 mt-0.5">
                            {t.padj !== null
                              ? `padj ${t.padj < 1e-4 ? t.padj.toExponential(1) : t.padj.toFixed(4)}`
                              : "Descriptive FPKM"}
                          </div>
                        </td>

                        <td className="py-3 px-3">
                          <div className="flex items-center gap-1.5 font-medium text-slate-100 whitespace-nowrap">
                            {isUp ? (
                              <ArrowDownCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                            ) : (
                              <ArrowUpCircle className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                            )}
                            <span>{t.recommended_flip}</span>
                          </div>
                          <div className="text-[10px] text-slate-400 mt-0.5 max-w-[210px] leading-snug">
                            {t.flip_rationale}
                          </div>
                        </td>

                        <td className="py-3 px-3 mono-tabular">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-slate-100">
                              {t.priority_score.toFixed(1)}
                            </span>
                            <span className="text-[10px] text-slate-500">/ 100</span>
                          </div>
                          <div className="w-24 h-1.5 rounded-full bg-slate-800 overflow-hidden mt-1">
                            <div
                              className="h-full bg-emerald-400"
                              style={{ width: `${Math.min(100, Math.max(4, t.priority_score))}%` }}
                            />
                          </div>
                          <div className="text-[10px] text-emerald-400/90 mt-1">{t.evidence_tier}</div>
                          <div className="text-[10px] text-slate-500 mt-0.5">
                            E:{t.score_breakdown.transcriptomic_0_30} · D:{t.score_breakdown.disease_evidence_0_25} · Rx:
                            {t.score_breakdown.druggability_0_25} · S:{t.score_breakdown.safety_selectivity_0_20}
                          </div>
                        </td>

                        <td className="py-3 px-3">
                          {t.safety_warning ? (
                            <div className="flex items-start gap-1.5 text-amber-300 text-[11px] leading-snug">
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                              <span>{t.safety_warning}</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5 text-emerald-400 text-[11px]">
                              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                              <span>No critical liability flagged</span>
                            </div>
                          )}

                          {topDisease && (
                            <div className="text-[10px] text-slate-400 mt-1.5 leading-snug">
                              Top link: <span className="text-slate-200">{topDisease.name}</span>{" "}
                              <span className="mono-tabular text-slate-500">({topDisease.score.toFixed(2)})</span>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: DRUG REPURPOSING (MoA AUDITED) */}
      {activeTab === "drugs" && (
        <div className="space-y-4">
          {/* Concordant Drugs */}
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>MoA-Validated Repurposing Candidates ({concordantDrugs.length})</span>
              </div>
              <span className="text-[11px] text-slate-400">
                Every candidate matches the target&apos;s required Turn OFF / Turn ON direction
              </span>
            </div>

            {concordantDrugs.length === 0 ? (
              <div className="p-4 rounded-lg bg-[#07090E] border border-slate-800/80 text-xs text-slate-400 leading-relaxed">
                No FDA-approved or clinical-stage drugs with a direction-concordant mechanism were returned by Open Targets for these top genes. Check the{" "}
                <button
                  onClick={() => setActiveTab("evidence")}
                  className="text-emerald-400 hover:underline font-medium"
                >
                  Literature, Trials &amp; Lab Plan
                </button>{" "}
                tab for direct CRISPRi / siRNA / rescue validation steps.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-800/80 bg-[#07090E]">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-[10px] mono-tabular uppercase tracking-wider text-slate-400">
                      <th className="py-2.5 px-3 font-medium">Drug Candidate</th>
                      <th className="py-2.5 px-3 font-medium">Target &amp; Flip</th>
                      <th className="py-2.5 px-3 font-medium">Mechanism of Action</th>
                      <th className="py-2.5 px-3 font-medium">Clinical Stage</th>
                      <th className="py-2.5 px-3 font-medium">Known Indications</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70">
                    {concordantDrugs.slice(0, 20).map((d, idx) => {
                      const drugUrl = getSafeDrugUrl(d.drug_id);
                      return (
                        <tr key={`${d.drug_id}-${d.target_gene}-${idx}`} className="hover:bg-slate-900/50 transition-colors align-top">
                          <td className="py-2.5 px-3">
                            <div className="flex items-center gap-1.5">
                              <span className="font-semibold text-slate-100">{d.drug_name}</span>
                              {drugUrl && (
                                <a
                                  href={drugUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-slate-500 hover:text-emerald-400"
                                  title={`View ${d.drug_name} on Open Targets`}
                                >
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              )}
                            </div>
                            <div className="text-[10px] text-slate-500 mono-tabular mt-0.5">
                              {d.drug_type} · {d.drug_id}
                            </div>
                          </td>

                          <td className="py-2.5 px-3 mono-tabular whitespace-nowrap">
                            <div className="font-semibold text-emerald-400">{d.target_gene}</div>
                            <div className="text-[10px] text-slate-400 mt-0.5">
                              log2FC {d.target_log2FC >= 0 ? "+" : ""}
                              {d.target_log2FC.toFixed(2)}
                            </div>
                          </td>

                          <td className="py-2.5 px-3">
                            <div className="text-slate-200">{d.mechanism}</div>
                            <div className="text-[10px] mono-tabular text-emerald-400/90 mt-0.5">
                              {d.action_type} · CONCORDANT
                            </div>
                          </td>

                          <td className="py-2.5 px-3 whitespace-nowrap mono-tabular">
                            <span
                              className={`text-[11px] font-semibold ${
                                d.stage_rank >= 4
                                  ? "text-emerald-400"
                                  : d.stage_rank >= 2
                                  ? "text-sky-400"
                                  : "text-slate-300"
                              }`}
                            >
                              {d.clinical_stage_label}
                            </span>
                          </td>

                          <td className="py-2.5 px-3 text-[11px] text-slate-400 max-w-[220px]">
                            {(() => {
                              const uniqueInd = Array.from(new Set((d.indications || []).map((x) => x.trim()).filter(Boolean)));
                              return uniqueInd.length > 0 ? uniqueInd.join(", ") : "Investigated indication";
                            })()}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Blocked Discordant Drugs (Critic Safety Proof) */}
          {blockedDrugs.length > 0 && (
            <div className="rounded-lg bg-[#07090E] border border-amber-500/30 overflow-hidden">
              <button
                onClick={() => setShowBlockedDrugs((v) => !v)}
                className="w-full px-3.5 py-2.5 flex items-center justify-between text-left hover:bg-amber-500/5 transition"
              >
                <div className="flex items-center gap-2 text-xs">
                  <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
                  <span className="font-semibold text-amber-300">
                    Blocked by Critic MoA Safety Guard ({blockedDrugs.length} discordant drug
                    {blockedDrugs.length === 1 ? "" : "s"} filtered out)
                  </span>
                </div>
                {showBlockedDrugs ? (
                  <ChevronUp className="w-4 h-4 text-slate-400" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                )}
              </button>

              {showBlockedDrugs && (
                <div className="px-3.5 pb-3 pt-1 border-t border-slate-800/80 space-y-2 text-xs">
                  <p className="text-[11px] text-slate-400">
                    These drugs act in the <strong className="text-slate-200">opposite</strong> biological direction to what the RNA-seq expression requires (e.g., an inhibitor for an already downregulated gene) and are automatically excluded from recommendations.
                  </p>
                  <div className="divide-y divide-slate-800/70">
                    {blockedDrugs.slice(0, 12).map((d, idx) => (
                      <div key={`${d.drug_id}-blk-${idx}`} className="py-2 flex items-start justify-between gap-3 flex-wrap">
                        <div>
                          <span className="font-semibold text-slate-200">{d.drug_name}</span>{" "}
                          <span className="mono-tabular text-[11px] text-amber-400">
                            · {d.target_gene} ({d.action_type})
                          </span>
                          <div className="text-[11px] text-slate-400 mt-0.5">{d.moa_audit_note}</div>
                        </div>
                        <span className="mono-tabular text-[10px] text-amber-400 uppercase font-semibold shrink-0">
                          Blocked
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Neutral / Manual Review Drugs */}
          {neutralDrugs.length > 0 && (
            <div className="rounded-lg bg-[#07090E] border border-slate-800/80 overflow-hidden">
              <button
                onClick={() => setShowNeutralDrugs((v) => !v)}
                className="w-full px-3.5 py-2 flex items-center justify-between text-left text-xs text-slate-400 hover:text-slate-200 transition"
              >
                <span>Manual Pharmacology Review ({neutralDrugs.length} modulator / unspecified MoA entries)</span>
                {showNeutralDrugs ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showNeutralDrugs && (
                <div className="px-3.5 pb-3 pt-1 border-t border-slate-800/80 divide-y divide-slate-800/70 text-xs">
                  {neutralDrugs.slice(0, 10).map((d, idx) => (
                    <div key={`${d.drug_id}-neu-${idx}`} className="py-2">
                      <span className="font-semibold text-slate-200">{d.drug_name}</span>{" "}
                      <span className="mono-tabular text-[11px] text-slate-400">
                        · {d.target_gene} · {d.action_type} · {d.clinical_stage_label}
                      </span>
                      <div className="text-[11px] text-slate-500 mt-0.5">{d.mechanism}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: LITERATURE, TRIALS & NEXT WET-LAB STEP */}
      {activeTab === "evidence" && (
        <div className="space-y-4">
          {/* Actionable Wet-Lab Validation Plan */}
          {wetlab && (
            <div className="p-4 rounded-lg bg-[#07090E] border border-emerald-500/30 space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <FlaskConical className="w-4 h-4 text-emerald-400" />
                  <h4 className="text-xs font-semibold uppercase tracking-wider mono-tabular text-emerald-400">
                    Suggested Next Wet-Lab Validation Plan
                  </h4>
                </div>
                <span className="text-[11px] mono-tabular text-slate-400">{wetlab.disease_context}</span>
              </div>

              {wetlab.recommended_qpcr_panel.length > 0 && (
                <div className="text-xs text-slate-300">
                  <span className="text-slate-400">5-Gene RT-qPCR Verification Panel: </span>
                  <span className="mono-tabular font-semibold text-slate-100">
                    {wetlab.recommended_qpcr_panel.join(" · ")}
                  </span>
                </div>
              )}

              <ol className="space-y-1.5 text-xs text-slate-300 list-decimal pl-5 leading-relaxed">
                {wetlab.actionable_steps.map((step, idx) => (
                  <li key={idx}>{step}</li>
                ))}
              </ol>

              <div className="text-[10px] text-slate-500 pt-2 border-t border-slate-800/80">
                {wetlab.caution}
              </div>
            </div>
          )}

          {/* PubMed + ClinicalTrials.gov Side-by-Side */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* PubMed */}
            <div className="p-3.5 rounded-lg bg-[#07090E] border border-slate-800/80 space-y-2.5">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                  <BookOpen className="w-3.5 h-3.5 text-sky-400" />
                  <span>Verified PubMed Literature</span>
                </div>
                <span className="text-[10px] mono-tabular text-slate-500">{literature.length} PMIDs</span>
              </div>

              {literature.length === 0 ? (
                <p className="text-xs text-slate-500 py-2">
                  No direct PubMed matches returned for the top 3 genes in this disease context.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {literature.map((lit) => {
                    const pubmedUrl = getSafePubMedUrl(lit.pmid);
                    return (
                      <div key={lit.pmid} className="pb-2.5 border-b border-slate-800/60 last:border-b-0 last:pb-0">
                        <div className="flex items-center justify-between gap-2 text-[10px] mono-tabular">
                          <span className="text-emerald-400 font-semibold">{lit.gene}</span>
                          {pubmedUrl ? (
                            <a
                              href={pubmedUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-sky-400 hover:underline"
                            >
                              <span>PMID:{lit.pmid}</span>
                              <ExternalLink className="w-2.5 h-2.5" />
                            </a>
                          ) : (
                            <span className="text-slate-500">PMID:{lit.pmid}</span>
                          )}
                        </div>
                        <p className="text-xs text-slate-200 leading-snug mt-1">{lit.title}</p>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {lit.journal} {lit.pub_date ? `· ${lit.pub_date}` : ""}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* ClinicalTrials.gov */}
            <div className="p-3.5 rounded-lg bg-[#07090E] border border-slate-800/80 space-y-2.5">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                  <Pill className="w-3.5 h-3.5 text-emerald-400" />
                  <span>ClinicalTrials.gov Studies</span>
                </div>
                <span className="text-[10px] mono-tabular text-slate-500">{trials.length} NCTs</span>
              </div>

              {trials.length === 0 ? (
                <p className="text-xs text-slate-500 py-2">
                  No matching clinical trials found for the top targets or drugs in this disease context.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {trials.map((tr) => {
                    const trialUrl = getSafeTrialUrl(tr.nct_id);
                    return (
                      <div key={tr.nct_id} className="pb-2.5 border-b border-slate-800/60 last:border-b-0 last:pb-0">
                        <div className="flex items-center justify-between gap-2 text-[10px] mono-tabular">
                          <span className="text-slate-300 font-semibold">{tr.query_gene_or_drug}</span>
                          {trialUrl ? (
                            <a
                              href={trialUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-emerald-400 hover:underline"
                            >
                              <span>{tr.nct_id}</span>
                              <ExternalLink className="w-2.5 h-2.5" />
                            </a>
                          ) : (
                            <span className="text-slate-500">{tr.nct_id}</span>
                          )}
                        </div>
                        <p className="text-xs text-slate-200 leading-snug mt-1">{tr.title}</p>
                        <div className="text-[10px] mono-tabular text-slate-500 mt-0.5">
                          {tr.phase} · {tr.status}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
