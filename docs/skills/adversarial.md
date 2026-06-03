# beril-adversarial-skill

**Role in CRAFT:** the **producer** of structured review
findings. Both paper-writer and presentation-maker consume its
output in their review-rewrite loops.

- **Repo:** [ArkinLaboratory/beril-adversarial-skill](https://github.com/ArkinLaboratory/beril-adversarial-skill)
- **Pinned in CRAFT at:** see `craft/skills/beril-adversarial-skill`
  submodule pin (`git submodule status` for current).
- **Schemas produced:** `adversarial-review-{paper,presentation,plan,project}.v3`
  — see [cross-skill contract §2](../architecture/contract.md).
- **Install path:** `pipx install git+https://github.com/ArkinLaboratory/beril-adversarial-skill.git@<tag>`
  (already done transitively if you `pipx install craft`).
- **Independent install:** `beril-adversarial install-skill <BERIL_ROOT>`
  (CRAFT's `install-platform` calls this for you).

## When to use it

- **Tier-0 quality assessment** of any BERIL research artifact
  (project, plan, paper, presentation) before publication.
- **As the producer of findings** that paper-writer + presentation-maker
  consume in their revise loops.
- **External integrators** can consume `adversarial-review-*.v3`
  outputs without going through CRAFT.

For platform-level data flow see [Skill
relationships](../architecture/relationships.md).

## Operator quick-reference

```bash
# Review a whole BERIL project
beril-adversarial review --type project <project_id> \
  --beril-root <BERIL_ROOT>

# Review a paper draft
beril-adversarial review --type paper <papers/draft_N> \
  --beril-root <BERIL_ROOT>

# Review a presentation draft
beril-adversarial review --type presentation <talks/draft_N> \
  --beril-root <BERIL_ROOT>
```

Cost: ~$1-2 LLM per project review; ~$0.50-1 per artifact review.
Wall-clock: ~5-15 minutes.

For mode/tier choices + flag-set reference, see the README below
(auto-pulled from the skill repo).

---

## Skill README (from the skill repo)

{%
  include-markdown "../../skills/beril-adversarial-skill/README.md"
  rewrite-relative-urls=false
%}
