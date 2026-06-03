# CRAFT — Release Notes

## v0.2.1 (2026-06-03) — Skill repos migrated to kbaseincubator + flipped public

The three skill repos transferred from `ArkinLaboratory` to
`kbaseincubator` and flipped public. With CRAFT already public
(v0.2.0), `pipx install` of CRAFT is now fully unauthenticated
— external operators no longer need read access to any
ArkinLaboratory repo.

This is a coordination-layer release (no skill version bumps;
no contract change). The skill versions CRAFT pins are
unchanged from v0.2.0:

- `beril-adversarial-skill @ v0.7.0.9`
- `beril-paper-writer-skill @ v1.0.1`
- `beril-presentation-maker-skill @ v1.0.0`

### What changed in v0.2.1

`pyproject.toml`:

- Three `dependencies` URLs flipped to `kbaseincubator/<skill>`.
- Comment updated to note the migration.

`.gitmodules`:

- Three submodule URLs flipped to `kbaseincubator/<skill>`.
- `git submodule sync` applied locally + committed.

`src/craft/cli.py`:

- `craft doctor`'s "install with pipx install ..." hint now
  points at `kbaseincubator` URLs.

`.github/workflows/cross-skill-smoke.yml`:

- Skill install URLs + filed-issue links flipped to
  `kbaseincubator`.

`README.md`:

- Removed the "skill repos are private" note from the install
  section.
- Skill repo table now points at `kbaseincubator/...`.
- pipx install example bumped to `@v0.2.1`.

`docs/quick-start/install.md`:

- Removed the "skill repo access" note.
- pipx install example bumped to `@v0.2.1`.

`docs/operations/troubleshooting.md`:

- Per-skill issue-tracker links + install commands updated to
  `kbaseincubator`.

`CRAFT-DEPENDENCIES.md`:

- Open-issue links updated to `kbaseincubator/...` (where the
  issues now live after the transfer).

`PLATFORM-PROPOSAL.md`:

- Tier-1 substrate's example repo URL + docs site URL updated
  to `kbaseincubator/...` to match the executed plan (was
  `ArkinLaboratory/...` in the proposal). The other
  ArkinLaboratory mentions in §4 are illustrations of "skill
  can live in any org" and stay as is.

### What's NOT in v0.2.1

- **No change to skill versions.** The CRAFT pins are still
  `adversarial v0.7.0.9 / paper-writer v1.0.1 /
  presentation-maker v1.0.0`. The two skill-side CI-portability
  issues (paper-writer `--auto-pick`, presentation-maker
  orchestrator Python discovery) remain open at their new
  `kbaseincubator` tracker locations.
- **No atlas migration.** `beril-atlas-skill` stays at
  `ArkinLaboratory` per the platform proposal — it's separable
  metrology, not in CRAFT.
- **No `AUGMENTATION-STREAM-RETROSPECTIVE.md` skill-table
  update.** The retrospective's per-skill table captures the
  state at the time of the retrospective (skill repos were at
  `ArkinLaboratory` then). It's a historical snapshot, not a
  current pointer.

### Verification

Local `pipx install --force git+https://github.com/kbaseincubator/craft.git@v0.2.1`
from a fresh shell with no `gh auth` should now succeed
end-to-end. The cross-skill smoke (next CI run) exercises the
same install path on a fresh Ubuntu runner.

---

## v0.2.0 (2026-06-03) — Unified MkDocs documentation site

Ships the Tier-3 presentation layer the platform proposal calls
for: a unified MkDocs Material docs site, auto-deployed to
GitHub Pages via `mkdocs gh-deploy` on push to main.

### What changed in v0.2.0

`docs/` (new):

- `index.md` — platform landing with the Tier-0 workflow
  mermaid diagram.
- `quick-start/` — install → first-run → verify walkthrough.
- `architecture/` — platform-structure + cross-skill contract
  (auto-pulled from `CRAFT-CONTRACT.md`) + skill relationships
  diagram + augmentation-stream retrospective (auto-pulled
  from `AUGMENTATION-STREAM-RETROSPECTIVE.md`).
- `skills/` — per-skill operator pages with the skill README
  auto-pulled from each submodule via the `include-markdown`
  plugin.
- `operations/` — coordinated release runbook (auto-pulled from
  `CROSS-SKILL-RELEASE.md`) + upstream dependencies (auto-pulled
  from `CRAFT-DEPENDENCIES.md`) + GitHub Actions setup
  (auto-pulled from `.github/workflows/README.md`) +
  troubleshooting decision tree.
- `extending/` — `adding-a-skill.md` (the formal join process)
  + `external-contributors.md` (scope + conventions).
- `reference/` — release notes (this file, auto-pulled) +
  platform proposal (auto-pulled from `PLATFORM-PROPOSAL.md`).

`mkdocs.yml`:

- MkDocs Material theme; light/dark toggle (indigo palette);
  navigation tabs + sections; search; content.code.copy +
  content.action.edit.
- `pymdownx.superfences` + `mermaid` custom-fence — diagrams
  ship as text.
- `pymdownx.snippets` + `include-markdown` plugin — auto-pull
  per-skill READMEs from submodules; auto-pull platform-level
  docs from repo root.
- Flat nav (Home / Quick Start / Architecture / Skills /
  Operations / Extending / Reference); 19 markdown pages total.

`.github/workflows/docs.yml` (new):

- Triggered on push to main (paths-filtered to docs/ + root
  doc files) + manual dispatch.
- Checks out with `submodules: recursive` so include-markdown
  can read per-skill READMEs.
- Installs `mkdocs-material`, `mkdocs-include-markdown-plugin`,
  `pymdown-extensions`.
- Runs `mkdocs build` then `mkdocs gh-deploy --force --clean`.
- 10-minute timeout; concurrency-grouped so docs deploys
  don't pile up.

`.gitignore`:

- Added `site/` (MkDocs build output) + `.mkdocs-venv/` (local
  preview venv).

### Local build verification

Build verified clean locally (46 warnings, all from per-skill
READMEs containing intra-repo links that exist on GitHub but
aren't in the docs/ tree; 0 errors; site renders correctly).

### One-time GitHub Pages setup needed

First docs deploy needs the GitHub Pages source set to the
`gh-pages` branch:

1. https://github.com/kbaseincubator/craft/settings/pages
2. "Build and deployment" → Source → "Deploy from a branch"
3. Branch: `gh-pages` / `(root)`
4. Save.

After that the docs workflow handles deploys automatically on
push to main.

### Site URL

After Pages activates: https://kbaseincubator.github.io/craft/

---

## v0.1.4 (2026-06-03) — Smoke narrowed to adversarial-only + fixture cleanup

First end-to-end cross-skill smoke run (26904057672) succeeded
at adversarial review on a real BERIL project but surfaced two
skill-level CI-portability gaps:

  paper-writer issue #1 — `draft` halts at the throughline-pick
    gate by architectural intent. No `--auto-pick` flag exists
    for unattended runs. The CRAFT smoke can't drive paper-writer
    end-to-end until the skill adds a CI/unattended mode.
    Filed: https://github.com/ArkinLaboratory/beril-paper-writer-skill/issues/1

  presentation-maker issue #1 — bash orchestrator can't discover
    the pipx-installed Python interpreter on a fresh GitHub
    Actions runner. The orchestrator works on Adam's hub
    deployment but fails in clean CI.
    Filed: https://github.com/ArkinLaboratory/beril-presentation-maker-skill/issues/1

This release narrows the cross-skill smoke to adversarial-only +
documents the limitations as known cross-skill-smoke caveats.

### What changed in v0.1.4

`.github/workflows/cross-skill-smoke.yml`:

- Removed the `Smoke — paper-writer draft` + `Smoke —
  presentation-maker draft` steps (commented out with linked
  issue markers + a comment explaining the descope).
- Narrowed `Verify artifacts produced` to check only
  `ADVERSARIAL_REVIEW_*.md` (the actual output format for
  `--type project`; the original verify step was looking for a
  JSON file that only `--type paper` and `--type presentation`
  produce).
- Fixed the failure-artifact-upload step to target only the
  smoke project subdir, not the entire `projects/` tree (the
  upstream BERIL repo has 100+ projects; the v0.1.3 upload was
  hundreds of MB).
- Fixed the sparse-checkout pattern bug: YAML heredocs preserve
  YAML indentation as literal whitespace in the heredoc content,
  which sparse-checkout treated as part of the pattern + matched
  everything. Switched to `printf` with explicit newlines.

`CRAFT-DEPENDENCIES.md`:

- New §6 "Known cross-skill-smoke limitations" documenting both
  open skill issues + the "when these land, re-broaden the smoke"
  checklist.

`pyproject.toml` + `src/craft/__init__.py`: version 0.1.3 → 0.1.4.

### Current smoke cost + scope

- Cost: ~$1-2 per run (just adversarial review on a real BERIL
  project)
- Wall-clock: ~10-15 min
- What it validates: adversarial CLI works on a clean runner;
  CRAFT install-platform deploys all three skills cleanly;
  sparse-checkout against the pinned BERIL commit works; CRAFT
  doctor passes
- What it does NOT validate (pending skill issues): paper-writer
  end-to-end, presentation-maker end-to-end, full Tier-0 workflow

### When the skill issues land

Per CRAFT-DEPENDENCIES.md §6, restoration is a 5-step process:
bump pin → restore smoke steps → restore artifact checks →
restore cost-summary loop → tag a CRAFT minor release.

## v0.1.3 (2026-06-03) — Cross-skill smoke: live BERIL repo via sparse-checkout

Pivots the cross-skill smoke from a static tarball fixture to a
live-BERIL-repo sparse-checkout. Eliminates fixture-drift risk
+ removes the operational chore of maintaining a separate
fixture artifact.

### Why

The original tarball approach (v0.1.1) required uploading + maintaining a
static BERIL project tarball at a private repo, with manual updates
when BERIL conventions evolved. The live-repo approach instead clones
a specific project subdirectory from the live BERIL repo at a pinned
commit SHA — exercises CRAFT against actual BERIL conventions, with
no drift.

### What changed

`.github/workflows/cross-skill-smoke.yml`:

- Removed: `SMOKE_BERIL_FIXTURE_TARBALL_URL` secret +
  `curl + tar -xz` extraction.
- Added: three repo **variables** (visible in UI; non-sensitive):
  - `SMOKE_BERIL_REPO` — e.g.
    `kbaseincubator/BERIL-research-observatory`
  - `SMOKE_BERIL_COMMIT` — full SHA for reproducibility
  - `SMOKE_BERIL_PROJECT_ID` — project subdir name
- Added: git sparse-checkout against the pinned commit, fetching
  only `projects/<PROJECT_ID>/` + `.claude/skills/` (~5-20 MB
  vs. the full 400+ MB BERIL repo).
- Pre-flight diagnostic now lists all four required config items
  + tells the operator exactly which one is missing.

`.github/workflows/README.md` — §2 + §3 rewritten with the
secrets-vs-variables rationale + the four-step setup walk-through.

### Required config (configure at the kbaseincubator/craft repo)

One secret:
- `CBORG_API_KEY` (same value as before)

Three new variables (NOT secrets — they're non-sensitive):
- `SMOKE_BERIL_REPO`
- `SMOKE_BERIL_COMMIT`
- `SMOKE_BERIL_PROJECT_ID`

See `.github/workflows/README.md` §3 for the step-by-step.

### Maintainer ongoing task

Bump `SMOKE_BERIL_COMMIT` quarterly so smoke exercises against
recent BERIL conventions. Tag each bump as a CRAFT patch release.

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
its own release cycle. See [PLATFORM-PROPOSAL.md §3](https://github.com/kbaseincubator/craft/blob/main/PLATFORM-PROPOSAL.md)
for the rationale.
