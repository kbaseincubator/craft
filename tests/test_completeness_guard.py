"""Tests for craft.run_record.check_no_dropped_stages (C1-A2).

The cross-record completeness guard: a resume must never lose a stage a
prior run completed. The canonical's `completed` stage-id set MUST be a
superset of every archived run's `completed` set. This is the invariant
the per-record schema validator can't see (it only reconciles
totals==sum(present)), and it directly targets the C1-A drop (a
`--resume-from` after failure that opened a fresh empty run and lost the
already-completed substory_design/curate_figures).

These are pure-function tests over hand-built minimal records — no
fixtures, no I/O.
"""
from __future__ import annotations

from craft.run_record import check_no_dropped_stages


def _stage(sid: str, status: str = "completed") -> dict:
    return {"id": sid, "status": status}


def _rec(run_id: str, stage_ids, *, status="completed",
         running=()) -> dict:
    stages = [_stage(s) for s in stage_ids]
    stages += [_stage(s, "running") for s in running]
    return {"run_id": run_id, "status": status, "stages": stages}


# ---------------------------------------------------------------------------
# Green: canonical is a superset → no errors
# ---------------------------------------------------------------------------

def test_complete_canonical_passes():
    canonical = _rec("run-1", ["plan", "substory_design", "curate_figures",
                               "qa_prep", "merge"])
    archive = _rec("run-1", ["plan", "substory_design", "curate_figures"])
    assert check_no_dropped_stages(canonical, [archive]) == []


def test_self_snapshot_skipped():
    """The canonical's own archived snapshot (same run_id) is skipped —
    it can't drop its own stages."""
    canonical = _rec("run-1", ["plan", "substory_design"])
    # an identical-run_id archive (the no-clobber snapshot of the same
    # accumulating record) must not trip the guard.
    assert check_no_dropped_stages(canonical, [dict(canonical)]) == []


def test_no_archives_passes():
    canonical = _rec("run-1", ["plan", "merge"])
    assert check_no_dropped_stages(canonical, []) == []


def test_running_stage_in_archive_not_required():
    """Only COMPLETED archived stages must be carried; a stage the prior
    run left `running` (it failed/was interrupted there) is not a drop."""
    canonical = _rec("run-1", ["plan", "substory_design", "qa_prep"])
    archive = _rec("run-1", ["plan", "substory_design"], status="failed",
                   running=["qa_prep"])  # qa_prep was running, not completed
    assert check_no_dropped_stages(canonical, [archive]) == []


# ---------------------------------------------------------------------------
# Red: a dropped completed stage → errors (the C1-A failure mode)
# ---------------------------------------------------------------------------

def test_dropped_stage_is_flagged():
    """The exact C1-A defect: a fresh canonical that lost substory_design
    + curate_figures which a prior (failed) run completed."""
    # prior run completed plan + substory_design + curate_figures, then died
    archive = _rec("run-1", ["plan", "substory_design", "curate_figures"],
                   status="failed")
    # the (buggy) fresh canonical only has the post-resume stages
    canonical = _rec("run-2", ["qa_prep", "merge"])
    errors = check_no_dropped_stages(canonical, [archive])
    assert len(errors) == 1
    msg = errors[0]
    assert "substory_design" in msg and "curate_figures" in msg
    assert "run-2" in msg and "run-1" in msg
    assert "must never drop a completed stage" in msg


def test_multiple_archives_each_checked():
    a1 = _rec("run-1", ["plan", "substory_design"], status="failed")
    a2 = _rec("run-2", ["plan", "substory_design", "curate_figures"],
              status="failed")
    canonical = _rec("run-3", ["plan", "qa_prep"])  # drops substory + curate
    errors = check_no_dropped_stages(canonical, [a1, a2])
    # both archives flag the drop
    assert len(errors) == 2
    joined = "\n".join(errors)
    assert "substory_design" in joined and "curate_figures" in joined


# ---------------------------------------------------------------------------
# Robustness: tolerant of malformed inputs (defense-in-depth, never raises)
# ---------------------------------------------------------------------------

def test_malformed_inputs_do_not_raise():
    assert check_no_dropped_stages({}, []) == []
    assert check_no_dropped_stages({"stages": "nope"}, [{"stages": None}]) == []
    # a non-dict archive entry is ignored, not a crash
    assert check_no_dropped_stages(_rec("run-1", ["plan"]), [None, 42]) == []
