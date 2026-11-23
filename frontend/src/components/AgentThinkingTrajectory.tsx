import React, { useState } from "react";
import {
  Compass,
  Cpu,
  Dna,
  Search,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Wrench,
  ArrowRight,
  Terminal,
  Code2,
} from "lucide-react";

export interface ToolCallItem {
  tool: string;
  input: string;
  output: string;
}

export interface AgentStep {
  id: string;
  agent: string;
  status: string;
  icon?: string;
  tools_selected: string[];
  tool_calls?: ToolCallItem[];
  thought: string;
  decision: string;
  latency_s: number;
  tokens?: number;
}

interface AgentThinkingTrajectoryProps {
  steps: AgentStep[];
  totalLatency?: number;
  defaultExpanded?: boolean;
}

const getAgentIcon = (id: string) => {
  switch (id) {
    case "planner":
      return <Compass className="w-3.5 h-3.5 text-emerald-400" />;
    case "computational_analyst":
      return <Cpu className="w-3.5 h-3.5 text-sky-400" />;
    case "biological_interpreter":
      return <Dna className="w-3.5 h-3.5 text-indigo-400" />;
    case "evidence_retriever":
      return <Search className="w-3.5 h-3.5 text-amber-400" />;
    case "critic":
      return <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />;
    default:
      return <CheckCircle2 className="w-3.5 h-3.5 text-slate-400" />;
  }
};

const getStatusBadge = (status: string) => {
  const s = (status || "").toUpperCase();
  if (s === "PASS" || s === "COMPLETED") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] mono-tabular font-semibold bg-emerald-500/15 text-emerald-400">
        <CheckCircle2 className="w-3 h-3" />
        {s}
      </span>
    );
  }
  if (s === "FAIL") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] mono-tabular font-semibold bg-rose-500/15 text-rose-400">
        <XCircle className="w-3 h-3" />
        {s}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] mono-tabular font-semibold bg-amber-500/15 text-amber-400">
      <AlertTriangle className="w-3 h-3" />
      {s || "INFO"}
    </span>
  );
};

export const AgentThinkingTrajectory: React.FC<AgentThinkingTrajectoryProps> = ({
  steps,
  totalLatency = 0,
  defaultExpanded = false,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(defaultExpanded);
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});

  const toggleToolExpand = (stepId: string) => {
    setExpandedTools((prev) => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  if (!steps || steps.length === 0) return null;

  return (
    <div className="w-full rounded-xl border border-slate-800 bg-[#0D121B]/90 overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between gap-3 text-left hover:bg-slate-900/60 transition-colors"
      >
        <div className="flex items-center gap-2.5 flex-wrap text-xs">
          <span className="font-semibold text-slate-100">Agent Execution Trajectory</span>
          <span className="text-[11px] text-slate-400 mono-tabular flex items-center gap-1">
            <Clock className="w-3 h-3 text-slate-500" />
            {totalLatency}s · {steps.length} agents
          </span>
        </div>

        <div className="flex items-center gap-1 text-xs text-slate-400 shrink-0">
          <span>{isExpanded ? "Hide trace" : "Inspect trace"}</span>
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 pt-3 border-t border-slate-800/80 space-y-3">
          {steps.map((step, idx) => {
            const areToolsExpanded = expandedTools[step.id] ?? false;

            return (
              <div
                key={step.id || idx}
                className="p-3.5 rounded-lg bg-[#07090E] border border-slate-800/80 space-y-2.5"
              >
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    {getAgentIcon(step.id)}
                    <span className="text-xs font-semibold text-slate-100">
                      {idx + 1}. {step.agent}
                    </span>
                    {getStatusBadge(step.status)}
                  </div>

                  <div className="flex items-center gap-2.5 text-[10px] text-slate-400 mono-tabular">
                    {step.tokens ? <span>{step.tokens.toLocaleString()} tok</span> : null}
                    <span>{step.latency_s}s</span>
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">
                  {step.thought}
                </p>

                {step.tool_calls && step.tool_calls.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <div className="flex items-center justify-between text-[10px] mono-tabular">
                      <span className="text-slate-400 flex items-center gap-1">
                        <Wrench className="w-3 h-3 text-sky-400" />
                        Tools ({step.tool_calls.length}): {step.tool_calls.map((t) => t.tool).join(" · ")}
                      </span>
                      <button
                        onClick={() => toggleToolExpand(step.id)}
                        className="text-sky-400 hover:underline"
                      >
                        {areToolsExpanded ? "Hide I/O" : "Show I/O"}
                      </button>
                    </div>

                    {areToolsExpanded && (
                      <div className="space-y-1.5 pt-1">
                        {step.tool_calls.map((tc, tIdx) => (
                          <div
                            key={tIdx}
                            className="p-2 rounded bg-[#0D121B] border border-slate-800 mono-tabular text-[10px] space-y-0.5"
                          >
                            <div className="text-sky-400 font-semibold flex items-center gap-1">
                              <Terminal className="w-3 h-3" />
                              <span>{tc.tool}()</span>
                            </div>
                            <div className="text-slate-400 pl-4">
                              <Code2 className="w-2.5 h-2.5 inline mr-1 text-slate-500" />
                              in: {tc.input}
                            </div>
                            <div className="text-emerald-400 pl-4">out: {tc.output}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {step.decision && (
                  <div className="pt-2 border-t border-slate-800/70 flex items-start gap-1.5 text-[11px] text-slate-300">
                    <ArrowRight className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{step.decision}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
