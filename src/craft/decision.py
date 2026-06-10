"""decision.py — CRAFT-platform shared validator for the `decision.v1`
contract (Cycle-4, DP6). Sibling of `run_record.validate_run_record`.

`decision.v1` is what a halt-and-handoff gate writes so Claude can render
the choice **completely inline** and resume from the user's reply (brief
Pillar 2). The renderer is `chrome.render_decision`; this module is the
shape contract.

THE KEY DESIGN POINT (cold-session finding, 2026-06-09): `decision.v1`
**EXTENDS the existing `.handoff.json`** — it does NOT replace it. The
`continue` CLI reads the handoff's own keys (notably `phase`, which
AUTHORIZES the `--pick` resume), so the decision payload must RETAIN those
keys and ADD the presentation fields on top. The validator therefore
checks BOTH contracts at once:

  CLI-required (handoff) keys — so a decision payload can never drift from
  a valid handoff the continue CLI can act on:
    - phase       : str, the gate/halt id; authorizes --pick (REQUIRED)
    - draft_dir   : str, absolute draft dir (REQUIRED)

  decision.v1 presentation keys (REQUIRED):
    - schema_version : "decision.v1"
    - skill          : one of the known skills
    - gate           : str; MUST equal `phase` (the handoff's phase IS the
                       gate — keeps the two surfaces consistent)
    - prompt         : non-empty str
    - kind           : single_select | approve_reject | free_text
    - options        : list[{id, summary, detail}]  (empty allowed only
                       for free_text)
    - default        : str|null; if non-null MUST be one of option ids
    - confirm        : bool (true → Claude echoes pick + one-beat confirm
                       before continuing; false → continue on the choice)
    - continue       : {"cmd": str containing the "{id}" placeholder}

The validator NEVER raises; it returns a list of human-readable error
strings (empty = valid). Substring-stable messages (tests assert
substrings, not equality).
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "decision.v1"

SKILLS = ("presentation-maker", "paper-writer", "adversarial")
KINDS = ("single_select", "approve_reject", "free_text")

# CLI-required keys carried over from .handoff.json (the continue CLI reads
# these; `phase` authorizes --pick). A decision payload that drops these is
# not a usable handoff, however pretty its presentation fields.
_REQUIRED_HANDOFF_KEYS = ("phase", "draft_dir")

# decision.v1 presentation keys.
_REQUIRED_DECISION_KEYS = (
    "schema_version", "skill", "gate", "prompt", "kind",
    "options", "default", "confirm", "continue",
)

_REQUIRED_OPTION_KEYS = ("id", "summary", "detail")


def _is_nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _validate_option(opt: Any, idx: int, errors: list[str]) -> str | None:
    prefix = f"options[{idx}]"
    if not isinstance(opt, dict):
        errors.append(f"{prefix}: not a JSON object")
        return None
    for k in _REQUIRED_OPTION_KEYS:
        if k not in opt:
            errors.append(f"{prefix}.{k}: missing required key")
    # id + summary must be non-empty; detail must be a str (may be long,
    # must be present — the whole point is showing it completely).
    oid = opt.get("id")
    if not _is_nonempty_str(oid):
        errors.append(f"{prefix}.id: must be a non-empty string")
        oid = None
    if "summary" in opt and not isinstance(opt["summary"], str):
        errors.append(f"{prefix}.summary: must be a string")
    if "detail" in opt and not isinstance(opt["detail"], str):
        errors.append(f"{prefix}.detail: must be a string")
    return oid if isinstance(oid, str) else None


def validate_decision(decision: Any) -> list[str]:
    """Validate a parsed decision.v1 / handoff-extension payload.

    Returns a list of human-readable error strings; empty list = valid.
    Never raises on user input.
    """
    errors: list[str] = []

    if not isinstance(decision, dict):
        return [f"decision root: expected JSON object; got "
                f"{type(decision).__name__}"]

    # --- CLI-required handoff keys (the extends-the-handoff contract) ---
    for k in _REQUIRED_HANDOFF_KEYS:
        if k not in decision:
            errors.append(
                f"{k}: missing required handoff key — decision.v1 EXTENDS "
                f".handoff.json and must retain the keys the continue CLI "
                f"reads ('phase' authorizes --pick)")
    if "phase" in decision and not _is_nonempty_str(decision["phase"]):
        errors.append("phase: must be a non-empty string (the gate/halt id)")
    if "draft_dir" in decision and not _is_nonempty_str(decision["draft_dir"]):
        errors.append("draft_dir: must be a non-empty string")

    # --- decision.v1 presentation keys ---
    for k in _REQUIRED_DECISION_KEYS:
        if k not in decision:
            errors.append(f"{k}: missing required decision.v1 key")

    if decision.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version: expected {SCHEMA_VERSION!r}; got "
            f"{decision.get('schema_version')!r}")

    if "skill" in decision and decision["skill"] not in SKILLS:
        errors.append(
            f"skill: must be one of {SKILLS}; got {decision['skill']!r}")

    if "prompt" in decision and not _is_nonempty_str(decision["prompt"]):
        errors.append("prompt: must be a non-empty string")

    kind = decision.get("kind")
    if "kind" in decision and kind not in KINDS:
        errors.append(f"kind: must be one of {KINDS}; got {kind!r}")

    # gate must equal phase — the handoff's phase IS the gate; keeping them
    # consistent stops the presentation drifting from the CLI authority key.
    gate = decision.get("gate")
    phase = decision.get("phase")
    if (_is_nonempty_str(gate) and _is_nonempty_str(phase)
            and gate != phase):
        errors.append(
            f"gate ({gate!r}) must equal phase ({phase!r}) — the handoff's "
            f"phase is the gate id")

    # options
    option_ids: list[str] = []
    opts = decision.get("options")
    if "options" in decision:
        if not isinstance(opts, list):
            errors.append("options: must be a list")
        else:
            for i, opt in enumerate(opts):
                oid = _validate_option(opt, i, errors)
                if oid is not None:
                    option_ids.append(oid)
            if len(option_ids) != len(set(option_ids)):
                errors.append("options[].id: ids must be unique")
            # selectable kinds need at least one option.
            if kind in ("single_select", "approve_reject") and not opts:
                errors.append(
                    f"options: must be non-empty for kind={kind!r}")

    # default: null allowed; if set, must reference an option id (for the
    # selectable kinds).
    if "default" in decision:
        default = decision["default"]
        if default is not None:
            if not isinstance(default, str):
                errors.append("default: must be a string or null")
            elif (kind in ("single_select", "approve_reject")
                  and option_ids and default not in option_ids):
                errors.append(
                    f"default ({default!r}) not found in options[].id "
                    f"({option_ids!r})")

    # confirm: must be a real bool (not truthy int) — it gates the
    # echo-and-wait behavior, so a wrong type is a real bug.
    if "confirm" in decision:
        if not isinstance(decision["confirm"], bool):
            errors.append("confirm: must be a boolean (true|false)")

    # continue.cmd: must carry the {id} placeholder so Claude can splice the
    # chosen id. (For free_text, {id} is still the slot the reply fills.)
    cont = decision.get("continue")
    if "continue" in decision:
        if not isinstance(cont, dict):
            errors.append("continue: must be a JSON object with a 'cmd'")
        else:
            cmd = cont.get("cmd")
            if not _is_nonempty_str(cmd):
                errors.append("continue.cmd: must be a non-empty string")
            elif "{id}" not in cmd:
                errors.append(
                    "continue.cmd: must contain the '{id}' placeholder so "
                    "the chosen option id can be spliced in")

    return errors
