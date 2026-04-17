"""Internal metrics helpers (CLI handlers, debug-query).

PR-B5 split: public facade lives at :mod:`ao_kernel.metrics`; the
argparse glue + non-Prometheus debug query surface live here so the
public package stays narrow (policy + errors + registry + derivation
+ export only).
"""
