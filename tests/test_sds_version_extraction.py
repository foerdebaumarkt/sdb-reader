"""Test version number extraction from SDS documents."""

import pytest

from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import SDSParser


@pytest.fixture
def parser() -> SDSParser:
    return SDSParser(language="de")


def test_version_extraction_from_german_sds(parser: SDSParser) -> None:
    """Version should be extracted from German SDS format 'Version X.Y'."""
    extraction_text = """ABSCHNITT 1: Bezeichnung des Stoffs
Handelsname: Beispielprodukt

ABSCHNITT 2: Mögliche Gefahren
Version 3.3 Überarbeitet am : 20.02.2025
Signalwort: Achtung
H315 Verursacht Hautreizungen
P264 Nach Gebrauch Hände gründlich waschen
"""

    extraction = ExtractionResult(
        text=extraction_text,
        raw_text=extraction_text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )

    result = parser.parse(extraction)
    assert result.sheet.version == "3.3"


def test_version_extraction_without_version(parser: SDSParser) -> None:
    """Version should be None when not present in text."""
    extraction_text = """ABSCHNITT 1: Bezeichnung des Stoffs
Handelsname: Beispielprodukt

ABSCHNITT 2: Mögliche Gefahren
Signalwort: Achtung
H315 Verursacht Hautreizungen
"""

    extraction = ExtractionResult(
        text=extraction_text,
        raw_text=extraction_text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )

    result = parser.parse(extraction)
    assert result.sheet.version is None


def test_version_extraction_multipart(parser: SDSParser) -> None:
    """Version with multiple parts should be extracted correctly."""
    extraction_text = """ABSCHNITT 1: Bezeichnung des Stoffs
Handelsname: Beispielprodukt

ABSCHNITT 2: Mögliche Gefahren
Version 2.5.1 Überarbeitet am : 10.01.2024
H315 Verursacht Hautreizungen
"""

    extraction = ExtractionResult(
        text=extraction_text,
        raw_text=extraction_text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )

    result = parser.parse(extraction)
    assert result.sheet.version == "2.5.1"
