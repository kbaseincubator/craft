# Troubleshooting

Decision tree for common CRAFT issues. Walk top-to-bottom; the
first matching symptom is usually it.

## Install issues

### `pipx install` of CRAFT fails

| Symptom | Likely cause | Fix |
|---|---|---|
| `Could not find a version that satisfies the requirement craft` | Wrong install URL (forgot `git+https://...`) | Use `pipx install git+https://github.com/kbaseincubator/craft.git@v0.1.4` |
| `ERROR: Couldn't install package: craft. Reason: pyproject.toml not found` | Forked CRAFT repo missing pyproject.toml | Install from the canonical kbaseincubator URL |
| `error: subprocess-exited-with-error` during dependency resolve | One of the three skills' git deps inaccessible | Check your network can reach github.com; check the skill's tag actually exists |
| Pip resolution takes >5 minutes and times out | First-time pipx venv build pulling lots of deps | Patient — first install does 3 venv builds + lots of transitive Python deps. ~3-5 min is normal. |

### `craft install-platform` fails

| Symptom | Likely cause | Fix |
|---|---|---|
| `beril-adversarial install-skill failed` (or paper-writer / presentation-maker) | Per-skill install hit a per-skill issue | Read the per-skill output above the summary; check `<BERIL_ROOT>/.claude/skills/<skill-name>/` for what got partially deployed |
| `<BERIL_ROOT> does not exist or is not a directory` | Path typo | Verify the BERIL_ROOT path; needs `.claude/` + `projects/` subdirs |
| `Permission denied` writing to `<BERIL_ROOT>/.claude/skills/` | BERIL_ROOT owned by another user | Run `chmod -R u+w <BERIL_ROOT>/.claude/` or run as the BERIL owner |

## `craft doctor` issues

See [Verify](../quick-start/verify.md) for the doctor command
itself. Common failures:

| `craft doctor` output | Cause | Fix |
|---|---|---|
| `✗ Skill CLI not on PATH: beril-adversarial` | pipx install partially failed | `pipx install --force git+https://github.com/ArkinLaboratory/beril-adversarial-skill.git@<tag>` |
| `beril-adversarial: version mismatch (installed: 0.7.0.7, CRAFT pins: 0.7.0.9)` | Skill installed but not at the CRAFT-pinned version | `pipx install --force git+https://github.com/ArkinLaboratory/beril-adversarial-skill.git@v0.7.0.9` |
| Per-skill `configure` step reports `claude CLI not on PATH` | Claude Code CLI not installed | Install Claude Code; see [code.claude.com/docs](https://code.claude.com/docs) |
| Per-skill `configure` step reports `CBORG_API_KEY missing` | `<BERIL_ROOT>/.env` doesn't have the key | Add `CBORG_API_KEY=<token>` to `<BERIL_ROOT>/.env` |
| Per-skill `configure` step reports `python-pptx not importable` | Skill's pipx venv missing a dep | `pipx install --force` the affected skill |

## Skill-specific issues (route to skill repo)

CRAFT is a meta-package; per-skill bugs route to the per-skill
issue trackers:

| Symptom | Skill | Repo for issues |
|---|---|---|
| Adversarial review produces empty / malformed JSON | adversarial | [ArkinLaboratory/beril-adversarial-skill/issues](https://github.com/ArkinLaboratory/beril-adversarial-skill/issues) |
| Paper-writer draft.docx malformed; throughline-pick hangs | paper-writer | [ArkinLaboratory/beril-paper-writer-skill/issues](https://github.com/ArkinLaboratory/beril-paper-writer-skill/issues) |
| Presentation-maker draft.pptx render issues, layout overlaps, image-gen failures | presentation-maker | [ArkinLaboratory/beril-presentation-maker-skill/issues](https://github.com/ArkinLaboratory/beril-presentation-maker-skill/issues) |

If the bug clearly crosses skills (e.g., adversarial schema
change breaks paper-writer's revise), file at
[kbaseincubator/craft/issues](https://github.com/kbaseincubator/craft/issues)
instead — that's the cross-skill coordination tracker.

## CI / smoke-test issues

See [GitHub Actions setup §7](github-actions.md#7-troubleshooting)
for the workflow-specific decision tree (secret-missing,
LibreOffice install failures, budget-exceeded, etc.).

## When `claude -p` fails in CI but works locally

Most common: CI runners lack the `claude` CLI's auth config that
your local hub has. The fix is in [GitHub Actions setup
§1b](github-actions.md) — add `ANTHROPIC_API_KEY` as a CI secret
so the runner can authenticate directly.

## When `claude doctor` reports drift after a skill release

The pin is enforced at the CRAFT level. Workflow:

1. CRAFT submodule pins skill at v0.7.0.9.
2. User does `pipx install --force` of the skill at a newer tag
   (e.g., v0.7.0.10) for testing.
3. `craft doctor` now reports a version mismatch.

Either:

- Roll the skill back: `pipx install --force git+https://github.com/.../beril-adversarial-skill.git@v0.7.0.9`
- OR wait for CRAFT to bump the pin (next CRAFT release).
- OR ignore the warning — `craft doctor` returns non-zero but
  the skills still work; the warning is informational.

## When you genuinely don't know what's wrong

1. Run `craft doctor <BERIL_ROOT>` and capture the full output.
2. Run the individual skill commands with `--verbose` if they
   support it.
3. Check `<BERIL_ROOT>/.auto-memory/MEMORY.md` for any recent
   memory entries that might be relevant.
4. File an issue at
   [kbaseincubator/craft/issues](https://github.com/kbaseincubator/craft/issues)
   with: the `craft doctor` output, the failing command, the
   error message, your platform (macOS / Linux version), and
   your Python / pipx versions.

## See also

- [Verify](../quick-start/verify.md) — `craft doctor` reference.
- [GitHub Actions setup](github-actions.md) — CI-specific
  troubleshooting.
- [Upstream dependencies](dependencies.md) — when an upstream
  deprecation is the cause.
