"""Portable PR delivery metadata validation helpers.

PR delivery metadata is an untrusted PR-author declaration. This module
validates the declaration for product portability and diagnostics, but it does
not make PR-author text release authority. The release authority remains the
repo-owned ao-release-gate decision plus GitHub enforcement.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping, cast

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default

PR_DELIVERY_METADATA_SCHEMA_NAME = "pr-delivery-metadata.schema.v1.json"
PR_DELIVERY_METADATA_SCHEMA_ID = "urn:ao:pr-delivery-metadata:v1"

_FENCE_RE = re.compile(
    r"```(?P<info>[^\n`]*)\n(?P<body>.*?)\n```",
    flags=re.DOTALL,
)

PrMetadataFinding = Literal[
    "pr_delivery_metadata_ok",
    "pr_delivery_metadata_absent",
    "pr_delivery_metadata_malformed_json",
    "pr_delivery_metadata_schema_invalid",
]


@dataclass(frozen=True)
class PrDeliveryMetadataValidation:
    """Sanitized PR delivery metadata validation result."""

    present: bool
    valid: bool
    finding_code: PrMetadataFinding
    message: str
    metadata: dict[str, Any] | None = None
    risk_class: str | None = None
    release_authority_impact: str | None = None
    work_package: str | None = None
    issue: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable sanitized result."""

        return {
            "schema_id": PR_DELIVERY_METADATA_SCHEMA_ID,
            "present": self.present,
            "valid": self.valid,
            "finding_code": self.finding_code,
            "message": self.message,
            "risk_class": self.risk_class,
            "release_authority_impact": self.release_authority_impact,
            "work_package": self.work_package,
            "issue": self.issue,
        }


def load_pr_delivery_metadata_schema() -> dict[str, Any]:
    """Load the bundled PR delivery metadata JSON Schema."""

    schema = load_default("schemas", PR_DELIVERY_METADATA_SCHEMA_NAME)
    Draft202012Validator.check_schema(schema)
    return cast(dict[str, Any], schema)


def extract_pr_delivery_metadata_block(markdown: str) -> str | None:
    """Extract the first fenced ``pr-delivery-metadata`` JSON block.

    Accepted info strings are intentionally narrow and explicit:

    - ``json pr-delivery-metadata``
    - ``pr-delivery-metadata json``
    - ``pr-delivery-metadata``

    A plain ``json`` fence is ignored so unrelated examples in the PR body
    cannot be treated as the delivery declaration by accident.
    """

    for match in _FENCE_RE.finditer(markdown):
        info = " ".join(match.group("info").strip().lower().split())
        tokens = set(info.split())
        if info == "pr-delivery-metadata" or {"json", "pr-delivery-metadata"}.issubset(tokens):
            return match.group("body").strip()
    return None


def validate_pr_delivery_metadata_object(metadata: object) -> PrDeliveryMetadataValidation:
    """Validate an already-parsed metadata object."""

    if not isinstance(metadata, dict):
        return PrDeliveryMetadataValidation(
            present=True,
            valid=False,
            finding_code="pr_delivery_metadata_schema_invalid",
            message="PR delivery metadata must be a JSON object.",
        )

    schema = load_pr_delivery_metadata_schema()
    errors = sorted(
        Draft202012Validator(schema).iter_errors(metadata),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(item) for item in first.absolute_path) or "<root>"
        return PrDeliveryMetadataValidation(
            present=True,
            valid=False,
            finding_code="pr_delivery_metadata_schema_invalid",
            message=(
                "PR delivery metadata schema validation failed "
                f"at {path} (validator={first.validator})."
            ),
        )

    return PrDeliveryMetadataValidation(
        present=True,
        valid=True,
        finding_code="pr_delivery_metadata_ok",
        message="PR delivery metadata validates against pr-delivery-metadata.schema.v1.json.",
        metadata=cast(dict[str, Any], metadata),
        risk_class=cast(str | None, metadata.get("risk_class")),
        release_authority_impact=cast(str | None, metadata.get("release_authority_impact")),
        work_package=cast(str | None, metadata.get("work_package")),
        issue=cast(str | None, metadata.get("issue")),
    )


def validate_pr_delivery_metadata_markdown(markdown: str) -> PrDeliveryMetadataValidation:
    """Extract and validate PR delivery metadata from a PR body."""

    block = extract_pr_delivery_metadata_block(markdown)
    if block is None:
        return PrDeliveryMetadataValidation(
            present=False,
            valid=False,
            finding_code="pr_delivery_metadata_absent",
            message="No fenced pr-delivery-metadata JSON block found in the PR body.",
        )
    try:
        parsed = json.loads(block)
    except json.JSONDecodeError:
        return PrDeliveryMetadataValidation(
            present=True,
            valid=False,
            finding_code="pr_delivery_metadata_malformed_json",
            message="PR delivery metadata block is not valid JSON.",
        )
    return validate_pr_delivery_metadata_object(parsed)


def pr_delivery_metadata_template_json() -> str:
    """Return the canonical JSON block used by the GitHub PR template."""

    return json.dumps(pr_delivery_metadata_template_object(), indent=2, sort_keys=True)


def pr_delivery_metadata_template_object(
    *,
    issue: str = "N/A",
    tracked_by: str = "N/A",
    work_package: str = "AO-MA-or-GPP-id",
    risk_class: str = "normal",
    release_authority_impact: str = "none",
    critical_fix: bool = False,
    implementer_provider: str = "openai",
    reviewer_providers: list[str] | None = None,
    review_artifacts: list[str] | None = None,
    verdict: str = "N/A",
    same_provider_exception: str = "N/A",
    boundary_credential_read: bool = False,
    boundary_credential_write: bool = False,
    boundary_state_mutation_test: bool = False,
    boundary_state_mutation_production: bool = False,
    boundary_cross: bool = False,
    boundary_user_communication: bool = False,
    user_approval_evidence: str = "N/A",
) -> dict[str, Any]:
    """Return a schema-shaped PR delivery metadata object.

    The helper centralizes the product UX defaults used by the template and
    generate/fix CLI commands. It deliberately does not read PR state or make
    release-authority decisions; it only creates the PR-author declaration
    block that the repo-owned gate can validate.
    """

    none_of_the_above = not any(
        (
            boundary_credential_read,
            boundary_credential_write,
            boundary_state_mutation_test,
            boundary_state_mutation_production,
            boundary_cross,
            boundary_user_communication,
        )
    )
    payload: dict[str, Any] = {
        "issue": "N/A",
        "tracked_by": "N/A",
        "work_package": "AO-MA-or-GPP-id",
        "risk_class": "normal",
        "release_authority_impact": "none",
        "critical_fix": False,
        "boundary_declaration": {
            "credential_read": boundary_credential_read,
            "credential_write": boundary_credential_write,
            "state_mutation_test": boundary_state_mutation_test,
            "state_mutation_production": boundary_state_mutation_production,
            "boundary_cross": boundary_cross,
            "user_communication": boundary_user_communication,
            "none_of_the_above": none_of_the_above,
            "user_approval_evidence": user_approval_evidence,
        },
        "cross_ai_review": {
            "implementer_provider": "openai",
            "reviewer_providers": ["anthropic"],
            "review_artifacts": ["N/A"],
            "verdict": "N/A",
            "same_provider_exception": "N/A",
        },
    }
    payload["issue"] = issue
    payload["tracked_by"] = tracked_by
    payload["work_package"] = work_package
    payload["risk_class"] = risk_class
    payload["release_authority_impact"] = release_authority_impact
    payload["critical_fix"] = critical_fix
    payload["cross_ai_review"]["implementer_provider"] = implementer_provider
    payload["cross_ai_review"]["reviewer_providers"] = (
        list(reviewer_providers) if reviewer_providers is not None else ["anthropic"]
    )
    payload["cross_ai_review"]["review_artifacts"] = (
        list(review_artifacts) if review_artifacts is not None else ["N/A"]
    )
    payload["cross_ai_review"]["verdict"] = verdict
    payload["cross_ai_review"]["same_provider_exception"] = same_provider_exception
    return payload


def render_pr_delivery_metadata_block(metadata: Mapping[str, Any]) -> str:
    """Render a fenced ``pr-delivery-metadata`` JSON block."""

    body = json.dumps(dict(metadata), indent=2, sort_keys=True)
    return f"```json pr-delivery-metadata\n{body}\n```"


def upsert_pr_delivery_metadata_block(markdown: str, metadata: Mapping[str, Any]) -> str:
    """Append or replace the first explicit PR delivery metadata block.

    Replacement is intentionally limited to the explicit info strings that
    :func:`extract_pr_delivery_metadata_block` accepts. Plain JSON examples in
    PR bodies are left untouched.
    """

    block = render_pr_delivery_metadata_block(metadata)
    for match in _FENCE_RE.finditer(markdown):
        info = " ".join(match.group("info").strip().lower().split())
        tokens = set(info.split())
        if info == "pr-delivery-metadata" or {"json", "pr-delivery-metadata"}.issubset(tokens):
            return markdown[: match.start()] + block + markdown[match.end() :]
    trimmed = markdown.rstrip()
    if not trimmed:
        return block + "\n"
    return trimmed + "\n\n## Delivery Metadata\n\n" + block + "\n"
