# Verify your installation

After [install](install.md), use `craft doctor` to confirm the
platform is healthy.

## `craft doctor`

```bash
craft doctor <BERIL_ROOT>
```

This runs three checks:

1. **Each skill CLI is on `PATH`** — verifies pipx installed all
   three skills successfully.
2. **Each skill reports a version** — verifies each skill's CLI
   is functional + checks the installed-version matches the
   CRAFT pin.
3. **Each skill's `configure` subcommand passes against your
   BERIL_ROOT** — verifies the per-skill runtime config (provider
   resolved, tier models pinned, `claude` on PATH, validation ping).

`craft configure <BERIL_ROOT>` is the dedicated **setup** umbrella — it runs each
skill's `configure` (interactive, so it can prompt for model-tier pins) to bootstrap
the runtime config. `craft doctor` re-runs them as a non-interactive **health probe**;
use `configure` to set things up, `doctor` to check them.

Sample output:

```
CRAFT doctor v0.3.0

── Skill CLIs on PATH
   ✓ beril-adversarial → /opt/pipx/bin/beril-adversarial
   ✓ beril-paper-writer → /opt/pipx/bin/beril-paper-writer
   ✓ beril-presentation-maker → /opt/pipx/bin/beril-presentation-maker

── Skill versions (vs CRAFT pins)
   ✓ beril-adversarial: 0.7.1 (matches pin)
   ✓ beril-paper-writer: 1.1.0 (matches pin)
   ✓ beril-presentation-maker: 1.1.0 (matches pin)

── Per-skill `configure` (BERIL_ROOT=/path/to/beril)
   beril-adversarial configure ...
   (per-skill output)
   beril-paper-writer configure ...
   beril-presentation-maker configure ...

═══════════════════════════════════════════════════════════
CRAFT doctor summary:
  Checks passed: 3/3
  Warnings:      0
═══════════════════════════════════════════════════════════
```

A clean exit code 0 means CRAFT is ready. Non-zero means at
least one warning — read the output above to find the issue.

## Pin-drift detection (v0.2.3+)

If a skill is installed at a different version than CRAFT pins
(common on a Hub where the skill was installed standalone
before CRAFT), `craft doctor` flags it in the Skill versions
section:

```
── Skill versions (vs CRAFT pins)
   ✓ beril-adversarial: 0.7.0.10 (matches pin)
   ⚠ beril-paper-writer: installed 1.0.1, CRAFT pins 1.0.2 — run `craft install-platform` to sync
   ✓ beril-presentation-maker: 1.0.1 (matches pin)
```

Resolve by re-running `craft install-platform <BERIL_ROOT>` —
the install-platform command's sync stage will detect the
drift and force-reinstall the affected skills at the pinned
versions.

## Skip the BERIL_ROOT check

If you just want to verify the install (skip the per-skill
configure):

```bash
craft doctor
```

Without `<BERIL_ROOT>`, doctor skips check #3 and only validates
the install + version checks. Useful right after `pipx install`
when you haven't set up the BERIL deployment yet.

## When something is wrong

- A skill CLI missing from `PATH` → `pipx install --force <skill-repo>` to reinstall.
- A skill reports the wrong version → check `pip list | grep beril` inside the skill's pipx venv.
- A skill's `configure` fails → read the per-skill output for the specific check that failed; usually missing env var or claude CLI issue.
- See [Operations → Troubleshooting](../operations/troubleshooting.md) for more.

## Integration smoke (optional, costs money)

To validate the full Tier-0 workflow end-to-end on a real BERIL
project, see the [first-run page](first-run.md). The full smoke
costs ~$10-15 LLM + takes ~60-90 minutes; CRAFT's CI runs the
same smoke quarterly + on demand.

## Next steps

- [Skills](../skills/adversarial.md) — per-skill operator docs.
- [Operations](../operations/release-runbook.md) — for maintainers
  + integrators.
