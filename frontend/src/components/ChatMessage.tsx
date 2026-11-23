import React, { useState } from "react";
import {
  FileText,
  Download,
  Copy,
  Check,
  Dna,
  User,
  TrendingUp,
  TrendingDown,
  Layers,
  ZoomIn,
  BarChart3,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  XCircle,
  ShieldCheck,
  Crosshair,
  FileSpreadsheet,
  ArrowRight,
} from "lucide-react";
import { AgentThinkingTrajectory, AgentStep } from "./AgentThinkingTrajectory";
import { ImageModal } from "./ImageModal";
import { TherapeuticDossier } from "./TherapeuticDossier";
import { DiscoveryDossier } from "../lib/discoveryAudit";

export interface CriticVerdictData {
  status: string;
  errors?: string[];
  warnings?: string[];
  corrections?: string[];
  statistical_checks_passed?: boolean;
  biological_grounding_passed?: boolean;
  safety_guardrails_passed?: boolean;
  therapeutic_moa_checks_passed?: boolean;
}

export interface ChatMessageData {
  id: string;
  sender: "user" | "assistant";
  timestamp: string;
  query?: string;
  dataset?: string;
  diseaseContext?: string;
  modelName?: string;
  mode?: string;
  uploadedFileName?: string;
  plainSummary?: string;
  steps?: AgentStep[];
  verdict?: CriticVerdictData;
  totalLatency?: number;
  defaultTab?: "overview" | "discovery" | "audit";
  stats?: {
    genes_tested: number;
    significant_genes: number;
    up_regulated: number;
    down_regulated: number;
    padj_threshold: number | null;
    inferential?: boolean;
    contrast: string;
    data_type?: string;
  };
  topGenes?: Array<{
    gene: string;
    log2FC: number;
    padj: number | null;
    direction: "up" | "down";
  }>;
  sigPathways?: Array<{
    source: string;
    term: string;
    adjP: number;
    overlap: string;
  }>;
  discovery?: DiscoveryDossier;
  interp?: {
    observations?: string[];
    claims?: Array<{
      statement: string;
      type?: string;
      genes?: string[];
      pathways?: string[];
      hedged?: boolean;
      audit_verdict?: string;
    }>;
    limitations?: string[];
    disclaimer?: string;
  };
  figures?: {
    volcano?: string;
    pathways?: string;
  };
  downloads?: {
    analysis_pdf?: string;
    pdf_report?: string;
    gene_table_csv?: string;
    target_dossier_csv?: string;
    trace_json?: string;
  };
}

interface ChatMessageProps {
  message: ChatMessageData;
  apiBaseUrl?: string;
}

type ResultTab = "overview" | "discovery" | "audit";

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  apiBaseUrl = "",
}) => {
  const [copied, setCopied] = useState<boolean>(false);
  const [modalImage, setModalImage] = useState<{ url: string; title: string } | null>(null);
  const [activeTab, setActiveTab] = useState<ResultTab>(
    message.defaultTab || (message.discovery && !message.stats ? "discovery" : "overview")
  );

  const isUser = message.sender === "user";
  const criticStep = message.steps?.find(
    (s) => s.id === "critic" || s.agent?.toLowerCase().includes("critic")
  );

  const verdictStatus = (
    message.verdict?.status ||
    criticStep?.status ||
    (message.discovery ? "PASS" : "UNAUDITED")
  ).toUpperCase();
  const verdictErrors = message.verdict?.errors || [];
  const verdictWarnings = message.verdict?.warnings || [];
  const hasFallbackStep = Boolean(message.steps?.some((s) => s.status === "FALLBACK"));

  const renderVerdictBadge = () => {
    if (verdictStatus === "PASS" && !hasFallbackStep) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs mono-tabular font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <CheckCircle2 className="w-3.5 h-3.5" />
          VERDICT: PASS ({verdictErrors.length} errors)
        </span>
      );
    }
    if (verdictStatus === "FAIL") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs mono-tabular font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
          <XCircle className="w-3.5 h-3.5" />
          VERDICT: FAIL ({verdictErrors.length} errors)
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs mono-tabular font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
        <AlertTriangle className="w-3.5 h-3.5" />
        VERDICT: {hasFallbackStep ? "FALLBACK" : verdictStatus} ({verdictErrors.length} errors)
      </span>
    );
  };

  const handleCopy = () => {
    if (message.plainSummary) {
      navigator.clipboard.writeText(message.plainSummary);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isUser) {
    return (
      <div className="flex justify-end mb-6">
        <div className="flex items-start gap-3 max-w-2xl">
          <div className="space-y-1 text-right">
            <div className="inline-block px-4 py-3 rounded-xl bg-[#0D121B] border border-slate-800 text-slate-100 text-sm leading-relaxed text-left">
              <p>{message.query}</p>
              <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-end gap-2 flex-wrap text-[11px] mono-tabular text-slate-400">
                {message.dataset && <span>{message.dataset}</span>}
                {message.diseaseContext && message.diseaseContext !== "auto" && (
                  <span>· {message.diseaseContext}</span>
                )}
                {message.uploadedFileName && <span>· {message.uploadedFileName}</span>}
                {message.modelName && <span>· {message.modelName}</span>}
              </div>
            </div>
            <div className="text-[10px] text-slate-500 mono-tabular pr-1">{message.timestamp}</div>
          </div>

          <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 shrink-0 mt-1">
            <User className="w-3.5 h-3.5" />
          </div>
        </div>
      </div>
    );
  }

  const hasStatsOrClaims = Boolean(message.stats || message.interp || message.figures);
  const hasDiscovery = Boolean(message.discovery);

  const pdfHref = `${apiBaseUrl}${
    message.downloads?.analysis_pdf ||
    message.downloads?.pdf_report ||
    `/api/report/analysis_pdf?dataset=${encodeURIComponent(message.dataset || "GSE202768")}&model=${encodeURIComponent(message.modelName || "gemma-3-4b")}`
  }`;
  const csvHref = `${apiBaseUrl}${
    message.downloads?.gene_table_csv || `/api/genes/${encodeURIComponent(message.dataset || "GSE202768")}`
  }`;
  const targetDossierCsvHref = message.downloads?.target_dossier_csv
    ? `${apiBaseUrl}${message.downloads.target_dossier_csv}`
    : undefined;
  const traceHref = `${apiBaseUrl}${
    message.downloads?.trace_json || `/api/trace/${encodeURIComponent(message.dataset || "GSE202768")}`
  }`;

  const modeLabel =
    message.mode === "live_statistical_engine"
      ? "Live Statistical & Discovery Engine"
      : message.mode === "live_target_discovery"
      ? "Live Gene-Flipping Discovery"
      : "Verified Trace + Live Discovery";

  const topTarget = message.discovery?.targets?.[0];
  const concordantCount = message.discovery?.concordant_drugs?.length || 0;
  const blockedCount = message.discovery?.blocked_drugs?.length || 0;

  return (
    <div className="flex items-start gap-3 mb-8 w-full">
      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 shrink-0 mt-1">
        <Dna className="w-4 h-4" />
      </div>

      <div className="flex-1 min-w-0 space-y-3.5">
        {message.steps && message.steps.length > 0 && (
          <AgentThinkingTrajectory
            steps={message.steps}
            totalLatency={message.totalLatency}
            defaultExpanded={false}
          />
        )}

        <div className="p-5 md:p-6 rounded-xl bg-[#0D121B] border border-slate-800 space-y-5">
          {/* Card Header */}
          <div className="flex items-center justify-between gap-2 pb-3 border-b border-slate-800/80 flex-wrap">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h2 className="text-xs mono-tabular font-semibold tracking-wider uppercase text-emerald-400">
                {message.dataset || "Analysis Dossier"}
              </h2>
              <span className="text-[11px] mono-tabular text-slate-500">· {modeLabel}</span>
            </div>

            <div className="flex items-center gap-2">
              {renderVerdictBadge()}
              {message.plainSummary && (
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>

          {/* Top-Level Result Tabs */}
          {hasStatsOrClaims && hasDiscovery && (
            <div
              role="tablist"
              aria-label="Analysis views"
              className="flex items-center gap-1.5 p-1 rounded-lg bg-[#07090E] border border-slate-800/80 overflow-x-auto"
            >
              <button
                role="tab"
                aria-selected={activeTab === "overview"}
                onClick={() => setActiveTab("overview")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition whitespace-nowrap ${
                  activeTab === "overview"
                    ? "bg-slate-800 text-slate-100 border border-slate-700"
                    : "text-slate-400 hover:text-slate-200 border border-transparent"
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5 text-sky-400" />
                <span>Overview &amp; Plots</span>
              </button>

              <button
                role="tab"
                aria-selected={activeTab === "discovery"}
                onClick={() => setActiveTab("discovery")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition whitespace-nowrap ${
                  activeTab === "discovery"
                    ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                    : "text-slate-400 hover:text-slate-200 border border-transparent"
                }`}
              >
                <Crosshair className="w-3.5 h-3.5 text-emerald-400" />
                <span>
                  Targets &amp; Drugs ({message.discovery?.targets?.length || 0} targets · {concordantCount} drugs)
                </span>
              </button>

              <button
                role="tab"
                aria-selected={activeTab === "audit"}
                onClick={() => setActiveTab("audit")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition whitespace-nowrap ${
                  activeTab === "audit"
                    ? "bg-slate-800 text-slate-100 border border-slate-700"
                    : "text-slate-400 hover:text-slate-200 border border-transparent"
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span>Critic Audit &amp; Claims</span>
              </button>
            </div>
          )}

          {/* TAB: OVERVIEW & PLOTS */}
          {activeTab === "overview" && (
            <div className="space-y-5">
              {message.plainSummary && (
                <p className="text-sm text-slate-200 leading-relaxed">{message.plainSummary}</p>
              )}

              {/* Quick Callout to Live Drug Discovery */}
              {hasDiscovery && topTarget && (
                <div className="p-3.5 rounded-lg bg-[#07090E] border border-emerald-500/30 flex items-center justify-between gap-3 flex-wrap">
                  <div className="space-y-0.5 min-w-0">
                    <div className="text-[11px] mono-tabular uppercase tracking-wider text-emerald-400 font-semibold">
                      Top Actionable Target · {message.discovery?.disease_context}
                    </div>
                    <div className="text-xs text-slate-200 leading-relaxed">
                      <span className="font-bold mono-tabular text-slate-100">{topTarget.gene}</span> (
                      {topTarget.recommended_flip}, priority{" "}
                      <span className="mono-tabular font-semibold text-emerald-400">
                        {topTarget.priority_score.toFixed(1)}/100
                      </span>
                      ) · {concordantCount} MoA-validated drug{concordantCount === 1 ? "" : "s"}
                      {blockedCount > 0 ? ` · ${blockedCount} discordant blocked` : ""}
                    </div>
                  </div>
                  <button
                    onClick={() => setActiveTab("discovery")}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 text-xs font-medium transition shrink-0"
                  >
                    <span>Open Target &amp; Drug Dossier</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Computational Metrics Strip */}
              {message.stats && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mono-tabular">
                  <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800/80">
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider">Features Tested</div>
                    <div className="text-lg font-bold text-slate-100 mt-0.5">
                      {message.stats.genes_tested?.toLocaleString() ?? "—"}
                    </div>
                    <div className="text-[10px] text-slate-500 truncate mt-0.5">{message.stats.data_type || "RNA-seq"}</div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800/80">
                    <div className="text-[10px] text-emerald-400 uppercase tracking-wider">Passed Threshold</div>
                    <div className="text-lg font-bold text-emerald-400 mt-0.5">
                      {message.stats.significant_genes?.toLocaleString() ?? "—"}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {message.stats.inferential === false || message.stats.padj_threshold === null
                        ? "|log2FC| >= 1.0 (Descriptive)"
                        : `padj < ${message.stats.padj_threshold}`}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800/80">
                    <div className="text-[10px] text-emerald-400 uppercase tracking-wider flex items-center gap-1">
                      <TrendingUp className="w-3 h-3" /> Upregulated
                    </div>
                    <div className="text-lg font-bold text-emerald-400 mt-0.5">
                      {message.stats.up_regulated?.toLocaleString() ?? "—"}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">log2FC &gt; 0 · Turn OFF</div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800/80">
                    <div className="text-[10px] text-rose-400 uppercase tracking-wider flex items-center gap-1">
                      <TrendingDown className="w-3 h-3" /> Downregulated
                    </div>
                    <div className="text-lg font-bold text-rose-400 mt-0.5">
                      {message.stats.down_regulated?.toLocaleString() ?? "—"}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">log2FC &lt; 0 · Turn ON</div>
                  </div>
                </div>
              )}

              {/* Top Genes */}
              {message.topGenes && message.topGenes.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-slate-800/80">
                  <div className="text-xs font-semibold text-slate-300">Top Differential Features</div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 mono-tabular">
                    {message.topGenes.slice(0, 10).map((g, idx) => {
                      const isUp = g.direction === "up" || (typeof g.log2FC === "number" && g.log2FC > 0);
                      const formattedFC =
                        typeof g.log2FC === "number" ? `${isUp ? "+" : ""}${g.log2FC.toFixed(2)}` : "—";
                      const formattedPadj =
                        typeof g.padj === "number"
                          ? g.padj < 1e-4
                            ? g.padj.toExponential(1)
                            : g.padj.toFixed(4)
                          : "Descriptive";

                      return (
                        <div
                          key={idx}
                          className="p-2.5 rounded-lg bg-[#07090E] border border-slate-800/80"
                        >
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-semibold text-slate-100 text-xs truncate">{g.gene}</span>
                            <span
                              className={`text-[10px] font-semibold ${
                                isUp ? "text-emerald-400" : "text-rose-400"
                              }`}
                            >
                              {formattedFC}
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-500 mt-1 truncate">padj: {formattedPadj}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Measured Visualizations */}
              {(message.figures?.volcano || message.figures?.pathways) && (
                <div className="space-y-2.5 pt-2 border-t border-slate-800/80">
                  <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <BarChart3 className="w-3.5 h-3.5 text-sky-400" />
                    <span>Computed Figures (Click to zoom)</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {message.figures.volcano && (
                      <div
                        onClick={() =>
                          setModalImage({
                            url: `${apiBaseUrl}${message.figures?.volcano}`,
                            title: `Differential Distribution (${message.dataset || "Dataset"})`,
                          })
                        }
                        className="group cursor-pointer rounded-lg bg-[#07090E] border border-slate-800 hover:border-emerald-500/50 overflow-hidden transition"
                      >
                        <div className="px-3 py-2 border-b border-slate-800/80 flex items-center justify-between text-[11px] mono-tabular text-slate-300">
                          <span className="truncate">Volcano / Distribution · {message.dataset}</span>
                          <ZoomIn className="w-3.5 h-3.5 text-slate-500 group-hover:text-emerald-400" />
                        </div>
                        <div className="h-48 w-full flex items-center justify-center p-2">
                          <img
                            src={`${apiBaseUrl}${message.figures.volcano}`}
                            alt={`Volcano plot for ${message.dataset}`}
                            className="max-h-full w-auto object-contain"
                            loading="lazy"
                          />
                        </div>
                      </div>
                    )}

                    {message.figures.pathways && (
                      <div
                        onClick={() =>
                          setModalImage({
                            url: `${apiBaseUrl}${message.figures?.pathways}`,
                            title:
                              message.sigPathways && message.sigPathways.length > 0
                                ? `Pathway Enrichment (${message.dataset || "Dataset"})`
                                : `Top Differential Features (${message.dataset || "Dataset"})`,
                          })
                        }
                        className="group cursor-pointer rounded-lg bg-[#07090E] border border-slate-800 hover:border-emerald-500/50 overflow-hidden transition"
                      >
                        <div className="px-3 py-2 border-b border-slate-800/80 flex items-center justify-between text-[11px] mono-tabular text-slate-300">
                          <span className="truncate">
                            {message.sigPathways && message.sigPathways.length > 0
                              ? "Pathway Enrichment"
                              : "Top Differential Features"}
                          </span>
                          <ZoomIn className="w-3.5 h-3.5 text-slate-500 group-hover:text-emerald-400" />
                        </div>
                        <div className="h-48 w-full flex items-center justify-center p-2">
                          <img
                            src={`${apiBaseUrl}${message.figures.pathways}`}
                            alt={`Secondary plot for ${message.dataset}`}
                            className="max-h-full w-auto object-contain"
                            loading="lazy"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB: THERAPEUTIC TARGETS, GENE FLIPPING & DRUGS */}
          {activeTab === "discovery" && message.discovery && (
            <TherapeuticDossier
              discovery={message.discovery}
              targetDossierCsvHref={targetDossierCsvHref}
            />
          )}

          {/* TAB: CRITIC AUDIT & CLAIMS */}
          {activeTab === "audit" && (
            <div className="space-y-4">
              {(message.verdict || criticStep) && (
                <div className="p-4 rounded-lg bg-[#07090E] border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between flex-wrap gap-2 pb-2.5 border-b border-slate-800/80">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" />
                      <div>
                        <h3 className="text-xs font-semibold text-slate-100 mono-tabular uppercase tracking-wide">
                          Critic v2 Verification Audit
                        </h3>
                        <p className="text-[10px] text-slate-500">
                          Direction concordance · §13 FPKM guard · T1 MoA concordance · T2 PMID/NCT verification
                        </p>
                      </div>
                    </div>
                    {renderVerdictBadge()}
                  </div>

                  {criticStep?.thought && (
                    <p className="text-xs text-slate-300 leading-relaxed">{criticStep.thought}</p>
                  )}

                  {verdictErrors.length > 0 && (
                    <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 space-y-1">
                      <div className="font-semibold mono-tabular text-[11px]">Errors Flagged:</div>
                      {verdictErrors.map((e, i) => (
                        <div key={i}>• {e}</div>
                      ))}
                    </div>
                  )}

                  {verdictWarnings.length > 0 && (
                    <div className="p-2.5 rounded bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 space-y-1">
                      <div className="font-semibold mono-tabular text-[11px]">Warnings:</div>
                      {verdictWarnings.map((w, i) => (
                        <div key={i}>• {w}</div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {message.interp?.claims && message.interp.claims.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300">Audited Biological Claims</div>
                  <div className="space-y-2">
                    {message.interp.claims.map((claim, cIdx) => {
                      const isHypothesis = claim.type === "hypothesis";
                      return (
                        <div
                          key={cIdx}
                          className="p-3.5 rounded-lg bg-[#07090E] border border-slate-800/80 space-y-2 text-xs"
                        >
                          <div className="flex items-center justify-between gap-2 text-[10px] mono-tabular text-slate-400">
                            <span>
                              Claim #{cIdx + 1} · {isHypothesis ? "Hypothesis" : "Supported"}
                            </span>
                            {claim.audit_verdict && (
                              <span className="text-emerald-400">{claim.audit_verdict}</span>
                            )}
                          </div>
                          <p className="text-slate-200 leading-relaxed text-xs sm:text-sm">
                            {claim.statement}
                          </p>
                          {claim.genes && claim.genes.length > 0 && (
                            <div className="text-[10px] mono-tabular text-slate-400 pt-1 border-t border-slate-800/60">
                              Genes: {claim.genes.join(" · ")}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {message.interp?.limitations && message.interp.limitations.length > 0 && (
                <div className="space-y-1 p-3 rounded-lg bg-[#07090E] border border-slate-800/80 text-[11px] text-slate-400">
                  <div className="font-semibold text-slate-300 flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                    <span>Study Limitations</span>
                  </div>
                  <ul className="space-y-1 list-disc pl-5">
                    {message.interp.limitations.map((lim, lIdx) => (
                      <li key={lIdx}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Non-clinical Disclaimer */}
          <div className="text-[10px] text-slate-500 mono-tabular">
            {message.interp?.disclaimer ||
              "RESEARCH USE ONLY: BioAgent-Lite outputs are for exploratory computational biology and wet-lab hypothesis prioritization, not clinical prescribing."}
          </div>

          {/* Real Downloads Bar */}
          {message.dataset && message.mode !== "live_target_discovery" && (
            <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between flex-wrap gap-2 text-xs">
              <div className="flex items-center gap-2 flex-wrap">
                <a
                  href={pdfHref}
                  download={`BioAgent_Analysis_Report_${message.dataset}.pdf`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Report (PDF)</span>
                </a>

                {targetDossierCsvHref && (
                  <a
                    href={targetDossierCsvHref}
                    download={`${message.dataset}_target_dossier.csv`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#07090E] hover:bg-slate-800 border border-emerald-500/40 text-emerald-300 transition"
                  >
                    <FileSpreadsheet className="w-3.5 h-3.5" />
                    <span>Target Dossier (CSV)</span>
                  </a>
                )}

                <a
                  href={csvHref}
                  download={`${message.dataset}_genes.csv`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#07090E] hover:bg-slate-800 border border-slate-800 text-slate-200 transition"
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Gene Table (CSV)</span>
                </a>

                <a
                  href={traceHref}
                  download={`${message.dataset}_trace.json`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#07090E] hover:bg-slate-800 border border-slate-800 text-slate-200 transition"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Execution Trace (JSON)</span>
                </a>
              </div>
            </div>
          )}
        </div>
      </div>

      {modalImage && (
        <ImageModal
          isOpen={true}
          onClose={() => setModalImage(null)}
          imageUrl={modalImage.url}
          title={modalImage.title}
        />
      )}
    </div>
  );
};
