"""run_record.py — CRAFT-platform shared validator for the
`run-record.v1` contract (Cycle 3 / DP1, 2026-06-07).

This module is the **single source of truth for the run-record.v1
schema**. The three kbaseincubator skills (presentation-maker,
paper-writer, adversarial) each project their existing run-end state
into this shape and write it to `<draft_dir>/audit/run_record.json`;
`craft status` reads it; future telemetry / chrome consume it. Atlas
is deferred (decision 1, 2026-06-07).

Design family
-------------
`run-record.v1` is a **sibling of `deliverable-validation.v1`** /
`content-overflow.v1` / `layout-overlaps.v1`: same projectable-fields
discipline (tokens, counts, paths) at flat scalar keys, no free-text
in slots a downstream telemetry projector would whitelist. The
*record* is shared; the *emitters* differ per skill (project, don't
rebuild).

Cross-skill conformance (Family E)
----------------------------------
This validator is the cross-skill check. Each skill commits a golden
sample `run_record.json` (one `running`, one `completed`) under its
tests; craft-platform's `tests/test_conformance.py` adds Family E,
which loads every skill's goldens and asserts each one passes
`validate_run_record`. The validator does NOT pin source identity
(unlike Family C's llm_config check) — the *record* is shared, not
the producer code.

Contract semantics (the parts that bite)
----------------------------------------
* **One canonical completion signal:** `status` is authoritative
  with four states — two non-terminal (`running`, `halted`) and two
  terminal (`completed`, `failed`). `finished_at` and `exit_code`
  are populated iff `status` is terminal. The `halted` state is the
  arbitrator for the previously-ambiguous halt-gate case: a process
  exit at a halt-gate (e.g. presmaker's throughline-pick) MUST set
  `status="halted"` BEFORE exit, so the trap-EXIT finalize hook
  doesn't mis-promote it to `completed`/`failed`. `craft status`
  + the driver poll-loop read `halted` as a distinct surface from
  both `running` (still working) and the terminals.

* **`halted` ⇒ `current_stage` is non-null** and names the gate
  (e.g. `"throughline_pick"`). This is the arbitrator: the gate
  name in the record makes the same handshake `.handoff.json`
  carries the user-facing prompt for. Three-signal coherence —
  status says halted, current_stage names where, .handoff.json
  carries the prompt — kills the DP1 split-signal class without
  retiring `.handoff.json` (different semantic class).
* **Ownership:** the top-level run owner writes
  `audit/run_record.json`. A substage adversarial NEVER writes the
  parent's canonical path — it writes
  `audit/runs/run-N/adversarial_run_record.json` and the parent's
  adversarial-stage entry points at it via `stages[].subrecord`.
* **No clobber on re-run:** the canonical path is the LATEST run's
  record; the archived per-run copy lives at
  `audit/runs/run-N/run_record.json`. `run_id` = `run-N`.
* **Atomic writes:** producers must write to a sibling tempfile and
  `os.replace()` into place — `craft status` polls mid-run and must
  never observe a half-written file. The validator does not assert
  this (it's a write-side discipline); the start-write contract is
  pinned by `craft status` doing the right thing on a `running`
  record.

The schema (canonical version-frozen shape)
-------------------------------------------
```jsonc
{
  "schema_version": "run-record.v1",
  "skill":          "presentation-maker | paper-writer | adversarial",
  "skill_version":  "1.3.0",                 // from the skill's __version__
  "run_id":         "run-3",                  // presmaker run-N; others
                                              // mirror per-draft monotonic
  "draft_dir":      "/abs/path/papers/draft_2",
  "mode":           "talk-45 | report | ... | null",  // null when not set
                                                      // (e.g. adversarial standalone)
  "status":         "running | halted | completed | failed",  // canonical signal
  "started_at":     "2026-06-07T18:00:00Z",
  "finished_at":    "2026-06-07T18:42:00Z | null",   // null iff status non-terminal
                                                      // (running OR halted)
  "exit_code":      0,                                // null iff status non-terminal
  "current_stage":  "adversarial_review | throughline_pick | null",
                                                      // non-null when halted (names
                                                      // the gate); may be null when
                                                      // running (between stages);
                                                      // null when terminal
  "stages": [                                          // ordered execution log
    {
      "id":              "slide_compose",
      "status":          "completed | running | failed | skipped",
      "model":           "claude-sonnet-4-6 | null",
      "started_at":      "...",
      "finished_at":     "... | null",
      "elapsed_seconds": 180.0,
      "input_tokens":    0,
      "output_tokens":   0,
      "cache_read_tokens":     0,
      "cache_creation_tokens": 0,
      "cost_usd":        0.0,
      "subrecord":       "audit/runs/run-3/adversarial_run_record.json | null"
    }
  ],
  "totals": {
    "cost_usd":              0.0,
    "input_tokens":          0,
    "output_tokens":         0,
    "cache_read_tokens":     0,
    "cache_creation_tokens": 0,
    "elapsed_seconds":       0.0
  },
  "models_used": ["claude-sonnet-4-6", "claude-opus-4-6"],
  "artifacts": {
    "user_intent":            "audit/user_intent.json | null",
    "deliverable_validation": "audit/deliverable_validation.json | null",
    "deliverable":            "deliverable/<name>.pptx | manuscript.docx | review.md | null"
  }
}
```

Validation strictness
---------------------
* Top-level keys are **required** (all of them). Missing key →
  error. Extra unknown top-level keys → **error** (additive
  evolution goes through a schema-version bump, not a v1
  extension).
* Within `stages[]` entries: required keys are the production-stage
  fields above. Extra keys inside a stage entry are also rejected
  (same evolution rule).
* Type checks are conservative: ints stay ints (not `1.0`), floats
  stay floats. Token-count fields are required to be `int >= 0`;
  `cost_usd` and `elapsed_seconds` are `float >= 0.0`. ISO-8601
  timestamps are validated by shape, not parsed (we don't import
  datetime here — keep the validator cheap and stdlib-free except
  for `re`).
* Cross-field invariants checked: status/finished_at/exit_code/
  current_stage consistency; `totals.*` matches `sum(stages[].*)`
  to a small float tolerance (drift is a real bug class).
* Atomic-write + clobber-protection are NOT validatable from a
  static record — they're write-side disciplines. `craft status`'s
  ability to render a `running` record exercises the read-side.

The validator never raises on bad input; it returns a list of
human-readable error strings. Empty list = the record is valid.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = "run-record.v1"

# Frozen vocabularies — projectable telemetry tokens.
SKILLS = ("presentation-maker", "paper-writer", "adversarial")
# Run-level status. Two non-terminal states (running, halted) and two
# terminal (completed, failed). `halted` is the arbitrator for a
# process exit at a halt-gate — see _check_status_invariants.
RUN_STATUSES = ("running", "halted", "completed", "failed")
_NON_TERMINAL_STATUSES = frozenset({"running", "halted"})
_TERMINAL_STATUSES = frozenset({"completed", "failed"})
# Stage-level status is unchanged: a stage doesn't halt; the run does;
# `current_stage` says where (when status=halted).
STAGE_STATUSES = ("completed", "running", "failed", "skipped")

# Top-level required keys (extra keys → error).
_REQUIRED_TOP_KEYS = frozenset({
    "schema_version", "skill", "skill_version", "run_id", "draft_dir",
    "mode", "status", "started_at", "finished_at", "exit_code",
    "current_stage", "stages", "totals", "models_used", "artifacts",
})

# Required keys per stage entry (extra keys → error).
_REQUIRED_STAGE_KEYS = frozenset({
    "id", "status", "model", "started_at", "finished_at",
    "elapsed_seconds", "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_creation_tokens", "cost_usd",
    "subrecord",
})

# Required keys in totals + artifacts.
_REQUIRED_TOTALS_KEYS = frozenset({
    "cost_usd", "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_creation_tokens", "elapsed_seconds",
})
_REQUIRED_ARTIFACT_KEYS = frozenset({
    "user_intent", "deliverable_validation", "deliverable",
})

# Token-count fields (must be int >= 0).
_INT_COUNT_FIELDS = (
    "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_creation_tokens",
)

# Numeric (float >= 0.0) fields in stages + totals.
_FLOAT_FIELDS = ("cost_usd", "elapsed_seconds")

# ISO-8601 UTC timestamp shape — strict enough to flag obvious junk,
# loose enough not to require a datetime parser. Producers emit
# `YYYY-MM-DDTHH:MM:SSZ` (or with fractional seconds before Z).
_ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)

# Reconciliation tolerance for totals.*: stages[].* may be small
# floats; sum drift up to 1e-6 (for cost_usd / elapsed_seconds) or
# zero for token-count integers is acceptable.
_FLOAT_TOTAL_TOLERANCE = 1e-6


def _is_int_nonneg(value: Any) -> bool:
    """True iff `value` is a non-negative int (not a float, not a bool)."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    )


def _is_float_nonneg(value: Any) -> bool:
    """True iff `value` is a non-negative number (int or float, not bool)."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value >= 0
    )


def _is_iso8601(value: Any) -> bool:
    return isinstance(value, str) and bool(_ISO8601_RE.match(value))


def _check_optional_str_or_null(
    value: Any, field: str, errors: list[str]
) -> None:
    """Most string-valued schema fields allow null (current_stage,
    mode, subrecord, …). Reject everything else."""
    if value is not None and not isinstance(value, str):
        errors.append(
            f"{field}: expected string or null; got {type(value).__name__}"
        )


def _validate_stage(
    stage: Any, idx: int, errors: list[str]
) -> None:
    """Validate one element of `stages[]` in place — append errors
    with the `stages[idx]` prefix so the caller can locate them."""
    prefix = f"stages[{idx}]"
    if not isinstance(stage, dict):
        errors.append(f"{prefix}: not a JSON object")
        return

    present = set(stage.keys())
    missing = _REQUIRED_STAGE_KEYS - present
    extra = present - _REQUIRED_STAGE_KEYS
    for key in sorted(missing):
        errors.append(f"{prefix}.{key}: missing required key")
    for key in sorted(extra):
        errors.append(
            f"{prefix}.{key}: unknown key; v1 schema is strict — bump "
            f"schema_version to extend"
        )
    if missing:
        return  # don't deref keys we already know are absent

    if not isinstance(stage["id"], str) or not stage["id"]:
        errors.append(f"{prefix}.id: must be a non-empty string")
    if stage["status"] not in STAGE_STATUSES:
        errors.append(
            f"{prefix}.status: must be one of {STAGE_STATUSES}; "
            f"got {stage['status']!r}"
        )
    _check_optional_str_or_null(stage["model"], f"{prefix}.model", errors)
    if not _is_iso8601(stage["started_at"]):
        errors.append(
            f"{prefix}.started_at: not an ISO-8601 UTC timestamp "
            f"(expected YYYY-MM-DDTHH:MM:SS[.fff]Z); "
            f"got {stage['started_at']!r}"
        )
    # finished_at: null iff status == "running", else ISO-8601.
    if stage["status"] == "running":
        if stage["finished_at"] is not None:
            errors.append(
                f"{prefix}.finished_at: must be null when status=running"
            )
    else:
        if not _is_iso8601(stage["finished_at"]):
            errors.append(
                f"{prefix}.finished_at: not an ISO-8601 UTC timestamp "
                f"(required when status != running); "
                f"got {stage['finished_at']!r}"
            )

    if not _is_float_nonneg(stage["elapsed_seconds"]):
        errors.append(
            f"{prefix}.elapsed_seconds: must be a non-negative number"
        )
    for f in _INT_COUNT_FIELDS:
        if not _is_int_nonneg(stage[f]):
            errors.append(
                f"{prefix}.{f}: must be a non-negative integer"
            )
    if not _is_float_nonneg(stage["cost_usd"]):
        errors.append(f"{prefix}.cost_usd: must be a non-negative number")
    _check_optional_str_or_null(
        stage["subrecord"], f"{prefix}.subrecord", errors,
    )


def _validate_totals(totals: Any, errors: list[str]) -> None:
    if not isinstance(totals, dict):
        errors.append("totals: not a JSON object")
        return
    present = set(totals.keys())
    missing = _REQUIRED_TOTALS_KEYS - present
    extra = present - _REQUIRED_TOTALS_KEYS
    for k in sorted(missing):
        errors.append(f"totals.{k}: missing required key")
    for k in sorted(extra):
        errors.append(
            f"totals.{k}: unknown key; v1 schema is strict"
        )
    if missing:
        return
    for f in _INT_COUNT_FIELDS:
        if not _is_int_nonneg(totals[f]):
            errors.append(
                f"totals.{f}: must be a non-negative integer"
            )
    for f in _FLOAT_FIELDS:
        if not _is_float_nonneg(totals[f]):
            errors.append(
                f"totals.{f}: must be a non-negative number"
            )


def _validate_artifacts(artifacts: Any, errors: list[str]) -> None:
    if not isinstance(artifacts, dict):
        errors.append("artifacts: not a JSON object")
        return
    present = set(artifacts.keys())
    missing = _REQUIRED_ARTIFACT_KEYS - present
    extra = present - _REQUIRED_ARTIFACT_KEYS
    for k in sorted(missing):
        errors.append(f"artifacts.{k}: missing required key")
    for k in sorted(extra):
        errors.append(
            f"artifacts.{k}: unknown key; v1 schema is strict"
        )
    if missing:
        return
    for k in _REQUIRED_ARTIFACT_KEYS:
        _check_optional_str_or_null(
            artifacts[k], f"artifacts.{k}", errors,
        )


def _check_totals_reconciliation(record: dict, errors: list[str]) -> None:
    """totals.* must equal sum(stages[].*) within tolerance — drift
    here is a real bug class (a producer that forgot to refresh totals
    after a stage append, or a reader that mutated stages but not
    totals)."""
    stages = record.get("stages")
    totals = record.get("totals")
    if not isinstance(stages, list) or not isinstance(totals, dict):
        return  # earlier checks will have flagged this
    # Skip reconciliation if any stage entry isn't a dict (other
    # errors handle that) or any required total key is missing.
    if any(not isinstance(s, dict) for s in stages):
        return
    if not _REQUIRED_TOTALS_KEYS.issubset(totals.keys()):
        return
    # Token counts: exact integer equality.
    for f in _INT_COUNT_FIELDS:
        try:
            stage_sum = sum(int(s[f]) for s in stages)
        except (KeyError, TypeError, ValueError):
            return  # malformed stage; defer to per-stage checks
        if totals[f] != stage_sum:
            errors.append(
                f"totals.{f} ({totals[f]}) != sum(stages[].{f}) "
                f"({stage_sum}) — producer must refresh totals on "
                f"every stage append/patch"
            )
    # Float fields: tolerance.
    for f in _FLOAT_FIELDS:
        try:
            stage_sum = sum(float(s[f]) for s in stages)
        except (KeyError, TypeError, ValueError):
            return
        if abs(float(totals[f]) - stage_sum) > _FLOAT_TOTAL_TOLERANCE:
            errors.append(
                f"totals.{f} ({totals[f]}) != sum(stages[].{f}) "
                f"({stage_sum}) — drift > {_FLOAT_TOTAL_TOLERANCE}"
            )


def _check_status_invariants(record: dict, errors: list[str]) -> None:
    """The status / finished_at / exit_code / current_stage quartet
    must be coherent. The canonical completion-signal rule (DP1):

        status ∈ {running, halted}     (non-terminal)
            ⇒ finished_at is None
            ⇒ exit_code   is None

        status ∈ {completed, failed}   (terminal)
            ⇒ finished_at is an ISO-8601 timestamp
            ⇒ exit_code   is int >= 0
            ⇒ current_stage is null
              (the run is over — no stage is "current")

        status == "halted"
            ⇒ current_stage MUST be non-null
              (it names the gate, e.g. "throughline_pick" — this is
              the arbitrator for the previously-ambiguous halt case:
              the gate name in the record makes the same handshake
              `.handoff.json` carries the user-facing prompt for)

        status == "running"
            ⇒ current_stage MAY be set (the one currently running)
              OR null (between stages — a presmaker `[Stage 11/14]`
              announce moment before the stage actually starts).
    """
    status = record.get("status")
    finished_at = record.get("finished_at")
    exit_code = record.get("exit_code")
    current_stage = record.get("current_stage")

    if status not in RUN_STATUSES:
        return  # earlier check flagged this

    if status in _NON_TERMINAL_STATUSES:
        # finished_at + exit_code must be null for BOTH running and
        # halted — neither is a completion signal.
        if finished_at is not None:
            errors.append(
                f"finished_at: must be null when status={status} "
                f"(non-terminal); got {finished_at!r}"
            )
        if exit_code is not None:
            errors.append(
                f"exit_code: must be null when status={status} "
                f"(non-terminal); got {exit_code!r}"
            )
        # halted-specific invariant: current_stage names the gate.
        if status == "halted" and current_stage is None:
            errors.append(
                "current_stage: must be non-null when status=halted "
                "(it names the halt-gate, e.g. 'throughline_pick'); "
                "got null"
            )
    else:
        # Terminal (completed / failed).
        if not _is_iso8601(finished_at):
            errors.append(
                "finished_at: not an ISO-8601 UTC timestamp "
                "(required when status is terminal)"
            )
        if not (isinstance(exit_code, int)
                and not isinstance(exit_code, bool)):
            errors.append(
                "exit_code: must be a non-negative integer when "
                "status is terminal"
            )
        elif exit_code < 0:
            errors.append(
                "exit_code: must be >= 0 (skills with rc=4 'unsafe' "
                "etc. still use non-negative exit codes)"
            )
        if current_stage is not None:
            errors.append(
                "current_stage: must be null when status is terminal "
                f"(got {current_stage!r}; the run is over — no stage "
                f"is 'current')"
            )

    # Optional hardening (Adam, 2026-06-07: fold-if-quick): timestamp
    # ordering. If both started_at and finished_at parse as ISO-8601,
    # finished_at MUST NOT be earlier than started_at. Cheap, pure
    # string comparison works because the ISO-8601 shape is
    # lexicographically sortable when normalized to the same suffix
    # (we accept `[.fff]?Z`; both ends use Z so the lex comparison is
    # correct within the same UTC encoding).
    started_at = record.get("started_at")
    if (_is_iso8601(started_at)
            and _is_iso8601(finished_at)
            and finished_at < started_at):
        errors.append(
            f"finished_at ({finished_at!r}) precedes started_at "
            f"({started_at!r}) — wall-clock cannot go backwards"
        )

    # Optional hardening: referential check on current_stage. When
    # non-null, current_stage MUST match one of stages[].id (otherwise
    # the gate name in the record points at nothing — chrome /
    # craft status would render a stage that doesn't exist).
    if current_stage is not None:
        stages = record.get("stages")
        if isinstance(stages, list):
            stage_ids = {
                s.get("id") for s in stages
                if isinstance(s, dict) and isinstance(s.get("id"), str)
            }
            if current_stage not in stage_ids:
                errors.append(
                    f"current_stage ({current_stage!r}) not found in "
                    f"stages[].id (have: {sorted(stage_ids)!r}). The "
                    f"halt-gate / running-stage name must reference an "
                    f"entry in stages[]."
                )


def validate_run_record(record: Any) -> list[str]:
    """Validate a parsed `run_record.json` against `run-record.v1`.

    Returns a list of human-readable error strings; empty list means
    the record is valid. Designed to never raise on user input — a
    `craft status` or Family E conformance test can dump the list
    directly.
    """
    errors: list[str] = []

    if not isinstance(record, dict):
        return [
            f"run_record root: expected JSON object; got "
            f"{type(record).__name__}"
        ]

    present = set(record.keys())
    missing = _REQUIRED_TOP_KEYS - present
    extra = present - _REQUIRED_TOP_KEYS
    for k in sorted(missing):
        errors.append(f"{k}: missing required top-level key")
    for k in sorted(extra):
        errors.append(
            f"{k}: unknown top-level key; v1 schema is strict — bump "
            f"schema_version to extend"
        )
    if missing:
        # Don't try further checks while top-level keys are missing —
        # they'd produce confusing cascade errors.
        return errors

    # Top-level scalars.
    if record["schema_version"] != SCHEMA_VERSION:
        errors.append(
            f"schema_version: expected {SCHEMA_VERSION!r}; "
            f"got {record['schema_version']!r}"
        )
    if record["skill"] not in SKILLS:
        errors.append(
            f"skill: must be one of {SKILLS}; got {record['skill']!r}"
        )
    if not isinstance(record["skill_version"], str) or not record["skill_version"]:
        errors.append("skill_version: must be a non-empty string")
    if not isinstance(record["run_id"], str) or not record["run_id"]:
        errors.append("run_id: must be a non-empty string")
    if not isinstance(record["draft_dir"], str) or not record["draft_dir"]:
        errors.append("draft_dir: must be a non-empty string")
    _check_optional_str_or_null(record["mode"], "mode", errors)
    if record["status"] not in RUN_STATUSES:
        errors.append(
            f"status: must be one of {RUN_STATUSES}; "
            f"got {record['status']!r}"
        )
    if not _is_iso8601(record["started_at"]):
        errors.append(
            f"started_at: not an ISO-8601 UTC timestamp; "
            f"got {record['started_at']!r}"
        )
    _check_optional_str_or_null(
        record["current_stage"], "current_stage", errors,
    )
    if not isinstance(record["models_used"], list):
        errors.append("models_used: must be a list of strings")
    else:
        for i, m in enumerate(record["models_used"]):
            if not isinstance(m, str):
                errors.append(
                    f"models_used[{i}]: must be a string; "
                    f"got {type(m).__name__}"
                )

    # Stages array.
    if not isinstance(record["stages"], list):
        errors.append("stages: must be a list")
    else:
        for i, stage in enumerate(record["stages"]):
            _validate_stage(stage, i, errors)

    # Totals + artifacts.
    _validate_totals(record["totals"], errors)
    _validate_artifacts(record["artifacts"], errors)

    # Cross-field invariants — only run when the per-key checks
    # already passed enough to make the cross-checks meaningful.
    _check_status_invariants(record, errors)
    _check_totals_reconciliation(record, errors)

    return errors
