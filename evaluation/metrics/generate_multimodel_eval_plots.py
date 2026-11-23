"""Measured Multi-Model Evaluation Plot Generator.

Reads strictly from outputs/tables/model_comparison.csv (generated from real
trace files in outputs/traces/). Skips any model whose Status is
'pending_local_gguf_run' so unmeasured models are never plotted with fabricated
numbers.
"""
import os
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIGURES_DIR = os.path.join(BASE_DIR, "outputs", "figures")
PUBLIC_DIR = os.path.join(BASE_DIR, "frontend", "public")
TABLES_DIR = os.path.join(BASE_DIR, "outputs", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]


def plot_measured_model_comparison() -> None:
    """Plot measured model comparison strictly from outputs/tables/model_comparison.csv."""
    csv_path = os.path.join(TABLES_DIR, "model_comparison.csv")
    if not os.path.exists(csv_path):
        print(f"Missing {csv_path}. Run evaluation/models/compare_models.py first.")
        return

    df = pd.read_csv(csv_path)
    measured = df[df["Status"] == "measured"].copy()
    if measured.empty:
        print("No measured model rows found in model_comparison.csv; skipping plot.")
        return

    models = measured["Model"].astype(str).tolist()
    x = np.arange(len(models))
    width = 0.25

    stat_acc = pd.to_numeric(measured["Statistical Accuracy"], errors="coerce").fillna(0.0).values
    ev_rate = pd.to_numeric(measured["Evidence Support Rate"], errors="coerce").fillna(0.0).values
    latency = pd.to_numeric(measured["Mean Latency (s)"], errors="coerce").fillna(0.0).values

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

    b1 = ax1.bar(x - width / 2, stat_acc, width, label="Statistical Accuracy", color="#10b981", edgecolor="#0f172a", linewidth=0.7)
    b2 = ax1.bar(x + width / 2, ev_rate, width, label="Evidence Support Rate", color="#0ea5e9", edgecolor="#0f172a", linewidth=0.7)
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 0.02, f"{h:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax1.set_title("Measured Quality Metrics (Measured Models Only)", fontsize=11.5, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(models, fontsize=9.5, fontweight="bold")
    ax1.set_ylim(0, 1.18)
    ax1.legend(fontsize=9)

    b3 = ax2.bar(x, latency, width * 1.4, color="#6366f1", edgecolor="#0f172a", linewidth=0.7)
    for bar in b3:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2, h + 0.3, f"{h:.1f}s", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax2.set_title("Measured Mean End-to-End Latency (s)", fontsize=11.5, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(models, fontsize=9.5, fontweight="bold")
    ax2.set_ylabel("Seconds")

    pending = df[df["Status"] != "measured"]["Model"].astype(str).tolist()
    subtitle = f"Pending local GGUF evaluation: {', '.join(pending)}" if pending else "All configured models measured"
    plt.suptitle(f"BioAgent-Lite Measured Model Evaluation\n({subtitle})", fontsize=12.5, fontweight="bold", y=1.03)
    plt.tight_layout()

    out_file = os.path.join(FIGURES_DIR, "all_models_4datasets_comparison.png")
    plt.savefig(out_file, bbox_inches="tight")
    plt.close()
    shutil.copy(out_file, os.path.join(PUBLIC_DIR, "all_models_4datasets_comparison.png"))
    print(f"Generated measured model comparison plot: {out_file}")


if __name__ == "__main__":
    plot_measured_model_comparison()
