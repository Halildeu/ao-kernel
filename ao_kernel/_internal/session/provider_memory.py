from __future__ import annotations
from ao_kernel._internal.shared.utils import write_text_atomic

import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from ao_kernel._internal.prj_kernel_api.codex_home import resolve_effective_codex_config
from ao_kernel._internal.session.context_store import (
    SessionContextError,
    SessionPaths,
    load_context,
    mark_compaction,
    save_context_atomic,
    upsert_provider_state,
)
from ao_kernel._internal.utils.budget import estimate_tokens


def _safe_slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    normalized = normalized.strip("-._")
    return normalized or "default"


def resolve_auto_compact_token_limit(*, workspace_root: Path) -> int:
    try:
        resolved = resolve_effective_codex_config(workspace_root)
    except Exception:
        return 0

    effective = resolved.get("effective_config") if isinstance(resolved, dict) else None
    if not isinstance(effective, dict):
        return 0
    try:
        return max(0, int(effective.get("model_auto_compact_token_limit") or 0))
    except Exception:
        return 0


def read_provider_session_state(
    *,
    workspace_root: Path,
    session_id: str = "default",
    provider: str,
    wire_api: str,
) -> dict[str, Any]:
    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    path = sp.context_path
    payload: dict[str, Any] = {
        "session_id": session_id,
        "context_path": str(path),
        "exists": False,
        "memory_strategy": "local_only",
        "provider_state": {},
        "continuation": {},
    }
    if not path.exists():
        return payload

    try:
        ctx = load_context(path)
    except SessionContextError as exc:
        payload["error_code"] = exc.error_code
        return payload

    payload["exists"] = True
    memory_strategy = str(ctx.get("memory_strategy") or "local_only")
    payload["memory_strategy"] = memory_strategy

    provider_state = ctx.get("provider_state") if isinstance(ctx.get("provider_state"), dict) else {}
    payload["provider_state"] = provider_state

    continuation: dict[str, Any] = {}
    provider_norm = str(provider or "").strip()
    wire_api_norm = str(wire_api or "").strip()
    provider_state_provider = str(provider_state.get("provider") or "").strip()
    provider_state_wire = str(provider_state.get("wire_api") or "").strip()
    if (
        memory_strategy in {"provider_state", "hybrid"}
        and provider_norm
        and wire_api_norm
        and provider_state_provider == provider_norm
        and provider_state_wire == wire_api_norm
    ):
        previous_response_id = str(provider_state.get("last_response_id") or "").strip()
        conversation_id = str(provider_state.get("conversation_id") or "").strip()
        if previous_response_id:
            continuation["previous_response_id"] = previous_response_id
        if conversation_id:
            continuation["conversation_id"] = conversation_id
    payload["continuation"] = continuation

    # Include compaction summary ref if available (for context reuse)
    compaction = ctx.get("compaction") if isinstance(ctx.get("compaction"), dict) else {}
    if compaction.get("status") == "completed" and compaction.get("summary_ref"):
        payload["compaction_summary_ref"] = str(compaction["summary_ref"])

    return payload


def _render_compaction_summary(*, markdown: str, session_id: str, approx_input_tokens: int) -> str:
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    digest = sha256(normalized.encode("utf-8")).hexdigest()
    lines = [line.rstrip() for line in normalized.split("\n")]
    headings = [line.lstrip("#").strip() for line in lines if line.startswith("#") and line.lstrip("#").strip()]
    bullets = [line.lstrip("-* ").strip() for line in lines if line.startswith(("-", "*")) and line.lstrip("-* ").strip()]
    paragraphs = [
        line.strip()
        for line in lines
        if line.strip() and not line.startswith("#") and not line.startswith(("-", "*"))
    ]

    out: list[str] = [
        "# Session Compaction Summary",
        "",
        f"- session_id: {session_id}",
        f"- approx_input_tokens: {approx_input_tokens}",
        f"- original_chars: {len(normalized)}",
        f"- original_lines: {len(lines)}",
        f"- original_sha256: {digest}",
        "",
    ]

    if headings:
        out.append("## Headings")
        for item in headings[:10]:
            out.append(f"- {item}")
        out.append("")

    if bullets:
        out.append("## Key Bullets")
        for item in bullets[:12]:
            out.append(f"- {item}")
        out.append("")

    if paragraphs:
        excerpt = " ".join(paragraphs[:6]).strip()
        if len(excerpt) > 2400:
            excerpt = excerpt[:2397] + "..."
        out.append("## Narrative Excerpt")
        out.append(excerpt)
        out.append("")

    summary = "\n".join(out).strip() + "\n"
    if len(summary) >= len(normalized):
        clipped = normalized[: min(len(normalized), 2200)].strip()
        if len(clipped) < len(normalized):
            clipped += "\n..."
        summary = "\n".join(
            [
                "# Session Compaction Summary",
                "",
                f"- session_id: {session_id}",
                f"- approx_input_tokens: {approx_input_tokens}",
                f"- original_sha256: {digest}",
                "",
                "## Excerpt",
                clipped,
                "",
            ]
        )
    return summary


def maybe_auto_compact_markdown(
    *,
    workspace_root: Path,
    session_id: str,
    markdown: str,
    provider: str,
    wire_api: str,
    threshold_tokens: int,
) -> dict[str, Any]:
    approx_input_tokens = max(0, int(estimate_tokens(markdown)))
    payload: dict[str, Any] = {
        "applied": False,
        "input_markdown": markdown,
        "approx_input_tokens": approx_input_tokens,
        "threshold_tokens": max(0, int(threshold_tokens)),
        "summary_ref": "",
    }

    if threshold_tokens < 1 or approx_input_tokens < threshold_tokens:
        return payload

    summary_text = _render_compaction_summary(
        markdown=markdown,
        session_id=session_id,
        approx_input_tokens=approx_input_tokens,
    )
    reports_dir = (workspace_root / ".cache" / "reports").resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Archive original content before compaction for audit/recovery
    archive_path = reports_dir / f"session_compaction_{_safe_slug(session_id)}.original.v1.md"
    try:
        write_text_atomic(archive_path, markdown)
    except Exception as exc:
        import logging
        logging.getLogger("ao_kernel").warning("session archive write failed (best-effort): %s", exc)

    summary_path = reports_dir / f"session_compaction_{_safe_slug(session_id)}.v1.md"
    write_text_atomic(summary_path, summary_text)

    try:
        summary_ref = summary_path.relative_to(workspace_root).as_posix()
    except Exception:
        summary_ref = str(summary_path)

    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    if sp.context_path.exists():
        try:
            ctx = load_context(sp.context_path)
            existing_state = ctx.get("provider_state") if isinstance(ctx.get("provider_state"), dict) else {}
            mark_compaction(
                ctx,
                summary_ref=summary_ref,
                trigger="auto_token_limit",
                source=f"{provider}:{wire_api}",
                approx_input_tokens=approx_input_tokens,
            )
            upsert_provider_state(
                ctx,
                provider=provider,
                wire_api=wire_api,
                conversation_id=str(existing_state.get("conversation_id") or "").strip(),
                last_response_id=str(existing_state.get("last_response_id") or "").strip(),
                summary_ref=summary_ref,
            )
            save_context_atomic(sp.context_path, ctx)
        except SessionContextError:
            pass

    payload.update(
        {
            "applied": True,
            "input_markdown": summary_text,
            "summary_ref": summary_ref,
            "summary_path": str(summary_path),
            "summary_tokens": max(0, int(estimate_tokens(summary_text))),
        }
    )
    return payload


def persist_provider_result(
    *,
    workspace_root: Path,
    session_id: str,
    provider: str,
    wire_api: str,
    response_id: str = "",
    conversation_id: str = "",
    summary_ref: str = "",
) -> dict[str, Any]:
    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    if not sp.context_path.exists():
        return {"updated": False, "reason": "session_missing", "path": str(sp.context_path)}

    try:
        ctx = load_context(sp.context_path)
        existing_state = ctx.get("provider_state") if isinstance(ctx.get("provider_state"), dict) else {}
        upsert_provider_state(
            ctx,
            provider=provider,
            wire_api=wire_api,
            conversation_id=str(conversation_id or existing_state.get("conversation_id") or "").strip(),
            last_response_id=str(response_id or existing_state.get("last_response_id") or "").strip(),
            summary_ref=str(summary_ref or existing_state.get("summary_ref") or "").strip(),
        )
        save_context_atomic(sp.context_path, ctx)
    except SessionContextError as exc:
        return {"updated": False, "reason": exc.error_code, "path": str(sp.context_path)}

    return {"updated": True, "path": str(sp.context_path)}
