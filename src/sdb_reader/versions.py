"""The versions of the library's two stages (BIB-4).

A caller that keeps texts or readings compares these with what it stored:
a text read at another ``extraction_stage()`` is read from the PDF again, a
reading made at another ``PARSER_VERSION`` is made again from the text.

Whoever changes a stage's code decides here; tests/test_stage_versions.py
asks (BIB-5).
"""

from __future__ import annotations

import pymupdf

# Raise when the same PDF can give another text: extraction.py, layout.py,
# line_breaks.py.
EXTRACTION_VERSION = 2

# Raise when the same text can give another reading: the verdict, the parser,
# the statements and their tables, the findings, the message codes, the JSON
# form. The sentences of the catalogs are no part of a reading.
PARSER_VERSION = 16


def extraction_stage() -> str:
    """The reading stage a text comes from: its version and the PDF library's.

    The text of a PDF depends on both, so a stored text holds for one value of
    this and no other.
    """
    return f"{EXTRACTION_VERSION}+pymupdf-{pymupdf.__version__}"
