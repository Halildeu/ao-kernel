"""Tests for Decision Extractor — JSON + heuristic extraction."""

from __future__ import annotations

import json

from ao_kernel.context.decision_extractor import Decision, extract_decisions


class TestJsonExtraction:
    def test_extract_from_json_object(self):
        output = json.dumps({"status": "approved", "version": "3.11", "count": 42})
        decisions = extract_decisions(output, request_id="req-001")
        assert len(decisions) >= 2
        keys = {d.key for d in decisions}
        assert "llm.status" in keys
        assert "llm.version" in keys
        assert all(d.confidence >= 0.8 for d in decisions)
        assert all(d.evidence_id == "req-001" for d in decisions)

    def test_extract_nested_json(self):
        output = json.dumps({"config": {"python": "3.11", "strict": True}})
        decisions = extract_decisions(output)
        keys = {d.key for d in decisions}
        assert "llm.config.python" in keys
        assert "llm.config.strict" in keys

    def test_skip_internal_keys(self):
        output = json.dumps({"_internal": "x", "type": "response", "id": "123", "result": "ok"})
        decisions = extract_decisions(output)
        keys = {d.key for d in decisions}
        assert "_internal" not in str(keys)
        assert "llm.result" in keys

    def test_json_embedded_in_text(self):
        output = 'Here is the result:\n{"answer": "yes", "confidence": 0.95}\nDone.'
        decisions = extract_decisions(output)
        assert len(decisions) >= 1
        assert any(d.key == "llm.answer" for d in decisions)

    def test_empty_output_returns_empty(self):
        assert extract_decisions("") == []
        assert extract_decisions("   ") == []

    def test_non_json_text_falls_to_heuristic(self):
        output = "The Python version is 3.11. We decided to use strict mode."
        decisions = extract_decisions(output)
        # Heuristic may or may not extract — but should not crash
        assert isinstance(decisions, list)

    def test_max_cap_20_decisions(self):
        obj = {f"key_{i}": f"value_{i}" for i in range(30)}
        decisions = extract_decisions(json.dumps(obj))
        assert len(decisions) <= 20


class TestHeuristicExtraction:
    def test_key_value_pattern(self):
        output = "Status: approved\nVersion: 3.11\nMode: production"
        decisions = extract_decisions(output)
        assert len(decisions) >= 2
        assert all(d.confidence <= 0.5 for d in decisions)

    def test_decision_pattern(self):
        output = "We decided to deploy the application to staging environment."
        decisions = extract_decisions(output)
        assert any("decision" in d.key for d in decisions)

    def test_heuristic_cap_10(self):
        lines = [f"Field_{i}: value_{i}" for i in range(20)]
        decisions = extract_decisions("\n".join(lines))
        assert len(decisions) <= 10


class TestDecisionDataclass:
    def test_to_dict(self):
        d = Decision(key="test.key", value="test_value", source="agent", confidence=0.9, evidence_id="req-1")
        as_dict = d.to_dict()
        assert as_dict["key"] == "test.key"
        assert as_dict["value"] == "test_value"
        assert as_dict["confidence"] == 0.9
        assert "extracted_at" in as_dict

    def test_frozen(self):
        d = Decision(key="k", value="v")
        import pytest
        with pytest.raises(AttributeError):
            d.key = "new_key"
