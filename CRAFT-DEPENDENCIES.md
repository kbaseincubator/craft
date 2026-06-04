# CRAFT-DEPENDENCIES.md — Upstream-Change Watchlist

**Platform:** CRAFT (Co-Scientist Research Assessment & Framing
Tools)
**Date:** 2026-06-03 (initial)
**Review cadence:** Quarterly, OR when an upstream announces a
deprecation, OR when CRAFT-DEPENDENCIES.md is referenced from a
CROSS-SKILL-RELEASE.md runbook execution.

**Purpose:** Track every external dependency the three CRAFT
skills lean on, with version notes + "last verified working
with" dates. Coordinated response to upstream changes is the
mechanism this document enables — Anthropic deprecations,
KBase | BERIL contract updates, image-gen provider shifts,
schema bumps all hit this list before they hit the skills.

The skills today depend on stable interfaces. This document
exists because they WILL change someday + early visibility
matters.

---

## How to use this document

1. **Quarterly review:** maintainer walks the table; updates
   "Last verified" dates; checks for vendor deprecation notices
   on the items.
2. **On Anthropic / KBase / vendor announcement:** if a
   deprecation hits an entry, file an issue at
   `kbaseincubator/craft` referencing this document + which
   skill(s) need to respond.
3. **On a CRAFT release:** confirm no entry needs an urgent
   action; bump "Last verified" for items that were exercised
   during the release smoke test.

---

## 1. Anthropic / Claude Code

The load-bearing dependency. Every CRAFT skill invokes Claude via
`claude -p` subagents. Anthropic's Claude Code CLI is the
substrate.

| Item | Current state | Last verified | Risk level | Watch for |
|---|---|---|---|---|
| `claude -p` flag (one-shot LLM invocation) | Stable | 2026-06-03 | Low | Deprecation or flag rename. Anthropic announces deprecations 30-90 days ahead in the [claude-code changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md). |
| stream-json output shape | Stable | 2026-06-03 | Low | Schema additions are non-breaking; renames/removals are. Each skill has a `stream_progress.py` parser that would break on a shape change. |
| Model availability (Sonnet 4.6, Opus 4.7) | Stable | 2026-06-03 | Medium | Model deprecations; CBORG mirror lag (~1-2 weeks behind direct Anthropic). |
| MCP tool surface | Evolving | 2026-06-03 | Low for CRAFT | The three skills don't currently consume MCP tools at runtime; if a skill adopts MCP, this row becomes load-bearing. |
| Auth model (Anthropic direct + CBORG gateway) | Stable | 2026-06-03 | Low | CBORG token policy changes; per-user quota shifts. |
| `CLAUDE_CODE_OPUS_4_6_FAST_MODE_OVERRIDE` env var | **DEPRECATED 06/01/2026** | 2026-06-03 | None | Removed; no CRAFT skill uses this env var, so no action needed. Listed here as a historical example of Anthropic's 30-90 day deprecation cadence. |

### Anthropic-side coordination notes

- The `claude-code` GitHub repo's `CHANGELOG.md` is the
  authoritative source for breaking changes.
- The platform's quarterly review should grep the changelog for
  the last 90 days of entries + cross-reference against the
  table above.
- If a deprecation lands that affects CRAFT skills, the
  `CROSS-SKILL-RELEASE.md` runbook coordinates the response.

---

## 2. KBase | BERIL

CRAFT skills install into `<BERIL_ROOT>/.claude/skills/` + read
KBase | BERIL project artifacts. The KBase | BERIL contract is
implicit but load-bearing.

| Item | Current state | Last verified | Risk level | Watch for |
|---|---|---|---|---|
| `.claude/skills/` discovery convention | Stable | 2026-06-03 | Low | Claude Code controls this; documented at the skill-loader level. |
| 4-zone draft layout (`deliverable / narrative / working / audit`) | Stable since BERIL v0.3.1 | 2026-06-03 | Low | Multiple CRAFT skills depend on this; BERIL changes would ripple through. |
| Project artifact conventions (`REPORT.md`, `RESEARCH_PLAN.md`, `notebooks/`, `figures/`) | Stable | 2026-06-03 | Low | New artifact types (e.g., `experiments/`) being added are non-breaking; renaming existing ones would be. |
| KBase Lakehouse database conventions | Stable; docs normalized 2026-06-03 | 2026-06-03 | Medium | "BERDL" is deprecated — the data layer is "KBase Lakehouse", the co-scientist is "BERIL". Documentation now uses these terms; operational artifacts (prompts, audit messages, code identifiers like `berdl_query`/`berdl_start`) still reference BERDL by design. |
| `<BERIL_ROOT>/.env` env-var convention | Stable | 2026-06-03 | Low | Any change to where env vars come from. |
| Sibling-skill discovery (e.g., paper-writer finds presentation-maker's draft) | Stable | 2026-06-03 | Low | Used by presentation-maker's D-009 "reuse-from-paper" path. |

### KBase | BERIL coordination notes

- BERIL's release cadence is not directly visible to CRAFT
  maintainers. The quarterly review should check the BERIL
  repo for recent commits to the skill-loader + draft-layout
  conventions.
- "BERDL" nomenclature is deprecated: the data layer is "KBase
  Lakehouse" and the co-scientist is "BERIL". CRAFT documentation
  was normalized to these terms on 2026-06-03. Operational
  artifacts (prompts, audit messages, code identifiers) still
  reference BERDL by design; a coordinated operational rename, if
  ever undertaken, is a separate v1.x consideration.

---

## 3. Python ecosystem

The three skills' direct Python dependencies. Listed by the
package name + which skill uses it.

| Package | Used by | Constraint | Last verified | Risk level | Watch for |
|---|---|---|---|---|---|
| `python-pptx>=0.6.23` | presentation-maker | Stable | 2026-06-03 | Low | python-pptx 1.0 release (currently 0.6.x; long-anticipated 1.0 jump). |
| `python-docx>=1.1.0` | paper-writer | Stable | 2026-06-03 | Low | `lxml` transitively bound; rare breaks. |
| `nbformat>=5.7.0` | paper-writer + presentation-maker | Stable | 2026-06-03 | Low | New cell-id requirement in future major; non-blocking for our use. |
| `Pillow>=10.0.0` | presentation-maker | Stable | 2026-06-03 | Low | Image-gen depends on Pillow for post-processing. |
| `requests>=2.31.0` | presentation-maker (image-gen client) | Stable | 2026-06-03 | Low | TLS / proxy behavior changes. |
| `lxml` (transitive via python-docx) | paper-writer | Stable | 2026-06-03 | Medium | Periodic compile / wheel issues on new Python releases. |
| `duckdb`, `pandas`, `numpy`, etc. | atlas-skill (NOT IN CRAFT) | n/a | n/a | n/a | Out of CRAFT's scope; managed separately. |

---

## 4. Image-gen providers

CRAFT presentation-maker generates AI illustrations for select
slides. Two providers + their auth models.

| Provider | Endpoint | Auth | Cost calibration | Last verified | Risk |
|---|---|---|---|---|---|
| **CBORG-Gemini** | LBL CBORG gateway | `CBORG_API_KEY` | ~$0.014/image (calibrated v0.3.3.2) | 2026-06-03 | Medium — CBORG quota policy + tenant model evolves |
| **Google AI Studio direct** | Google AI Studio API | `GOOGLE_AI_STUDIO_API_KEY` | ~$0.03/image (gemini-3-pro-image-preview) | 2026-06-03 | Medium — Google model availability + pricing changes; `gemini-3-pro-image-preview` is a preview-tier model |

### Image-gen coordination notes

- M5b's auto-discovery probe at `image_client.py` resolves the
  active model from the configured provider; if the model is
  renamed (e.g., `gemini-3-pro-image-preview` → `gemini-3-pro-image`
  GA), the probe surfaces the change at runtime.
- Provider deprecations are coordinated at the
  presentation-maker patch level; CRAFT bumps if the provider
  set materially changes.

---

## 5. BibTeX + citation databases

Paper-writer's citation pool resolves bibliographic references
via multiple paths.

| Source | Used for | Last verified | Risk |
|---|---|---|---|
| `pubmed.gov` API | DOI + PMID resolution | 2026-06-03 | Low — NCBI API stable; rate-limited |
| `crossref.org` API | DOI resolution + metadata | 2026-06-03 | Low |
| Local BibTeX files in project artifacts | Citation extraction | 2026-06-03 | Low |

Paper-writer handles failures gracefully (citations marked TBD
when resolution fails); citation-database outages don't block
draft production.

---

## 6. Known cross-skill-smoke limitations

The cross-skill smoke test (`.github/workflows/cross-skill-smoke.yml`)
was narrowed to **adversarial-only** in CRAFT v0.1.4 (2026-06-03)
after the first end-to-end run surfaced two skill-level CI-portability
gaps. Documented here so the limitation is visible + the smoke can
be re-broadened when the upstream fixes land.

| Skill | Issue | Filed | Status | Workaround |
|---|---|---|---|---|
| beril-paper-writer-skill | `draft` halts at the throughline-pick gate by design; no `--auto-pick` flag for CI/unattended runs | [issue #1](https://github.com/kbaseincubator/beril-paper-writer-skill/issues/1) | Open as of 2026-06-03 | Two-stage invocation (`draft` → parse handoff JSON → `continue --pick TL1`); not currently in smoke |
| beril-presentation-maker-skill | Bash orchestrator can't discover the pipx-installed Python interpreter on a fresh GitHub Actions runner | [issue #1](https://github.com/kbaseincubator/beril-presentation-maker-skill/issues/1) | Open as of 2026-06-03 | None viable from CRAFT side; the orchestrator's interpreter-discovery logic needs to read the `beril-presentation-maker` shim's shebang |

**When these land:**

1. Bump the affected skill's pinned version in CRAFT's
   `pyproject.toml` + the submodule.
2. Restore the smoke's `Smoke — paper-writer draft` +
   `Smoke — presentation-maker draft` steps (commented out in
   the workflow with anchor markers).
3. Restore the matching artifact checks in `Verify artifacts
   produced` (paper `.docx` + presentation `.pptx`).
4. Restore the cost summary's `papers/` + `talks/` aggregation.
5. Tag a CRAFT minor release noting the smoke surface expansion.

**Architectural note:** these are not CRAFT bugs. The cross-skill
smoke is doing exactly what it's designed to do — surface
clean-room-CI-vs-hub-deployment drift before it hits operators.
The paper-writer issue is a design-vs-CI tension; the
presentation-maker issue is a portability bug. Both belong in the
skill repos, not CRAFT.

---

## 7. Cross-skill dependencies

The internal CRAFT contract surface. See `CRAFT-CONTRACT.md` §2
for the full schema list; this section is the operational
"what version of X does CRAFT pin" view.

| Producer | Schema | Pinned in CRAFT v0.1.0 | Consumers |
|---|---|---|---|
| beril-adversarial-skill | `adversarial-review-{paper,presentation}.v3` | v0.7.0.9 | paper-writer (v1.0.1) + presentation-maker (v1.0.0) |
| beril-paper-writer-skill | `claim_inventory.tsv`, `citation_pool.json` | v1.0.1 | presentation-maker via D-009 reuse-from-paper |
| beril-presentation-maker-skill | `slide_spec.v1`, `layout-overlaps.v1`, `content-overflow.v1`, `review-cascade.v1` | v1.0.0 | (external integrators) |

**Schema-bump policy** lives in `CRAFT-CONTRACT.md §2.2`. This
table is the snapshot of currently-pinned versions.

---

## 8. Operating-system + tooling

| Item | Used for | Last verified | Risk |
|---|---|---|---|
| `pipx` | Skill install path | 2026-06-03 | Low |
| `bash 4+` | Orchestrator scripts (each skill ships `presentation_maker.sh`, etc.) | 2026-06-03 | Low |
| `LibreOffice` (`soffice`) | Optional: PDF render + visual-QA | 2026-06-03 | Low (optional path; skills fall back gracefully) |
| `pdftoppm` (poppler) | Optional: visual-QA PNG rendering | 2026-06-03 | Low |
| Python 3.10+ | Required for all three skills | 2026-06-03 | Low |
| `git` 2.0+ | Submodule operations | 2026-06-03 | Low |

---

## 9. Review log

| Date | Reviewer | Changes | Action items |
|---|---|---|---|
| 2026-06-03 | Initial draft | Created document with current state | None (snapshot) |

(Future entries appended on each quarterly review or coordinated
release.)

---

*This document is updated whenever an upstream item changes
state. Last "Last verified" dates should never drift more than
90 days past the most recent quarterly review.*
