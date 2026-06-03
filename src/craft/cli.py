"""CRAFT CLI entry point.

Subcommands:
  craft install-platform <BERIL_ROOT>   — install all three CRAFT
                                          skills into a BERIL deployment
  craft doctor [<BERIL_ROOT>]           — verify platform health
  craft version                         — print CRAFT + skill versions

Each subcommand is a thin coordinator over the underlying per-skill
CLIs. The skills do the actual work; CRAFT orchestrates the
sequence + reports a unified summary.
"""

from __future__ import annotations

import argparse
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
# install-platform
# ---------------------------------------------------------------------------


def cmd_install_platform(args: argparse.Namespace) -> int:
    """Run all three skills' install-skill commands in sequence."""
    beril_root = Path(args.beril_root).resolve()
    if not beril_root.is_dir():
        print(f"Error: BERIL_ROOT not found: {beril_root}", file=sys.stderr)
        return 1

    print(f"CRAFT install-platform v{__version__}", file=sys.stderr)
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
                f"pipx install git+https://github.com/ArkinLaboratory/{name}.git",
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

    # Check 2: each skill's --version (cross-checks pipx install integrity)
    print("", file=sys.stderr)
    print("── Skill versions", file=sys.stderr)
    for skill in _SKILLS:
        cli = skill["cli"]
        if shutil.which(cli) is None:
            continue
        try:
            result = subprocess.run(
                [cli, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            version_str = (result.stdout + result.stderr).strip().split()[-1]
            print(f"   {cli}: {version_str}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"   {cli}: ERROR reading version: {exc}", file=sys.stderr)
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
    p_install.set_defaults(func=cmd_install_platform)

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
