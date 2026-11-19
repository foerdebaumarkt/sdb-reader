#!/usr/bin/env python3
"""The reference lists every exported name, and each with a description.

``docs/reference.md`` names the exported names by hand, in groups, and
Sphinx fetches each one's signature and description from the code. Two
things could go wrong without a warning from Sphinx: a name the package
exports is not on the page, and a name is there with nothing said about it.
``make docs`` runs this over the built page and fails on either:

    .venv/bin/python tools/docs/reference_names.py build/site/reference.html

``tests/test_release.py`` holds the list on the page equal to the package's
without building anything.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

_DIRECTIVE = re.compile(
    r"^\.\. (?:auto(?:function|class|exception)|py:data):: (\w+)$", re.MULTILINE
)
_ENTRY = re.compile(
    r'<dt class="sig sig-object py" id="sdb_reader\.(\w+)">.*?</dt>\s*<dd>(.*?)(?=<dl class="py|</dd>)',
    re.DOTALL,
)


def listed(page: str) -> list[str]:
    """The names *page*, the Markdown source of the reference, lists, in its order.

    >>> listed(".. autofunction:: read_sheet\\n\\n.. py:data:: PARSER_VERSION\\n")
    ['read_sheet', 'PARSER_VERSION']
    """
    return _DIRECTIVE.findall(page)


def described(built: str) -> dict[str, bool]:
    """Each name with an entry in *built*, the reference as HTML, and whether
    the entry says something beside the signature.

    >>> described('<dt class="sig sig-object py" id="sdb_reader.f">f()</dt> <dd><p>Does.</p></dd>')
    {'f': True}
    >>> described('<dt class="sig sig-object py" id="sdb_reader.g">g()</dt> <dd></dd>')
    {'g': False}
    """
    return {
        name: bool(html.unescape(re.sub(r"<[^>]+>", "", body)).strip())
        for name, body in _ENTRY.findall(built)
    }


def problems(built: str, exported: list[str]) -> list[str]:
    """What is wrong with the built reference for the names *exported*."""
    entries = described(built)
    said = [
        f"{name} is exported and not in the reference"
        for name in exported
        if name not in entries
    ]
    said += [
        f"{name} is in the reference and not exported"
        for name in entries
        if name not in exported
    ]
    said += [
        f"{name} has no description" for name in exported if entries.get(name) is False
    ]
    return said


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    import sdb_reader

    exported = list(sdb_reader.__all__)
    source = Path(__file__).resolve().parents[2] / "docs" / "reference.md"
    on_the_page = listed(source.read_text(encoding="utf-8"))
    said = [
        f"{name} is listed twice in docs/reference.md"
        for name in sorted(set(on_the_page))
        if on_the_page.count(name) > 1
    ]
    said += problems(Path(argv[0]).read_text(encoding="utf-8"), exported)
    for line in said:
        print(f"reference: {line}", file=sys.stderr)
    return 1 if said else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
