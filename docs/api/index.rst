ao-kernel API Reference (V5 Epic 8 E-8-4)
==========================================

.. note::

   **Documentation only.** This API reference is auto-generated from
   docstrings in the public-facade modules. It does NOT flip any guard
   flag; ``support_widening``, ``production_platform_claim``, and
   ``live_adapter_execution`` remain ``const false``. The
   ``_internal`` namespace is intentionally excluded.

Build
-----

.. code-block:: bash

   pip install 'ao-kernel[docs]'
   sphinx-build -b html docs/api docs/api/_build/html

Public Facade
-------------

.. autosummary::
   :toctree: generated
   :recursive:

   ao_kernel
   ao_kernel.client
   ao_kernel.governance
   ao_kernel.llm
   ao_kernel.config
   ao_kernel.session
   ao_kernel.workspace
   ao_kernel.tool_gateway
   ao_kernel.mcp_server
   ao_kernel.telemetry
   ao_kernel.errors
   ao_kernel.cli
   ao_kernel.context

Out of Scope
------------

- The ``ao_kernel._internal`` package (private implementation)
- Bundled JSON resources under ``ao_kernel/defaults/``
- The test suite under ``tests/``
- Live provider client surfaces (live_adapter_execution remains false)

Operator Boundaries
-------------------

This reference is descriptive; it does NOT replace:

- The deployment guide (``docs/PRODUCTION-DEPLOYMENT-GUIDE.md``, E-8-1)
- The operator runbook (``docs/OPERATOR-RUNBOOK.md``, E-8-3)
- The migration guide (``docs/MIGRATION-GUIDE-V4-TO-V5.md``, E-8-6)
- The tutorial (``docs/TUTORIAL-BUILD-AO-MA-SPM-PROGRAM.md``, E-8-5)

See Also
--------

- V5 roadmap: ``.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md``
- Cross-AI Peer Review HARD RULE (2026-05-05 + 2026-05-14)
- ADR-0004 (implementer provider ≠ reviewer provider)
