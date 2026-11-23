"""Empirical Evaluation Plot Generator for BioAgent-Lite.

Reads strictly measured benchmark tables and reference DESeq2 output from disk:
- outputs/tables/architecture_comparison.csv
- outputs/tables/ablation_results.csv
- reference/outputs/GSE202768/de_results.csv

Zero synthetic distributions (no simulated Beta curves, no hand-crafted confusion arrays).
Saves publication-quality figures to outputs/figures/ and frontend/public/.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABLES_DIR = os.path.join(BASE_DIR, "outputs", "tables")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "figures")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend", "public")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["figure.dpi"] = 300


def _save_fig(filename: str) -> None:
    out_path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(out_path, bbox_inches="tight")
    plt.savefig(os.path.join(FRONTEND_DIR, filename), bbox_inches="tight")
    plt.close()
    print(f"Generated measured figure: {out_path}")


def plot_measured_architecture_comparison() -> None:
    """Plot measured architecture metrics directly from outputs/tables/architecture_comparison.csv."""
    csv_path = os.path.join(TABLES_DIR, "architecture_comparison.csv")
    if not os.path.exists(csv_path):
        print(f"Skipping architecture plot: {csv_path} not found. Run rebuild_measured_artifacts.py first.")
        return

    df = pd.read_csv(csv_path)
    metrics = ["DE Precision", "DE Recall", "DE F1", "Statistical Accuracy", "Evidence Support Rate"]
    labels = ["Precision", "Recall", "F1", "Stat Acc", "Evidence Support"]

    x = np.arange(len(metrics))
    n_sys = len(df)
    width = 0.72 / max(1, n_sys)
    palette = ["#ef4444", "#10b981", "#0ea5e9", "#6366f1"]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    for i, (_, row) in enumerate(df.iterrows()):
        vals = [float(row.get(m, 0.0)) for m in metrics]
        offset = (i - (n_sys - 1) / 2.0) * width
        bars = ax.bar(
            x + offset,
            vals,
            width,
            label=str(row["System"]),
            color=palette[i % len(palette)],
            alpha=0.9,
            edgecolor="#1e293b",
            linewidth=0.7,
        )
        for bar in bars:
            h = bar.get_height()
            ax.annotate(
                f"{h:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8.5,
                fontweight="bold",
            )

    ax.set_ylabel("Measured Score (0.0 to 1.0)", fontsize=11)
    ax.set_title("Measured Architecture Comparison on GSE202768 (Trace-Derived)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10.5, fontweight="bold")
    ax.set_ylim(0, 1.18)
    ax.axhline(1.0, color="#64748b", linestyle=":", alpha=0.6)
    ax.legend(loc="upper left", frameon=True, fontsize=9.5)
    plt.tight_layout()
    _save_fig("comprehensive_metrics_comparison.png")


def plot_measured_ablation_impact() -> None:
    """Plot measured ablation metrics directly from outputs/tables/ablation_results.csv."""
    csv_path = os.path.join(TABLES_DIR, "ablation_results.csv")
    if not os.path.exists(csv_path):
        print(f"Skipping ablation plot: {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    configs = [str(c) for c in df["Configuration"].tolist()]
    ev_support = [float(v) for v in df["Evidence Support Rate"].tolist()]
    stat_acc = [float(v) for v in df["Statistical Accuracy"].tolist()]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    colors = ["#0ea5e9", "#f59e0b", "#ef4444", "#6366f1", "#10b981"][: len(configs)]

    bars1 = ax1.bar(configs, ev_support, color=colors, alpha=0.88, edgecolor="#1e293b", linewidth=0.7)
    ax1.set_title("Measured Evidence Support Rate by Ablation", fontsize=11.5, fontweight="bold")
    ax1.set_ylabel("Evidence Support Rate", fontsize=10.5)
    ax1.set_ylim(0, 1.15)
    ax1.tick_params(axis="x", rotation=18, labelsize=8.5)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2, yval + 0.02, f"{yval:.1%}", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    bars2 = ax2.bar(configs, stat_acc, color=colors, alpha=0.88, edgecolor="#1e293b", linewidth=0.7)
    ax2.set_title("Measured Statistical Accuracy by Ablation", fontsize=11.5, fontweight="bold")
    ax2.set_ylabel("Statistical Accuracy", fontsize=10.5)
    ax2.set_ylim(0, 1.15)
    ax2.tick_params(axis="x", rotation=18, labelsize=8.5)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2, yval + 0.02, f"{yval:.1%}", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    plt.suptitle("Measured Role Ablation Study on GSE202768 (Trace-Derived)", fontsize=13.5, fontweight="bold", y=1.02)
    plt.tight_layout()
    _save_fig("ablation_impact_breakdown.png")


def plot_empirical_deseq2_distribution() -> None:
    """Plot real empirical DESeq2 volcano/effect-size distribution from reference/outputs/GSE202768/de_results.csv."""
    de_path = os.path.join(BASE_DIR, "reference", "outputs", "GSE202768", "de_results.csv")
    if not os.path.exists(de_path):
        print(f"Skipping DESeq2 empirical distribution: {de_path} not found.")
        return

    de_df = pd.read_csv(de_path).dropna(subset=["padj", "log2FoldChange"])
    sig_mask = (de_df["padj"] < 0.05) & (de_df["log2FoldChange"].abs() >= 1.0)
    up_mask = sig_mask & (de_df["log2FoldChange"] > 0)
    down_mask = sig_mask & (de_df["log2FoldChange"] < 0)

    neg_log_p = -np.log10(de_df["padj"].clip(lower=1e-300))

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(de_df.loc[~sig_mask, "log2FoldChange"], neg_log_p[~sig_mask], s=6, color="#94a3b8", alpha=0.35, label="Non-significant")
    ax.scatter(de_df.loc[up_mask, "log2FoldChange"], neg_log_p[up_mask], s=10, color="#10b981", alpha=0.75, label=f"Up-regulated ({int(up_mask.sum())})")
    ax.scatter(de_df.loc[down_mask, "log2FoldChange"], neg_log_p[down_mask], s=10, color="#ef4444", alpha=0.75, label=f"Down-regulated ({int(down_mask.sum())})")

    ax.axhline(-np.log10(0.05), color="#475569", linestyle="--", linewidth=1)
    ax.axvline(1.0, color="#475569", linestyle=":", linewidth=1)
    ax.axvline(-1.0, color="#475569", linestyle=":", linewidth=1)
    ax.set_xlabel("log2 Fold Change (PRRX1 KD vs Control)", fontsize=11)
    ax.set_ylabel("-log10(Adjusted p-value)", fontsize=11)
    ax.set_title(f"GSE202768 Empirical DESeq2 Volcano Plot (N = {len(de_df):,} tested genes)", fontsize=12.5, fontweight="bold")
    ax.legend(loc="upper right", frameon=True, fontsize=9)
    plt.tight_layout()
    _save_fig("volcano_plot_GSE202768.png")


if __name__ == "__main__":
    plot_measured_architecture_comparison()
    plot_measured_ablation_impact()
    plot_empirical_deseq2_distribution()
    print("Measured evaluation plots updated cleanly with zero synthetic curves.")
