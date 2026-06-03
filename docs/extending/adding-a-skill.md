# Adding a skill

CRAFT is **explicitly extensible**. The current three skills are
the v0.1 of the platform; future additions are coherent
extensions with the same interface contract.

This page is the process for adding a 4th (5th, Nth) skill.

## What qualifies as a CRAFT skill

A new skill joins CRAFT when it:

### Produces or consumes a CRAFT contract

Plausible categories:

- **Domain-specific reviewer** that produces
  `adversarial-review-<type>.v3`-shape findings (e.g.,
  metabolomics-specific reviewer, microbiome-specific reviewer).
- **Feedback-incorporation skill** that consumes adversarial
  findings + drafter outputs and produces structured
  feedback-to-author artifacts.
- **Research-quality-improvement skill** that produces audit
  JSON consumed by the cascade (e.g., methods-drift detector,
  reproducibility checker, claim-grounding validator).
- **Cross-artifact reconciliation skill** (does the paper match
  the presentation? do both match the project plan?).
- **Domain-translation skill** (lay-audience versions, internal-
  stakeholder versions, regulator-conformant versions).

If your skill produces structured findings, point your
schema at [contract §2](../architecture/contract.md) and bring
the schema spec to the platform review.

### Conforms to the operational commitments

All in [contract §3](../architecture/contract.md):

- **4-zone draft layout** (`deliverable/`, `narrative/`,
  `working/`, `audit/`).
- **`claude -p` subagent invocation pattern** + stream-json
  parsing.
- **Independently installable** via `pipx install` +
  `<skill> install-skill <BERIL_ROOT>`.
- **Env var contract** — any new env vars added to [contract
  §3.4](../architecture/contract.md) BEFORE adoption.
- **Auto-memory convention** at `<BERIL_ROOT>/.auto-memory/MEMORY.md`.

### Maintains its own repo + release cycle

Joining CRAFT does **NOT** require giving up the skill's
independence. The platform references the skill via a git
submodule pinned to tagged releases.

You keep:

- Your own GitHub repo (any org — kbaseincubator,
  ArkinLaboratory, your own org, an external contributor's).
- Your own release cadence with your own tags.
- Your own issue tracker + PR workflow.
- Your own internal docs (`SPEC.md`, `LAYOUT.md`, `DECISIONS.md`,
  `CONTRACT.md`).
- Your own README — CRAFT's docs site pulls it via
  `include-markdown`.

### Commits to platform-level coordination

- PRs against the platform repo when contract-touching changes
  happen.
- Participation in the [release runbook](../operations/release-runbook.md)
  for coordinated releases.
- Updates to [Upstream dependencies](../operations/dependencies.md)
  when new external dependencies arise.

## What CRAFT does NOT require

- **Membership in any specific GitHub org.** Your skill can live
  in any org as long as the platform repo can reference it as a
  submodule.
- **A specific tech stack.** Today's skills are Python + bash;
  future skills could be Rust or Go as long as the
  `install-skill` pattern is respected + the `claude -p`
  invocation pattern works.
- **Surrendering the skill's independent identity.** Skills
  retain their own README + brand + release cadence.

## The joining process

1. **Draft a CRAFT membership proposal** in your skill repo
   describing:
   - What contract the skill produces and/or consumes (cite
     [contract §2](../architecture/contract.md)).
   - How the skill conforms to [contract §3](../architecture/contract.md).
   - The skill's repo URL + current stable release tag.
   - A representative end-to-end run cost + wall-clock.

2. **Open a PR against [kbaseincubator/craft](https://github.com/kbaseincubator/craft)**
   that:
   - Adds the skill as a candidate submodule under `skills/`.
   - Adds the skill's `pip` dependency to `pyproject.toml` with
     a strict version pin.
   - Adds a per-skill page under `docs/skills/<your-skill>.md`
     (modeled on the existing per-skill pages).
   - Adds the skill to the [Tier-0 workflow diagram](../index.md)
     if it participates in the canonical workflow, OR documents
     an alternative workflow it participates in.
   - Updates [contract §2.1 producer/consumer table](../architecture/contract.md)
     if the skill adds new schemas.

3. **Platform-level review.** Existing CRAFT skill maintainers +
   the platform maintainer (Adam, for v0.x) review against:
   - The contract conformance claims.
   - The schema additions (no clash with existing producer
     schemas; new fields well-versioned).
   - The dependencies surface (any new upstream entries in
     [CRAFT-DEPENDENCIES](../operations/dependencies.md)?).
   - The smoke-test plan (does the cross-skill smoke gain
     coverage for the new skill, or does it need a parallel
     smoke?).

4. **Acceptance.** PR merged; skill becomes a CRAFT submodule;
   first CRAFT release including the new skill bumps platform
   minor version (CRAFT v0.X → v0.(X+1)). Documented in
   [release notes](../reference/release-notes.md).

5. **Ongoing participation** per the commitments above.

## Departing the platform

A skill that no longer fits the contract (significant
divergence; no longer maintained; org migration breaking the
submodule reference) can be removed from CRAFT.

Process:

1. Removal proposal as a PR against the platform repo.
2. CRAFT contract review: which schemas does the departing
   skill produce? Are there CRAFT consumers? If yes, the
   consumers either (a) migrate to a replacement, (b) accept
   the schema becoming external/unsupported, or (c) the
   skill's removal is gated on a replacement being ready.
3. Platform major-version bump (CRAFT v0.X → v1.0 if the
   departure is significant) documenting the removal.
4. The skill continues to exist as a standalone skill; just no
   longer under the CRAFT platform's coordination.

## See also

- [Cross-skill contract](../architecture/contract.md) — the
  interface pin you're committing to.
- [Platform structure](../architecture/platform-structure.md) —
  the three-tier architecture you're slotting into.
- [External contributors](external-contributors.md) — guidance
  for contributors outside the Arkin Lab / KBase orbits.
- [Platform proposal](../reference/platform-proposal.md) — the
  architectural argument for CRAFT.
