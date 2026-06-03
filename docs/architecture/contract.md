# Cross-skill contract

The CRAFT contract is the **interface pin** that lets the three
skills release independently without breaking each other. It
codifies the schemas they share, the operational invariants
they all uphold, and the process for evolving them.

The full contract lives at `CRAFT-CONTRACT.md` in the platform
repo root and is included below verbatim. The platform
maintainer is the source of truth for contract evolution; this
page is auto-rendered from that file.

## Why the contract exists

The three skills work independently — each has its own CLI,
its own install, its own release cycle. But they also
**explicitly compose**:

- `beril-adversarial-skill` produces structured review findings
  (the `adversarial-review-{paper,presentation}.v3` schemas).
- `beril-paper-writer-skill` consumes those findings in its
  review-rewrite loop.
- `beril-presentation-maker-skill` consumes those findings in
  its review-rewrite loop AND consumes paper-writer's
  `citation_pool.json` via the reuse-from-paper path.

The contract pins:

1. **Schema versioning.** Producer schemas have stability
   guarantees through the current CRAFT major version. Breaking
   changes require a dual-version support window.
2. **The 4-zone draft layout** (`deliverable/`, `narrative/`,
   `working/`, `audit/`) — what every skill produces under
   `<BERIL_ROOT>/projects/<project_id>/{papers,talks}/draft_N/`.
3. **The `claude -p` subagent invocation pattern** + stream-json
   output parsing — the load-bearing primitive.
4. **The `install-skill` discoverability convention** — every
   skill stays independently installable; `craft install-platform`
   is a coordinator, not a replacement.
5. **The environment-variable contract** (`CBORG_API_KEY`,
   `GOOGLE_AI_STUDIO_API_KEY`, `BERIL_ROOT`).
6. **The auto-memory convention** for cross-skill discoveries.
7. **The tiered review cascade pattern** for skills with quality
   gates.

For the rationale see the [platform proposal](../reference/platform-proposal.md);
for the join/depart process for future skills see [Adding a
skill](../extending/adding-a-skill.md).

---

## The contract — full text

{%
  include-markdown "../../CRAFT-CONTRACT.md"
  start="## 1. What this contract is"
  rewrite-relative-urls=false
%}
