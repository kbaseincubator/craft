# beril-paper-writer-skill

**Role in CRAFT:** the **manuscript drafter** — ICMJE-conformant
scientific manuscripts from BERDL projects. Consumes adversarial
review in its review-rewrite loop; produces `citation_pool.json`
that presentation-maker can reuse.

- **Repo:** [kbaseincubator/beril-paper-writer-skill](https://github.com/kbaseincubator/beril-paper-writer-skill)
- **Pinned in CRAFT at:** see `craft/skills/beril-paper-writer-skill`
  submodule pin.
- **Schemas produced:** `claim_inventory.tsv`,
  `citation_pool.json` — see [cross-skill contract §2](../architecture/contract.md).
- **Schemas consumed:** `adversarial-review-paper.v3` (in
  revise loop).
- **Install path:** `pipx install git+https://github.com/kbaseincubator/beril-paper-writer-skill.git@<tag>`
  (transitive via `pipx install craft`).
- **Independent install:** `beril-paper-writer install-skill <BERIL_ROOT>`.

## When to use it

- **Drafting a manuscript** from a complete BERIL project
  (non-empty REPORT.md, RESEARCH_PLAN.md, notebooks, figures).
- **Review-rewrite cycles** consuming adversarial output to
  iterate on the draft.
- **Citation pool reuse**: produces `working/citation_pool.json`
  that presentation-maker's D-009 reuse path consumes.

For platform-level data flow see [Skill
relationships](../architecture/relationships.md).

## Operator quick-reference

```bash
# Initial draft — halts at throughline-pick gate by design
beril-paper-writer draft <project_id> --depth standard

# Resume at throughline pick (the .handoff.json lists candidates)
beril-paper-writer continue projects/<project_id>/papers/draft_1 --pick TL1

# Revise against adversarial review (in audit/adversarial_review.json)
beril-paper-writer revise projects/<project_id>/papers/draft_1
```

Cost: ~$5-10 LLM standard depth. Wall-clock: ~20-30 minutes.

**Throughline halt by design:** paper-writer deliberately halts
mid-pipeline so the user picks the throughline. This is
load-bearing for manuscript quality — auto-picking would
produce drafts that don't reflect the user's framing of the work.

For mode/depth choices + flag-set reference, see the README
below (auto-pulled from the skill repo).

---

## Skill README (from the skill repo)

{%
  include-markdown "../../skills/beril-paper-writer-skill/README.md"
  rewrite-relative-urls=false
%}
