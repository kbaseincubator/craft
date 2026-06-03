# Coordinated release runbook

Most CRAFT changes are single-skill patches that release on
their own cadence. **Coordinated releases** are the exception:
they happen when a change touches two or more skills together
(schema bumps, contract changes, upstream-deprecation responses).

This page is the runbook. The full text lives at
`CROSS-SKILL-RELEASE.md` in the platform repo and is included
verbatim below.

## When this applies

A change is a coordinated release if it:

- Modifies a schema in [contract §2.1](../architecture/contract.md).
- Modifies an operational invariant in [contract §3](../architecture/contract.md).
- Requires simultaneous version bumps in two or more skills.
- Responds to an upstream deprecation listed in
  [Upstream dependencies](dependencies.md).

If NO to all of these: it's a single-skill patch. Release on the
skill's own cadence; CRAFT picks it up on the next platform
release.

## When this does NOT apply

- Single-skill bug fixes that don't touch the contract.
- Per-skill prompt-iteration or quality-improvement that stays
  within the skill's own surface.
- Documentation-only changes to a single skill.

## Quick navigation

- [Phase A — Plan the change](#phase-a-plan-the-change)
- [Phase B — Producer skill lands the change](#phase-b-producer-skill-lands-the-change)
- [Phase C — Consumer skills adapt](#phase-c-consumer-skills-adapt)
- [Phase D — Cross-skill smoke test](#phase-d-cross-skill-smoke-test)
- [Phase E — Producer skill tags](#phase-e-producer-skill-tags)
- [Phase F — Consumer skills tag](#phase-f-consumer-skills-tag)
- [Phase G — CRAFT platform tags](#phase-g-craft-platform-tags)
- [Phase H — Verify + close](#phase-h-verify-close)

---

{%
  include-markdown "../../CROSS-SKILL-RELEASE.md"
  start="## 1. Decision: is this a coordinated release?"
  rewrite-relative-urls=false
%}
