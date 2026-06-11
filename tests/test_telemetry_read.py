"""C1 Workstream D — telemetry read surface: union + summarize + render +
the `craft inspect telemetry` CLI.

Mirrors narrative-connector's read tests, with CRAFT's perf axis being COST
(p50/p95 cost per stage) rather than rows/bytes. Hermetic — builds a synthetic
`<root>/telemetry/craft/**` tree and asserts the union/summary/render.
"""
from __future__ import annotations

import json

from craft import cli
from craft.telemetry import read as tr


def _write_sink(root, *, user, month, batch, records):
    d = root / "telemetry" / "craft" / user / month
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{batch}.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
        encoding="utf-8")


def _stage(op, cost, dur_ms, *, run_id, draft_hash, user="aparkin",
           status="completed", **kw):
    r = {
        "op": op, "cost_usd": cost, "duration_ms": dur_ms, "status": status,
        "run_id": run_id, "draft_hash": draft_hash, "user": user,
        "skill": "presentation-maker", "model": "sonnet",
        "input_tokens": 100, "output_tokens": 50,
        "ts": 1_700_000_000.0,
    }
    r.update(kw)
    return r


def _run_rec(cost, *, run_id, draft_hash, user="aparkin", ts=1_700_000_100.0):
    return {
        "kind": "run_finalize", "status": "completed", "cost_usd": cost,
        "run_id": run_id, "draft_hash": draft_hash, "user": user,
        "duration_ms": 60000.0, "ts": ts, "skill": "presentation-maker",
    }


# ---------------------------------------------------------------------------
# union + summarize
# ---------------------------------------------------------------------------

def test_union_globs_all_users_and_months(tmp_path):
    _write_sink(tmp_path, user="alice", month="2026-06", batch="run-1",
                records=[_stage("plan", 0.2, 1000, run_id="run-1",
                                draft_hash="aaaa", user="alice")])
    _write_sink(tmp_path, user="bob", month="2026-05", batch="run-1",
                records=[_stage("plan", 0.3, 1100, run_id="run-1",
                                draft_hash="bbbb", user="bob")])
    rows = tr.union_telemetry(str(tmp_path))
    assert len(rows) == 2
    assert {r["user"] for r in rows} == {"alice", "bob"}


def test_union_skips_torn_lines(tmp_path):
    d = tmp_path / "telemetry" / "craft" / "u" / "2026-06"
    d.mkdir(parents=True)
    (d / "run-1.jsonl").write_text(
        json.dumps(_stage("plan", 0.2, 1000, run_id="run-1",
                          draft_hash="aaaa")) + "\n"
        + '{"op": "broken", "cost_usd":\n'   # torn line
        + json.dumps(_stage("merge", 0.0, 50, run_id="run-1",
                            draft_hash="aaaa")) + "\n",
        encoding="utf-8")
    rows = tr.union_telemetry(str(tmp_path))
    assert len(rows) == 2  # torn line skipped, two good rows kept
    assert {r["op"] for r in rows} == {"plan", "merge"}


def test_summarize_reports_per_stage_cost_percentiles(tmp_path):
    # three slide_compose stages with costs 0.10, 0.50, 0.90
    recs = [
        _stage("slide_compose", 0.10, 1000, run_id="run-1", draft_hash="a"),
        _stage("slide_compose", 0.50, 2000, run_id="run-2", draft_hash="a"),
        _stage("slide_compose", 0.90, 3000, run_id="run-3", draft_hash="a"),
    ]
    _write_sink(tmp_path, user="aparkin", month="2026-06", batch="b",
                records=recs)
    summary = tr.summarize(tr.union_telemetry(str(tmp_path)))
    sc = summary["by_op"]["slide_compose"]
    assert sc["count"] == 3
    assert sc["p50_usd"] == 0.50          # nearest-rank median
    assert sc["p95_usd"] == 0.90
    assert abs(sc["total_usd"] - 1.50) < 1e-9
    assert sc["p50_ms"] == 2000.0
    assert sc["input_tokens"] == 300      # 3 × 100


def test_summarize_reconstructs_drafts_with_cost(tmp_path):
    # one draft (hash "a"), two runs, each with a run_finalize cost
    recs = [
        _stage("plan", 0.2, 1000, run_id="run-1", draft_hash="a"),
        _run_rec(0.20, run_id="run-1", draft_hash="a", ts=100.0),
        _stage("plan", 0.3, 1100, run_id="run-2", draft_hash="a"),
        _run_rec(0.30, run_id="run-2", draft_hash="a", ts=200.0),
    ]
    _write_sink(tmp_path, user="aparkin", month="2026-06", batch="b",
                records=recs)
    summary = tr.summarize(tr.union_telemetry(str(tmp_path)))
    drafts = summary["drafts"]
    assert len(drafts) == 1
    key = "a:aparkin"
    d = drafts[key]
    assert d["n_runs"] == 2
    assert abs(d["cost_usd"] - 0.50) < 1e-9       # run-level costs summed
    assert d["run_order"] == ["run-1", "run-2"]   # ts-sorted timeline


def test_summarize_error_classes_empty_until_populated(tmp_path):
    _write_sink(tmp_path, user="u", month="2026-06", batch="b",
                records=[_stage("plan", 0.2, 1000, run_id="run-1",
                                draft_hash="a")])
    summary = tr.summarize(tr.union_telemetry(str(tmp_path)))
    assert summary["error_classes"] == {}     # reserved field, unpopulated
    # but a record that DID carry one is summarized.
    _write_sink(tmp_path, user="u", month="2026-07", batch="b2",
                records=[_stage("merge", 0.0, 5, run_id="run-2",
                                draft_hash="a", error_class="ToolTimeout")])
    summary2 = tr.summarize(tr.union_telemetry(str(tmp_path)))
    assert summary2["error_classes"]["ToolTimeout"]["count"] == 1


def test_summarize_empty_root(tmp_path):
    summary = tr.summarize(tr.union_telemetry(str(tmp_path)))
    assert summary["total"] == 0 and summary["by_op"] == {}


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def test_render_text_shows_cost_axis(tmp_path):
    recs = [_stage("plan", 0.20, 1000, run_id="run-1", draft_hash="abcd1234"),
            _run_rec(0.20, run_id="run-1", draft_hash="abcd1234")]
    _write_sink(tmp_path, user="aparkin", month="2026-06", batch="b",
                records=recs)
    summary = tr.summarize(tr.union_telemetry(str(tmp_path)))
    text = tr.render_text(summary)
    assert "craft telemetry" in text
    assert "p50=$0.2000" in text          # the cost axis, not rows/bytes
    assert "plan" in text
    assert "abcd1234" in text             # the opaque draft hash
    assert "aparkin" in text


# ---------------------------------------------------------------------------
# `craft inspect telemetry` CLI
# ---------------------------------------------------------------------------

def test_cli_inspect_telemetry_text(tmp_path, capsys):
    _write_sink(tmp_path, user="aparkin", month="2026-06", batch="run-1",
                records=[_stage("plan", 0.2, 1000, run_id="run-1",
                                draft_hash="abcd"),
                         _run_rec(0.2, run_id="run-1", draft_hash="abcd")])
    rc = cli.main(["inspect", "telemetry", "--root", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "craft telemetry" in out and "plan" in out


def test_cli_inspect_telemetry_json_shape(tmp_path, capsys):
    _write_sink(tmp_path, user="aparkin", month="2026-06", batch="run-1",
                records=[_stage("plan", 0.2, 1000, run_id="run-1",
                                draft_hash="abcd")])
    rc = cli.main(["inspect", "telemetry", "--root", str(tmp_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) >= {"total", "users", "by_op", "error_classes",
                            "status", "runs", "drafts"}
    assert payload["total"] == 1


def test_cli_inspect_telemetry_disabled_no_root(monkeypatch, capsys):
    from craft.telemetry import egress as txe
    monkeypatch.setenv(txe.TELEMETRY_ROOT_ENV, "off")
    rc = cli.main(["inspect", "telemetry"])
    assert rc == 2
    assert "disabled" in capsys.readouterr().err.lower()
