# CRAFT — Platform Proposal

**CRAFT** = **C**o-Scientist **R**esearch **A**ssessment &
**F**raming **T**ools — a KBase | BERIL platform that
augments the Co-Scientist research workflow with adversarial
review (assessment) and human-consumable artifact drafting
(framing: paper + presentation). Name selected 2026-06-03.

**Date:** 2026-06-03
**Status:** Proposal (NOT a plan). Decision input for Adam.
**Supersedes:** `CONSOLIDATED-REPO-ASSESSMENT.md` (kept for
historical reference; the framing was wrong — that doc treated
the question as "should 4 skills consolidate?" The real question
is "should the 3 production-skills become an explicit platform?")

---

## 1. Framing

### The platform: what it is

A coordinated set of three skills that **augment KBase | BERIL
with research-assessment capability**. Skills today:

- **beril-adversarial-skill** (review-as-data)
- **beril-paper-writer-skill** (ICMJE-conformant manuscript drafting)
- **beril-presentation-maker-skill** (KBase-branded presentation drafting)

The current first delivery is a coherent workflow:

1. **Tier-0 adversarial assessment** of a BERIL research artifact
   (project, plan, paper, presentation) — review-as-data via
   `beril-adversarial`.
2. **Two human-consumable artifacts** generated and reviewable
   inside the platform: the paper (paper-writer) and the
   presentation (presentation-maker), each with their own
   review-rewrite loop using adversarial v3 schema.
3. **Availability for future user assessment** alongside other
   BERIL artifacts (notebooks, REPORT.md, RESEARCH_PLAN.md,
   figures).

### What the platform is NOT

- **Not BERIL itself.** It sits on top of KBase | BERIL's existing
  skill-layer + `.claude/skills/` discovery + `claude -p` LLM
  invocation. Standalone repo, standalone release cycles, no
  BERIL-side changes required.
- **Not a kit of independent tools.** The three skills work
  individually but they are EXPLICITLY designed to compose: the
  adversarial skill is consumed by both the paper-writer's
  review-rewrite loop and the presentation-maker's review-rewrite
  loop. The platform codifies that contract.
- **Not the augmentation stream.** The augmentation stream
  (`augmentation-stream-plan.md`) was the dev-process framing
  that produced these skills. The platform is the PRODUCT shape
  of three of them (atlas is metrology + stays separate per the
  retrospective + this proposal's §3).
- **Not closed.** Future review systems, feedback-incorporation
  systems, research-quality-improvement skills are explicit
  extension points (§7).

### The forward trajectory

The current three skills are the v0.1 of the platform.
Future additions are *coherent extensions* with the same
interface contract (see §4):

- New review systems (e.g., domain-specific reviewers beyond
  the general adversarial)
- Feedback-incorporation systems (consuming review output, surfacing
  to authors)
- Research-quality-improvement skills (e.g., methods-drift
  detectors, reproducibility checkers, claim-grounding
  validators)
- Cross-artifact reconciliation skills (does the paper match
  the presentation? do both match the project plan?)

Each new skill joins the platform by conforming to the
`CRAFT-CONTRACT.md` interface (§4) and being added
to the meta-package's pinned dependency list.

## 2. The three-tier structure

The proposal's structural answer to "how do you give the three
skills a platform identity without breaking their independence"
is a three-tier wrapper around the existing repos. None of the
three skill repos changes substantively; the platform tier adds
coordination + presentation + governance.

### Tier 1 — the platform substrate

**Repo:** new at `ArkinLaboratory/craft`. Independent git
history from the skill repos.

**Contains:**

```
craft/
├── README.md                    # platform-level entry doc
├── PLATFORM-CONTRACT.md         # cross-skill interface pinning
├── PLATFORM-DEPENDENCIES.md     # upstream-change watchlist
├── CROSS-SKILL-RELEASE.md       # runbook for coordinated releases
├── pyproject.toml               # meta-package; lists 3 skills as deps
├── src/craft/
│   ├── __init__.py
│   ├── cli.py                   # `craft install-platform`
│   ├── install_platform.py      # orchestrates 3 install-skill calls
│   └── doctor.py                # checks all 3 skills installed cleanly
├── skills/                      # git submodules (NOT mono-repo subdirs)
│   ├── beril-adversarial-skill/    → submodule
│   ├── beril-paper-writer-skill/   → submodule
│   └── beril-presentation-maker-skill/ → submodule
├── docs/                        # MkDocs source for unified docs site
│   ├── mkdocs.yml
│   ├── index.md                 # platform landing
│   ├── tier-0-workflow.md       # the "what does this platform do" page
│   ├── adding-a-skill.md        # how to extend the platform
│   └── ...                      # per-skill pages pull from submodule READMEs
├── tests/
│   ├── platform_smoke/          # cross-skill integration tests
│   └── ...
└── .github/workflows/
    ├── platform-ci.yml          # runs on platform PRs
    └── cross-skill-smoke.yml    # runs when any submodule tags a release
```

**Key choice: git submodules, NOT mono-repo subdirs.** Each skill
stays in its own repo with its own release cycle + tags + issue
tracker. The platform references each at a specific tagged
commit (e.g., `beril-presentation-maker-skill @ v1.0.0`). Bumping
the platform's pin is an explicit, reviewable PR — exactly when
you want coordinated cross-skill release attention.

**Meta-package shape:** `pyproject.toml` lists the three skills
as pinned `pip` dependencies (`beril-paper-writer-skill==1.0.0`
etc.). `pipx install craft` transitively installs
all three. `craft install-platform <BERIL_ROOT>` runs
the three `install-skill` invocations in sequence + reports a
summary.

### Tier 2 — the coordination mechanism

This is the substantive new capability beyond the three skills'
existing operational surface. The coordination mechanism has
four components, all living in the platform repo:

**(a) `PLATFORM-CONTRACT.md`** — the cross-skill interface pin.
Codifies every contract the three skills share:

- The 4-zone draft layout (`deliverable/ narrative/ working/ audit/`)
- The audit-JSON schema versioning policy (`schema_version` field;
  non-breaking-add; deprecation-window-for-bumps)
- The adversarial v3 schema specifically (the consumer-side dep
  for paper-writer + presentation-maker)
- The `claude -p` subagent invocation pattern + stream-json output
- The `.claude/skills/` deployment convention
- The `CBORG_API_KEY` / `GOOGLE_AI_STUDIO_API_KEY` env var contract
- The auto-memory integration at `.auto-memory/MEMORY.md`

When a new skill joins the platform, it commits to this contract.
When the contract evolves (e.g., a new audit-JSON schema), the
change goes through a platform-level review.

**(b) `PLATFORM-DEPENDENCIES.md`** — the upstream-change watchlist.

Lists every external dependency the platform leans on:

- Anthropic Claude Code: `claude -p` flag, stream-json output
  shape, MCP tool surface, login model. (Today's research:
  `claude -p` is stable, but `CLAUDE_CODE_OPUS_4_6_FAST_MODE_OVERRIDE`
  was deprecated 06/01/2026 — pattern of narrow deprecations
  with 30-90 day notice is real.)
- KBase | BERIL: `.claude/skills/` discovery, draft-zone
  conventions, project-artifact contracts (REPORT.md, RESEARCH_PLAN.md,
  notebooks, figures).
- Python ecosystem: `python-pptx`, `python-docx`, `nbformat`,
  `Pillow`, `lxml` (transitive).
- Image-gen providers: CBORG-Gemini, Google AI Studio direct,
  their API surfaces.
- BibTeX / citation databases for paper-writer's resolution.

Each entry has a "last verified working with" date + a quarterly
review cadence. Anthropic and Google announce deprecations
30-90 days ahead; tracking actively means the platform has time
to respond before users notice.

**(c) `CROSS-SKILL-RELEASE.md`** — coordinated release runbook.

When a change touches all three skills (e.g., adversarial v3 → v4
schema bump), the runbook codifies:

- Which skill leads (usually the upstream producer of the
  changed contract, e.g., adversarial).
- Branch + PR order across the three repos.
- Test coordination: each consumer skill must pass tests against
  the new contract before the producer tags.
- Platform-level smoke test gate (see (d)).
- Release sequencing: producer tags first; consumers tag with
  their pinned dep bumped; platform meta-package tags last with
  all three submodules updated.
- Communication: ChangeLog entry on platform repo + per-skill
  RELEASE_NOTES.md.

**(d) Platform CI smoke test.**

A GitHub Action that runs when ANY submodule tags a new release:

1. Clones the platform repo + updates the submodule pin to the
   new tag.
2. Runs a cross-skill integration test (typical: small project
   → adversarial review → paper-writer drafts paper → consumes
   review → presentation-maker drafts presentation → consumes
   review → both ship). ~$10-15 LLM cost per smoke run.
3. Reports pass/fail to the platform issue tracker.

Catches "paper-writer v1.1.0 broke presentation-maker's
adversarial integration" within hours, not in production.
Acceptance cost: ~$50-100/month of CI LLM spend if smokes fire
quarterly per skill (3 skills × ~1 release per quarter).

### Tier 3 — the unified presentation

For end users, DOE leadership, future contributors. Built once,
reused continuously.

**(a) Platform landing page** at
`ArkinLaboratory.github.io/craft/`:

- One-paragraph "what is this platform" framing
- The Tier-0 workflow diagram (review → paper → presentation
  → ready for user assessment)
- Per-skill pages pulled from each submodule's README + TUTORIAL
  + HUB_INSTALL + HANDOFF + RELEASE_NOTES (auto-included via
  MkDocs)
- Architectural diagrams (the three skills' contract relationships
  + the KBase | BERIL substrate they sit on)
- "Adding a skill" page for future contributors

**(b) Unified install runbook.**

```bash
# One pipx install. Pulls all three skills as transitive deps.
pipx install craft

# One platform-install command. Runs the three install-skill
# invocations in sequence; reports a summary; verifies
# .claude/skills/ deployment.
craft install-platform <BERIL_ROOT>

# Verify cross-skill integration (doctor command — checks each
# skill is installed + dependencies present + .env populated).
craft doctor <BERIL_ROOT>
```

**(c) Architectural diagrams.** The current
`AUGMENTATION-STREAM-RETROSPECTIVE.md` is dev-process framing;
the platform docs site needs a clean product-facing diagram set:

- The Tier-0 workflow (input → review → paper + presentation
  → user assessment)
- The skill-contract relationships (who consumes whose schema)
- The platform substrate (where KBase | BERIL ends and the
  platform begins)
- The extension path (where new skills plug in)

**(d) Per-skill page generation.** MkDocs reads each submodule's
existing docs + presents them under a unified site nav. Per-skill
maintenance unchanged — skill authors edit their own README; the
platform site picks up the change on next build. No platform-
specific docs that skill authors need to maintain.

## 3. Atlas: explicitly NOT in the platform

Atlas is **metrology** — observability across BERIL deployments
+ learned-pattern indexing. The three production skills produce
research artifacts; atlas observes the patterns + drifts. Different
shape, different release cadence, different operational mode.

Atlas:
- Stays at `ArkinLaboratory/beril-atlas-skill`.
- Has its own pipx install + install-skill.
- Its own release cycle (build-once-observe).
- May INFORM the platform (atlas observations could surface
  cross-platform-skill issues, e.g., "users on platform v1.x
  consistently hit X failure mode"). Information flow only;
  no install dependency.

The platform does NOT depend on atlas; atlas does NOT depend on
the platform. They share the BERIL substrate + the auto-memory
convention but operate independently.

This is explicit per Adam's framing ("atlas is a separable
metrology package"). Confirmed by CONSOLIDATED-REPO-ASSESSMENT.md
§6 NF1 (atlas's DuckDB engine + observability model don't fit
into a content-production package).

## 4. The platform contract — what the three skills commit to

This section is the substantive content of `PLATFORM-CONTRACT.md`.
Sketched here; the actual file would be ~30-50 pages with full
schema definitions.

### 4.1 Schema commitments (consumer-producer contracts)

| Schema | Producer | Consumer(s) | Version |
|---|---|---|---|
| `adversarial-review-{paper,presentation}.v3` | adversarial | paper-writer, presentation-maker | v3 stable through platform v1.x |
| `slide_spec.v1` | presentation-maker | (external integrators) | v1 stable through platform v1.x |
| `claim_inventory.tsv` | paper-writer | (external integrators); presentation-maker reads via reuse-from-paper-writer | stable through platform v1.x |
| `citation_pool.json` | paper-writer | presentation-maker (reuse path) | stable through platform v1.x |
| 4-zone draft layout | all three | (external integrators) | stable since BERIL v0.3.1; non-negotiable |

**Schema-bump policy:**
- Non-breaking additions (new fields, new finding kinds) ship at
  patch-version-bump of producer skill.
- Breaking changes (renamed fields, changed semantics) require:
  - Platform-level discussion at `PLATFORM-DEPENDENCIES.md` review.
  - Dual-version support window (typically 1-2 minor releases).
  - Coordinated bump across producer + all consumers.

### 4.2 Operational commitments

- **Independent ship cycles.** Each skill releases on its own
  cadence (patch + minor). Major version bumps may be
  coordinated if they imply contract changes.
- **Backward compatibility within major.** A platform-v1.x
  patch release does NOT break a v1.x consumer of the schemas
  above.
- **Pipx install + install-skill discoverability.** Each skill's
  install path must work standalone (`pipx install <skill>` +
  `<skill> install-skill <BERIL_ROOT>`) regardless of platform.
- **`claude -p` invocation contract.** Each skill invokes Claude
  via the `claude -p` subagent pattern + parses stream-json
  output. Platform-level Anthropic deprecation response is
  coordinated.
- **Auto-memory convention.** Each skill reads `.auto-memory/MEMORY.md`
  on startup. Platform-level guidance on what cross-skill
  discoveries get auto-saved.

### 4.3 Joining the platform (for future skills)

A new skill joins the platform when:

1. It produces or consumes a contract relevant to the existing
   three (e.g., a new review system that produces
   `adversarial-review-<artifact>.v3`-shape findings; a feedback-
   incorporation skill that consumes them).
2. It conforms to the operational commitments in §4.2.
3. It maintains its own repo + release cycle (submodule pattern).
4. It commits to the platform's coordination mechanism (PRs
   against the platform repo when contract-touching changes happen).

The platform does NOT require:
- Membership in `ArkinLaboratory` GitHub org (could be external
  contributor's org, with the platform repo linking to it).
- A specific tech stack (the skill can be Python + bash today;
  could be Rust or Go tomorrow as long as the install-skill
  pattern is respected).
- Surrendering the skill's independent identity.

## 5. What this proposal LOSES vs. the status quo

Honest accounting:

- **Some operational complexity.** The submodule pattern adds a
  layer; cross-skill coordination is now explicit (good) but
  also requires discipline (cost).
- **Platform-level CI cost.** ~$50-100/month of LLM smoke spend
  (the cross-skill integration test).
- **Platform-level documentation burden.** Even though most of
  it is auto-generated from per-skill docs, the architectural
  diagrams + Tier-0 workflow page + extension docs need
  authoring + maintenance.
- **Decision cycle latency.** A change to `PLATFORM-CONTRACT.md`
  requires platform-level review, not just one-skill-author
  decision. Slows individual skill changes that touch the
  contract.

The status-quo independence is partially traded for coordination
visibility. Per Adam's framing this is the right trade.

## 6. What this proposal PRESERVES

The augmentation-stream architectural argument holds:

- Each skill remains independently installable + releasable.
- The "BERIL's skill-layer absorbs the capability stack" claim
  still stands — the platform is a coordination wrapper, not a
  refactor.
- Future external contributors can write a skill matching the
  augmentation pattern + optionally join the platform if it fits.
- Atlas stays at its own pace (observability, not content
  production).
- The 4-zone draft layout + schema-versioning discipline + tiered
  review cascade pattern continue as platform invariants.

## 7. Forward extension points

Future skills the platform can absorb (from Adam's framing +
inferred natural extensions):

| Future skill class | What it produces / consumes |
|---|---|
| Domain-specific reviewers (e.g., microbiome-specific, structural-bio-specific) | Produces adversarial-shape findings tuned to a domain; consumed by paper-writer + presentation-maker review loops |
| Feedback-incorporation systems | Consumes adversarial findings + drafter outputs; produces revised artifacts with reframing logs |
| Research-quality-improvement skills | Methods-drift detection, reproducibility checking, claim-grounding validation; produces audit JSON consumed by the cascade |
| Cross-artifact reconciliation | Does the paper match the presentation? Does both match the project plan? Produces reconciliation reports |
| Domain-translation skills | Produces lay-audience versions of papers / presentations; consumes the existing artifacts |
| Synthesis skills | Consumes multiple BERDL projects + produces meta-analyses |

Each follows the contract in §4. The platform absorbs them as
submodule additions + meta-package dep bumps.

## 8. Concrete next steps (if Adam approves the direction)

This proposal does NOT commit to any path. If Adam decides to
proceed:

**Phase 0 (decision, ~1 day):**
- Name selected: **CRAFT** (Co-Scientist Research Assessment &
  Framing Tools), 2026-06-03.
- Repo location TBD (`ArkinLaboratory/craft` is the default;
  alternatives: new GitHub org like `KBaseResearchAssessment`).
- Adam confirms whether to proceed with the three-tier structure
  as proposed.

**Phase 1 (substrate, ~3-5 days):**
- Create `ArkinLaboratory/craft` repo.
- Add three skills as git submodules pointing at their v1.0.0
  tags.
- Write meta-package pyproject.toml + `install-platform` CLI.
- Initial draft of `PLATFORM-CONTRACT.md` + `PLATFORM-DEPENDENCIES.md`
  + `CROSS-SKILL-RELEASE.md`.
- First platform release: `v0.1.0`.

**Phase 2 (coordination, ~2-3 days):**
- Set up platform CI (GitHub Actions; smoke test on submodule
  release).
- Set up platform issue tracker conventions (cross-skill labels,
  triage process).
- First cross-skill smoke run (small project end-to-end through
  all three skills via the platform).

**Phase 3 (presentation, ~1-2 days):**
- Set up MkDocs site at `ArkinLaboratory.github.io/craft/`.
- Draft architectural diagrams.
- Write the Tier-0 workflow page.
- Auto-include per-skill docs.

**Phase 4 (announcement + handoff, ~half day):**
- Cross-reference the platform from each skill's README.
- Update `augmentation-stream-plan.md` + workspace `CLAUDE.md`
  to point at the platform.
- Public announcement (if appropriate; depends on the audience).

**Total: ~8-12 days of work.** Distributed; can be paused at
any phase. Each phase produces a usable artifact.

## 9. Decision points for Adam

**ALL DECIDED 2026-06-03.** Recorded here for traceability:

1. **Platform name + repo name:** CRAFT
   (Co-Scientist Research Assessment & Framing Tools). Repo
   name: `craft`.

2. **Repo location:** **`kbaseincubator/craft`** (preferred);
   Adam has org-level access. Skills currently at
   `ArkinLaboratory/...` may also migrate to `kbaseincubator/...`
   for everything; if so, CRAFT's submodule references update
   to track the migration. Decision: skills migrate together
   with CRAFT setup OR skills migrate later as a separate
   move — TBD during Phase 1 setup based on what's least
   disruptive.

3. **Submodule pinning policy:** strict (tagged releases only;
   no `main`-tracking).

4. **Initial platform version:** `v0.1.0` for first ship. v1.0
   gated on adversarial reaching v1.0 (currently v0.7.0.8).

5. **CI provider:** GitHub Actions. Workflows live at
   `.github/workflows/` on the platform repo. Phase 2 will
   include explanatory notes on how the platform CI works so
   the maintainer (Adam) understands what's running + where.

6. **Docs hosting:** GitHub Pages on the platform repo.
   `kbaseincubator.github.io/craft/` is the natural URL.

7. **Atlas relationship:** Atlas is OUT of the platform. Atlas
   undergoing revisions; cross-referencing between CRAFT docs
   and atlas docs is acceptable; locale updates may be needed
   when atlas's repo location moves.
2. **Repo location.** `ArkinLaboratory/<name>` is the natural
   choice; alternatives include creating a new GitHub org
   (`KBaseResearchAssessment` or similar) if the platform's
   identity is meant to be distinct from the lab.
3. **Submodule pinning policy.** Pin to tagged releases (strict)
   OR pin to commits on each skill's `main` branch (looser, more
   flexible, less stable). Recommend strict; tag-only.
4. **Initial platform version.** `v0.1.0` is the natural start
   for an early proposal-shape platform. v1.0 when all three
   submodules are at v1.0 stably (presentation-maker just
   tagged v1.0.0; paper-writer is at v1.0.0; adversarial is
   at v0.7.0.8). Adversarial's v1.0 may be the gating signal.
5. **CI provider.** GitHub Actions is the natural fit (each
   skill already uses it). If Adam has a preference for
   self-hosted CI (e.g., a KBase Jenkins), that changes Phase
   2.
6. **Docs hosting.** GitHub Pages on the platform repo OR an
   external host (e.g., kbase.us subdomain). Determines MkDocs
   deploy target.
7. **Atlas relationship.** Confirmed OUT of the platform.
   Whether atlas's documentation cross-references the platform
   (and vice versa) is Adam's call.

## 10. Recommendation

**Adopt the three-tier structure.** It:

- Matches Adam's framing (three-skill platform; atlas separate).
- Solves the coordinated-upstream-change problem
  (`PLATFORM-DEPENDENCIES.md` + cross-skill CI).
- Solves the simplified-install problem (meta-package +
  `install-platform`).
- Solves the unified-documentation problem (MkDocs site with
  auto-included per-skill docs).
- Solves the future-extension-discoverability problem
  (`adding-a-skill.md` + `PLATFORM-CONTRACT.md`).
- Preserves what's working (independent skill ship cycles, the
  augmentation-stream architectural argument, atlas's autonomy).
- Adds explicit governance + presentation surface without
  forcing a refactor.

The total cost is ~8-12 days distributed; each phase produces a
usable artifact; pausable at any phase. Compared to the
benefits over a multi-year platform lifetime, the cost is
proportional.

**What to NOT do:**

- Do not fold atlas in.
- Do not consolidate the three skills into one repo subdirs.
- Do not force the three skills onto a single coordinated
  release cycle (independent patch/minor releases preserved;
  coordinated only for contract changes).
- Do not extract `beril_skill_common` infrastructure code yet
  — premature; the duplication is ~700-1000 lines + the
  cross-skill coupling cost would be higher than the de-dup
  benefit. Revisit in 6-12 months once the platform is stable.

---

*This document is a proposal for Adam's review. Decision is
Adam's; this proposal does not commit to any path.*
