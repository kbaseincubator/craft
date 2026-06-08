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
        no_sync_skills=overrides.get(
            "no_sync_skills", True
        ),  # default skip sync in tests
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


# --- configure umbrella (CRAFT-CONTRACT §3.4) -------------------------------


def _configure_ns(beril_root: str) -> argparse.Namespace:
    """Build the configure Namespace. configure has no flags beyond
    beril_root (mirrors install-platform's positional surface)."""
    return argparse.Namespace(beril_root=beril_root)


def test_configure_missing_beril_root() -> None:
    """configure must error cleanly when BERIL_ROOT doesn't exist."""
    rc = cli.cmd_configure(_configure_ns("/no/such/path"))
    assert rc == 1


def test_configure_skips_missing_clis(tmp_path, capsys, monkeypatch):
    """When every per-skill CLI is absent from PATH, configure returns
    rc=2 (no skills configured) and names the missing ones."""
    monkeypatch.setattr("shutil.which", lambda _: None)
    rc = cli.cmd_configure(_configure_ns(str(tmp_path)))
    captured = capsys.readouterr()
    assert rc == 2
    assert "Missing CLIs:  3" in captured.err


def test_configure_invokes_each_skill_with_correct_argv(tmp_path, capsys, monkeypatch):
    """The umbrella shells out to `<cli> configure <BERIL_ROOT>` for each
    skill in `_SKILLS` order. Mock shutil.which + subprocess.run to capture
    the argv per call and confirm the all-OK happy path."""
    monkeypatch.setattr("shutil.which", lambda c: f"/usr/local/bin/{c}")
    captured_calls: list[list[str]] = []

    class _OK:
        returncode = 0

    def fake_run(cmd, **kwargs):
        captured_calls.append(list(cmd))
        # The umbrella does NOT pass timeout / capture_output — the configure
        # preflight is interactive (model-pin picker + .env-extend confirmation).
        # This is the load-bearing distinction vs doctor's Check 3 quick probe.
        assert "timeout" not in kwargs, "configure umbrella must not pass timeout="
        assert "capture_output" not in kwargs, (
            "configure umbrella must not pass capture_output= (interactive passthrough)"
        )
        return _OK()

    monkeypatch.setattr("subprocess.run", fake_run)

    rc = cli.cmd_configure(_configure_ns(str(tmp_path)))
    err = capsys.readouterr().err
    assert rc == 0, err
    # One call per skill, in _SKILLS order, with the right argv shape.
    assert len(captured_calls) == 3
    for skill, call in zip(cli._SKILLS, captured_calls):
        assert call == [skill["cli"], "configure", str(tmp_path.resolve())]
    # Summary line confirms the all-ok count.
    assert "Configured OK: 3/3" in err
    assert "All CRAFT skills configured cleanly." in err


def test_configure_aggregates_partial_failure(tmp_path, capsys, monkeypatch):
    """If one skill's configure exits non-zero, the umbrella returns
    rc=1 (partial), names the failure in the summary, but keeps going
    for the rest."""
    monkeypatch.setattr("shutil.which", lambda c: f"/usr/local/bin/{c}")
    # Fail the SECOND skill (paper-writer); the first + third succeed.
    failing_cli = cli._SKILLS[1]["cli"]

    class _OK:
        returncode = 0

    class _Fail:
        returncode = 7

    def fake_run(cmd, **kwargs):
        return _Fail() if cmd[0] == failing_cli else _OK()

    monkeypatch.setattr("subprocess.run", fake_run)

    rc = cli.cmd_configure(_configure_ns(str(tmp_path)))
    err = capsys.readouterr().err
    assert rc == 1
    assert "Configured OK: 2/3" in err
    assert f"{cli._SKILLS[1]['name']}: configure exited rc=7" in err


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
    monkeypatch.setattr(cli.importlib.metadata, "requires", lambda _pkg: fake_requires)
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
    monkeypatch.setattr(cli, "_installed_skill_version", lambda _cli: "0.7.0.10")

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
        cli,
        "_installed_skill_version",
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


# ===========================================================================
# craft status (Cycle 3 / DP1)
# ===========================================================================
#
# `craft status` reads <draft_dir>/audit/run_record.json and renders a
# compact surface. It MUST NEVER traceback — the brief calls this out
# as the read-side validator of the contract. These tests exercise:
#   - clean records of each status (running / halted / completed / failed)
#   - missing record (no traceback; clear "no run record" message;
#     exit 2 so scripts can branch on it)
#   - malformed JSON (no traceback; error message; exit 2)
#   - --json dumps verbatim including for halted / running records
#   - validator-failure surface (still renders, prints warnings, exits 2)
#   - missing draft_dir (clear error, exit 2)
#
# Fixtures are platform-owned (in tests/fixtures/run_record_v1/) — same
# goldens the validator unit tests use. They're copied into a tmp_path
# layout per test so the fixture dir isn't mutated.

import json  # noqa: E402
import shutil  # noqa: E402

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "run_record_v1"


def _make_draft_with_record(tmp_path: Path, golden_name: str) -> Path:
    """Build a <draft_dir>/audit/run_record.json tmp layout pointing at
    the named golden. Returns the draft_dir path."""
    draft_dir = tmp_path / "draft"
    audit_dir = draft_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        _FIXTURES_DIR / golden_name,
        audit_dir / "run_record.json",
    )
    return draft_dir


def test_status_missing_draft_dir_exits_2(tmp_path, capsys):
    rc = cli.main(["status", str(tmp_path / "no_such_dir")])
    assert rc == 2
    err = capsys.readouterr().err
    assert "draft_dir not found" in err


def test_status_missing_record_exits_2_with_clear_message(tmp_path, capsys):
    """The no-run-yet case. No traceback; rc=2 distinguishes "no record"
    from "running cleanly" (rc=0)."""
    draft_dir = tmp_path / "draft"
    draft_dir.mkdir()  # exists, no audit/ yet
    rc = cli.main(["status", str(draft_dir)])
    assert rc == 2
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "no run record" in out
    # Stretch: the message tells the operator what's happening.
    assert "Cycle 3" in out or "no run has started" in out


def test_status_malformed_json_exits_2_with_clear_message(tmp_path, capsys):
    draft_dir = tmp_path / "draft"
    audit = draft_dir / "audit"
    audit.mkdir(parents=True)
    (audit / "run_record.json").write_text("{not valid json", encoding="utf-8")
    rc = cli.main(["status", str(draft_dir)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "not valid JSON" in err
    # Hints at the producer-side discipline so an operator knows
    # who to file a bug against.
    assert "atomic-write" in err


def test_status_completed_render_includes_expected_fields(
    tmp_path, capsys,
):
    draft_dir = _make_draft_with_record(
        tmp_path, "presentation_maker_completed.json",
    )
    rc = cli.main(["status", str(draft_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    # Each field from the brief's example surface should appear.
    assert "skill:" in out
    assert "presentation-maker" in out
    assert "status:     completed" in out
    assert "started:" in out
    assert "elapsed:" in out
    assert "cost:" in out
    assert "tokens:" in out
    # Terminal extras.
    assert "exit_code=0" in out
    assert "deliverable: deliverable/draft.pptx" in out


def test_status_running_render_shows_current_stage(tmp_path, capsys):
    draft_dir = _make_draft_with_record(
        tmp_path, "presentation_maker_running.json",
    )
    rc = cli.main(["status", str(draft_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "status:     running" in out
    # Running record's current_stage was "slide_compose" in the golden.
    assert "stage: slide_compose" in out
    # No exit_code line for a running record.
    assert "exit_code" not in out


def test_status_halted_render_surfaces_gate_and_resume_hint(
    tmp_path, capsys,
):
    draft_dir = _make_draft_with_record(
        tmp_path, "presentation_maker_halted.json",
    )
    rc = cli.main(["status", str(draft_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "status:     halted" in out
    assert "stage: throughline_pick" in out
    assert "halt:" in out
    assert "throughline_pick" in out
    # The resume hint guides the operator without baking in a
    # skill-specific command (the per-skill `continue` does it).
    assert "continue" in out


def test_status_failed_render_shows_exit_code(tmp_path, capsys):
    draft_dir = _make_draft_with_record(
        tmp_path, "paper_writer_failed.json",
    )
    rc = cli.main(["status", str(draft_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "status:     failed" in out
    # paper_writer_failed.json has exit_code=1.
    assert "exit_code=1" in out


def test_status_json_dumps_record_verbatim(tmp_path, capsys):
    draft_dir = _make_draft_with_record(
        tmp_path, "paper_writer_completed.json",
    )
    rc = cli.main(["status", str(draft_dir), "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    record = json.loads(out)
    assert record["schema_version"] == "run-record.v1"
    assert record["skill"] == "paper-writer"
    assert record["status"] == "completed"


def test_status_json_on_missing_record_emits_error_envelope(tmp_path, capsys):
    """`--json` is the power-user surface; on missing record it MUST
    still produce parseable JSON so a script's `jq` pipeline doesn't
    choke."""
    draft_dir = tmp_path / "draft"
    draft_dir.mkdir()
    rc = cli.main(["status", str(draft_dir), "--json"])
    assert rc == 2
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "error" in payload
    assert payload["draft_dir"] == str(draft_dir.resolve())


def test_status_validator_failure_renders_surface_and_warns(
    tmp_path, capsys,
):
    """An out-of-contract record (e.g. extra top-level key from a
    producer running ahead of the schema) renders WHAT IT CAN +
    surfaces validator warnings + exits 2. The renderer is
    intentionally permissive about missing keys for this reason —
    the operator wants the surface even when the record is iffy."""
    draft_dir = _make_draft_with_record(
        tmp_path, "presentation_maker_completed.json",
    )
    # Doctor the record: add a top-level key the v1 validator rejects.
    rec_path = draft_dir / "audit" / "run_record.json"
    record = json.loads(rec_path.read_text(encoding="utf-8"))
    record["surprise_key"] = "from the future"
    rec_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    rc = cli.main(["status", str(draft_dir)])
    assert rc == 2
    captured = capsys.readouterr()
    # Surface still rendered (default-render branch ran).
    assert "skill:" in captured.out
    # Warning was emitted to stderr.
    assert "WARNING" in captured.err
    assert "surprise_key" in captured.err


def test_status_never_raises_on_arbitrary_garbage(tmp_path, capsys):
    """Defensive: the read-side cannot traceback on a malformed
    record (the renderer is meant to render `?` for unknown
    fields). Try a JSON object with NO known keys."""
    draft_dir = tmp_path / "draft"
    audit = draft_dir / "audit"
    audit.mkdir(parents=True)
    (audit / "run_record.json").write_text(
        json.dumps({"random": "shape"}), encoding="utf-8",
    )
    # No exception should propagate; main returns an int.
    rc = cli.main(["status", str(draft_dir)])
    assert isinstance(rc, int)


def test_status_help_includes_run_record_phrasing(capsys):
    """The help text should signal the contract this subcommand reads."""
    with pytest.raises(SystemExit):
        cli.main(["status", "--help"])
    out = capsys.readouterr().out
    assert "run_record.json" in out
    assert "run-record.v1" in out
