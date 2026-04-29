from __future__ import annotations

from io import StringIO

import pandas as pd

from pdg.models import ReportDef, SectionDef, SectionState


def render_report_markdown(
    report: ReportDef,
    section_states: dict[str, SectionState],
    max_table_rows: int = 10,
) -> str:
    """Render the report as markdown for preview before saving."""
    out = StringIO()
    any_section = False
    for section in report.sections:
        state = section_states.get(section.key)
        if not state or not state.csv_files:
            continue
        any_section = True
        out.write(f"# {section.title}\n\n")
        for idx, csv_path in enumerate(state.csv_files):
            heading = _heading_for(section, idx)
            out.write(f"## Table {idx + 1}: {heading}\n\n")
            try:
                df = pd.read_csv(csv_path)
            except Exception as exc:  # noqa: BLE001
                out.write(f"_(failed to read {csv_path.name}: {exc})_\n\n")
                continue
            out.write(_df_to_markdown(df, max_rows=max_table_rows))
            out.write("\n")
            if section.graph_type:
                out.write(f"_[{section.graph_type} chart will be inserted here]_\n\n")
        if state.analysis_approved and state.analysis_text:
            out.write("## Analysis\n\n")
            out.write(state.analysis_text.strip() + "\n\n")
        elif state.analysis_text:
            out.write("## Analysis (not approved — will NOT be included in docx)\n\n")
            out.write(state.analysis_text.strip() + "\n\n")
    if not any_section:
        return "_No sections with CSVs to preview._"
    return out.getvalue()


def _heading_for(section: SectionDef, idx: int) -> str:
    if section.loading_levels:
        label = (
            section.loading_levels[idx]
            if idx < len(section.loading_levels)
            else f"#{idx + 1}"
        )
        return f"{section.heading_prefix} {label} Loading"
    return section.heading_prefix


def _df_to_markdown(df: pd.DataFrame, max_rows: int = 10) -> str:
    if len(df) > max_rows:
        head = df.head(max_rows)
        suffix = f"\n_… {len(df) - max_rows} more rows_\n"
    else:
        head = df
        suffix = ""
    cols = [str(c) for c in head.columns]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for _, row in head.iterrows():
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines) + suffix + "\n"
