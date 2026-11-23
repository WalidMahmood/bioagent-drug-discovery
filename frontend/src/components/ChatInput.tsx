import React, { useState, useRef } from "react";
import {
  ArrowUp,
  Paperclip,
  X,
  FileSpreadsheet,
  Database,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Crosshair,
} from "lucide-react";

export interface DatasetPreset {
  id: string;
  name: string;
  description: string;
  genes: string;
  type: string;
  role: string;
}

export const PRESET_DATASETS: DatasetPreset[] = [
  {
    id: "PDAC_Gemcitabine",
    name: "PDAC Gemcitabine",
    description: "Pancreatic Chemoresistance (Live Stats)",
    genes: "2,000 genes",
    type: "Live CSV Engine",
    role: "Live Test",
  },
  {
    id: "GSE202768",
    name: "GSE202768",
    description: "Hs578T TNBC PRRX1 Knockdown",
    genes: "14,009 genes",
    type: "Counts (pydeseq2)",
    role: "Development",
  },
  {
    id: "GSE113650",
    name: "GSE113650",
    description: "TNBC vs Non-TNBC Breast Lines",
    genes: "14,817 genes",
    type: "CuffDiff (q-values)",
    role: "Ext. Validation",
  },
  {
    id: "GSE95304",
    name: "GSE95304",
    description: "shMyc vs shSCR Perturbation",
    genes: "14,387 genes",
    type: "FPKM (§13 Guard)",
    role: "Held-Out",
  },
  {
    id: "GSE336903",
    name: "GSE336903",
    description: "Mus musculus Cell-Line FPKM (Fig. 7)",
    genes: "54,289 features",
    type: "FPKM (§13 Guard)",
    role: "Smoke Test",
  },
];

export const DISEASE_PRESETS: Array<{ value: string; label: string }> = [
  { value: "auto", label: "Auto (from dataset)" },
  { value: "Triple-Negative Breast Cancer", label: "Cancer: Triple-Negative Breast Cancer" },
  { value: "Pancreatic Ductal Adenocarcinoma", label: "Cancer: Pancreatic Cancer (PDAC)" },
  { value: "Non-Small Cell Lung Carcinoma", label: "Cancer: Non-Small Cell Lung Cancer" },
  { value: "Colorectal Carcinoma", label: "Cancer: Colorectal Carcinoma" },
  { value: "Rheumatoid Arthritis", label: "General: Rheumatoid Arthritis (Autoimmune)" },
  { value: "Idiopathic Pulmonary Fibrosis", label: "General: Pulmonary Fibrosis" },
  { value: "Alzheimer Disease", label: "General: Alzheimer Disease" },
  { value: "Type 2 Diabetes Mellitus", label: "General: Type 2 Diabetes" },
  { value: "custom", label: "Custom disease..." },
];

interface ChatInputProps {
  onSendMessage: (
    query: string,
    dataset: string,
    uploadedFile?: any,
    diseaseContext?: string
  ) => void;
  isLoading: boolean;
  selectedDataset: string;
  onSelectDataset: (datasetId: string) => void;
  diseaseContext: string;
  onDiseaseContextChange: (disease: string) => void;
  apiBaseUrl?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  isLoading,
  selectedDataset,
  onSelectDataset,
  diseaseContext,
  onDiseaseContextChange,
  apiBaseUrl = "",
}) => {
  const [inputText, setInputText] = useState<string>("");
  const [customDisease, setCustomDisease] = useState<string>("");
  const [isCustomMode, setIsCustomMode] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [uploadedFile, setUploadedFile] = useState<any | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${apiBaseUrl}/api/upload`, {
        method: "POST",
        body: formData,
      });

      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(payload.detail || `Upload rejected (HTTP ${res.status})`);
      }

      setUploadedFile({
        name: payload.filename || file.name,
        originalName: file.name,
        size: `${(file.size / 1024).toFixed(1)} KB`,
        detectedType: payload.detected_data_type,
        estimatedGenes: payload.estimated_genes,
        guardrailStatus: payload.guardrail_status,
        recommendedStrategy: payload.recommended_strategy,
      });
    } catch (err: any) {
      setUploadedFile(null);
      setUploadError(err?.message || "Upload failed. Check file format (.csv/.tsv) and backend connectivity.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (isLoading || isUploading) return;

    const resolvedDisease = isCustomMode
      ? customDisease.trim() || "auto"
      : diseaseContext;

    const query =
      inputText.trim() ||
      `Analyze differential expression, gene-flipping targets, and MoA-audited drugs for ${
        uploadedFile ? uploadedFile.originalName || uploadedFile.name : selectedDataset
      }`;
    onSendMessage(query, selectedDataset, uploadedFile, resolvedDisease);
    setInputText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto px-4 pb-3 pt-1">
      <div className="mb-2.5">
        <div className="flex items-center justify-between gap-2 flex-wrap mb-1.5">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400 mono-tabular">
            <Database className="w-3.5 h-3.5 text-emerald-400" />
            <span>Dataset &amp; Live CSV Engine</span>
          </div>

          {/* Disease Focus Selector */}
          <div className="flex items-center gap-1.5 text-[11px]">
            <Crosshair className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <label htmlFor="disease-context-select" className="text-slate-400 hidden sm:inline">
              Disease Focus:
            </label>
            <select
              id="disease-context-select"
              value={isCustomMode ? "custom" : diseaseContext}
              onChange={(e) => {
                const val = e.target.value;
                if (val === "custom") {
                  setIsCustomMode(true);
                } else {
                  setIsCustomMode(false);
                  onDiseaseContextChange(val);
                }
              }}
              className="px-2 py-1 rounded-md bg-[#0D121B] border border-slate-800 hover:border-slate-700 text-slate-200 text-[11px] focus:outline-none focus:border-emerald-500/60"
            >
              {DISEASE_PRESETS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {isCustomMode && (
              <input
                type="text"
                value={customDisease}
                onChange={(e) => {
                  setCustomDisease(e.target.value);
                  onDiseaseContextChange(e.target.value || "auto");
                }}
                placeholder="e.g. Glioblastoma or Asthma"
                className="w-36 sm:w-44 px-2 py-1 rounded-md bg-[#0D121B] border border-emerald-500/50 text-slate-100 placeholder-slate-500 text-[11px] focus:outline-none"
              />
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {PRESET_DATASETS.map((d) => {
            const isSelected = selectedDataset === d.id && !uploadedFile;
            return (
              <button
                key={d.id}
                onClick={() => {
                  setUploadedFile(null);
                  setUploadError(null);
                  onSelectDataset(d.id);
                }}
                className={`p-2 rounded-lg text-left transition-colors border ${
                  isSelected
                    ? "bg-emerald-500/10 border-emerald-500/60 text-slate-100"
                    : "bg-[#0D121B]/90 border-slate-800 hover:border-slate-700 text-slate-400 hover:text-slate-200"
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="font-semibold text-[11px] text-slate-100 mono-tabular truncate">{d.name}</span>
                  {isSelected && <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />}
                </div>
                <div className="text-[10px] text-slate-400 truncate mt-0.5">{d.description}</div>
                <div className="text-[9px] text-emerald-400/90 mono-tabular mt-1 flex items-center justify-between gap-1">
                  <span className="truncate">{d.genes}</span>
                  <span className="text-slate-500 shrink-0">{d.role}</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {uploadError && (
        <div className="mb-2.5 px-3 py-2 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span className="truncate">{uploadError}</span>
          </div>
          <button
            onClick={() => setUploadError(null)}
            className="p-0.5 rounded hover:bg-rose-500/20 text-rose-300"
            aria-label="Dismiss upload error"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative rounded-xl border transition-colors bg-[#0D121B]/95 backdrop-blur-md shadow-xl ${
          isDragging
            ? "border-emerald-400 ring-1 ring-emerald-400/40"
            : "border-slate-800 focus-within:border-emerald-500/60"
        }`}
      >
        {uploadedFile && (
          <div className="px-3 py-2.5 border-b border-slate-800 flex items-center justify-between bg-[#07090E]/70">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="flex items-center justify-center w-7 h-7 rounded-md bg-emerald-500/15 text-emerald-400 shrink-0">
                <FileSpreadsheet className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-semibold text-slate-100 truncate">{uploadedFile.originalName || uploadedFile.name}</span>
                  <span className="text-[10px] text-slate-400 mono-tabular">{uploadedFile.size}</span>
                  <span className="text-[10px] mono-tabular text-emerald-400">· {uploadedFile.detectedType}</span>
                </div>
                <div className="text-[10px] text-slate-400 truncate">
                  {Number(uploadedFile.estimatedGenes).toLocaleString()} rows · {uploadedFile.recommendedStrategy}
                </div>
              </div>
            </div>

            <button
              onClick={() => setUploadedFile(null)}
              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
              title="Remove uploaded matrix"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="flex items-end gap-2 p-2.5">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || isUploading}
            className="p-2.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-[#07090E] text-slate-300 hover:text-white transition shrink-0 disabled:opacity-50"
            title="Upload .csv, .tsv, or .txt expression matrix"
          >
            {isUploading ? <Loader2 className="w-4 h-4 animate-spin text-emerald-400" /> : <Paperclip className="w-4 h-4" />}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.tsv,.txt"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFileUpload(e.target.files[0]);
                e.target.value = "";
              }
            }}
            className="hidden"
          />

          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              uploadedFile
                ? `Uploaded ${uploadedFile.originalName || uploadedFile.name}. Run live statistical & Critic analysis...`
                : `Run multi-agent analysis on ${selectedDataset} or ask about differential genes and §13 guardrails...`
            }
            rows={1}
            disabled={isLoading}
            className="w-full max-h-32 py-2 px-1 bg-transparent text-slate-100 placeholder-slate-500 text-sm focus:outline-none resize-none leading-relaxed"
          />

          <button
            onClick={() => handleSubmit()}
            disabled={isLoading || isUploading}
            className={`p-2.5 rounded-lg flex items-center justify-center shrink-0 transition ${
              isLoading || isUploading
                ? "bg-emerald-500/20 text-emerald-400 cursor-wait"
                : "bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold"
            }`}
            title="Run analysis"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowUp className="w-4 h-4 stroke-[2.5]" />}
          </button>
        </div>

        {isDragging && (
          <div className="absolute inset-0 rounded-xl bg-[#07090E]/95 border-2 border-dashed border-emerald-400 flex flex-col items-center justify-center gap-1.5 pointer-events-none z-20">
            <UploadCloud className="w-7 h-7 text-emerald-400" />
            <div className="text-sm font-semibold text-slate-100">Drop expression matrix (.csv, .tsv, .txt)</div>
            <div className="text-xs text-slate-400">Validated for data type (§13) before statistical execution</div>
          </div>
        )}
      </div>
    </div>
  );
};
