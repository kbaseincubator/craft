"""CRAFT CLI smoke tests.

These tests exercise the platform CLI without requiring the
three skills to actually be installed. The CLI's job is to
COORDINATE per-skill CLIs; the per-skill behavior is tested in
each skill's own test suite.

Cross-skill integration tests (the actual "does this end-to-end
work?") live in Phase 2's CI smoke test, not here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import craft  # noqa: E402
from craft import cli  # noqa: E402


def test_version_attribute_exists() -> None:
    """Pin: __version__ is SemVer-shaped."""
    v = craft.__version__
    assert v[0].isdigit()
    assert "." in v


def test_skills_list_has_three_entries() -> None:
    """Pin: CRAFT v0.1.0 ships exactly three skills."""
    assert len(cli._SKILLS) == 3


def test_skills_list_names_match_expected() -> None:
    """Pin: skill names match the three repos at v0.1.0."""
    names = {s["name"] for s in cli._SKILLS}
    assert names == {
        "beril-adversarial-skill",
        "beril-paper-writer-skill",
        "beril-presentation-maker-skill",
    }


def test_skills_list_clis_match_expected() -> None:
    """Pin: CLI command names match per-skill pyproject scripts."""
    clis = {s["cli"] for s in cli._SKILLS}
    assert clis == {
        "beril-adversarial",
        "beril-paper-writer",
        "beril-presentation-maker",
    }


def test_cli_parser_builds() -> None:
    """Smoke: the argparse parser builds without error."""
    with pytest.raises(SystemExit):
        cli.main(["--version"])


def test_install_platform_missing_beril_root() -> None:
    """install-platform must error cleanly when BERIL_ROOT
    doesn't exist."""
    rc = cli.cmd_install_platform(argparse.Namespace(beril_root="/no/such/path"))
    assert rc == 1


def test_install_platform_skips_missing_clis(tmp_path, capsys, monkeypatch):
    """When the per-skill CLI isn't on PATH, install-platform
    skips that skill + reports it (doesn't crash)."""
    # Make all three CLIs "missing"
    monkeypatch.setattr("shutil.which", lambda _: None)
    rc = cli.cmd_install_platform(
        argparse.Namespace(
            beril_root=str(tmp_path),
        )
    )
    captured = capsys.readouterr()
    # rc=2 when all three are missing (no skills installed)
    assert rc == 2
    assert "Missing CLIs: 3" in captured.err


def test_doctor_runs_without_beril_root() -> None:
    """doctor without BERIL_ROOT should still run (just skips
    the configure check)."""
    rc = cli.cmd_doctor(argparse.Namespace(beril_root=None))
    # rc=1 because skills won't be on PATH in the test env;
    # that's expected. Test pins that doctor doesn't crash.
    assert rc in (0, 1)


def test_version_subcommand_returns_zero(capsys) -> None:
    """version subcommand always returns 0."""
    rc = cli.cmd_version(argparse.Namespace())
    captured = capsys.readouterr()
    assert rc == 0
    assert craft.__version__ in captured.out
