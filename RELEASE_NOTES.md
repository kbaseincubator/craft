# CRAFT — Release Notes

## v0.1.2 (2026-06-03) — Node 24 action bumps

Pre-emptive fix for GitHub Actions Node.js 20 deprecation
(forced to Node 24 on June 16th, 2026). Bumps third-party action
versions to their Node-24-supporting releases:

- `actions/checkout@v4` → `actions/checkout@v5`
- `actions/setup-python@v5` → `actions/setup-python@v6`
- `actions/setup-node@v4` → `actions/setup-node@v5`
- `actions/upload-artifact@v4` → `actions/upload-artifact@v5`

v0.1.1 was running cleanly + green; this is the pre-emptive
upgrade so the June 16th deadline doesn't break us silently.

The first cross-skill-release-runbook entry would normally cover
a coordinated bump like this — but since none of the three
skills' workflows are affected (their CI is in their own repos),
this is a CRAFT-internal patch with no cross-skill coordination
needed.

## v0.1.1 (2026-06-03) — Phase 2 CI

Adds GitHub Actions workflows for continuous platform health-
checking + manual cross-skill smoke testing.

### What ships in v0.1.1

- **`.github/workflows/platform-ci.yml`** — Platform CI (cheap
  smoke). Runs on every push to main + every PR. Verifies:
  - Submodule pins resolve to tagged releases (strict policy)
  - Meta-package installs cleanly
  - `craft` CLI commands work
  - `pytest tests/` passes
  - Ruff lint + format clean

  Cost: $0 LLM, ~3 min wall-clock per run.

- **`.github/workflows/cross-skill-smoke.yml`** — Cross-Skill
  Smoke Test (full smoke). Behind manual trigger + quarterly
  cron + repository-dispatch event. Exercises:
  - Adversarial review on a BERIL fixture project
  - Paper-writer draft consuming the review
  - Presentation-maker draft consuming the review
  - Cross-artifact verification (all three deliverables produced)

  Cost: ~$10-15 LLM per run, ~60 min wall-clock. 90-min timeout
  + per-skill cost caps + `max_cost_usd` workflow input as
  guardrails. Requires repo secrets:
  `CBORG_API_KEY`, `SMOKE_BERIL_FIXTURE_TARBALL_URL`.

- **`.github/workflows/README.md`** — Maintainer notes
  explaining what each workflow does, when it fires, what it
  catches, what it doesn't, how to set up the secrets, and
  troubleshooting.

### Maintainer setup required (first-time)

The platform CI runs immediately (no secrets needed). The
cross-skill smoke requires two repo secrets to be configured
before it can run. See `.github/workflows/README.md` §3 for
the step-by-step setup. Both are optional for v0.1.1 ship — the
platform-CI is the active gating workflow; cross-skill-smoke is
behind manual trigger.

### What does NOT ship in v0.1.1

- **Repository-dispatch trigger from submodule repos** —
  deferred to v0.2.0. Until then, cross-skill smoke fires
  manually OR via the quarterly cron.
- **Code coverage tracking** — not in v0.1.x scope.
- **PyPI publishing automation** — CRAFT installs from git URLs;
  PyPI not required.
- **Python version matrix testing** — pinned to 3.12 for v0.1.x.

## v0.1.0 (2026-06-03) — Initial platform release

First CRAFT platform release. Substrate-only ship — the
infrastructure for coordinating the three skills + the
documentation surface. No new skill features.

### What ships in v0.1.0

- **Meta-package** `craft` installable via `pipx install
  git+https://github.com/kbaseincubator/craft.git@v0.1.0`.
  Transitively installs the three CRAFT skills as pinned
  dependencies.

- **CLI** `craft install-platform <BERIL_ROOT>` + `craft doctor
  [<BERIL_ROOT>]` + `craft version`. Coordinates per-skill
  install-skill invocations + verifies deployment health.

- **Pinned skill versions:**
  - beril-adversarial-skill **v0.7.0.9**
  - beril-paper-writer-skill **v1.0.1**
  - beril-presentation-maker-skill **v1.0.0**

  Pinned via the three submodules under `skills/` + the
  meta-package's `pyproject.toml` dependency list. Both pins must
  match; the platform CI smoke test (Phase 2 deliverable) will
  enforce this once enabled.

- **Documentation surface:**
  - `README.md` — platform landing
  - `PLATFORM-PROPOSAL.md` — architectural design + rationale
  - `CRAFT-CONTRACT.md` — cross-skill interface contract
  - `CRAFT-DEPENDENCIES.md` — upstream-change watchlist
  - `CROSS-SKILL-RELEASE.md` — coordinated-release runbook
  - `AUGMENTATION-STREAM-RETROSPECTIVE.md` — the architectural
    argument the platform validates

### What does NOT ship in v0.1.0

- **Cross-skill smoke test (CI).** Phase 2 deliverable. Until
  it lands, cross-skill compatibility is verified manually per
  the `CROSS-SKILL-RELEASE.md` runbook §3 Phase D.
- **Unified documentation site (MkDocs).** Phase 3 deliverable.
  Until it lands, per-skill docs live in each submodule's
  README + the platform-level docs at this repo's root.
- **GitHub Actions workflows.** Phase 2 deliverable.

### Phase progression

| Phase | Description | Status |
|---|---|---|
| 1 (substrate) | Meta-package + submodules + core docs | **DONE 2026-06-03 (this release)** |
| 2 (coordination) | GitHub Actions CI + smoke test + issue triage conventions | Pending |
| 3 (presentation) | MkDocs site + architectural diagrams | Pending |
| 4 (announcement) | Cross-reference from skill READMEs + workspace CLAUDE.md update | Pending |

### Skills' status at v0.1.0

| Skill | Version | Production-ready? | Notes |
|---|---|---|---|
| beril-adversarial-skill | v0.7.0.9 | Stable | v3 schema; consumed by both drafters |
| beril-paper-writer-skill | v1.0.1 | Yes (v1.0.0 shipped 2026-05-20; v1.0.1 patched adversarial exit-code routing) | Holistic-write pipeline; v1.x backlog at `V1_X_BACKLOG.md` in the skill repo |
| beril-presentation-maker-skill | v1.0.0 | Yes (shipped 2026-06-03) | v0.8.1 architectural baseline + production-handoff framing in `HANDOFF.md` |

### Atlas is NOT in the platform

[beril-atlas-skill](https://github.com/ArkinLaboratory/beril-atlas-skill)
is metrology (observability) — distinct from CRAFT's
research-artifact-production focus. Stays as its own skill with
its own release cycle. See [PLATFORM-PROPOSAL.md §3](PLATFORM-PROPOSAL.md)
for the rationale.
