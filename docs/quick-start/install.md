# Install CRAFT

CRAFT installs as a meta-package via [pipx](https://pypa.github.io/pipx/).
It transitively pulls in the three CRAFT skills + provides a
`craft` CLI that coordinates per-skill `install-skill`
invocations into one command.

## Prerequisites

- **Python 3.10 or newer** on your system.
- **pipx** installed and on `PATH`. If you don't have it:
  ```bash
  python -m pip install --user pipx
  python -m pipx ensurepath
  ```
- **Claude Code CLI** (`claude`) installed and authenticated. See
  the [Claude Code installation docs](https://code.claude.com/docs)
  if you don't have it yet.
- A **BERIL deployment** at `<BERIL_ROOT>` with `.claude/skills/`
  + `projects/` directories. The [KBase | BERIL repo](https://github.com/kbaseincubator/BERIL-research-observatory)
  is the canonical deployment substrate.
- **`<BERIL_ROOT>/.env`** with at minimum:
  ```
  CBORG_API_KEY=<your LBL CBORG gateway token>
  ```
  Optional for image-gen alternatives:
  ```
  GOOGLE_AI_STUDIO_API_KEY=<your key>
  ```

## Install command

```bash
pipx install git+https://github.com/kbaseincubator/craft.git@v0.2.3
```

Replace `v0.2.3` with the latest tag if you want the current
release; see [release notes](../reference/release-notes.md) for
what each version ships.

!!! warning "Pre-existing skill installs"
    pipx **doesn't reinstall packages that are already installed
    as standalone apps**. If you've previously run
    `pipx install beril-adversarial-skill` (etc.) at a different
    version, `pipx install craft` leaves those pre-existing
    venvs untouched — `craft install-platform` would deploy
    skill data from the *old* versions, not the ones CRAFT pins.

    `craft install-platform` (v0.2.3+) detects this drift and
    force-syncs each skill to the CRAFT-pinned version
    automatically, prompting before each reinstall. Pass
    `--yes` for unattended runs, or `--no-sync-skills` to skip
    the sync (e.g., when you have a hand-installed version you
    want to keep).

CRAFT's `pyproject.toml` pins the three skill versions, so this
single `pipx install` transitively installs:

- `beril-adversarial-skill` (pinned by CRAFT)
- `beril-paper-writer-skill` (pinned by CRAFT)
- `beril-presentation-maker-skill` (pinned by CRAFT)

Total install time: ~3-5 minutes. Each skill goes into its own
pipx venv; the CRAFT meta-package shares its venv with the
`craft` CLI.

## Verify CRAFT installed

```bash
craft --version
# CRAFT v0.2.3
```

You should also see the three skill CLIs on `PATH`:

```bash
beril-adversarial --version
beril-paper-writer --version
beril-presentation-maker --version
```

## Install CRAFT into your BERIL deployment

The pipx install put the skills on your `PATH`, but each skill
still needs to deploy its skill data (prompts, tools, references)
into `<BERIL_ROOT>/.claude/skills/<skill-name>/`. CRAFT's
`install-platform` command runs the three per-skill `install-skill`
invocations in sequence:

```bash
craft install-platform <BERIL_ROOT>
```

You'll see per-skill install summaries. After it completes:

```bash
ls <BERIL_ROOT>/.claude/skills/
# beril-adversarial/  beril-paper-writer/  beril-presentation-maker/
```

## Cost and billing — read before you run (changed 2026-06-15)

CRAFT skills run by calling `claude -p` (non-interactive Claude
Code). As of **June 15, 2026**, Anthropic bills `claude -p` /
Agent SDK usage from a **separate, per-user monthly "Agent SDK
credit"** — not your normal subscription usage limits
([official details](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)).
What that means for running CRAFT:

- **Claim your Agent SDK credit first.** It's a one-time opt-in
  in your Claude account, then refreshes monthly. Without it,
  there's no credit for `claude -p` to draw on.
- **The credit is small relative to a full run.** It's $20/mo
  (Pro), $100 (Max 5x), $200 (Max 20x), with no rollover. A
  paper-writer draft runs on the order of several to ~$10; a
  presentation draft a few dollars; an adversarial review under a
  dollar. On Pro that is roughly two paper drafts before the
  credit is exhausted.
- **Know the cliff.** When the monthly credit runs out: if you've
  **enabled usage credits**, further runs bill at standard API
  rates; if not, **`claude -p` requests stop until the credit
  refreshes** — a skill can fail mid-run for billing reasons, not
  bugs.
- **Heavier or shared/production use → use an Anthropic API key.**
  Configure Claude Code with an `ANTHROPIC_API_KEY` from the
  Claude Platform for predictable pay-as-you-go billing with no
  monthly cap. Anthropic explicitly recommends an API key for
  shared production automation.

Interactive Claude Code, Cowork, and web/desktop/mobile chat are
**not** affected by this change.

**LBL/KBase operators** have a cleaner option: point `claude -p`
itself at CBORG, which serves Claude (incl. Opus 4-6) and
documents a [Claude Code integration](https://cborg.lbl.gov/tools_claudecode/).
Setting

```
ANTHROPIC_BASE_URL=https://api.cborg.lbl.gov          # note: NO /v1 suffix
ANTHROPIC_AUTH_TOKEN=<same value as CBORG_API_KEY>
```

routes the reasoning stages through CBORG at API rates (reusing
the key CRAFT already requires), sidestepping the subscription
credit entirely. The token is the same as `CBORG_API_KEY`, but
the base URL is **not** the same as `CBORG_BASE_URL`: the
OpenAI-style `CBORG_BASE_URL` ends in `/v1`, whereas
`ANTHROPIC_BASE_URL` must be the bare host — the Anthropic client
appends `/v1/messages` itself, so a `/v1` here resolves to
`/v1/v1/messages` and 404s.

Set these where **Claude Code** reads them — a shell `export`, or
an `env` block in `<BERIL_ROOT>/.claude/settings.json`. Putting
them only in `<BERIL_ROOT>/.env` is **not** enough: CRAFT reads
`.env` for its own image/CBORG calls but does not inject it into
the `claude -p` environment. This is otherwise separate from
`CBORG_API_KEY`, which CRAFT uses for image generation and some
direct model calls.

> **VPN:** `api.cborg.lbl.gov` is on the LBL network. Running
> locally requires the **LBL VPN** to be connected — without it,
> `claude -p` calls fail with a connection error that can look
> like a skill bug. On the **KBase Hub** you are already
> on-network, so no VPN is needed.

## Next steps

- [First run](first-run.md) — exercise one skill end-to-end on a
  small BERIL project.
- [Verify](verify.md) — `craft doctor` health check + integration
  smoke check.
