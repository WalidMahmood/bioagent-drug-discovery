import React, { useState, useEffect } from "react";
import {
  Cpu,
  Activity,
  HardDrive,
  ChevronDown,
  Layers,
  ChevronUp,
  CheckCircle2,
  Server,
} from "lucide-react";

export interface SystemInfoData {
  runtime_mode?: string;
  llm_server_online?: boolean;
  gpu: {
    available?: boolean;
    name: string;
    vram_total_gb: number;
    vram_used_gb: number;
    vram_free_gb: number;
    vram_pct: number;
    runtime: string;
  };
  cpu: {
    cores: number;
    threads: number;
    usage_pct: number;
  };
  ram: {
    used_gb: number;
    total_gb: number;
    usage_pct: number;
  };
  model: {
    id: string;
    name: string;
    status?: string;
    tokens_per_sec: number | null;
    precision: string;
    benchmark_accuracy: string;
    recommended: boolean;
    verdict?: string;
  };
  context: {
    window_size: number;
    active_tokens: number;
    session_total_tokens?: number;
    pct_used: number;
  };
  available_models: Array<{
    id: string;
    name: string;
    status?: string;
    recommended: boolean;
    vram: number;
    speed: number | null;
  }>;
}

interface SystemTelemetryProps {
  currentModel: string;
  onModelChange: (modelId: string) => void;
  apiBaseUrl?: string;
}

export const SystemTelemetry: React.FC<SystemTelemetryProps> = ({
  currentModel,
  onModelChange,
  apiBaseUrl = "",
}) => {
  const [data, setData] = useState<SystemInfoData | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;

    const fetchTelemetry = async () => {
      try {
        const res = await fetch(`${apiBaseUrl}/api/system_info?model=${encodeURIComponent(currentModel)}`);
        if (res.ok) {
          const json = await res.json();
          if (isMounted) {
            setData(json);
            setBackendOnline(true);
          }
        } else if (isMounted) {
          setBackendOnline(false);
        }
      } catch {
        if (isMounted) {
          setBackendOnline(false);
        }
      }
    };

    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 5000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [currentModel, apiBaseUrl]);

  const gpuAvailable = Boolean(data?.gpu?.available);
  const vramUsed = data?.gpu?.vram_used_gb ?? 0;
  const vramTotal = data?.gpu?.vram_total_gb ?? 0;
  const vramPct = data?.gpu?.vram_pct ?? 0;
  const cpuPct = data?.cpu?.usage_pct ?? 0;
  const ramUsed = data?.ram?.used_gb ?? 0;
  const ramTotal = data?.ram?.total_gb ?? 0;
  const ramPct = data?.ram?.usage_pct ?? 0;
  const activeTokens = data?.context?.active_tokens ?? 0;
  const windowSize = data?.context?.window_size ?? 8192;
  const contextPct = data?.context?.pct_used ?? 0;

  const availableModels = data?.available_models || [
    { id: "gemma-3-4b", name: "Google Gemma 3 4B IT (Q8_K_XL)", status: "measured", recommended: true, vram: 4.9, speed: 38.5 },
    { id: "medgemma-4b", name: "Google MedGemma 4B IT (Q8_K_XL)", status: "pending_local_gguf_run", recommended: false, vram: 4.9, speed: null },
    { id: "qwen-3-8b", name: "Alibaba Qwen3 8B IT (Q4_K_M)", status: "pending_local_gguf_run", recommended: false, vram: 5.1, speed: null },
  ];

  const activeModelObj = availableModels.find((m) => m.id === currentModel) || availableModels[0];
  const runtimeLabel = !backendOnline
    ? "API Offline"
    : data?.llm_server_online
    ? "Live LLM Connected"
    : "Stats & Trace Replay";

  return (
    <aside
      aria-label="Runtime & Model Configuration"
      className="fixed top-3 left-4 z-40 w-[300px] hidden lg:block select-none text-xs"
    >
      <div className="rounded-xl border border-slate-800 bg-[#0D121B]/95 backdrop-blur-md shadow-xl overflow-hidden">
        <div className="px-3 py-2.5 flex items-center justify-between gap-2 border-b border-slate-800/80">
          <div className="flex items-center gap-2 min-w-0">
            <Server className={`w-3.5 h-3.5 shrink-0 ${backendOnline ? "text-emerald-400" : "text-slate-500"}`} />
            <span className="font-semibold text-slate-100 truncate text-[12px]">
              {runtimeLabel}
            </span>
          </div>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition"
            title={isExpanded ? "Collapse details" : "Expand host telemetry"}
          >
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        <div className="p-3 relative">
          <div className="text-[10px] uppercase mono-tabular tracking-wider text-slate-400 mb-1.5 flex items-center justify-between">
            <span>Model Profile</span>
            <span className="text-emerald-400">
              {activeModelObj?.status === "measured" ? "Measured" : "Pending GGUF"}
            </span>
          </div>

          <div className="relative">
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-[#07090E] border border-slate-800 hover:border-slate-700 text-left transition"
            >
              <span className="text-slate-100 font-medium text-[11px] truncate">
                {activeModelObj?.name || currentModel}
              </span>
              <ChevronDown
                className={`w-3 h-3 text-slate-400 shrink-0 transition-transform ${
                  isDropdownOpen ? "rotate-180" : ""
                }`}
              />
            </button>

            {isDropdownOpen && (
              <div className="absolute top-full left-0 right-0 mt-1 p-1 rounded-lg bg-[#0D121B] border border-slate-700 shadow-2xl z-50 space-y-1">
                {availableModels.map((m) => {
                  const isSelected = m.id === currentModel;
                  return (
                    <button
                      key={m.id}
                      onClick={() => {
                        onModelChange(m.id);
                        setIsDropdownOpen(false);
                      }}
                      className={`w-full flex items-start justify-between p-2 rounded-md text-left transition ${
                        isSelected
                          ? "bg-emerald-500/10 border border-emerald-500/30 text-white"
                          : "hover:bg-slate-800/70 text-slate-300"
                      }`}
                    >
                      <div className="space-y-0.5 min-w-0">
                        <div className="font-semibold text-[11px] truncate">{m.name}</div>
                        <div className="text-[10px] mono-tabular text-slate-400">
                          {m.status === "measured"
                            ? `Measured · ${m.speed ?? "—"} tok/s`
                            : "Pending local GGUF run"}
                        </div>
                      </div>
                      {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="px-3 pb-3 grid grid-cols-2 gap-2 mono-tabular">
          <div className="p-2 rounded-lg bg-[#07090E] border border-slate-800/80">
            <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
              <span className="flex items-center gap-1">
                <HardDrive className="w-3 h-3 text-emerald-400" />
                {gpuAvailable ? "GPU VRAM" : "Host RAM"}
              </span>
              <span className="text-slate-100 font-semibold">
                {backendOnline ? `${gpuAvailable ? vramPct : ramPct}%` : "—"}
              </span>
            </div>
            <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden mb-1">
              <div
                className="h-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${backendOnline ? (gpuAvailable ? vramPct : ramPct) : 0}%` }}
              />
            </div>
            <div className="text-[9px] text-slate-500 truncate">
              {backendOnline
                ? gpuAvailable
                  ? `${vramUsed} / ${vramTotal} GB`
                  : `${ramUsed} / ${ramTotal} GB`
                : "Awaiting backend"}
            </div>
          </div>

          <div className="p-2 rounded-lg bg-[#07090E] border border-slate-800/80">
            <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
              <span className="flex items-center gap-1">
                <Layers className="w-3 h-3 text-sky-400" />
                Last Run
              </span>
              <span className="text-slate-100 font-semibold">{contextPct}%</span>
            </div>
            <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden mb-1">
              <div
                className="h-full bg-sky-400 transition-all duration-300"
                style={{ width: `${contextPct}%` }}
              />
            </div>
            <div className="text-[9px] text-slate-500 truncate">
              {activeTokens.toLocaleString()} / {windowSize.toLocaleString()} tok
            </div>
          </div>
        </div>

        {isExpanded && (
          <div className="px-3 pb-3 pt-2 border-t border-slate-800/80 space-y-1.5 mono-tabular text-[10px]">
            <div className="flex justify-between text-slate-300">
              <span className="flex items-center gap-1 text-slate-400">
                <Cpu className="w-3 h-3" /> Host CPU
              </span>
              <span className="text-slate-100">{backendOnline ? `${cpuPct.toFixed(1)}%` : "—"}</span>
            </div>
            <div className="flex justify-between text-slate-300">
              <span className="flex items-center gap-1 text-slate-400">
                <Activity className="w-3 h-3" /> GPU Device
              </span>
              <span className="text-slate-200 truncate max-w-[160px]">
                {data?.gpu?.name || "Not detected"}
              </span>
            </div>
            {data?.model?.verdict && (
              <div className="pt-1.5 text-[10px] text-slate-400 font-sans leading-relaxed border-t border-slate-800/60">
                {data.model.verdict}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
