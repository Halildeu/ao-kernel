"""Thin subprocess wrapper around ``gh issue`` and ``gh api`` for issues.

Only the surface ``project_sync`` needs is modelled. Tests substitute the
real client with a stub so the module under test never touches the network.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

from ao_kernel.project_sync.errors import (
    GhCliNotAvailableError,
    ProjectV2APIError,
)


@dataclass(frozen=True)
class IssueRecord:
    """A minimal view of a GitHub issue.

    Only the fields used by derivers and the label migrator are modelled;
    callers who need richer data can fetch raw JSON via :py:meth:`raw`.
    """

    number: int
    node_id: str
    title: str
    body: str
    labels: list[str] = field(default_factory=list)
    state: str = "open"
    raw: dict[str, Any] = field(default_factory=dict)


class IssueClient:
    """``gh`` CLI wrapper for issues."""

    def __init__(self, *, gh_binary: str | None = None, repo: str | None = None) -> None:
        self._gh_binary = gh_binary or shutil.which("gh") or "gh"
        self._repo = repo

    def _require_gh(self) -> None:
        if shutil.which(self._gh_binary) is None and not self._gh_binary.startswith("/"):
            raise GhCliNotAvailableError(
                f"gh CLI not found on PATH; set --gh-binary or install GitHub CLI ({self._gh_binary!r})"
            )

    def _run(self, args: list[str]) -> str:
        self._require_gh()
        cmd = [self._gh_binary, *args]
        if self._repo:
            cmd += ["--repo", self._repo]
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise ProjectV2APIError(
                f"gh command failed (exit={completed.returncode}): {' '.join(args)}",
                stderr=completed.stderr,
            )
        return completed.stdout

    def get_issue(self, number: int) -> IssueRecord:
        """Fetch a single issue with labels + body."""
        raw_out = self._run(
            [
                "issue",
                "view",
                str(number),
                "--json",
                "number,title,body,labels,state,id",
            ]
        )
        try:
            payload = json.loads(raw_out)
        except json.JSONDecodeError as exc:
            raise ProjectV2APIError(f"gh issue view returned non-JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ProjectV2APIError("gh issue view returned non-object payload")
        labels_field = payload.get("labels", [])
        labels: list[str] = []
        if isinstance(labels_field, list):
            for lbl in labels_field:
                if isinstance(lbl, dict) and isinstance(lbl.get("name"), str):
                    labels.append(lbl["name"])
                elif isinstance(lbl, str):
                    labels.append(lbl)
        return IssueRecord(
            number=int(payload.get("number", number)),
            node_id=str(payload.get("id", "")),
            title=str(payload.get("title", "")),
            body=str(payload.get("body", "")),
            labels=labels,
            state=str(payload.get("state", "open")),
            raw=payload,
        )

    def list_issues_with_label(self, label: str, *, limit: int = 100) -> list[IssueRecord]:
        """List issues carrying a given label (open + closed)."""
        raw_out = self._run(
            [
                "issue",
                "list",
                "--label",
                label,
                "--state",
                "all",
                "--limit",
                str(limit),
                "--json",
                "number,title,body,labels,state,id",
            ]
        )
        try:
            payload = json.loads(raw_out)
        except json.JSONDecodeError as exc:
            raise ProjectV2APIError(f"gh issue list returned non-JSON: {exc}") from exc
        if not isinstance(payload, list):
            return []
        out: list[IssueRecord] = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            labels_field = entry.get("labels", [])
            labels: list[str] = []
            if isinstance(labels_field, list):
                for lbl in labels_field:
                    if isinstance(lbl, dict) and isinstance(lbl.get("name"), str):
                        labels.append(lbl["name"])
                    elif isinstance(lbl, str):
                        labels.append(lbl)
            out.append(
                IssueRecord(
                    number=int(entry.get("number", 0)),
                    node_id=str(entry.get("id", "")),
                    title=str(entry.get("title", "")),
                    body=str(entry.get("body", "")),
                    labels=labels,
                    state=str(entry.get("state", "open")),
                    raw=entry,
                )
            )
        return out

    def add_labels(self, number: int, labels: list[str]) -> None:
        """Add labels to an issue (idempotent on GitHub's side)."""
        if not labels:
            return
        self._run(["issue", "edit", str(number), *sum((["--add-label", lbl] for lbl in labels), [])])

    def remove_label(self, number: int, label: str) -> None:
        """Remove a single label from an issue."""
        self._run(["issue", "edit", str(number), "--remove-label", label])

    def create_issue(
        self,
        *,
        title: str,
        body: str,
        labels: list[str],
        milestone: str | None = None,
    ) -> IssueRecord:
        """Open a fresh issue and return its record."""
        args = ["issue", "create", "--title", title, "--body", body]
        for lbl in labels:
            args += ["--label", lbl]
        if milestone:
            args += ["--milestone", milestone]
        raw_out = self._run(args)
        # ``gh issue create`` prints the URL of the new issue. Parse it for
        # the number; full record is then refreshed via ``get_issue`` so we
        # have the node_id GraphQL mutations need.
        url = raw_out.strip().splitlines()[-1].strip()
        number = self._parse_issue_number_from_url(url)
        return self.get_issue(number)

    @staticmethod
    def _parse_issue_number_from_url(url: str) -> int:
        """Extract the trailing issue number from a github.com URL."""
        if "/" not in url:
            raise ProjectV2APIError(f"unexpected gh issue create output: {url!r}")
        tail = url.rsplit("/", 1)[-1]
        try:
            return int(tail)
        except ValueError as exc:
            raise ProjectV2APIError(f"could not parse issue number from {url!r}") from exc
