"""v3.13 H2b1 — roadmap small-trio coverage tranche.

Three ``_internal/roadmap/*.py`` files pulled out of
``coverage.run.omit`` by this PR:

- ``change_proposals.py`` — ``validate_change`` schema errors +
  ``apply_change_to_roadmap_obj`` with 4 patch ops (append_note,
  replace_notes, replace_steps, replace_title). Fail-closed validation
  surfaces ``CHANGE_INVALID`` / ``CHANGE_TYPE_UNSUPPORTED`` /
  ``PATCH_OP_UNSUPPORTED`` with structured messages.
- ``sanitize.py`` — ``scan_directory`` rule matrix
  (FORBIDDEN_TOKEN / EMAIL_DETECTED / PRIVATE_KEY_MARKER /
  TOKEN_PREFIX_DETECTED) + ``findings_fingerprint`` determinism.
- ``evidence.py`` — ``init_evidence_dir`` layout + ``write_step_evidence``
  per-step artefact tree + ``write_integrity_manifest`` SHA-256 envelope.

v3.12 H2a (tranche 5A) left these deeper-surface siblings omitted. v3.13
H2b1 closes the gap with pins written against the real APIs (per Codex
plan-time guardrail: ``change_proposals`` is not a dataclass module,
``sanitize`` is directory scan + fingerprint, ``evidence`` is the
per-step artefact + manifest writer — NOT a JSONL event writer).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# change_proposals.py
# ---------------------------------------------------------------------------


def _write_change_schema(tmp_path: Path) -> Path:
    """Minimal JSON Schema accepting the modify/patches envelope."""
    schema_obj: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["type", "target", "patches"],
        "properties": {
            "type": {"type": "string", "enum": ["modify"]},
            "target": {
                "type": "object",
                "required": ["milestone_id"],
                "properties": {"milestone_id": {"type": "string", "minLength": 1}},
            },
            "patches": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "object", "required": ["op", "milestone_id"]},
            },
        },
    }
    path = tmp_path / "change.schema.v1.json"
    path.write_text(json.dumps(schema_obj), encoding="utf-8")
    return path


class TestValidateChange:
    def test_valid_change_returns_empty_errors(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.change_proposals import validate_change

        schema_path = _write_change_schema(tmp_path)
        change = {
            "type": "modify",
            "target": {"milestone_id": "M1"},
            "patches": [{"op": "append_milestone_note", "milestone_id": "M1", "note": "n"}],
        }
        assert validate_change(change, schema_path) == []

    def test_missing_required_fields_collects_messages(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.change_proposals import validate_change

        schema_path = _write_change_schema(tmp_path)
        # No `target`, no `patches` → 2 required-field errors.
        errors = validate_change({"type": "modify"}, schema_path)
        assert len(errors) >= 2
        # Each message carries its json_path anchor.
        assert all(":" in e for e in errors)

    def test_wrong_type_enum_is_reported(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.change_proposals import validate_change

        schema_path = _write_change_schema(tmp_path)
        errors = validate_change(
            {"type": "delete", "target": {"milestone_id": "M1"}, "patches": [{"op": "x", "milestone_id": "M1"}]},
            schema_path,
        )
        assert any("delete" in e for e in errors)


class TestApplyChangeTypeGuards:
    def test_non_modify_change_type_raises(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="CHANGE_TYPE_UNSUPPORTED"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": []},
                change_obj={"type": "delete"},
            )

    def test_missing_target_milestone_id_raises(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="target.milestone_id missing"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": []},
                change_obj={"type": "modify", "target": {}, "patches": [{}]},
            )

    def test_empty_patches_raises(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="patches must be a non-empty list"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={"type": "modify", "target": {"milestone_id": "M1"}, "patches": []},
            )

    def test_patch_milestone_id_mismatch_raises(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="patch.milestone_id must match target.milestone_id"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [{"op": "append_milestone_note", "milestone_id": "M2", "note": "n"}],
                },
            )

    def test_milestone_not_found_raises(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="milestone not found"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": []},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [{"op": "append_milestone_note", "milestone_id": "M1", "note": "n"}],
                },
            )

    def test_unsupported_patch_op_raises(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="PATCH_OP_UNSUPPORTED"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [{"op": "delete_milestone", "milestone_id": "M1"}],
                },
            )


class TestApplyChangePatchOps:
    def test_append_milestone_note_preserves_existing(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        result = apply_change_to_roadmap_obj(
            roadmap_obj={"milestones": [{"id": "M1", "notes": ["first"]}]},
            change_obj={
                "type": "modify",
                "target": {"milestone_id": "M1"},
                "patches": [
                    {"op": "append_milestone_note", "milestone_id": "M1", "note": "second"},
                ],
            },
        )
        assert result["milestones"][0]["notes"] == ["first", "second"]

    def test_append_milestone_note_initializes_list_when_absent(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        result = apply_change_to_roadmap_obj(
            roadmap_obj={"milestones": [{"id": "M1"}]},  # no notes
            change_obj={
                "type": "modify",
                "target": {"milestone_id": "M1"},
                "patches": [{"op": "append_milestone_note", "milestone_id": "M1", "note": "alpha"}],
            },
        )
        assert result["milestones"][0]["notes"] == ["alpha"]

    def test_append_milestone_note_requires_non_empty_note(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="append_milestone_note requires note"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [{"op": "append_milestone_note", "milestone_id": "M1", "note": "   "}],
                },
            )

    def test_replace_milestone_notes_filters_empty(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        result = apply_change_to_roadmap_obj(
            roadmap_obj={"milestones": [{"id": "M1", "notes": ["old"]}]},
            change_obj={
                "type": "modify",
                "target": {"milestone_id": "M1"},
                "patches": [
                    {
                        "op": "replace_milestone_notes",
                        "milestone_id": "M1",
                        "notes": ["kept", "", "  ", "also-kept"],
                    }
                ],
            },
        )
        assert result["milestones"][0]["notes"] == ["kept", "also-kept"]

    def test_replace_milestone_notes_requires_list(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="replace_milestone_notes requires notes"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [{"op": "replace_milestone_notes", "milestone_id": "M1", "notes": "not-a-list"}],
                },
            )

    def test_replace_milestone_steps_requires_non_empty(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="replace_milestone_steps requires steps"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [{"op": "replace_milestone_steps", "milestone_id": "M1", "steps": []}],
                },
            )

    def test_replace_milestone_steps_validates_type(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match=r"steps\[0\].type missing"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [
                        {
                            "op": "replace_milestone_steps",
                            "milestone_id": "M1",
                            "steps": [{"name": "no-type"}],
                        }
                    ],
                },
            )

    def test_replace_milestone_steps_rejects_non_dict(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match=r"steps\[1\] must be an object"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [
                        {
                            "op": "replace_milestone_steps",
                            "milestone_id": "M1",
                            "steps": [{"type": "t1"}, "not-a-dict"],
                        }
                    ],
                },
            )

    def test_replace_milestone_steps_replaces_and_dupes(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        original_step = {"type": "original", "data": "keep"}
        result = apply_change_to_roadmap_obj(
            roadmap_obj={"milestones": [{"id": "M1", "steps": [original_step]}]},
            change_obj={
                "type": "modify",
                "target": {"milestone_id": "M1"},
                "patches": [
                    {
                        "op": "replace_milestone_steps",
                        "milestone_id": "M1",
                        "steps": [{"type": "new1"}, {"type": "new2"}],
                    }
                ],
            },
        )
        assert [s["type"] for s in result["milestones"][0]["steps"]] == ["new1", "new2"]
        # Shallow copy guard: original caller dict untouched.
        assert original_step == {"type": "original", "data": "keep"}

    def test_replace_milestone_title_happy(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        result = apply_change_to_roadmap_obj(
            roadmap_obj={"milestones": [{"id": "M1", "title": "old"}]},
            change_obj={
                "type": "modify",
                "target": {"milestone_id": "M1"},
                "patches": [{"op": "replace_milestone_title", "milestone_id": "M1", "title": "new"}],
            },
        )
        assert result["milestones"][0]["title"] == "new"

    def test_replace_milestone_title_requires_non_empty(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="replace_milestone_title requires title"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [{"op": "replace_milestone_title", "milestone_id": "M1", "title": "  "}],
                },
            )

    def test_roadmap_without_milestones_list_raises_on_apply(self) -> None:
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        # Top-level `milestones` absent/non-list → empty collection →
        # milestone-not-found guard fires.
        with pytest.raises(ValueError, match="milestone not found"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": "not-a-list"},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [{"op": "append_milestone_note", "milestone_id": "M1", "note": "n"}],
                },
            )

    def test_non_dict_patch_entry_raises(self) -> None:
        """Codex iter-1 absorb: patch entry must be an object."""
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="patch entry must be an object"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": ["not-a-dict"],
                },
            )

    def test_missing_patch_milestone_id_raises(self) -> None:
        """Codex iter-1 absorb: patch.milestone_id must be a non-empty
        string. Empty / missing surfaces as CHANGE_INVALID."""
        from ao_kernel._internal.roadmap.change_proposals import (
            apply_change_to_roadmap_obj,
        )

        with pytest.raises(ValueError, match="patch.milestone_id missing"):
            apply_change_to_roadmap_obj(
                roadmap_obj={"milestones": [{"id": "M1"}]},
                change_obj={
                    "type": "modify",
                    "target": {"milestone_id": "M1"},
                    "patches": [{"op": "append_milestone_note", "note": "n"}],  # no milestone_id
                },
            )


# ---------------------------------------------------------------------------
# sanitize.py
# ---------------------------------------------------------------------------


class TestSanitizeScanDirectory:
    def test_missing_root_returns_ok_true_and_empty(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        ok, findings = scan_directory(root=tmp_path / "does-not-exist")
        assert ok is True
        assert findings == []

    def test_clean_directory_returns_no_findings(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        (tmp_path / "a.txt").write_text("nothing sensitive here", encoding="utf-8")
        ok, findings = scan_directory(root=tmp_path)
        assert ok is True
        assert findings == []

    def test_forbidden_token_triggers_rule(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        (tmp_path / "doc.txt").write_text("Hello Beykent customer", encoding="utf-8")
        ok, findings = scan_directory(root=tmp_path)
        assert ok is False
        rules = {f.rule for f in findings}
        assert "FORBIDDEN_TOKEN" in rules

    def test_custom_forbidden_token_overrides_default(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        (tmp_path / "doc.txt").write_text("Widget: ProductX", encoding="utf-8")
        # "Beykent" (default) is absent, "ProductX" custom is present.
        ok, findings = scan_directory(root=tmp_path, forbidden_tokens=["ProductX"])
        assert ok is False
        assert any(f.rule == "FORBIDDEN_TOKEN" for f in findings)

    def test_custom_forbidden_tokens_strip_empty(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        (tmp_path / "doc.txt").write_text("clean content", encoding="utf-8")
        # Empty + whitespace tokens filtered; no default fallback since
        # we passed a list.
        ok, findings = scan_directory(root=tmp_path, forbidden_tokens=["", "   "])
        assert ok is True
        assert findings == []

    def test_email_detected_triggers_rule(self, tmp_path: Path) -> None:
        """Real-world email addresses must trigger ``EMAIL_DETECTED``."""
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        (tmp_path / "mail.txt").write_text("contact: user@example.com", encoding="utf-8")
        ok, findings = scan_directory(root=tmp_path)
        assert ok is False
        rules = {f.rule for f in findings}
        assert "EMAIL_DETECTED" in rules

    def test_email_regex_does_not_match_backslash_escaped_pseudo_address(self, tmp_path: Path) -> None:
        """A literal backslash before the TLD is not a valid email match."""
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        (tmp_path / "plain.txt").write_text(r"contact: user@example\.com", encoding="utf-8")
        _, findings = scan_directory(root=tmp_path)
        rules = {f.rule for f in findings}
        assert "EMAIL_DETECTED" not in rules

    def test_private_key_marker_triggers_rule(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        (tmp_path / "id_rsa").write_text(
            "-----BEGIN OPENSSH PRIVATE KEY-----\nmock-body\n",
            encoding="utf-8",
        )
        ok, findings = scan_directory(root=tmp_path)
        assert ok is False
        assert any(f.rule == "PRIVATE_KEY_MARKER" for f in findings)

    def test_token_prefix_detection(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        # Token prefixes; value intentionally opaque per the rule.
        (tmp_path / "secrets.env").write_text(
            "OPENAI_KEY=sk-REDACTED\nGH_PAT=ghp_REDACTED\n",
            encoding="utf-8",
        )
        ok, findings = scan_directory(root=tmp_path)
        assert ok is False
        assert any(f.rule == "TOKEN_PREFIX_DETECTED" for f in findings)

    def test_multiple_rules_single_file_emit_multiple_findings(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        # FORBIDDEN_TOKEN + PRIVATE_KEY_MARKER + TOKEN_PREFIX_DETECTED all
        # in one file — each rule is independent (break inside a rule
        # group stops duplicates, not cross-rule emission).
        (tmp_path / "mix.txt").write_text(
            "Beykent banner\n-----BEGIN PRIVATE KEY-----\nghp_REDACTED",
            encoding="utf-8",
        )
        _, findings = scan_directory(root=tmp_path)
        rules = {f.rule for f in findings}
        assert "FORBIDDEN_TOKEN" in rules
        assert "PRIVATE_KEY_MARKER" in rules
        assert "TOKEN_PREFIX_DETECTED" in rules

    def test_findings_carry_relative_posix_paths(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.sanitize import scan_directory

        sub = tmp_path / "nested" / "dir"
        sub.mkdir(parents=True)
        (sub / "note.txt").write_text("Beykent", encoding="utf-8")
        _, findings = scan_directory(root=tmp_path)
        assert any(f.path == "nested/dir/note.txt" for f in findings)


class TestSanitizeFingerprint:
    def test_same_findings_same_fingerprint(self) -> None:
        from ao_kernel._internal.roadmap.sanitize import (
            SanitizeFinding,
            findings_fingerprint,
        )

        a = [
            SanitizeFinding(path="f1.txt", rule="FORBIDDEN_TOKEN"),
            SanitizeFinding(path="f2.txt", rule="EMAIL_DETECTED"),
        ]
        b = [
            SanitizeFinding(path="f1.txt", rule="FORBIDDEN_TOKEN"),
            SanitizeFinding(path="f2.txt", rule="EMAIL_DETECTED"),
        ]
        assert findings_fingerprint(a) == findings_fingerprint(b)

    def test_different_findings_different_fingerprint(self) -> None:
        from ao_kernel._internal.roadmap.sanitize import (
            SanitizeFinding,
            findings_fingerprint,
        )

        a = [SanitizeFinding(path="f1.txt", rule="FORBIDDEN_TOKEN")]
        b = [SanitizeFinding(path="f1.txt", rule="EMAIL_DETECTED")]
        assert findings_fingerprint(a) != findings_fingerprint(b)

    def test_fingerprint_is_16_char_sha256_prefix(self) -> None:
        from ao_kernel._internal.roadmap.sanitize import findings_fingerprint

        fp = findings_fingerprint([])
        assert len(fp) == 16
        # hex string — lowercase 0-9 / a-f
        assert all(c in "0123456789abcdef" for c in fp)


# ---------------------------------------------------------------------------
# evidence.py
# ---------------------------------------------------------------------------


class TestInitEvidenceDir:
    def test_creates_run_dir_and_steps_subdir(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.evidence import init_evidence_dir

        paths = init_evidence_dir(tmp_path / "evidence-root", "run-abc")
        assert paths.run_dir.is_dir()
        assert paths.steps_dir.is_dir()
        assert paths.steps_dir == paths.run_dir / "steps"

    def test_returns_expected_path_shape(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.evidence import init_evidence_dir

        paths = init_evidence_dir(tmp_path, "run-xyz")
        assert paths.roadmap_path.name == "roadmap.json"
        assert paths.plan_path.name == "plan.json"
        assert paths.summary_path.name == "summary.json"
        assert paths.dlq_path.name == "dlq.json"
        assert paths.run_dir.name == "run-xyz"

    def test_idempotent_when_called_twice(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.evidence import init_evidence_dir

        paths_first = init_evidence_dir(tmp_path, "run-a")
        paths_second = init_evidence_dir(tmp_path, "run-a")
        assert paths_first.run_dir == paths_second.run_dir


class TestWriteStepEvidence:
    def test_writes_input_output_logs_files(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.evidence import (
            init_evidence_dir,
            write_step_evidence,
        )

        paths = init_evidence_dir(tmp_path, "run-1")
        write_step_evidence(
            paths,
            "step-42",
            step_input={"k": "v-input"},
            step_output={"k": "v-output"},
            logs="line-1\nline-2\n",
        )
        step_dir = paths.steps_dir / "step-42"
        assert json.loads((step_dir / "input.json").read_text(encoding="utf-8")) == {"k": "v-input"}
        assert json.loads((step_dir / "output.json").read_text(encoding="utf-8")) == {"k": "v-output"}
        assert (step_dir / "logs.txt").read_text(encoding="utf-8") == "line-1\nline-2\n"


class TestWriteIntegrityManifest:
    def test_writes_manifest_with_sha256_entries_sorted(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.evidence import (
            MANIFEST_NAME,
            init_evidence_dir,
            write_integrity_manifest,
            write_step_evidence,
        )

        paths = init_evidence_dir(tmp_path, "run-42")
        write_step_evidence(
            paths,
            "s1",
            step_input={"a": 1},
            step_output={"a": 2},
            logs="hi",
        )
        write_integrity_manifest(paths.run_dir)

        manifest_path = paths.run_dir / MANIFEST_NAME
        assert manifest_path.is_file()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["version"] == "v1"
        assert manifest["run_id"] == "run-42"
        assert manifest["created_at"].endswith("Z")

        files = manifest["files"]
        assert all(entry["sha256"] and entry["path"] for entry in files)
        # Sorted ascending by path.
        assert [e["path"] for e in files] == sorted(e["path"] for e in files)
        # Manifest excludes itself.
        assert all(entry["path"] != MANIFEST_NAME for entry in files)

    def test_manifest_uses_relative_posix_paths(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.evidence import (
            MANIFEST_NAME,
            init_evidence_dir,
            write_integrity_manifest,
            write_step_evidence,
        )

        paths = init_evidence_dir(tmp_path, "run-p")
        write_step_evidence(paths, "nested", step_input={}, step_output={}, logs="")
        write_integrity_manifest(paths.run_dir)

        manifest = json.loads((paths.run_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
        # Slashes are POSIX, not backslashes (even on Windows).
        assert all("\\" not in e["path"] for e in manifest["files"])
        # Step evidence uses relative paths under steps/<step_id>/.
        assert any(e["path"].startswith("steps/nested/") for e in manifest["files"])

    def test_manifest_excludes_itself_on_recompute(self, tmp_path: Path) -> None:
        """Running write_integrity_manifest twice must not list the
        previous manifest — rebuild is idempotent."""
        from ao_kernel._internal.roadmap.evidence import (
            MANIFEST_NAME,
            init_evidence_dir,
            write_integrity_manifest,
            write_step_evidence,
        )

        paths = init_evidence_dir(tmp_path, "run-re")
        write_step_evidence(paths, "s1", step_input={}, step_output={}, logs="x")
        write_integrity_manifest(paths.run_dir)
        # Rebuild — first manifest already exists, must be skipped.
        write_integrity_manifest(paths.run_dir)

        manifest = json.loads((paths.run_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert all(entry["path"] != MANIFEST_NAME for entry in manifest["files"])
