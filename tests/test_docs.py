"""The documentation holds together: links, the two languages, generated pages."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

_FENCE = re.compile(r"^(\s*)```.*?^\1```[ \t]*$", re.MULTILINE | re.DOTALL)
_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
_HEADING = re.compile(r"^(#{1,6}) (.+?)\s*$", re.MULTILINE)

# The operator's manual: each English page and its German counterpart.
MANUAL = {
    "README.md": "README.md",
    "installing.md": "installation.md",
    "reading.md": "lesen.md",
    "showing.md": "anzeigen.md",
    "collection.md": "bestand.md",
    "output.md": "ausgabe.md",
    "embedded-file.md": "eingebettete-datei.md",
    "asking.md": "fragen.md",
    "comparing-runs.md": "laeufe-vergleichen.md",
    "messages.md": "meldungen.md",
    "troubleshooting.md": "fehlerbehebung.md",
}


def _pages() -> list[Path]:
    return sorted(
        [
            *ROOT.glob("README*.md"),
            ROOT / "CONTRIBUTING.md",
            *DOCS.rglob("*.md"),
            *(ROOT / "tools").rglob("README.md"),
        ]
    )


def _prose(text: str) -> str:
    """The page without its fenced blocks: what is in them is no Markdown."""
    return _FENCE.sub("", text)


def _anchors(page: Path) -> set[str]:
    """The anchors a page's headings get, as the usual renderers make them."""
    anchors = set()
    for _, title in _HEADING.findall(_prose(page.read_text(encoding="utf-8"))):
        plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title).replace("`", "")
        anchors.add(re.sub(r"[^\w\- ]", "", plain.lower()).replace(" ", "-"))
    return anchors


@pytest.mark.parametrize("page", _pages(), ids=lambda p: str(p.relative_to(ROOT)))
def test_every_relative_link_leads_somewhere(page: Path) -> None:
    broken = []
    for target in _LINK.findall(_prose(page.read_text(encoding="utf-8"))):
        if re.match(r"[a-z][a-z0-9+.-]*:", target):
            continue  # another site; not ours to check
        path, _, anchor = target.partition("#")
        linked = (page.parent / path).resolve() if path else page
        if not linked.exists():
            broken.append(f"{target}: no such file")
        elif anchor and linked.suffix == ".md" and anchor not in _anchors(linked):
            broken.append(f"{target}: no such heading")

    assert broken == []


def test_the_manual_has_the_same_pages_in_both_languages() -> None:
    assert {p.name for p in (DOCS / "usage").glob("*.md")} == set(MANUAL)
    assert {p.name for p in (DOCS / "bedienung").glob("*.md")} == set(MANUAL.values())


@pytest.mark.parametrize(("english", "german"), sorted(MANUAL.items()))
def test_a_page_of_the_manual_is_built_alike_in_both_languages(
    english: str, german: str
) -> None:
    """The same headings in number and nesting, and the same code blocks,
    so that one page cannot be changed without the other. Commands, options
    and output are the program's and read the same in both."""
    one = (DOCS / "usage" / english).read_text(encoding="utf-8")
    other = (DOCS / "bedienung" / german).read_text(encoding="utf-8")

    def levels(text: str) -> list[int]:
        return [len(marks) for marks, _ in _HEADING.findall(_prose(text))]

    def blocks(text: str) -> list[str]:
        return [match.group(0) for match in _FENCE.finditer(text)]

    assert levels(one) == levels(other)
    assert blocks(one) == blocks(other)


def _message_pages() -> ModuleType:
    return _tool("message_pages")


def _tool(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "tools" / "docs" / f"{name}.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("language", ["de", "en"])
def test_the_list_of_all_messages_is_what_the_tool_writes(language: str) -> None:
    """Run tools/docs/message_pages.py after changing a code or a sentence."""
    tool = _message_pages()
    path = tool.PAGES[language][0]

    assert path.read_text(encoding="utf-8") == tool.page(language)


@pytest.mark.spec("SDW-31")
@pytest.mark.parametrize("language", ["de", "en"])
def test_the_table_of_presets_is_what_the_tool_writes(language: str) -> None:
    """Run tools/docs/preset_table.py after changing presets.toml."""
    tool = _tool("preset_table")

    assert tool.PAGES[language].read_text(encoding="utf-8") == tool.page(language)
