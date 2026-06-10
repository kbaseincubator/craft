<!-- PROTOTYPE — draft of the chrome section a skill's SKILL.md will carry
     (CRAFT Cycle-4, Pillar 3). Phase-0: this is the contract we put in the
     session context for Test 2, to see whether Claude renders a decision.v1
     halt correctly. Not yet installed in any skill. -->

## CRAFT interaction layer — how to surface this skill's output

This skill's orchestrator emits **CRAFT signature blocks** on stdout — boxed,
glyph-tagged lines (`◆ CRAFT · <skill> · STAGE …`, a double-boxed `DECISION`,
a terse `RESULT`). They are the user-facing signal. Follow these rules:

1. **Surface signature blocks verbatim.** When a tool result contains a CRAFT
   STAGE / DECISION / RESULT block, pass it through **as-is**. Do NOT
   re-narrate it, summarize it, restate its numbers, or wrap it in extra
   prose. The box is the signal; your prose around it is noise. A bare
   acknowledgement ("Stage 5 is running.") is worse than silence — let the
   block speak.

2. **On a DECISION halt, render the choice completely + inline, then act on
   the reply.** When the orchestrator halts at a decision (it writes a
   `decision.v1` to `<draft_dir>/.handoff.json` and prints a DECISION block),
   the run is paused waiting for the user. You MUST:
   - Present **every** option **completely** — show each option's full
     `detail` text, not just the summary, and never a file path or a "see
     .handoff.json". The user decides from what you show; show all of it.
   - Make choosing trivial: list the option `id`s (e.g. **TL1 / TL2 / TL3**),
     note the `default`, and ask the user to pick one.
   - When the user answers with a choice (e.g. "TL1", or "approve"), invoke
     the command in the decision's `continue.cmd`, substituting their choice
     for `{id}`. The user must NEVER see or type the raw `--pick` flag or the
     draft path — you translate their plain choice into the command and run
     it.
   - Do not invent options or change the `id`s; use exactly what `decision.v1`
     carries.

3. **Keep your own running commentary minimal.** The STAGE banners ARE the
   progress display — do not duplicate them with "now I'll run the next
   stage" narration. Speak up only for: a DECISION (per rule 2), an error/
   blocker, or a final summary the user asked for.

### decision.v1 shape (what you'll find in .handoff.json)
```jsonc
{
  "schema_version": "decision.v1",
  "skill": "presentation-maker",
  "draft_dir": "/abs/.../talks/draft_N",
  "gate": "throughline_pick",          // the halt id
  "prompt": "Choose the throughline for your talk:",
  "kind": "single_select",             // single_select | approve_reject | free_text
  "options": [
    {"id": "TL1", "summary": "one-line", "detail": "FULL text — show this completely"},
    …
  ],
  "default": "TL1",
  "continue": {"cmd": "beril-presentation-maker continue {draft_dir} --pick {id}"}
}
```
Render every `option.detail` in full; collect a choice; run `continue.cmd`
with the chosen `id`. The `default` is what `--auto-advance` would pick
unattended — surface it, but let the user override.
