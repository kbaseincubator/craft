# CRAFT

**Co-Scientist Research Assessment & Framing Tools.** A KBase | BERIL
platform that augments the Co-Scientist research workflow with
adversarial review (assessment) and human-consumable artifact
drafting (framing — paper + presentation).

CRAFT is the **coordination wrapper** for three skills that compose
into a coherent Tier-0 research assessment workflow:

- **beril-adversarial-skill** — review-as-data; Tier-0 quality
  assessment of research artifacts
- **beril-paper-writer-skill** — ICMJE-conformant manuscript
  drafting with review-rewrite loop
- **beril-presentation-maker-skill** — KBase-branded scientific
  presentation drafting (talks + posters) with review-rewrite loop

The platform provides:

- **Unified install** via `pipx install craft` + `craft install-platform <BERIL_ROOT>`
- **Cross-skill interface contract** ensuring the three skills
  stay compositionally coherent
- **Coordinated upstream-change response** for Anthropic / KBase | BERIL /
  vendor evolution
- **Cross-skill smoke testing** in CI

## The Tier-0 workflow

```mermaid
flowchart LR
    A[BERIL project<br/>artifacts] --> B[beril-adversarial<br/>Tier-0 review]
    B --> C[adversarial_review.<br/>{json,md}]
    A --> D[beril-paper-writer<br/>holistic draft]
    A --> E[beril-presentation-maker<br/>per-substory compose]
    C --> D
    C --> E
    D --> F[papers/draft_N/<br/>deliverable/draft.docx]
    E --> G[talks/draft_N/<br/>deliverable/draft.pptx]
    D -.->|citation_pool.json| E
    F --> H[Ready for user<br/>assessment]
    G --> H

    classDef artifact fill:#f9f,stroke:#333,stroke-width:1px
    classDef skill fill:#bbf,stroke:#333,stroke-width:2px
    classDef output fill:#bfb,stroke:#333,stroke-width:1px
    class A artifact
    class B,D,E skill
    class C output
    class F,G output
```

The platform's **first delivery** is the Tier-0 workflow as
shown. Future deliveries extend it with new review systems,
feedback-incorporation skills, research-quality-improvement
skills, cross-artifact reconciliation, and synthesis skills —
see [Adding a skill](extending/adding-a-skill.md).

## Why CRAFT exists

The three skills work independently. CRAFT is the layer that
makes them work *together* — a platform-level contract + a
coordination mechanism + a unified presentation surface. See the
[platform proposal](reference/platform-proposal.md) for the
architectural rationale + the
[augmentation-stream retrospective](architecture/retrospective.md)
for the broader stream-level argument.

## Where to go from here

- **Trying CRAFT for the first time:** start with [Quick Start →
  Install](quick-start/install.md).
- **Adding a 4th skill to CRAFT:** see
  [Extending → Adding a skill](extending/adding-a-skill.md).
- **Inheriting CRAFT operations:** start with the
  [release runbook](operations/release-runbook.md) and the
  [troubleshooting](operations/troubleshooting.md) page.
- **Auditing the architectural choices:** the
  [platform proposal](reference/platform-proposal.md) is the
  source of truth.

## Skills not in CRAFT

[beril-atlas-skill](https://github.com/ArkinLaboratory/beril-atlas-skill)
is metrology (observability across BERIL deployments) — distinct
from CRAFT's research-artifact-production focus. It stays as its
own skill with its own release cycle. See
[platform proposal §3](reference/platform-proposal.md) for the
rationale.

## License + repo

- Repo: [kbaseincubator/craft](https://github.com/kbaseincubator/craft)
- License: MIT (the three submodules carry their own LICENSE files)
- Platform maintainer: [Arkin Laboratory](https://arkinlab.bio/)
