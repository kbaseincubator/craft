# CRAFT chrome / interaction-layer contract (canonical)

**Schema:** `decision.v1` (the halt-and-handoff presentation contract) + the
CRAFT output-signature blocks (`STAGE` / `DECISION` / `RESULT`).
**Renderer:** `craft.chrome` (canonical at `craft-platform/src/craft/chrome.py`;
each skill VENDORS a byte-identical copy — Family-F conformance).
**Validator:** `craft.decision.validate_decision`.
**Status:** Cycle-4 (DP6) Phase 1 — foundation. Wired into skills in Phase 2.

This is the **source of record** for the chrome section that each CRAFT skill
carries in its `SKILL.md`. Phase 2 vendors the "Contract text for SKILL.md"
block below into each skill verbatim. Keep this doc and the per-skill SKILL.md
copies in sync (they are a copy-not-share pair, like the chrome.py vendoring).

---

## Why this contract exists (the two facts it is built on)

Both were proven empirically in the Cycle-4 Phase-0 synthetic harness
(`prototypes/cycle4-chrome/`):

1. **Inside Claude, the message body is the legible signal — not the box.**
   A skill's orchestrator runs as a non-TTY subprocess, so (a) its stdout
   carries **zero color** (the `chrome._color()` seam correctly no-ops when
   piped) and (b) the Claude transcript **folds** long tool output. The boxed
   STAGE/DECISION/RESULT blocks are real and useful at a bare terminal, but
   **inside Claude the user sees them only if Claude re-renders them as message
   text.** So the contract is: *Claude reconstructs the structured contract
   (decision.v1 / run-record) as its own message, in a consistent presentation
   style.* "Pass the box through verbatim" is NOT enough — folded output hides
   it.

2. **`decision.v1` EXTENDS the existing `.handoff.json` — it does not replace
   it.** The `continue` CLI reads the handoff's own keys (notably **`phase`**,
   which authorizes `--pick`). A decision payload therefore RETAINS those keys
   and ADDS the presentation fields on top. `gate` MUST equal `phase`. This is
   why `validate_decision` checks both contracts at once.

---

## The three signature classes (what the orchestrator emits)

| Class | Box | When | Prominence |
|---|---|---|---|
| `STAGE` | single rule `┌─┐` | a pipeline stage starts/updates | quiet, present |
| `DECISION` | double rule `╔═╗` | a halt-and-handoff gate | **loudest** |
| `RESULT` | no box, terse glyph line | a stage/run produces a deliverable | terse |

Each carries the per-skill signature: a glyph + `CRAFT · <skill>` label.

| Skill | Glyph |
|---|---|
| presentation-maker | `◆` |
| paper-writer | `✎` |
| adversarial | `⚔` |

Color is strictly additive (a bare-terminal bonus through the single
`_color()` seam); the structural signature (box + glyph + label) carries the
whole distinction with color stripped — which is the inside-Claude condition.

---

## `decision.v1` shape

`decision.v1` is written to `<draft_dir>/.handoff.json` at a halt. It is the
union of the real handoff keys and the presentation fields:

```jsonc
{
  // --- retained handoff keys (the continue CLI reads these) ---
  "phase": "throughline_pick",     // the halt id; AUTHORIZES --pick (required)
  "draft_dir": "/abs/.../talks/draft_N",
  // ... any other handoff fields the skill already wrote (candidates,
  //     candidates_md, next_command, …) are retained, not stripped.

  // --- decision.v1 presentation fields ---
  "schema_version": "decision.v1",
  "skill": "presentation-maker",   // presentation-maker | paper-writer | adversarial
  "gate": "throughline_pick",      // MUST equal `phase`
  "prompt": "Pick the throughline for the deck:",
  "kind": "single_select",         // single_select | approve_reject | free_text
  "options": [
    {"id": "TL1", "summary": "one-line", "detail": "FULL text — show completely"}
    // … empty list allowed only for free_text
  ],
  "default": "TL1",                // str | null; if set, must be an option id
  "confirm": true,                 // bool — gates the echo-and-confirm beat (below)
  "continue": {"cmd": "beril-presentation-maker continue {draft_dir} --pick {id}"}
}
```

`continue.cmd` MUST carry the `{id}` placeholder so Claude can splice the
chosen option id. The user must NEVER see the raw `--pick` flag or the draft
path.

---

## Contract text for SKILL.md (vendor this block into each skill, Phase 2)

> *(Substitute the skill's own name + glyph. The text below is for
> presentation-maker; paper-writer uses `✎ paper-writer`, adversarial uses
> `⚔ adversarial`.)*

### CRAFT interaction layer — how to surface this skill's output

This skill's orchestrator runs as a subprocess. Inside this session its stdout
is non-TTY (no color) and long output is folded out of view, so **the
user-facing signal is YOUR message, not the raw tool output.** Your job is to
re-render the skill's structured signals — STAGE progress, DECISION halts,
RESULT deliverables — as clear, consistent message text. Follow these rules:

1. **Re-render the structured contract as message text — do not rely on the
   raw box being visible.** When a tool result contains a CRAFT `STAGE` /
   `DECISION` / `RESULT` block (or the `decision.v1` / run-record JSON behind
   it), reconstruct it in your own message in a consistent presentation style.
   The boxed block in stdout is bare-terminal chrome and a data source; the
   legible copy the user reads is the one you write. Keep your style consistent
   run-to-run so the skill's "voice" is recognizable.

2. **On a DECISION halt, render the choice completely + inline, honor
   `confirm`, then act on the reply.** When the orchestrator halts at a gate it
   writes a `decision.v1` to `<draft_dir>/.handoff.json` and exits; the run is
   paused waiting for the user. You MUST:
   - Present **every** option **completely** — show each option's full
     `detail` text, not just the `summary`, and never a file path or a "see
     `.handoff.json`". The user decides from what you show; show all of it.
   - Make choosing trivial: list the option `id`s (e.g. **TL1 / TL2 / TL3**),
     note which is the `default`, and ask the user to pick one.
   - **Honor `confirm`:**
     - `confirm: true` (consequential, hard-to-reverse gates — e.g. a
       throughline pick that sets the whole deck): after the user picks, **echo
       the pick back and confirm once** ("Resuming with **TL1** — go?") BEFORE
       running `continue.cmd`. Do not silent-auto-run.
     - `confirm: false` (the choice is cheap or already-spent — e.g. an
       image-approval where the cost is already incurred): run `continue.cmd`
       directly on the stated choice; no extra confirmation beat needed.
   - When you act, invoke the command in `continue.cmd`, substituting the
     chosen `id` for `{id}`. The user must NEVER see or type the raw `--pick`
     flag or the draft path — you translate their plain choice into the
     command and run it.
   - Do not invent options or change the `id`s; use exactly what `decision.v1`
     carries. For `kind: free_text`, the user's typed reply fills the `{id}`
     slot.

3. **Report progress + cost at boundaries, from the run-record — not a
   continuous tick.** The STAGE banners mark stage boundaries; surface a brief
   "Stage N/M (<stage>) — <state>" line at those boundaries, and read
   stage/cost/tokens/model from the run-record (`audit/run_record.json`) when
   reporting them. Do **not** narrate every internal step or invent a live
   progress meter (continuous live ticking is deferred). A final cost/summary
   line when the run completes is welcome; per-step "now I'll run the next
   stage" narration is noise.

4. **Suppress orchestrator NOISE.** Lines the orchestrator marks as internal
   (e.g. `[orchestrator] …` diagnostics) are written to
   `<audit_dir>/orchestrator.log`, not to the user. Do not surface that log
   content unless the user is debugging or an error/blocker requires it.

5. **Speak up only when it carries signal.** A DECISION (rule 2), an
   error/blocker, a boundary report (rule 3), or a final summary the user asked
   for. A bare "Stage 5 is running." with nothing else is worse than silence —
   let the structured re-render do the work.

---

## Conformance

- **Family F** (`tests/test_conformance.py`) — each skill's vendored
  `chrome.py` is byte-identical to craft-platform's canonical. Graceful-skips
  until Phase 2 vendors the copies; fails loud after. The glyphs are multi-byte
  UTF-8 — copy the file verbatim (a locale/encoding slip diverges them
  invisibly).
- **Family G** (`tests/test_conformance.py`) — each skill's shipped
  `decision.v1` goldens (`tests/fixtures/decision_v1/*.json`) validate against
  the shared `validate_decision`. Graceful-skips until Phase 2.
- **Platform goldens** (`tests/test_decision.py`) — the canonical
  `decision.v1` goldens (`tests/fixtures/decision_v1/throughline_single_select.json`,
  `image_approve_reject.json`) validate clean and are the worked examples of
  the handoff-extension shape (single_select/confirm:true and
  approve_reject/confirm:false).
- **Renderer** (`tests/test_chrome.py`) — display-width alignment (the
  must-fix: pad by visible glyph width, not `len()`), the color seam, the
  signature content, and the no-path/no-flag-leak guarantee.
