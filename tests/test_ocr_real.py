"""Text recognition with the real program, not a stand-in.

Every other test of a scanned sheet replaces ``tesseract``. This one runs it,
so that a change in how the program is called, or in what the reader makes of
its output, shows up before a user's scan does.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pymupdf
import pytest

from sdb_reader import (
    DocumentKind,
    extract_pdf_text,
    extraction_from_dict,
    extraction_to_dict,
    read_sheet,
    reading_to_dict,
)

SHEET = """Sicherheitsdatenblatt
gemäß Verordnung (EG) Nr. 1907/2006
ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
Handelsname: Musterreiniger
ABSCHNITT 2: Mögliche Gefahren
Signalwort: Achtung
H315 Verursacht Hautreizungen.
"""

# Locally a machine may lack the program; CI installs it and must run this.
pytestmark = [
    pytest.mark.real_tesseract,
    pytest.mark.skipif(
        shutil.which("tesseract") is None and not os.environ.get("CI"),
        reason="tesseract is not installed on this machine",
    ),
]


def _scan(path: Path) -> Path:
    """A PDF whose only page is a picture of the sheet: no text layer."""
    with pymupdf.open() as written:
        written.new_page().insert_text((72, 90), SHEET, fontsize=13)
        picture = written[0].get_pixmap(dpi=200)
    with pymupdf.open() as scanned:
        page = scanned.new_page()
        page.insert_image(page.rect, pixmap=picture)
        scanned.save(path)
    return path


@pytest.mark.spec("SDB-46", "SDB-116")
def test_a_scanned_sheet_is_read_by_the_real_program(tmp_path: Path) -> None:
    path = _scan(tmp_path / "scan.pdf")
    with pymupdf.open(path) as document:
        assert document[0].get_text().strip() == ""

    extraction = extract_pdf_text(path)

    assert extraction.extractor == "pymupdf+ocr"
    # The program's version goes with the text it read, and into what is
    # stored and printed (SDB-116).
    version = extraction.metadata["tesseract"]
    assert isinstance(version, str)
    assert int(version.split(".")[0]) >= 5
    assert extraction_to_dict(extraction)["tesseract"] == version
    assert (
        extraction_from_dict(extraction_to_dict(extraction)).metadata["tesseract"]
        == version
    )
    assert "Sicherheitsdatenblatt" in extraction.text
    assert "H315" in extraction.text

    reading = read_sheet(path)
    assert reading_to_dict(reading)["extraction"]["tesseract"] == version

    assert reading.verification.kind is DocumentKind.SAFETY_DATA_SHEET
    assert reading.parser_result is not None
    assert reading.parser_result.sheet.hazard_statements.hazard_codes == ["H315"]
