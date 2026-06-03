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
pipx install git+https://github.com/kbaseincubator/craft.git@v0.1.4
```

Replace `v0.1.4` with the latest tag if you want the current
release; see [release notes](../reference/release-notes.md) for
what each version ships.

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
# CRAFT v0.1.4
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

## Next steps

- [First run](first-run.md) — exercise one skill end-to-end on a
  small BERIL project.
- [Verify](verify.md) — `craft doctor` health check + integration
  smoke check.
