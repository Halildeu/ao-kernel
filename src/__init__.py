"""Project source package (WWV) — DEPRECATED: use ao_kernel.* instead."""
import warnings as _w

_w.warn(
    "Importing from 'src.*' is deprecated. Use 'ao_kernel.*' instead. "
    "This shim will be removed in v2.0.0.",
    FutureWarning,
    stacklevel=2,
)
del _w
