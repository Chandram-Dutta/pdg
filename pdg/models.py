from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SectionDef:
    """Definition of a single report section that accepts CSV data."""

    key: str
    title: str
    description: str
    heading_prefix: str
    graph_type: str | None = None
    graph_xlabel: str = ""
    graph_ylabel: str = ""
    loading_levels: list[str] | None = None
    ieee_limits: dict[str, float] | None = None


@dataclass
class ReportDef:
    """Definition of a full report format (collection of sections)."""

    key: str
    name: str
    sections: list[SectionDef]


@dataclass
class SectionState:
    """Runtime state: CSV files assigned to a section."""

    csv_files: list[Path] = field(default_factory=list)
    analysis_text: str = ""
    analysis_approved: bool | None = None
