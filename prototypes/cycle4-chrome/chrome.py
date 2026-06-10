#!/usr/bin/env python3
"""chrome.py — CRAFT Cycle-4 output-signature renderer (PROTOTYPE).

Phase-0 scratch prototype (spike/craft-platform/prototypes/cycle4-chrome/).
NOT the shipped renderer — this is the harness we eyeball-test in a real
Claude session to prove two design bets before touching any skill:
  1. the box + glyph + skill-ID label reads as DISTINCT inside a
     tool-result block amid Claude's prose (structural legibility);
  2. color is a TTY-only bonus that degrades cleanly (absent/no-op when
     piped or captured by a non-TTY subprocess — i.e. inside Claude).

Four output classes (brief Pillar 1):
  STAGE    — boxed banner, single rule. Live progress per run-record stage.
  DECISION — boxed block, DOUBLE rule (most prominent). Renders a
             decision.v1 with options shown COMPLETELY inline.
  RESULT   — terse one-liner (glyph + facts), no box.
  NOISE    — NOT rendered here; the shipped design demotes [orchestrator]
             internals to audit/orchestrator.log, off stdout.

Design under test (parked open decisions — see README):
  - glyph set + single-rule STAGE vs double-rule DECISION
  - color via the _color() seam vs structural-only
The renderer carries the WHOLE distinction structurally; color is
strictly additive and never load-bearing.
"""
from __future__ import annotations

import os
import sys

# --- Per-skill signature: glyph + label. "Which skill is talking" at a
# glance. (Brief: ◆ presentation-maker · ✎ paper-writer · ⚔ adversarial.)
_SKILL_SIG = {
    "presentation-maker": ("◆", "presentation-maker"),
    "paper-writer":       ("✎", "paper-writer"),
    "adversarial":        ("⚔", "adversarial"),
}
_BRAND = "CRAFT"

# Box widths. Kept modest so a banner doesn't wrap in a narrow Claude
# tool-result render; long fields are not truncated (legibility > tidy).
_WIDTH = 72


# ---------------------------------------------------------------------------
# Color seam — the ONLY place ANSI is emitted. TTY-gated + NO_COLOR-aware.
# No-op when piped or captured by a non-TTY subprocess (i.e. inside Claude),
# so structural legibility never depends on it.
# ---------------------------------------------------------------------------

_ANSI = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "cyan": "\033[36m", "yellow": "\033[33m", "green": "\033[32m",
    "magenta": "\033[35m",
}


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR") is not None:   # https://no-color.org
        return False
    if os.environ.get("CRAFT_FORCE_COLOR") == "1":  # test hook only
        return True
    return sys.stdout.isatty()


def _color(text: str, *styles: str) -> str:
    """Wrap `text` in ANSI styles iff color is enabled; else return it
    unchanged. The single chromatic seam."""
    if not styles or not _color_enabled():
        return text
    prefix = "".join(_ANSI.get(s, "") for s in styles)
    return f"{prefix}{text}{_ANSI['reset']}"


# ---------------------------------------------------------------------------
# Box primitives
# ---------------------------------------------------------------------------

def _rule(kind: str, width: int) -> tuple[str, str, str, str, str, str]:
    """Return (tl, tr, bl, br, h, v) box-drawing chars for a single or
    double rule."""
    if kind == "double":
        return "╔", "╗", "╚", "╝", "═", "║"
    return "┌", "┐", "└", "┘", "─", "│"


def _visible_len(s: str) -> int:
    """Length of `s` ignoring ANSI escape sequences, so a color-wrapped
    line pads to the same visible width as a plain one (keeps the right
    border aligned whether or not color is on)."""
    out, i = 0, 0
    while i < len(s):
        if s[i] == "\033":
            j = s.find("m", i)
            if j == -1:
                break
            i = j + 1
            continue
        out += 1
        i += 1
    return out


def _box(lines: list[str], *, kind: str = "single",
         width: int = _WIDTH, accent: tuple[str, ...] = ()) -> str:
    """Render `lines` inside a box of FIXED inner width. Callers must
    pre-wrap content to <= width (see _wrap) — the box never grows to fit
    one long line (that was the Phase-0 width-blowout defect). Padding
    uses visible length so color escapes don't push the right border."""
    tl, tr, bl, br, h, v = _rule(kind, width)
    inner = width + 2
    top = _color(tl + h * inner + tr, *accent)
    bot = _color(bl + h * inner + br, *accent)
    vbar = _color(v, *accent)
    out = [top]
    for s in lines:
        pad = inner - 1 - _visible_len(s)
        out.append(f"{vbar} {s}{' ' * max(pad, 0)}{vbar}")
    out.append(bot)
    return "\n".join(out)


def _sig(skill: str) -> tuple[str, str]:
    return _SKILL_SIG.get(skill, ("◇", skill))


# ---------------------------------------------------------------------------
# STAGE
# ---------------------------------------------------------------------------

def render_stage(skill: str, n: int, N: int, stage: str, model: str,
                 state: str, elapsed: str, cost: str) -> str:
    """Boxed STAGE banner (single rule).

    Header line is the signature: <glyph> CRAFT · <skill> · STAGE n/N.
    Detail line carries stage / model / state / elapsed / cost.
    """
    glyph, label = _sig(skill)
    header = f"{glyph} {_BRAND} · {label} · STAGE {n}/{N}"
    detail = f"{stage}  ·  {model}  ·  {state}  ·  {elapsed}  ·  ${cost}"
    body = [_color(hl, "bold", "cyan") for hl in _wrap(header, _WIDTH)]
    body += [_color(dl, "dim") for dl in _wrap(detail, _WIDTH)]
    return _box(body, kind="single", width=_WIDTH, accent=("cyan",))


# ---------------------------------------------------------------------------
# DECISION — the central bet. Double rule = most prominent class.
# Options are shown COMPLETELY (full detail), never a file pointer.
# ---------------------------------------------------------------------------

def render_decision(decision: dict) -> str:
    """Boxed DECISION block from a decision.v1 dict. Renders every
    option's full detail inline. Handles single_select + approve_reject
    + free_text `kind`s."""
    skill = decision.get("skill", "?")
    glyph, label = _sig(skill)
    gate = decision.get("gate", "")
    kind = decision.get("kind", "single_select")
    prompt = decision.get("prompt", "")
    options = decision.get("options", []) or []
    default = decision.get("default")

    w = _WIDTH
    lines: list[str] = []
    lines.append(_color(f"{glyph} {_BRAND} · {label} · DECISION", "bold",
                        "yellow"))
    if gate:
        lines.append(_color(f"gate: {gate}   ·   kind: {kind}", "dim"))
    lines.append("")
    for pl in _wrap(prompt, w):
        lines.append(_color(pl, "bold"))
    if prompt:
        lines.append("")

    # Options — each shown COMPLETELY. summary AND detail are wrapped to
    # the fixed box width so no single line blows the box out; the full
    # text is always present (wrap, never truncate).
    ids = []
    for opt in options:
        oid = opt.get("id", "?")
        ids.append(oid)
        summary = opt.get("summary", "")
        detail = opt.get("detail", "")
        is_default = (oid == default)
        marker = "★" if is_default else "•"
        head_lines = _wrap(f"{marker} [{oid}] {summary}", w)
        for i, hl in enumerate(head_lines):
            # indent continuation of a wrapped header under the text
            txt = hl if i == 0 else f"    {hl}"
            lines.append(_color(txt, "bold", "green" if is_default else ""))
        for dl in _wrap(detail, w - 6):
            lines.append(f"      {dl}")
        lines.append("")

    if default is not None:
        lines.append(_color(
            f"default if you don't choose (--auto-advance): {default}", "dim"))

    # How the user answers — NO raw command, NO draft path, NO --pick
    # flag (the Phase-0 width blowout AND the "user must never see the
    # flag/path" rule both pointed here). The user just states an id;
    # Claude translates it to continue.cmd. We surface the menu of ids.
    if ids:
        choose = ("approve / reject" if kind == "approve_reject"
                  else " / ".join(ids))
        for cl in _wrap(f"To choose: tell me {choose}.", w):
            lines.append(_color(cl, "bold", "magenta"))

    return _box(lines, kind="double", width=w, accent=("yellow",))


def _wrap(text: str, width: int) -> list[str]:
    """Greedy word-wrap, preserving explicit newlines. Keeps the full
    text — wrapping is for legibility, never truncation."""
    if not text:
        return []
    out: list[str] = []
    for para in text.split("\n"):
        if not para:
            out.append("")
            continue
        cur = ""
        for word in para.split(" "):
            if cur and len(cur) + 1 + len(word) > width:
                out.append(cur)
                cur = word
            else:
                cur = f"{cur} {word}".strip()
        if cur:
            out.append(cur)
    return out


# ---------------------------------------------------------------------------
# RESULT — terse, no box.
# ---------------------------------------------------------------------------

def render_result(skill: str, summary: str, *, deliverable: str | None = None,
                  cost: str | None = None) -> str:
    """One-line RESULT (glyph + facts). Not the deprecated full digest."""
    glyph, label = _sig(skill)
    bits = [f"{glyph} {_BRAND} · {label} · RESULT · {summary}"]
    if cost is not None:
        bits.append(f"${cost}")
    line = "  ·  ".join(bits)
    out = _color(line, "bold", "green")
    if deliverable:
        out += "\n" + _color(f"    → {deliverable}", "dim")
    return out


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _demo() -> None:
    """Print one of each class for the legibility + color eyeball test."""
    print()
    print(render_stage(
        "presentation-maker", 5, 14, "slide_compose", "opus",
        "running", "2m18s", "3.42"))
    print()
    print(render_stage(
        "paper-writer", 3, 9, "drafting", "opus", "running",
        "11m04s", "5.18"))
    print()
    # A representative DECISION (the central bet).
    demo_decision = {
        "schema_version": "decision.v1",
        "skill": "presentation-maker",
        "draft_dir": "/projects/caulobacter_fur_lipida_loss/talks/draft_3",
        "gate": "throughline_pick",
        "prompt": "Choose the throughline for your talk:",
        "kind": "single_select",
        "options": [
            {"id": "TL1",
             "summary": "Δfur derepression is the demonstrable driver of lipid loss",
             "detail": ("The deletion of fur derepresses the iron regulon; "
                        "the resulting iron dysregulation is the proximate, "
                        "measurable cause of the membrane-lipid collapse. "
                        "Strongest evidence chain (fitness + lipidomics + "
                        "the NMDC independent-cohort confirmation); the "
                        "cleanest single-sentence claim a reviewer can't "
                        "dismiss.")},
            {"id": "TL2",
             "summary": "Lipid remodeling is an adaptive response, not damage",
             "detail": ("Frames the lipid change as a regulated survival "
                        "program rather than failure. More novel, but the "
                        "causal arrow is weaker in the current data — invites "
                        "the 'correlation' objection.")},
            {"id": "TL3",
             "summary": "A systems view: fur sits at an iron–lipid coupling hub",
             "detail": ("The broadest framing — positions fur as the node "
                        "coupling iron homeostasis to membrane composition. "
                        "Most ambitious; hardest to defend in a 30-min talk "
                        "without overclaiming.")},
        ],
        "default": "TL1",
        "continue": {
            "cmd": ("beril-presentation-maker continue "
                    "/projects/caulobacter_fur_lipida_loss/talks/draft_3 "
                    "--pick {id}")},
    }
    print(render_decision(demo_decision))
    print()
    # An approve_reject DECISION (proves the contract generalizes).
    demo_image = {
        "schema_version": "decision.v1",
        "skill": "presentation-maker",
        "draft_dir": "/projects/caulobacter_fur_lipida_loss/talks/draft_3",
        "gate": "image_approval",
        "prompt": "Approve this AI-generated concept image for slide 5?",
        "kind": "approve_reject",
        "options": [
            {"id": "approve", "summary": "Use the generated image",
             "detail": ("A stylized cell membrane with iron ions dispersing — "
                        "concept illustration for the big-idea slide. "
                        "Estimated cost already spent: $0.04.")},
            {"id": "reject", "summary": "Skip — leave the slot to curated figures",
             "detail": "No AI image; the slide falls back to the curated figure set."},
        ],
        "default": "approve",
        "continue": {
            "cmd": ("beril-presentation-maker continue "
                    "/projects/caulobacter_fur_lipida_loss/talks/draft_3 "
                    "--image-decision {id} --slide 5")},
    }
    print(render_decision(demo_image))
    print()
    print(render_result(
        "presentation-maker", "deck assembled · 31 slides · 14 stages",
        deliverable="deliverable/draft.pptx", cost="19.76"))
    print()


if __name__ == "__main__":
    if "--demo" in sys.argv:
        _demo()
    else:
        print("chrome.py (prototype) — run with --demo to print samples.",
              file=sys.stderr)
        sys.exit(0)
