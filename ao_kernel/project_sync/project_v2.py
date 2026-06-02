"""Thin subprocess wrapper around ``gh api graphql`` for Projects v2.

This module owns the only place that shells out to ``gh``. Tests substitute
:class:`ProjectV2Client` with a stub. The wire format is GitHub GraphQL —
we keep it minimal and only model the surface the module actually needs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, NewType

from ao_kernel.project_sync.errors import (
    GhCliNotAvailableError,
    ProjectV2APIError,
)

# Type-safe aliases — the GraphQL surface returns opaque strings for these.
ProjectFieldId = NewType("ProjectFieldId", str)
ProjectItemId = NewType("ProjectItemId", str)
ProjectOptionId = NewType("ProjectOptionId", str)


@dataclass(frozen=True)
class ProjectField:
    """A single Projects v2 custom field plus its option map."""

    field_id: ProjectFieldId
    name: str
    data_type: str
    options: dict[str, ProjectOptionId]


class ProjectV2Client:
    """Subprocess wrapper around ``gh api graphql``.

    Constructed with a ``gh`` binary path (defaults to PATH lookup). All
    queries go through :py:meth:`_graphql` so tests can swap the binary out
    via a stub subclass.
    """

    def __init__(self, *, gh_binary: str | None = None) -> None:
        self._gh_binary = gh_binary or shutil.which("gh") or "gh"

    def _require_gh(self) -> None:
        if shutil.which(self._gh_binary) is None and not self._gh_binary.startswith("/"):
            raise GhCliNotAvailableError(
                f"gh CLI not found on PATH; set --gh-binary or install GitHub CLI ({self._gh_binary!r})"
            )

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Run a single GraphQL query.

        Variables are passed through ``-F`` flags so payloads stay typed
        (gh casts integers, strings, booleans differently per flag prefix).
        """
        self._require_gh()
        cmd: list[str] = [self._gh_binary, "api", "graphql", "-f", f"query={query}"]
        for key, value in variables.items():
            if isinstance(value, bool):
                cmd += ["-F", f"{key}={'true' if value else 'false'}"]
            elif isinstance(value, int):
                cmd += ["-F", f"{key}={value}"]
            elif isinstance(value, str):
                cmd += ["-f", f"{key}={value}"]
            elif value is None:
                continue
            else:
                cmd += ["-f", f"{key}={json.dumps(value)}"]
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise ProjectV2APIError(
                f"gh graphql call failed (exit={completed.returncode})",
                stderr=completed.stderr,
            )
        try:
            payload = json.loads(completed.stdout) if completed.stdout else {}
        except json.JSONDecodeError as exc:
            raise ProjectV2APIError(
                f"gh graphql returned non-JSON: {exc}",
                stderr=completed.stderr,
            ) from exc
        if isinstance(payload, dict) and payload.get("errors"):
            raise ProjectV2APIError(
                f"gh graphql errors: {payload['errors']}",
                stderr=completed.stderr,
            )
        return payload if isinstance(payload, dict) else {}

    def fetch_fields(self, project_node_id: str) -> dict[str, ProjectField]:
        """Return a name → ProjectField map for the project board.

        The field IDs come back as opaque strings — we route every later
        mutation through the cached map so the field name string we typed
        in the CLI is the only mutable handle in user-land.
        """
        query = (
            "query($projectId: ID!) {"
            "  node(id: $projectId) {"
            "    ... on ProjectV2 {"
            "      fields(first: 50) {"
            "        nodes {"
            "          ... on ProjectV2Field { id name dataType }"
            "          ... on ProjectV2SingleSelectField {"
            "            id name dataType options { id name }"
            "          }"
            "          ... on ProjectV2IterationField {"
            "            id name dataType"
            "          }"
            "        }"
            "      }"
            "    }"
            "  }"
            "}"
        )
        data = self._graphql(query, {"projectId": project_node_id})
        nodes_raw = data.get("data", {}).get("node", {}).get("fields", {}).get("nodes", [])
        if not isinstance(nodes_raw, list):
            return {}
        result: dict[str, ProjectField] = {}
        for node in nodes_raw:
            if not isinstance(node, dict):
                continue
            name = node.get("name")
            field_id = node.get("id")
            data_type = node.get("dataType", "")
            if not (isinstance(name, str) and isinstance(field_id, str)):
                continue
            options_map: dict[str, ProjectOptionId] = {}
            raw_options = node.get("options")
            if isinstance(raw_options, list):
                for opt in raw_options:
                    if not isinstance(opt, dict):
                        continue
                    opt_name = opt.get("name")
                    opt_id = opt.get("id")
                    if isinstance(opt_name, str) and isinstance(opt_id, str):
                        options_map[opt_name] = ProjectOptionId(opt_id)
            result[name] = ProjectField(
                field_id=ProjectFieldId(field_id),
                name=name,
                data_type=str(data_type),
                options=options_map,
            )
        return result

    def find_item_for_issue(self, project_node_id: str, issue_node_id: str) -> ProjectItemId | None:
        """Locate the existing board item for a given issue, if any.

        Returns ``None`` when the issue is not yet on the board.
        """
        query = (
            "query($projectId: ID!, $issueId: ID!) {"
            "  node(id: $projectId) {"
            "    ... on ProjectV2 {"
            "      items(first: 100) {"
            "        nodes {"
            "          id content { ... on Issue { id } }"
            "        }"
            "      }"
            "    }"
            "  }"
            "}"
        )
        data = self._graphql(query, {"projectId": project_node_id, "issueId": issue_node_id})
        nodes_raw = data.get("data", {}).get("node", {}).get("items", {}).get("nodes", [])
        if not isinstance(nodes_raw, list):
            return None
        for node in nodes_raw:
            if not isinstance(node, dict):
                continue
            content = node.get("content")
            if isinstance(content, dict) and content.get("id") == issue_node_id:
                item_id = node.get("id")
                if isinstance(item_id, str):
                    return ProjectItemId(item_id)
        return None

    def add_issue_to_project(self, project_node_id: str, issue_node_id: str) -> ProjectItemId:
        """Add an issue as a project board item; idempotent via fetch first."""
        existing = self.find_item_for_issue(project_node_id, issue_node_id)
        if existing is not None:
            return existing
        mutation = (
            "mutation($projectId: ID!, $contentId: ID!) {"
            "  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {"
            "    item { id }"
            "  }"
            "}"
        )
        data = self._graphql(mutation, {"projectId": project_node_id, "contentId": issue_node_id})
        item = data.get("data", {}).get("addProjectV2ItemById", {}).get("item", {})
        item_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(item_id, str):
            raise ProjectV2APIError("addProjectV2ItemById returned no item id")
        return ProjectItemId(item_id)

    def set_field_value(
        self,
        *,
        project_node_id: str,
        item_id: ProjectItemId,
        field: ProjectField,
        value: str | int | float,
    ) -> None:
        """Set a single project field on an item.

        Routes by ``data_type`` so callers do not need to remember which
        ``ProjectV2FieldValue`` variant corresponds to which field kind.
        """
        data_type = field.data_type.upper()
        if data_type == "SINGLE_SELECT":
            if not isinstance(value, str):
                raise ProjectV2APIError(
                    f"field {field.name!r} requires a string option name (got {type(value).__name__})"
                )
            option_id = field.options.get(value)
            if option_id is None:
                raise ProjectV2APIError(
                    f"field {field.name!r} has no option named {value!r} (have {sorted(field.options)})"
                )
            value_clause = "{ singleSelectOptionId: $optionId }"
            variables: dict[str, Any] = {
                "projectId": project_node_id,
                "itemId": item_id,
                "fieldId": field.field_id,
                "optionId": option_id,
            }
        elif data_type == "TEXT":
            value_clause = "{ text: $text }"
            variables = {
                "projectId": project_node_id,
                "itemId": item_id,
                "fieldId": field.field_id,
                "text": str(value),
            }
        elif data_type == "NUMBER":
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ProjectV2APIError(f"field {field.name!r} requires numeric value: {value!r}") from exc
            value_clause = "{ number: $number }"
            variables = {
                "projectId": project_node_id,
                "itemId": item_id,
                "fieldId": field.field_id,
                "number": number,
            }
        else:
            raise ProjectV2APIError(f"unsupported field data type for {field.name!r}: {field.data_type}")
        mutation_template = (
            "mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, %s) {"
            "  updateProjectV2ItemFieldValue(input: {"
            "    projectId: $projectId, itemId: $itemId, fieldId: $fieldId,"
            "    value: %s"
            "  }) { projectV2Item { id } }"
            "}"
        )
        if data_type == "SINGLE_SELECT":
            extra_decl = "$optionId: String!"
        elif data_type == "TEXT":
            extra_decl = "$text: String!"
        else:
            extra_decl = "$number: Float!"
        mutation = mutation_template % (extra_decl, value_clause)
        self._graphql(mutation, variables)

    def fetch_field_values(
        self,
        project_node_id: str,
        item_id: ProjectItemId,
    ) -> dict[str, str]:
        """Return current field name → display value map for an item.

        Used by the drift healer to compare expected vs actual without
        re-fetching every field individually.
        """
        query = (
            "query($projectId: ID!, $itemId: ID!) {"
            "  node(id: $projectId) {"
            "    ... on ProjectV2 {"
            "      items(first: 100) {"
            "        nodes {"
            "          id"
            "          fieldValues(first: 50) {"
            "            nodes {"
            "              ... on ProjectV2ItemFieldSingleSelectValue {"
            "                name field { ... on ProjectV2FieldCommon { name } }"
            "              }"
            "              ... on ProjectV2ItemFieldTextValue {"
            "                text field { ... on ProjectV2FieldCommon { name } }"
            "              }"
            "              ... on ProjectV2ItemFieldNumberValue {"
            "                number field { ... on ProjectV2FieldCommon { name } }"
            "              }"
            "            }"
            "          }"
            "        }"
            "      }"
            "    }"
            "  }"
            "}"
        )
        data = self._graphql(query, {"projectId": project_node_id, "itemId": item_id})
        items_raw = data.get("data", {}).get("node", {}).get("items", {}).get("nodes", [])
        if not isinstance(items_raw, list):
            return {}
        result: dict[str, str] = {}
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            if item.get("id") != item_id:
                continue
            values = item.get("fieldValues", {}).get("nodes", []) if isinstance(item.get("fieldValues"), dict) else []
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, dict):
                    continue
                field_meta = value.get("field")
                if not isinstance(field_meta, dict):
                    continue
                field_name = field_meta.get("name")
                if not isinstance(field_name, str):
                    continue
                if "name" in value and isinstance(value["name"], str):
                    result[field_name] = value["name"]
                elif "text" in value and isinstance(value["text"], str):
                    result[field_name] = value["text"]
                elif "number" in value and isinstance(value["number"], (int, float)):
                    result[field_name] = str(value["number"])
        return result
