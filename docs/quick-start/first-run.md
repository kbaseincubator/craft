# First run

After [install](install.md) you have CRAFT on your `PATH` and all
three skills deployed into `<BERIL_ROOT>/.claude/skills/`. This
page exercises one skill end-to-end on a small BERIL project to
confirm the integration works.

## Pick a small project

The smaller and simpler the BERIL project, the faster + cheaper
the first run. Pick a project with:

- A non-empty `REPORT.md` (the load-bearing input for all three
  skills)
- A `RESEARCH_PLAN.md`
- 3-10 notebooks under `notebooks/`
- A handful of figures under `figures/`

If you don't have one yet, the
[KBase | BERIL repo](https://github.com/kbaseincubator/BERIL-research-observatory)
has 100+ example projects under `projects/`.

## Run adversarial review (cheapest skill, fastest feedback)

```bash
cd <BERIL_ROOT>
beril-adversarial review \
  --type project \
  <project_id> \
  --beril-root <BERIL_ROOT>
```

Cost: ~$1-2 LLM. Wall-clock: ~5-15 minutes. Output:
`<project>/ADVERSARIAL_REVIEW_N.md` — a structured P0/P1/P2
review of the project's research artifacts.

## Run paper-writer (manuscript draft)

```bash
beril-paper-writer draft <project_id> \
  --depth standard
```

The pipeline halts at the throughline-pick gate + writes a
`.handoff.json` listing the candidate throughlines. To resume:

```bash
beril-paper-writer continue projects/<project_id>/papers/draft_1 --pick TL1
```

Cost: ~$5-10 LLM. Wall-clock: ~20-30 minutes. Output:
`projects/<project_id>/papers/draft_N/deliverable/draft.docx`.

For full details + alternatives see the
[beril-paper-writer skill page](../skills/paper-writer.md).

## Run presentation-maker (slide deck draft)

```bash
beril-presentation-maker draft <project_id> \
  --tier STRONG --mode talk-30 \
  --auto-advance
```

Cost: ~$3-12 LLM. Wall-clock: ~45-90 minutes. Output:
`projects/<project_id>/talks/draft_N/deliverable/draft.pptx`.

For mode/tier choices + flag-set reference see the
[beril-presentation-maker skill page](../skills/presentation-maker.md).

## Run all three together (the Tier-0 workflow)

Once you've validated each individually, you can run the full
Tier-0 workflow:

1. Adversarial review first (produces `audit/adversarial_review.{json,md}`).
2. Paper-writer + presentation-maker in parallel (or sequence)
   — both consume the adversarial review in their revise loops.

The platform doesn't enforce an order; the skills coordinate via
the artifacts they write under the project's draft directories.
See [skill relationships](../architecture/relationships.md) for
the full data-flow picture.

## Next steps

- [Verify](verify.md) — run `craft doctor` to confirm everything
  is healthy.
- [Skills](../skills/adversarial.md) — per-skill operator + user
  documentation.
- [Operations → Troubleshooting](../operations/troubleshooting.md)
  if something didn't work.
