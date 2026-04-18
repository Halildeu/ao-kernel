"""RFC 7396 JSON Merge Patch — policy-doc object patch only.

PR-C5 stdlib-only implementation. Public entrypoint
:func:`apply_merge_patch` performs a recursive merge of a
``patch`` Mapping into a ``baseline`` Mapping per RFC 7396 rules:

- ``patch[k] is None`` → delete key ``k`` from baseline.
- Both baseline[k] and patch[k] are Mapping → recurse.
- Else → replace baseline[k] with patch[k].
- Keys present only in baseline (not in patch) → preserved.

Scope (Codex iter-1 note): narrow to **policy-doc object patch
only**. Signature is ``Mapping → dict``; top-level non-object
patches (list/scalar/null) are rejected with ``TypeError``.
Operators wanting whole-document delete must use the
``proposed_policies`` API instead of ``proposed_policy_patches``.

Immutability: both ``baseline`` and ``patch`` arguments are
treated as read-only. The helper always returns a fresh dict.
"""

from __future__ import annotations

from typing import Any, Mapping


def apply_merge_patch(
    baseline: Mapping[str, Any],
    patch: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply an RFC 7396 JSON Merge Patch to a policy document.

    See module docstring for the full contract.
    """
    if not isinstance(patch, Mapping):
        raise TypeError(
            "apply_merge_patch: patch must be a Mapping "
            "(policy-doc object patch only)"
        )
    out: dict[str, Any] = (
        dict(baseline) if isinstance(baseline, Mapping) else {}
    )
    for key, pval in patch.items():
        if pval is None:
            out.pop(key, None)
        elif (
            isinstance(pval, Mapping)
            and isinstance(out.get(key), Mapping)
        ):
            out[key] = apply_merge_patch(out[key], pval)
        else:
            out[key] = pval
    return out


def load_policy_patches_from_dir(
    patches_dir: "Path",
) -> dict[str, dict[str, Any]]:
    """Load policy patches from ``patches_dir/*.patch.json``.

    Filename convention (reversible, PR-C5 Codex iter-1 absorb):
    ``<policy_filename>.patch.json`` → maps to policy filename
    ``<policy_filename>.json`` (version suffix preserved).

    Example: ``policy_worktree_profile.v1.patch.json`` → patches
    ``policy_worktree_profile.v1.json``.

    Returns a dict of ``{policy_filename: patch_dict}`` suitable
    for ``simulate_policy_change(proposed_policy_patches=...)``.
    """
    import json
    from pathlib import Path as _Path

    patches_dir = _Path(patches_dir)
    if not patches_dir.is_dir():
        raise FileNotFoundError(
            f"patches directory does not exist: {patches_dir}"
        )
    result: dict[str, dict[str, Any]] = {}
    for patch_file in sorted(patches_dir.glob("*.patch.json")):
        # Strip .patch.json suffix; add .json back.
        stem = patch_file.name[: -len(".patch.json")]
        policy_filename = f"{stem}.json"
        patch_content = json.loads(patch_file.read_text(encoding="utf-8"))
        if not isinstance(patch_content, dict):
            raise TypeError(
                f"patch file {patch_file!s} must contain a JSON object"
            )
        result[policy_filename] = patch_content
    return result


# Lazy re-import for type annotation above (avoids Path import at module top).
from pathlib import Path  # noqa: E402, F401


__all__ = ["apply_merge_patch", "load_policy_patches_from_dir"]
