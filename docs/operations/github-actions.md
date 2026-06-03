# GitHub Actions setup

CRAFT runs two GitHub Actions workflows:

- **`platform-ci.yml`** — cheap unit/lint smoke on every PR and
  push. ~3 minutes wall-clock, $0 LLM, ~3 Actions-minutes.
- **`cross-skill-smoke.yml`** — end-to-end Tier-0 workflow smoke
  against a real BERIL fixture. Manual + quarterly cron. ~60
  minutes wall-clock, $10-15 LLM, ~60 Actions-minutes.

The maintainer notes below are the load-bearing operator
documentation: what each workflow does, what secrets/variables
it needs, and how to set it up the first time.

This content lives at `.github/workflows/README.md` in the
platform repo and is included verbatim below — that's the
canonical maintainer doc; this docs page is the discoverable
mirror.

---

{%
  include-markdown "../../.github/workflows/README.md"
  start="## 1. `platform-ci.yml` — Platform CI (cheap smoke)"
  rewrite-relative-urls=false
%}
