"""BioAgent-Lite Dynamic Analysis Report PDF Generator.

Generates structured computational genomics analysis reports for any executed
GEO benchmark or user-uploaded expression matrix using ReportLab Platypus.
Enforces strict output path confinement and reports the actual Critic verdict.
"""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
TRACES_DIR = OUTPUTS_DIR / "traces"
REPORTS_DIR = OUTPUTS_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DATASET_TRACE_MAP = {
    "GSE202768": "eval_GSE202768_20260907T061142Z.json",
    "GSE113650": "eval_GSE113650_20260907T061208Z.json",
    "GSE95304": "eval_GSE95304_20260907T061231Z.json",
    "GSE336903": "eval_GSE336903_20260907T061251Z.json",
}

MODELS_MAP = {
    "gemma-3-4b": "Google Gemma 3 4B IT (Q8_K_XL) — Measured Primary Model",
    "medgemma-4b": "Google MedGemma 4B IT (Q8_K_XL) — Pending Local GGUF Run",
    "qwen-3-8b": "Alibaba Qwen3 8B IT (Q4_K_M) — Pending Local GGUF Run",
}


def _safe_slug(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", str(name or "report")).strip("._")
    return cleaned[:64] or "report"


def _xml_escape(text: Any) -> str:
    s = str(text or "")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_analysis_pdf(
    dataset: str,
    model_id: str = "gemma-3-4b",
    run_data: Optional[Dict[str, Any]] = None,
) -> Path:
    """Generate a dynamic PDF report for a specific analyzed dataset."""
    safe_ds = _safe_slug(dataset)

    verdict: Dict[str, Any] = {}
    if not run_data:
        live_trace = TRACES_DIR / f"live_{safe_ds}.json"
        if live_trace.exists():
            with open(live_trace, "r", encoding="utf-8") as fh:
                run_data = json.load(fh)
        elif safe_ds == "PDAC_Gemcitabine":
            pdac_path = BASE_DIR / "data" / "test_datasets" / "PDAC_gemcitabine_counts.csv"
            if pdac_path.exists():
                from backend.realtime_engine import run_realtime_analysis

                run_data = run_realtime_analysis(pdac_path, dataset_name=safe_ds, model_name=model_id)

    if run_data:
        comp = run_data.get("stats", {})
        interp = run_data.get("interp", {})
        verdict = run_data.get("verdict", {})
    else:
        trace_file_name = DATASET_TRACE_MAP.get(safe_ds)
        trace_data: Dict[str, Any] = {}
        if trace_file_name and (TRACES_DIR / trace_file_name).exists():
            with open(TRACES_DIR / trace_file_name, "r", encoding="utf-8") as fh:
                trace_data = json.load(fh)
        comp = trace_data.get("comp", {})
        interp = trace_data.get("interp", {})
        verdict = trace_data.get("verdict", {})

    output_pdf_path = (REPORTS_DIR / f"BioAgent_Analysis_Report_{safe_ds}.pdf").resolve()
    if not output_pdf_path.is_relative_to(REPORTS_DIR.resolve()):
        raise ValueError("Resolved PDF output path escapes REPORTS_DIR.")

    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("DocTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=colors.HexColor("#0F172A"))
    subtitle_style = ParagraphStyle("DocSubtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#0F766E"))
    h2_style = ParagraphStyle("SectionHeading", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=colors.HexColor("#0F172A"), spaceBefore=10, spaceAfter=4)
    body_style = ParagraphStyle("BodyTextCustom", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=13, textColor=colors.HexColor("#334155"))
    bold_body = ParagraphStyle("BoldBody", parent=body_style, fontName="Helvetica-Bold")
    table_header_style = ParagraphStyle("TableHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.white)
    table_cell_style = ParagraphStyle("TableCell", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#1E293B"))
    table_cell_bold = ParagraphStyle("TableCellBold", parent=table_cell_style, fontName="Helvetica-Bold")
    disclaimer_style = ParagraphStyle("Disclaimer", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=7.5, leading=10, textColor=colors.HexColor("#64748B"))

    story = []

    verdict_status = str(verdict.get("status", "UNAUDITED")).upper()
    err_count = len(verdict.get("errors", []) or [])
    badge_color = "#0F766E" if verdict_status == "PASS" else ("#B45309" if verdict_status == "REVISED" else "#B91C1C")
    badge_label = f"{verdict_status} ({err_count} errors)"

    header_data = [
        [
            Paragraph("<b>BioAgent-Lite: Transcriptomics Analysis Report</b>", title_style),
            Paragraph(f"<b>CRITIC:</b> <font color='{badge_color}'>{_xml_escape(badge_label)}</font>", ParagraphStyle("StatusBadge", parent=body_style, alignment=2, fontName="Helvetica-Bold")),
        ],
        [
            Paragraph("Multi-Agent Differential Expression, Evidence Grounding &amp; Audit Summary", subtitle_style),
            Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", ParagraphStyle("DateText", parent=body_style, alignment=2, textColor=colors.HexColor("#64748B"))),
        ],
    ]
    header_table = Table(header_data, colWidths=[370, 170])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F766E"), spaceAfter=10))

    model_name = MODELS_MAP.get(model_id, MODELS_MAP["gemma-3-4b"])
    meta_data = [
        [Paragraph("<b>Dataset:</b>", bold_body), Paragraph(_xml_escape(safe_ds), body_style), Paragraph("<b>Model:</b>", bold_body), Paragraph(_xml_escape(model_name), body_style)],
        [Paragraph("<b>Contrast:</b>", bold_body), Paragraph(_xml_escape(comp.get("contrast", "Group A vs Group B")), body_style), Paragraph("<b>Data Type:</b>", bold_body), Paragraph(_xml_escape(comp.get("data_type", "RNA-seq")), body_style)],
    ]
    meta_table = Table(meta_data, colWidths=[75, 195, 75, 195])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Executive Summary
    story.append(Paragraph("1. Executive Biological Synthesis", h2_style))
    fallback_summary = (
        f"Multi-agent differential expression analysis completed for {safe_ds}. "
        f"Evaluated {comp.get('n_total_tested', comp.get('genes_tested', 0)):,} features with "
        f"{comp.get('n_sig', comp.get('significant_genes', 0)):,} meeting the threshold."
    )
    summary_text = (run_data.get("plain_summary") if run_data else None) or fallback_summary
    summary_box = Table([[Paragraph(_xml_escape(summary_text), body_style)]], colWidths=[540])
    summary_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(summary_box)
    story.append(Spacer(1, 10))

    # Stats table
    story.append(Paragraph("2. Computational Summary Metrics", h2_style))
    padj_disp = f"padj < {comp.get('padj_threshold', 0.05)}" if comp.get("inferential", True) and comp.get("padj_threshold") is not None else "Descriptive |log2FC| >= 1.0"
    stats_data = [
        [
            Paragraph("<b>Features Tested</b>", table_header_style),
            Paragraph("<b>Passed Threshold</b>", table_header_style),
            Paragraph("<b>Upregulated</b>", table_header_style),
            Paragraph("<b>Downregulated</b>", table_header_style),
            Paragraph("<b>Criterion</b>", table_header_style),
        ],
        [
            Paragraph(f"<b>{comp.get('n_total_tested', comp.get('genes_tested', 0)):,}</b>", table_cell_bold),
            Paragraph(f"<b>{comp.get('n_sig', comp.get('significant_genes', 0)):,}</b>", table_cell_bold),
            Paragraph(f"{comp.get('n_up', comp.get('up_regulated', 0)):,}", table_cell_style),
            Paragraph(f"{comp.get('n_down', comp.get('down_regulated', 0)):,}", table_cell_style),
            Paragraph(_xml_escape(padj_disp), table_cell_style),
        ],
    ]
    stats_table = Table(stats_data, colWidths=[100, 105, 95, 95, 145])
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 10))

    # Top genes table
    story.append(Paragraph("3. Top Differential Features", h2_style))
    gene_rows = [[
        Paragraph("<b>Rank</b>", table_header_style),
        Paragraph("<b>Gene</b>", table_header_style),
        Paragraph("<b>log2FC</b>", table_header_style),
        Paragraph("<b>Adjusted p-value</b>", table_header_style),
        Paragraph("<b>Direction</b>", table_header_style),
    ]]
    raw_genes = (comp.get("top_genes") or (run_data.get("top_genes") if run_data else []) or [])[:10]
    for idx, g in enumerate(raw_genes):
        fc = g.get("log2FC")
        fc_str = f"{'+' if isinstance(fc, (int, float)) and fc > 0 else ''}{fc:.2f}" if isinstance(fc, (int, float)) and not math.isinf(fc) else "N/A"
        padj = g.get("padj")
        padj_str = f"{padj:.2e}" if isinstance(padj, (int, float)) and not math.isnan(padj) else "N/A (Descriptive)"
        direction = str(g.get("direction", "up" if isinstance(fc, (int, float)) and fc > 0 else "down")).upper()
        dir_color = "#16A34A" if direction == "UP" else "#DC2626"
        gene_rows.append([
            Paragraph(str(idx + 1), table_cell_style),
            Paragraph(f"<b>{_xml_escape(g.get('gene', 'N/A'))}</b>", table_cell_bold),
            Paragraph(fc_str, table_cell_style),
            Paragraph(padj_str, table_cell_style),
            Paragraph(f"<font color='{dir_color}'><b>{direction}</b></font>", table_cell_style),
        ])

    gene_table = Table(gene_rows, colWidths=[40, 140, 110, 140, 110])
    gene_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(gene_table)
    story.append(Spacer(1, 10))

    # Figures (strictly matching this dataset only)
    volcano_path = FIGURES_DIR / f"volcano_plot_{safe_ds}.png"
    pathway_path = FIGURES_DIR / f"pathways_{safe_ds}.png"
    img_elements = []
    if volcano_path.exists():
        img_elements.append(Image(str(volcano_path), width=260, height=175))
    if pathway_path.exists():
        img_elements.append(Image(str(pathway_path), width=260, height=175))

    if img_elements:
        story.append(Paragraph("4. Computed Visualizations", h2_style))
        fig_table = Table([img_elements], colWidths=[270] * len(img_elements))
        fig_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story.append(fig_table)
        story.append(Spacer(1, 8))

    # Observations & Limitations
    obs_list = interp.get("observations", [])
    if obs_list:
        story.append(Paragraph("5. Audited Observations", h2_style))
        for obs in obs_list[:5]:
            story.append(Paragraph(f"• {_xml_escape(obs)}", body_style))
            story.append(Spacer(1, 2))
        story.append(Spacer(1, 6))

    story.append(Paragraph("6. Limitations &amp; Research-Use Disclaimer", h2_style))
    for lim in interp.get("limitations", ["Exploratory transcriptomic summary; orthogonal experimental validation is required."]):
        story.append(Paragraph(f"• {_xml_escape(lim)}", body_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 6))
    disclaimer_text = interp.get(
        "disclaimer",
        "RESEARCH USE ONLY: BioAgent-Lite outputs are intended exclusively for basic scientific research and hypothesis generation, not clinical diagnosis or therapeutic guidance.",
    )
    story.append(Paragraph(f"<b>DISCLAIMER:</b> {_xml_escape(disclaimer_text)}", disclaimer_style))

    doc.build(story)
    return output_pdf_path
