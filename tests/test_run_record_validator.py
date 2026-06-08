"""Unit tests for craft.run_record.validate_run_record.

Locks the `run-record.v1` contract shape with a small set of platform-
owned goldens + negative-case fixtures. Per-skill goldens (one
`running` + one `completed` per skill) land in their respective
tests/fixtures/ trees during Steps 2/4/5 of Cycle 3; Family E in
`test_conformance.py` discovers them.

The validator is a pure function: `validate_run_record(record: dict)
-> list[str]`. Empty list = valid; otherwise human-readable error
strings (the test asserts substring matches, not list equality, so a
later message refinement doesn't crack the suite).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from craft.run_record import validate_run_record

# ---------------------------------------------------------------------------
# Fixtures — platform-owned goldens cover the three skills + statuses
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "run_record_v1"

# Map of (label → file path). Used by parametrize to enumerate goldens.
_PLATFORM_GOLDENS = {
    "presmaker_running":         "presentation_maker_running.json",
    "presmaker_halted":          "presentation_maker_halted.json",
    "presmaker_completed":       "presentation_maker_completed.json",
    "paper_writer_completed":    "paper_writer_completed.json",
    "paper_writer_failed":       "paper_writer_failed.json",
    "adversarial_standalone":    "adversarial_standalone_completed.json",
}


def _load(filename: str) -> dict:
    return json.loads((_FIXTURE_DIR / filename).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Positive tests — every platform-owned golden validates clean
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,filename",
    list(_PLATFORM_GOLDENS.items()),
    ids=list(_PLATFORM_GOLDENS.keys()),
)
def test_platform_golden_validates_clean(label, filename):
    """Every shipped golden must pass validation with no errors. Each
    one exercises a different facet of the schema (skill + status
    combination); together they're the load-bearing positive
    coverage."""
    record = _load(filename)
    errors = validate_run_record(record)
    assert errors == [], (
        f"golden {label} ({filename}) should validate clean; "
        f"got {len(errors)} error(s):\n  " + "\n  ".join(errors)
    )


# ---------------------------------------------------------------------------
# Negative tests — each schema rule has a dedicated fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def good_record():
    """A known-clean record we mutate per test to provoke specific
    error classes without re-spelling the full schema in each test."""
    return _load("presentation_maker_completed.json")


def test_not_dict_returns_error():
    errors = validate_run_record([])
    assert any("expected JSON object" in e for e in errors)


def test_unknown_top_key_is_strict(good_record):
    good_record["extra_field"] = "should be rejected"
    errors = validate_run_record(good_record)
    assert any("extra_field" in e and "unknown" in e for e in errors)


def test_missing_top_key_reported(good_record):
    del good_record["status"]
    errors = validate_run_record(good_record)
    assert any("status" in e and "missing" in e for e in errors)


def test_wrong_schema_version(good_record):
    good_record["schema_version"] = "run-record.v2"
    errors = validate_run_record(good_record)
    assert any("schema_version" in e for e in errors)


def test_invalid_skill(good_record):
    good_record["skill"] = "atlas"
    errors = validate_run_record(good_record)
    assert any("skill" in e and "must be one of" in e for e in errors)


def test_invalid_status(good_record):
    good_record["status"] = "in-progress"
    errors = validate_run_record(good_record)
    assert any("status" in e and "must be one of" in e for e in errors)


def test_running_must_have_null_finished_at(good_record):
    good_record["status"] = "running"
    good_record["finished_at"] = good_record["started_at"]
    good_record["exit_code"] = None
    good_record["current_stage"] = "slide_compose"
    errors = validate_run_record(good_record)
    assert any(
        "finished_at" in e and "must be null when status=running" in e
        for e in errors
    )


def test_running_must_have_null_exit_code(good_record):
    good_record["status"] = "running"
    good_record["finished_at"] = None
    good_record["exit_code"] = 0
    good_record["current_stage"] = "slide_compose"
    errors = validate_run_record(good_record)
    assert any(
        "exit_code" in e and "must be null when status=running" in e
        for e in errors
    )


def test_terminal_must_set_finished_at(good_record):
    good_record["status"] = "completed"
    good_record["finished_at"] = None
    good_record["exit_code"] = 0
    errors = validate_run_record(good_record)
    assert any(
        "finished_at" in e
        and ("required when status is terminal" in e
             or "ISO-8601" in e)
        for e in errors
    )


def test_terminal_must_have_null_current_stage(good_record):
    good_record["status"] = "completed"
    good_record["current_stage"] = "still-doing-something"
    errors = validate_run_record(good_record)
    assert any(
        "current_stage" in e and "must be null when status is terminal" in e
        for e in errors
    )


def test_bad_iso8601_started_at(good_record):
    good_record["started_at"] = "2026-06-07 18:00:00"  # space instead of T
    errors = validate_run_record(good_record)
    assert any(
        "started_at" in e and "ISO-8601" in e for e in errors
    )


def test_negative_cost_is_invalid(good_record):
    good_record["totals"]["cost_usd"] = -0.01
    errors = validate_run_record(good_record)
    assert any("cost_usd" in e for e in errors)


def test_bool_not_accepted_for_int_count(good_record):
    """Tokens are ints but bool is a subclass of int — we explicitly
    reject it (telemetry projectors want a number, not True/False)."""
    good_record["stages"][0]["input_tokens"] = True
    good_record["totals"]["input_tokens"] = 1
    errors = validate_run_record(good_record)
    assert any("input_tokens" in e for e in errors)


def test_totals_token_count_mismatch_reported(good_record):
    """Whole point of totals reconciliation: if the producer forgot
    to refresh totals after a stage append, this catches it."""
    good_record["totals"]["input_tokens"] = 999999  # drift from sum
    errors = validate_run_record(good_record)
    assert any(
        "totals.input_tokens" in e and "sum(stages" in e for e in errors
    )


def test_totals_cost_drift_within_tolerance_is_ok(good_record):
    """A sub-microcent rounding drift is acceptable — producers do
    float arithmetic and we can't demand bit-exact equality."""
    # Nudge the sum by less than the tolerance (1e-6).
    good_record["totals"]["cost_usd"] = good_record["totals"]["cost_usd"] + 1e-9
    errors = validate_run_record(good_record)
    # Should still validate clean.
    assert errors == [], errors


def test_totals_cost_drift_outside_tolerance_is_caught(good_record):
    good_record["totals"]["cost_usd"] = good_record["totals"]["cost_usd"] + 0.5
    errors = validate_run_record(good_record)
    assert any(
        "totals.cost_usd" in e and "drift" in e for e in errors
    )


def test_stage_with_unknown_key_rejected(good_record):
    good_record["stages"][0]["surprise_field"] = "no"
    errors = validate_run_record(good_record)
    assert any(
        "stages[0].surprise_field" in e and "unknown" in e for e in errors
    )


def test_stage_running_must_have_null_finished_at(good_record):
    # The presmaker running golden already exercises this; here we
    # negative-test by forcing a terminal-style finished_at onto a
    # running stage in the otherwise-clean completed record.
    good_record["stages"][0]["status"] = "running"
    # Leave finished_at as the existing terminal timestamp.
    errors = validate_run_record(good_record)
    assert any(
        "stages[0].finished_at" in e and "must be null when status=running"
        in e for e in errors
    )


def test_stage_status_skipped_is_allowed(good_record):
    """A skipped stage is a legitimate run-record entry (presmaker
    skips stages when `--resume-from <later>` is set). It needs a
    started_at + finished_at like any non-running stage."""
    good_record["stages"][0]["status"] = "skipped"
    # Existing started_at + finished_at remain valid.
    errors = validate_run_record(good_record)
    assert errors == [], errors


def test_subrecord_is_optional_string_or_null(good_record):
    good_record["stages"][0]["subrecord"] = 42  # not str or null
    errors = validate_run_record(good_record)
    assert any("subrecord" in e for e in errors)


def test_artifacts_extra_key_rejected(good_record):
    good_record["artifacts"]["wat"] = "no"
    errors = validate_run_record(good_record)
    assert any(
        "artifacts.wat" in e and "unknown" in e for e in errors
    )


def test_artifacts_missing_key_rejected(good_record):
    del good_record["artifacts"]["deliverable"]
    errors = validate_run_record(good_record)
    assert any(
        "artifacts.deliverable" in e and "missing" in e for e in errors
    )


# ---------------------------------------------------------------------------
# halted-status invariants (Step-1 amend, Adam 2026-06-07)
# ---------------------------------------------------------------------------


@pytest.fixture
def halted_record():
    """A clean halted record (parallel to good_record's completed)."""
    return _load("presentation_maker_halted.json")


def test_halted_golden_validates_clean(halted_record):
    """The halted golden parses + validates with no errors."""
    assert validate_run_record(halted_record) == []


def test_halted_status_is_in_vocab():
    """RUN_STATUSES must contain `halted` — pins the vocab so a future
    accidental rename of the constant trips this test before tests that
    indirectly depend on it."""
    from craft.run_record import RUN_STATUSES
    assert "halted" in RUN_STATUSES


def test_halted_requires_non_null_current_stage(halted_record):
    """The arbitrator rule: status=halted ⇒ current_stage names the
    gate. If current_stage is null the halt has nowhere to point — a
    halt-without-a-gate is the bug DP1's split-signal class produces."""
    halted_record["current_stage"] = None
    errors = validate_run_record(halted_record)
    assert any(
        "current_stage" in e and "must be non-null when status=halted" in e
        for e in errors
    )


def test_halted_must_have_null_finished_at(halted_record):
    """halted is non-terminal — finished_at would be a contradiction."""
    halted_record["finished_at"] = "2026-06-07T19:30:00Z"
    errors = validate_run_record(halted_record)
    assert any(
        "finished_at" in e and "must be null when status=halted" in e
        for e in errors
    )


def test_halted_must_have_null_exit_code(halted_record):
    """halted is non-terminal — exit_code would be a contradiction."""
    halted_record["exit_code"] = 0
    errors = validate_run_record(halted_record)
    assert any(
        "exit_code" in e and "must be null when status=halted" in e
        for e in errors
    )


def test_halted_with_unreferenced_current_stage_caught(halted_record):
    """current_stage names a gate that doesn't appear in stages[].id —
    the referential check catches this (otherwise craft status renders
    a phantom gate name)."""
    halted_record["current_stage"] = "no_such_gate"
    errors = validate_run_record(halted_record)
    assert any(
        "current_stage" in e and "not found in stages[].id" in e
        for e in errors
    )


def test_running_with_unreferenced_current_stage_caught(good_record):
    """Same referential check on a running record (not halt-specific —
    the rule applies whenever current_stage is non-null)."""
    good_record["status"] = "running"
    good_record["finished_at"] = None
    good_record["exit_code"] = None
    good_record["current_stage"] = "ghost_stage"
    errors = validate_run_record(good_record)
    assert any(
        "current_stage" in e and "not found in stages[].id" in e
        for e in errors
    )


def test_running_with_null_current_stage_is_ok(good_record):
    """running + current_stage=null is legitimate (between stages /
    pre-first-stage). The halt rule does NOT apply to running."""
    good_record["status"] = "running"
    good_record["finished_at"] = None
    good_record["exit_code"] = None
    good_record["current_stage"] = None
    errors = validate_run_record(good_record)
    # No halt-style error about null current_stage.
    assert not any(
        "must be non-null when status=halted" in e for e in errors
    )


# ---------------------------------------------------------------------------
# Optional hardening: wall-clock ordering + referential current_stage
# (Adam 2026-06-07 "fold-if-quick" — folded in)
# ---------------------------------------------------------------------------


def test_finished_at_before_started_at_caught(good_record):
    """A finalize that wrote finished_at < started_at is broken
    arithmetic. Cheap pure-string compare on the ISO-8601 shape works
    because both ends carry the Z suffix."""
    good_record["started_at"] = "2026-06-07T18:00:00Z"
    good_record["finished_at"] = "2026-06-07T17:00:00Z"  # 1h earlier
    errors = validate_run_record(good_record)
    assert any(
        "finished_at" in e and "precedes started_at" in e for e in errors
    )


def test_finished_at_equal_to_started_at_is_ok(good_record):
    """An instantaneous run (started == finished) is allowed —
    timestamp resolution is per-second, so any sub-second run rounds
    to equal. The strict-less check (`<`) correctly accepts this."""
    good_record["started_at"] = "2026-06-07T18:00:00Z"
    good_record["finished_at"] = "2026-06-07T18:00:00Z"
    errors = validate_run_record(good_record)
    # The timestamp-ordering check should NOT fire (other rules may).
    assert not any("precedes started_at" in e for e in errors)


def test_validator_never_raises_on_arbitrary_input():
    """The function must be safe to call on any user input — it's
    used by `craft status`, which must never traceback on a
    malformed record."""
    for bad in [None, 42, "string", [], {"junk": "garbage"}]:
        result = validate_run_record(bad)
        assert isinstance(result, list)
        assert all(isinstance(e, str) for e in result)


def test_validator_returns_only_strings(good_record):
    """Output discipline check — every element of the returned list
    is a human-readable string the validator's caller can dump
    verbatim."""
    good_record["status"] = "bogus"
    errors = validate_run_record(good_record)
    for e in errors:
        assert isinstance(e, str)
        assert e  # non-empty


# ---------------------------------------------------------------------------
# Deep-copy isolation — every test gets a fresh `good_record` because
# we mutate it in-place. (pytest already does this via the fixture
# function call, but we sanity-check by validating an unmodified copy
# of the source golden.)
# ---------------------------------------------------------------------------


def test_source_golden_is_unmutated_after_other_tests(good_record):
    """If any of the negative tests above accidentally mutated a
    module-level dict, this test would fail. Sanity guard."""
    pristine = _load("presentation_maker_completed.json")
    # `good_record` is built from the same file, so it should match
    # the pristine copy when the fixture was just instantiated.
    assert good_record == pristine, (
        "The good_record fixture has drifted from the on-disk "
        "golden — a test is mutating module-level state."
    )
    # Also: deep-copy the pristine + validate to belt-and-suspenders.
    assert validate_run_record(copy.deepcopy(pristine)) == []
