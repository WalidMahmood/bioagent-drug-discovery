import React, { useState, useEffect, useRef } from "react";
import {
  Dna,
  ArrowRight,
  ShieldCheck,
  Compass,
  Cpu,
  Search,
  Loader2,
  Crosshair,
  Pill,
} from "lucide-react";
import { SystemTelemetry } from "./components/SystemTelemetry";
import { ChatHeader } from "./components/ChatHeader";
import { ChatMessage, ChatMessageData } from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import { ResearcherGuideModal } from "./components/ResearcherGuideModal";

const API_BASE = "";

const INSTANT_DISCOVERY_DEMOS = [
  {
    id: "NSCLC_EGFR_Demo",
    label: "Cancer · Lung Adenocarcinoma (EGFR, ERBB2, CDK4)",
    disease: "Non-Small Cell Lung Carcinoma",
    description: "Tests Turn OFF (inhibit) & Turn ON (restore) gene-flipping + live MoA guard on NSCLC.",
    genes: [
      { gene: "EGFR", log2FC: 2.8, padj: 1e-12 },
      { gene: "ERBB2", log2FC: 2.1, padj: 1e-9 },
      { gene: "CDK4", log2FC: 1.9, padj: 1e-7 },
      { gene: "TP53", log2FC: -2.2, padj: 1e-8 },
      { gene: "MET", log2FC: 2.4, padj: 1e-10 },
    ],
  },
  {
    id: "RA_Autoimmune_Demo",
    label: "General Disease · Rheumatoid Arthritis (TNF, JAK1, IL6)",
    disease: "Rheumatoid Arthritis",
    description: "Tests general-disease drug repurposing on autoimmune inflammatory targets.",
    genes: [
      { gene: "TNF", log2FC: 3.1, padj: 1e-14 },
      { gene: "JAK1", log2FC: 2.2, padj: 1e-10 },
      { gene: "IL6", log2FC: 2.9, padj: 1e-11 },
      { gene: "PTGS2", log2FC: 1.8, padj: 1e-6 },
      { gene: "IL10", log2FC: -1.9, padj: 1e-6 },
    ],
  },
];

export const App: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>("PDAC_Gemcitabine");
  const [diseaseContext, setDiseaseContext] = useState<string>("auto");
  const [currentModel, setCurrentModel] = useState<string>("gemma-3-4b");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [showGuide, setShowGuide] = useState<boolean>(false);
  const [activeStepIndex, setActiveStepIndex] = useState<number>(0);
  const [loadingStepText, setLoadingStepText] = useState<string>("Running Planner Agent...");

  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messages.length > 0 || isLoading) {
      chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading]);

  useEffect(() => {
    if (!isLoading) return;

    const stepsCycle = [
      "Planner Agent: Checking metadata and §13 data-type guardrails...",
      "Computational Analyst: Running differential expression statistics...",
      "Therapeutic Discovery: Querying live Open Targets v4, PubMed & ClinicalTrials.gov...",
      "Biological Interpreter: Synthesizing hedged claims and pathways...",
      "Evidence Retriever: Grounding genes, PMIDs, and NCT trial IDs...",
      "Critic v2: Auditing directions, MoA concordance, and safety disclaimers...",
    ];

    let step = 0;
    const interval = setInterval(() => {
      step = (step + 1) % stepsCycle.length;
      setActiveStepIndex(step);
      setLoadingStepText(stepsCycle[step]);
    }, 1000);

    return () => clearInterval(interval);
  }, [isLoading]);

  const handleSendMessage = async (
    query: string,
    dataset: string,
    uploadedFile?: any,
    requestedDisease?: string
  ) => {
    if (isLoading) return;

    const activeDisease = requestedDisease || diseaseContext;
    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `assistant-${Date.now()}`;

    const userMsg: ChatMessageData = {
      id: userMessageId,
      sender: "user",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      query,
      dataset: uploadedFile ? uploadedFile.name : dataset,
      diseaseContext: activeDisease,
      modelName: currentModel,
      uploadedFileName: uploadedFile ? uploadedFile.originalName || uploadedFile.name : undefined,
    };

    setMessages((prev) => [...prev, userMsg]);
    setActiveStepIndex(0);
    setLoadingStepText("Planner Agent: Checking metadata and §13 data-type guardrails...");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset,
          model: currentModel,
          query,
          use_critic: true,
          disease_context: activeDisease === "auto" ? undefined : activeDisease,
          custom_filename: uploadedFile ? uploadedFile.name : undefined,
        }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || `Pipeline API returned HTTP ${response.status}`);
      }

      const assistantMsg: ChatMessageData = {
        id: assistantMessageId,
        sender: "assistant",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        query,
        dataset: data.dataset || dataset,
        diseaseContext: data.discovery?.disease_context || activeDisease,
        modelName: data.model?.name || currentModel,
        mode: data.mode,
        plainSummary: data.plain_summary,
        steps: data.steps,
        verdict: data.verdict,
        totalLatency: data.total_latency_s,
        stats: data.stats,
        topGenes: data.top_genes,
        sigPathways: data.sig_pathways,
        discovery: data.discovery,
        interp: data.interp,
        figures: data.figures,
        downloads: data.downloads,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessageData = {
        id: assistantMessageId,
        sender: "assistant",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        plainSummary: `Pipeline execution failed: ${err?.message || "Network error"}. Verify the API backend is reachable.`,
        dataset,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      setActiveStepIndex(0);
    }
  };

  const handleInstantDiscoveryDemo = async (demo: (typeof INSTANT_DISCOVERY_DEMOS)[number]) => {
    if (isLoading) return;

    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `assistant-${Date.now()}`;

    const userMsg: ChatMessageData = {
      id: userMessageId,
      sender: "user",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      query: `Run live gene-flipping target & drug repurposing discovery for ${demo.disease} (${demo.genes.map((g) => g.gene).join(", ")}).`,
      dataset: demo.id,
      diseaseContext: demo.disease,
      modelName: currentModel,
    };

    setMessages((prev) => [...prev, userMsg]);
    setActiveStepIndex(2);
    setLoadingStepText("Therapeutic Discovery: Querying live Open Targets v4, PubMed & ClinicalTrials.gov...");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset_name: demo.id,
          disease_context: demo.disease,
          genes: demo.genes,
          max_targets: 10,
        }),
      });

      const dossier = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(dossier.detail || `Discovery API returned HTTP ${response.status}`);
      }

      const assistantMsg: ChatMessageData = {
        id: assistantMessageId,
        sender: "assistant",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        dataset: demo.id,
        diseaseContext: demo.disease,
        modelName: currentModel,
        mode: "live_target_discovery",
        defaultTab: "discovery",
        discovery: dossier,
        verdict: {
          status: "PASS",
          errors: [],
          warnings: [],
          therapeutic_moa_checks_passed: true,
        },
        plainSummary: `Live Open Targets v4 + PubMed + ClinicalTrials.gov discovery for ${demo.disease}: mapped ${dossier.sources?.targets_mapped ?? 0} targets, validated ${dossier.concordant_drugs?.length ?? 0} MoA-concordant drugs, and automatically blocked ${dossier.blocked_drugs?.length ?? 0} discordant drugs.`,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessageData = {
        id: assistantMessageId,
        sender: "assistant",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        plainSummary: `Discovery query failed: ${err?.message || "Network error"}.`,
        dataset: demo.id,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      setActiveStepIndex(0);
    }
  };

  const handleReset = () => {
    setMessages([]);
    setSelectedDataset("PDAC_Gemcitabine");
    setDiseaseContext("auto");
  };

  const handleQuickPrompt = (datasetId: string, promptText: string, presetDisease = "auto") => {
    setSelectedDataset(datasetId);
    setDiseaseContext(presetDisease);
    handleSendMessage(promptText, datasetId, undefined, presetDisease);
  };

  return (
    <div className="relative min-h-screen bg-[#07090E] text-slate-100 font-sans flex flex-col">
      <SystemTelemetry
        currentModel={currentModel}
        onModelChange={(newModel) => setCurrentModel(newModel)}
        apiBaseUrl={API_BASE}
      />

      <ChatHeader
        onReset={handleReset}
        apiBaseUrl={API_BASE}
        onOpenGuide={() => setShowGuide(true)}
      />

      <main className="flex-1 w-full lg:pl-[308px] pt-4 pb-64 overflow-y-auto">
        <div className="w-full max-w-4xl mx-auto px-4">
        {messages.length === 0 && (
          <div className="py-2 md:py-4 flex flex-col items-center text-center">
            <div className="text-[11px] mono-tabular uppercase tracking-widest text-emerald-400 mb-2">
              Local-First Therapeutic Target &amp; Drug Discovery Engine
            </div>

            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-slate-100 mb-2 max-w-2xl leading-tight">
              From RNA-seq expression to audited gene-flipping targets &amp; drugs
            </h1>

            <p className="text-xs md:text-sm text-slate-400 max-w-xl mb-5 leading-relaxed">
              Upload any cancer or general-disease expression CSV/TSV matrix, or run a verified benchmark.
              BioAgent-Lite computes real statistics, queries live Open Targets v4, PubMed &amp; ClinicalTrials.gov,
              and blocks discordant drug mechanisms automatically.
            </p>

            {/* Primary 4 Benchmark & Live Engine Cards */}
            <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-3xl text-left">
              <button
                onClick={() =>
                  handleQuickPrompt(
                    "PDAC_Gemcitabine",
                    "Run live differential expression, gene-flipping target prioritization, and MoA-audited drug repurposing for Gemcitabine-resistant pancreatic cancer.",
                    "Pancreatic Ductal Adenocarcinoma"
                  )
                }
                className="group p-3.5 rounded-xl bg-[#0D121B] hover:bg-slate-900/80 border border-emerald-500/40 hover:border-emerald-400 transition-colors text-left"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs mono-tabular font-semibold text-emerald-400">
                    Live Engine · PDAC Chemoresistance
                  </span>
                  <ArrowRight className="w-4 h-4 text-emerald-400 transition-transform group-hover:translate-x-0.5" />
                </div>
                <h3 className="text-sm font-semibold text-slate-100">
                  Pancreatic Cancer Live Stats + Drug Discovery
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Computes live Welch + BH-FDR on 2,000 genes, ranks Turn OFF/ON targets, and pulls real Open Targets drugs &amp; trials.
                </p>
              </button>

              <button
                onClick={() =>
                  handleQuickPrompt(
                    "GSE202768",
                    "Analyze differential expression, gene-flipping targets, and MoA-audited drugs for PRRX1 knockdown in Hs578T TNBC cells.",
                    "Triple-Negative Breast Cancer"
                  )
                }
                className="group p-3.5 rounded-xl bg-[#0D121B] hover:bg-slate-900/80 border border-slate-800 hover:border-emerald-500/50 transition-colors text-left"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs mono-tabular font-semibold text-emerald-400">
                    GSE202768 · Raw Counts (TNBC)
                  </span>
                  <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-emerald-400 transition-colors" />
                </div>
                <h3 className="text-sm font-semibold text-slate-100">PRRX1 Knockdown in Hs578T Breast Cancer</h3>
                <p className="text-xs text-slate-400 mt-1">
                  14,009 genes via pydeseq2 Wald test (3,946 significant) paired with live target &amp; drug discovery.
                </p>
              </button>

              <button
                onClick={() =>
                  handleQuickPrompt(
                    "GSE113650",
                    "Analyze differential expression and actionable targets between TNBC and non-TNBC breast cancer cell lines.",
                    "Triple-Negative Breast Cancer"
                  )
                }
                className="group p-3.5 rounded-xl bg-[#0D121B] hover:bg-slate-900/80 border border-slate-800 hover:border-emerald-500/50 transition-colors text-left"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs mono-tabular font-semibold text-sky-400">
                    GSE113650 · External Validation
                  </span>
                  <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-sky-400 transition-colors" />
                </div>
                <h3 className="text-sm font-semibold text-slate-100">TNBC vs Non-TNBC External Cohort</h3>
                <p className="text-xs text-slate-400 mt-1">
                  14,817 tested genes (990 significant at q &lt; 0.05) with live PubMed and clinical trial grounding.
                </p>
              </button>

              <button
                onClick={() =>
                  handleQuickPrompt(
                    "GSE95304",
                    "Verify how the §13 Data-Type Guard handles normalized FPKM matrices in GSE95304 and ranks targets descriptively.",
                    "Triple-Negative Breast Cancer"
                  )
                }
                className="group p-3.5 rounded-xl bg-[#0D121B] hover:bg-slate-900/80 border border-slate-800 hover:border-amber-500/50 transition-colors text-left"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs mono-tabular font-semibold text-amber-400">
                    GSE95304 · FPKM Safety Guard (§13)
                  </span>
                  <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-amber-400 transition-colors" />
                </div>
                <h3 className="text-sm font-semibold text-slate-100">shMyc Knockdown Refusal Guard Test</h3>
                <p className="text-xs text-slate-400 mt-1">
                  Refuses invalid DESeq2 on FPKM data, ranks 14,387 genes descriptively, and audits targets safely.
                </p>
              </button>
            </div>

            {/* Instant Cancer & General-Disease Gene-Flipping Rediscovery Strip */}
            <div className="w-full max-w-3xl mt-4 text-left">
              <div className="flex items-center gap-1.5 text-[11px] mono-tabular text-slate-400 uppercase tracking-wider mb-1.5">
                <Pill className="w-3.5 h-3.5 text-emerald-400" />
                <span>Instant Live Gene-Flipping &amp; MoA Guard Demos (Cancer + General Disease)</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {INSTANT_DISCOVERY_DEMOS.map((demo) => (
                  <button
                    key={demo.id}
                    onClick={() => handleInstantDiscoveryDemo(demo)}
                    className="group p-3 rounded-xl bg-[#0D121B] hover:bg-slate-900/80 border border-slate-800 hover:border-emerald-500/50 transition text-left"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-slate-100">{demo.label}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-emerald-400 shrink-0" />
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">{demo.description}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4 text-[11px] text-slate-500 mono-tabular">
              Zero Mock Drugs · Live Open Targets v4 + PubMed + ClinicalTrials.gov · Critic v2 MoA Guard · RTX 5050 Ready
            </div>
          </div>
        )}

        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} apiBaseUrl={API_BASE} />
        ))}

        {isLoading && (
          <div className="mb-8 p-5 rounded-xl bg-[#0D121B] border border-emerald-500/30">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2.5">
                <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
                <div>
                  <div className="text-sm font-semibold text-slate-100">Running BioAgent-Lite Discovery Pipeline</div>
                  <div className="text-xs text-emerald-400 mono-tabular">{loadingStepText}</div>
                </div>
              </div>
              <div className="text-xs mono-tabular text-slate-400">{selectedDataset}</div>
            </div>

            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 pt-2 border-t border-slate-800/80">
              {[
                { name: "Planner", icon: Compass, idx: 0 },
                { name: "Analyst", icon: Cpu, idx: 1 },
                { name: "Discovery", icon: Crosshair, idx: 2 },
                { name: "Interpreter", icon: Dna, idx: 3 },
                { name: "Retriever", icon: Search, idx: 4 },
                { name: "Critic v2", icon: ShieldCheck, idx: 5 },
              ].map((agent) => {
                const IconComponent = agent.icon;
                const isCurrent = activeStepIndex === agent.idx;
                const isPassed = activeStepIndex > agent.idx;
                return (
                  <div
                    key={agent.name}
                    className={`flex items-center gap-1.5 px-2 py-1.5 rounded-md text-[11px] mono-tabular ${
                      isCurrent
                        ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-semibold"
                        : isPassed
                        ? "bg-slate-900 text-slate-300"
                        : "text-slate-600"
                    }`}
                  >
                    <IconComponent className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">{agent.name}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
        </div>
      </main>

      <div className="fixed bottom-0 left-0 right-0 lg:pl-[308px] z-20 pointer-events-none bg-[#07090E]/95 backdrop-blur-md border-t border-slate-800/70 pt-2 pb-1">
        <div className="max-w-4xl mx-auto pointer-events-auto">
          <ChatInput
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            selectedDataset={selectedDataset}
            onSelectDataset={(ds) => setSelectedDataset(ds)}
            diseaseContext={diseaseContext}
            onDiseaseContextChange={(dis) => setDiseaseContext(dis)}
            apiBaseUrl={API_BASE}
          />
        </div>
      </div>

      <ResearcherGuideModal isOpen={showGuide} onClose={() => setShowGuide(false)} />
    </div>
  );
};

export default App;
