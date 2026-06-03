"""Network-free tests for project_sync GitHub client wrappers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from ao_kernel.project_sync.errors import GhCliNotAvailableError, ProjectV2APIError
from ao_kernel.project_sync.issues import IssueClient
from ao_kernel.project_sync.project_v2 import (
    ProjectField,
    ProjectFieldId,
    ProjectItemId,
    ProjectOptionId,
    ProjectV2Client,
)


class StubProjectClient(ProjectV2Client):
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        super().__init__(gh_binary="/stub/gh")
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"query": query, "variables": variables})
        if not self.responses:
            raise AssertionError("no stub response queued")
        return self.responses.pop(0)


def test_project_v2_graphql_builds_typed_gh_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """_graphql uses -F for bool/int and -f for strings/json payloads."""

    captured: dict[str, Any] = {}

    def fake_which(binary: str) -> str:
        return "/usr/bin/gh"

    def fake_run(cmd: list[str], **kwargs: Any) -> SimpleNamespace:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr("ao_kernel.project_sync.project_v2.shutil.which", fake_which)
    monkeypatch.setattr("ao_kernel.project_sync.project_v2.subprocess.run", fake_run)

    result = ProjectV2Client(gh_binary="gh")._graphql(
        "query($flag: Boolean!) { viewer { login } }",
        {"flag": True, "count": 3, "name": "halil", "skip": None, "payload": {"a": 1}},
    )

    assert result == {"ok": True}
    cmd = captured["cmd"]
    assert "-F" in cmd
    assert "flag=true" in cmd
    assert "count=3" in cmd
    assert "name=halil" in cmd
    assert "skip=None" not in cmd
    assert 'payload={"a": 1}' in cmd
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["check"] is False


def test_project_v2_graphql_fails_when_gh_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ao_kernel.project_sync.project_v2.shutil.which", lambda _binary: None)
    with pytest.raises(GhCliNotAvailableError):
        ProjectV2Client(gh_binary="gh")._graphql("query { viewer { login } }", {})


def test_project_v2_graphql_surfaces_cli_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ao_kernel.project_sync.project_v2.shutil.which", lambda _binary: "/usr/bin/gh")
    monkeypatch.setattr(
        "ao_kernel.project_sync.project_v2.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=7, stdout="", stderr="rate limited"),
    )
    with pytest.raises(ProjectV2APIError) as exc_info:
        ProjectV2Client(gh_binary="gh")._graphql("query { viewer { login } }", {})
    assert exc_info.value.stderr == "rate limited"


def test_project_v2_fetch_fields_parses_single_select_options() -> None:
    client = StubProjectClient(
        [
            {
                "data": {
                    "node": {
                        "fields": {
                            "nodes": [
                                {
                                    "id": "F_risk",
                                    "name": "Risk",
                                    "dataType": "SINGLE_SELECT",
                                    "options": [{"id": "O_high", "name": "high"}],
                                },
                                {"id": "F_text", "name": "Evidence", "dataType": "TEXT"},
                                None,
                                {"name": "bad-no-id"},
                            ]
                        }
                    }
                }
            }
        ]
    )

    fields = client.fetch_fields("PVT_1")

    assert fields["Risk"].field_id == "F_risk"
    assert fields["Risk"].options == {"high": "O_high"}
    assert fields["Evidence"].data_type == "TEXT"
    assert "bad-no-id" not in fields


def test_project_v2_find_item_and_add_issue_paths() -> None:
    existing = StubProjectClient(
        [
            {"data": {"node": {"items": {"nodes": [{"id": "ITEM_1", "content": {"id": "ISSUE_1"}}]}}}},
        ]
    )
    assert existing.find_item_for_issue("PVT_1", "ISSUE_1") == "ITEM_1"

    creator = StubProjectClient(
        [
            {"data": {"node": {"items": {"nodes": []}}}},
            {"data": {"addProjectV2ItemById": {"item": {"id": "ITEM_2"}}}},
        ]
    )
    assert creator.add_issue_to_project("PVT_1", "ISSUE_2") == "ITEM_2"

    broken = StubProjectClient(
        [
            {"data": {"node": {"items": {"nodes": []}}}},
            {"data": {"addProjectV2ItemById": {"item": {}}}},
        ]
    )
    with pytest.raises(ProjectV2APIError):
        broken.add_issue_to_project("PVT_1", "ISSUE_3")


def test_project_v2_set_field_value_routes_supported_types() -> None:
    client = StubProjectClient([{}, {}, {}])
    item_id = ProjectItemId("ITEM_1")

    client.set_field_value(
        project_node_id="PVT_1",
        item_id=item_id,
        field=ProjectField(
            field_id=ProjectFieldId("F_risk"),
            name="Risk",
            data_type="SINGLE_SELECT",
            options={"high": ProjectOptionId("O_high")},
        ),
        value="high",
    )
    client.set_field_value(
        project_node_id="PVT_1",
        item_id=item_id,
        field=ProjectField(ProjectFieldId("F_text"), "Evidence", "TEXT", {}),
        value=123,
    )
    client.set_field_value(
        project_node_id="PVT_1",
        item_id=item_id,
        field=ProjectField(ProjectFieldId("F_number"), "Estimate", "NUMBER", {}),
        value="2.5",
    )

    variables = [call["variables"] for call in client.calls]
    assert variables[0]["optionId"] == "O_high"
    assert variables[1]["text"] == "123"
    assert variables[2]["number"] == 2.5


def test_project_v2_set_field_value_rejects_invalid_values() -> None:
    client = StubProjectClient([])
    item_id = ProjectItemId("ITEM_1")
    select_field = ProjectField(ProjectFieldId("F_risk"), "Risk", "SINGLE_SELECT", {"high": ProjectOptionId("O")})

    with pytest.raises(ProjectV2APIError, match="requires a string"):
        client.set_field_value(project_node_id="PVT", item_id=item_id, field=select_field, value=1)
    with pytest.raises(ProjectV2APIError, match="no option"):
        client.set_field_value(project_node_id="PVT", item_id=item_id, field=select_field, value="low")
    with pytest.raises(ProjectV2APIError, match="numeric"):
        client.set_field_value(
            project_node_id="PVT",
            item_id=item_id,
            field=ProjectField(ProjectFieldId("F_num"), "Estimate", "NUMBER", {}),
            value="not-a-number",
        )
    with pytest.raises(ProjectV2APIError, match="unsupported"):
        client.set_field_value(
            project_node_id="PVT",
            item_id=item_id,
            field=ProjectField(ProjectFieldId("F_date"), "Due", "DATE", {}),
            value="2026-06-03",
        )


def test_project_v2_fetch_field_values_parses_display_values() -> None:
    client = StubProjectClient(
        [
            {
                "data": {
                    "node": {
                        "items": {
                            "nodes": [
                                {"id": "OTHER", "fieldValues": {"nodes": []}},
                                {
                                    "id": "ITEM_1",
                                    "fieldValues": {
                                        "nodes": [
                                            {"name": "high", "field": {"name": "Risk"}},
                                            {"text": "doc", "field": {"name": "Evidence"}},
                                            {"number": 3, "field": {"name": "Estimate"}},
                                            {"name": "ignored", "field": {}},
                                            "bad",
                                        ]
                                    },
                                },
                            ]
                        }
                    }
                }
            }
        ]
    )

    assert client.fetch_field_values("PVT_1", ProjectItemId("ITEM_1")) == {
        "Risk": "high",
        "Evidence": "doc",
        "Estimate": "3",
    }


def test_issue_client_get_and_list_parse_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = [
        json.dumps(
            {
                "number": 42,
                "id": "ISSUE_42",
                "title": "t",
                "body": "b",
                "labels": [{"name": "risk:high"}, "mirror:authority"],
                "state": "OPEN",
            }
        ),
        json.dumps(
            [
                {
                    "number": 43,
                    "id": "ISSUE_43",
                    "title": "t2",
                    "body": "",
                    "labels": [{"name": "epic-1"}],
                    "state": "CLOSED",
                },
                "bad",
            ]
        ),
    ]
    calls: list[list[str]] = []

    def fake_run(self: IssueClient, args: list[str]) -> str:
        calls.append(args)
        return outputs.pop(0)

    monkeypatch.setattr(IssueClient, "_run", fake_run)
    client = IssueClient(repo="Halildeu/ao-kernel")

    issue = client.get_issue(42)
    listed = client.list_issues_with_label("mirror:authority")

    assert issue.labels == ["risk:high", "mirror:authority"]
    assert listed[0].number == 43
    assert listed[0].labels == ["epic-1"]
    assert calls[0][:3] == ["issue", "view", "42"]
    assert calls[1][:4] == ["issue", "list", "--label", "mirror:authority"]


def test_issue_client_mutation_helpers_and_create(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(self: IssueClient, args: list[str]) -> str:
        calls.append(args)
        if args[:2] == ["issue", "create"]:
            return "https://github.com/Halildeu/ao-kernel/issues/77\n"
        if args[:3] == ["issue", "view", "77"]:
            return json.dumps({"number": 77, "id": "ISSUE_77", "title": "created", "body": "", "labels": []})
        return ""

    monkeypatch.setattr(IssueClient, "_run", fake_run)
    client = IssueClient(repo="Halildeu/ao-kernel")

    client.add_labels(1, [])
    client.add_labels(1, ["risk:high", "epic-1"])
    client.remove_label(1, "risk:high")
    created = client.create_issue(title="created", body="body", labels=["epic-1"], milestone="v5")

    assert created.number == 77
    assert calls[0] == ["issue", "edit", "1", "--add-label", "risk:high", "--add-label", "epic-1"]
    assert calls[1] == ["issue", "edit", "1", "--remove-label", "risk:high"]
    assert calls[2][:4] == ["issue", "create", "--title", "created"]
    assert "--milestone" in calls[2]


def test_issue_client_rejects_bad_json_and_bad_create_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = IssueClient(repo="Halildeu/ao-kernel")
    monkeypatch.setattr(IssueClient, "_run", lambda self, args: "{not-json")

    with pytest.raises(ProjectV2APIError, match="non-JSON"):
        client.get_issue(1)
    with pytest.raises(ProjectV2APIError, match="non-JSON"):
        client.list_issues_with_label("x")

    assert IssueClient._parse_issue_number_from_url("https://github.com/o/r/issues/123") == 123
    with pytest.raises(ProjectV2APIError, match="unexpected"):
        IssueClient._parse_issue_number_from_url("not-a-url")
    with pytest.raises(ProjectV2APIError, match="could not parse"):
        IssueClient._parse_issue_number_from_url("https://github.com/o/r/issues/not-a-number")
