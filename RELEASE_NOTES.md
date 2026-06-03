# CRAFT — Release Notes

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
