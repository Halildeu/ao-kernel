"""ao-kernel — Governed AI orchestration runtime."""

__version__ = "2.0.0"

from ao_kernel.config import load_default, load_with_override, workspace_root

__all__ = [
    "__version__",
    "workspace_root",
    "load_default",
    "load_with_override",
]
