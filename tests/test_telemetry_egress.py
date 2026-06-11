"""C1 Workstream D — telemetry egress: the WHITELIST REDACTION AUDIT (the
load-bearing safety guard) + off-switch/consent + batching/per-user-key +
best-effort swallow.

The redaction audit is the SHIP GATE: the egress payload contains ONLY
enumerated CRAFT_KEEP fields, and disallowed shapes (draft_dir, project/draft
names, presenter/author strings, any path) NEVER appear — even buried in a kept
field. "You can't leak what you don't emit": the strongest test crafts a
run-record stuffed with identifier-shaped values in dropped fields and asserts
none egress.

Mirrors narrative-connector's tests/unit/test_telemetry_egress.py 1:1 in shape,
specialised to CRAFT's run-record. The fixtures use REAL run-record stage shapes
(run_record._REQUIRED_STAGE_KEYS) so the audit can't pass against a toy record.
"""
from __future__ import annotations

import json
import re

from craft import telemetry as tx
from craft.telemetry import egress as txe


# --- a recorder for the injected writer (the real (target_uri, lines) shape) --

class _Sink:
    def __init__(self, *, fail=False):
        self.calls = []  # (target_uri, payload_lines)
        self.fail = fail

    def __call__(self, *, target_uri, payload_lines):
        if self.fail:
            raise RuntimeError("s3 down")
        self.calls.append((target_uri, payload_lines))
        return sum(len(line) for line in payload_lines)

    @property
    def records(self):
        out = []
        for _uri, lines in self.calls:
            out.extend(json.loads(line) for line in lines)
        return out


# --- realistic run-record fixtures (REAL stage schema) ----------------------

def _full_stage(**over):
    """A stage entry with the full run-record stage schema
    (run_record._REQUIRED_STAGE_KEYS) — id/status/model/started_at/finished_at/
    elapsed_seconds/input|output|cache_*_tokens/cost_usd/subrecord."""
    s = {
        "id": "slide_compose", "status": "completed", "model": "sonnet",
        "started_at": "2026-06-08T17:01:05Z",
        "finished_at": "2026-06-08T17:06:00Z",
        "elapsed_seconds": 295.0, "input_tokens": 1200, "output_tokens": 800,
        "cache_read_tokens": 300, "cache_creation_tokens": 100,
        "cost_usd": 0.42,
        # subrecord on the real record is a path-ish pointer → MUST drop.
        "subrecord": "audit/runs/run-1/slide_compose.json",
    }
    s.update(over)
    return s


def _rich_record():
    """A FULL run-record carrying every identifier trap in the DROPPED fields —
    an absolute draft_dir, a semantic project/draft name, presenter/title text
    in subrecord — so the audit proves none of them egress."""
    return {
        "schema_version": "run-record.v1",
        "skill": "presentation-maker",
        "skill_version": "1.3.1",
        "run_id": "run-2",
        # the identifier trap: an absolute path with a semantic project name.
        "draft_dir":
            "/Users/aparkin/BERIL/projects/caulobacter_fur_lipida_loss/talks/draft_2",
        "mode": "talk-30",
        "status": "completed",
        "started_at": "2026-06-08T17:00:00Z",
        "finished_at": "2026-06-08T17:42:00Z",
        "exit_code": 0,
        "current_stage": None,
        "stages": [
            _full_stage(id="plan", cost_usd=0.20,
                        subrecord="audit/runs/run-1/00_plan.md"),
            _full_stage(
                id="slide_compose",
                # a presenter/title string buried in subrecord → MUST NOT leak.
                subrecord="presenter=Adam Arkin; title=Caulobacter fur lipida loss"),
        ],
        "totals": {
            "cost_usd": 0.62, "input_tokens": 2400, "output_tokens": 1600,
            "cache_read_tokens": 600, "cache_creation_tokens": 200,
            "elapsed_seconds": 590.0,
        },
        "models_used": ["sonnet"],
        "artifacts": {"user_intent": True, "deliverable_validation": True,
                      "deliverable": "deliverable/draft.pptx"},
    }


# ===================================================================
# The whitelist redaction audit (the SHIP GATE)
# ===================================================================

def test_keep_set_is_exactly_the_audited_allowlist():
    """Pin the whitelist: any future change adds a KEEP field only with an
    explicit, audited justification (the strict-allowlist discipline)."""
    assert tx.CRAFT_KEEP == frozenset({
        "ts", "kind", "op", "skill", "skill_version", "mode", "status",
        "model", "error_class", "cost_usd", "input_tokens", "output_tokens",
        "cache_read_tokens", "cache_creation_tokens", "duration_ms",
        "run_id", "draft_hash",
    })


def test_redaction_audit_only_keep_fields_egress():
    recs = tx.project_record(_rich_record(), user="aparkin",
                             craft_version="0.4.2")
    allowed = set(tx.CRAFT_KEEP) | {"user", "craft_version"}
    for rec in recs:
        assert set(rec).issubset(allowed), (
            f"non-allowlist key egressed: {set(rec) - allowed}")
    # per-stage records carry the computed + shared fields.
    stage_recs = [r for r in recs if r.get("kind") != "run_finalize"]
    assert stage_recs
    sc = next(r for r in stage_recs if r["op"] == "slide_compose")
    assert sc["status"] == "completed" and sc["model"] == "sonnet"
    assert sc["cost_usd"] == 0.42
    assert sc["duration_ms"] == 295000.0          # elapsed_seconds×1000
    assert sc["ts"] > 0                            # computed epoch
    assert sc["skill"] == "presentation-maker"
    assert sc["run_id"] == "run-2"
    assert "draft_hash" in sc
    assert sc["user"] == "aparkin" and sc["craft_version"] == "0.4.2"
    # the run-level record.
    run = next(r for r in recs if r.get("kind") == "run_finalize")
    assert run["status"] == "completed" and run["cost_usd"] == 0.62
    assert run["duration_ms"] == 590000.0


def test_redaction_audit_blob_form_no_identifier_survives():
    """The STRONGEST form: build a record stuffed with identifier-shaped values
    in dropped fields, project it, then assert NONE of those strings — no
    abs-path, no draft-name token, no presenter — appear ANYWHERE in the
    serialized payload."""
    recs = tx.project_record(_rich_record(), user="aparkin",
                             craft_version="0.4.2")
    blob = json.dumps(recs)
    for shape in (
        "caulobacter_fur_lipida_loss",          # project NAME
        "draft_2",                              # draft NAME
        "/Users/",                              # abs path root
        "/Users/aparkin/BERIL/projects",        # the draft_dir
        "talks",                                # path segment
        "Adam Arkin",                           # presenter
        "Caulobacter fur lipida loss",          # title
        "audit/runs",                           # subrecord path
        ".pptx",                                # artifact filename
        "draft_dir", "subrecord", "models_used",  # banned KEYS
    ):
        assert shape not in blob, f"disallowed shape {shape!r} egressed"
    # And no absolute-path leading slash anywhere in a value.
    for rec in recs:
        for v in rec.values():
            if isinstance(v, str):
                assert not v.startswith("/"), f"abs path leaked: {v!r}"


def test_banned_keys_never_appear():
    recs = tx.project_record(_rich_record(), user="u", craft_version="0")
    for rec in recs:
        for banned in ("draft_dir", "subrecord", "models_used", "artifacts",
                       "schema_version", "exit_code", "current_stage",
                       "started_at", "finished_at", "elapsed_seconds", "id"):
            assert banned not in rec, f"{banned} leaked"


def test_draft_hash_is_opaque():
    """draft_hash is fixed-length hex, has no '/', and contains no name
    substring. Deterministic for the same names; user not folded in."""
    rec = tx.project_record(_rich_record(), user="aparkin",
                            craft_version="0")[0]
    dh = rec["draft_hash"]
    assert len(dh) == 16 and all(c in "0123456789abcdef" for c in dh)
    assert "/" not in dh
    assert "caulobacter" not in dh and "draft_2" not in dh
    # same names → same hash regardless of user.
    rec2 = tx.project_record(_rich_record(), user="someone_else",
                             craft_version="9")[0]
    assert rec2["draft_hash"] == dh
    assert not re.search(r"\d+/\d+/\d+", dh)


def test_future_field_does_not_silently_egress():
    """Drop-by-default: a NEW unknown field on a stage (or the record) is absent
    from CRAFT_KEEP → it never egresses (forward-safety)."""
    rec = _rich_record()
    rec["secret_field"] = "leak-me"
    rec["stages"][0]["another_secret"] = "leak-me-too"
    recs = tx.project_record(rec, user="u", craft_version="0")
    blob = json.dumps(recs)
    assert "leak-me" not in blob
    assert "secret_field" not in blob and "another_secret" not in blob


def test_error_class_reserved_absent_until_populated():
    """error_class is in KEEP (reserved) but NOT on the run-record today →
    it's absent from every projected record (never fabricated)."""
    recs = tx.project_record(_rich_record(), user="u", craft_version="0")
    for rec in recs:
        assert "error_class" not in rec
    # but if a future record DID carry it on a stage, it would egress.
    rec = _rich_record()
    rec["stages"][0]["error_class"] = "ToolTimeout"
    recs2 = tx.project_record(rec, user="u", craft_version="0")
    sc = next(r for r in recs2 if r.get("op") == "plan")
    assert sc["error_class"] == "ToolTimeout"


# ===================================================================
# Off-switch / consent
# ===================================================================

def test_default_on_root_resolution(monkeypatch):
    monkeypatch.delenv(txe.TELEMETRY_ROOT_ENV, raising=False)
    assert txe.egress_root() == txe.DEFAULT_TELEMETRY_ROOT == "/global_share"
    for off in ("off", "local", "none", "disabled", "", "OFF"):
        monkeypatch.setenv(txe.TELEMETRY_ROOT_ENV, off)
        assert txe.egress_root() is None, f"{off!r} should disable"
    monkeypatch.setenv(txe.TELEMETRY_ROOT_ENV, "s3a://bkt/pref")
    assert txe.egress_root() == "s3a://bkt/pref"


def test_egress_disabled_when_root_off(monkeypatch, tmp_path):
    monkeypatch.setenv(txe.TELEMETRY_ROOT_ENV, "off")
    sink = _Sink()
    out = txe.egress_run_record(_rich_record(), audit_dir=tmp_path,
                                user="u", upload=sink)
    assert out is None
    assert sink.calls == []          # upload NEVER called — cheap no-op


def test_consent_printed_once_and_flag_recorded(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv(txe.TELEMETRY_ROOT_ENV, str(tmp_path / "root"))
    audit = tmp_path / "audit"
    audit.mkdir()
    sink = _Sink()
    txe.egress_run_record(_rich_record(), audit_dir=audit, user="aparkin",
                          upload=sink, batch_id="run-2")
    err1 = capsys.readouterr().err
    assert "telemetry" in err1.lower() and "opt out" in err1.lower()
    assert txe._consent_flag_path(audit).exists()
    # second egress → no re-prompt.
    txe.egress_run_record(_rich_record(), audit_dir=audit, user="aparkin",
                          upload=sink, batch_id="run-3")
    err2 = capsys.readouterr().err
    assert "opt out" not in err2.lower()


def test_consent_is_non_blocking_under_closed_stdin(monkeypatch, tmp_path):
    """Load-bearing for default-on: consent is print+flag, NEVER input()."""
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    def _boom(*a, **k):
        raise AssertionError("_ensure_consent must NOT call input()")
    monkeypatch.setattr("builtins.input", _boom)
    audit = tmp_path / "audit"
    audit.mkdir()
    txe._ensure_consent(root="/global_share", user="aparkin", audit_dir=audit)
    assert txe._consent_flag_path(audit).exists()


def test_consent_notice_states_what_where_and_optout(monkeypatch, tmp_path,
                                                     capsys):
    audit = tmp_path / "audit"
    audit.mkdir()
    txe._ensure_consent(root="/global_share", user="aparkin", audit_dir=audit)
    err = capsys.readouterr().err.lower()
    assert "/global_share" in err
    assert "aparkin" in err and "username" in err
    assert txe.TELEMETRY_ROOT_ENV.lower() in err and "off" in err


# ===================================================================
# Batching + per-user key
# ===================================================================

def test_one_file_per_finalize_keyed_by_user_draft_and_run(monkeypatch,
                                                           tmp_path):
    monkeypatch.setenv(txe.TELEMETRY_ROOT_ENV, "s3a://bkt/pref")
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / txe._CONSENT_FLAG).write_text("consented\n")  # pre-consent
    sink = _Sink()
    out = txe.egress_run_record(_rich_record(), audit_dir=audit,
                                user="aparkin", upload=sink, now=0.0)
    assert out is not None and out > 0
    assert len(sink.calls) == 1                # ONE batched file
    uri, lines = sink.calls[0]
    # 2 stages + 1 run-level = 3 records in the one file.
    assert len(lines) == 3
    # The default batch key is <draft_hash>-<run_id> (CRAFT's run-N is
    # per-draft, so it must carry the opaque draft_hash to avoid collision
    # across drafts that both start at run-1 — see the cross-draft test).
    dh = txe._draft_hash(*txe._draft_names(_rich_record()["draft_dir"]))
    assert uri == (
        f"s3a://bkt/pref/telemetry/craft/aparkin/1970-01/{dh}-run-2.jsonl")
    # the draft_hash in the filename is opaque (no name leak in the path).
    assert "caulobacter" not in uri and "draft_2" not in uri


def test_two_drafts_same_run_n_no_collision(monkeypatch, tmp_path):
    """C1-D collision guard: two DIFFERENT drafts both at run-1 (CRAFT's
    run-N is per-draft) must NOT clobber each other — the opaque draft_hash
    in the batch key disambiguates them. (Caught in the e2e: without it,
    the second finalize overwrote the first.)"""
    monkeypatch.setenv(txe.TELEMETRY_ROOT_ENV, "s3a://bkt")
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / txe._CONSENT_FLAG).write_text("consented\n")
    sink = _Sink()
    rec_a = _rich_record()
    rec_a["run_id"] = "run-1"
    rec_a["draft_dir"] = "/x/projects/alpha_project/talks/draft_1"
    rec_b = _rich_record()
    rec_b["run_id"] = "run-1"
    rec_b["draft_dir"] = "/x/projects/beta_project/talks/draft_1"
    txe.egress_run_record(rec_a, audit_dir=audit, user="u", upload=sink,
                          now=0.0)
    txe.egress_run_record(rec_b, audit_dir=audit, user="u", upload=sink,
                          now=0.0)
    uris = [c[0] for c in sink.calls]
    assert uris[0] != uris[1], "two drafts at run-1 collided on one file"
    assert "run-1.jsonl" in uris[0] and "run-1.jsonl" in uris[1]


def test_two_users_two_keys_no_collision(monkeypatch, tmp_path):
    monkeypatch.setenv(txe.TELEMETRY_ROOT_ENV, "s3a://bkt")
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / txe._CONSENT_FLAG).write_text("consented\n")
    sink = _Sink()
    txe.egress_run_record(_rich_record(), audit_dir=audit, user="alice",
                          upload=sink, now=0.0, batch_id="run-1")
    txe.egress_run_record(_rich_record(), audit_dir=audit, user="bob",
                          upload=sink, now=0.0, batch_id="run-1")
    uris = [c[0] for c in sink.calls]
    assert "telemetry/craft/alice/1970-01/run-1.jsonl" in uris[0]
    assert "telemetry/craft/bob/1970-01/run-1.jsonl" in uris[1]
    assert uris[0] != uris[1]


# ===================================================================
# Best-effort swallow (the never-perturb discipline)
# ===================================================================

def test_upload_failure_is_swallowed(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv(txe.TELEMETRY_ROOT_ENV, "s3a://bkt")
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / txe._CONSENT_FLAG).write_text("consented\n")
    out = txe.egress_run_record(_rich_record(), audit_dir=audit, user="u",
                                upload=_Sink(fail=True))
    assert out is None             # swallowed, no raise
    assert "telemetry egress skipped" in capsys.readouterr().err.lower()


def test_local_root_writes_a_real_file(monkeypatch, tmp_path):
    """Default _default_upload to a local/mounted root writes the JSONL file —
    the dev-prefix path the read surface consumes."""
    root = tmp_path / "gs"
    monkeypatch.setenv(txe.TELEMETRY_ROOT_ENV, str(root))
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / txe._CONSENT_FLAG).write_text("consented\n")
    out = txe.egress_run_record(_rich_record(), audit_dir=audit,
                                user="aparkin", now=0.0)
    assert out is not None and out > 0
    dh = txe._draft_hash(*txe._draft_names(_rich_record()["draft_dir"]))
    f = (root / "telemetry" / "craft" / "aparkin" / "1970-01"
         / f"{dh}-run-2.jsonl")
    assert f.is_file()
    recs = [json.loads(line) for line in f.read_text().splitlines() if line]
    assert len(recs) == 3
    # the file on disk passes the redaction audit too.
    blob = f.read_text()
    assert "caulobacter" not in blob and "/Users/" not in blob
