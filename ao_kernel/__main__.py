"""Module entrypoint for ``python -m ao_kernel``."""

from __future__ import annotations

from ao_kernel.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
