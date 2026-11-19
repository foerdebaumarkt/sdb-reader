#!/usr/bin/env python3
"""What the release workflow asks before it builds a release, and its notes.

A release is a tag ``v<version>`` (docs/contributing/releasing.md). The
workflow calls this before anything is built:

    .venv/bin/python tools/release.py check v0.9.0   # exit 1 names what is wrong
    .venv/bin/python tools/release.py notes 0.9.0    # the changelog's section
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The first version that is published. An older version was never public and
# is not released by the workflow (BIB-23).
FIRST_PUBLIC = (0, 9, 0)

_TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
_SECTION = re.compile(r"^## (.+)$", re.MULTILINE)
_RELEASE = re.compile(r"(\d+\.\d+\.\d+) – \d{4}-\d{2}-\d{2}")


def problems(tag: str, version: str, changelog: str) -> list[str]:
    """Why *tag* cannot be released as the package's *version*; empty if it can.

    >>> log = "# Changelog\\n\\n## Unreleased\\n\\n## 0.9.0 – 2026-12-01\\n\\nFirst.\\n"
    >>> problems("v0.9.0", "0.9.0", log)
    []
    >>> problems("v0.9.0", "0.9.1", log)
    ['the tag v0.9.0 is not the version of the package, 0.9.1']
    """
    found = _TAG.fullmatch(tag)
    if found is None:
        return [f"the tag {tag} is not of the form v<major>.<minor>.<patch>"]
    said = []
    if tag != f"v{version}":
        said.append(f"the tag {tag} is not the version of the package, {version}")
    if tuple(int(part) for part in found.groups()) < FIRST_PUBLIC:
        first = ".".join(str(part) for part in FIRST_PUBLIC)
        said.append(f"{tag} is older than the first public version, {first}")
    releases = [
        match[1]
        for title in _SECTION.findall(changelog)
        if (match := _RELEASE.fullmatch(title))
    ]
    if not releases or releases[0] != tag.removeprefix("v"):
        said.append(
            f"the changelog's newest release is not {tag.removeprefix('v')}: "
            "its section with the date is missing"
        )
    return said


def notes(changelog: str, version: str) -> str:
    """The section of *version* in *changelog*, without its heading.

    >>> log = "## Unreleased\\n\\n## 0.9.0 – 2026-12-01\\n\\nFirst.\\n\\n## 0.8.0 – 2026-11-01\\n\\nOld.\\n"
    >>> notes(log, "0.9.0")
    'First.'
    """
    sections = re.split(r"^## ", changelog, flags=re.MULTILINE)
    for section in sections[1:]:
        title, _, body = section.partition("\n")
        match = _RELEASE.fullmatch(title.strip())
        if match and match[1] == version:
            return body.strip()
    raise ValueError(f"the changelog has no section for {version}")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("check", "notes"):
        print(__doc__, file=sys.stderr)
        return 2
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if argv[0] == "notes":
        print(notes(changelog, argv[1]))
        return 0
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    said = problems(argv[1], project["project"]["version"], changelog)
    for line in said:
        print(f"not released: {line}", file=sys.stderr)
    return 1 if said else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
