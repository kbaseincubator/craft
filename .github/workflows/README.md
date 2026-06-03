# CRAFT GitHub Actions — Maintainer Notes

**Audience:** the CRAFT maintainer (Adam) + future contributors
learning what's running, when, and why.

GitHub Actions = GitHub's built-in CI runner. Each `.yml` file
in `.github/workflows/` is one **workflow** (a sequence of
jobs); a workflow has **triggers** (`on:` block) telling
GitHub when to run it. Workflows run on GitHub-hosted **runners**
(temporary Linux VMs; free for public repos, metered for private
ones).

For Linux VM tier on `kbaseincubator`'s private repos: 2000
GitHub-Actions-minutes/month free under most GitHub plans. The
two workflows below combined use far less than that
budget — Platform CI runs ~3 min per push (~$0 in compute,
modest in minutes); Cross-Skill Smoke runs ~60 min per trigger
($10-15 in LLM API costs, ~60 minutes of runner time).

---

## 1. `platform-ci.yml` — Platform CI (cheap smoke)

**What it does:** verifies the meta-package + CLI work after
every push to main or PR. Catches "submodule pin broken" /
"pyproject borked" / "CLI broken" without exercising the LLM
stack.

**Triggers:**
- Every PR against main
- Every push to main (after PR merge OR direct push)
- Manual via "Actions" tab → "Platform CI" → "Run workflow"

**Cost:** $0 LLM, ~3 min wall-clock per run, ~3 GitHub-Actions-
minutes per run.

**What this catches:**
- Submodule pins resolving to commits that aren't tagged
  (violates CRAFT-CONTRACT.md §3 strict-pinning policy)
- `pyproject.toml` syntax errors
- `craft` CLI imports broken
- `pytest tests/` regressions
- Lint errors (ruff)

**What this does NOT catch:**
- LLM-stack regressions (paper-writer can't produce a draft;
  adversarial schema drift; etc.) — that's `cross-skill-smoke.yml`
- Hub deployment issues (claude CLI not on PATH; CBORG token
  missing) — those manifest at production install time, not CI

**Maintainer actions:**
- Watch for the green checkmark on each PR + push.
- If it goes red, click into the workflow run + read the failing
  step's log.
- The failing step's name (e.g., "Verify submodule tag pinning")
  tells you which contract is broken.

---

## 2. `cross-skill-smoke.yml` — Cross-Skill Smoke Test (full smoke)

**What it does:** the actual end-to-end test. Real BERIL fixture
→ adversarial review → paper-writer draft → presentation-maker
draft → verifies all three artifacts produced.

**Triggers:**
- **Manual** (`workflow_dispatch`) — the recommended use. Click
  "Actions" tab → "Cross-Skill Smoke Test" → "Run workflow".
  Optional inputs: `max_cost_usd` (default $20),
  `project_id` (use empty for fixture-default).
- **Quarterly cron** — 1st of Mar/Jun/Sep/Dec at 08:00 UTC.
  Catches "the platform still works" without manual attention.
- **Repository dispatch** — when a submodule tags a new release,
  it pings CRAFT via the GitHub API + this workflow fires.
  Requires the submodule's workflow to be set up (Step 5 below).

**Cost:** ~$10-15 LLM per run, ~60 min wall-clock, ~60 GitHub-
Actions-minutes.

**Cost guardrails:**
- 90-minute workflow timeout (kills if hangs)
- `max_cost_usd` workflow input (default $20)
- Per-skill cost caps (`--max-revise-cost-usd 5`,
  `--max-image-cost-usd 0.20`) inside each skill's invocation

**What this catches:**
- Adversarial schema drift breaking paper-writer / presentation-
  maker consumers
- BERIL contract drift breaking all three skills
- Image-gen provider auth or model-availability issues
- New regressions across cross-skill boundaries

**Required config** (two secrets + three variables; configure
at Settings → Secrets and variables → Actions):

| Item | Kind | Purpose | Example value |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | **Secret** | Direct Anthropic API for `claude -p` on CI runner | Get one at https://console.anthropic.com/settings/keys (starts with `sk-ant-...`) |
| `CBORG_API_KEY` | **Secret** | LBL CBORG gateway token (needed for presentation-maker's image-gen) | Copy from your `~/.env` or `BERIL_ROOT/.env` |
| `SMOKE_BERIL_REPO` | **Variable** | Upstream BERIL repo for fixture | `kbaseincubator/BERIL-research-observatory` |
| `SMOKE_BERIL_COMMIT` | **Variable** | Pinned commit SHA (smoke reproducibility) | `940c3b0ee7bbf63bc576bd6e8c25210ad692df8e` |
| `SMOKE_BERIL_PROJECT_ID` | **Variable** | Project subdir name | `microbeatlas_metal_ecology` |

**Note on the two API keys:** Your local BERIL deployment uses a
`claude` CLI that's configured to route through the CBORG gateway,
so `CBORG_API_KEY` is enough locally. CI runners start fresh
with no pre-configured `claude` routing, so the `claude -p`
invocations need a direct Anthropic API key. Cost from CI smoke
runs goes against your Anthropic account, not CBORG quota.
Image-gen (in presentation-maker) still routes through CBORG
because that path is configured at the skill level, not the
shell-CLI level.

**Why a mix of secrets and variables:**
- **Secrets** are masked in CI logs + used for sensitive values
  (tokens, API keys). `CBORG_API_KEY` qualifies.
- **Variables** are visible in the UI + used for non-sensitive
  configuration. The BERIL repo name, commit SHA, and project
  ID are all public information — making them variables means
  you can see them at a glance in the Actions UI.

**Without this config the workflow fails at the pre-flight
step with a clear error listing exactly what's missing.** You
can run the workflow once before configuring to see the
diagnostic.

**Approach: smoke against the live BERIL repo via sparse-checkout.**
The cross-skill smoke clones a specific project subdirectory
from the live BERIL repo (e.g.,
`kbaseincubator/BERIL-research-observatory`) at a pinned
commit SHA. Sparse-checkout means we fetch only the project +
`.claude/skills/` config, not the full 400+ MB BERIL repo —
typical clone is ~5-20 MB.

**Pinning the commit is load-bearing.** Without a pin, the BERIL
repo can evolve between smoke runs + the same CRAFT version
produces different smoke outcomes. With a pin, smoke is
reproducible. Bump the pin deliberately as a CRAFT-maintenance
task (typically alongside the quarterly smoke cycle).

**Maintainer actions:**
- Run manually before any platform release tag.
- Watch for the quarterly cron + investigate failures.
- **Bump `SMOKE_BERIL_COMMIT` quarterly** so smoke exercises
  against recent BERIL conventions. Tag the bump as a CRAFT
  patch release with a note in RELEASE_NOTES.md.
- If a failure looks like a real regression, file an issue
  + link the failure run.

---

## 3. Setting up the cross-skill smoke — first-time walk-through

Before the `cross-skill-smoke.yml` workflow can run, two secrets +
three variables need to be configured in the CRAFT GitHub repo.

### Step 1a — `ANTHROPIC_API_KEY` (secret)

A direct Anthropic API key (NOT a CBORG token). CI runners
start fresh with no `claude` CLI auth config, so they need a
direct Anthropic key. Get one at
https://console.anthropic.com/settings/keys (starts with
`sk-ant-...`).

1. Open https://github.com/kbaseincubator/craft/settings/secrets/actions
2. **Secrets** tab → click "New repository secret"
3. Name: `ANTHROPIC_API_KEY`
4. Value: paste the key (no quotes, no leading/trailing
   whitespace)
5. Click "Add secret"

### Step 1b — `CBORG_API_KEY` (secret)

This is your existing CBORG gateway token (the same one in
`<BERIL_ROOT>/.env`). Needed because presentation-maker's
image-gen routes through CBORG even when text invocations go
direct-Anthropic.

1. Same page → "New repository secret"
2. Name: `CBORG_API_KEY`
3. Value: paste the token (no quotes, no leading/trailing
   whitespace)
4. Click "Add secret"

Both secrets are masked in CI logs.

### Step 2 — `SMOKE_BERIL_REPO` (variable)

The upstream BERIL repo that contains the project the smoke
exercises.

1. Same page → switch to **Variables** tab → click "New
   repository variable"
2. Name: `SMOKE_BERIL_REPO`
3. Value: `kbaseincubator/BERIL-research-observatory`
4. Click "Add variable"

(Or use any other BERIL-style repo with a `projects/` subdir
containing the standard 4-zone artifact layout.)

### Step 3 — `SMOKE_BERIL_COMMIT` (variable)

A specific commit SHA from the BERIL repo. The smoke fetches THIS
commit (not main branch HEAD) so smoke is reproducible even as
BERIL evolves.

To find a current SHA:

```bash
gh api /repos/kbaseincubator/BERIL-research-observatory/commits/main --jq .sha
```

Or browse to https://github.com/kbaseincubator/BERIL-research-observatory/commits/main
and copy a recent SHA.

1. **Variables** tab → "New repository variable"
2. Name: `SMOKE_BERIL_COMMIT`
3. Value: full SHA (40 hex chars; example:
   `940c3b0ee7bbf63bc576bd6e8c25210ad692df8e`)
4. Click "Add variable"

**Bump quarterly** to exercise smoke against recent BERIL
conventions. Tag the bump as a CRAFT patch release.

### Step 4 — `SMOKE_BERIL_PROJECT_ID` (variable)

Which project subdirectory in the BERIL repo to use as the
smoke fixture. Recommendation: pick a project with the standard
4-zone artifact set (REPORT.md + RESEARCH_PLAN.md + notebooks/
+ figures/ + references.md).

1. **Variables** tab → "New repository variable"
2. Name: `SMOKE_BERIL_PROJECT_ID`
3. Value: e.g. `microbeatlas_metal_ecology`
4. Click "Add variable"

### Step 5 — Verify by running the workflow

After all four are configured:

1. Open https://github.com/kbaseincubator/craft/actions
2. Click "Cross-Skill Smoke Test" in the left sidebar
3. Click "Run workflow" → "Run workflow"
4. Watch the run. The pre-flight step will list all four
   config items + confirm "✓ pre-flight passed". If any are
   missing the pre-flight fails with a clear diagnostic.

The first run will take ~60 minutes wall-clock + ~$10-15 in
LLM API costs.

### Deferring the cross-skill smoke

The `platform-ci.yml` workflow runs without ANY of these config
items. The `cross-skill-smoke.yml` workflow will fail cleanly
at the pre-flight step with a clear "what's missing" message
+ won't run any LLM stages. This is fine for incremental setup —
configure when you're ready to spend the $10-15 on first run.

---

## 4. Repository-dispatch trigger (deferred — Phase 2.1)

The third trigger in `cross-skill-smoke.yml` is
`repository_dispatch`. For this to fire automatically when one
of the three submodule repos tags a new release, those repos
need a workflow that pings CRAFT via the GitHub API.

This is a Phase 2.1 task (not blocking the v0.1.0 platform
ship). When ready, each submodule repo gets a small workflow
file:

```yaml
# .github/workflows/notify-craft-on-tag.yml
# Triggers CRAFT cross-skill smoke when this skill tags a release.

name: Notify CRAFT

on:
  push:
    tags:
      - 'v*'

jobs:
  ping-craft:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger CRAFT cross-skill smoke
        env:
          # Personal access token with "repo" scope on
          # kbaseincubator/craft. Add this secret in EACH submodule
          # repo at: Settings → Secrets → CRAFT_DISPATCH_TOKEN
          CRAFT_DISPATCH_TOKEN: ${{ secrets.CRAFT_DISPATCH_TOKEN }}
        run: |
          curl -X POST \
            -H "Authorization: token $CRAFT_DISPATCH_TOKEN" \
            -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/repos/kbaseincubator/craft/dispatches \
            -d '{"event_type":"submodule-released","client_payload":{"skill":"'"$GITHUB_REPOSITORY"'","tag":"'"$GITHUB_REF_NAME"'"}}'
```

When the submodule tags v1.0.2 (for example), GitHub fires the
"Notify CRAFT" workflow on the submodule's repo, which makes an
API call to CRAFT's repo with `repository_dispatch` event
type `submodule-released`. CRAFT's `cross-skill-smoke.yml` sees
this event type in its `on:` block + fires.

**Deferred because:**
- Requires a personal access token (PAT) with cross-repo write
  access — adds a secret-management step you should configure
  deliberately.
- Quarterly cron + manual-trigger cover most of the value
  without the cross-repo PAT complexity.

Recommendation: ship v0.1.0 without the repository-dispatch
trigger; add it in v0.2.0 if you want auto-firing on every
submodule release.

---

## 5. What's NOT in v0.1.0

For honesty + future planning:

- **No code coverage tracking** (e.g., codecov.io integration).
  Tests run + pass/fail; coverage isn't measured. Add in v0.2.0
  if you want it.
- **No release-on-tag automation.** Tags are created manually
  per `CROSS-SKILL-RELEASE.md`. A future workflow could
  auto-publish to PyPI on tag — deferred until needed.
- **No PyPI publishing** of the meta-package itself. CRAFT
  installs via `pipx install git+https://github.com/kbaseincubator/craft.git@v0.1.0`;
  no PyPI presence required. If PyPI publishing is wanted later,
  add a workflow that publishes to TestPyPI on RC tags + PyPI
  on stable tags.
- **No matrix testing across Python versions.** Pinned to 3.12.
  v0.2.0 could matrix 3.10/3.11/3.12 if cross-version stability
  becomes a concern.

---

## 6. Node.js version policy (third-party actions)

GitHub Actions third-party actions (the `uses:` entries) are
implemented in Node.js. GitHub periodically deprecates older
Node versions; the action authors release new major versions
that target the newer Node.

CRAFT's policy: **use the latest Node-supported major version**
of each action. Currently (as of CRAFT v0.1.2):

  actions/checkout@v5         (Node 24)
  actions/setup-python@v6     (Node 24)
  actions/setup-node@v5       (Node 24)
  actions/upload-artifact@v5  (Node 24)

When a deprecation warning surfaces in CI output, bump the
affected action to its new major version + tag a CRAFT patch
release. Document in RELEASE_NOTES.md.

This is a small recurring maintenance task (~once per year
typical, more during transitions like the June 2026 Node 20 →
Node 24 cut-over). The cost is reading the action's release
notes + verifying no behavioral changes affect our use.

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Platform CI: "submodule not on tagged commit" | A submodule was bumped to a non-tag commit | Either tag the commit, or pin the submodule to an existing tag |
| Platform CI: ruff lint fails | New code doesn't match style | Run `ruff format src/ tests/` locally + commit the autofix |
| Cross-Skill Smoke: pre-flight secrets missing | Repo secrets not configured | See §3 above |
| Cross-Skill Smoke: LibreOffice install fails | Apt mirror timeout | Re-run the workflow; the apt step is idempotent |
| Cross-Skill Smoke: Anthropic CLI install fails | npm registry issue | Re-run; the npm step is idempotent |
| Cross-Skill Smoke: budget exceeded | `max_cost_usd` cap hit | Investigate the cost summary in the workflow log; consider lower per-skill caps |
| Quarterly cron fired during deprecation window | Workflow scheduled regardless of context | Disable the workflow in the Actions UI; re-enable after the deprecation lands |

For other failures, the workflow's "Upload artifacts (on
failure for forensics)" step saves the entire BERIL fixture
draft directory as a downloadable artifact (14-day retention).
Click the workflow run → "Artifacts" panel → download for local
debugging.
