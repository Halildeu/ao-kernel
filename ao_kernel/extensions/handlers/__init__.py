"""Code-owned handlers for bundled extensions.

Handlers are registered explicitly (D7: no plugin auto-discovery). Each
bundled extension with real behavior ships a module here and a public
registration function called by ``ao_kernel.extensions.bootstrap``.
"""
