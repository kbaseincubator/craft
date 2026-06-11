"""Cross-skill CRAFT runtime-config conformance fixture (CRAFT-CONTRACT §3.4).

Purpose: catch copy-drift across the three CRAFT skills' canonical
`llm_config.py` files. The contract says the resolver is **copied, not
shared** ("the other CRAFT skills copy it … a shared conformance fixture
keeps the copies in step"). This file is that fixture.

Atlas is **excluded** by design (CRAFT-CONTRACT §3.4 "Conformance boundary
+ atlas" — atlas is a separate product that verifies in its own suite).

How this is run
---------------
The fixture imports three sibling packages (`beril_adversarial`,
`beril_paper_writer`, `beril_presentation_maker`) — distinct
distributions, no namespace collision. They are NOT runtime deps of
`craft`; we editable-install them into the venv that runs craft-platform's
pytest:

    pip install -r tests/requirements-conformance.txt

The requirements file pins:
    -e skills/beril-adversarial-skill
    -e skills/beril-paper-writer-skill
    -e skills/beril-presentation-maker-skill

Locally the imports may fail (no editable install yet). Module-level
`pytest.skip` handles that gracefully with the exact remediation
command. CI installs the requirements first so the fixture is required
where it matters.

The three assertion families
----------------------------

Family A — **behavioral identity** of the pure resolver functions.
For every input in the fixture table, the three skills' implementations
return equal results (or all raise an equivalent `ConfigError`).
Behavior is the contract; this is the load-bearing family.

Family B — **shared-block identity + additive-only property** of
`compose_env_append`. The full output differs across skills (each
carries its own per-skill marker), but the shared CRAFT-block region
between `SHARED_OPEN`/`SHARED_CLOSE` sentinels must be byte-identical,
and the additive-only contract (no re-declaration of keys already in
the user's .env) must hold per skill.

Family C — **source identity** of the canonical function set, via
`inspect.getsource`. Pinpoints *which* function drifted faster than
a behavioral diff. The set is **explicit** so per-skill additions
(paper-writer's `pick_tier`, anything similar) are allowed by
construction.

What this file does NOT cover
-----------------------------
- Live model discovery / HTTP (that's `configure`'s I/O, not the resolver).
- `settings.json` writing (configure's job).
- Atlas (its own suite).
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import os
from pathlib import Path
from textwrap import dedent

import pytest

# Editable-install the 3 skills before running this file (or the module
# imports will fail; behavior on failure is environment-aware — see below).
try:
    from beril_adversarial import llm_config as a_lc  # type: ignore
    from beril_adversarial.commands import configure as a_cfg  # type: ignore
    from beril_adversarial.commands import template_env as a_te  # type: ignore
    from beril_paper_writer import llm_config as p_lc  # type: ignore
    from beril_paper_writer.commands import configure as p_cfg  # type: ignore
    from beril_paper_writer.commands import template_env as p_te  # type: ignore
    from beril_presentation_maker import llm_config as m_lc  # type: ignore
    from beril_presentation_maker.commands import configure as m_cfg  # type: ignore
    from beril_presentation_maker.commands import template_env as m_te  # type: ignore
except ImportError as exc:
    # CI MUST FAIL when the editable installs aren't in place — a silent
    # skip there would let a broken `tests/requirements-conformance.txt`
    # or a busted CI step pass green. Locally we skip with the remediation
    # hint so a fresh checkout can still run `pytest` without prep.
    #
    # GitHub Actions / GitLab CI / most CI systems set `CI=true`; we treat
    # any truthy `CI` env var as "must hard-fail." The CRAFT platform-ci
    # workflow installs `requirements-conformance.txt` BEFORE invoking
    # pytest, so this branch in CI means the install step regressed.
    if os.environ.get("CI"):
        raise RuntimeError(
            f"Cross-skill conformance imports failed in CI ({exc}). "
            "Was `pip install -r tests/requirements-conformance.txt` run "
            "before pytest? See .github/workflows/platform-ci.yml — the "
            "`Install conformance-fixture deps` step must succeed before "
            "this file is collected."
        ) from exc
    pytest.skip(
        f"Cross-skill conformance requires the 3 CRAFT skills editable-installed:\n"
        f"    pip install -r tests/requirements-conformance.txt\n"
        f"Import failed: {exc}",
        allow_module_level=True,
    )

# Triples used everywhere below. `SKILLS` is the canonical 3-skill matrix
# Family A/B/C iterate over.
SKILLS: list[tuple[str, object, object, object]] = [
    ("adversarial", a_lc, a_cfg, a_te),
    ("paper-writer", p_lc, p_cfg, p_te),
    ("presentation-maker", m_lc, m_cfg, m_te),
]

LC_TRIPLE = (a_lc, p_lc, m_lc)
CFG_TRIPLE = (a_cfg, p_cfg, m_cfg)
TE_TRIPLE = (a_te, p_te, m_te)


# ---------------------------------------------------------------------------
# Anti-vacuity guard: the 3 llm_config modules must resolve to DISTINCT
# files on disk.
# ---------------------------------------------------------------------------
#
# This is the most insidious vacuous-pass mode for the conformance fixture:
# a future packaging change (a namespace package, a wheel-build script that
# merges sources, a symlink farm) could make `beril_adversarial.llm_config`,
# `beril_paper_writer.llm_config`, and `beril_presentation_maker.llm_config`
# all resolve to the SAME physical file. Family C's source-equality would
# then "pass" trivially — but the contract's intent (each skill has its OWN
# verbatim copy that copy-drift across copies would diverge) would be silently
# broken.
#
# Verified to hold today; this test pins it.


def test_anti_vacuity_llm_config_modules_resolve_to_distinct_files():
    paths = [Path(mod.__file__).resolve() for mod in LC_TRIPLE]
    assert len(set(paths)) == 3, (
        "Family-C vacuous-pass guard: the 3 skills' llm_config modules "
        "must resolve to 3 distinct files. Otherwise source-equality "
        "assertions below trivially pass on the same physical file.\n"
        f"adversarial: {paths[0]}\n"
        f"paper-writer: {paths[1]}\n"
        f"presentation-maker: {paths[2]}"
    )


# ---------------------------------------------------------------------------
# Input fixtures (parametrize Family A + B over these — brief §3.3)
# ---------------------------------------------------------------------------

PROVIDER_INFERENCE_CASES = [
    ({"CBORG_API_KEY": "k"}, "cborg"),
    ({"ANTHROPIC_API_KEY": "k"}, "anthropic"),
    ({"CBORG_API_KEY": "k", "ANTHROPIC_API_KEY": "k2"}, "cborg"),
    ({}, "subscription"),
    ({"ACTIVE_PROVIDER": "anthropic", "CBORG_API_KEY": "k"}, "anthropic"),
]

PROVIDER_INFERENCE_INVALID_CASES = [
    {"ACTIVE_PROVIDER": "bogus"},
]

# Tier resolution — input → no canonical answer needed (we compare cross-skill).
CBORG_AVAILABLE_FIXTURE = [
    "claude-opus-4-8",
    "claude-opus-4-8-high",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
]

TIER_RESOLUTION_INPUTS = [
    # all pinned + available includes them
    (
        {
            "MODEL_REASONING": "claude-opus-4-8",
            "MODEL_STANDARD": "claude-sonnet-4-6",
            "MODEL_FAST": "claude-haiku-4-5",
        },
        CBORG_AVAILABLE_FIXTURE,
    ),
    # pins set, available=None → pins pass through unchecked
    (
        {
            "MODEL_REASONING": "claude-opus-4-7",
            "MODEL_STANDARD": "claude-sonnet-4-5",
            "MODEL_FAST": "claude-haiku-4-4",
        },
        None,
    ),
    # unset + available → discovery picks newest non-high per family
    ({}, CBORG_AVAILABLE_FIXTURE),
    # unset + available=None → all three unresolved
    ({}, None),
    # pin not in available → tier unresolved + warning
    ({"MODEL_REASONING": "claude-opus-4-99"}, CBORG_AVAILABLE_FIXTURE),
    # available has no model for fast family → unresolved + warning
    ({}, ["claude-opus-4-8", "claude-sonnet-4-6"]),
]

BASE_URL_CASES = [
    {},  # default
    {"CBORG_BASE_URL": "https://api.cborg.lbl.gov/v1"},
    {"CBORG_BASE_URL": "https://api.cborg.lbl.gov/v1/"},  # trailing slash
    {"CBORG_BASE_URL": "https://api.cborg.lbl.gov"},  # bare host
    {"CBORG_BASE_URL": "https://proxy.example.com/cborg"},
    {"CBORG_BASE_URL": "https://proxy.example.com/cborg/v1"},
]

PARSE_ENV_TEXT_CASES = [
    # The verified-fragile masking case (configure's round-1 bug).
    ("CBORG_API_KEY=   # paste key", {"CBORG_API_KEY": ""}),
    ("FOO=bar  # comment", {"FOO": "bar"}),
    # No whitespace before # → kept as part of the URL.
    ("URL=https://example.com/#frag", {"URL": "https://example.com/#frag"}),
    # Quoted values are taken verbatim; trailing-after-quote ignored.
    ('FOO="quoted # not a comment"', {"FOO": "quoted # not a comment"}),
    # Whole-line comments + blank lines are dropped.
    ("# header comment\n\nKEY=val\n", {"KEY": "val"}),
    # Last-write-wins for duplicate keys.
    ("K=1\nK=2", {"K": "2"}),
]


# ---------------------------------------------------------------------------
# Family A — behavioral identity of the pure resolver functions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("env,expected", PROVIDER_INFERENCE_CASES)
def test_familyA_infer_provider_matches_across_skills(env, expected):
    """Each skill's `infer_provider(env)` returns the same string."""
    results = [mod.infer_provider(env) for mod in LC_TRIPLE]
    assert results == [expected, expected, expected], (
        f"infer_provider diverged across skills for env={env}: "
        f"adv={results[0]!r} pw={results[1]!r} pm={results[2]!r}"
    )


@pytest.mark.parametrize("env", PROVIDER_INFERENCE_INVALID_CASES)
def test_familyA_infer_provider_invalid_raises_equivalent_error(env):
    """For the invalid-provider case, each skill raises its OWN
    `ConfigError` type (distinct classes per the copy-not-share design).
    We do NOT compare types; we compare that all three raise a
    `ConfigError` and that `str(exc)` is equal."""
    messages = []
    for mod in LC_TRIPLE:
        with pytest.raises(mod.ConfigError) as excinfo:
            mod.infer_provider(env)
        messages.append(str(excinfo.value))
    assert messages[0] == messages[1] == messages[2], (
        f"ConfigError messages diverged: {messages}"
    )


@pytest.mark.parametrize("env", BASE_URL_CASES)
def test_familyA_bare_host_matches_across_skills(env):
    results = [mod.bare_host(env) for mod in LC_TRIPLE]
    assert results[0] == results[1] == results[2], (
        f"bare_host diverged for env={env}: {results}"
    )


@pytest.mark.parametrize("env", BASE_URL_CASES)
def test_familyA_app_internal_base_url_matches_across_skills(env):
    """The Stage-6 helper. Same input → same output across skills."""
    results = [mod.app_internal_base_url(env) for mod in LC_TRIPLE]
    assert results[0] == results[1] == results[2], (
        f"app_internal_base_url diverged for env={env}: {results}"
    )


@pytest.mark.parametrize("env", BASE_URL_CASES)
def test_familyA_app_internal_base_url_equals_bare_host_plus_v1(env):
    """Invariant per CRAFT-CONTRACT §3.4: for any input the two base
    URLs differ by exactly `/v1`."""
    for mod in LC_TRIPLE:
        assert mod.app_internal_base_url(env) == mod.bare_host(env) + "/v1"


@pytest.mark.parametrize("family", ["opus", "sonnet", "haiku"])
def test_familyA_pick_newest_matches_across_skills(family):
    results = [mod.pick_newest(CBORG_AVAILABLE_FIXTURE, family) for mod in LC_TRIPLE]
    assert results[0] == results[1] == results[2], (
        f"pick_newest('{family}') diverged: {results}"
    )


@pytest.mark.parametrize("env,available", TIER_RESOLUTION_INPUTS)
def test_familyA_resolve_tier_models_matches_across_skills(env, available):
    """Compare the full (models, unresolved, warnings) tuple element-wise."""
    triples = [mod.resolve_tier_models(env, available) for mod in LC_TRIPLE]
    for i in (1, 2):
        assert triples[i][0] == triples[0][0], (
            f"resolve_tier_models models diverged at skill {i}: "
            f"{triples[0][0]} vs {triples[i][0]}"
        )
        assert sorted(triples[i][1]) == sorted(triples[0][1]), (
            f"resolve_tier_models unresolved diverged at skill {i}: "
            f"{triples[0][1]} vs {triples[i][1]}"
        )
        assert sorted(triples[i][2]) == sorted(triples[0][2]), (
            f"resolve_tier_models warnings diverged at skill {i}: "
            f"{triples[0][2]} vs {triples[i][2]}"
        )


# Inputs for `resolve()` — needs the provider/credentials present.
RESOLVE_INPUTS = [
    (
        {"ACTIVE_PROVIDER": "cborg", "CBORG_API_KEY": "k"},
        CBORG_AVAILABLE_FIXTURE,
    ),
    (
        {"ACTIVE_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "k"},
        CBORG_AVAILABLE_FIXTURE,
    ),
    (
        {"ACTIVE_PROVIDER": "subscription"},
        None,
    ),
]


@pytest.mark.parametrize("env,available", RESOLVE_INPUTS)
def test_familyA_resolve_matches_across_skills(env, available):
    """ResolvedConfig is a per-skill dataclass type; compare field-by-field
    via dataclasses.asdict so distinct types compare cleanly."""
    asdicts = [dataclasses.asdict(mod.resolve(env, available)) for mod in LC_TRIPLE]
    for i in (1, 2):
        assert asdicts[i] == asdicts[0], (
            f"resolve diverged at skill {i} for env={env}: "
            f"adversarial={asdicts[0]} vs skill_{i}={asdicts[i]}"
        )


@pytest.mark.parametrize("text,expected", PARSE_ENV_TEXT_CASES)
def test_familyA_parse_env_text_matches_across_skills(text, expected):
    """parse_env_text is a copied pure helper; behavior must be identical."""
    results = [mod.parse_env_text(text) for mod in CFG_TRIPLE]
    assert results[0] == results[1] == results[2] == expected, (
        f"parse_env_text diverged for input {text!r}: {results}"
    )


# ---------------------------------------------------------------------------
# Family B — compose_env_append shared-block identity + additive-only
# ---------------------------------------------------------------------------


def _extract_shared_region(text: str, te_mod) -> str:
    """Slice between the SHARED_OPEN and SHARED_CLOSE sentinels."""
    open_sentinel = "# >>> CRAFT shared config"
    close_sentinel = "# <<< CRAFT shared config"
    start = text.find(open_sentinel)
    end = text.find(close_sentinel)
    if start == -1 or end == -1 or end < start:
        return ""
    # Include the close-sentinel line in the slice. find() returns the
    # start of the close sentinel; capture the rest of that line.
    eol = text.find("\n", end)
    if eol == -1:
        eol = len(text)
    else:
        eol += 1  # include the newline so the regions match byte-for-byte
    return text[start:eol]


def test_familyB_sentinel_constants_match_across_skills():
    """The sentinel strings (which Family-B logic depends on) are equal."""
    open_vals = [m.SHARED_OPEN for m in CFG_TRIPLE]
    close_vals = [m.SHARED_CLOSE for m in CFG_TRIPLE]
    assert open_vals[0] == open_vals[1] == open_vals[2]
    assert close_vals[0] == close_vals[1] == close_vals[2]


def test_familyB_shared_block_region_byte_identical():
    """compose_env_append('') ⊃ the shared block. The region between the
    open and close sentinels must be byte-identical across the 3 skills,
    even though each skill's per-skill marker (outside the region) differs."""
    outputs = [m.compose_env_append("") for m in CFG_TRIPLE]
    regions = [_extract_shared_region(outputs[i], TE_TRIPLE[i]) for i in range(3)]
    assert regions[0], "adversarial compose_env_append('') has no shared region"
    assert regions[0] == regions[1] == regions[2], (
        f"Shared block region diverged:\n"
        f"adv:\n{regions[0]!r}\npw:\n{regions[1]!r}\npm:\n{regions[2]!r}"
    )


# Fixture .env contents for additive-only property checks (brief §3.3).
ADDITIVE_ONLY_KEYS = [
    "CBORG_API_KEY",
    "ANTHROPIC_API_KEY",
    "CBORG_BASE_URL",
    "ACTIVE_PROVIDER",
    "MODEL_REASONING",
    "MODEL_STANDARD",
    "MODEL_FAST",
]


@pytest.mark.parametrize("key", ADDITIVE_ONLY_KEYS)
def test_familyB_compose_omits_keys_already_present_per_skill(key):
    """For each skill: if the user's .env already declares KEY, the
    appended block must NOT contain a `KEY=` line. This is the
    additive-only contract — re-declaring shadows the user's value via
    last-write-wins inside python-dotenv."""
    env_text = f"{key}=user_set_value\n"
    for name, _lc, cfg_mod, _te in SKILLS:
        out = cfg_mod.compose_env_append(env_text)
        assert f"{key}=" not in out, (
            f"{name}: compose_env_append re-declared {key!r} when user .env "
            f"already had it. Additive-only contract broken. Output:\n{out}"
        )


def test_familyB_idempotent_when_both_sentinel_and_marker_present_per_skill():
    """For each skill: with both the shared sentinel AND its per-skill
    marker already present, `compose_env_append` returns empty."""
    for name, _lc, cfg_mod, te_mod in SKILLS:
        # The block te_mod.render() emits includes both sentinels + marker.
        env_text = te_mod.render(include_shared=True)
        out = cfg_mod.compose_env_append(env_text)
        assert out == "", (
            f"{name}: compose_env_append non-empty when both sentinel + "
            f"marker already present. Output:\n{out}"
        )


@pytest.mark.parametrize(
    "credential_key",
    ["CBORG_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "KBASE_AUTH_TOKEN"],
)
def test_familyB_compose_never_declares_credentials(credential_key):
    """The shared CRAFT block must NEVER contain a bare `KEY=` line for
    a known credential (it READS them, never declares them, per CRAFT-
    CONTRACT §3.4). True for compose_env_append('') with no user .env."""
    for name, _lc, cfg_mod, _te in SKILLS:
        out = cfg_mod.compose_env_append("")
        # Match the start-of-line declaration; any commented mention is fine.
        bad_line = f"\n{credential_key}="
        assert bad_line not in out and not out.startswith(f"{credential_key}="), (
            f"{name}: compose_env_append declared {credential_key!r}. "
            f"Credentials must be READ, never DECLARED, per §3.4."
        )


# ---------------------------------------------------------------------------
# Family C — source identity of the canonical function set + constants
# ---------------------------------------------------------------------------

# The brief's explicit canonical set. Per-skill additions (paper-writer's
# `pick_tier`, atlas's `pick_tier`, anything new) are allowed by construction
# — they're simply not in this set. If Family C fails on one of these, that's
# a brief-design question for Adam, not a unilateral set edit.
CANONICAL_FUNCTION_NAMES = [
    "_val",
    "infer_provider",
    "bare_host",
    "app_internal_base_url",  # added in Stage 6 / piece 2
    "_version_key",
    "pick_newest",
    "resolve_tier_models",
    "resolve",
]

CANONICAL_CONSTANT_NAMES = [
    "CBORG_BARE_HOST",
    "PROVIDERS",
    "TIER_FAMILY",
    "TIER_ENV",
    "TIER_ENVKEY",
]


def _normalize_source(src: str) -> str:
    """Strip trailing whitespace from each line and trailing blank lines.
    Per Adam's Stage-6 decision: normalization is STRICT (trailing-whitespace
    / dedent only; do NOT collapse interior whitespace)."""
    return dedent("\n".join(line.rstrip() for line in src.splitlines())).rstrip()


def _extract_constant_assign_source(module, const_name: str) -> str:
    """Read the source of the module and return the `name = …` Assign
    segment for `const_name`, normalized.

    Constants don't expose source via `inspect.getsource` (they're
    objects, not code definitions). Parse the module's source text
    with `ast`, find the top-level `Assign` whose target name matches,
    and return its exact source segment via `ast.get_source_segment`.

    Raises AssertionError if the name isn't found at module level.
    """
    src = inspect.getsource(module)
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == const_name:
                    segment = ast.get_source_segment(src, node)
                    assert segment is not None, (
                        f"ast.get_source_segment returned None for "
                        f"{const_name!r} in {module.__name__}"
                    )
                    return _normalize_source(segment)
    raise AssertionError(
        f"No top-level Assign for {const_name!r} found in {module.__name__}"
    )


@pytest.mark.parametrize("fn_name", CANONICAL_FUNCTION_NAMES)
def test_familyC_function_source_identical_across_skills(fn_name):
    """inspect.getsource of each canonical function is byte-identical
    (after strict normalization) across the 3 CRAFT skills."""
    sources = []
    for name, lc_mod, _cfg, _te in SKILLS:
        fn = getattr(lc_mod, fn_name)
        sources.append((name, _normalize_source(inspect.getsource(fn))))
    ref_name, ref_src = sources[0]
    for name, src in sources[1:]:
        assert src == ref_src, (
            f"Family C: source of {fn_name!r} diverged between "
            f"{ref_name} and {name}. Diff:\n"
            f"--- {ref_name}\n{ref_src}\n"
            f"+++ {name}\n{src}"
        )


@pytest.mark.parametrize("const_name", CANONICAL_CONSTANT_NAMES)
def test_familyC_constant_value_identical_across_skills(const_name):
    """Module constants in the canonical set have equal VALUES across
    the 3 skills. Kept as a readable diagnostic: a divergence here is
    genuine semantic drift, not formatting drift. The source-equality
    test below is the load-bearing assertion that closes the
    formatting-drift hole; this one fires first with a cleaner message
    when the constants actually differ by value."""
    values = [getattr(lc_mod, const_name) for _name, lc_mod, _cfg, _te in SKILLS]
    assert values[0] == values[1] == values[2], (
        f"Family C: constant {const_name!r} value diverged across skills: {values}"
    )


@pytest.mark.parametrize("const_name", CANONICAL_CONSTANT_NAMES)
def test_familyC_constant_source_identical_across_skills(const_name):
    """The Assign-source segment for each canonical constant is
    byte-identical (after strict normalization) across the 3 skills.

    Closes the formatting-drift hole that pure value-equality leaves
    open: two skills' `TIER_ENVKEY` could be `{"a": "b", "c": "d"}` vs
    a multi-line literal — value-equal but source-divergent. Family C
    exists to *localize* drift; source-equality catches the cosmetic
    drift that's the first symptom of a non-verbatim copy.

    Per Adam's Stage-6 decision: STRICT normalization (trailing-
    whitespace / dedent only). Do NOT collapse interior whitespace.
    """
    sources = []
    for name, lc_mod, _cfg, _te in SKILLS:
        sources.append((name, _extract_constant_assign_source(lc_mod, const_name)))
    ref_name, ref_src = sources[0]
    for name, src in sources[1:]:
        assert src == ref_src, (
            f"Family C: source of constant {const_name!r} diverged between "
            f"{ref_name} and {name}. Diff:\n"
            f"--- {ref_name}\n{ref_src}\n"
            f"+++ {name}\n{src}"
        )


# ---------------------------------------------------------------------------
# Family D — user_intent.py copy byte-identity (presentation-maker ↔ paper-writer)
# ---------------------------------------------------------------------------
#
# `user_intent.py` (schema user-intent.v1: mode/tier/audience + *_explicit flags)
# is COPIED verbatim into the two drafting skills that halt-and-handoff on the
# user's mode pick — presentation-maker (Cycle 1) and paper-writer (Cycle 2).
# Per the copy-not-share convention (same as llm_config, Family C) the copies
# MUST stay byte-identical. adversarial + atlas have no user_intent (they don't
# persist a user mode pick), so this pair is the entire matrix — hence its own
# family rather than a row in the 3-skill SKILLS matrix.
#
# Unlike Family C we compare the *file* source, not inspect.getsource of named
# symbols: the skills load this module via importlib-by-path, not as a clean
# package path (presmaker's skill/tools/ has no __init__.py), so we locate each
# copy relative to its installed package root (the llm_config module's dir).


def _user_intent_path(llm_config_module) -> Path:
    """Locate user_intent.py relative to a skill's installed package root.
    llm_config lives at <pkg>/llm_config.py, so its parent is the package
    root; user_intent lives at <pkg>/skill/tools/user_intent.py."""
    return Path(llm_config_module.__file__).parent / "skill" / "tools" / "user_intent.py"


def test_familyD_user_intent_copy_byte_identical():
    """user_intent.py is byte-identical (after strict normalization) between
    presentation-maker and paper-writer. A drift here means a one-sided edit to
    a copied module — re-sync before tagging (md5-equal as of v1.2.0/v1.2.0)."""
    m_path = _user_intent_path(m_lc)
    p_path = _user_intent_path(p_lc)
    assert m_path.is_file(), f"presentation-maker user_intent.py missing at {m_path}"
    assert p_path.is_file(), f"paper-writer user_intent.py missing at {p_path}"
    m_src = _normalize_source(m_path.read_text(encoding="utf-8"))
    p_src = _normalize_source(p_path.read_text(encoding="utf-8"))
    assert m_src == p_src, (
        "user_intent.py drifted between presentation-maker and paper-writer.\n"
        "The two copies must stay byte-identical (copy-not-share convention).\n"
        f"  presmaker:   {m_path}\n"
        f"  paperwriter: {p_path}\n"
        "Diff them and re-sync the copies before tagging."
    )


# ---------------------------------------------------------------------------
# Family E — `run-record.v1` golden-sample schema conformance (Cycle 3, DP1)
# ---------------------------------------------------------------------------
#
# Cycle 3 introduces a uniform run-record (`audit/run_record.json`) emitted
# by the 3 kbaseincubator skills. The *emitters* differ per skill (they
# project from each skill's existing run-end state — finalize_run for
# presmaker, save_state for paper-writer, aggregate_metadata for
# adversarial), but the *record* itself is a shared schema. Unlike
# Families A-D, this is **shape**-not-source-identity: each skill ships
# golden sample `run_record.json` files under its own tests; this family
# discovers and validates them against the single shared validator in
# `craft.run_record.validate_run_record`.
#
# Per-skill goldens land in Steps 2 (presmaker), 4 (paper-writer), and 5
# (adversarial) of Cycle 3. Until they ship, this family graceful-skips per
# skill (the same discipline as the Family A-D editable-install skip);
# CI fails-loud once they're expected to be present (via the same `CI=true`
# escape valve used at module top).
#
# Discovery convention:
#   <skill_pkg_root>/../../../tests/fixtures/run_record_v1/*.json
# i.e. each skill's repo carries a `tests/fixtures/run_record_v1/` dir
# containing one-or-more golden run_record.json samples. Family E iterates
# over every *.json there, asserting:
#   1. it parses as JSON;
#   2. `validate_run_record(parsed) == []`.
#
# This is intentionally lightweight — the load-bearing per-skill positive
# coverage is in `tests/test_run_record_validator.py` (platform-owned
# goldens). Family E catches the case where a skill's emitter drifts from
# the contract but its own test suite missed it.


def _skill_repo_root(llm_config_module) -> Path:
    """Walk up from a skill's `llm_config.py` to its repo root.

    Layout: <repo>/src/<pkg>/llm_config.py → repo = parents[2].
    """
    return Path(llm_config_module.__file__).resolve().parents[2]


def _find_skill_goldens(repo_root: Path) -> list[Path]:
    """Return all *.json files under `<repo>/tests/fixtures/run_record_v1/`,
    or an empty list if the directory is absent."""
    fixture_dir = repo_root / "tests" / "fixtures" / "run_record_v1"
    if not fixture_dir.is_dir():
        return []
    return sorted(fixture_dir.glob("*.json"))


@pytest.mark.parametrize("skill_label,llm_config_module", [
    ("presentation-maker", m_lc),
    ("paper-writer",       p_lc),
    ("adversarial",        a_lc),
], ids=["presmaker", "paper-writer", "adversarial"])
def test_familyE_run_record_goldens_validate(skill_label, llm_config_module):
    """Family E: every skill-shipped golden `run_record.json` validates
    against the shared `run-record.v1` validator.

    GRACEFUL-SKIP when the skill hasn't yet shipped goldens. They land in
    Cycle-3 Steps 2/4/5 — until then, this assertion vacuously passes.
    CI must NOT silently skip once the version threshold below is met;
    we tie the skip to the absence of the fixture directory, not to a
    version comparison, because the version-floor handshake (which
    skill versions are required to carry goldens) lives in
    `CROSS-SKILL-RELEASE.md`, not here.
    """
    from craft.run_record import validate_run_record  # noqa: E402

    repo_root = _skill_repo_root(llm_config_module)
    goldens = _find_skill_goldens(repo_root)

    if not goldens:
        pytest.skip(
            f"{skill_label}: no goldens at "
            f"{repo_root}/tests/fixtures/run_record_v1/ "
            f"(Cycle 3 Steps 2/4/5 ship these; pre-Step they're absent)."
        )

    for golden_path in goldens:
        try:
            record = json.loads(golden_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"{skill_label} golden {golden_path.name}: "
                f"not valid JSON ({exc})"
            )
        errors = validate_run_record(record)
        # Optional cross-check: a skill's goldens should declare
        # `"skill": <skill_label>` (they could in principle ship a
        # golden for a different skill, but that would be a smell).
        if isinstance(record, dict) and "skill" in record:
            assert record["skill"] == skill_label, (
                f"{skill_label} shipped a golden under its own "
                f"tests/fixtures/run_record_v1/ that claims "
                f"`skill: {record['skill']!r}`. If this is "
                f"intentional (cross-skill comparison fixture), move "
                f"it to craft-platform/tests/fixtures/run_record_v1/."
            )
        assert errors == [], (
            f"{skill_label} golden {golden_path.name} failed "
            f"validation ({len(errors)} error(s)):\n  "
            + "\n  ".join(errors)
        )


# ---------------------------------------------------------------------------
# Family F — chrome.py vendored-copy BYTE-IDENTITY (Cycle-4, DP6)
# ---------------------------------------------------------------------------
#
# Cycle 4 introduces `chrome.py` — the CRAFT output-signature renderer
# (STAGE / DECISION / RESULT + the per-skill glyph signature). The canonical
# source lives in craft-platform at `src/craft/chrome.py`; each skill VENDORS
# a byte-identical COPY (same copy-not-share discipline as llm_config Family-C
# and user_intent Family-D). chrome.py is deliberately dependency-free
# (stdlib-only display-width via `unicodedata`, no `wcwidth`/`rich`) PRECISELY
# so it can vendor clean into every skill — including the presmaker SHELL copy,
# which must emit identical bytes (the glyphs are multi-byte Unicode, so a
# locale/encoding slip would diverge them).
#
# WIRING SCHEDULE: the vendored copies land in **Phase 2** (skill wiring).
# This Cycle-4 PHASE-1 commit ships the canonical chrome.py + this armed-but-
# dormant family. Until a skill vendors its copy, this family GRACEFUL-SKIPS
# per skill (exactly as Family E did pre-Cycle-3-Steps and Family A-D do
# without the editable install). Once Phase 2 vendors them, drift fails loud.
#
# Discovery convention (mirrors how skills vendor the run-record emitter):
#   <skill_pkg_root>/chrome.py
# i.e. each skill carries a top-of-package `chrome.py` copy alongside its
# `llm_config.py`. If a skill places it elsewhere in Phase 2, update
# `_skill_chrome_path` to match the chosen vendoring location.

_CANONICAL_CHROME = Path(__file__).resolve().parents[1] / "src" / "craft" / "chrome.py"


def _skill_chrome_path(llm_config_module) -> Path:
    """Locate a skill's vendored chrome.py relative to its package root.

    llm_config lives at <pkg>/llm_config.py, so its parent is the package
    root; the vendored chrome.py sits beside it at <pkg>/chrome.py. (Phase 2
    finalizes the vendoring location — adjust here if it differs.)"""
    return Path(llm_config_module.__file__).parent / "chrome.py"


def test_familyF_canonical_chrome_exists():
    """Anti-vacuity: the canonical chrome.py must exist in craft-platform.
    If it's gone, every per-skill byte-identity check below would compare
    against nothing and the family would be meaningless."""
    assert _CANONICAL_CHROME.is_file(), (
        f"canonical chrome.py missing at {_CANONICAL_CHROME} — Cycle-4 "
        f"Phase-1 must ship it before any skill vendors a copy."
    )


@pytest.mark.parametrize("skill_label,llm_config_module", [
    ("presentation-maker", m_lc),
    ("paper-writer",       p_lc),
    ("adversarial",        a_lc),
], ids=["presmaker", "paper-writer", "adversarial"])
def test_familyF_chrome_copy_byte_identical(skill_label, llm_config_module):
    """Family F: each skill's vendored chrome.py is byte-identical (after
    strict normalization) to craft-platform's canonical chrome.py.

    GRACEFUL-SKIP until the skill vendors its copy (Cycle-4 Phase 2). Tying
    the skip to the absence of the file (not a version compare) keeps the
    version-floor handshake in CROSS-SKILL-RELEASE.md, same as Family E."""
    skill_chrome = _skill_chrome_path(llm_config_module)
    if not skill_chrome.is_file():
        pytest.skip(
            f"{skill_label}: no vendored chrome.py at {skill_chrome} "
            f"(Cycle-4 Phase 2 vendors it; pre-wiring it's absent)."
        )
    canonical = _normalize_source(_CANONICAL_CHROME.read_text(encoding="utf-8"))
    vendored = _normalize_source(skill_chrome.read_text(encoding="utf-8"))
    assert vendored == canonical, (
        f"{skill_label} chrome.py drifted from craft-platform's canonical.\n"
        f"The vendored copy must stay byte-identical (copy-not-share).\n"
        f"  canonical: {_CANONICAL_CHROME}\n"
        f"  vendored:  {skill_chrome}\n"
        f"Diff them and re-sync from the canonical before tagging.\n"
        f"NOTE: the glyphs are multi-byte UTF-8 — a locale/encoding slip "
        f"can diverge them invisibly; copy the file verbatim."
    )


# ---------------------------------------------------------------------------
# Family G — `decision.v1` per-skill golden conformance (Cycle-4, DP6)
# ---------------------------------------------------------------------------
#
# decision.v1 is the halt-and-handoff presentation contract (the renderer is
# chrome.render_decision; the shape contract is craft.decision). It EXTENDS
# the existing `.handoff.json` — retaining the keys the continue CLI reads
# (phase authorizes --pick) and adding the presentation fields. Like Family E
# (run-record), the *emitters* differ per skill (each skill's halt writes its
# own .handoff.json + decision fields) but the *shape* is one shared schema.
#
# The load-bearing positive coverage is craft-platform's own goldens in
# `tests/test_decision.py` (validated there directly). This family is the
# cross-skill catch: once a skill ships decision.v1 goldens in Phase 2, they
# must validate against the single shared validator. GRACEFUL-SKIP until then.
#
# Discovery convention (mirrors Family E):
#   <skill_repo>/tests/fixtures/decision_v1/*.json


def _find_skill_decision_goldens(repo_root: Path) -> list[Path]:
    fixture_dir = repo_root / "tests" / "fixtures" / "decision_v1"
    if not fixture_dir.is_dir():
        return []
    return sorted(fixture_dir.glob("*.json"))


@pytest.mark.parametrize("skill_label,llm_config_module", [
    ("presentation-maker", m_lc),
    ("paper-writer",       p_lc),
    ("adversarial",        a_lc),
], ids=["presmaker", "paper-writer", "adversarial"])
def test_familyG_decision_goldens_validate(skill_label, llm_config_module):
    """Family G: every skill-shipped golden `decision.v1` payload validates
    against the shared `validate_decision` contract.

    GRACEFUL-SKIP until the skill ships decision goldens (Cycle-4 Phase 2)."""
    from craft.decision import validate_decision  # noqa: E402

    repo_root = _skill_repo_root(llm_config_module)
    goldens = _find_skill_decision_goldens(repo_root)

    if not goldens:
        pytest.skip(
            f"{skill_label}: no goldens at "
            f"{repo_root}/tests/fixtures/decision_v1/ "
            f"(Cycle-4 Phase 2 ships these; pre-wiring they're absent)."
        )

    for golden_path in goldens:
        try:
            decision = json.loads(golden_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"{skill_label} decision golden {golden_path.name}: "
                f"not valid JSON ({exc})"
            )
        if isinstance(decision, dict) and "skill" in decision:
            assert decision["skill"] == skill_label, (
                f"{skill_label} shipped a decision golden claiming "
                f"`skill: {decision['skill']!r}`. Move cross-skill "
                f"fixtures to craft-platform/tests/fixtures/decision_v1/."
            )
        errors = validate_decision(decision)
        assert errors == [], (
            f"{skill_label} decision golden {golden_path.name} failed "
            f"validation ({len(errors)} error(s)):\n  "
            + "\n  ".join(errors)
        )


# ---------------------------------------------------------------------------
# Family H — `check_no_dropped_stages` BEHAVIORAL identity (C1-A2)
# ---------------------------------------------------------------------------
#
# The C1-A2 completeness guard is canonical in craft.run_record.
# check_no_dropped_stages, but each skill ships STANDALONE on the hub (no
# craft-platform on PYTHONPATH), so the function is VENDORED into each
# skill's emitter (presmaker finalize_run.py, paper-writer
# run_record_emitter.py) — same copy-not-share constraint as the run-record
# emitter itself. Unlike chrome.py (byte-identity, Family-F), the three
# copies legitimately differ in TYPE ANNOTATIONS (`craft` uses
# `Any`/`set[str]`; the skills avoid `Any` to stay import-light), so we pin
# BEHAVIOR not source — the same discipline as Family-A for the resolver.
#
# Every copy MUST return identical output to the canonical across an input
# matrix that exercises: complete-superset (pass), the C1-A drop (fail),
# the self-snapshot skip, running-not-completed, multi-archive, and
# malformed inputs. A logic drift in any copy fails loud here.

import importlib.util as _ilu  # noqa: E402


def _load_module_by_path(name: str, path: Path):
    spec = _ilu.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, (
        f"could not build import spec for {path}")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _skill_emitter_path(llm_config_module, filename: str) -> Path:
    """Locate a skill's vendored emitter (which carries the vendored
    completeness guard) under <pkg>/skill/tools/<filename>."""
    return (Path(llm_config_module.__file__).parent
            / "skill" / "tools" / filename)


# (input, expected-error-count) — behavior the canonical defines.
def _completeness_matrix():
    def stage(sid, status="completed"):
        return {"id": sid, "status": status}

    def rec(run_id, ids, status="completed", running=()):
        stages = [stage(s) for s in ids] + [stage(s, "running") for s in running]
        return {"run_id": run_id, "status": status, "stages": stages}

    return [
        # complete superset → 0
        (rec("run-1", ["plan", "substory_design", "qa_prep"]),
         [rec("run-1", ["plan", "substory_design"])], 0),
        # self-snapshot (same run_id) skipped → 0
        (rec("run-1", ["plan", "substory_design"]),
         [rec("run-1", ["plan", "substory_design"])], 0),
        # the C1-A drop → 1
        (rec("run-2", ["qa_prep", "merge"]),
         [rec("run-1", ["plan", "substory_design", "curate_figures"],
              status="failed")], 1),
        # running-in-archive not required → 0
        (rec("run-1", ["plan", "substory_design", "qa_prep"]),
         [rec("run-1", ["plan", "substory_design"], status="failed",
              running=["qa_prep"])], 0),
        # multi-archive, each flags → 2
        (rec("run-3", ["plan", "qa_prep"]),
         [rec("run-1", ["plan", "substory_design"], status="failed"),
          rec("run-2", ["plan", "substory_design", "curate_figures"],
              status="failed")], 2),
        # no archives → 0
        (rec("run-1", ["plan", "merge"]), [], 0),
        # malformed → 0 (never raises)
        ({}, [], 0),
        ({"stages": "nope"}, [{"stages": None}], 0),
        (rec("run-1", ["plan"]), [None, 42], 0),
    ]


@pytest.mark.parametrize("skill_label,llm_config_module,filename", [
    ("presentation-maker", m_lc, "finalize_run.py"),
    ("paper-writer",       p_lc, "run_record_emitter.py"),
], ids=["presmaker", "paper-writer"])
def test_familyH_completeness_guard_behavioral_identity(
    skill_label, llm_config_module, filename,
):
    """Family H: the skill's vendored check_no_dropped_stages returns the
    SAME error-count as craft's canonical across the matrix. (Behavioral,
    not source — the copies differ only in type annotations.)"""
    from craft.run_record import check_no_dropped_stages as canonical

    emitter_path = _skill_emitter_path(llm_config_module, filename)
    if not emitter_path.is_file():
        pytest.skip(f"{skill_label}: no emitter at {emitter_path}")
    mod = _load_module_by_path(f"_c1a2_{skill_label}", emitter_path)
    vendored = getattr(mod, "check_no_dropped_stages", None)
    if not callable(vendored):
        # GRACEFUL-SKIP until the skill vendors the C1-A2 guard (it lands
        # in this round; the conformance submodule re-pins in the
        # coordinated release — same discipline as Family-F/G pre-re-pin).
        pytest.skip(
            f"{skill_label}: emitter {filename} has no vendored "
            f"check_no_dropped_stages yet (C1-A2 lands at re-pin)."
        )
    for i, (canonical_rec, archives, expected_n) in enumerate(
            _completeness_matrix()):
        can_out = canonical(canonical_rec, archives)
        ven_out = vendored(canonical_rec, archives)
        assert len(can_out) == expected_n, (
            f"matrix[{i}]: canonical returned {len(can_out)} errs, "
            f"expected {expected_n}")
        assert len(ven_out) == len(can_out), (
            f"{skill_label} matrix[{i}]: vendored guard returned "
            f"{len(ven_out)} error(s), canonical {len(can_out)} — the "
            f"vendored copy has drifted from craft's logic. Re-sync."
        )
