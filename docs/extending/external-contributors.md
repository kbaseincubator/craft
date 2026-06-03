# External contributors

CRAFT welcomes contributions from outside the Arkin Lab / KBase
orbits. This page is the entry point for external contributors —
what's accepted, what's not, and how to engage.

## Contributions that are welcome

### Bug reports

For platform-level issues (cross-skill coordination, install,
docs):

- File at [kbaseincubator/craft/issues](https://github.com/kbaseincubator/craft/issues).
- Include: CRAFT version (`craft --version`), platform
  (macOS/Linux + version), Python version, pipx version, the
  failing command, the full error output.

For per-skill bugs:

- File at the per-skill issue tracker (see
  [Troubleshooting](../operations/troubleshooting.md) for the
  table).

### Documentation improvements

Docs PRs are encouraged. Typo fixes, clarifications, missing
operator guidance, broken links — all are welcome at
[kbaseincubator/craft](https://github.com/kbaseincubator/craft).

For per-skill READMEs, PR against the skill's own repo. CRAFT's
docs site auto-pulls per-skill READMEs via include-markdown, so
your improvement flows through on next deploy.

### Test contributions

Cross-skill smoke fixtures, per-skill regression tests, edge
case coverage — all welcome. The cross-skill smoke runs against
a single pinned BERIL fixture; broadening that with additional
fixtures would strengthen the smoke.

### Skill proposals

A new skill that meets the [Adding a skill](adding-a-skill.md)
criteria is a major contribution. The process is the same as
internal contributions:

1. Draft a CRAFT membership proposal.
2. Open a PR.
3. Platform-level review.
4. Acceptance + ongoing participation.

External contributors are explicitly welcome to propose new
skills — the platform contract does NOT require membership in a
specific GitHub org.

## Contributions that need discussion first

These touch platform-level invariants. Open an issue before
investing in a PR:

- Changes to the cross-skill contract (schema bumps, new
  invariants, removed fields).
- Changes to the operational commitments
  ([§3 of the contract](../architecture/contract.md)).
- Removal of a skill from CRAFT.
- New CRAFT-level CLI commands (additions to `craft install-platform`,
  `craft doctor`, etc.).
- Changes to the install model (e.g., switching from pipx to
  Conda).

## Contributions outside scope

CRAFT is **research-artifact production for KBase | BERIL**. It
is NOT:

- A general LLM agent framework. Don't propose features that
  don't relate to research-artifact production.
- A BERIL replacement. Don't propose BERIL-side changes through
  CRAFT.
- A multi-vendor LLM wrapper. CRAFT skills use `claude -p`; that
  is a deliberate substrate choice. Pluggable LLM backends are
  out of scope.
- A presentation/paper template factory. The skills produce
  KBase-branded artifacts following ICMJE / KBase conventions;
  alternative templating + branding is out of scope.

If you're unsure, open a discussion or an issue and ask before
investing in code.

## Code conventions

For PRs against the CRAFT platform repo:

- **Python:** ruff-formatted; `ruff format src/ tests/` before
  commit. Type hints encouraged but not enforced beyond what
  pyright catches at the platform CLI level.
- **Markdown:** kebab-case file names; 70-char line wraps in
  prose for diffability; no trailing whitespace.
- **Tests:** unit tests for CLI additions go in `tests/`. End-to-
  end coverage goes in the cross-skill smoke workflow.
- **Commit messages:** present-tense imperative subject; body
  describes the why; reference the issue number if any.

For PRs against per-skill repos, see the skill's own
contribution docs (most have `CONTRIBUTION.md`).

## Communication channels

- **GitHub issues + PRs** are the primary surface — for both
  platform and per-skill repos.
- **For sensitive issues** (security, compliance) contact the
  [Arkin Lab](https://arkinlab.bio/) directly.

## Licensing

CRAFT is MIT-licensed (see `LICENSE`). The three submodules
carry their own LICENSE files (also MIT today; could diverge in
future).

By submitting a PR you agree to license your contribution under
the receiving repo's license.

## See also

- [Adding a skill](adding-a-skill.md) — full process for skill
  contributions.
- [Cross-skill contract](../architecture/contract.md) — the
  interface you're committing to.
- [Platform structure](../architecture/platform-structure.md) —
  the three-tier architecture.
