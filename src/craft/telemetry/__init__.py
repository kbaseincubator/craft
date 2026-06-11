"""craft.telemetry (C1 Workstream D) — a projecting consumer of the corrected
run-record. Egress (projector + whitelist + best-effort batch write) +
read (union + summarize + render). Vendored byte-equal into each skill (the
standalone-on-hub constraint — no `craft` on the Hub PYTHONPATH); a conformance
Family pins the copies. See `egress.py` / `read.py`.
"""
from __future__ import annotations

from craft.telemetry.egress import (
    CRAFT_KEEP,
    DEFAULT_TELEMETRY_ROOT,
    TELEMETRY_ROOT_ENV,
    egress_root,
    egress_run_record,
    project_record,
)
from craft.telemetry.read import (
    render_text,
    summarize,
    union_telemetry,
)

__all__ = [
    "CRAFT_KEEP",
    "DEFAULT_TELEMETRY_ROOT",
    "TELEMETRY_ROOT_ENV",
    "egress_root",
    "egress_run_record",
    "project_record",
    "render_text",
    "summarize",
    "union_telemetry",
]
