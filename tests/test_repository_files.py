"""Checks over the playbook's own files that ship with the public repository."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from tests.support import (
    EXTERNAL_URI_SCHEMES,
    ROOT,
    heading_slug,
    heading_slugs,
    markdown_link_targets,
    read,
    repository_paths,
)


def test_ci_covers_supported_python_versions() -> None:
    workflows = sorted((ROOT / ".github/workflows").glob("*.y*ml"))
    assert "test.yml" in {path.name for path in workflows}

    workflow = read(".github/workflows/test.yml")

    assert "permissions:\n  contents: read" in workflow
    assert "fail-fast: false" in workflow
    version_match = re.search(r"python-version: \[([^]]+)\]", workflow)
    assert version_match is not None
    versions = {
        version.strip().strip("\"'") for version in version_match.group(1).split(",")
    }
    assert {"3.11", "3.12"} <= versions
    assert "python-version: ${{ matrix.python-version }}" in workflow
    assert "uses: actions/checkout@" in workflow
    assert "uses: actions/setup-python@" in workflow
    assert "python -m pip install -r requirements-dev.txt" in workflow
    assert "cache-dependency-path: requirements-dev.txt" in workflow
    assert "run: python -m mypy ." in workflow
    assert "run: python -m pytest -q" in workflow
    assert "run: |" not in workflow
    for content in (path.read_text() for path in workflows):
        assert re.search(r"^\s+if:", content, re.MULTILINE) is None
        assert "continue-on-error" not in content


def test_heading_slug_preserves_underscores_and_strips_emphasis() -> None:
    assert heading_slug("Use `snake_case_name`") == "use-snake_case_name"
    assert heading_slug("**Bold** and *italic*") == "bold-and-italic"
    assert heading_slug("under_score and *star*") == "under_score-and-star"


def test_heading_slug_matches_github_whitespace_handling() -> None:
    # GitHub's slugger removes punctuation and lowercases text, but only
    # replaces each whitespace character with a hyphen -- it never collapses
    # repeated whitespace/hyphen runs or strips leading/trailing hyphens.
    assert heading_slug("Development & community") == "development--community"
    assert heading_slug("A -- B") == "a----b"


def test_heading_slugs_ignores_headings_inside_fenced_code_blocks() -> None:
    markdown = (
        "# Real Heading\n\n"
        "```bash\n"
        "# This looks like a heading but is a shell comment\n"
        "echo hi\n"
        "```\n\n"
        "## Another Real Heading\n"
    )
    slugs = heading_slugs(markdown)
    assert slugs == {"real-heading", "another-real-heading"}
    assert "this-looks-like-a-heading-but-is-a-shell-comment" not in slugs


def test_heading_slugs_disambiguates_duplicate_headings() -> None:
    markdown = "# Setup\n\n## Setup\n\n### Setup\n"
    slugs = heading_slugs(markdown)
    assert slugs == {"setup", "setup-1", "setup-2"}


def test_markdown_link_targets_excludes_links_inside_fenced_code_blocks() -> None:
    markdown = (
        "See [real link](README.md) for details.\n\n"
        "```markdown\n"
        "[fake link](does-not-exist.md)\n"
        "```\n"
    )
    targets = markdown_link_targets(markdown)
    assert targets == ["README.md"]
    assert "does-not-exist.md" not in targets


def test_markdown_navigation_links_resolve_across_the_repository() -> None:
    examined = 0
    anchors_validated = 0

    for path in repository_paths():
        if path.suffix.lower() != ".md":
            continue
        source = ROOT / path
        markdown = source.read_text()

        for target in markdown_link_targets(markdown):
            if target.startswith(EXTERNAL_URI_SCHEMES):
                continue

            if target.startswith("#"):
                # Same-page anchor: validate against this file's own headings
                # rather than skipping it.
                examined += 1
                anchors_validated += 1
                assert target[1:] in heading_slugs(markdown), (path, target)
                continue

            path_part, _, fragment = target.partition("#")
            examined += 1
            resolved = (source.parent / path_part).resolve()
            assert resolved.is_file(), (path, target)

            if fragment and resolved.suffix == ".md":
                slugs = heading_slugs(resolved.read_text())
                assert fragment in slugs, (path, target)
                anchors_validated += 1

    assert examined >= 40
    assert anchors_validated >= 4


def test_repository_keeps_its_governance_minimal() -> None:
    """A repository of learnings, not a project with process.

    Only a licence and a contributing guide earn their place. The rest is
    furniture that accumulates by default, so name it and keep it out.
    """
    for path in ("LICENSE", "CONTRIBUTING.md", ".github/dependabot.yml"):
        assert (ROOT / path).is_file(), path

    for path in (
        ".github/CODEOWNERS",
        ".github/ISSUE_TEMPLATE",
        ".github/pull_request_template.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
    ):
        assert not (ROOT / path).exists(), (
            f"{path}: governance stays minimal by design; private vulnerability "
            "reporting is documented in CONTRIBUTING.md"
        )


def test_dependency_updates_cover_code_and_workflows() -> None:
    configuration = read(".github/dependabot.yml")

    assert configuration.count("package-ecosystem:") == 2
    assert 'package-ecosystem: "pip"' in configuration
    assert 'package-ecosystem: "github-actions"' in configuration
    assert configuration.count("interval: monthly") == 2


def test_development_tool_versions_have_one_owner() -> None:
    requirements = read("requirements-dev.txt").splitlines()

    assert {"mypy", "pytest", "ruff"} == {
        line.split("==", 1)[0] for line in requirements
    }
    assert all(re.fullmatch(r"[a-z-]+==\d+(?:\.\d+)+", line) for line in requirements)
    for path in (
        "AGENTS.md",
        "README.md",
        "CONTRIBUTING.md",
        ".github/workflows/test.yml",
        "pyproject.toml",
    ):
        text = read(path)
        assert "pytest==" not in text
        assert "ruff==" not in text
        assert "mypy==" not in text

    agents = read("AGENTS.md")
    contributing = read("CONTRIBUTING.md")
    assert "## Commands" in agents
    for command in (
        "python3 -m pip install -r requirements-dev.txt",
        "python3 -m ruff check . && python3 -m ruff format --check . "
        "&& python3 -m mypy . && python3 -m pytest -q",
    ):
        assert command in agents
        assert command in contributing


def test_documented_check_commands_pin_the_installed_tools() -> None:
    """Bare `ruff`/`mypy` resolve to whatever is first on PATH.

    The pinned versions in requirements-dev.txt only bind when the tools are
    invoked through the same interpreter that installed them, so every
    documented invocation goes through `python3 -m` (or `python -m` in CI).
    """
    checked = 0
    for path in ("AGENTS.md", "CONTRIBUTING.md", "README.md"):
        text = read(path)
        for tool in ("ruff", "mypy", "pytest"):
            for match in re.finditer(rf"(?<![\w./-]){tool}\b", text):
                checked += 1
                prefix = text[max(0, match.start() - 3) : match.start()]
                assert prefix == "-m ", (path, tool, match.start())
    # Guard against a vacuous pass: the documented commands must mention the
    # tools at all for the rule above to have examined anything.
    assert checked >= 9

    workflow = read(".github/workflows/test.yml")
    for tool in ("ruff", "mypy", "pytest"):
        assert f"run: python -m {tool}" in workflow, tool
        assert not re.search(rf"run:\s+{tool}\s", workflow), tool


def test_examples_are_invoked_consistently_as_modules() -> None:
    """`python3 examples/evaluate_cascade.py` fails on its package import.

    Documenting one example as a path and the other as a module invites the
    reader to guess the failing form, so every documented invocation uses -m.
    """
    for path in ("README.md", "docs/concepts/evaluation.md", "docs/limitations.md"):
        text = read(path)
        assert not re.search(r"python3?\s+examples/\S+\.py", text), path


def test_shipped_tree_carries_no_development_lane_references() -> None:
    """The published snapshot must not describe paths it does not contain."""
    excluded = Path("dev")
    scanned: list[Path] = []
    forbidden = ("dev" + "/", ".git" + "attributes")
    text_suffixes = {".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
    for path in repository_paths():
        if (
            excluded in path.parents
            or path.name == ".git" + "attributes"
            or path.suffix.lower() not in text_suffixes
        ):
            continue
        scanned.append(path)
        text = (ROOT / path).read_text(errors="ignore")
        for token in forbidden:
            assert token not in text, (path, token)

    assert len(scanned) >= 25
    assert {path.suffix for path in scanned} >= {".md", ".py", ".toml", ".txt", ".yml"}


def test_figure_checksum_recorded_in_provenance_matches_the_file() -> None:
    """The provenance page states a SHA-256 for the case-study figure.

    An unverified checksum is worse than none: it looks like evidence while
    drifting silently. Recompute it instead of trusting the text.
    """
    figure = ROOT / "docs/case-studies/figures/corrected-context-contrasts.svg"
    digest = hashlib.sha256(figure.read_bytes()).hexdigest()

    provenance = read("docs/provenance.md")
    recorded = re.findall(r"\b([0-9a-f]{64})\b", provenance)
    assert recorded == [digest], (recorded, digest)
