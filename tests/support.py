"""Shared helpers for checks that ship with the public playbook."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]

EXTERNAL_URI_SCHEMES = ("http://", "https://", "mailto:")

MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
FENCED_CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)


def read(path: str) -> str:
    return (ROOT / path).read_text()


def repository_paths(*, include_untracked: bool = False) -> list[Path]:
    command = ["git", "ls-files", "--cached"]
    if include_untracked:
        command.extend(["--others", "--exclude-standard"])
    output = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [Path(path) for path in output.splitlines()]


def heading_slug(heading: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s", "-", text)
    return text


def heading_slugs(markdown: str) -> set[str]:
    # Remove fenced code blocks first so shell comments (e.g. `# some note`)
    # inside ``` fences aren't mistaken for Markdown headings.
    without_fences = FENCED_CODE_BLOCK_PATTERN.sub("", markdown)
    slugs: dict[str, int] = {}
    result: set[str] = set()
    for _, heading in HEADING_PATTERN.findall(without_fences):
        slug = heading_slug(heading)
        count = slugs.get(slug, 0)
        slugs[slug] = count + 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def markdown_link_targets(markdown: str) -> list[str]:
    # Remove fenced code blocks first so example links inside ``` fences
    # (e.g. documentation of the link syntax itself) aren't checked as real
    # references.
    without_fences = FENCED_CODE_BLOCK_PATTERN.sub("", markdown)
    return MARKDOWN_LINK_PATTERN.findall(without_fences)
