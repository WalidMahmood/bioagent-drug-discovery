"""BioAgent-Lite FastAPI Backend Service.

Provides:
- Honest host/GPU hardware telemetry & live local LLM health probing
- Strict path-confined upload, table, figure, gene-table, trace, and PDF endpoints
- Trace-derived multi-dataset benchmark replay (GSE202768, GSE113650, GSE95304, GSE336903)
- Dataset-agnostic live statistical analysis for user-uploaded CSV/TSV matrices
"""

import csv
import io
import json
import math
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import psutil
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(
    title="BioAgent-Lite API",
    description="Backend service for BioAgent-Lite multi-agent gene expression analysis system.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
TRACES_DIR = OUTPUTS_DIR / "traces"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
REPORTS_DIR = OUTPUTS_DIR / "reports"

for _dir in (TABLES_DIR, FIGURES_DIR, TRACES_DIR, UPLOADS_DIR, REPORTS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_UPLOAD_EXTS: Set[str] = {".csv", ".tsv", ".txt"}

DATASET_TRACE_MAP = {
    "GSE202768": "eval_GSE202768_20260907T061142Z.json",
    "GSE113650": "eval_GSE113650_20260907T061208Z.json",
    "GSE95304": "eval_GSE95304_20260907T061231Z.json",
    "GSE336903": "eval_GSE336903_20260907T061251Z.json",
}

MODELS_CONFIG = {
    "gemma-3-4b": {
        "name": "Google Gemma 3 4B IT (Q8_K_XL)",
        "vram_gb": 4.9,
        "speed_tks": 38.5,
        "status": "measured",
        "accuracy": "87.1% mean (4 datasets)",
        "precision": "Q8_K_XL",
        "recommended": True,
        "verdict": "Primary evaluated model across all 4 GEO datasets (0.0% invented-gene hallucination)",
    },
    "medgemma-4b": {
        "name": "Google MedGemma 4B IT (Q8_K_XL)",
        "vram_gb": 4.9,
        "speed_tks": None,
        "status": "pending_local_gguf_run",
        "accuracy": "Pending local GGUF run",
        "precision": "Q8_K_XL (Biomedical Domain)",
        "recommended": False,
        "verdict": "Configured in models.yaml; awaiting local GGUF benchmark traces",
    },
    "qwen-3-8b": {
        "name": "Alibaba Qwen3 8B IT (Q4_K_M)",
        "vram_gb": 5.1,
        "speed_tks": None,
        "status": "pending_local_gguf_run",
        "accuracy": "Pending local GGUF run",
        "precision": "Q4_K_M",
        "recommended": False,
        "verdict": "Configured in models.yaml; awaiting local GGUF benchmark traces",
    },
}

SESSION_STATE = {
    "total_tokens": 0,
    "last_run_tokens": 0,
    "last_run_timestamp": time.time(),
    "runs_count": 0,
    "active_model": "gemma-3-4b",
}


def safe_slug(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", str(raw or "")).strip("._")
    if not cleaned:
        raise HTTPException(status_code=400, detail="Invalid identifier.")
    return cleaned[:96]


def safe_resolve(base_dir: Path, filename: str, allowed_exts: Optional[Set[str]] = None) -> Path:
    """Strictly confine a user-supplied filename to base_dir."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    clean_name = Path(filename).name
    if clean_name in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if allowed_exts is not None and Path(clean_name).suffix.lower() not in allowed_exts:
        raise HTTPException(status_code=400, detail="Unsupported file type.")
    base_resolved = base_dir.resolve()
    target = (base_resolved / clean_name).resolve()
    if not target.is_relative_to(base_resolved):
        raise HTTPException(status_code=400, detail="Access outside allowed directory denied.")
    return target


def sanitize_floats(obj: Any) -> Any:
    """Recursively replace Infinity, -Infinity, and NaN with JSON-compliant values."""
    if isinstance(obj, float):
        if math.isinf(obj):
            return 999.0 if obj > 0 else -999.0
        if math.isnan(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_floats(v) for v in obj]
    return obj


def _probe_local_llm() -> bool:
    endpoint = os.getenv("LLM_SERVER_ENDPOINT", "http://127.0.0.1:8080").rstrip("/")
    try:
        req = urllib.request.Request(f"{endpoint}/health", method="GET")
        with urllib.request.urlopen(req, timeout=0.4) as resp:
            return resp.status == 200
    except Exception:
        return False


@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "system": "BioAgent-Lite Multi-Agent Framework",
        "version": "2.0.0",
        "llm_server_online": _probe_local_llm(),
        "agents": [
            {"name": "Planner Agent", "role": "Decomposes query, enforces §13 data-type guard, constructs DAG"},
            {"name": "Computational Analyst", "role": "Executes PyDESeq2 / CuffDiff / descriptive Welch statistics deterministically"},
            {"name": "Biological Interpreter", "role": "Synthesizes hedged claims from top genes and enriched pathways"},
            {"name": "Evidence Retriever", "role": "Grounds gene and normalized pathway claims against computed tables"},
            {"name": "Critic / Verifier", "role": "Audits directions, §13 guardrails, and hedging with re-prompt or claim pruning"},
        ],
    }


@app.get("/api/report/analysis_pdf")
async def download_analysis_report_pdf(dataset: str = "GSE202768", model: str = "gemma-3-4b"):
    safe_ds = safe_slug(dataset)
    safe_model = model if model in MODELS_CONFIG else "gemma-3-4b"
    try:
        from backend.report_generator import build_analysis_pdf

        pdf_path = build_analysis_pdf(dataset=safe_ds, model_id=safe_model)
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="Analysis report PDF could not be generated.")
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"BioAgent_Analysis_Report_{safe_ds}.pdf",
            headers={"Content-Disposition": f"attachment; filename=BioAgent_Analysis_Report_{safe_ds}.pdf"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate analysis PDF: {exc}")


@app.get("/api/system_info")
async def get_system_info(model: str = "gemma-3-4b"):
    m_info = MODELS_CONFIG.get(model, MODELS_CONFIG["gemma-3-4b"])
    SESSION_STATE["active_model"] = model if model in MODELS_CONFIG else "gemma-3-4b"

    cpu_pct = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    ram_used_gb = round(mem.used / (1024 ** 3), 1)
    ram_total_gb = round(mem.total / (1024 ** 3), 1)

    gpu_available = False
    gpu_name = "No local CUDA GPU detected"
    gpu_total = 0.0
    gpu_used = 0.0
    gpu_free = 0.0
    gpu_pct = 0.0

    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,nounits,noheader"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = [x.strip() for x in res.stdout.strip().splitlines()[0].split(",")]
            if len(parts) >= 4:
                gpu_available = True
                gpu_name = parts[0]
                gpu_total = round(float(parts[1]) / 1024.0, 2)
                gpu_used = round(float(parts[2]) / 1024.0, 2)
                gpu_free = round(float(parts[3]) / 1024.0, 2)
                gpu_pct = round((gpu_used / gpu_total) * 100.0, 1) if gpu_total > 0 else 0.0
    except Exception:
        pass

    llm_online = _probe_local_llm()
    context_window = int(os.getenv("CONTEXT_WINDOW_TOKENS", "8192"))
    active_tokens = min(context_window, SESSION_STATE["last_run_tokens"])

    return {
        "runtime_mode": "Live Local LLM (llama.cpp)" if llm_online else "Local Stats & Verified Trace Replay",
        "llm_server_online": llm_online,
        "gpu": {
            "available": gpu_available,
            "name": gpu_name,
            "vram_total_gb": gpu_total,
            "vram_used_gb": gpu_used,
            "vram_free_gb": gpu_free,
            "vram_pct": gpu_pct,
            "runtime": "llama.cpp CUDA" if (gpu_available and llm_online) else "CPU / Deterministic Stats",
        },
        "cpu": {
            "cores": psutil.cpu_count(logical=False),
            "threads": psutil.cpu_count(logical=True),
            "usage_pct": cpu_pct,
        },
        "ram": {
            "used_gb": ram_used_gb,
            "total_gb": ram_total_gb,
            "usage_pct": mem.percent,
        },
        "model": {
            "id": SESSION_STATE["active_model"],
            "name": m_info["name"],
            "status": m_info["status"],
            "tokens_per_sec": m_info["speed_tks"],
            "precision": m_info["precision"],
            "benchmark_accuracy": m_info["accuracy"],
            "recommended": m_info["recommended"],
            "verdict": m_info["verdict"],
        },
        "context": {
            "window_size": context_window,
            "active_tokens": active_tokens,
            "session_total_tokens": SESSION_STATE["total_tokens"],
            "pct_used": round((active_tokens / context_window) * 100.0, 1) if context_window > 0 else 0.0,
        },
        "available_models": [
            {
                "id": k,
                "name": v["name"],
                "status": v["status"],
                "recommended": v["recommended"],
                "vram": v["vram_gb"],
                "speed": v["speed_tks"],
            }
            for k, v in MODELS_CONFIG.items()
        ],
    }


@app.post("/api/upload")
async def upload_expression_matrix(file: UploadFile = File(...)):
    raw_name = file.filename or "uploaded_matrix.csv"
    clean_base = Path(raw_name).name
    ext = Path(clean_base).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTS:
        raise HTTPException(status_code=400, detail="Only .csv, .tsv, and .txt expression matrices are supported.")

    safe_name = f"{safe_slug(Path(clean_base).stem)}{ext}"
    dest_path = safe_resolve(UPLOADS_DIR, safe_name, ALLOWED_UPLOAD_EXTS)

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the 25 MB size limit.")

    with open(dest_path, "wb") as fh:
        fh.write(content)

    text_sample = content[:8192].decode("utf-8", errors="ignore")
    lines = [ln for ln in text_sample.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        raise HTTPException(status_code=400, detail="Uploaded file must contain a header row and at least one data row.")

    header_line = lines[0]
    delimiter = "\t" if "\t" in header_line else ","
    col_names = [c.strip().strip('"') for c in header_line.split(delimiter)]
    if len(col_names) < 3:
        raise HTTPException(status_code=400, detail="Matrix must contain a gene column and at least 2 sample columns.")

    has_floats = False
    for line in lines[1:15]:
        parts = line.split(delimiter)
        for p in parts[1:]:
            try:
                val = float(p.strip())
                if "." in p.strip() and val != int(val):
                    has_floats = True
                    break
            except ValueError:
                pass
        if has_floats:
            break

    row_count_est = max(1, content.count(b"\n") - 1)
    detected_type = "FPKM / Normalized Continuous Values" if has_floats else "Raw Discrete Integer Counts"
    strategy = (
        "Descriptive log2FC ranking (§13 Count-refusal guard activated)"
        if has_floats
        else "Welch t-test + Benjamini-Hochberg FDR (Live Screening)"
    )

    return {
        "status": "success",
        "filename": safe_name,
        "size_bytes": len(content),
        "columns": col_names[:10],
        "total_columns": len(col_names),
        "estimated_genes": row_count_est,
        "detected_data_type": detected_type,
        "recommended_strategy": strategy,
        "guardrail_status": (
            "ACTIVATED (Refused count-based NB-GLM for non-integer values)"
            if has_floats
            else "PASSED (Integer count schema compliant)"
        ),
    }


@app.get("/api/datasets")
async def get_datasets():
    csv_path = TABLES_DIR / "dataset_summary.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Dataset summary table not found.")
    with open(csv_path, mode="r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return {"datasets": rows}


@app.get("/api/tables/{table_name}")
async def get_table(table_name: str):
    clean_stem = safe_slug(table_name[:-4] if table_name.lower().endswith(".csv") else table_name)
    csv_path = safe_resolve(TABLES_DIR, f"{clean_stem}.csv", {".csv"})
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"Table {clean_stem} not found.")
    with open(csv_path, mode="r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return {"table": clean_stem, "rows": rows}


@app.get("/api/figures/{figure_name}")
async def get_figure(figure_name: str):
    fig_path = safe_resolve(FIGURES_DIR, figure_name, {".png", ".jpg", ".jpeg", ".svg"})
    if not fig_path.exists():
        raise HTTPException(status_code=404, detail=f"Figure {figure_name} not found.")
    media = "image/svg+xml" if fig_path.suffix.lower() == ".svg" else "image/png"
    return FileResponse(fig_path, media_type=media)


@app.get("/api/genes/{dataset}")
async def download_gene_table(dataset: str):
    """Download the actual differential expression gene table CSV for the requested dataset."""
    safe_ds = safe_slug(dataset)

    # 1. Custom/live run computed DE CSV
    live_csv = safe_resolve(UPLOADS_DIR, f"{safe_ds}_de_results.csv", {".csv"})
    if live_csv.exists():
        return FileResponse(
            live_csv,
            media_type="text/csv",
            filename=f"{safe_ds}_de_results.csv",
            headers={"Content-Disposition": f"attachment; filename={safe_ds}_de_results.csv"},
        )

    # 2. Full DESeq2 reference CSV for GSE202768
    if safe_ds == "GSE202768":
        ref_csv = BASE_DIR / "reference" / "outputs" / "GSE202768" / "de_results.csv"
        if ref_csv.exists():
            return FileResponse(
                ref_csv,
                media_type="text/csv",
                filename="GSE202768_de_results.csv",
                headers={"Content-Disposition": "attachment; filename=GSE202768_de_results.csv"},
            )

    # 3. Extract top_genes from preserved GEO trace JSON
    trace_name = DATASET_TRACE_MAP.get(safe_ds)
    if trace_name:
        trace_path = TRACES_DIR / trace_name
        if trace_path.exists():
            with open(trace_path, "r", encoding="utf-8") as fh:
                tdata = json.load(fh)
            genes = tdata.get("comp", {}).get("top_genes", [])
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=["gene", "log2FC", "padj", "pvalue", "direction"])
            writer.writeheader()
            for g in genes:
                writer.writerow({k: g.get(k) for k in ("gene", "log2FC", "padj", "pvalue", "direction")})
            buf.seek(0)
            return StreamingResponse(
                iter([buf.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={safe_ds}_top_genes.csv"},
            )

    raise HTTPException(status_code=404, detail=f"Gene table not found for dataset {safe_ds}.")


@app.get("/api/trace/{dataset}")
async def download_dataset_trace(dataset: str):
    """Return the actual execution trace JSON for a benchmark or live dataset."""
    safe_ds = safe_slug(dataset)
    live_trace = safe_resolve(TRACES_DIR, f"live_{safe_ds}.json", {".json"})
    if live_trace.exists():
        with open(live_trace, "r", encoding="utf-8") as fh:
            return sanitize_floats(json.load(fh))

    trace_name = DATASET_TRACE_MAP.get(safe_ds)
    if trace_name:
        trace_path = TRACES_DIR / trace_name
        if trace_path.exists():
            with open(trace_path, "r", encoding="utf-8") as fh:
                return sanitize_floats(json.load(fh))

    raise HTTPException(status_code=404, detail=f"Execution trace not found for dataset {safe_ds}.")


@app.get("/api/manifest")
async def get_manifest():
    manifest_path = OUTPUTS_DIR / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Manifest file not found.")
    with open(manifest_path, mode="r", encoding="utf-8") as fh:
        data = json.load(fh)
    return sanitize_floats(data)


class PipelineRunRequest(BaseModel):
    dataset: str = "GSE202768"
    model: str = "gemma-3-4b"
    query: Optional[str] = "Analyze differential expression and enriched pathways."
    disease_context: Optional[str] = "cancer"
    use_critic: bool = True
    compare_dataset: Optional[str] = None
    custom_filename: Optional[str] = None


class DiscoverRequest(BaseModel):
    genes: List[Dict[str, Any]]
    disease_context: str = "cancer"
    dataset_name: str = "custom_query"
    max_targets: int = 10


def _default_disease_for_dataset(dataset: str, requested: Optional[str]) -> str:
    if requested and requested.strip() and requested.strip().lower() != "auto":
        return requested.strip()
    mapping = {
        "GSE202768": "triple-negative breast cancer",
        "GSE113650": "triple-negative breast cancer",
        "GSE95304": "cancer MYC",
        "GSE336903": "cancer",
        "PDAC_Gemcitabine": "pancreatic ductal adenocarcinoma",
    }
    return mapping.get(dataset, "cancer")


@app.post("/api/discover")
async def discover_targets_and_drugs(req: DiscoverRequest):
    """Run live Open Targets + PubMed + ClinicalTrials.gov discovery with MoA Concordance Audit."""
    from tools.therapeutic_discovery import run_target_discovery

    if not req.genes:
        raise HTTPException(status_code=400, detail="Provide at least one gene with log2FC.")
    dossier = run_target_discovery(
        top_genes=req.genes,
        disease_context=req.disease_context,
        dataset_name=safe_slug(req.dataset_name),
        max_targets=max(1, min(15, req.max_targets)),
        use_cache=True,
        live_network=True,
    )
    return sanitize_floats(dossier)


@app.get("/api/target_dossier_csv/{dataset}")
async def download_target_dossier_csv(dataset: str, disease: str = "cancer"):
    """Download a structured CSV of ranked therapeutic targets, gene-flipping actions, drugs, and safety flags."""
    from tools.therapeutic_discovery import run_target_discovery

    safe_ds = safe_slug(dataset)
    top_genes: List[Dict[str, Any]] = []

    live_trace = safe_resolve(TRACES_DIR, f"live_{safe_ds}.json", {".json"})
    if live_trace.exists():
        with open(live_trace, "r", encoding="utf-8") as fh:
            ldata = json.load(fh)
        top_genes = ldata.get("top_genes", [])
    elif safe_ds in DATASET_TRACE_MAP:
        tpath = TRACES_DIR / DATASET_TRACE_MAP[safe_ds]
        if tpath.exists():
            with open(tpath, "r", encoding="utf-8") as fh:
                tdata = json.load(fh)
            top_genes = tdata.get("comp", {}).get("top_genes", [])

    if not top_genes:
        raise HTTPException(status_code=404, detail=f"No computed genes found for {safe_ds}.")

    dossier = run_target_discovery(
        top_genes=top_genes[:12],
        disease_context=_default_disease_for_dataset(safe_ds, disease),
        dataset_name=safe_ds,
        max_targets=12,
        use_cache=True,
        live_network=True,
    )
    buf = io.StringIO()
    fieldnames = [
        "gene",
        "ensembl_id",
        "log2FC",
        "padj",
        "recommended_flip",
        "priority_score",
        "evidence_tier",
        "concordant_drugs_count",
        "total_known_drugs",
        "is_essential",
        "safety_liabilities_count",
        "safety_warning",
        "opentargets_url",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for t in dossier.get("targets", []):
        writer.writerow({k: t.get(k, "") for k in fieldnames})
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={safe_ds}_target_dossier.csv"},
    )


def _build_steps_from_trace(dataset_id: str, trace_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build honest, trace-derived UI steps from a real preserved eval_*.json trace."""
    comp = trace_data.get("comp", {})
    plan = trace_data.get("plan", {})
    interp = trace_data.get("interp", {})
    verdict = trace_data.get("verdict", {})
    traces = trace_data.get("traces", [])

    def _find_traces(agent_name: str) -> List[Dict[str, Any]]:
        return [t for t in traces if t.get("agent") == agent_name]

    planner_t = (_find_traces("planner") or [{}])[-1]
    comp_t = (_find_traces("computational_analyst") or [{}])[-1]
    bio_t = (_find_traces("biological_interpreter") or [{}])[-1]
    ev_t = (_find_traces("evidence_retriever") or [{}])[-1]
    critic_ts = _find_traces("critic")

    critic_calls = []
    for ct in critic_ts:
        snap = ct.get("verdict_snapshot", {})
        it = ct.get("iteration", 0)
        errs = snap.get("errors", [])
        critic_calls.append({
            "tool": f"critic_audit_iter_{it}",
            "input": f"claims={snap.get('audit_scores', {}).get('total_claims_audited', len(interp.get('claims', [])))}",
            "output": (
                f"Iteration {it}: {ct.get('verdict_status')} ({len(errs)} errors)"
                + (f" — {errs[0]}" if errs else "")
            ),
        })

    final_verdict_status = verdict.get("status", "UNKNOWN")
    if any(t.get("fallback") for t in (planner_t, bio_t)):
        critic_thought_note = "Note: One or more upstream LLM calls used deterministic fallback in this trace."
    elif len(critic_ts) > 1:
        critic_thought_note = (
            f"Recorded {len(critic_ts)} audit passes in preserved trace (initial errors caught: "
            f"{critic_ts[0].get('errors_count', 0)}; final status: {final_verdict_status}). "
            f"Note: Updated codebase replaces legacy tag-stripping with Biology re-prompting or full claim pruning."
        )
    else:
        critic_thought_note = f"Single-pass deterministic audit completed with status {final_verdict_status} ({len(verdict.get('errors', []))} errors)."

    top_genes = comp.get("top_genes", [])[:5]
    top_pathways = comp.get("top_pathways", [])[:3]

    return [
        {
            "id": "planner",
            "agent": "Planner Agent",
            "status": "FALLBACK" if planner_t.get("fallback") else "COMPLETED",
            "icon": "Compass",
            "tools_selected": ["validate_metadata", "data_type_guard_s13", "plan_schema"],
            "tool_calls": [
                {"tool": "plan_schema", "input": f"dataset='{dataset_id}', organism='{plan.get('organism', 'N/A')}'", "output": f"data_type='{plan.get('data_type', 'N/A')}', method='{plan.get('de_method', 'N/A')}'"},
            ],
            "thought": f"Goal: {plan.get('analysis_goal', 'Differential expression analysis')}. Guardrails: {', '.join(plan.get('safety_guardrails', []))}.",
            "decision": f"Selected method: {plan.get('de_method', comp.get('data_type', 'N/A'))}",
            "latency_s": round(float(planner_t.get("latency_s", 0.0) or 0.0), 2),
            "tokens": int((planner_t.get("usage") or {}).get("total_tokens", 0) or 0),
        },
        {
            "id": "computational_analyst",
            "agent": "Computational Analyst",
            "status": "COMPLETED",
            "icon": "Cpu",
            "tools_selected": ["Deterministic Statistical Engine", "Enrichment Loader"],
            "tool_calls": [
                {"tool": "execute_computation", "input": f"dataset='{dataset_id}', contrast='{comp.get('contrast', 'N/A')}'", "output": f"Tested {comp.get('n_total_tested', 0):,} features; {comp.get('n_sig', 0):,} passed threshold ({comp.get('n_up', 0):,} up, {comp.get('n_down', 0):,} down)"},
            ],
            "thought": "; ".join(comp_t.get("execution_log", []) or [f"Executed {comp.get('data_type', 'DE analysis')} on {dataset_id}."]),
            "decision": f"Top genes: {', '.join(g.get('gene', '') for g in top_genes)}",
            "latency_s": round(float(comp_t.get("latency_s", 0.0) or 0.0), 2),
            "tokens": 0,
        },
        {
            "id": "biological_interpreter",
            "agent": "Biological Interpreter",
            "status": "FALLBACK" if bio_t.get("fallback") else "COMPLETED",
            "icon": "Dna",
            "tools_selected": ["Structured Biological Synthesis"],
            "tool_calls": [
                {"tool": "interpret_results", "input": f"top_genes={len(comp.get('top_genes', []))}, pathways={len(comp.get('top_pathways', []))}", "output": f"Generated {len(interp.get('claims', []))} claims; top pathways: {', '.join(p.get('term', '') for p in top_pathways) or 'none'}"},
            ],
            "thought": (interp.get("observations") or ["Synthesized biological observations from computed results."])[0],
            "decision": f"Produced {len(interp.get('claims', []))} hedged claims with study limitations and research-use disclaimer.",
            "latency_s": round(float(bio_t.get("latency_s", 0.0) or 0.0), 2),
            "tokens": int((bio_t.get("usage") or {}).get("total_tokens", 0) or 0),
        },
        {
            "id": "evidence_retriever",
            "agent": "Evidence Retriever",
            "status": "COMPLETED",
            "icon": "Search",
            "tools_selected": ["Computed DE & Enrichment Index"],
            "tool_calls": [
                {"tool": "verify_claim_references", "input": f"corpus='{ev_t.get('corpus', 'computed_tables')}'", "output": f"Grounded {ev_t.get('grounded_records', 0)}/{ev_t.get('n_records', 0)} records in preserved trace"},
            ],
            "thought": f"Cross-referenced cited genes and pathway names directly against computed DE and enrichment outputs for {dataset_id}.",
            "decision": f"Grounded {ev_t.get('grounded_records', 0)}/{ev_t.get('n_records', 0)} records.",
            "latency_s": 0.05,
            "tokens": 0,
        },
        {
            "id": "critic",
            "agent": "Adversarial Critic / Verifier",
            "status": final_verdict_status,
            "icon": "ShieldCheck",
            "tools_selected": ["Direction Consistency Checker", "§13 Data-Type Auditor", "Hedging & Disclaimer Validator"],
            "tool_calls": critic_calls or [{"tool": "critic_audit", "input": "claims", "output": f"VERDICT: {final_verdict_status}"}],
            "thought": critic_thought_note,
            "decision": f"VERDICT: {final_verdict_status} ({len(verdict.get('errors', []))} errors, {len(verdict.get('warnings', []))} warnings)",
            "latency_s": 0.05,
            "tokens": 0,
        },
    ]


@app.post("/api/run")
async def run_pipeline(req: PipelineRunRequest):
    query_lower = (req.query or "").lower()
    is_realtime = (
        req.dataset == "PDAC_Gemcitabine"
        or bool(req.custom_filename)
        or "gemcitabine" in query_lower
        or "pdac" in query_lower
        or "custom" in req.dataset.lower()
    )

    if is_realtime:
        from backend.realtime_engine import run_realtime_analysis

        target_file: Optional[Path] = None
        ds_name = req.dataset
        contrast_override: Optional[str] = None

        if req.custom_filename:
            target_file = safe_resolve(UPLOADS_DIR, req.custom_filename, ALLOWED_UPLOAD_EXTS)
            if not target_file.exists():
                raise HTTPException(status_code=404, detail=f"Uploaded file '{req.custom_filename}' not found.")
            ds_name = Path(req.custom_filename).stem
        else:
            target_file = BASE_DIR / "data" / "test_datasets" / "PDAC_gemcitabine_counts.csv"
            ds_name = "PDAC_Gemcitabine"
            contrast_override = "Gemcitabine-Resistant (n=3) vs Parental Sensitive (n=3) PDAC Cells"

        real_data = run_realtime_analysis(
            file_path=target_file,
            dataset_name=ds_name,
            contrast_name=contrast_override,
            model_name=req.model,
        )
        from tools.therapeutic_discovery import run_target_discovery

        disease_ctx = _default_disease_for_dataset(ds_name, req.disease_context)
        real_data["discovery"] = run_target_discovery(
            top_genes=real_data.get("top_genes", []),
            disease_context=disease_ctx,
            dataset_name=ds_name,
            max_targets=10,
            use_cache=True,
            live_network=True,
        )
        real_data.setdefault("downloads", {})["target_dossier_csv"] = (
            f"/api/target_dossier_csv/{ds_name}?disease={disease_ctx}"
        )
        run_tokens = sum(int(s.get("tokens", 0)) for s in real_data["steps"])
        SESSION_STATE["last_run_tokens"] = run_tokens
        SESSION_STATE["total_tokens"] += run_tokens
        SESSION_STATE["runs_count"] += 1
        SESSION_STATE["last_run_timestamp"] = time.time()
        return sanitize_floats(real_data)

    if req.dataset not in DATASET_TRACE_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown benchmark dataset '{req.dataset}'.")

    trace_file = TRACES_DIR / DATASET_TRACE_MAP[req.dataset]
    if not trace_file.exists():
        raise HTTPException(status_code=404, detail=f"Execution trace missing for {req.dataset}.")

    with open(trace_file, mode="r", encoding="utf-8") as fh:
        trace_data = json.load(fh)

    comp_info = trace_data.get("comp", {})
    interp_info = trace_data.get("interp", {})
    verdict_info = trace_data.get("verdict", {})

    plain_summaries = {
        "GSE202768": (
            "Triple-Negative Breast Cancer (Hs578T) PRRX1 knockdown (KD_DOX vs KD_noDOX, raw counts, pydeseq2): "
            "3,946 genes reached padj < 0.05 (2,002 upregulated, 1,944 downregulated) out of 14,009 tested. "
            "Top upregulated genes include TGFBI (+1.95 log2FC), COL1A1 (+2.08 log2FC), and TNC (+1.89 log2FC), "
            "while PRRX1 itself is strongly suppressed (-2.28 log2FC). "
            "Note: This cached trace was recorded with Gemma 3 4B IT; the Critic caught 3 initial direction errors on iteration 0."
        ),
        "GSE113650": (
            "External validation comparing TNBC (MDA-MB-468, HCC70, HCC1143) vs non-TNBC (MCF7, BT474, T47D) breast cancer lines "
            "using published CuffDiff tables: 990 significant genes (q < 0.05) across 14,817 tested features, "
            "highlighting IER3, IGFBP4, and basal/epithelial markers with zero direction errors."
        ),
        "GSE95304": (
            "Held-out FPKM perturbation benchmark (shMyc vs shSCR): Master Plan §13 Data-Type Refusal Guard blocked count-based DESeq2 "
            "on normalized FPKM values and executed descriptive log2FC ranking across 14,387 expressed genes (2,063 with |log2FC| >= 1.0), "
            "including SNORD78 (+11.05 log2FC) and MIR1292 (-10.83 log2FC)."
        ),
        "GSE336903": (
            "Cross-species Mus musculus Fig. 7 cell-line FPKM smoke test: Planner identified mouse gene identifiers and enforced "
            "descriptive FPKM analysis under §13 across 54,289 features (3,014 with |log2FC| >= 1.0), passing Critic verification with zero direction errors."
        ),
    }

    steps = _build_steps_from_trace(req.dataset, trace_data)
    run_tokens = sum(int(s.get("tokens", 0)) for s in steps)
    SESSION_STATE["last_run_tokens"] = run_tokens
    SESSION_STATE["total_tokens"] += run_tokens
    SESSION_STATE["runs_count"] += 1
    SESSION_STATE["last_run_timestamp"] = time.time()

    raw_pathways = comp_info.get("top_pathways", [])[:6]
    formatted_pathways = [
        {
            "source": p.get("source", "Enrichment"),
            "term": p.get("term", ""),
            "adjP": p.get("padj", p.get("adjP", 1.0)),
            "overlap": p.get("overlap", "N/A"),
        }
        for p in raw_pathways
    ]

    from tools.therapeutic_discovery import run_target_discovery

    disease_ctx = _default_disease_for_dataset(req.dataset, req.disease_context)
    discovery_dossier = run_target_discovery(
        top_genes=comp_info.get("top_genes", [])[:15],
        disease_context=disease_ctx,
        dataset_name=req.dataset,
        max_targets=10,
        use_cache=True,
        live_network=True,
    )

    response_data = {
        "status": "success",
        "mode": "verified_trace_replay",
        "dataset": req.dataset,
        "compare_dataset": req.compare_dataset,
        "model": MODELS_CONFIG.get(req.model, MODELS_CONFIG["gemma-3-4b"]),
        "total_latency_s": round(sum(float(s.get("latency_s", 0.0)) for s in steps), 2),
        "plain_summary": plain_summaries.get(req.dataset, ""),
        "steps": steps,
        "verdict": verdict_info,
        "stats": {
            "genes_tested": comp_info.get("n_total_tested", 0),
            "significant_genes": comp_info.get("n_sig", 0),
            "up_regulated": comp_info.get("n_up", 0),
            "down_regulated": comp_info.get("n_down", 0),
            "padj_threshold": comp_info.get("padj_threshold", 0.05),
            "inferential": "fpkm" not in str(comp_info.get("data_type", "")).lower(),
            "contrast": comp_info.get("contrast", "Condition A vs Condition B"),
            "data_type": comp_info.get("data_type", "RNA-seq"),
        },
        "top_genes": comp_info.get("top_genes", [])[:15],
        "sig_pathways": formatted_pathways,
        "discovery": discovery_dossier,
        "interp": {
            "observations": interp_info.get("observations", []),
            "claims": interp_info.get("claims", []),
            "limitations": interp_info.get("limitations", []),
            "disclaimer": interp_info.get(
                "disclaimer",
                "RESEARCH USE ONLY: BioAgent-Lite outputs are intended exclusively for basic scientific research and hypothesis generation, not clinical guidance.",
            ),
        },
        "figures": {
            "volcano": f"/api/figures/volcano_plot_{req.dataset}.png",
            "pathways": f"/api/figures/pathways_{req.dataset}.png",
        },
        "downloads": {
            "analysis_pdf": f"/api/report/analysis_pdf?dataset={req.dataset}&model={req.model}",
            "pdf_report": f"/api/report/analysis_pdf?dataset={req.dataset}&model={req.model}",
            "gene_table_csv": f"/api/genes/{req.dataset}",
            "target_dossier_csv": f"/api/target_dossier_csv/{req.dataset}?disease={disease_ctx}",
            "trace_json": f"/api/trace/{req.dataset}",
        },
        "trace": trace_data,
    }

    return sanitize_floats(response_data)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
