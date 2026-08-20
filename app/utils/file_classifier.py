"""Pure helper for classifying changed file paths.

Used by structural impact selection and input readiness to ensure a single,
consistent definition of source/test/non-coverable files.
"""


def classify_changed_file(file_path: str) -> str:
    """Classify a changed file as source, test, or non-coverable.

    Mirrors the semantics previously established in InputReadinessV2Service so
    that coverage-gap analysis only runs against files that can meaningfully
    be covered by LCOV.
    """
    path_lower = file_path.lower()

    test_patterns = [
        "__tests__",
        "test_",
        "_test.",
        ".test.",
        ".spec.",
        "_spec.",
        "spec_",
        "/tests/",
        "/test/",
    ]

    non_coverable_patterns = [
        "/docs/",
        "/documentation/",
        "/.github/",
        "/.vscode/",
        "/.idea/",
        "/node_modules/",
        "/.next/",
        "/build/",
        "/dist/",
        "/out/",
        "/.cache/",
        "/coverage/",
        "/.env",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "dockerfile",
        "docker-compose",
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
    ]

    for pattern in test_patterns:
        if pattern in path_lower or path_lower.endswith(pattern):
            return "test"

    for pattern in non_coverable_patterns:
        if pattern in path_lower or path_lower.endswith(pattern):
            return "non_coverable"

    return "source"
