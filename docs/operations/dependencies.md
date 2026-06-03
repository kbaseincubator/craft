# Upstream dependencies

CRAFT skills lean on external dependencies that can change:
Anthropic Claude Code's `claude -p` invocation, KBase | BERIL
contracts, image-gen provider APIs, Python ecosystem libraries.
The dependencies watchlist tracks each with version notes + a
"last verified working with" date.

The full watchlist lives at `CRAFT-DEPENDENCIES.md` in the
platform repo and is included verbatim below. The platform
maintainer reviews it quarterly + on any vendor deprecation
notice.

## How operators use this page

- **Before a coordinated release:** check that no entry needs an
  urgent action.
- **When something breaks unexpectedly:** check the "Last
  verified" dates. Anything stale (>1 quarter) is a suspect.
- **When a vendor announces a deprecation:** open an issue at
  `kbaseincubator/craft` referencing the affected entry; the
  [release runbook](release-runbook.md) coordinates the response.

For the troubleshooting decision tree on user-reported issues
see [Troubleshooting](troubleshooting.md).

---

{%
  include-markdown "../../CRAFT-DEPENDENCIES.md"
  start="## 1. Anthropic / Claude Code"
  rewrite-relative-urls=false
%}
