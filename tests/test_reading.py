"""Reading one file: the library's entry point."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdb_reader import reading
from sdb_reader.extraction import ExtractionError, ExtractionResult
from sdb_reader.label_images import LabelImages, LabelImagesStatus
from sdb_reader.messages import Message
from sdb_reader.verification import DocumentKind


def _extraction(text: str) -> ExtractionResult:
    return ExtractionResult(
        text=text,
        raw_text=text,
        extractor="stub",
        pages_sampled=1,
        warnings=[],
        metadata={"character_count": len(text)},
    )


SHEET = (
    "SICHERHEITSDATENBLATT gemäß Verordnung (EG) Nr. 1907/2006\n"
    "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
    "1.1 Produktidentifikator\nHandelsname: Beispiel\n"
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.2 Kennzeichnungselemente\nSignalwort: Achtung\n"
    "H315 Verursacht Hautreizungen.\n"
    "P280 Schutzhandschuhe tragen.\n"
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
    "Verordnung (EG) Nr. 1272/2008\n"
) * 3


def test_a_sheet_is_read_judged_and_parsed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(reading, "extract_pdf_text", lambda *a, **k: _extraction(SHEET))
    monkeypatch.setattr(
        reading,
        "read_label_images",
        lambda *a, **k: LabelImages("stage", LabelImagesStatus.NO_LABEL),
    )

    result = reading.read_sheet(tmp_path / "a.pdf")

    assert result.verification.kind is DocumentKind.SAFETY_DATA_SHEET
    assert result.parser_result is not None
    assert "H315" in result.parser_result.sheet.hazard_statements.hazard_codes
    assert result.errors == []
    # Storing is the caller's: reading leaves the directory as it found it.
    assert list(tmp_path.iterdir()) == []


def test_an_unreadable_file_is_no_sheet_and_says_why(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def unreadable(*args: object, **kwargs: object) -> ExtractionResult:
        raise ExtractionError(Message("pdf-not-found"))

    monkeypatch.setattr(reading, "extract_pdf_text", unreadable)

    result = reading.read_sheet(tmp_path / "a.pdf")

    assert result.verification.kind is DocumentKind.DOCUMENT
    assert result.extraction is None
    assert result.parser_result is None
    assert result.errors == [Message("pdf-not-found")]
    assert result.warnings == [Message("unreadable")]
