"""CRAFT CLI entry point.

Subcommands:
  craft install-platform <BERIL_ROOT>   — install all three CRAFT
                                          skills into a BERIL deployment
  craft configure <BERIL_ROOT>          — run each skill's `configure`
                                          interactively (CRAFT-CONTRACT §3.4
                                          runtime-config bootstrap)
  craft doctor [<BERIL_ROOT>]           — verify platform health
  craft version                         — print CRAFT + skill versions

Each subcommand is a thin coordinator over the underlying per-skill
CLIs. The skills do the actual work; CRAFT orchestrates the
sequence + reports a unified summary.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from craft import __version__


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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
