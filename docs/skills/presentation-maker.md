# beril-presentation-maker-skill

**Role in CRAFT:** the **presentation drafter** — KBase-branded
scientific presentations (talks + posters) from BERDL projects.
Consumes adversarial review in its review-rewrite loop; consumes
paper-writer's `citation_pool.json` via the D-009 reuse path.

- **Repo:** [ArkinLaboratory/beril-presentation-maker-skill](https://github.com/ArkinLaboratory/beril-presentation-maker-skill)
- **Pinned in CRAFT at:** see `craft/skills/beril-presentation-maker-skill`
  submodule pin.
- **Schemas produced:** `slide_spec.v1`, `compose-fragment.v1`/`.v2`,
  `layout-overlaps.v1`, `content-overflow.v1`, `review-cascade.v1`
  — see [cross-skill contract §2](../architecture/contract.md).
- **Schemas consumed:** `adversarial-review-presentation.v3` (in
  revise loop) + `citation_pool.json` (from paper-writer).
- **Install path:** `pipx install git+https://github.com/ArkinLaboratory/beril-presentation-maker-skill.git@<tag>`
  (transitive via `pipx install craft`).
- **Independent install:** `beril-presentation-maker install-skill <BERIL_ROOT>`.

## When to use it

- **Drafting talks or posters** from a complete BERIL project.
- **Review-rewrite cycles** consuming adversarial output to
  iterate on the deck.
- **Image generation** for big-idea metaphor + claim-evidence
  slides (CBORG-Gemini default; AI Studio direct as alternative).

For platform-level data flow see [Skill
relationships](../architecture/relationships.md).

## Operator quick-reference

```bash
# Initial draft — talks/draft_1
beril-presentation-maker draft <project_id> \
  --tier STRONG --mode talk-30 \
  --auto-advance --auto-approve-images

# Revise against adversarial review (in audit/adversarial_review.json)
beril-presentation-maker revise projects/<project_id>/talks/draft_1
```

Cost: ~$3-12 LLM (depends on image-gen count). Wall-clock:
~45-90 minutes.

**Mode choices:** `talk-30` (default), `talk-45`, `talk-60`,
`poster`. **Tier choices:** `STRONG` (default), `THIN`,
`EXPLORATORY` — controls cascade depth + image-gen count.

For mode/tier reference + the full flag-set, see the README
below (auto-pulled from the skill repo).

---

## Skill README (from the skill repo)

{%
  include-markdown "../../skills/beril-presentation-maker-skill/README.md"
  rewrite-relative-urls=false
%}
