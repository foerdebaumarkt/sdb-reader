"""The examples in the documentation run and hold what they claim."""

from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
_BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)

# The pages for developers, in the order their index gives them: an example
# may use what an earlier page made (``path``, ``reading``, ``sheet``).
API_PAGES = (
    "getting-started.md",
    "reading.md",
    "messages.md",
    "judging.md",
    "statements.md",
    "stored-texts.md",
    "embedded.md",
    "schema.md",
)


def _run(page: Path, namespace: dict[str, object]) -> int:
    blocks = _BLOCK.findall(page.read_text(encoding="utf-8"))
    for block in blocks:
        exec(compile(block, page.name, "exec"), namespace)
    return len(blocks)


def test_the_python_examples_of_the_api_pages_run_in_order() -> None:
    """One namespace for the whole part, as its index says; each example
    asserts what its page says about it."""
    namespace: dict[str, object] = {}
    for name in API_PAGES:
        assert _run(DOCS / "api" / name, namespace), f"{name} has no example"


def test_the_page_on_the_current_sheet_stands_on_its_own() -> None:
    assert _run(DOCS / "api" / "current-sheet.md", {})


def test_every_api_page_with_python_is_run() -> None:
    """A new page with examples has to be listed, or nothing runs them."""
    with_python = {
        page.name
        for page in (DOCS / "api").glob("*.md")
        if _BLOCK.search(page.read_text(encoding="utf-8"))
    }
    assert with_python == {*API_PAGES, "current-sheet.md"}


def test_no_other_page_holds_python_nobody_runs() -> None:
    elsewhere = [
        str(page.relative_to(DOCS))
        for page in DOCS.rglob("*.md")
        if page.parent.name != "api" and _BLOCK.search(page.read_text(encoding="utf-8"))
    ]
    assert elsewhere == []
