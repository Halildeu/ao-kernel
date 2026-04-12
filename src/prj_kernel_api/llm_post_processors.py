"""LLM post-processing — evidence writing, output save, payload construction.

Extracted from adapter_llm_actions_runtime.py (PR0 seam extraction).
Single responsibility: after response normalization, write evidence files
and build the final response payload dict.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from src.shared.utils import write_text_atomic

from src.prj_kernel_api.llm_transport import sha256_hex


def _sanitize_name(text: str) -> str:
    """Sanitize a string for use in file paths."""
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", text).strip("_.")[:120] or "item"


def save_output_text(
    output_text: str,
    *,
    workspace_root: str,
    request_id: str,
    provider_id: str,
) -> str | None:
    """Save LLM output text to evidence file.

    Returns full path on success, None on failure.
    """
    if not output_text:
        return None
    try:
        ws_root = Path(workspace_root).resolve()
        out_dir = ws_root / ".cache" / "reports" / "llm_live_outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_request = _sanitize_name(str(request_id or "request"))
        safe_provider = _sanitize_name(str(provider_id or "provider"))
        out_path = out_dir / f"{safe_request}_{safe_provider}.txt"
        write_text_atomic(out_path, output_text)
        return str(out_path)
    except Exception:
        return None


def truncate_output(
    output_text: str,
    *,
    max_chars: int,
) -> tuple[str, bool]:
    """Truncate output for payload preview.

    Returns (preview_text, is_truncated).
    """
    if max_chars > 0:
        if len(output_text) > max_chars:
            return output_text[:max_chars], True
        return output_text, False
    if output_text:
        return "", True
    return "", False


def build_live_response_payload(
    *,
    provider_id: str,
    model: str,
    timeout_seconds: float,
    tls_cafile: str | None,
    http_status: int | None,
    elapsed_ms: int,
    error_type: str | None,
    error_detail: str | None,
    output_sha256: str,
    output_preview: str,
    output_truncated: bool,
    output_full_path: str | None,
) -> Dict[str, Any]:
    """Build the final payload dict for a live LLM call response."""
    return {
        "provider_id": provider_id,
        "model": model,
        "dry_run": False,
        "api_key_present": True,
        "timeout_seconds": timeout_seconds,
        "tls_cafile": tls_cafile,
        "http_status": http_status,
        "elapsed_ms": elapsed_ms,
        "error_type": error_type,
        "error_detail": error_detail,
        "output_sha256": output_sha256,
        "output_preview": output_preview,
        "output_truncated": output_truncated,
        "output_full_path": output_full_path,
        "nondeterministic": True,
    }


def process_live_response(
    *,
    resp_bytes: bytes,
    transport_result: Dict[str, Any],
    provider_id: str,
    model: str,
    workspace_root: str,
    request_id: str,
    max_output_chars: int,
) -> Dict[str, Any]:
    """Full post-processing pipeline for a live call response.

    Takes raw transport result and produces the final payload + writes evidence.
    Returns the payload dict ready for build_response().
    """
    from src.prj_kernel_api.llm_response_normalizer import extract_llm_output_text

    output_text = extract_llm_output_text(resp_bytes) if resp_bytes else ""
    output_sha = sha256_hex(resp_bytes) if resp_bytes else sha256_hex(b"")

    output_full_path = save_output_text(
        output_text,
        workspace_root=workspace_root,
        request_id=request_id,
        provider_id=provider_id,
    )

    output_preview, output_truncated = truncate_output(
        output_text,
        max_chars=max_output_chars,
    )

    return build_live_response_payload(
        provider_id=provider_id,
        model=model,
        timeout_seconds=transport_result["elapsed_ms"] / 1000.0,
        tls_cafile=transport_result.get("tls_cafile"),
        http_status=transport_result.get("http_status"),
        elapsed_ms=transport_result["elapsed_ms"],
        error_type=transport_result.get("error_type"),
        error_detail=transport_result.get("error_detail"),
        output_sha256=output_sha,
        output_preview=output_preview,
        output_truncated=output_truncated,
        output_full_path=output_full_path,
    )
