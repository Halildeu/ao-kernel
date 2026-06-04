"""Support-widening per-surface smoke harnesses (V5 Epic 3 E-3-2).

Library-mode-only harnesses that exercise stub adapters (no network, no `.ao/`
mutation) and emit a `support_widening_evidence.v1` artifact per surface class.
Stub purity is enforced by a dominant runtime kill-switch (`killswitch.py`):
network, subprocess, shell, dynamic-import and secret-env access all fail closed
inside the harness execution context."""
