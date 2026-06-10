"""Unit tests for craft.decision.validate_decision (Cycle-4, DP6).

Locks the `decision.v1` contract shape. A `decision.v1` payload is what a
halt-and-handoff gate writes so Claude can render the choice COMPLETELY
INLINE and resume from the user's reply. The central design point: it
**EXTENDS the existing `.handoff.json`** — it RETAINS the keys the
`continue` CLI reads (notably `phase`, which authorizes `--pick`) and ADDS
the presentation fields on top. The validator checks BOTH contracts.

The validator is a pure function: `validate_decision(decision) ->
list[str]`. Empty list = valid; otherwise human-readable error strings.
Tests assert SUBSTRING matches (not list equality) so a later message
refinement doesn't crack the suite — same discipline as
`test_run_record_validator.py`.

Platform-owned goldens live in `tests/fixtures/decision_v1/`:
  - throughline_single_select.json  (single_select, confirm:true)
  - image_approve_reject.json       (approve_reject, confirm:false)
Each is a REALISTIC handoff-extension: it carries the real `.handoff.json`
keys (phase, draft_dir, candidates, candidates_md, next_command) AND the
decision.v1 presentation fields. Negative cases mutate a deep copy of a
golden so they exercise the validator against an otherwise-valid payload.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from craft.decision import KINDS, SCHEMA_VERSION, SKILLS, validate_decision

# ---------------------------------------------------------------------------
# Goldens
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "decision_v1"

_GOLDENS = {
    "throughline_single_select": "throughline_single_select.json",
    "image_approve_reject":      "image_approve_reject.json",
}


def _load(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / _GOLDENS[name]).read_text(encoding="utf-8"))


@pytest.fixture
def throughline() -> dict:
    return _load("throughline_single_select")


@pytest.fixture
def image() -> dict:
    return _load("image_approve_reject")


# ---------------------------------------------------------------------------
# Goldens validate clean
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(_GOLDENS))
def test_golden_validates_clean(name):
    errors = validate_decision(_load(name))
    assert errors == [], f"{name} should validate clean; got: {errors}"


def test_golden_throughline_shape(throughline):
    # The golden is genuinely the union of handoff + decision.v1 — assert
    # both surfaces are present so the fixture can't silently lose one.
    assert throughline["phase"] == "throughline_pick"          # handoff key
    assert throughline["gate"] == throughline["phase"]         # cross-check
    assert throughline["schema_version"] == SCHEMA_VERSION
    assert throughline["kind"] == "single_select"
    assert throughline["confirm"] is True
    assert "candidates" in throughline                         # real handoff field
    assert "next_command" in throughline                       # real handoff field
    assert "{id}" in throughline["continue"]["cmd"]


def test_golden_image_shape(image):
    assert image["phase"] == "image_approval"
    assert image["gate"] == image["phase"]
    assert image["kind"] == "approve_reject"
    assert image["confirm"] is False
    ids = [o["id"] for o in image["options"]]
    assert ids == ["approve", "reject"]


# ---------------------------------------------------------------------------
# Root type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [None, [], "x", 3, 3.0, True])
def test_non_dict_root_is_one_error(bad):
    errs = validate_decision(bad)
    assert len(errs) == 1
    assert "decision root" in errs[0]


def test_empty_dict_reports_all_missing_keys():
    errs = validate_decision({})
    joined = "\n".join(errs)
    # both handoff keys and all decision.v1 keys flagged missing
    assert "phase: missing required handoff key" in joined
    assert "draft_dir: missing required handoff key" in joined
    for k in ("schema_version", "skill", "gate", "prompt", "kind",
              "options", "default", "confirm", "continue"):
        assert f"{k}: missing required decision.v1 key" in joined


# ---------------------------------------------------------------------------
# Handoff-extension contract (the load-bearing design point)
# ---------------------------------------------------------------------------

def test_missing_phase_flags_handoff_extension_contract(throughline):
    d = copy.deepcopy(throughline)
    del d["phase"]
    errs = validate_decision(d)
    msg = "\n".join(errs)
    assert "phase: missing required handoff key" in msg
    assert "EXTENDS" in msg and "authorizes --pick" in msg


def test_missing_draft_dir_flagged(throughline):
    d = copy.deepcopy(throughline)
    del d["draft_dir"]
    errs = validate_decision(d)
    assert any("draft_dir: missing required handoff key" in e for e in errs)


@pytest.mark.parametrize("blank", ["", "   "])
def test_phase_must_be_nonempty(throughline, blank):
    d = copy.deepcopy(throughline)
    d["phase"] = blank
    d["gate"] = blank  # keep gate==phase so we isolate the emptiness error
    errs = validate_decision(d)
    assert any("phase: must be a non-empty string" in e for e in errs)


def test_draft_dir_must_be_nonempty(throughline):
    d = copy.deepcopy(throughline)
    d["draft_dir"] = ""
    errs = validate_decision(d)
    assert any("draft_dir: must be a non-empty string" in e for e in errs)


# ---------------------------------------------------------------------------
# schema_version / skill / prompt / kind
# ---------------------------------------------------------------------------

def test_wrong_schema_version(throughline):
    d = copy.deepcopy(throughline)
    d["schema_version"] = "decision.v2"
    errs = validate_decision(d)
    assert any("schema_version: expected 'decision.v1'" in e for e in errs)


def test_unknown_skill(throughline):
    d = copy.deepcopy(throughline)
    d["skill"] = "atlas"
    errs = validate_decision(d)
    assert any("skill: must be one of" in e for e in errs)


@pytest.mark.parametrize("skill", SKILLS)
def test_known_skills_accepted(throughline, skill):
    d = copy.deepcopy(throughline)
    d["skill"] = skill
    errs = validate_decision(d)
    assert not any(e.startswith("skill:") for e in errs)


@pytest.mark.parametrize("blank", ["", "   "])
def test_prompt_must_be_nonempty(throughline, blank):
    d = copy.deepcopy(throughline)
    d["prompt"] = blank
    errs = validate_decision(d)
    assert any("prompt: must be a non-empty string" in e for e in errs)


def test_unknown_kind(throughline):
    d = copy.deepcopy(throughline)
    d["kind"] = "multi_select"
    errs = validate_decision(d)
    assert any("kind: must be one of" in e for e in errs)


@pytest.mark.parametrize("kind", KINDS)
def test_known_kinds_accepted_for_kind_check(throughline, kind):
    d = copy.deepcopy(throughline)
    d["kind"] = kind
    # free_text may then trip the options-non-empty rule for selectable
    # kinds; we only assert the *kind* check itself doesn't fire.
    errs = validate_decision(d)
    assert not any(e.startswith("kind:") for e in errs)


# ---------------------------------------------------------------------------
# gate == phase cross-check
# ---------------------------------------------------------------------------

def test_gate_must_equal_phase(throughline):
    d = copy.deepcopy(throughline)
    d["gate"] = "some_other_gate"
    errs = validate_decision(d)
    assert any("must equal phase" in e for e in errs)


def test_gate_equal_phase_passes(image):
    # sanity: image golden already has gate==phase and validates clean
    assert validate_decision(image) == []


# ---------------------------------------------------------------------------
# options
# ---------------------------------------------------------------------------

def test_options_must_be_list(throughline):
    d = copy.deepcopy(throughline)
    d["options"] = {"id": "TL1"}
    errs = validate_decision(d)
    assert any("options: must be a list" in e for e in errs)


def test_option_missing_required_keys(throughline):
    d = copy.deepcopy(throughline)
    d["options"] = [{"id": "TL1"}]  # no summary, no detail
    d["default"] = "TL1"
    errs = validate_decision(d)
    joined = "\n".join(errs)
    assert "options[0].summary: missing required key" in joined
    assert "options[0].detail: missing required key" in joined


def test_option_blank_id(throughline):
    d = copy.deepcopy(throughline)
    d["options"] = [{"id": "  ", "summary": "s", "detail": "d"}]
    d["default"] = None
    errs = validate_decision(d)
    assert any("options[0].id: must be a non-empty string" in e for e in errs)


def test_option_detail_wrong_type(throughline):
    d = copy.deepcopy(throughline)
    d["options"] = [{"id": "TL1", "summary": "s", "detail": 42}]
    d["default"] = "TL1"
    errs = validate_decision(d)
    assert any("options[0].detail: must be a string" in e for e in errs)


def test_option_not_an_object(throughline):
    d = copy.deepcopy(throughline)
    d["options"] = ["TL1"]
    d["default"] = None
    errs = validate_decision(d)
    assert any("options[0]: not a JSON object" in e for e in errs)


def test_duplicate_option_ids(throughline):
    d = copy.deepcopy(throughline)
    d["options"] = [
        {"id": "TL1", "summary": "a", "detail": "d"},
        {"id": "TL1", "summary": "b", "detail": "d"},
    ]
    d["default"] = "TL1"
    errs = validate_decision(d)
    assert any("ids must be unique" in e for e in errs)


@pytest.mark.parametrize("kind", ["single_select", "approve_reject"])
def test_selectable_kind_needs_options(throughline, kind):
    d = copy.deepcopy(throughline)
    d["kind"] = kind
    d["options"] = []
    d["default"] = None
    errs = validate_decision(d)
    assert any("options: must be non-empty for kind" in e for e in errs)


def test_free_text_allows_empty_options(throughline):
    d = copy.deepcopy(throughline)
    d["kind"] = "free_text"
    d["options"] = []
    d["default"] = None
    errs = validate_decision(d)
    assert not any(e.startswith("options:") for e in errs)


# ---------------------------------------------------------------------------
# default
# ---------------------------------------------------------------------------

def test_default_null_is_allowed(throughline):
    d = copy.deepcopy(throughline)
    d["default"] = None
    errs = validate_decision(d)
    assert not any(e.startswith("default") for e in errs)


def test_default_must_reference_option_id(throughline):
    d = copy.deepcopy(throughline)
    d["default"] = "TLZ"
    errs = validate_decision(d)
    assert any("not found in options[].id" in e for e in errs)


def test_default_wrong_type(throughline):
    d = copy.deepcopy(throughline)
    d["default"] = 0
    errs = validate_decision(d)
    assert any("default: must be a string or null" in e for e in errs)


# ---------------------------------------------------------------------------
# confirm — must be a REAL bool (a wrong type gates the echo-and-wait beat)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [1, 0, "true", "false", None])
def test_confirm_must_be_real_bool(throughline, bad):
    d = copy.deepcopy(throughline)
    d["confirm"] = bad
    errs = validate_decision(d)
    assert any("confirm: must be a boolean" in e for e in errs)


@pytest.mark.parametrize("good", [True, False])
def test_confirm_accepts_both_bools(throughline, good):
    d = copy.deepcopy(throughline)
    d["confirm"] = good
    errs = validate_decision(d)
    assert not any(e.startswith("confirm:") for e in errs)


# ---------------------------------------------------------------------------
# continue.cmd — must carry the {id} placeholder
# ---------------------------------------------------------------------------

def test_continue_not_object(throughline):
    d = copy.deepcopy(throughline)
    d["continue"] = "beril continue --pick {id}"
    errs = validate_decision(d)
    assert any("continue: must be a JSON object" in e for e in errs)


def test_continue_cmd_blank(throughline):
    d = copy.deepcopy(throughline)
    d["continue"] = {"cmd": "   "}
    errs = validate_decision(d)
    assert any("continue.cmd: must be a non-empty string" in e for e in errs)


def test_continue_cmd_missing_placeholder(throughline):
    d = copy.deepcopy(throughline)
    d["continue"] = {"cmd": "beril-presentation-maker continue /x --pick TL1"}
    errs = validate_decision(d)
    assert any("{id}" in e and "placeholder" in e for e in errs)
