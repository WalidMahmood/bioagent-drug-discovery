import React, { useEffect, useState } from "react";
import { X, BookOpen, ShieldCheck, Cpu, Copy, Check } from "lucide-react";

interface ResearcherGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type GuideTab = "overview" | "glossary" | "rtx5050";

export const ResearcherGuideModal: React.FC<ResearcherGuideModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [tab, setTab] = useState<GuideTab>("overview");
  const [copiedCmd, setCopiedCmd] = useState<boolean>(false);

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const rtxCommands = `# 1. Start your local GGUF model on RTX 5050 (8 GB VRAM)
llama-server -m ./models/gemma-3-4b-it-Q8_K_XL.gguf --port 8081 -ngl 99 -c 8192

# 2. Run retrospective cancer + general-disease drug rediscovery benchmark
python3 scripts/run_rtx5050_benchmark.py --rediscovery-only

# 3. Run any custom RNA-seq CSV with your local model + live Open Targets
python3 scripts/run_rtx5050_benchmark.py --csv my_experiment.csv --disease "Triple-Negative Breast Cancer"`;

  const handleCopyCmd = () => {
    navigator.clipboard.writeText(rtxCommands);
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="researcher-guide-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[88vh] flex flex-col rounded-xl bg-[#0D121B] border border-slate-800 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between gap-3">
          <div>
            <h2 id="researcher-guide-title" className="text-base font-bold text-slate-100">
              Researcher Guide &amp; Local Model Setup
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Plain-English guide for wet-lab biologists, clinicians, and local RTX 5050 runs
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white transition"
            aria-label="Close guide"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Bar */}
        <div className="px-5 pt-3 flex items-center gap-1.5 border-b border-slate-800/80 pb-3">
          <button
            onClick={() => setTab("overview")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
              tab === "overview"
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                : "text-slate-400 hover:text-slate-200 border border-transparent"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>How It Works</span>
          </button>

          <button
            onClick={() => setTab("glossary")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
              tab === "glossary"
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                : "text-slate-400 hover:text-slate-200 border border-transparent"
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Plain-English Glossary</span>
          </button>

          <button
            onClick={() => setTab("rtx5050")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
              tab === "rtx5050"
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                : "text-slate-400 hover:text-slate-200 border border-transparent"
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>Plug In Local GPU Models</span>
          </button>
        </div>

        {/* Body */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs text-slate-300 leading-relaxed">
          {tab === "overview" && (
            <div className="space-y-3">
              <p className="text-slate-200">
                BioAgent-Lite turns any raw or normalized RNA-seq dataset (cancer, autoimmune, fibrotic, neurological, or metabolic disease) into a verified <strong className="text-emerald-400">Therapeutic Target &amp; Drug Discovery Dossier</strong> without letting an AI invent genes, drugs, or citations.
              </p>

              <div className="space-y-2">
                {[
                  {
                    step: "1. Choose Disease & Dataset",
                    desc: "Pick a built-in benchmark, run the live PDAC Gemcitabine CSV, or drop your own expression CSV/TSV matrix. Select any cancer or general disease focus.",
                  },
                  {
                    step: "2. §13 Data-Type Guardrail",
                    desc: "Before running statistics, the Planner inspects whether values are raw integer counts or normalized FPKM/TPM. It refuses invalid DESeq2 calls on normalized matrices so p-values are never fabricated.",
                  },
                  {
                    step: "3. Deterministic Statistics",
                    desc: "Computes real log2 fold-change, Welch t-test p-values, and Benjamini-Hochberg adjusted p-values (padj), plus Volcano and pathway plots.",
                  },
                  {
                    step: "4. Live Therapeutic Target & Gene-Flipping Engine",
                    desc: "Queries live Open Targets Platform v4, NCBI PubMed, and ClinicalTrials.gov to score each top gene (0–100), determine whether to Turn OFF (Inhibit) or Turn ON (Restore), and surface approved or clinical drugs.",
                  },
                  {
                    step: "5. Critic v2 MoA & Citation Audit",
                    desc: "Automatically blocks discordant drugs (for example, blocking an inhibitor for a gene that is already downregulated) and rejects any unverified PMID or NCT trial ID.",
                  },
                  {
                    step: "6. Export Ready-to-Use Files",
                    desc: "Download the ranked Target Dossier CSV, full Gene Table CSV, Audit Trace JSON, or formatted PDF summary.",
                  },
                ].map((item) => (
                  <div
                    key={item.step}
                    className="p-3 rounded-lg bg-[#07090E] border border-slate-800/80"
                  >
                    <div className="font-semibold text-slate-100">{item.step}</div>
                    <div className="text-slate-400 mt-0.5">{item.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === "glossary" && (
            <div className="space-y-2.5">
              {[
                {
                  term: "log2FC (Log2 Fold Change)",
                  def: "How strongly a gene's expression changed between disease/treated and control samples. +1.0 means 2x higher; +2.0 means 4x higher; -1.0 means 2x lower.",
                },
                {
                  term: "padj (Adjusted P-Value / BH-FDR)",
                  def: "Statistical confidence after correcting for thousands of simultaneous gene tests. Values below 0.05 indicate reliable differential expression.",
                },
                {
                  term: "Gene Flipping (Turn OFF vs Turn ON)",
                  def: "The core therapeutic hypothesis: if a gene is abnormally elevated (log2FC > 0), turning it OFF (inhibitor, siRNA, CRISPRi) may reverse the disease signature. If a protective gene is lost (log2FC < 0), turning it ON (agonist, rescue) is evaluated.",
                },
                {
                  term: "MoA Concordance Guard (Critic T1)",
                  def: "A deterministic pharmacology safety check. It verifies that every suggested drug's Mechanism of Action matches the gene's flip direction—blocking inhibitors on downregulated genes and agonists on upregulated genes.",
                },
                {
                  term: "§13 FPKM Refusal Guard",
                  def: "Negative-binomial tests (DESeq2) mathematically require raw integer counts. When FPKM/TPM data is detected, BioAgent-Lite refuses inferential p-values and switches cleanly to descriptive log2FC ranking.",
                },
                {
                  term: "Priority Score (0–100)",
                  def: "A transparent, formula-based score summing Transcriptomic Strength (0–30), Open Targets Disease Link (0–25), Clinical Druggability (0–25), and Safety / Low Essentiality (0–20).",
                },
              ].map((g) => (
                <div
                  key={g.term}
                  className="p-3 rounded-lg bg-[#07090E] border border-slate-800/80"
                >
                  <div className="font-semibold text-emerald-400 mono-tabular">{g.term}</div>
                  <div className="text-slate-300 mt-1">{g.def}</div>
                </div>
              ))}
            </div>
          )}

          {tab === "rtx5050" && (
            <div className="space-y-3">
              <p className="text-slate-200">
                BioAgent-Lite runs 100% locally on an <strong className="text-emerald-400">NVIDIA RTX 5050 (8 GB VRAM)</strong> using OpenAI-compatible <span className="mono-tabular text-slate-100">llama-server</span> endpoints—keeping patient or proprietary lab data completely private.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mono-tabular">
                <div className="p-2.5 rounded-lg bg-[#07090E] border border-slate-800/80">
                  <div className="font-semibold text-slate-100">Gemma 3 4B IT</div>
                  <div className="text-[10px] text-emerald-400 mt-0.5">Q8_K_XL · ~4.8 GB VRAM</div>
                  <div className="text-[10px] text-slate-400 mt-1">Fast general baseline</div>
                </div>
                <div className="p-2.5 rounded-lg bg-[#07090E] border border-slate-800/80">
                  <div className="font-semibold text-slate-100">MedGemma 4B IT</div>
                  <div className="text-[10px] text-emerald-400 mt-0.5">Q8_K_XL · ~4.8 GB VRAM</div>
                  <div className="text-[10px] text-slate-400 mt-1">Biomedical specialist</div>
                </div>
                <div className="p-2.5 rounded-lg bg-[#07090E] border border-slate-800/80">
                  <div className="font-semibold text-slate-100">Qwen3 8B IT</div>
                  <div className="text-[10px] text-amber-400 mt-0.5">Q4_K_M · ~5.6 GB VRAM</div>
                  <div className="text-[10px] text-slate-400 mt-1">Deep reasoning (8K ctx)</div>
                </div>
              </div>

              <div className="rounded-lg bg-[#07090E] border border-slate-800 overflow-hidden">
                <div className="px-3 py-2 border-b border-slate-800 flex items-center justify-between">
                  <span className="text-[11px] mono-tabular text-slate-400">Terminal Commands</span>
                  <button
                    onClick={handleCopyCmd}
                    className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-white transition"
                  >
                    {copiedCmd ? (
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
                </div>
                <pre className="p-3 text-[11px] mono-tabular text-slate-200 overflow-x-auto leading-relaxed">
                  {rtxCommands}
                </pre>
              </div>

              <p className="text-[11px] text-slate-400">
                Full setup notes, model comparison workflow, and thesis remediation changelog are documented in{" "}
                <span className="mono-tabular text-slate-200">CHANGES_AND_REMEDIATION_SUMMARY.md</span>.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
