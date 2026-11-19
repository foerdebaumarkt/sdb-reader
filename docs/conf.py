"""Sphinx configuration of the documentation site (``make docs``).

The pages are the Markdown files under ``docs/``, read through MyST as they
are; they stay readable on GitHub. What only the site needs is here, in
``index.md`` (the navigation), ``changelog.md`` and ``reference.md`` (the
exported names, described from the code).
"""

from __future__ import annotations

import os
import sys
from enum import Enum
from importlib.metadata import version as installed_version
from pathlib import Path
from typing import Any

from pygments.lexers.special import TextLexer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "docs"))

from site_links import for_site

project = "sdb-reader"
author = "Förde-Baumarkt Holger Claussen GmbH & Co. KG"
copyright = f"2026, {author}"
release = installed_version("sdb-reader")
version = release

# Where a link that leaves docs/ points: the file on GitHub, at the tag a
# release is built for. The release workflow names the tag; a build from a
# checkout points at main.
REPOSITORY = "https://github.com/foerdebaumarkt/sdb-reader"
REF = os.environ.get("SDB_READER_DOCS_REF", "main")

extensions = ["myst_parser", "sphinx.ext.autodoc"]
source_suffix = {".md": "markdown"}
root_doc = "index"
# docs/README.md is the entry for a reader on GitHub; on the site index.md
# stands in its place.
exclude_patterns = ["README.md", "_templates"]
templates_path = ["_templates"]

# The reference (reference.md) is made from the descriptions in the code:
# every exported name is listed there by hand, in groups, and autodoc fetches
# its signature and description. A description Sphinx cannot render is a
# warning, and `make docs` fails on a warning.
autodoc_member_order = "bysource"
autodoc_typehints = "signature"
autodoc_typehints_format = "short"
# The names are shown as a caller writes them, sdb_reader.<name>; the page
# says once where they come from.
add_module_names = False
# The right-hand contents of the reference list the names without their
# parents: "render", not "Catalog.render".
toc_object_entries_show_parents = "hide"

# The anchors GitHub gives headings, down to the last level, so that a link
# to a heading works in both places.
myst_heading_anchors = 6

# The pages are English with a German operator's manual beside the English
# one; the site's own words (search, navigation) are English.
language = "en"

html_theme = "furo"
html_title = f"sdb-reader {release}"
html_sidebars = {
    "**": [
        "sidebar/brand.html",
        "sidebar/search.html",
        "sidebar/scroll-start.html",
        "sidebar/navigation.html",
        "sidebar/versions.html",
        "sidebar/scroll-end.html",
    ]
}
html_show_sphinx = False
html_copy_source = False
html_show_sourcelink = False


def _links_for_the_site(app: Any, docname: str, source: list[str]) -> None:  # noqa: ARG001
    source[0] = for_site(source[0], docname=docname, repository=REPOSITORY, ref=REF)


def _no_signature_for_an_enumeration(
    app: Any,  # noqa: ARG001
    what: str,
    name: str,  # noqa: ARG001
    obj: Any,
    options: Any,  # noqa: ARG001
    signature: str | None,
    return_annotation: str | None,
) -> tuple[str | None, str | None] | None:
    """An enumeration is not called with values; its members say what it is."""
    if what == "class" and isinstance(obj, type) and issubclass(obj, Enum):
        return "", None
    return signature, return_annotation


def setup(app: Any) -> None:
    app.connect("autodoc-process-signature", _no_signature_for_an_enumeration)
    app.connect("source-read", _links_for_the_site)
    # GitHub draws a ```mermaid block as a diagram. The site shows its text:
    # drawing it needs a script of some megabytes, fetched from another
    # server on every visit or carried along. Without this line the block's
    # unknown language is a warning, and a warning fails the build.
    app.add_lexer("mermaid", TextLexer)
