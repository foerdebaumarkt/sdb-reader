"""Releases and the documentation site (specs/bibliothek.md, BIB-22, BIB-23)."""

from __future__ import annotations

import doctest
import importlib.util
import io
import re
import sys
import tarfile
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://foerdebaumarkt.github.io/sdb-reader/"
REPOSITORY = "https://github.com/foerdebaumarkt/sdb-reader"
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
    "project"
]
RELEASE = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _tool(path: str) -> ModuleType:
    file = ROOT / "tools" / path
    spec = importlib.util.spec_from_file_location(file.stem, file)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # A dataclass or a doctest looks its module up by name.
    sys.modules[file.stem] = module
    spec.loader.exec_module(module)
    return module


def _job(name: str) -> str:
    """The text of one job of the release workflow."""
    jobs = RELEASE.split("\njobs:\n", 1)[1]
    found = re.search(rf"^  {name}:\n(.*?)(?=^  \w+:\n|\Z)", jobs, re.M | re.S)
    assert found is not None, name
    return found.group(1)


def _edition(folder: Path, version: str, page: str) -> None:
    """A release's documentation file, with one page that says *page*."""
    data = page.encode()
    with tarfile.open(folder / f"sdb-reader-{version}-docs.tar.gz", "w:gz") as archive:
        info = tarfile.TarInfo("site/index.html")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))


@pytest.mark.parametrize(
    "path", ["release.py", "docs/site_links.py", "docs/assemble_site.py"]
)
def test_the_examples_in_the_tools_hold(path: str) -> None:
    """The tools are no package, so pytest does not collect their examples."""
    result = doctest.testmod(_tool(path))

    assert result.failed == 0


class TestTheSite:
    @pytest.mark.spec("BIB-22")
    def test_the_package_and_the_pages_name_the_one_address(self) -> None:
        assert PROJECT["urls"]["Documentation"] == SITE
        assert PROJECT["urls"]["Source"] == REPOSITORY
        for page in (
            "README.md",
            "README.de.md",
            "docs/usage/README.md",
            "docs/bedienung/README.md",
            "docs/contributing/releasing.md",
        ):
            assert SITE in (ROOT / page).read_text(encoding="utf-8"), page
        assert f'REPOSITORY = "{REPOSITORY}"' in (ROOT / "docs" / "conf.py").read_text(
            encoding="utf-8"
        )

    @pytest.mark.spec("BIB-22")
    def test_the_readme_the_index_shows_has_no_link_that_needs_the_repository(
        self,
    ) -> None:
        """The package index shows README.md on a page of its own, where a
        relative link leads nowhere. Every link names a page of the site's
        newest edition or a file of the repository, and each of them exists."""
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        wrong = []
        for target in _LINK.findall(text):
            if target.startswith(f"{SITE}latest/"):
                page = target.removeprefix(f"{SITE}latest/").removesuffix(".html")
                file = ROOT / "docs" / f"{page}.md"
            elif target.startswith(
                (f"{REPOSITORY}/blob/main/", f"{REPOSITORY}/tree/main/")
            ):
                file = ROOT / target.split("/main/", 1)[1]
            else:
                wrong.append(f"{target}: neither the site nor the repository")
                continue
            if not file.exists():
                wrong.append(f"{target}: no {file.relative_to(ROOT)}")

        assert wrong == []

    @pytest.mark.spec("BIB-22")
    def test_every_page_is_in_the_navigation(self) -> None:
        """Sphinx warns about a page no table of contents names, and the
        build fails on a warning; this says the same without building."""
        docs = ROOT / "docs"
        index = (docs / "index.md").read_text(encoding="utf-8")
        named = set()
        for block in re.findall(r"```\{toctree\}\n(.*?)```", index, re.S):
            named |= {
                line.strip()
                for line in block.splitlines()
                if line.strip() and not line.startswith(":")
            }
        pages = {
            str(path.relative_to(docs).with_suffix(""))
            for path in docs.rglob("*.md")
            if path.relative_to(docs).parts[0] != "_templates"
        }

        assert named == pages - {"index", "README"}

    @pytest.mark.spec("BIB-22")
    def test_a_link_that_leaves_the_pages_leads_to_the_repository_at_the_tag(
        self,
    ) -> None:
        links = _tool("docs/site_links.py")

        def on_site(text: str, docname: str) -> str:
            return links.for_site(
                text, docname=docname, repository=REPOSITORY, ref="v0.9.0"
            )

        assert (
            on_site("see [BIB-1](../../specs/bibliothek.md#regeln)", "api/stability")
            == f"see [BIB-1]({REPOSITORY}/blob/v0.9.0/specs/bibliothek.md#regeln)"
        )
        assert (
            on_site("[news](../CHANGELOG.md)", "how-it-works") == "[news](changelog.md)"
        )
        assert on_site("[news](../../CHANGELOG.md)", "usage/installing") == (
            "[news](../changelog.md)"
        )
        # Inside the pages, to another site, an anchor, a picture's address,
        # and a fenced block: all as they were.
        for same in (
            "[next](reading.md#exit-codes)",
            "[up](../how-it-works.md)",
            "[uv](https://docs.astral.sh/uv/)",
            "[above](#install)",
            "```\n[kept](../../specs/README.md)\n```",
        ):
            assert on_site(same, "usage/installing") == same

    @pytest.mark.spec("BIB-22")
    def test_the_site_is_put_together_from_what_each_release_built(
        self, tmp_path: Path
    ) -> None:
        assemble = _tool("docs/assemble_site.py").assemble
        files = tmp_path / "files"
        files.mkdir()
        _edition(files, "0.9.0", "first")
        _edition(files, "0.10.0", "newest")
        _edition(files, "0.9.1", "fix")
        (files / "sdb_reader-0.10.0-py3-none-any.whl").write_text("no edition")
        out = tmp_path / "pages"

        versions = assemble(files, out)

        # By number, not by letters: 0.10.0 is newer than 0.9.1.
        assert versions == ["0.10.0", "0.9.1", "0.9.0"]
        assert (out / "0.9.0" / "index.html").read_text() == "first"
        assert (out / "latest" / "index.html").read_text() == "newest"
        assert 'url=latest/"' in (out / "index.html").read_text()
        listed = re.findall(
            r'<li><a href="([^"]+)"', (out / "versions.html").read_text()
        )
        assert listed == ["0.10.0/", "0.9.1/", "0.9.0/"]
        assert (out / ".nojekyll").exists()
        assert sorted(path.name for path in out.iterdir()) == [
            ".nojekyll",
            "0.10.0",
            "0.9.0",
            "0.9.1",
            "index.html",
            "latest",
            "versions.html",
        ]

    @pytest.mark.spec("BIB-22")
    def test_a_file_that_is_no_edition_is_refused(self, tmp_path: Path) -> None:
        assemble = _tool("docs/assemble_site.py").assemble
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ValueError, match="no sdb-reader"):
            assemble(empty, tmp_path / "a")

        other = tmp_path / "other"
        other.mkdir()
        with tarfile.open(other / "sdb-reader-0.9.0-docs.tar.gz", "w:gz") as archive:
            info = tarfile.TarInfo("elsewhere/index.html")
            archive.addfile(info, io.BytesIO(b""))
        with pytest.raises(ValueError, match="does not hold the folder site/"):
            assemble(other, tmp_path / "b")


class TestARelease:
    LOG = (
        "# Changelog\n\n## Unreleased\n\n"
        "## 0.9.1 – 2026-12-10\n\nA fix.\n\n### Breaking\n\nNothing.\n\n"
        "## 0.9.0 – 2026-12-01\n\nThe first.\n"
    )

    @pytest.mark.spec("BIB-23")
    def test_a_tag_is_released_only_as_the_packages_version(self) -> None:
        problems = _tool("release.py").problems

        assert problems("v0.9.1", "0.9.1", self.LOG) == []
        assert problems("v0.9.2", "0.9.1", self.LOG) == [
            "the tag v0.9.2 is not the version of the package, 0.9.1",
            "the changelog's newest release is not 0.9.2: "
            "its section with the date is missing",
        ]
        assert problems("0.9.1", "0.9.1", self.LOG) == [
            "the tag 0.9.1 is not of the form v<major>.<minor>.<patch>"
        ]
        assert problems("v0.9.1rc1", "0.9.1", self.LOG) != []

    @pytest.mark.spec("BIB-23")
    def test_a_version_before_the_first_public_one_is_not_released(self) -> None:
        tool = _tool("release.py")
        log = "## Unreleased\n\n## 0.8.9 – 2026-11-30\n\nNever public.\n"

        assert tool.FIRST_PUBLIC == (0, 9, 0)
        assert tool.problems("v0.8.9", "0.8.9", log) == [
            "v0.8.9 is older than the first public version, 0.9.0"
        ]
        # By number, not by letters.
        assert tool.problems("v0.10.0", "0.10.0", "## 0.10.0 – 2027-01-01\n") == []

    @pytest.mark.spec("BIB-23")
    def test_the_changelog_has_to_name_the_release(self) -> None:
        tool = _tool("release.py")
        unreleased = "# Changelog\n\n## Unreleased\n\nNot dated yet.\n"

        assert tool.problems("v0.9.0", "0.9.0", unreleased) == [
            "the changelog's newest release is not 0.9.0: "
            "its section with the date is missing"
        ]
        assert tool.notes(self.LOG, "0.9.1") == "A fix.\n\n### Breaking\n\nNothing."
        assert tool.notes(self.LOG, "0.9.0") == "The first."
        with pytest.raises(ValueError, match=r"no section for 0\.8\.0"):
            tool.notes(self.LOG, "0.8.0")

    @pytest.mark.spec("BIB-23")
    def test_the_workflow_starts_on_a_version_tag_and_checks_it_first(self) -> None:
        trigger = RELEASE.split("\npermissions:", 1)[0]
        assert "tags:\n      - 'v[0-9]+.[0-9]+.[0-9]+'" in trigger
        assert "branches:" not in trigger
        assert "workflow_dispatch" not in trigger

        build = _job("build")
        check = build.index("tools/release.py check")
        assert "git merge-base --is-ancestor" in build
        for later in ("make dist", "make package-check", "make docs", "pytest"):
            assert build.index(later) > check, later

    @pytest.mark.spec("BIB-23")
    def test_nothing_leaves_a_repository_that_is_not_public(self) -> None:
        """The index and the site are the two ways out, and each job that
        takes one runs only for a public repository. No other job may ask
        for the token either of them publishes with."""
        public = (
            "needs.build.outputs.public == 'true' "
            "&& github.event.repository.private == false"
        )
        outward = {
            "pypi": "pypa/gh-action-pypi-publish@",
            "deploy": "actions/deploy-pages@",
        }
        jobs = re.findall(r"^  (\w+):\n", RELEASE.split("\njobs:\n", 1)[1], re.M)
        assert set(outward) < set(jobs)

        for name in jobs:
            job = _job(name)
            condition = re.search(r"^    if: (.+)$", job, re.M)
            if name in outward:
                assert outward[name] in job
                assert condition is not None, name
                assert public in condition.group(1), name
            else:
                assert "id-token: write" not in job, name
                assert not any(action in job for action in outward.values()), name
        assert "permissions: {}" in RELEASE
        # The answer the jobs run on is GitHub's, asked in the build job.
        assert 'gh api "repos/${GITHUB_REPOSITORY}" --jq .private' in _job("build")

    @pytest.mark.spec("BIB-23")
    def test_the_index_takes_the_package_without_a_stored_secret(self) -> None:
        pypi = _job("pypi")

        assert "name: pypi" in pypi
        assert "id-token: write" in pypi
        assert "secrets." not in RELEASE
        assert "password:" not in RELEASE
