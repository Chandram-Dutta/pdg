from __future__ import annotations

import tempfile

import matplotlib.pyplot as plt
import pandas as pd

from pdg.models import SectionDef


def _add_ieee_limit_line(ax, x_labels, ieee_limits: dict[str, float]) -> None:
    """Overlay a stepped IEEE 519-2022 limit line on a bar chart."""
    limit_vals = []
    for label in x_labels:
        key = str(label)
        limit_vals.append(ieee_limits.get(key))

    if not any(v is not None for v in limit_vals):
        return

    xs, ys = [], []
    for i, v in enumerate(limit_vals):
        if v is not None:
            xs.append(i)
            ys.append(v)

    ax.step(xs, ys, where="mid", color="red", linewidth=1.5,
            linestyle="--", label="IEEE 519-2022 Limit", zorder=5)
    ax.legend(fontsize=7, loc="upper right")


def plot_section(df: pd.DataFrame, title: str, section: SectionDef) -> str | None:
    """Create a chart for the section and return the path to a temp PNG, or None."""
    if section.graph_type is None:
        return None

    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 4.5))

    first_col = df.columns[0]
    x_labels = df[first_col]
    # Exclude IEEE limit/pass-fail columns from the plot data
    skip_cols = {first_col, "IEEE_Limit_pct", "Limit_Passed"}
    plot_cols = [c for c in numeric.columns if c not in skip_cols]
    plot_df = numeric[plot_cols] if plot_cols else numeric

    if section.graph_type == "bar":
        plot_df.plot(kind="bar", ax=ax)
        if len(x_labels) == len(plot_df):
            ax.set_xticks(range(len(x_labels)))
            ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=7)
        if section.ieee_limits:
            _add_ieee_limit_line(ax, x_labels, section.ieee_limits)
    elif section.graph_type == "line":
        x = x_labels if len(x_labels) == len(plot_df) else plot_df.index
        for col in plot_df.columns:
            ax.plot(x, plot_df[col], label=col)
        ax.legend()
    elif section.graph_type == "scatter":
        for col in plot_df.columns:
            ax.scatter(x_labels, plot_df[col], label=col, s=12)
        ax.legend()
    else:
        plt.close(fig)
        return None

    ax.set_title(title, fontsize=10)
    ax.set_xlabel(section.graph_xlabel)
    ax.set_ylabel(section.graph_ylabel)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        fig.savefig(tmp.name, dpi=160)
    plt.close(fig)
    return tmp.name
