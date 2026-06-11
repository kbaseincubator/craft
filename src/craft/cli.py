"""CRAFT CLI entry point.

Subcommands:
  craft install-platform <BERIL_ROOT>   — install all three CRAFT
                                          skills into a BERIL deployment
  craft configure <BERIL_ROOT>          — run each skill's `configure`
                                          interactively (CRAFT-CONTRACT §3.4
                                          runtime-config bootstrap)
  craft doctor [<BERIL_ROOT>]           — verify platform health
  craft status <draft_dir>              — read audit/run_record.json
                                          (run-record.v1; Cycle-3 DP1) and
                                          render a compact status surface.
                                          --json dumps the raw record.
  craft version                         — print CRAFT + skill versions

Each subcommand is a thin coordinator over the underlying per-skill
CLIs. The skills do the actual work; CRAFT orchestrates the
sequence + reports a unified summary.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from craft import __version__
from craft.run_record import validate_run_record


# The three CRAFT skills + their pipx-installed CLI names. Listed
# in dependency order: adversarial first (it produces schemas the
# other two consume), then the two drafters in arbitrary order
# (their order doesn't matter functionally; lexical for stability).
_SKILLS: list[dict[str, str]] = [
    {
        "name": "beril-adversarial-skill",
        "cli": "beril-adversarial",
        "purpose": "review-as-data (produces adversarial review JSON)",
    },
    {
        "name": "beril-paper-writer-skill",
        "cli": "beril-paper-writer",
        "purpose": "manuscript drafter (consumes adversarial review)",
    },
    {
        "name": "beril-presentation-maker-skill",
        "cli": "beril-presentation-maker",
        "purpose": "presentation drafter (consumes adversarial review + paper-writer citation pool)",
    },
]


# ---------------------------------------------------------------------------
# Skill version pinning + sync
# ---------------------------------------------------------------------------
#
# The bug this layer fixes (CRAFT v0.2.2 ↓): pipx leaves pre-existing
# skill venvs alone when you install a meta-package whose deps name
# those same packages. CRAFT's pyproject.toml pinning gets silently
# ignored — `pipx install craft@v0.2.2` on a hub with v0.7.0.4 of
# adversarial installed leaves you on v0.7.0.4 of adversarial, not
# the v0.7.0.10 CRAFT pins.
#
# `craft install-platform` now resolves CRAFT's own pinned URLs from
# its installed metadata and force-syncs each skill to the pinned
# version before deploying skill data. `craft doctor` reports drift
# so users can detect the issue before it bites them.


# Pattern for parsing the `name @ git+https://.../skill.git@vTAG` dep
# strings returned by importlib.metadata.requires(). Captures three
# groups: skill name, full install URL (without the @tag suffix on
# the URL itself; pipx wants the full @tag URL), pinned tag.
_DEP_RE = re.compile(
    r"^(?P<name>beril-[\w-]+-skill)\s*@\s*"
    r"(?P<url_with_tag>git\+https?://\S+@(?P<tag>[\w.\-]+))\s*$"
)


def _resolve_skill_pins() -> dict[str, dict[str, str]]:
    """Return {skill_name: {url, tag}} from CRAFT's installed metadata.

    Reads `importlib.metadata.requires('craft')` and parses the
    `beril-*-skill @ git+https://...@vN.N.N` URL form CRAFT uses for
    every skill dep. Skips non-skill deps (build extras, etc.) and
    skill deps that don't have the @tag form.

    Returns an empty dict if CRAFT itself isn't installed (e.g.,
    running from an uninstalled checkout) — in that case the caller
    falls back to skipping the sync stage.
    """
    pins: dict[str, dict[str, str]] = {}
    try:
        requires = importlib.metadata.requires("craft") or []
    except importlib.metadata.PackageNotFoundError:
        return pins
    for req in requires:
        m = _DEP_RE.match(req)
        if m is None:
            continue
        pins[m.group("name")] = {
            "url_with_tag": m.group("url_with_tag"),
            "tag": m.group("tag"),
        }
    return pins


def _installed_skill_version(cli: str) -> Optional[str]:
    """Return the installed skill's reported version, or None if the
    CLI isn't on PATH / errors. Parses the last whitespace-delimited
    token from `<cli> --version` output (handles the various output
    shapes across our three skills)."""
    if shutil.which(cli) is None:
        return None
    try:
        result = subprocess.run(
            [cli, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:  # noqa: BLE001
        return None
    tokens = (result.stdout + result.stderr).strip().split()
    return tokens[-1] if tokens else None


def _versions_match(installed: Optional[str], pinned_tag: str) -> bool:
    """True iff the installed version matches the CRAFT-pinned tag.

    Tags are of the form `v0.7.0.10` / `v1.0.2` etc.; reported skill
    versions are bare (`0.7.0.10`, `1.0.2`). Normalize by stripping
    the leading `v` from the tag.
    """
    if installed is None:
        return False
    return installed == pinned_tag.lstrip("v")


def _sync_skill_to_pinned_version(
    name: str,
    pin: dict[str, str],
    *,
    auto_yes: bool,
) -> tuple[bool, str]:
    """Ensure pipx has `name` installed at `pin['tag']`. Force-installs
    if missing or version-mismatched. Returns (ok, summary_msg).

    auto_yes=True skips the interactive confirmation prompt — used
    on `craft install-platform --yes` for CI / scripted runs.
    """
    cli_name = next((s["cli"] for s in _SKILLS if s["name"] == name), None)
    installed = _installed_skill_version(cli_name) if cli_name else None
    pinned = pin["tag"]

    if _versions_match(installed, pinned):
        return True, f"already at {pinned}"

    action = "install" if installed is None else f"reinstall ({installed} → {pinned})"
    if not auto_yes:
        prompt = f"   Sync {name}: {action}? [Y/n] "
        try:
            answer = input(prompt).strip().lower()
        except EOFError:
            answer = "y"
        if answer and answer not in ("y", "yes"):
            return False, f"skipped by user (still at {installed or 'NOT INSTALLED'})"

    # Run pipx install --force <url>@<tag>. --force is safe whether
    # the venv exists or not; it rebuilds in place.
    cmd = ["pipx", "install", "--force", pin["url_with_tag"]]
    try:
        result = subprocess.run(cmd, capture_output=False)
    except FileNotFoundError:
        return False, "pipx not on PATH — install pipx first"
    except Exception as exc:  # noqa: BLE001
        return False, f"pipx subprocess raised: {exc}"

    if result.returncode != 0:
        return False, f"pipx install exited rc={result.returncode}"

    # Verify the install landed at the right version.
    new_installed = _installed_skill_version(cli_name) if cli_name else None
    if _versions_match(new_installed, pinned):
        return True, f"synced to {pinned}"
    return False, (
        f"post-install version mismatch: expected {pinned}, "
        f"got {new_installed or 'NOT INSTALLED'}"
    )


# ---------------------------------------------------------------------------
# install-platform
# ---------------------------------------------------------------------------


def cmd_install_platform(args: argparse.Namespace) -> int:
    """Force-sync each skill to its CRAFT-pinned version, then run
    each skill's install-skill command against BERIL_ROOT."""
    beril_root = Path(args.beril_root).resolve()
    if not beril_root.is_dir():
        print(f"Error: BERIL_ROOT not found: {beril_root}", file=sys.stderr)
        return 1

    print(f"CRAFT install-platform v{__version__}", file=sys.stderr)
    print(f"BERIL_ROOT: {beril_root}", file=sys.stderr)
    print("", file=sys.stderr)

    # Stage 1: sync each skill to the version CRAFT pins.
    sync_skipped = getattr(args, "no_sync_skills", False)
    if sync_skipped:
        print(
            "── Skipping skill-version sync (--no-sync-skills)",
            file=sys.stderr,
        )
    else:
        print(
            f"── Syncing skill versions to CRAFT v{__version__} pins",
            file=sys.stderr,
        )
        pins = _resolve_skill_pins()
        if not pins:
            print(
                "   ⚠ Could not resolve skill pins from CRAFT metadata "
                "(CRAFT not installed via pipx?). Skipping sync; will "
                "run install-skill against whatever's on PATH.",
                file=sys.stderr,
            )
        else:
            auto_yes = getattr(args, "yes", False)
            sync_errors: list[str] = []
            for skill in _SKILLS:
                name = skill["name"]
                if name not in pins:
                    print(
                        f"   ⚠ {name}: no pin in CRAFT metadata; skipping",
                        file=sys.stderr,
                    )
                    continue
                ok, msg = _sync_skill_to_pinned_version(
                    name, pins[name], auto_yes=auto_yes
                )
                marker = "✓" if ok else "✗"
                print(f"   {marker} {name}: {msg}", file=sys.stderr)
                if not ok:
                    sync_errors.append(f"{name}: {msg}")
            if sync_errors:
                print("", file=sys.stderr)
                print(
                    "   ⚠ One or more skill syncs failed. Continuing to "
                    "install-skill stage anyway; per-skill versions may "
                    "drift from CRAFT's pin.",
                    file=sys.stderr,
                )
        print("", file=sys.stderr)

    # Stage 2: existing per-skill install-skill loop.
    n_ok = 0
    n_missing = 0
    n_failed = 0
    skipped_reasons: list[str] = []

    for skill in _SKILLS:
        cli = skill["cli"]
        name = skill["name"]
        print(f"── {name}", file=sys.stderr)

        if shutil.which(cli) is None:
            print(
                f"   SKIP: `{cli}` not on PATH. Install with: "
                f"pipx install git+https://github.com/kbaseincubator/{name}.git",
                file=sys.stderr,
            )
            n_missing += 1
            skipped_reasons.append(f"{name}: CLI not on PATH")
            continue

        try:
            result = subprocess.run(
                [cli, "install-skill", str(beril_root)],
                capture_output=False,  # let output stream through
            )
        except Exception as exc:  # noqa: BLE001
            print(f"   ERROR: {exc}", file=sys.stderr)
            n_failed += 1
            skipped_reasons.append(f"{name}: subprocess raised {exc}")
            continue

        if result.returncode == 0:
            n_ok += 1
        else:
            n_failed += 1
            skipped_reasons.append(
                f"{name}: install-skill exited rc={result.returncode}"
            )

    print("", file=sys.stderr)
    print("═" * 60, file=sys.stderr)
    print("CRAFT install-platform summary:", file=sys.stderr)
    print(f"  Installed OK: {n_ok}/{len(_SKILLS)}", file=sys.stderr)
    print(f"  Missing CLIs: {n_missing}", file=sys.stderr)
    print(f"  Failed:       {n_failed}", file=sys.stderr)
    if skipped_reasons:
        print("", file=sys.stderr)
        print("Issues:", file=sys.stderr)
        for r in skipped_reasons:
            print(f"  - {r}", file=sys.stderr)
    print("═" * 60, file=sys.stderr)

    if n_ok == len(_SKILLS):
        print("All CRAFT skills installed cleanly.", file=sys.stderr)
        return 0
    elif n_ok > 0:
        print("Partial install. Resolve the issues above + re-run.", file=sys.stderr)
        return 1
    else:
        print("No CRAFT skills installed. Verify pipx + PATH first.", file=sys.stderr)
        return 2


# ---------------------------------------------------------------------------
# configure (umbrella — CRAFT-CONTRACT §3.4)
# ---------------------------------------------------------------------------


def cmd_configure(args: argparse.Namespace) -> int:
    """Run each skill's `configure` against BERIL_ROOT in dependency order.

    Each skill's `configure` is the CRAFT runtime-config bootstrapper —
    it extends `<BERIL_ROOT>/.env` with the additive-only CRAFT shared
    block + the skill's per-skill marker, resolves provider + tier
    models, writes `<BERIL_ROOT>/.claude/settings.json` (+
    `settings.local.json`) for `claude -p` routing, and runs a
    response-asserting validation ping. See CRAFT-CONTRACT §3.4.

    This umbrella mirrors `cmd_install_platform`'s shape: per-skill
    `── name`, ✓/✗ result, summary block, return codes
    `0` all-ok / `1` partial / `2` none. Unlike `cmd_doctor`'s Check 3
    probe (which sets `timeout=30` and captures output for a quick
    health check), this command does NEITHER — the configure preflight
    is interactive (model-pin picker on a TTY, confirmation prompts on
    .env writes), so we let stdin/stdout flow straight through to the
    user's terminal.
    """
    beril_root = Path(args.beril_root).resolve()
    if not beril_root.is_dir():
        print(f"Error: BERIL_ROOT not found: {beril_root}", file=sys.stderr)
        return 1

    print(f"CRAFT configure v{__version__}", file=sys.stderr)
    print(f"BERIL_ROOT: {beril_root}", file=sys.stderr)
    print("", file=sys.stderr)

    n_ok = 0
    n_missing = 0
    n_failed = 0
    skipped_reasons: list[str] = []

    for skill in _SKILLS:
        cli = skill["cli"]
        name = skill["name"]
        print(f"── {name}", file=sys.stderr)

        if shutil.which(cli) is None:
            print(
                f"   SKIP: `{cli}` not on PATH. Install with: "
                f"pipx install git+https://github.com/kbaseincubator/{name}.git",
                file=sys.stderr,
            )
            n_missing += 1
            skipped_reasons.append(f"{name}: CLI not on PATH")
            continue

        try:
            # Interactive passthrough: NO timeout, NO capture_output. The
            # configure preflight prompts for model pins on a TTY + asks
            # for `.env`-extend confirmation; both need stdin/stdout.
            result = subprocess.run(
                [cli, "configure", str(beril_root)],
            )
        except Exception as exc:  # noqa: BLE001
            print(f"   ✗ ERROR: {exc}", file=sys.stderr)
            n_failed += 1
            skipped_reasons.append(f"{name}: subprocess raised {exc}")
            continue

        if result.returncode == 0:
            print(f"   ✓ {name} configured", file=sys.stderr)
            n_ok += 1
        else:
            print(
                f"   ✗ {name}: configure exited rc={result.returncode}",
                file=sys.stderr,
            )
            n_failed += 1
            skipped_reasons.append(f"{name}: configure exited rc={result.returncode}")

    print("", file=sys.stderr)
    print("═" * 60, file=sys.stderr)
    print("CRAFT configure summary:", file=sys.stderr)
    print(f"  Configured OK: {n_ok}/{len(_SKILLS)}", file=sys.stderr)
    print(f"  Missing CLIs:  {n_missing}", file=sys.stderr)
    print(f"  Failed:        {n_failed}", file=sys.stderr)
    if skipped_reasons:
        print("", file=sys.stderr)
        print("Issues:", file=sys.stderr)
        for r in skipped_reasons:
            print(f"  - {r}", file=sys.stderr)
    print("═" * 60, file=sys.stderr)

    if n_ok == len(_SKILLS):
        print("All CRAFT skills configured cleanly.", file=sys.stderr)
        return 0
    elif n_ok > 0:
        print(
            "Partial configure. Resolve the issues above + re-run.",
            file=sys.stderr,
        )
        return 1
    else:
        print(
            "No CRAFT skills configured. Verify pipx + PATH first.",
            file=sys.stderr,
        )
        return 2


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def cmd_doctor(args: argparse.Namespace) -> int:
    """Verify platform health: skills installed, configure passes,
    cross-skill dependencies present."""
    print(f"CRAFT doctor v{__version__}", file=sys.stderr)
    print("", file=sys.stderr)

    n_ok = 0
    n_warnings = 0

    # Check 1: each skill's CLI is on PATH
    print("── Skill CLIs on PATH", file=sys.stderr)
    for skill in _SKILLS:
        cli = skill["cli"]
        cli_path = shutil.which(cli)
        if cli_path:
            print(f"   ✓ {cli} → {cli_path}", file=sys.stderr)
            n_ok += 1
        else:
            print(f"   ✗ {cli} NOT on PATH", file=sys.stderr)
            n_warnings += 1

    # Check 2: installed skill versions match CRAFT pins.
    print("", file=sys.stderr)
    print("── Skill versions (vs CRAFT pins)", file=sys.stderr)
    pins = _resolve_skill_pins()
    for skill in _SKILLS:
        cli = skill["cli"]
        name = skill["name"]
        if shutil.which(cli) is None:
            continue
        installed = _installed_skill_version(cli)
        if installed is None:
            print(f"   {cli}: ERROR reading version", file=sys.stderr)
            n_warnings += 1
            continue
        pinned = pins.get(name, {}).get("tag")
        if pinned is None:
            print(f"   {cli}: {installed}  (CRAFT pin unknown)", file=sys.stderr)
            continue
        if _versions_match(installed, pinned):
            print(f"   ✓ {cli}: {installed} (matches pin)", file=sys.stderr)
        else:
            print(
                f"   ⚠ {cli}: installed {installed}, "
                f"CRAFT pins {pinned} — run `craft install-platform` to sync",
                file=sys.stderr,
            )
            n_warnings += 1

    # Check 3: each skill's configure (if a BERIL_ROOT was supplied)
    if args.beril_root:
        beril_root = Path(args.beril_root).resolve()
        if not beril_root.is_dir():
            print(f"\n   ✗ BERIL_ROOT not found: {beril_root}", file=sys.stderr)
            n_warnings += 1
        else:
            print("", file=sys.stderr)
            print(
                f"── Per-skill `configure` (BERIL_ROOT={beril_root})", file=sys.stderr
            )
            for skill in _SKILLS:
                cli = skill["cli"]
                if shutil.which(cli) is None:
                    continue
                print(f"   {cli} configure ...", file=sys.stderr)
                try:
                    subprocess.run(
                        [cli, "configure", str(beril_root)],
                        capture_output=False,
                        timeout=30,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"   ERROR: {exc}", file=sys.stderr)
                    n_warnings += 1

    # Summary
    print("", file=sys.stderr)
    print("═" * 60, file=sys.stderr)
    print("CRAFT doctor summary:", file=sys.stderr)
    print(f"  Checks passed: {n_ok}/{len(_SKILLS)}", file=sys.stderr)
    print(f"  Warnings:      {n_warnings}", file=sys.stderr)
    print("═" * 60, file=sys.stderr)

    return 0 if n_warnings == 0 else 1


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


def cmd_version(args: argparse.Namespace) -> int:
    """Print CRAFT + each skill's version."""
    print(f"CRAFT v{__version__}")
    print("")
    print("Skills:")
    for skill in _SKILLS:
        cli = skill["cli"]
        if shutil.which(cli) is None:
            print(f"  {skill['name']}: NOT INSTALLED")
            continue
        try:
            result = subprocess.run(
                [cli, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            v = (result.stdout + result.stderr).strip().split()[-1]
            print(f"  {skill['name']}: {v}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {skill['name']}: ERROR ({exc})")
    return 0


# ---------------------------------------------------------------------------
# craft status (Cycle 3 / DP1) — read-only run-record.v1 surface
# ---------------------------------------------------------------------------
#
# Reads <draft_dir>/audit/run_record.json (the canonical pollable path
# the per-skill emitters maintain — Steps 2 / 4 / 5 of Cycle 3). Renders
# a single-screen status surface that distinguishes the four `status`
# values (running / halted / completed / failed) plus the missing-record
# case. NEVER raises a traceback — if `craft status` ever does, the
# contract is wrong (this is the reader that validates the contract on
# a real run).
#
# Two render modes:
#   default — single-line-per-field human surface (the Cycle-3 brief's
#             "compact, single-screen status" example).
#   --json  — emit the raw record verbatim (for scripting / the driver
#             poll loop / piping to jq).
#
# Exit codes:
#   0 — the record is parseable + validates clean against
#       run-record.v1 (the run may be running/halted/completed/
#       failed; status is rendered, no opinion).
#   2 — missing record OR malformed JSON OR validator reports
#       errors. The render still happens (in --json mode the
#       partial record dumps; in default mode the missing/error
#       case prints a clear message). Distinct from skill exit
#       codes so a script can disambiguate "no run yet" from
#       "run failed."


def _load_run_record(draft_dir: Path) -> tuple[Optional[dict], Optional[str]]:
    """Read <draft_dir>/audit/run_record.json. Returns
    (record, error_message). Both may be None: a clean missing-file
    returns (None, None); a parse error returns (None, message);
    a successful parse returns (record, None)."""
    path = draft_dir / "audit" / "run_record.json"
    if not path.is_file():
        return None, None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"could not read {path}: {exc}"
    try:
        record = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, (
            f"{path} is not valid JSON ({exc}). The atomic-write "
            f"discipline should prevent half-written files; if you "
            f"see this on a live run, the producer's tempfile + "
            f"os.replace path is broken."
        )
    if not isinstance(record, dict):
        return None, f"{path}: expected JSON object, got {type(record).__name__}"
    return record, None


def _fmt_cost(usd: float) -> str:
    """`$1.84` formatting — two decimals, $-prefixed, never scientific."""
    return f"${usd:,.2f}"


def _fmt_tokens(n: int) -> str:
    """Compact token count: `412k`, `88k`, `1.2M`. Falls back to the
    raw number for tiny counts."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n // 1_000}k"
    return f"{n}"


def _fmt_elapsed(seconds: float) -> str:
    """Human-readable elapsed: `42s`, `12m`, `1h 14m`."""
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    if total < 3600:
        return f"{total // 60}m"
    h = total // 3600
    m = (total % 3600) // 60
    return f"{h}h {m}m" if m else f"{h}h"


def _render_status_surface(record: dict) -> str:
    """Render the compact human-readable status. Defensive about
    missing keys (a half-written record shouldn't crash the
    renderer); fields the record doesn't carry render as `?`.

    Layout (matches the Cycle-3 brief):
        skill:      paper-writer v1.2.0     mode: report
        status:     running                 stage: drafting
        started:    2026-06-07 18:00Z       elapsed: 12m
        cost:       $1.84                   tokens: 412k in / 88k out

    For halted: stage shows the gate name; a "halt note" line tells
    the operator how to resume. For terminal (completed/failed):
    exit_code shown; a "deliverable:" line points at the artifact.
    """
    skill = record.get("skill", "?")
    skill_version = record.get("skill_version", "?")
    mode = record.get("mode") or "—"
    status = record.get("status", "?")
    current_stage = record.get("current_stage")
    stage_render = current_stage or "—"
    started_at = record.get("started_at", "?")
    finished_at = record.get("finished_at")
    exit_code = record.get("exit_code")
    totals = record.get("totals") or {}
    cost = float(totals.get("cost_usd", 0.0) or 0.0)
    elapsed = float(totals.get("elapsed_seconds", 0.0) or 0.0)
    in_toks = int(totals.get("input_tokens", 0) or 0)
    out_toks = int(totals.get("output_tokens", 0) or 0)
    artifacts = record.get("artifacts") or {}
    deliverable = artifacts.get("deliverable")

    # Strip the seconds suffix from started_at for the surface render
    # (full ISO stays in --json). "2026-06-07T18:00:00Z" → "2026-06-07 18:00Z".
    started_short = started_at
    if isinstance(started_at, str) and len(started_at) >= 16:
        started_short = started_at[:10] + " " + started_at[11:16] + "Z"

    lines = [
        f"  skill:      {skill} v{skill_version}     mode: {mode}",
        f"  status:     {status:<22} stage: {stage_render}",
        f"  started:    {started_short:<22} elapsed: {_fmt_elapsed(elapsed)}",
        f"  cost:       {_fmt_cost(cost):<22} tokens: {_fmt_tokens(in_toks)} in / {_fmt_tokens(out_toks)} out",
    ]

    if status == "halted":
        gate = current_stage or "?"
        lines.append("")
        lines.append(
            f"  halt:       awaiting operator input at gate {gate!r}."
        )
        # Best-effort hint: presmaker's throughline_pick gate writes
        # .handoff.json — if it's there, surface the resume command.
        # This is read-only (we don't open the file), so it's safe.
        lines.append(
            f"              the per-skill handoff (.handoff.json if "
            f"present) carries the prompt; resume via the skill's "
            f"`continue` subcommand."
        )
    elif status in ("completed", "failed"):
        if isinstance(exit_code, int):
            lines.append(f"  finished:   exit_code={exit_code}")
        if deliverable:
            lines.append(f"  deliverable: {deliverable}")
    return "\n".join(lines)


def cmd_status(args: argparse.Namespace) -> int:
    draft_dir = Path(args.draft_dir).expanduser().resolve()
    if not draft_dir.is_dir():
        print(
            f"craft status: draft_dir not found: {draft_dir}",
            file=sys.stderr,
        )
        return 2

    record, err = _load_run_record(draft_dir)

    if args.json:
        if record is None:
            # Emit a tiny error-envelope (still valid JSON for scripts).
            payload = {
                "error": err or "no run_record.json found",
                "draft_dir": str(draft_dir),
            }
            print(json.dumps(payload, indent=2))
            return 2
        # Dump verbatim; do NOT validate here — `--json` is the
        # power-user surface that wants the raw record even if it's
        # half-written or pre-contract.
        print(json.dumps(record, indent=2))
        return 0

    if record is None:
        if err is not None:
            print(f"craft status: {err}", file=sys.stderr)
            return 2
        # Clean missing-record case: not a runtime error, but
        # status-of-nothing isn't a `status 0` either. Distinguish:
        # 2 = "no run record" so scripts can branch on it.
        print(
            f"craft status: no run record at "
            f"{draft_dir / 'audit' / 'run_record.json'}"
        )
        print(
            "  Either this draft predates the run-record.v1 contract "
            "(skill version < Cycle 3) or no run has started yet."
        )
        return 2

    # Validate. If the record is malformed-in-detail, render what we
    # can AND surface the validator errors as a warning. We do NOT
    # refuse to render — the operator wants the surface even when
    # the record is iffy.
    errors = validate_run_record(record)
    print(_render_status_surface(record))
    if errors:
        print("")
        print(
            f"  WARNING: run_record.json fails {len(errors)} "
            f"validation check(s) — the producer is out of contract:",
            file=sys.stderr,
        )
        # Limit to first 10 to avoid console-flooding.
        for e in errors[:10]:
            print(f"    - {e}", file=sys.stderr)
        if len(errors) > 10:
            print(
                f"    ... and {len(errors) - 10} more "
                f"(re-run with --json to inspect the raw record)",
                file=sys.stderr,
            )
        return 2
    return 0


# ---------------------------------------------------------------------------
# craft inspect telemetry (C1 / DP D) — the read surface over the egress sink
# ---------------------------------------------------------------------------
#
# Unions <root>/telemetry/craft/**/*.jsonl (all users, all months) and
# summarizes: per-stage p50/p95 COST (+ tokens + duration), status counts,
# error-class rates (empty-until-populated), and per-draft (draft_hash×user)
# run timelines + total cost — the "which draft cost what, when" view C2's
# cost model consumes. Default render is human text; --json dumps the raw
# summary. The root defaults to CRAFT_TELEMETRY_ROOT (or /global_share).


def cmd_inspect_telemetry(args: argparse.Namespace) -> int:
    from craft.telemetry import egress as _tx_egress
    from craft.telemetry import read as _tx_read

    # Root precedence: explicit --root, else the egress config (env or
    # default). A disabled egress config (off) still allows an explicit
    # --root for reading a sink written elsewhere.
    root = args.root
    if root is None:
        root = _tx_egress.egress_root()
    if root is None:
        print(
            "craft inspect telemetry: telemetry is disabled "
            f"({_tx_egress.TELEMETRY_ROOT_ENV}=off) and no --root was given. "
            "Pass --root <path> to inspect a sink, or set "
            f"{_tx_egress.TELEMETRY_ROOT_ENV} to the shared root.",
            file=sys.stderr,
        )
        return 2

    rows = _tx_read.union_telemetry(root)
    summary = _tx_read.summarize(rows)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(_tx_read.render_text(summary), end="")
    return 0


# ---------------------------------------------------------------------------
# argparse setup + dispatch
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="craft",
        description=(
            "CRAFT — Co-Scientist Research Assessment & Framing "
            "Tools. Platform CLI for the BERIL research-assessment "
            "skill stack."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"craft {__version__}",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    # install-platform
    p_install = subparsers.add_parser(
        "install-platform",
        help="Install all three CRAFT skills into a BERIL deployment.",
    )
    p_install.add_argument(
        "beril_root",
        help="Path to the BERIL deployment (contains .claude/skills/).",
    )
    p_install.add_argument(
        "--no-sync-skills",
        action="store_true",
        help=(
            "Skip the pre-install skill-version sync. Use when you "
            "have hand-installed skill versions you want to keep."
        ),
    )
    p_install.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Auto-confirm skill-version sync prompts (for CI / scripted runs).",
    )
    p_install.set_defaults(func=cmd_install_platform)

    # configure (CRAFT-CONTRACT §3.4 runtime-config bootstrap, all skills)
    p_configure = subparsers.add_parser(
        "configure",
        help=(
            "Run each CRAFT skill's `configure` interactively against "
            "BERIL_ROOT — provider + tier-model pin + validation ping."
        ),
    )
    p_configure.add_argument(
        "beril_root",
        help="Path to the BERIL deployment (contains .env + .claude/).",
    )
    p_configure.set_defaults(func=cmd_configure)

    # doctor
    p_doctor = subparsers.add_parser(
        "doctor",
        help="Verify platform health (skill CLIs, versions, config).",
    )
    p_doctor.add_argument(
        "beril_root",
        nargs="?",
        default=None,
        help="Optional BERIL_ROOT for per-skill configure checks.",
    )
    p_doctor.set_defaults(func=cmd_doctor)

    # version
    p_version = subparsers.add_parser(
        "version",
        help="Print CRAFT + each skill's version.",
    )
    p_version.set_defaults(func=cmd_version)

    # status (Cycle 3 / DP1)
    p_status = subparsers.add_parser(
        "status",
        help=(
            "Read <draft_dir>/audit/run_record.json (run-record.v1) "
            "and render a compact status surface. --json dumps raw."
        ),
        description=(
            "Cycle 3 / DP1: read <draft_dir>/audit/run_record.json "
            "(the run-record.v1 contract emitted by every CRAFT skill) "
            "and render a compact status surface — distinguishes the "
            "four run states (running / halted / completed / failed) "
            "plus the missing-record case. Never tracebacks. --json "
            "dumps the raw record for scripting; exit code 0 on a "
            "clean parse, 2 on missing/malformed/out-of-contract."
        ),
    )
    p_status.add_argument(
        "draft_dir",
        help="Path to a skill's draft directory (e.g. "
             "papers/draft_2 or talks/draft_3).",
    )
    p_status.add_argument(
        "--json",
        action="store_true",
        help="Dump the raw run_record.json verbatim (for scripts).",
    )
    p_status.set_defaults(func=cmd_status)

    # inspect (C1 / DP D) — read surfaces over the shared telemetry sink.
    p_inspect = subparsers.add_parser(
        "inspect",
        help="Read surfaces over CRAFT's shared telemetry sink.",
    )
    inspect_sub = p_inspect.add_subparsers(dest="inspect_cmd", required=True)
    p_telemetry = inspect_sub.add_parser(
        "telemetry",
        help=(
            "Union <root>/telemetry/craft/**/*.jsonl and report per-stage "
            "p50/p95 cost + tokens + duration, status/error-class counts, "
            "and per-draft run timelines. --json dumps the raw summary."
        ),
        description=(
            "C1 Workstream D: the read surface over the telemetry egress "
            "sink. Unions every per-user/per-month JSONL written by the "
            "skills' record_finalize, then summarizes the CRAFT cost axis "
            "(p50/p95 cost per stage) + the opaque draft_hash×user run "
            "timelines C2's cost model consumes. Best-effort: torn lines + "
            "unreadable files are skipped, never raised."
        ),
    )
    p_telemetry.add_argument(
        "--root",
        default=None,
        help=(
            "Telemetry root to read (default: CRAFT_TELEMETRY_ROOT or "
            "/global_share). Reads <root>/telemetry/craft/**/*.jsonl."
        ),
    )
    p_telemetry.add_argument(
        "--json",
        action="store_true",
        help="Dump the raw summary dict (for scripting) instead of text.",
    )
    p_telemetry.set_defaults(func=cmd_inspect_telemetry)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
