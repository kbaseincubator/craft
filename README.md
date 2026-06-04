# CRAFT

**Co-Scientist Research Assessment & Framing Tools.** A
KBase | BERIL platform that augments the Co-Scientist research
workflow with adversarial review (assessment) and
human-consumable artifact drafting (framing: paper + presentation).

## The platform shape

CRAFT consists of three skills that compose:

| Skill | Purpose | Repo |
|---|---|---|
| **beril-adversarial-skill** | Review-as-data (Tier-0 assessment of research artifacts) | [kbaseincubator/beril-adversarial-skill](https://github.com/kbaseincubator/beril-adversarial-skill) |
| **beril-paper-writer-skill** | ICMJE-conformant manuscript drafting | [kbaseincubator/beril-paper-writer-skill](https://github.com/kbaseincubator/beril-paper-writer-skill) |
| **beril-presentation-maker-skill** | KBase-branded presentation drafting (talks + posters) | [kbaseincubator/beril-presentation-maker-skill](https://github.com/kbaseincubator/beril-presentation-maker-skill) |

The platform pins specific compatible versions of the three +
provides:

- **Unified install** via `pipx install craft` + `craft install-platform <BERIL_ROOT>`
- **Health-check** via `craft doctor [<BERIL_ROOT>]`
- **Cross-skill contract** ([CRAFT-CONTRACT.md](CRAFT-CONTRACT.md))
- **Coordinated upstream-change response**
  ([CRAFT-DEPENDENCIES.md](CRAFT-DEPENDENCIES.md))
- **Cross-skill release runbook**
  ([CROSS-SKILL-RELEASE.md](CROSS-SKILL-RELEASE.md))

## The Tier-0 workflow (the platform's first delivery)

```
BERIL project artifacts
       │
       ▼
beril-adversarial-skill          ──→  audit/adversarial_review.json
       │  (Tier-0 assessment)
       │
       ├─────────────────────────┐
       ▼                         ▼
beril-paper-writer-skill    beril-presentation-maker-skill
       │  (manuscript draft        │  (presentation draft
       │   + review-rewrite        │   + review-rewrite
       │   loop)                   │   loop)
       ▼                         ▼
papers/draft_N/             talks/draft_N/
deliverable/draft.docx      deliverable/draft.pptx
```

Future skills will extend this workflow: domain-specific reviewers,
feedback-incorporation systems, research-quality-improvement
skills, cross-artifact reconciliation, domain-translation skills,
synthesis skills across BERIL projects.

## Quick start

After cloning a BERIL deployment + verifying `claude` is on
PATH:

```bash
# 1. Install CRAFT + its three skills (pipx transitively pulls them in)
pipx install git+https://github.com/kbaseincubator/craft.git@v0.2.3

# 2. Deploy all three skills into the BERIL deployment
craft install-platform <BERIL_ROOT>

# 3. Verify cross-skill integration
craft doctor <BERIL_ROOT>
```

After that, the three skills are individually usable via:

```bash
beril-adversarial review --type {paper,presentation,plan,project} <draft-or-project>
beril-paper-writer draft <project_id>
beril-presentation-maker draft <project_id>
```

See each skill's `HUB_INSTALL.md` for full per-skill operator
docs (linked from the skill repo READMEs).

## Versioning

CRAFT versions track the platform-level **contract** — the
cross-skill interface in [CRAFT-CONTRACT.md](CRAFT-CONTRACT.md).
Individual skills release on their own cadence; CRAFT bumps when
the contract surface changes OR when coordinated cross-skill
releases happen.

Current pins (CRAFT v0.2.3):

| Skill | Pinned version |
|---|---|
| beril-adversarial-skill | v0.7.0.10 |
| beril-paper-writer-skill | v1.0.2 |
| beril-presentation-maker-skill | v1.0.1 |

See [RELEASE_NOTES.md](RELEASE_NOTES.md) for the platform's
version history.

## Documentation

| Doc | Audience | What's in it |
|---|---|---|
| [PLATFORM-PROPOSAL.md](PLATFORM-PROPOSAL.md) | Maintainer / contributor | Architectural design: three-tier structure, motivations, costs, alternatives considered, decision rationale |
| [CRAFT-CONTRACT.md](CRAFT-CONTRACT.md) | Skill author / integrator | The cross-skill interface contract: schemas, operational commitments, joining-the-platform rules |
| [CRAFT-DEPENDENCIES.md](CRAFT-DEPENDENCIES.md) | Maintainer | Upstream-change watchlist: Anthropic, KBase BERIL, image-gen providers, etc. |
| [CROSS-SKILL-RELEASE.md](CROSS-SKILL-RELEASE.md) | Skill maintainer | Runbook for coordinated releases that touch multiple skills |
| [AUGMENTATION-STREAM-RETROSPECTIVE.md](AUGMENTATION-STREAM-RETROSPECTIVE.md) | Architectural reader | The architectural argument the platform validates: "can BERIL's skill-layer absorb a Co-Scientist capability stack via drop-in augmentation?" |
| Per-skill docs | Per skill, in each submodule under `skills/<name>/` | README, TUTORIAL, HUB_INSTALL, CONTRACT, SPEC, LAYOUT, DECISIONS, RELEASE_NOTES, HANDOFF |

## Status

**v0.1.0** — first platform release. Bundles three skills at
their current production versions:

- beril-adversarial-skill v0.7.0.9 (stable)
- beril-paper-writer-skill v1.0.1 (production-ready;
  shipped 2026-05-20 as v1.0.0, patched to v1.0.1 for
  adversarial exit-code routing)
- beril-presentation-maker-skill v1.0.0
  (production-ready; shipped 2026-06-03)

v0.1.0 is the substrate release. The platform structure
(meta-package, install coordinator, cross-skill contract) is
in place. Phase 2 (cross-skill CI smoke testing) + Phase 3
(unified docs site) follow.

## Repo structure

```
craft/
├── README.md                              # this file
├── PLATFORM-PROPOSAL.md                   # architectural design
├── CRAFT-CONTRACT.md                      # cross-skill contract
├── CRAFT-DEPENDENCIES.md                  # upstream-change watchlist
├── CROSS-SKILL-RELEASE.md                 # coordinated-release runbook
├── AUGMENTATION-STREAM-RETROSPECTIVE.md   # architectural argument
├── RELEASE_NOTES.md                       # platform version history
├── pyproject.toml                         # meta-package; pins 3 skills
├── src/craft/                             # CLI source
│   ├── __init__.py
│   └── cli.py
├── skills/                                # git submodules (pinned)
│   ├── beril-adversarial-skill/        → v0.7.0.9
│   ├── beril-paper-writer-skill/       → v1.0.1
│   └── beril-presentation-maker-skill/ → v1.0.0
└── tests/                                 # platform CLI + smoke tests
```

## Cloning with submodules

The skills are git submodules pinned at specific tags. To clone
with submodules included:

```bash
git clone --recurse-submodules https://github.com/kbaseincubator/craft.git
```

Or for an existing clone:

```bash
git submodule update --init --recursive
```

## Atlas — NOT in the platform

[beril-atlas-skill](https://github.com/ArkinLaboratory/beril-atlas-skill)
is metrology (observability across BERIL deployments) — distinct
from CRAFT's research-artifact-production focus. Atlas stays as
its own skill with its own release cycle. See
[PLATFORM-PROPOSAL.md §3](PLATFORM-PROPOSAL.md) for the
rationale.

## License

MIT (see [LICENSE](LICENSE)). The three submodules carry their
own LICENSE files; the platform license applies only to the
CRAFT-specific code + docs (the `src/craft/` package + the
workspace-root markdown files).
