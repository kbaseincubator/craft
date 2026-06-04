# CRAFT-CONTRACT.md — Platform Interface Pin

**Platform:** CRAFT (Co-Scientist Research Assessment & Framing
Tools)
**Date:** 2026-06-03 (initial draft)
**Status:** Initial draft. Captures the cross-skill contract
that exists implicitly across the three production skills as
of their current versions (adversarial v0.7.0.8, paper-writer
v1.0.0, presentation-maker v1.0.0). Live document; updated when
contract surface changes.

**Audience:** (1) maintainers of the three CRAFT skills, (2)
authors of new skills proposing to join the platform, (3)
integrators consuming CRAFT outputs from outside the platform.

For platform structure see `PLATFORM-PROPOSAL.md`. For per-skill
internal docs see each skill's repo `CONTRACT.md`. For the
upstream-change watchlist see `CRAFT-DEPENDENCIES.md`.

---

## 1. What this contract is

CRAFT consists of three skills that are **explicitly designed
to compose**:

- **beril-adversarial-skill** (review-as-data; the producer of
  structured review findings)
- **beril-paper-writer-skill** (manuscript drafter; consumes
  adversarial review for review-rewrite loop)
- **beril-presentation-maker-skill** (presentation drafter;
  consumes adversarial review for review-rewrite loop;
  consumes paper-writer's citation pool for reuse-from-paper)

This document pins the **interface contract** between them +
the **operational invariants** they share. The contract is the
load-bearing piece that lets each skill release independently
without breaking the others.

**Versioning:** the contract itself is versioned at the platform
level. Today: **CRAFT contract v0.1**. Bumping the contract
version requires platform-level review + a dual-version
support window (typically 1-2 minor releases per skill).

---

## 2. Schema commitments

### 2.1 Producer schemas (other skills consume these)

| Schema | Producer | Version | Consumers | Stability |
|---|---|---|---|---|
| `adversarial-review-paper.v3` | adversarial | v3 (since v0.7.0) | paper-writer | Stable through CRAFT v1.x |
| `adversarial-review-presentation.v3` | adversarial | v3 (since v0.7.0) | presentation-maker | Stable through CRAFT v1.x |
| `adversarial-review-plan.v3` | adversarial | v3 | (external; no CRAFT consumer yet) | Stable through CRAFT v1.x |
| `adversarial-review-project.v3` | adversarial | v3 | (external; no CRAFT consumer yet) | Stable through CRAFT v1.x |
| `claim_inventory.tsv` | paper-writer | v1 | (external integrators) | Stable through CRAFT v1.x |
| `citation_pool.json` | paper-writer | v1 | presentation-maker (reuse-from-paper path; D-009) | Stable through CRAFT v1.x |
| `slide_spec.v1` | presentation-maker | v1 | (external integrators) | Stable through CRAFT v1.x |
| `compose-fragment.v1` / `compose-fragment.v2` | presentation-maker | v1 + v2 (v0.4 fused-notes shape) | (internal to presentation-maker; documented for forensics) | Stable through CRAFT v1.x |
| `layout-overlaps.v1` | presentation-maker | v1 (v0.8.0 G.10-A) | (cascade Tier-1; external integrators) | Stable through CRAFT v1.x |
| `content-overflow.v1` | presentation-maker | v1 (v0.8.0 G.10-C) | (cascade Tier-1 + revise_loop) | Stable through CRAFT v1.x |
| `review-cascade.v1` | paper-writer + presentation-maker | v1 (M4b pattern) | (external integrators; future review systems) | Stable through CRAFT v1.x |

### 2.2 Schema-bump policy

**Non-breaking additions** (new fields, new finding kinds, new
optional content) ship at patch-version-bump of the producer
skill. No contract version bump. Consumer skills MAY adopt the
new field on their own cadence.

**Breaking changes** (renamed fields, changed semantics, removed
fields) require:

1. Discussion at the platform-level review (PR against
   `CRAFT-CONTRACT.md`).
2. **Dual-version support window** in the producer skill: emit
   BOTH old and new schema shape for at least one minor release
   cycle (~3 months typical).
3. Coordinated bump of all consumers within the support window.
4. CRAFT contract version bump (v0.1 → v0.2, etc.).
5. Entry in `CROSS-SKILL-RELEASE.md` documenting the migration.

**Deprecation notice convention:** when a field is being deprecated,
the producer schema's `schema_version` field accepts a hint
suffix (`v3` → `v3.deprecated-field-X-removed-at-v4`) for
operator visibility. Consumers should warn-on-deprecated-field-use
during the support window.

### 2.3 Specific schema details

The full schema specifications live in each producer skill's
repo (`CONTRACT.md` and `SPEC.md`). What follows is the
cross-skill-visible surface only.

**`adversarial-review-{type}.v3` shape:**

```json
{
  "schema_version": "adversarial-review-{paper,presentation,plan,project}.v3",
  "tier": "STRONG" | "THIN" | "EXPLORATORY",
  "findings": [
    {
      "id": "F001",
      "class": "...",        // see §2.3.1 below
      "severity": "P0" | "P1" | "P2" | "info",
      "confidence": "high" | "medium" | "low",
      "slide_id": <int> | null,  // for presentation
      "claim_id": "<string>" | null,  // for paper
      "issue": "<operator-readable description>",
      "fix_hint": "<actionable guidance>",
      "fix_target": "<prompt-name or stage-name>",
      "report_evidence": [...],
      ...
    },
    ...
  ],
  "summary": {
    "by_severity": {"P0": <int>, "P1": <int>, ...},
    "by_class": {"<class>": <int>, ...}
  }
}
```

**Finding class enum (v3):**

For `--type paper`:
- `register_drift`, `claim_evidence`, `central_objection`,
  `citation_reality`, `unbacked_quantitative`, `methods_gap`,
  `figure_provenance`, `discussion_overreach`, `compliance`,
  `narrative_weakness` (legacy v2 alias; routes to
  `central_objection` in v3).

For `--type presentation`:
- `register_drift`, `claim_evidence`, `qa_softball`,
  `substory_arc`, `throughline`, `missing_slide`,
  `citation_reality`, `unbacked_quantitative`,
  `central_objection`, `content_overflow` (v0.8.0+; routes via
  presentation-maker's REVISE_CLASSES).

For `--type plan` + `--type project`: see beril-adversarial-skill
CONTRACT.md.

**Synthetic-id prefixes (assigned by consumer skills):**

- `F###` — adversarial-produced findings (the canonical source)
- `CO###` — content_overflow findings (presentation-maker; v0.8.1)
- `VQ###` — visual-QA findings (presentation-maker; v0.8.0 G.7)
- Future skills SHOULD use a similar 2-letter prefix for their
  synthetic findings to keep the namespace clean.

---

## 3. Operational commitments

### 3.1 The 4-zone draft layout

All three skills produce drafts under the KBase | BERIL 4-zone
convention:

```
<BERIL_ROOT>/projects/<project_id>/{papers,talks}/draft_N/
├── deliverable/           # audience-facing artifacts
├── narrative/             # decision artifacts (throughline, substory, etc.)
├── working/               # machine-readable intermediates
└── audit/                 # logs, cost, review outputs
```

This convention is **non-negotiable** for CRAFT membership.
External integrators reading CRAFT outputs can rely on this
layout being stable.

**Naming conventions inside the layout:**

- `deliverable/draft.{pptx,docx}` — the audience-facing artifact
- `deliverable/speaker-notes.md` (presentation-maker) /
  `deliverable/draft.md` (paper-writer) — secondary deliverable
- `narrative/00_throughline.md`, `narrative/02_substories.md` —
  decision sequence (per-skill specifics)
- `working/slide_spec.json` (presentation-maker) /
  `working/claim_inventory.tsv` (paper-writer) — canonical
  machine-readable spec
- `working/citation_pool.json` — citation source (paper-writer
  produces; presentation-maker consumes via D-009 reuse path)
- `audit/adversarial_review.{json,md}` — review output
- `audit/review_cascade.{json,md}` — cascade aggregate
- `audit/runs/run-N/summary.json` — per-run metadata
- `audit/state.json` — pipeline state for `--resume-from`

### 3.2 The `claude -p` subagent invocation pattern

Each CRAFT skill invokes Claude via `claude -p` subagents,
parsing stream-json output for cost + tool-use accounting. This
is the load-bearing primitive — the pattern that lets each skill
stand on its own without an Anthropic SDK dependency or auth
federation.

**Invariants:**

- Skills invoke `claude` via the user's `$PATH` (no hard-coded
  paths).
- Skills pass prompts as `claude -p <prompt-file>` invocations
  with structured input via stdin or named file paths.
- Skills parse stream-json output via a per-skill `stream_progress.py`-
  shaped parser. (Cross-skill consolidation of this parser is a
  v0.9+ candidate; not committed.)
- Skills RESPECT the user's existing Anthropic / CBORG auth
  configuration; they don't manage auth themselves.

**Coordinated response to upstream changes:** if Anthropic
deprecates or modifies the `claude -p` flag or the stream-json
output shape, CRAFT skills must coordinate a response. The
mechanism is `CRAFT-DEPENDENCIES.md` + the cross-skill release
runbook.

### 3.3 Install-skill discoverability

Each CRAFT skill MUST be independently installable:

```bash
pipx install <skill-package-name>
<skill-cli> install-skill <BERIL_ROOT>
```

regardless of CRAFT presence. The platform's `craft install-platform`
command IS a coordinator over the per-skill `install-skill`
invocations, not a replacement. A user can still install one
skill in isolation.

**Idempotency:** every `install-skill` must be safe to re-run.
Re-installing doesn't damage user-edited files outside the
skill's `.claude/skills/<name>/` deployment dir.

### 3.4 Environment variable contract

| Variable | Required by | Purpose |
|---|---|---|
| `CBORG_API_KEY` | paper-writer, presentation-maker (image-gen) | LLM access via LBL CBORG gateway |
| `GOOGLE_AI_STUDIO_API_KEY` | presentation-maker (image-gen, optional) | Direct Google AI Studio for image generation |
| `BERIL_ROOT` | all three (or explicit `--beril-root <path>` per invocation) | BERIL deployment location |

Skills read env vars from `<BERIL_ROOT>/.env` automatically (via
python-dotenv). Users do NOT need to `export` them in their
shell.

**Future variables MUST be added to this table** before any skill
starts depending on them.

### 3.5 Auto-memory convention

Each skill reads `.auto-memory/MEMORY.md` (workspace-level) on
startup, picking up cross-skill discoveries.

Categories of memory entries that cross-skill consumers should
expect:

- `reference_beril_*` — BERIL operational pitfalls + project-
  artifact conventions
- `reference_kberdl_*` — KBase Lakehouse schema details + database
  conventions
- `project_<skill>_*` — per-skill ongoing state pointers
- `reference_adversarial_*` — adversarial schema/CLI behavior
  notes

**Auto-memory hygiene:** when a skill makes a cross-skill-
relevant discovery (e.g., BERIL produces a new artifact type,
adversarial introduces a new finding class), the discovery
SHOULD be written to auto-memory as a `reference_*` entry so
other skills + future conversations pick it up.

### 3.6 The tiered review cascade pattern

Skills that have quality gates (paper-writer + presentation-maker
today; future review-system skills tomorrow) converge on the
same tiered cascade structure:

```
Tier 1: ~$0    Deterministic validators + read-if-present audit-JSONs
               P3-P5 short-circuit; P0 fails the tier
Tier 2: ~$0.05 Narrative-light Haiku review (advisory; never gates)
Tier 3: ~$0.50 Canonical adversarial review (the load-bearing tier)
```

**For new skills joining CRAFT:** if you produce findings that
should flow through the cascade, write them to a versioned
audit JSON at `audit/<your-skill>.json`. The platform's existing
cascade readers will (eventually) lift them at Tier 1 via
the read-if-present pattern.

---

## 4. Joining the platform (for future skills)

A new skill joins CRAFT when:

1. **It produces or consumes a CRAFT contract.** Examples:
   - A domain-specific reviewer that produces
     `adversarial-review-<type>.v3`-shape findings
   - A feedback-incorporation skill that consumes adversarial
     findings + drafter outputs
   - A research-quality-improvement skill that produces audit
     JSON consumed by the cascade
   - A cross-artifact reconciliation skill (paper-vs-presentation
     consistency)
   - A domain-translation skill (lay-audience versions)

2. **It conforms to §3 operational commitments:**
   - 4-zone draft layout
   - `claude -p` invocation pattern
   - Independently installable via `pipx install` +
     `<skill> install-skill <BERIL_ROOT>`
   - Env var contract (additions added to §3.4 table BEFORE
     adoption)
   - Auto-memory convention

3. **It maintains its own repo + release cycle.** Joining CRAFT
   does NOT require giving up the skill's independence. The
   platform references the skill via git submodule pinned to
   tagged releases.

4. **It commits to the platform's coordination mechanism:**
   - PRs against the platform repo when contract-touching
     changes happen
   - Participation in `CROSS-SKILL-RELEASE.md` runbook for
     coordinated releases
   - Updates to `CRAFT-DEPENDENCIES.md` when new external
     dependencies arise

### CRAFT does NOT require

- **Membership in any specific GitHub org.** The skill can live
  in any org (kbaseincubator, ArkinLaboratory, an external
  contributor's org, etc.) as long as the platform repo can
  reference it as a submodule.
- **A specific tech stack.** The skill can be Python + bash
  today; could be Rust or Go tomorrow as long as the
  install-skill pattern is respected + the `claude -p`
  invocation pattern works.
- **Surrendering the skill's independent identity.** Skills
  retain their own README + brand + release cadence.

### Joining process

1. Skill author drafts a "CRAFT membership proposal" describing
   what contract the skill produces/consumes + how it conforms
   to §3.
2. PR against the platform repo adding the skill as a candidate
   submodule.
3. Platform-level review by existing CRAFT skill maintainers +
   Adam (as panel-of-one for v0.x; broadened later).
4. Acceptance: PR merged; skill becomes a CRAFT submodule; first
   CRAFT release including the new skill bumps platform minor
   version (CRAFT v0.X → v0.(X+1)).
5. Skill author commits to ongoing participation per §4.4 above.

### Departing the platform

A skill that no longer fits the contract (significant divergence;
no longer maintained; org migration breaking the submodule
reference) can be removed from CRAFT. Process:

1. Removal proposal as a PR against the platform repo.
2. CRAFT contract review: which schemas does the departing skill
   produce? Are there CRAFT consumers? If yes, the consumers
   either (a) migrate to a replacement, (b) accept the schema
   becoming external/unsupported, or (c) the skill's removal
   is gated on a replacement being ready.
3. Platform major-version bump (CRAFT v0.X → v1.0 if the
   departure is significant) documenting the removal.
4. The skill continues to exist as a standalone skill; just no
   longer under the CRAFT platform's coordination.

---

## 5. Contract version history

| Version | Date | Change |
|---|---|---|
| v0.1 (draft) | 2026-06-03 | Initial draft. Captures the contract as it exists across adversarial v0.7.0.8, paper-writer v1.0.0, presentation-maker v1.0.0. |

(Future entries appended as the contract evolves.)

---

## 6. Contract review cadence

- **Quarterly:** review `CRAFT-DEPENDENCIES.md` for upstream
  changes (Anthropic deprecations, KBase | BERIL contract
  updates, image-gen provider shifts).
- **On schema bump:** review the affected section here + bump
  the contract version if breaking.
- **On new skill joining:** review §4 process + update §2.1
  table.
- **Annually:** review the operational commitments in §3 against
  actual practice; codify drift.

---

*This document is the CRAFT platform's interface pin. The
load-bearing operational invariants live here. Changes require
platform-level review.*
