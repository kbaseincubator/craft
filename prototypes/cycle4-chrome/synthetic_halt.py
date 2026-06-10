#!/usr/bin/env python3
"""synthetic_halt.py — CRAFT Cycle-4 Phase-0 synthetic halt (PROTOTYPE).

Simulates the throughline-pick HALT without a pipeline: writes a
decision.v1 payload to a scratch .handoff.json, prints the DECISION
block via chrome.render_decision, and exits 0 like the real halt-and-
handoff gate does.

This is the central-bet test (brief Phase 0, item 2): in a real Claude
session with chrome-interaction.md in context, run this and observe
whether Claude renders the FULL throughline options cleanly inline,
collects a choice (e.g. "TL1"), and shows it would invoke the
continue.cmd — or buries / mangles / summarizes it.

Usage:
    python synthetic_halt.py [--draft-dir DIR] [--gate throughline_pick|image_approval]
The default writes <draft-dir>/.handoff.json (draft-dir defaults to a
scratch dir under this prototype).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import chrome

# The 3 caulobacter throughline candidates, hardcoded with FULL detail
# text (the point of the test: options shown completely, not pointers).
_THROUGHLINE_DECISION = {
    "schema_version": "decision.v1",
    "skill": "presentation-maker",
    "gate": "throughline_pick",
    "prompt": "Choose the throughline for your talk:",
    "kind": "single_select",
    "options": [
        {"id": "TL1",
         "summary": "Δfur derepression is the demonstrable driver of lipid loss",
         "detail": (
             "The deletion of fur derepresses the iron regulon; the "
             "resulting iron dysregulation is the proximate, measurable "
             "cause of the membrane-lipid collapse. This is the strongest "
             "evidence chain in the project — fitness data, lipidomics, and "
             "the NMDC independent-cohort confirmation all point the same "
             "way — and it is the cleanest single-sentence claim a reviewer "
             "cannot easily dismiss. Risk: it is the least novel framing "
             "(it confirms an expected regulatory consequence).")},
        {"id": "TL2",
         "summary": "Lipid remodeling is an adaptive response, not damage",
         "detail": (
             "Reframes the membrane-lipid change as a regulated survival "
             "program the cell mounts under iron stress, rather than passive "
             "damage. More novel and more interesting to a general audience, "
             "but the causal arrow is weaker in the current data: the "
             "'adaptive' reading rests on correlation between the lipid "
             "shift and survival, and a sharp reviewer will press on whether "
             "it is regulated or merely a consequence.")},
        {"id": "TL3",
         "summary": "A systems view: fur is an iron–lipid coupling hub",
         "detail": (
             "The broadest framing — positions fur as the regulatory node "
             "that couples iron homeostasis to membrane composition, with "
             "lipid loss as one readout of a wider coupling. The most "
             "ambitious and the most defensible-if-it-lands, but also the "
             "hardest to support in a 30-minute talk without overclaiming "
             "beyond what the single-organism data show.")},
    ],
    "default": "TL1",
    "continue": {
        "cmd": "beril-presentation-maker continue {draft_dir} --pick {id}"},
}

_IMAGE_DECISION = {
    "schema_version": "decision.v1",
    "skill": "presentation-maker",
    "gate": "image_approval",
    "prompt": "Approve this AI-generated concept image for slide 5?",
    "kind": "approve_reject",
    "options": [
        {"id": "approve", "summary": "Use the generated image",
         "detail": (
             "A stylized cell membrane with iron ions dispersing outward — "
             "a concept illustration for the big-idea slide. The provider "
             "charge ($0.04) is already spent; approving binds it into the "
             "deck, rejecting discards it.")},
        {"id": "reject", "summary": "Skip — leave the slot to curated figures",
         "detail": (
             "No AI image on slide 5; the slide falls back to the curated "
             "figure set selected earlier in the run.")},
    ],
    "default": "approve",
    "continue": {
        "cmd": ("beril-presentation-maker continue {draft_dir} "
                "--image-decision {id} --slide 5")},
}

_GATES = {
    "throughline_pick": _THROUGHLINE_DECISION,
    "image_approval": _IMAGE_DECISION,
}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="synthetic_halt")
    p.add_argument(
        "--draft-dir",
        default=str(Path(__file__).resolve().parent / "scratch-draft"),
        help="Where to write the scratch .handoff.json.")
    p.add_argument("--gate", choices=sorted(_GATES), default="throughline_pick")
    args = p.parse_args(argv)

    draft_dir = Path(args.draft_dir)
    draft_dir.mkdir(parents=True, exist_ok=True)

    decision = dict(_GATES[args.gate])
    decision["draft_dir"] = str(draft_dir)
    # Resolve {draft_dir} in the continue cmd (leave {id} for Claude/the
    # user to fill from the choice).
    cont = dict(decision["continue"])
    cont["cmd"] = cont["cmd"].replace("{draft_dir}", str(draft_dir))
    decision["continue"] = cont

    # Write the .handoff.json (the halt's durable artifact).
    handoff = draft_dir / ".handoff.json"
    handoff.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")

    # Print the DECISION block (what the orchestrator emits to stdout at
    # the halt).
    print()
    print(chrome.render_decision(decision))
    print()
    print(f"[halt] wrote {handoff}", file=sys.stderr)
    print(f"[halt] paused at gate '{args.gate}' — awaiting operator choice.",
          file=sys.stderr)
    # Exit 0: a clean halt-and-handoff (the real gate exits 0 too).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
