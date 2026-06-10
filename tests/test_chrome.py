"""Unit tests for craft.chrome (Cycle-4 output-signature renderer).

Locks the three behaviors the brief flags as load-bearing:
  1. DISPLAY-WIDTH alignment — every line of a boxed block has the same
     visible width as its top border, including glyph-heavy lines
     (◆ ★ · Δ —) and lines containing genuinely wide (CJK) chars. This
     is the must-fix: len()-padding would misalign the right border.
  2. COLOR SEAM — 0 ANSI when piped (non-TTY, i.e. inside Claude); ANSI
     under CRAFT_FORCE_COLOR=1; NO_COLOR overrides force. Structural
     legibility never depends on color.
  3. Render shape — STAGE/DECISION/RESULT carry the signature (glyph +
     CRAFT + skill label + class), DECISION shows every option's full
     detail and never leaks the raw continue cmd / draft path.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))

from craft import chrome  # noqa: E402

_CHROME_PY = _SRC / "craft" / "chrome.py"


# ---------------------------------------------------------------------------
# Display width
# ---------------------------------------------------------------------------

def test_display_width_basics():
    assert chrome._display_width("abc") == 3
    assert chrome._display_width("") == 0
    # Ambiguous-width signature glyphs render as 1 cell (modern default).
    for g in "◆★·Δ—–✎⚔◇•│║":
        assert chrome._display_width(g) == 1, g
    # Genuine East-Asian Wide / Fullwidth = 2.
    assert chrome._display_width("中") == 2
    assert chrome._display_width("ＡＢ") == 4  # fullwidth Latin
    # Combining mark contributes 0 (é as e + U+0301).
    assert chrome._display_width("é") == 1
    # Zero-width chars = 0.
    assert chrome._display_width("a​b") == 2


def test_display_width_ignores_ansi():
    plain = "◆ CRAFT · presentation-maker"
    colored = chrome._color(plain, "bold", "cyan")
    # When color is off (default non-TTY in tests) _color is a no-op, so
    # force it to prove the ANSI-stripping path.
    forced = "\033[1m\033[36m" + plain + "\033[0m"
    assert chrome._display_width(forced) == chrome._display_width(plain)
    assert chrome._display_width(colored) == chrome._display_width(plain)


# ---------------------------------------------------------------------------
# Alignment — the must-fix
# ---------------------------------------------------------------------------

def _aligned(block: str) -> bool:
    lines = block.split("\n")
    top = chrome._display_width(lines[0])
    return all(chrome._display_width(ln) == top for ln in lines)


def test_stage_box_aligned_on_glyph_lines():
    block = chrome.render_stage(
        "presentation-maker", 5, 14, "slide_compose", "opus",
        "running", "2m18s", "3.42")
    assert _aligned(block)
    # the glyph header line specifically matches the border
    top = chrome._display_width(block.split("\n")[0])
    glyph_line = next(ln for ln in block.split("\n") if "◆" in ln)
    assert chrome._display_width(glyph_line) == top


def test_decision_box_aligned_with_glyphs_and_emdash_and_wide():
    decision = {
        "skill": "presentation-maker", "phase": "throughline_pick",
        "gate": "throughline_pick", "draft_dir": "/x",
        "prompt": "Choose the throughline — pick one:", "kind": "single_select",
        "options": [
            {"id": "TL1", "summary": "Δfur — the demonstrable driver ◆",
             "detail": "em—dash, Δ glyph, star ★, middot · all here."},
            {"id": "TL2", "summary": "CJK width check 中文标题",
             "detail": "包含中文字符的说明文本，用于测试宽字符对齐。"},
        ],
        "default": "TL1", "confirm": True,
        "continue": {"cmd": "x {draft_dir} --pick {id}"},
    }
    block = chrome.render_decision(decision)
    assert _aligned(block), "decision box misaligned on glyph/wide lines"


def test_stage_each_class_uses_expected_rule():
    stage = chrome.render_stage("paper-writer", 1, 9, "extract", "opus",
                                "running", "0s", "0.00")
    assert stage.startswith("┌") and stage.rstrip().endswith("┘")  # single
    dec = chrome.render_decision({
        "skill": "adversarial", "phase": "x", "gate": "x", "draft_dir": "/x",
        "prompt": "p", "kind": "free_text", "options": [], "default": None,
        "continue": {"cmd": "c"}})
    assert dec.startswith("╔") and dec.rstrip().endswith("╝")  # double


# ---------------------------------------------------------------------------
# Signature content
# ---------------------------------------------------------------------------

def test_signature_glyphs_and_labels():
    s = chrome.render_stage("presentation-maker", 1, 2, "plan", "opus",
                            "running", "1s", "0.10")
    assert "◆ CRAFT · presentation-maker · STAGE 1/2" in s
    p = chrome.render_stage("paper-writer", 1, 2, "plan", "opus", "running",
                            "1s", "0.10")
    assert "✎ CRAFT · paper-writer" in p
    a = chrome.render_result("adversarial", "review done")
    assert "⚔ CRAFT · adversarial · RESULT" in a


def _dewrap(block: str) -> str:
    """Strip box chrome (borders, padding) and rejoin wrapped lines into a
    single whitespace-collapsed string, so a wrapped-but-complete detail
    can be asserted as present in full."""
    inner = []
    for ln in block.split("\n"):
        s = ln.strip()
        if not s or set(s) <= set("╔╗╚╝═║┌┐└┘─│ "):
            continue
        # drop the leading/trailing vertical bar of a content row
        s = s.strip("║│").strip()
        inner.append(s)
    return " ".join(" ".join(inner).split())


def test_decision_shows_full_detail_and_hides_raw_command():
    full_detail = ("FULL DETAIL TOKEN that must appear completely inline "
                   "and not be truncated to a pointer.")
    decision = {
        "skill": "presentation-maker", "phase": "throughline_pick",
        "gate": "throughline_pick",
        "draft_dir": "/projects/foo/talks/draft_3",
        "prompt": "Choose:", "kind": "single_select",
        "options": [{"id": "TL1", "summary": "s", "detail": full_detail}],
        "default": "TL1", "confirm": True,
        "continue": {"cmd": "beril-presentation-maker continue "
                            "/projects/foo/talks/draft_3 --pick {id}"},
    }
    block = chrome.render_decision(decision)
    # detail is shown COMPLETELY (may be word-wrapped across rows).
    assert full_detail in _dewrap(block)
    assert "--pick" not in block                     # no raw flag leaked
    assert "/projects/foo/talks/draft_3" not in block  # no draft path leaked
    assert "To choose: tell me TL1." in block        # clean choice prompt


def test_decision_approve_reject_choice_prompt():
    block = chrome.render_decision({
        "skill": "presentation-maker", "phase": "image_approval",
        "gate": "image_approval", "draft_dir": "/x",
        "prompt": "Approve?", "kind": "approve_reject",
        "options": [{"id": "approve", "summary": "yes", "detail": "use it"},
                    {"id": "reject", "summary": "no", "detail": "skip it"}],
        "default": "approve", "confirm": False, "continue": {"cmd": "c"}})
    assert "To choose: tell me approve / reject." in block
    assert "★ [approve]" in block  # default marked


def test_default_option_marked_with_star():
    block = chrome.render_decision({
        "skill": "presentation-maker", "phase": "g", "gate": "g",
        "draft_dir": "/x", "prompt": "p", "kind": "single_select",
        "options": [{"id": "A", "summary": "a", "detail": "d"},
                    {"id": "B", "summary": "b", "detail": "d"}],
        "default": "B", "confirm": True, "continue": {"cmd": "c"}})
    assert "★ [B]" in block and "• [A]" in block


# ---------------------------------------------------------------------------
# Color seam — behavior via subprocess (real isatty / env gating)
# ---------------------------------------------------------------------------

def _demo_stdout(env_extra: dict[str, str]) -> str:
    import os
    env = dict(os.environ)
    env.pop("NO_COLOR", None)
    env.pop("CRAFT_FORCE_COLOR", None)
    env["PYTHONPATH"] = str(_SRC)
    env.update(env_extra)
    # Piped (captured) → stdout is NOT a tty.
    r = subprocess.run([sys.executable, str(_CHROME_PY), "--demo"],
                       capture_output=True, text=True, env=env)
    return r.stdout


def test_color_off_when_piped():
    out = _demo_stdout({})
    assert "\033[" not in out, "ANSI leaked to non-TTY (piped) output"


def test_color_on_under_force():
    out = _demo_stdout({"CRAFT_FORCE_COLOR": "1"})
    assert "\033[" in out, "force-color did not emit ANSI"


def test_no_color_overrides_force():
    out = _demo_stdout({"CRAFT_FORCE_COLOR": "1", "NO_COLOR": "1"})
    assert "\033[" not in out, "NO_COLOR did not override CRAFT_FORCE_COLOR"


def test_structural_signature_survives_without_color():
    """The whole distinction (box + glyph + label) is present with color
    stripped — the inside-Claude condition."""
    out = _demo_stdout({})  # no color
    assert "◆ CRAFT · presentation-maker" in out
    assert "╔" in out and "║" in out  # decision box present
    assert "┌" in out                  # stage box present


# ---------------------------------------------------------------------------
# NOISE → log
# ---------------------------------------------------------------------------

def test_note_noise_appends_to_audit_log(tmp_path):
    chrome.note_noise(tmp_path, "[orchestrator] internal detail 1")
    chrome.note_noise(tmp_path, "[orchestrator] internal detail 2")
    log = (tmp_path / "orchestrator.log").read_text(encoding="utf-8")
    assert "internal detail 1" in log and "internal detail 2" in log
    assert log.count("\n") == 2  # one line each, no stdout


def test_note_noise_never_raises_on_bad_dir(tmp_path):
    # A path whose parent can't be created should not raise.
    bad = tmp_path / "a_file"
    bad.write_text("x")
    chrome.note_noise(bad / "nope", "msg")  # parent is a file → OSError swallowed
