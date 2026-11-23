"""Measured Cross-Dataset Evaluation Plot Generator.

Reads strictly from measured outputs/tables/dataset_generalization.csv and
outputs/tables/architecture_comparison.csv generated from real trace files in
outputs/traces/. Contains zero hardcoded confusion matrices or unmeasured
multi-model numbers.
"""
import os
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABLES_DIR = os.path.join(BASE_DIR, "outputs", "tables")
FIGURES_DIR = os.path.join(BASE_DIR, "outputs", "figures")
PUBLIC_DIR = os.path.join(BASE_DIR, "frontend", "public")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]


def plot_measured_dataset_generalization() -> None:
    """Plot strictly measured per-dataset generalization metrics from dataset_generalization.csv."""
    csv_path = os.path.join(TABLES_DIR, "dataset_generalization.csv")
    if not os.path.exists(csv_path):
        print(f"Missing {csv_path}. Run evaluation/metrics/rebuild_measured_artifacts.py first.")
        return

    df = pd.read_csv(csv_path)
    if df.empty:
        print("dataset_generalization.csv is empty; nothing to plot.")
        return

    datasets = df["Dataset"].astype(str).tolist()
    x = np.arange(len(datasets))
    width = 0.25

    stat_acc = pd.to_numeric(df["Statistical Accuracy"], errors="coerce").fillna(0.0).values
    ev_rate = pd.to_numeric(df["Evidence Support Rate"], errors="coerce").fillna(0.0).values
    de_prec = pd.to_numeric(df["DE Precision"], errors="coerce").fillna(0.0).values

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    b1 = ax.bar(x - width, de_prec, width, label="Cited-Gene Precision", color="#0ea5e9", edgecolor="#0f172a", linewidth=0.7)
    b2 = ax.bar(x, stat_acc, width, label="Statistical Accuracy", color="#10b981", edgecolor="#0f172a", linewidth=0.7)
    b3 = ax.bar(x + width, ev_rate, width, label="Evidence Support Rate", color="#6366f1", edgecolor="#0f172a", linewidth=0.7)

    for bars in (b1, b2, b3):
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

    ax.set_title("BioAgent-Lite: Measured Cross-Dataset Generalization (Gemma 3 4B IT Traces)", fontsize=12.5, fontweight="bold", pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(datasets, fontsize=10, fontweight="bold")
    ax.set_ylabel("Measured Score (0.0 to 1.0)", fontsize=10.5)
    ax.set_ylim(0, 1.18)
    ax.legend(loc="upper right", fontsize=9.5)
    plt.tight_layout()

    out_file = os.path.join(FIGURES_DIR, "architecture_comparison_all_datasets.png")
    plt.savefig(out_file, bbox_inches="tight")
    plt.close()
    shutil.copy(out_file, os.path.join(PUBLIC_DIR, "architecture_comparison_all_datasets.png"))
    print(f"Generated measured cross-dataset plot: {out_file}")


if __name__ == "__main__":
    plot_measured_dataset_generalization()
