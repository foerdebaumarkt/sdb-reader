"""The versions of the library's three stages (BIB-4).

A caller that keeps texts or readings compares these with what it stored:
a text read at another ``extraction_stage()`` is read from the PDF again, so
are the pictograms found at another ``label_images_stage()``, and a reading
made at another ``PARSER_VERSION`` is made again from the text and the
pictograms.

Whoever changes a stage's code decides here; tests/test_stage_versions.py
asks (BIB-5).
"""

from __future__ import annotations

import pymupdf

# Raise when the same PDF can give another text: extraction.py, layout.py,
# line_breaks.py.
EXTRACTION_VERSION = 2

# Raise when the same PDF can give other pictograms from the drawing of its
# label: label_images.py, label_blocks.py and pictogram_references.json
# (SDB-179, SDB-188).
LABEL_IMAGES_VERSION = 2

# Raise when the same text can give another reading: the verdict, the parser,
# the statements and their tables, the findings, the message codes, the JSON
# form, and the heading of a small package's label (label_blocks.py). The
# sentences of the catalogs are no part of a reading.
PARSER_VERSION = 25


def extraction_stage() -> str:
    """The reading stage a text comes from: its version and the PDF library's.

    The text of a PDF depends on both, so a stored text holds for one value of
    this and no other.
    """
    return f"{EXTRACTION_VERSION}+pymupdf-{pymupdf.__version__}"


def label_images_stage() -> str:
    """The stage the pictograms found in a label's drawing come from: its
    version and the PDF library's, which draws the page (SDB-179)."""
    return f"{LABEL_IMAGES_VERSION}+pymupdf-{pymupdf.__version__}"
