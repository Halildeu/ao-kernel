"""Test / demo fixtures shipped with ao-kernel.

Runtime package. Public stability policy: fixture entry points
(currently just ``codex_stub``) preserve their deterministic behaviour
within the same semver minor. They are NOT a production adapter
authoring API; workspaces that point their workflows at these fixtures
for CI determinism should pin the major version and migrate at
v(N+1).0 per CHANGELOG notes.

See ``ao_kernel.fixtures.codex_stub`` for the invocation contract.
"""
