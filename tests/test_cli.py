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


def _install_ns(beril_root: str, **overrides) -> argparse.Namespace:
    """Build the install-platform Namespace with default attrs the
    CLI reads. Callers can override yes / no_sync_skills per test."""
    return argparse.Namespace(
        beril_root=beril_root,
        no_sync_skills=overrides.get("no_sync_skills", True),  # default skip sync in tests
        yes=overrides.get("yes", True),  # never prompt in tests
    )


def test_install_platform_missing_beril_root() -> None:
    """install-platform must error cleanly when BERIL_ROOT
    doesn't exist."""
    rc = cli.cmd_install_platform(_install_ns("/no/such/path"))
    assert rc == 1


def test_install_platform_skips_missing_clis(tmp_path, capsys, monkeypatch):
    """When the per-skill CLI isn't on PATH, install-platform
    skips that skill + reports it (doesn't crash)."""
    # Make all three CLIs "missing"
    monkeypatch.setattr("shutil.which", lambda _: None)
    rc = cli.cmd_install_platform(_install_ns(str(tmp_path)))
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


# ---------------------------------------------------------------------------
# v0.2.3 skill-version sync layer
# ---------------------------------------------------------------------------


def test_dep_regex_parses_canonical_form() -> None:
    """The dep parser must match the form CRAFT pyproject.toml
    actually ships."""
    line = (
        "beril-adversarial-skill @ git+https://github.com/"
        "kbaseincubator/beril-adversarial-skill.git@v0.7.0.10"
    )
    m = cli._DEP_RE.match(line)
    assert m is not None
    assert m.group("name") == "beril-adversarial-skill"
    assert m.group("tag") == "v0.7.0.10"
    assert m.group("url_with_tag").endswith("@v0.7.0.10")


def test_dep_regex_ignores_non_skill_deps() -> None:
    """Build extras and non-pinned deps should not match."""
    for line in [
        "pytest>=7.4.0; extra == 'dev'",
        "ruff>=0.4.0",
        "build>=1.0.0; extra == 'dev'",
    ]:
        assert cli._DEP_RE.match(line) is None


def test_versions_match_strips_v_prefix() -> None:
    """Installed versions are bare; pinned tags carry a leading v."""
    assert cli._versions_match("0.7.0.10", "v0.7.0.10") is True
    assert cli._versions_match("1.0.2", "v1.0.2") is True
    assert cli._versions_match("0.7.0.9", "v0.7.0.10") is False
    assert cli._versions_match(None, "v0.7.0.10") is False


def test_resolve_skill_pins_returns_dict(monkeypatch) -> None:
    """Pinned-URL resolution returns a {name: {url, tag}} dict for
    the three CRAFT skills when CRAFT metadata is available."""
    fake_requires = [
        "beril-adversarial-skill @ git+https://github.com/kbaseincubator/"
        "beril-adversarial-skill.git@v0.7.0.10",
        "beril-paper-writer-skill @ git+https://github.com/kbaseincubator/"
        "beril-paper-writer-skill.git@v1.0.2",
        "beril-presentation-maker-skill @ git+https://github.com/kbaseincubator/"
        "beril-presentation-maker-skill.git@v1.0.1",
        "pytest>=7.4.0; extra == 'dev'",
    ]
    monkeypatch.setattr(
        cli.importlib.metadata, "requires", lambda _pkg: fake_requires
    )
    pins = cli._resolve_skill_pins()
    assert len(pins) == 3
    assert pins["beril-adversarial-skill"]["tag"] == "v0.7.0.10"
    assert pins["beril-paper-writer-skill"]["tag"] == "v1.0.2"
    assert pins["beril-presentation-maker-skill"]["tag"] == "v1.0.1"


def test_resolve_skill_pins_empty_when_craft_not_installed(monkeypatch) -> None:
    """If CRAFT isn't installed (running from a checkout), the
    resolver returns empty + the caller can fall back gracefully."""
    def raise_not_found(_pkg):
        raise cli.importlib.metadata.PackageNotFoundError("craft")
    monkeypatch.setattr(cli.importlib.metadata, "requires", raise_not_found)
    assert cli._resolve_skill_pins() == {}


def test_sync_skill_skips_when_version_matches(monkeypatch) -> None:
    """If the installed version already matches the pin, sync is
    a no-op + returns success without invoking pipx."""
    # Pretend the CLI is on PATH and reports the matching version.
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/fake/bin/beril-adversarial")
    monkeypatch.setattr(
        cli, "_installed_skill_version", lambda _cli: "0.7.0.10"
    )

    def boom(*_a, **_k):
        raise AssertionError("pipx should NOT be invoked on a no-op sync")
    monkeypatch.setattr(cli.subprocess, "run", boom)

    ok, msg = cli._sync_skill_to_pinned_version(
        "beril-adversarial-skill",
        {"url_with_tag": "git+https://...@v0.7.0.10", "tag": "v0.7.0.10"},
        auto_yes=True,
    )
    assert ok is True
    assert "already at v0.7.0.10" in msg


def test_sync_skill_force_installs_on_drift(monkeypatch) -> None:
    """Version mismatch → pipx install --force is invoked + the
    post-install version check passes."""
    call_log: list[list[str]] = []

    def fake_run(cmd, *_a, **_k):
        call_log.append(list(cmd))
        class _R:
            returncode = 0
        return _R()

    # First _installed_skill_version returns the OLD version; the
    # post-install call returns the NEW version.
    installed_versions = iter(["0.7.0.4", "0.7.0.10"])
    monkeypatch.setattr(
        cli, "_installed_skill_version",
        lambda _cli: next(installed_versions),
    )
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    ok, msg = cli._sync_skill_to_pinned_version(
        "beril-adversarial-skill",
        {
            "url_with_tag": (
                "git+https://github.com/kbaseincubator/"
                "beril-adversarial-skill.git@v0.7.0.10"
            ),
            "tag": "v0.7.0.10",
        },
        auto_yes=True,
    )
    assert ok is True
    assert "synced to v0.7.0.10" in msg
    # pipx install --force <url@tag> should have been called.
    assert any(
        c[0] == "pipx" and "--force" in c and any("@v0.7.0.10" in x for x in c)
        for c in call_log
    )
