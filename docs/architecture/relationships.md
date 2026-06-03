# Skill relationships

How the three CRAFT skills compose. This page walks the
data-flow contract — who produces what, who consumes what, what
sits behind the workflow that the [home page diagram](../index.md)
shows.

## Data-flow contract

```mermaid
flowchart TB
    subgraph BERIL["BERIL project artifacts (input)"]
        R[REPORT.md]
        RP[RESEARCH_PLAN.md]
        NB[notebooks/*.ipynb]
        FG[figures/]
    end

    subgraph ADV[beril-adversarial]
        ADV_CORE[review pipeline]
    end

    subgraph PW[beril-paper-writer]
        PW_DRAFT[holistic draft]
        PW_REVISE[review-rewrite loop]
    end

    subgraph PM[beril-presentation-maker]
        PM_COMPOSE[per-substory compose]
        PM_REVISE[review-rewrite loop]
    end

    subgraph ART_ADV["audit/adversarial_review.{json,md}"]
        SCHEMA_PAPER[adversarial-review-paper.v3]
        SCHEMA_PRES[adversarial-review-presentation.v3]
        SCHEMA_PROJ[adversarial-review-project.v3]
    end

    subgraph ART_PW["papers/draft_N/"]
        PW_DOCX[deliverable/draft.docx]
        PW_CITES[working/citation_pool.json]
        PW_CLAIMS[working/claim_inventory.tsv]
    end

    subgraph ART_PM["talks/draft_N/"]
        PM_PPTX[deliverable/draft.pptx]
        PM_NOTES[deliverable/speaker-notes.md]
        PM_SPEC[working/slide_spec.json]
    end

    R --> ADV_CORE
    RP --> ADV_CORE
    NB --> ADV_CORE
    FG --> ADV_CORE
    R --> PW_DRAFT
    RP --> PW_DRAFT
    NB --> PW_DRAFT
    FG --> PW_DRAFT
    R --> PM_COMPOSE
    RP --> PM_COMPOSE
    NB --> PM_COMPOSE
    FG --> PM_COMPOSE

    ADV_CORE --> ART_ADV
    SCHEMA_PAPER --> PW_REVISE
    SCHEMA_PRES --> PM_REVISE

    PW_DRAFT --> ART_PW
    PW_REVISE --> ART_PW
    PM_COMPOSE --> ART_PM
    PM_REVISE --> ART_PM

    PW_CITES -.->|D-009 reuse path| PM_COMPOSE

    classDef art fill:#f9f,stroke:#333,stroke-width:1px
    classDef skill fill:#bbf,stroke:#333,stroke-width:2px
    classDef input fill:#ffd,stroke:#333,stroke-width:1px
    classDef output fill:#bfb,stroke:#333,stroke-width:1px
    class R,RP,NB,FG input
    class ADV,PW,PM skill
    class ART_ADV art
    class ART_PW,ART_PM output
```

## Who produces what

| Producer | Schema / artifact | Version | Consumer(s) |
|---|---|---|---|
| adversarial | `adversarial-review-paper.v3` | v3 (since v0.7.0) | paper-writer |
| adversarial | `adversarial-review-presentation.v3` | v3 (since v0.7.0) | presentation-maker |
| adversarial | `adversarial-review-plan.v3` | v3 | (external; no CRAFT consumer yet) |
| adversarial | `adversarial-review-project.v3` | v3 | (external; no CRAFT consumer yet) |
| paper-writer | `claim_inventory.tsv` | v1 | (external integrators) |
| paper-writer | `citation_pool.json` | v1 | presentation-maker (D-009 reuse-from-paper path) |
| presentation-maker | `slide_spec.v1` | v1 | (external integrators) |
| presentation-maker + paper-writer | `review-cascade.v1` | v1 (M4b pattern) | (external integrators; future review systems) |

The full schema table + stability guarantees lives in the
[cross-skill contract §2](contract.md).

## The 4-zone draft layout

Every CRAFT skill produces drafts under the same KBase | BERIL
convention:

```
<BERIL_ROOT>/projects/<project_id>/{papers,talks}/draft_N/
├── deliverable/           # audience-facing artifacts (.docx, .pptx)
├── narrative/             # decision artifacts (throughline, substory)
├── working/               # machine-readable intermediates (.json, .tsv)
└── audit/                 # logs, cost, review outputs
```

This is non-negotiable for CRAFT membership. External
integrators reading CRAFT outputs can rely on it being stable.
See [contract §3.1](contract.md) for the canonical naming
conventions inside each zone.

## The review-rewrite loop

Both drafter skills (paper-writer + presentation-maker) consume
adversarial review the same way:

```mermaid
flowchart LR
    D[draft_N/<br/>working/spec.json] --> A[adversarial review]
    A --> R[audit/<br/>adversarial_review.json]
    R --> REV[revise loop:<br/>read findings →<br/>route to fix targets →<br/>regenerate]
    REV --> D2[draft_N+1/<br/>or in-place rewrite]
```

The drafter:

1. Produces a draft with full audit trail in `audit/`.
2. The user (or `craft` orchestration) runs adversarial review
   against the draft.
3. The drafter's `revise` verb (paper-writer:
   `beril-paper-writer revise`; presentation-maker:
   `beril-presentation-maker revise`) reads the adversarial JSON
   from `audit/adversarial_review.json`, routes each finding to
   its `fix_target` prompt/stage, and regenerates either
   in-place or to a new `draft_N+1`.

The contract here is: **both drafters consume the same v3
schema shape**. Adversarial doesn't need per-consumer-skill
output; the consumers do the routing.

## Cross-skill independence

Despite the composition, each skill can run **fully independently**:

- You can run `beril-adversarial review --type project` without
  ever invoking paper-writer or presentation-maker. The review
  is useful on its own.
- You can run `beril-paper-writer draft` without an adversarial
  review present. The drafter just skips the revise loop.
- You can run `beril-presentation-maker draft` without either
  paper-writer or adversarial. Same — revise loop becomes a
  no-op; reuse-from-paper path becomes a no-op.

CRAFT is the layer that makes the composition **explicit and
testable**. The skills' independence is preserved.

## The Tier-0 workflow

Putting it together — the platform's first delivery:

```mermaid
sequenceDiagram
    participant U as User / orchestrator
    participant A as beril-adversarial
    participant P as beril-paper-writer
    participant V as beril-presentation-maker

    U->>A: review --type project <id>
    A-->>U: audit/adversarial_review.{json,md} (project-level)

    par paper + presentation in parallel
        U->>P: draft <id>
        P-->>U: papers/draft_1/deliverable/draft.docx
        U->>P: revise (consumes audit/adversarial_review.json — paper-shape)
        P-->>U: papers/draft_1/deliverable/draft.docx (revised)
    and
        U->>V: draft <id> --tier STRONG --mode talk-30
        V-->>U: talks/draft_1/deliverable/draft.pptx
        Note over V,P: D-009 reuse path: V consumes P's citation_pool.json
        U->>V: revise (consumes audit/adversarial_review.json — presentation-shape)
        V-->>U: talks/draft_1/deliverable/draft.pptx (revised)
    end

    U->>A: review --type paper <papers/draft_1>
    U->>A: review --type presentation <talks/draft_1>
    A-->>U: per-artifact adversarial review (for final assessment)
```

The platform doesn't *enforce* this sequence; the skills
coordinate via the artifacts they write under the project's
draft directories. See [first run](../quick-start/first-run.md)
for the actual commands.

## See also

- [Cross-skill contract](contract.md) — the full schema + invariants pin.
- [Augmentation stream retrospective](retrospective.md) —
  how these three skills came to exist as a coherent stream.
- Per-skill operator docs: [adversarial](../skills/adversarial.md),
  [paper-writer](../skills/paper-writer.md),
  [presentation-maker](../skills/presentation-maker.md).
