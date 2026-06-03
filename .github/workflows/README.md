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

**Required secrets** (configure at Settings → Secrets and
variables → Actions → New repository secret):

| Secret name | What it is | How to set it |
|---|---|---|
| `CBORG_API_KEY` | LBL CBORG gateway token (your existing dev token works) | Copy from your `~/.env` or `BERIL_ROOT/.env` |
| `SMOKE_BERIL_FIXTURE_TARBALL_URL` | URL of a small BERIL fixture project (tarball) | Upload a fixture project as a release asset on a private BERIL fixture repo, OR use GitHub Releases on a smoke-fixture repo |

**Without these secrets the workflow fails at the pre-flight
step with a clear error.** You can run the workflow once before
setting the secrets to see what's missing.

**Setting the secrets (first time):**
1. Navigate to https://github.com/kbaseincubator/craft/settings/secrets/actions
2. Click "New repository secret"
3. Name: `CBORG_API_KEY`, Value: (paste your token)
4. Click "Add secret"
5. Repeat for `SMOKE_BERIL_FIXTURE_TARBALL_URL`

The secrets are then available to ALL workflow runs as
`secrets.CBORG_API_KEY` etc. Not visible in logs (GitHub masks
them).

**About the fixture tarball:** the cross-skill smoke needs a
real BERIL project to operate on. A minimal one suffices — a
project with REPORT.md, RESEARCH_PLAN.md, 2-3 notebooks, a few
figures. The tarball gets downloaded + extracted at smoke time.
Recommendation: create a private GitHub repo with a single
release containing the fixture tarball; point
SMOKE_BERIL_FIXTURE_TARBALL_URL at the release asset URL.

**Maintainer actions:**
- Run manually before any platform release tag.
- Watch for the quarterly cron + investigate failures.
- If a failure looks like a real regression, file an issue
  + link the failure run.

---

## 3. Setting up the secrets — first-time walk-through

Before the `cross-skill-smoke.yml` workflow can run, two secrets
need to be configured in the CRAFT GitHub repo:

### CBORG_API_KEY

This is your existing CBORG gateway token (the same one in
`<BERIL_ROOT>/.env`).

1. Open https://github.com/kbaseincubator/craft/settings/secrets/actions
2. Click "New repository secret"
3. Name: `CBORG_API_KEY`
4. Value: paste the token (no quotes, no leading/trailing
   whitespace)
5. Click "Add secret"

### SMOKE_BERIL_FIXTURE_TARBALL_URL

This needs a tarball of a small BERIL project that the smoke
exercises. Three options:

**Option A — create a smoke-fixture repo (recommended):**

1. Create a private repo `kbaseincubator/craft-smoke-fixtures`.
2. Pick a small BERIL project (e.g., a stripped-down version of
   one of your existing projects with ~3-5 notebooks).
3. Tar it up: `tar -czf craft-smoke-v1.tar.gz <project-dir>`
4. Upload as a release asset on the smoke-fixtures repo.
5. Set `SMOKE_BERIL_FIXTURE_TARBALL_URL` to the asset URL
   (right-click the asset → Copy link).

**Option B — use an existing BERIL artifact location:**

If you already have a fixture project hosted somewhere accessible
to GitHub Actions runners (S3 bucket, public URL), use that URL
directly.

**Option C — defer the cross-skill smoke until later:**

The `platform-ci.yml` workflow runs without these secrets. The
`cross-skill-smoke.yml` workflow will fail at the pre-flight step
with a clear message, but won't run any LLM stages. This is fine
for v0.1.0 — the cheap-smoke is enough until you're ready to set
up the full smoke.

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

## 6. Troubleshooting

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
