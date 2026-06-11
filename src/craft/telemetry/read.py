"""CRAFT telemetry read surface (C1 Workstream D) — the dev-team payoff.

Unions the per-user, per-month telemetry files written by :mod:`craft.telemetry.
egress` and summarizes them into the "which draft cost what, when" view C2's
cost model consumes. A near-verbatim port of narrative-connector's
`telemetry_read.py`, with CRAFT's perf axis being **cost** (+ tokens +
duration) rather than rows/bytes.

Reads a filesystem-prefix ``<root>`` (the dev/mounted prefix). The
union/summarize split is structured so an ``s3a://`` list-and-download path can
drop in later behind :func:`union_telemetry` without changing the summary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def union_telemetry(root: str, *, read_lines=None) -> list[dict]:
    """Union every telemetry record under ``<root>/telemetry/craft/**/*.jsonl``
    (all users, all months) into one flat list of row dicts, in filename-sorted
    (stable, roughly chronological by month-partition) order.

    ``read_lines`` is injectable for hermetic tests / a future s3a lister.
    Best-effort per file: a torn JSON line is skipped, a bad file is skipped —
    never raises on a partial sink."""
    rows: list[dict] = []
    if read_lines is None:
        read_lines = _fs_read_lines
    for _path, lines in read_lines(root):
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # torn/partial append — skip, don't fail
            if isinstance(rec, dict):
                rows.append(rec)
    return rows


def _fs_read_lines(root: str):
    """Default reader: glob ``<root>/telemetry/craft/**/*.jsonl`` on the local
    filesystem, sorted by path (stable union order)."""
    base = Path(root) / "telemetry" / "craft"
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*.jsonl")):
        try:
            yield path, path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue  # unreadable file — skip


def _percentile(sorted_vals: list[float], q: float) -> float:
    """The q-th percentile (0..1) via nearest-rank on a pre-sorted list.
    Returns 0.0 for an empty list. Deterministic — no numpy dependency."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    import math
    rank = max(1, math.ceil(q * len(sorted_vals)))
    idx = min(rank - 1, len(sorted_vals) - 1)
    return float(sorted_vals[idx])


def reconstruct_runs(rows: list[dict]) -> dict[str, Any]:
    """Stitch the opaque correlation keys into run / draft structure (NO
    semantic names — everything keys on ``run_id``/``draft_hash``):

      - **runs** — rows grouped by ``run_id``: ``{run_id -> {first_ts, last_ts,
        ops, draft_hash, user, cost_usd}}``. ``first_ts`` orders the timeline.
      - **drafts** — runs grouped by ``(draft_hash, user)`` (per-user-draft; a
        bare ``draft_hash`` across users is the same draft SHAPE): ``{key ->
        {draft_hash, user, run_order (ts-sorted run ids), n_runs, cost_usd}}``.

    CRAFT has no ``depends_on`` DAG yet, so there are NO edges (the brief omits
    them). Pure (no IO). Rows with no ``run_id`` are skipped."""
    runs: dict[str, dict[str, Any]] = {}
    for r in rows:
        rid = r.get("run_id")
        if not rid:
            continue
        ts = r.get("ts")
        run = runs.setdefault(rid, {
            "run_id": rid, "first_ts": ts, "last_ts": ts, "ops": set(),
            "draft_hash": None, "user": None, "cost_usd": 0.0,
        })
        if isinstance(ts, (int, float)):
            if run["first_ts"] is None or ts < run["first_ts"]:
                run["first_ts"] = ts
            if run["last_ts"] is None or ts > run["last_ts"]:
                run["last_ts"] = ts
        op = r.get("op")
        if op:
            run["ops"].add(op)
        if r.get("draft_hash"):
            run["draft_hash"] = r["draft_hash"]
        if r.get("user"):
            run["user"] = r["user"]
        # Sum the run-level finalize cost into the run (per-stage costs would
        # double-count against the run_finalize total; count only that kind).
        if r.get("kind") == "run_finalize":
            c = r.get("cost_usd")
            if isinstance(c, (int, float)):
                run["cost_usd"] += float(c)

    drafts: dict[str, dict[str, Any]] = {}
    for rid, run in runs.items():
        dh = run["draft_hash"]
        if not dh:
            continue
        key = f"{dh}:{run['user'] or '?'}"
        draft = drafts.setdefault(key, {
            "draft_hash": dh, "user": run["user"], "run_ids": [],
            "cost_usd": 0.0,
        })
        draft["run_ids"].append(rid)
        draft["cost_usd"] += run["cost_usd"]

    for draft in drafts.values():
        draft["run_order"] = sorted(
            draft["run_ids"],
            key=lambda x: (runs[x]["first_ts"] is None,
                           runs[x]["first_ts"] or 0))
        draft["n_runs"] = len(draft["run_ids"])
        del draft["run_ids"]

    runs_out = {
        rid: {
            "run_id": rid, "first_ts": run["first_ts"],
            "last_ts": run["last_ts"], "ops": sorted(run["ops"]),
            "draft_hash": run["draft_hash"], "user": run["user"],
            "cost_usd": run["cost_usd"],
        }
        for rid, run in runs.items()
    }
    return {"runs": runs_out, "drafts": drafts}


def summarize(rows: list[dict]) -> dict[str, Any]:
    """Aggregate unioned telemetry rows into the dev-team view:

      - ``total`` — record count;
      - ``users`` — distinct attributed users;
      - ``by_op`` — per ``op`` (stage): ``count``, **``p50_usd``/``p95_usd``**
        (the CRAFT cost axis), ``p50_ms``/``p95_ms`` (duration), and token sums;
      - ``error_classes`` — per ``error_class`` token: count + rate
        (empty-until-populated — ``error_class`` is reserved on the run-record);
      - ``status`` — per status token: count;
      - ``runs`` / ``drafts`` — the correlation reconstruction
        (:func:`reconstruct_runs`): rows grouped into runs (``run_id``) and runs
        into per-user-drafts (``draft_hash`` × ``user``) with each draft's
        ts-ordered run timeline + total cost.

    Pure (no IO); rows missing a perf field are simply not counted toward that
    statistic."""
    total = len(rows)
    by_op: dict[str, dict[str, Any]] = {}
    costs: dict[str, list[float]] = {}
    durations: dict[str, list[float]] = {}
    users: set[str] = set()
    error_classes: dict[str, int] = {}
    status_counts: dict[str, int] = {}

    for r in rows:
        u = r.get("user")
        if u:
            users.add(u)
        op = r.get("op") or "(none)"
        slot = by_op.setdefault(op, {
            "count": 0, "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_creation_tokens": 0,
        })
        slot["count"] += 1
        for tok in ("input_tokens", "output_tokens",
                    "cache_read_tokens", "cache_creation_tokens"):
            v = r.get(tok)
            if isinstance(v, (int, float)):
                slot[tok] += v
        c = r.get("cost_usd")
        if isinstance(c, (int, float)):
            costs.setdefault(op, []).append(float(c))
        dm = r.get("duration_ms")
        if isinstance(dm, (int, float)):
            durations.setdefault(op, []).append(float(dm))
        ec = r.get("error_class")
        if ec:
            error_classes[ec] = error_classes.get(ec, 0) + 1
        st = r.get("status")
        if st:
            status_counts[st] = status_counts.get(st, 0) + 1

    for op, slot in by_op.items():
        cs = sorted(costs.get(op, []))
        slot["p50_usd"] = _percentile(cs, 0.50)
        slot["p95_usd"] = _percentile(cs, 0.95)
        slot["total_usd"] = sum(cs)
        slot["n_costed"] = len(cs)
        ds = sorted(durations.get(op, []))
        slot["p50_ms"] = _percentile(ds, 0.50)
        slot["p95_ms"] = _percentile(ds, 0.95)
        slot["n_timed"] = len(ds)

    error_rates = {
        ec: {"count": n, "rate": (n / total if total else 0.0)}
        for ec, n in error_classes.items()
    }

    correlation = reconstruct_runs(rows)
    return {
        "total": total,
        "users": sorted(users),
        "by_op": by_op,
        "error_classes": error_rates,
        "status": status_counts,
        "runs": correlation["runs"],
        "drafts": correlation["drafts"],
    }


def render_text(summary: dict[str, Any]) -> str:
    """A compact human view of :func:`summarize` (the ``inspect telemetry``
    default render). The ``--json`` path emits the raw summary instead."""
    lines = [
        "# craft telemetry — usage + cost",
        f"records: {summary['total']}  ·  users: {len(summary['users'])} "
        f"({', '.join(summary['users']) or '—'})",
        "",
        "## per-stage (p50 / p95 cost, duration, token sums)",
    ]
    by_op = summary.get("by_op", {})
    if not by_op:
        lines.append("  (no records)")
    for op in sorted(by_op):
        s = by_op[op]
        lines.append(
            f"  {op}: n={s['count']}  "
            f"p50=${s.get('p50_usd', 0):.4f}  p95=${s.get('p95_usd', 0):.4f}  "
            f"total=${s.get('total_usd', 0):.2f}  "
            f"p50={s.get('p50_ms', 0):.0f}ms  p95={s.get('p95_ms', 0):.0f}ms  "
            f"in={s.get('input_tokens', 0)}  out={s.get('output_tokens', 0)}"
        )
    lines.append("")
    lines.append("## status counts")
    st = summary.get("status", {})
    if not st:
        lines.append("  (none)")
    for s in sorted(st):
        lines.append(f"  {s}: {st[s]}")
    lines.append("")
    lines.append("## error classes (rate over all records)")
    ecs = summary.get("error_classes", {})
    if not ecs:
        lines.append("  (none — error_class is reserved until a per-stage "
                     "failure taxonomy is recorded)")
    for ec in sorted(ecs):
        e = ecs[ec]
        lines.append(f"  {ec}: {e['count']}  ({e['rate'] * 100:.1f}%)")

    drafts = summary.get("drafts", {})
    lines.append("")
    lines.append("## drafts (opaque draft_hash × user — run order + total cost)")
    if not drafts:
        lines.append("  (no correlated runs)")
    for key in sorted(drafts):
        d = drafts[key]
        lines.append(
            f"  draft {d['draft_hash']}  user={d.get('user') or '?'}  "
            f"runs={d.get('n_runs', 0)}  total=${d.get('cost_usd', 0):.2f}"
        )
        order = d.get("run_order", [])
        if order:
            lines.append("    timeline: " + " → ".join(order))
    return "\n".join(lines) + "\n"
