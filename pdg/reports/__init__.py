from __future__ import annotations

from pdg.models import ReportDef
from pdg.reports.power_quality import POWER_QUALITY_REPORT

REPORT_REGISTRY: list[ReportDef] = [
    POWER_QUALITY_REPORT,
]


def get_report(key: str) -> ReportDef:
    for r in REPORT_REGISTRY:
        if r.key == key:
            return r
    raise KeyError(f"Unknown report: {key}")
