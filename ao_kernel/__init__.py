"""ao-kernel — Governed AI orchestration runtime."""

__version__ = "3.11.0"

from ao_kernel.client import AoKernelClient
from ao_kernel.config import load_default, load_with_override, workspace_root

__all__ = [
    "__version__",
    "AoKernelClient",
    "workspace_root",
    "load_default",
    "load_with_override",
]
