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
from typing import Any, Literal, cast

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
    return schema


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

    payload = {
        "issue": "N/A",
        "tracked_by": "N/A",
        "work_package": "AO-MA-or-GPP-id",
        "risk_class": "normal",
        "release_authority_impact": "none",
        "critical_fix": False,
        "boundary_declaration": {
            "credential_read": False,
            "credential_write": False,
            "state_mutation_test": False,
            "state_mutation_production": False,
            "boundary_cross": False,
            "user_communication": False,
            "none_of_the_above": True,
            "user_approval_evidence": "N/A",
        },
        "cross_ai_review": {
            "implementer_provider": "openai",
            "reviewer_providers": ["anthropic"],
            "review_artifacts": ["N/A"],
            "verdict": "N/A",
            "same_provider_exception": "N/A",
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)
