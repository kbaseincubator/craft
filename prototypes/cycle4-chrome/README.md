# CRAFT Cycle-4 chrome — Phase-0 synthetic harness (PROTOTYPE)

Scratch prototype to prove the two riskiest design bets of Cycle-4 (chrome/
legibility, DP6) in a **real Claude session**, cheaply, **before** touching any
skill repo. Brief: `handoffs/CRAFT-cycle4-chrome-legibility-brief.md` (Phase 0
+ Pillars 1–3).

Nothing here is shipped. No skill repos are touched; no git. This is the
prototype we later harden into the real `chrome.py` + `decision.v1` validator.

## Files
- `chrome.py` — prototype renderer. `render_stage` / `render_decision` /
  `render_result`; per-skill glyph+label (◆ presentation-maker · ✎ paper-writer
  · ⚔ adversarial); a single `_color()` seam (TTY-gated, `NO_COLOR`-aware,
  no-op when piped). `python chrome.py --demo` prints one of each block.
- `synthetic_halt.py` — writes a `decision.v1` to a scratch `.handoff.json`,
  prints the DECISION block, exits 0 like the real halt. `--gate
  throughline_pick` (default, single_select) or `--gate image_approval`
  (approve_reject — proves the contract generalizes).
- `chrome-interaction.md` — draft of the SKILL.md chrome section (the
  Claude-interaction contract under test in Test 2).

## Design choices in this prototype (the parked open decisions)
- **STAGE = single-rule box** (`┌─┐`), **DECISION = double-rule box** (`╔═╗`) —
  DECISION is the most prominent class by design.
- **RESULT = no box**, a terse glyph-tagged one-liner.
- **Color is strictly additive.** Every distinction (box + glyph + label) is
  structural and survives with color stripped. `_color()` is the only ANSI
  emitter; it no-ops unless stdout is a TTY and `NO_COLOR` is unset.

---

## Adam's test protocol (run in a REAL Claude session)

### Test 1 — signature + color reality
Have Claude run:
```
python chrome.py --demo
```
Observe in the tool-result block:
- Do the **box + glyph + skill-ID label** read as DISTINCT from Claude's
  surrounding prose? Is "which skill is talking" instant?
- Does **color** render, come through as raw escape codes (`\033[36m…`), or get
  stripped? (Expectation from the brief: stripped/absent inside Claude, since
  the subprocess stdout is non-TTY. Confirm empirically.)
- Compare single-rule STAGE vs double-rule DECISION — does the prominence
  ordering read right?

Optional bare-terminal contrast (shows the color seam working where a TTY
exists): `CRAFT_FORCE_COLOR=1 python chrome.py --demo` vs piped
`python chrome.py --demo | cat` (latter must be plain).

### Test 2 — decision.v1 inline rendering (the central bet)
With `chrome-interaction.md` loaded into the session context, have Claude run:
```
python synthetic_halt.py
```
Observe:
- Does Claude present the **full** throughline options (TL1/TL2/TL3) cleanly
  **inline**, including each option's complete `detail` text — NOT a summary,
  NOT "see .handoff.json"?
- Does it make choosing trivial (lists the ids + the default) and collect a
  choice (e.g. "TL1")?
- On the reply, does it show it would invoke
  `beril-presentation-maker continue <draft_dir> --pick TL1` — with the user
  never seeing the raw `--pick` flag or the draft path?

Also run `python synthetic_halt.py --gate image_approval` to confirm the
approve/reject `kind` renders + collects cleanly too.

**Gate:** if the in-session decision rendering doesn't behave, we adjust
`decision.v1` + `chrome-interaction.md` HERE (cheap) before wiring any
pipeline.

---

## Phase-0 findings (CC, in-session, 2026-06-09)

**Both bets PROVED.** Test 1: the box + glyph + `CRAFT · <skill>` label read as
clearly distinct inside a Claude tool-result block, amid prose — structural,
zero color needed. Test 2: with `chrome-interaction.md` as the contract, the
synthetic `decision.v1` halt rendered as a complete inline choice (all three
candidates, full detail) with a trivial "tell me TL1/TL2/TL3" and no
path/flag exposed; the `.handoff.json` artifact is well-formed; both
`single_select` and `approve_reject` kinds render + collect cleanly.

**Color reality confirmed empirically:** captured (non-TTY, i.e. inside Claude)
→ ZERO ANSI, plain box-drawing. `CRAFT_FORCE_COLOR=1` (bare TTY) → 53 ANSI
lines. `NO_COLOR` overrides force. So color is absent exactly where legibility
matters, and the structural signature carries the whole distinction — as the
brief predicted.

**Two defects found + fixed in-phase (the gate's purpose):**
1. *Box width blowout* — one long line (the raw `continue.cmd`, ~190 chars with
   an absolute draft path) stretched the DECISION box off-screen. Fixed: the
   box is now a FIXED width and every content line is wrapped to it (full text
   preserved, never truncated); padding uses visible length so color escapes
   don't push the border.
2. *Path/flag leak* — the rendered DECISION showed the raw
   `continue …/talks/draft_3 --pick {id}` line, which the brief says the user
   must NEVER see. Fixed: removed from the block entirely; replaced with
   "To choose: tell me TL1 / TL2 / TL3." Claude translates the plain id →
   `continue.cmd` per the SKILL.md contract.
   (Residual: a 1-char right-border off-by-one on a few lines ending exactly at
   the wrap boundary — em-dash/Unicode cell-width; cosmetic, deferred to
   hardening.)

## Three open decisions — CC's read (hand-back)

1. **Glyph set + box styling — KEEP as prototyped.** ◆/✎/⚔ + single-rule STAGE
   vs double-rule DECISION gave a clear, correct prominence ordering in-session
   (DECISION unmistakably loudest, STAGE present-but-quiet, RESULT terse). The
   double rule is worth reserving exclusively for DECISION. One caution: the
   glyphs are multi-byte Unicode — fine in the Claude transcript, but the
   hardened renderer's Family-F byte-identity check must store them UTF-8 and
   the shell-side presmaker copy must emit the same bytes.

2. **Auto-invoke vs confirm — PRESENT + CONFIRM, do not auto-invoke.** The
   decision halts are exactly the high-stakes, hard-to-reverse moments
   (throughline sets the whole deck; image-approval spends/commits). Claude
   should collect the choice, then run `continue.cmd` — but a throughline pick
   is consequential enough that a one-beat "resuming with TL1 — go?" is the
   right default over silent auto-run. For `approve_reject` image the cost is
   already spent, so confirm-then-run is fine too. Net: the SKILL.md contract
   should say "collect the choice and resume" but NOT "auto-run without
   acknowledgement." (Adam's call — flagged because it's a UX/safety tradeoff,
   not a code one.)

3. **Color — KEEP the `_color()` seam, structural-first.** It costs one
   well-contained function, it's correct (off when captured, on at a bare TTY,
   `NO_COLOR` honored), and it's a free win for anyone running a skill directly
   in a terminal. It is never load-bearing (Phase 0 proved structural-only
   carries the signal). So: ship structural as the contract, keep color as the
   documented progressive enhancement. Not worth REMOVING; not worth investing
   more than the seam.
