"""What the library promises about how it changes (specs/bibliothek.md)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from sdb_reader import EXTRACTION_VERSION, PARSER_VERSION

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
    "project"
]

_SECTION = re.compile(r"^## (.+)$", re.MULTILINE)
_RELEASE = re.compile(r"^(\d+)\.(\d+)\.(\d+) – (\d{4})-(\d{2})-(\d{2})$")


@pytest.mark.spec("BIB-18")
def test_the_changelog_opens_with_unreleased_and_dates_every_release() -> None:
    sections = _SECTION.findall(CHANGELOG)

    assert sections[0] == "Unreleased"
    releases = [_RELEASE.match(title) for title in sections[1:]]
    assert all(releases), [
        t for t, r in zip(sections[1:], releases, strict=True) if not r
    ]
    versions = [
        tuple(int(part) for part in found.groups()[:3]) for found in releases if found
    ]
    assert versions == sorted(versions, reverse=True)
    assert len(set(versions)) == len(versions)


@pytest.mark.spec("BIB-18")
def test_the_newest_release_in_the_changelog_is_the_packages_version() -> None:
    """Before the first release there is none: "Unreleased" then names the
    stage versions the first one reads with."""
    releases = _SECTION.findall(CHANGELOG)[1:]

    if releases:
        assert releases[0].split(" – ")[0] == PROJECT["version"]
    else:
        assert f"`EXTRACTION_VERSION` is {EXTRACTION_VERSION}" in CHANGELOG
        assert f"`PARSER_VERSION` is {PARSER_VERSION}" in CHANGELOG


@pytest.mark.spec("BIB-16")
def test_the_package_names_the_pythons_it_supports_and_the_tests_run_with_each() -> (
    None
):
    """From 3.12 on, every version named: the oldest as ``requires-python``,
    each as a classifier, and each in the matrix of the test workflow. Any
    other workflow that sets Python up uses one of them."""
    oldest = re.fullmatch(r">=3\.(\d+)", PROJECT["requires-python"])
    assert oldest is not None
    named = {
        found.group(1)
        for line in PROJECT["classifiers"]
        if (found := re.fullmatch(r"Programming Language :: Python :: (3\.\d+)", line))
    }
    minors = sorted(int(version.split(".")[1]) for version in named)
    assert minors[0] == int(oldest.group(1)) >= 12
    assert minors == list(range(minors[0], minors[-1] + 1))

    workflows = ROOT / ".github" / "workflows"
    matrix = re.search(r"python: \[([^\]]+)\]", (workflows / "tests.yml").read_text())
    assert matrix is not None
    assert set(re.findall(r"[\d.]+", matrix.group(1))) == named

    for workflow in sorted(workflows.glob("*.yml")):
        fixed = re.findall(r"python-version:\s*'([\d.]+)'", workflow.read_text("utf-8"))
        assert set(fixed) <= named, workflow.name

    for config, pattern in (
        ("ruff.toml", r'target-version = "py3(\d+)"'),
        ("mypy.ini", r"python_version = 3\.(\d+)"),
    ):
        checked = re.search(pattern, (ROOT / config).read_text(encoding="utf-8"))
        assert checked is not None, config
        assert int(checked.group(1)) == minors[0], config


@pytest.mark.spec("BIB-13", "BIB-14", "BIB-15", "BIB-17")
def test_the_page_for_developers_states_each_promise() -> None:
    """These four are promises about what maintainers will do; no test can
    hold them before the fact. What can be held is that a developer is told."""
    page = (ROOT / "docs" / "api" / "stability.md").read_text(encoding="utf-8")

    for rule in ("BIB-13", "BIB-14", "BIB-15", "BIB-16", "BIB-17", "BIB-18"):
        assert rule in page, rule
