"""What the reading leaves out of a text no sheet prints (SDB-167, SDB-168)."""

from __future__ import annotations

import pytest

from sdb_reader import read_extraction
from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import MAX_STATEMENT_LINES
from sdb_reader.reading import MAX_LINE_CHARACTERS, SheetReading

SHEET = (
    "Sicherheitsdatenblatt\n"
    "gemäß Verordnung (EG) Nr. 1907/2006\n"
    "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
    "1.1 Produktidentifikator\nHandelsname: Musterkleber\n"
    "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
    "Musterwerk GmbH\nHafenstraße 4\n20457 Hamburg\nTelefon: +49 40 5550123\n"
    "1.4 Notrufnummer\nGiftnotruf Musterstadt: +49 30 5550100\n"
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.1 Einstufung des Stoffs oder Gemischs\nSkin Irrit. 2, H315\n"
    "2.2 Kennzeichnungselemente\n"
    "Gefahrenpiktogramme\nGHS07\nSignalwort\nAchtung\n"
    "{label}"
    "Gefahrenhinweise\nH315 Verursacht Hautreizungen.\n"
    "Sicherheitshinweise\n{precautions}"
    "2.3 Sonstige Gefahren\nKeine bekannt.\n"
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
    "ABSCHNITT 16: Sonstige Angaben\nÜberarbeitet am: 01.02.2025\n"
)


def _read(
    label: str = "", precautions: str = "P280 Schutzhandschuhe tragen.\n"
) -> tuple[ExtractionResult, SheetReading]:
    text = SHEET.format(label=label, precautions=precautions)
    extraction = ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )
    return extraction, read_extraction(extraction)


def _messages(reading: SheetReading, code: str) -> list[dict[str, object]]:
    assert reading.parser_result is not None
    return [dict(m.params) for m in reading.parser_result.warnings if m.code == code]


@pytest.mark.spec("SDB-167")
def test_a_line_longer_than_a_sheet_prints_is_not_read_and_named() -> None:
    long = "-" * (MAX_LINE_CHARACTERS + 1)
    extraction, reading = _read(label=f"{long}\n{long}x\n")
    _, plain = _read()
    assert _messages(reading, "line-too-long") == [
        {"count": 2, "length": MAX_LINE_CHARACTERS + 2}
    ]
    assert reading.parser_result is not None
    assert plain.parser_result is not None
    assert reading.parser_result.sheet.hazard_statements == (
        plain.parser_result.sheet.hazard_statements
    )
    # The text as read stays as it was, to be kept and read again.
    assert reading.extraction is extraction
    assert long in reading.extraction.text


@pytest.mark.spec("SDB-167")
def test_a_line_as_long_as_the_limit_is_read() -> None:
    _, reading = _read(label="-" * MAX_LINE_CHARACTERS + "\n")
    assert _messages(reading, "line-too-long") == []


@pytest.mark.spec("SDB-168")
def test_a_statement_ends_after_its_last_line_and_is_named() -> None:
    lines = "".join(f"weiter {n}\n" for n in range(MAX_STATEMENT_LINES + 20))
    _, reading = _read(
        precautions=f"P280 Schutzhandschuhe\n{lines}P102 Darf nicht in die Hände von Kindern gelangen.\n"
    )
    assert reading.parser_result is not None
    statements = reading.parser_result.sheet.hazard_statements
    assert _messages(reading, "statement-too-long") == [{"codes": "P280"}]
    text = statements.precautionary_text or ""
    # The statement and the 99 lines that make its 100; nothing after them.
    assert f"weiter {MAX_STATEMENT_LINES - 2}" in text
    assert f"weiter {MAX_STATEMENT_LINES - 1}" not in text
    # The next code begins a statement again.
    assert "P102" in statements.precautionary_codes
    assert "Darf nicht in die Hände von Kindern gelangen." in text


@pytest.mark.spec("SDB-168")
def test_a_statement_of_as_many_lines_as_it_may_take_is_whole() -> None:
    lines = "".join(f"weiter {n}\n" for n in range(MAX_STATEMENT_LINES - 1))
    _, reading = _read(precautions=f"P280 Schutzhandschuhe\n{lines}")
    assert _messages(reading, "statement-too-long") == []
    assert reading.parser_result is not None
    text = reading.parser_result.sheet.hazard_statements.precautionary_text or ""
    assert f"weiter {MAX_STATEMENT_LINES - 2}" in text
