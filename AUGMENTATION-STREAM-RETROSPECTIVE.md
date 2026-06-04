# BERIL Drop-In Augmentation Stream — Retrospective

**Date:** 2026-06-03
**Status:** Stream-level architectural retrospective written
after presentation-maker v0.8.1 ship. Companion document to
`augmentation-stream-plan.md` (the active plan). The stream-
level argument has accumulated enough evidence that this
retrospective is now writable.

**Audience:** Adam Arkin (the panel-of-one reviewer) + any
future engineer or PI evaluating whether BERIL's skill-layer
abstraction can absorb a Co-Scientist capability stack via
drop-in augmentation (vs. a refactor of BERIL itself).

For per-skill internal docs see each skill's
`spike/beril-<name>-skill-draft/{SPEC,LAYOUT,DECISIONS,RELEASE_NOTES,HANDOFF}.md`.

---

## 1. The framing this retrospective answers

The augmentation stream asked: *"What's possible with BERIL-as-it-stands?
Can the skill-layer abstraction absorb a Co-Scientist capability stack
without refactoring BERIL itself?"*

The four skills built across this stream are the evidence:

| Skill | Repo | State at retrospective |
|---|---|---|
| beril-paper-writer-skill | `ArkinLaboratory/beril-paper-writer-skill` | **v1.0.0** (2026-05-20) |
| beril-presentation-maker-skill | `ArkinLaboratory/beril-presentation-maker-skill` | **v0.8.1** (2026-06-03) |
| beril-adversarial-skill | `ArkinLaboratory/beril-adversarial-skill` | **v0.7.0.x** (multiple patches) |
| beril-atlas-skill | `ArkinLaboratory/beril-atlas-skill` | **operational** (Phase 2b cold-scan executed 2026-04-19) |

Two at v1.0 / v0.8.1 (production-ready); one at v0.7.x (stable +
load-bearing for the other two); one operational. The stream-level
argument has cleared the threshold the original plan set
("when two of them are at v1 plus credible roadmaps, write the
retrospective" — `augmentation-stream-plan.md` §4).

## 2. The architectural answer

**Yes. The skill-layer abstraction absorbs the capability stack.**
Evidence:

- **Zero BERIL fork required.** All four skills install via
  `pipx install <skill-repo>` + `<skill> install-skill <BERIL_ROOT>`.
  No BERIL upstream commits; no BERIL configuration changes; no
  BERIL version pinning. Each skill drops into `.claude/skills/<name>/`
  and Claude Code auto-discovers via the existing skill loader.
- **No shared runtime state.** The skills don't talk to each other
  at runtime (modulo the optional reuse-from-sibling-draft pattern
  in §5 below). They share artifact contracts (REPORT.md,
  RESEARCH_PLAN.md, notebooks) but not in-memory state.
- **No global service.** Every skill runs as a CLI invocation
  under BERIL's existing harness — no daemon, no port allocation,
  no auth federation beyond what BERIL already provides
  (`.env` with `CBORG_API_KEY`).
- **Independent ship cycles.** Each skill releases on its own
  cadence: paper-writer shipped v1 in a 5-stage progression over
  ~4 weeks; presentation-maker iterated through v0.3-v0.8 across
  ~7 weeks with 4 Tier-I-veto-with-carries cycles before reaching
  ship; adversarial accumulated patches as the consumer skills
  surfaced schema needs; atlas is operational mode-locked.

The drop-in augmentation pattern works. The remaining question
(was always going to be) about *scope*: what kinds of capabilities
can the pattern absorb, and where does it hit its ceiling?

## 3. The patterns that repeat

The four skills converged on a consistent set of patterns. These
are not coincidences — each was discovered independently and
adopted across skills as the value became clear.

### Pattern: pipx-installable Python package + skill-as-package-data

Each skill is a Python package; the BERIL-side skill data (prompts,
shell orchestrator, Python tools, references, master templates,
test fixtures) ships as package data via `importlib.resources`.
A vendored `install-skill` CLI command copies the bundled data
into `<BERIL_ROOT>/.claude/skills/<name>/`.

**Why this works:** pipx isolates the Python deps per-skill (no
"pip install pollutes BERIL's env" problem). The package-data
pattern means `pipx install --force ...` upgrades both the CLI
and the skill data atomically. The `install-skill` command is the
one operational seam where the skill needs to touch BERIL's
filesystem — and it's idempotent + non-destructive.

**Where it caught fire:** the v0.8.0 install-skill smoke fixture
gap (presentation-maker). The skill bundled fixtures inside the
package but `install-skill` didn't ship them to the BERIL deploy.
Closed in v0.8.0 (moved fixtures into the package + added
`tests` to `_SHIPPED_SUBDIRS`). Pattern-level lesson: "single
source of truth in the package; install-skill is dumb copy" is
the invariant; deviations from it cause silent failure modes.

### Pattern: prompts versioned as `.md` files

Bumping a prompt is a versioned change, not a silent edit. Each
skill numbers its prompts (`methods.v1.md`, `slide_compose.v2.md`,
`adversarial_paper.v1.md`). Bumping triggers a deliberate
re-evaluation; sub-versions accumulate as overlays
(`slide_compose.v3.2_overlay.md`) on top of the prior version.

**Why this works:** prompts ARE the LLM contract. Operators
calibrate cost + quality against a prompt-version pair. Silent
prompt edits would invalidate that calibration. The overlay
pattern (presentation-maker v0.6-v0.8) keeps the v2 baseline
stable while v3.x experimentation runs.

**Where it caught fire:** D-098 (presentation-maker v0.8.0). The
v3.2 slide_compose overlay contradicted the dedicated
`stage_deck_close` stage, telling the per-substory composer to
author the deck_close slide. Caught + fixed in v0.8.0 (prompt
rewrite + merger guard). Pattern-level lesson: overlay stacking
introduces inter-overlay interactions that aren't unit-testable
in isolation; **live-LLM smoke gates** (D-076 pattern) are the
forcing function that catches prompt-layering drift.

### Pattern: Python tools handle structured ops; prompts handle judgment

The split is principled:
- **Python tools** parse markdown (REPORT.md, RESEARCH_PLAN.md),
  validate schemas (slide_spec, claim inventory), generate
  citations from BibTeX, render PowerPoint via python-pptx,
  audit deterministically (figure-provenance, no-artifact-refs,
  content-overflow detection, layout-overlap detection).
- **Prompts** judge: which throughline to pick, how to compose a
  substory, when to add a caveat, what register suits this tier,
  whether an AI image illustrates or distracts.

**Why this works:** structured ops are cheap + reproducible.
Judgment is expensive + variable. Pushing structured ops out of
prompts cuts LLM cost ~50-70% and makes the pipeline debuggable
(failing a Python validator is interpretable; failing an LLM
output is mysterious).

**Where it caught fire:** the v0.8.0 G.10-A bounding-box overlap
detector (presentation-maker). Pre-G.10-A, visual-QA (a vision
LLM) was judging `element_overlap` from rasterized PNGs with
high mis-attribution rate. Pure-geometric `python-pptx` shape
inspection replaced it for the overlap class. Pattern-level
lesson: when an LLM is wrong with high frequency about
something that's geometrically determinable, the structured-op
side of the split is the right answer; the prompt isn't.

### Pattern: `claude -p` subagent invocation

The orchestrator (a bash script per skill) invokes prompts as
`claude -p` subagents, parsing stream-json output for cost +
tool-use accounting. This is the operational pattern that lets
each skill stand on its own — no Anthropic SDK dependency, no
auth federation, just shell-out to `claude`.

**Why this works:** `claude -p` is the existing BERIL primitive.
Skills aren't reinventing LLM invocation; they're sequencing
existing invocations into pipelines. The output schema (stream-
json) is stable; cost accounting is uniform across skills.

**Where it caught fire:** orchestrator output parsing fragility
when stream-json format drifted (paper-writer Stage 4; presentation-
maker M3). Each skill independently arrived at a `stream_progress.py`
parser — converged pattern. Pattern-level lesson: the parser is
infrastructure; share it across skills (presentation-maker now
imports adversarial's parser; paper-writer has its own — there's
a v0.9+ consolidation opportunity).

### Pattern: strict input contracts + escape hatches

Every prompt names absolute-path inputs at the top; the
orchestrator passes them. No runtime path discovery inside
prompts. When an expected input is absent, prompts halt with a
specific error message rather than improvising.

**Why this works:** runtime path discovery inside prompts (the
anti-pattern) means failures manifest as garbage output, not
clean errors. Strict input contracts mean a missing file is a
halt + clear diagnostic; the operator knows exactly what's
wrong.

**Where it caught fire:** v0.5.1 D-076 smoke gate
(presentation-maker). When prompt edits invalidated cached
calibration, the gate halted runs with a clear "no fresh v3
smoke pass" diagnostic instead of producing miscalibrated
decks. Pattern-level lesson: input contracts pay off MOST when
the prompt-stack version surface widens (v1 → v2 → v3 → v3.1
→ v3.2 → v3.3 in presentation-maker); the strict contract is
what makes that version surface tractable.

### Pattern: bounded retry semantics

Any external validation (validator, citation pool, schema
check) that a prompt might fail uses REPAIR_MODE-style bounded
retry: re-invoke the prompt with the specific named failure as
input, capped at 3 attempts. Bounded retry means failures are
detected + repaired without unbounded LLM cost.

**Why this works:** LLM output is variable. Without retry,
single-shot failures kill the pipeline. With unbounded retry,
LLM cost diverges. Bounded retry is the operational compromise.

### Pattern: tiered review cascade

Every skill that has a quality gate has converged on a tiered
review structure: cheap deterministic checks first (Tier 1);
moderately-cheap narrative-light review (Tier 2); expensive
canonical adversarial review (Tier 3); fail-fast short-circuit
when Tier 1 surfaces a P0. The presentation-maker M4b cascade
is the most-developed version; paper-writer's review-rewrite
loop converged on a similar shape independently.

**Why this works:** cost. A talk-30 STRONG presentation-maker
run can fail a P0 mechanical validator (figure path missing,
slide_spec schema violation) at $0 in Tier 1 instead of spending
$0.50-1.50 of Tier 3 adversarial review only to surface the same
finding. Fail-fast saves the expensive tiers for cases where
Tiers 1 + 2 passed.

**Where it caught fire:** the v0.4 M4b cascade design. The
cascade is the natural place for new validators to plug in
(presentation-maker's `check_figure_provenance`, `check_substory_shape`,
`check_curator_figure_floor`, `check_cross_tenant_grounding`,
`check_slide_layout_overlaps`, `check_content_overflow` all
read-if-present at Tier 1). Pattern-level lesson: the cascade
is **extensible storage** for deterministic findings; the
prompt-side review is **synthesis** over those findings.

### Pattern: auto-memory integration

Each skill reads workspace-level auto-memory (`.auto-memory/MEMORY.md`)
on startup. Cross-skill discoveries (KBase Lakehouse pitfalls,
KBase Lakehouse schema details, citation canonicalizations, prompt-layering
drift patterns) accumulate there and inform future invocations.

**Why this works:** the panel-of-one model needs persistent
memory across conversations + across skills. Auto-memory is
the durable substrate. Without it, the same learning cycle
would repeat per-conversation.

**Where it caught fire:** the v0.6-v0.8 Tier-I veto cycles
(presentation-maker). Each veto added a memory entry; subsequent
cycles read those entries on startup and avoided re-litigating
the same architectural decisions. The veto pattern itself
(D-066/D-079/D-084/D-092/D-098 lineage) is documented as a
memory entry now — visible to future cycles as a recognized
operational mode, not a surprise.

## 4. Where the four diverge

The patterns above repeat. The skill-level *architectures* diverge
in instructive ways:

### paper-writer: holistic write + subtract-only optimizer

Paper-writer's v1 architecture is a **single Opus draft pass**
followed by a **subtract-only optimizer** (the v0.8 holistic-write
Python pipeline). The drafter sees the entire claim inventory
and writes the manuscript end-to-end; the optimizer only removes
content (never adds), so the drafter's choices are the load-bearing
ones.

**Why this shape:** scientific manuscripts have a tight integration
across sections (intro → methods → results → discussion). Per-
section composition (the v0.5 attempt) produced visible seams
where one section contradicted another. Holistic write — at higher
upfront cost — preserves cross-section coherence.

### presentation-maker: architect-then-parallel-compose (v0.4 opt-in)

Presentation-maker's v0.4 path is the **architect-then-parallel-compose**
pattern: a deck_outline stage decides the substory partition,
then N parallel `slide_compose` invocations (one per substory)
fill in slides. The compose-fragments merge post-hoc into a
single slide_spec.json + .pptx.

**Why this shape:** presentations are more *modular* than papers.
Each substory is an independent narrative beat; parallel compose
cuts wall-clock 3-4× without coherence loss (validated by M6 A/B
testing). The opt-in `--architecture-pipeline v0_4` preserved
the v0.3 sequential path for backward compat; v0.4 became the
faster path for operators who could afford the slight content-
shape regression.

**Divergence reason:** the same content density that requires
holistic write for a manuscript (~10,000 words, integrated) can
be parallelized for a deck (~30 slides, 4 substory beats). The
artifact shape determines the composition shape.

### adversarial: review-as-data + multi-type schema

Adversarial-skill is the **producer** of structured review data
that the other skills consume. It has no LLM-pipeline of its own
in the produce-an-artifact sense; it produces *reviews* of
artifacts other skills produced.

**Why this shape:** review is fundamentally meta-data over a
target artifact. Adversarial owns the review schema
(`adversarial-review-{paper,plan,project,presentation}.v3`) and
the LLM-side judgment of "does this artifact pass." Consumer
skills (paper-writer's review-rewrite loop, presentation-maker's
cascade Tier 3) call adversarial as a subprocess + read the
resulting JSON.

**Divergence reason:** adversarial isn't producing content; it's
producing structured judgments. The pipeline-producer shape
(paper-writer's holistic write, presentation-maker's parallel
compose) doesn't apply. The natural shape is request-response
with versioned schemas.

### atlas: observability + learned-pattern indexing

Atlas is the **observer** of BERIL deployments. It runs cold-scans
that walk the BERIL filesystem + index learned patterns
(cross-project schema drift, citation canonicalizations,
recurring failure modes). It has no content-production pipeline;
it has a measurement pipeline.

**Why this shape:** observability needs cross-cutting access to
all other skills' outputs but produces no content. Atlas reads
where the others write; atlas indexes where the others
specialize.

**Divergence reason:** observability is a horizontal capability;
content production is vertical. They occupy orthogonal positions
in the skill ecosystem.

## 5. What this means for BERIL's design

The drop-in augmentation pattern's success has implications for
BERIL's evolution:

1. **The skill layer is the right abstraction for capability
   extension.** Four substantial skills shipped without BERIL-
   side changes. Future capabilities (review, validation,
   format conversion, alternate-target generation) should drop
   in as additional skills, not refactor BERIL.

2. **The 4-zone draft layout is a load-bearing contract** —
   `deliverable/ + narrative/ + working/ + audit/`. This
   convention emerged independently in paper-writer's v0.6 +
   presentation-maker's v0.3.1 + adversarial's review output
   structure. It is now the de facto interop contract; new
   skills should adopt it.

3. **The cascade pattern is the right home for deterministic
   validators.** Each skill's tiered review cascade aggregates
   structured findings + short-circuits on P0. New validators
   plug in via the read-if-present audit-JSON pattern; no
   cascade rewrite needed.

4. **Live-LLM smoke gates are the only thing that catches prompt
   drift.** Mocked LLM tests do NOT substitute. The D-076
   pattern (presentation-maker) + paper-writer's analogous
   smoke-test runbook are the operational defense against
   silent prompt-layering regressions.

5. **The reuse-from-sibling pattern works** — paper-writer's
   citation pool reused by presentation-maker is the strongest
   example. Skills should write structured outputs (citation_pool.json,
   claim_inventory.tsv) that sibling skills can consume; doing
   so cuts redundant LLM cost.

6. **Adam-veto-with-carries is a recognized operational mode**
   — not a failure. The presentation-maker Tier-I veto lineage
   (D-066, D-079, D-084, D-092, D-098) demonstrates that
   mechanical-pass + operator-veto-with-carries is the *expected*
   shape of a panel-of-one review cycle. The pattern is now
   memory-encoded; future skills shouldn't be surprised by it.

## 6. Stream-level lessons learned

Beyond the architectural points above:

### Lesson: the panel-of-one cadence works for v0.x; v1.0 is the
                                          delineation point

For v0.x cycles, single-reviewer (Adam) with carry-list discipline
was sufficient. Tier-I reads with explicit veto-with-carries
produced shippable iterations within ~1-2 weeks per cycle.

The v1.0 transition is the natural moment to widen review:
production deployment, multi-tenant use, cross-skill stress
testing. Paper-writer's v1.0 path (Stage 7 dev runs + holdout
campaign) is the template — explicit pass/fail criteria,
multi-project verification, no carries above the v1.0 threshold.

Presentation-maker reaches the analogous gate at v1.0 (the
HANDOFF.md framing is in place; the question is whether the
production team accepts the documented stable surface).

### Lesson: the four skills' release velocity is uneven on
                                purpose

- Atlas: shipped fast (Phase 2b, operational); intentionally
  minimal iteration after that.
- Adversarial: continuous patch cycle (v0.4 → v0.7.0.8) driven by
  consumer skills' schema needs.
- Paper-writer: bounded staged release (Stages 1-7 → v1.0 in
  ~4 weeks).
- Presentation-maker: extended iteration (v0.3 → v0.8.1 across
  ~7 weeks + 4 Tier-I veto cycles).

The velocity differences are not bugs. Atlas is naturally
"build-once-observe-forever." Adversarial is naturally
"patches-driven-by-consumer-need." Paper-writer's Stage discipline
suited a manuscript pipeline. Presentation-maker's longer
iteration suited the layout/visual/content-quality joint
optimization problem (presentations have more dimensions of
"quality" than papers do).

### Lesson: documentation as a stream-level deliverable

Each skill ships with the same doc surface: README.md / TUTORIAL.md
/ HUB_INSTALL.md / CONTRACT.md / SPEC.md / LAYOUT.md /
DECISIONS.md / RELEASE_NOTES.md / HANDOFF.md (the v1.0
addition). Adopting the doc-set convention across skills was
not planned upfront; it converged because each skill discovered
the same audience set independently (user / operator / integrator
/ maintainer / vendor).

This convention is now reusable for future skills. A new BERIL-
augmentation skill should adopt the doc-set on day 1, not
discover it across cycles.

### Lesson: cross-skill conversations are expensive

The four skills were built in (mostly) separate conversations.
Cross-skill coordination — when paper-writer's schema needs
prompted an adversarial-skill patch, or when presentation-maker
needed to consume paper-writer's citation pool — happened via
memory entries + explicit handoff at conversation boundaries.

This is workable but introduces latency. A v0.9+ improvement
would be **cross-skill coordination as a first-class artifact**
(a shared "cross-skill issues" log, indexed by skill pair).
Auto-memory partially serves this role; making it explicit
would reduce the friction.

## 7. What's left at the stream level

### Skill-level work remaining

- **presentation-maker v1.0 tag** — pending Adam's deliberate
  call. HANDOFF.md is in place. The v0.8.1 ship cleared the
  Tier-I carries that matter; remaining items are v0.9+ deferred
  (per HANDOFF.md §3).
- **adversarial v0.8** — would consolidate the v0.7.x patch
  cycle and align with the v3+ schema as a stable baseline.
  No urgency.
- **atlas v0.2** — cache fix; non-blocking.
- **paper-writer v1.1** — Tier-1 native check-table buildout
  (#48 from V1_X_BACKLOG.md) + drafter-discipline fix (#46).
  Not blocking the stream argument.

### Stream-level work remaining

- **Cross-skill smoke harness.** Today each skill smoke-tests
  in isolation. A stream-level smoke would verify the
  paper-writer → presentation-maker reuse path + the adversarial
  consumer-side schema compatibility across both. Would need a
  workspace-level test harness (out of any one skill's repo).
- **Multi-user / multi-tenant deployment.** All four skills are
  CLI-style invocations. The web-wrap question (spike Claim 5
  about Agent SDK feasibility) is orthogonal to the augmentation
  argument but eventually material for hub deployment at scale.
- **Stream-level retrospective publication.** This document, +
  the per-skill HANDOFF.md docs, are the public artifact of the
  augmentation stream's architectural argument. If/when the work
  goes external (publication, conference talk, internal review
  with DOE leadership), these docs are the source of truth.

## 8. Verdict

The augmentation stream's architectural question — *"can BERIL's
skill-layer abstraction absorb a Co-Scientist capability stack
without refactoring BERIL itself?"* — is answered **yes**.

The four skills are working evidence. The patterns that repeated
across them are now codified (this document) and reusable. The
divergences are instructive about *which* shape suits which
capability. The drop-in augmentation pattern has cleared its
own ship gate.

The deprioritized BERIL refactor spike asked the inverse question
(*"should BERIL be refactored?"*). The augmentation stream's
success doesn't make that question moot — there are still
classes of capability (multi-user web wrap, real-time collaboration,
cross-conversation state synchronization) where the skill-layer
abstraction's ceiling will eventually bind. But for the
Co-Scientist content-production stack specifically, augmentation
was the right choice.

---

*This document is the stream-level retrospective. Updates if/when
material new evidence shifts the architectural argument (e.g., a
new skill that the skill-layer abstraction CANNOT absorb, or a
production deployment that surfaces an unrecoverable scale
issue).*
