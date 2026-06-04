# CROSS-SKILL-RELEASE.md — Coordinated Release Runbook

**Platform:** CRAFT (Co-Scientist Research Assessment & Framing
Tools)
**Date:** 2026-06-03 (initial)

**Purpose:** When a change touches all three CRAFT skills (e.g.,
adversarial schema bump rippling into paper-writer + presentation-
maker; Anthropic CLI deprecation requiring all three to adopt
new invocation; KBase Lakehouse contract change), this runbook codifies
the sequencing + tests + release ordering.

**When this runbook applies:** any change that requires bumping
two or more of the three CRAFT skills' versions together to
preserve the platform contract.

**When this runbook does NOT apply:** single-skill patches (e.g.,
a presentation-maker bug fix that doesn't touch the contract).
Those release on the skill's own cadence; CRAFT may pick up the
new version on the next platform release but no coordination is
needed.

---

## 1. Decision: is this a coordinated release?

Before invoking this runbook, confirm the change is genuinely
cross-skill. Tests:

- [ ] Does the change modify a schema in `CRAFT-CONTRACT.md §2.1`?
- [ ] Does the change modify an operational invariant in
      `CRAFT-CONTRACT.md §3`?
- [ ] Does the change require simultaneous version bumps in
      two or more skills?
- [ ] Does the change respond to an upstream deprecation in
      `CRAFT-DEPENDENCIES.md`?

If YES to any: this runbook applies. If NO to all: it's a
single-skill patch; release per the skill's own cadence; no
CRAFT-level coordination needed.

---

## 2. Roles in a coordinated release

| Role | Responsibility |
|---|---|
| **Producer skill maintainer** | Lands the change in the skill that produces the changed contract (e.g., adversarial for schema bumps; presentation-maker for slide_spec bumps) |
| **Consumer skill maintainer(s)** | Lands the matching change in skills that consume the contract |
| **Platform maintainer** | Coordinates the order; updates `CRAFT-CONTRACT.md`; bumps CRAFT version |
| **CI watcher** | Monitors the platform smoke test results (Phase 2 deliverable; GitHub Actions notifier) |

For v0.x with Adam as panel-of-one, all four roles collapse to
Adam (with Claude Code as agent). Listed separately because the
delineation matters when the platform broadens to multiple
contributors.

---

## 3. The release sequence

A coordinated release proceeds in 7 phases. Each phase is
discrete; a phase can be paused or retried without losing prior
progress.

### Phase A — Plan the change

1. Open an issue at `kbaseincubator/craft` titled
   `[cross-skill] <one-line description>`. Add label
   `cross-skill-release`.
2. In the issue body, list:
   - Which skill produces the changed contract
   - Which skills consume it
   - Whether the change is backward-compatible (additive) OR
     breaking
   - Dual-support window planned (only if breaking)
   - Estimated timeline (typically 1-4 weeks for a breaking
     change to flow through all consumers)
3. Notify each affected skill's maintainer (in v0.x: just Adam).

### Phase B — Producer skill lands the change

4. Producer skill maintainer creates a branch off `main` of the
   producer skill's repo (e.g., adversarial).
5. Implements the change:
   - For breaking schema changes: emit BOTH the old and new
     shape in parallel during the dual-support window. Mark the
     old shape's `schema_version` with a `.deprecated-at-vN`
     suffix.
   - For Anthropic / KBase / etc. upstream-driven changes:
     adopt the new pattern; verify the skill's tests cover the
     change.
6. Updates the skill's `CONTRACT.md` to document the new
   surface.
7. Updates the skill's `RELEASE_NOTES.md` with the change.
8. Opens a PR; runs CI; lands when green.
9. **Does NOT tag yet.** Wait for consumers to confirm
   compatibility.

### Phase C — Consumer skills adapt

10. Each consumer skill maintainer:
    - Pulls the producer skill's `main` branch
    - Implements the consumer-side adaptation:
      - For additive changes: optionally adopt the new field /
        finding kind / etc.
      - For breaking changes: switch from old shape to new
        shape; update tests; verify the dual-support window's
        old-shape path still works during the deprecation
        window
    - Updates the consumer's `RELEASE_NOTES.md`
    - Opens a PR against the consumer skill's repo
    - Runs CI; lands when green
    - **Does NOT tag yet.**

### Phase D — Cross-skill smoke test

11. Platform maintainer pulls each skill's `main` branch into a
    temporary platform clone:
    ```bash
    git clone https://github.com/kbaseincubator/craft.git /tmp/craft-smoke
    cd /tmp/craft-smoke
    git submodule update --init --recursive
    cd skills/beril-adversarial-skill && git checkout main && cd ../..
    cd skills/beril-paper-writer-skill && git checkout main && cd ../..
    cd skills/beril-presentation-maker-skill && git checkout main && cd ../..
    ```
12. Runs the cross-skill smoke test (Phase 2 deliverable; for
    v0.1.0 this is a manual end-to-end run on a small project):
    - Adversarial reviews a known project
    - Paper-writer drafts a paper consuming the adversarial review
    - Presentation-maker drafts a presentation consuming both
    - All three end-to-end + the rendered artifacts open cleanly
13. If smoke passes: proceed to Phase E.
14. If smoke fails: file blockers as issues; loop back to Phase
    C with the producer / consumer maintainers; do not proceed.

### Phase E — Producer skill tags

15. Producer skill maintainer tags + pushes:
    ```bash
    cd <producer-skill-repo>
    git tag -a v<X.Y.Z> -m "release notes summary"
    git push origin main
    git push origin v<X.Y.Z>
    ```
16. Verify the tag is visible at GitHub.

### Phase F — Consumer skills tag

17. Each consumer skill maintainer:
    - Bumps the dep pin on the producer skill's new tag in their
      `pyproject.toml`
    - Adds a `RELEASE_NOTES.md` entry referencing the producer's
      new tag
    - Opens a final PR; lands when green
    - Tags + pushes their own new release
18. The order of consumer tags doesn't matter (they're peers);
    just ensure all consumers tag before Phase G.

### Phase G — CRAFT platform tags

19. Platform maintainer:
    - Updates `pyproject.toml` to pin the three new skill versions
    - Updates submodule refs to the new tags:
      ```bash
      cd skills/beril-adversarial-skill && git fetch && git checkout v<new-tag> && cd ../..
      cd skills/beril-paper-writer-skill && git fetch && git checkout v<new-tag> && cd ../..
      cd skills/beril-presentation-maker-skill && git fetch && git checkout v<new-tag> && cd ../..
      git add skills/ pyproject.toml
      git commit -m "platform release v<X.Y.Z>: <summary>"
      ```
    - Updates `RELEASE_NOTES.md` with the cross-skill change
      summary
    - Updates `CRAFT-CONTRACT.md` if §2.1 or §3 changed
    - Updates `CRAFT-DEPENDENCIES.md` with the "Last verified"
      bumps + any vendor-side state changes
    - Bumps CRAFT version in `pyproject.toml` + `src/craft/__init__.py`
    - Commits + tags:
      ```bash
      git tag -a v<X.Y.Z> -m "CRAFT v<X.Y.Z> — <summary>"
      git push origin main
      git push origin v<X.Y.Z>
      ```

### Phase H — Verify + close

20. Run `pipx install --force git+https://github.com/kbaseincubator/craft.git@v<X.Y.Z>` on a fresh machine + verify `craft install-platform <BERIL_ROOT>` succeeds.
21. Update the GitHub issue from Phase A: list the tags, link
    the PRs, close.
22. Email / Slack notification to affected stakeholders (in v0.x:
    just Adam writing a memory entry).

---

## 4. Timing windows

| Phase | Typical duration | Maximum |
|---|---|---|
| A (planning) | ~half day | 1 week |
| B (producer lands) | 1-3 days | 1 week |
| C (consumers adapt) | 1-5 days | 2 weeks |
| D (smoke test) | ~half day | 1 day |
| E (producer tags) | minutes | hours |
| F (consumers tag) | hours | 1 day |
| G (CRAFT tags) | ~half day | 1 day |
| H (verify + close) | ~half day | 1 day |
| **Total** | **~1-2 weeks** | **~1 month** |

For breaking changes with dual-support windows, add the
deprecation window (typically 1-2 minor releases ≈ 3-6 months)
between phases B+C and Phase E. The dual-support pattern is:

- Phase B: producer adds the new shape; keeps old shape.
- Phase C: consumers adopt the new shape; old shape still
  works for any non-adopted consumer.
- (Dual-support window: 3-6 months of both shapes coexisting.)
- Phase E (deferred): producer removes the old shape; tags major
  bump.
- Phase F: consumers remove old-shape-support code; tag.
- Phase G: CRAFT tags major bump documenting the breaking
  change.

---

## 5. Rollback

If a Phase G CRAFT release surfaces a regression:

1. Identify which submodule's bump caused the regression.
2. Revert the offending submodule pin:
   ```bash
   cd skills/<offender>
   git checkout <previous-version-tag>
   cd ../..
   git commit -am "rollback: <offender> to <previous-version>"
   git tag -a v<X.Y.Z+1> -m "rollback release"
   git push origin main
   git push origin v<X.Y.Z+1>
   ```
3. File an issue documenting what regressed + scheduling the
   re-fix.

This pattern preserves the platform's working state while
allowing rollback of individual skill bumps. The submodule
pinning is what makes this possible.

---

## 6. Historical log

(Cross-skill releases recorded here. Initial entry on
2026-06-03 documents the v0.1.0 setup itself, which is a
"platform creation" not a "coordinated release" — but worth
documenting as Entry 0.)

### Entry 0 — 2026-06-03 — CRAFT v0.1.0 platform creation

Not a coordinated release; the platform was created with the
three skills at their current production versions:

- beril-adversarial-skill v0.7.0.9 (pinned; no change)
- beril-paper-writer-skill v1.0.1 (pinned; no change)
- beril-presentation-maker-skill v1.0.0 (pinned; no change)

No cross-skill PRs; just the platform repo setup. Documented
here as the baseline.

### Entry 1 — (future)

(Appended on first coordinated release.)

---

*This document is the runbook. When a coordinated release is in
progress, the platform maintainer follows this sequence + logs
the result in §6.*
