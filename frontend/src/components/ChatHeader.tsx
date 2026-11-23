import React from "react";
import { RotateCcw, Dna, HelpCircle } from "lucide-react";

interface ChatHeaderProps {
  onReset: () => void;
  apiBaseUrl?: string;
  onOpenGuide?: () => void;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  onReset,
  onOpenGuide,
}) => {
  return (
    <header className="sticky top-0 z-30 w-full border-b border-slate-800/80 bg-[#07090E]/90 backdrop-blur-md">
      <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 pl-0 lg:pl-80 transition-all min-w-0">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 shrink-0">
            <Dna className="w-4 h-4" />
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <h1 className="text-sm md:text-base font-bold text-slate-100 tracking-tight truncate">
                BioAgent<span className="text-emerald-400">-Lite</span>
              </h1>
              <span className="hidden sm:inline text-[11px] font-mono text-slate-400 truncate">
                Target &amp; Drug Discovery · Critic v2
              </span>
            </div>
            <p className="text-[11px] text-slate-500 hidden sm:block truncate">
              Cancer &amp; General Disease Transcriptomics · Live Open Targets, PubMed &amp; Trials
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {onOpenGuide && (
            <button
              onClick={onOpenGuide}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-800 hover:border-emerald-500/50 bg-slate-900/70 hover:bg-slate-800/80 text-slate-200 hover:text-white text-xs transition"
              title="Plain-English researcher guide and local RTX 5050 setup"
            >
              <HelpCircle className="w-3.5 h-3.5 text-emerald-400" />
              <span className="hidden sm:inline">How it works</span>
            </button>
          )}

          <button
            onClick={onReset}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900/70 hover:bg-slate-800/80 text-slate-300 hover:text-white text-xs transition"
            title="Reset session"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Reset</span>
          </button>
        </div>
      </div>
    </header>
  );
};
