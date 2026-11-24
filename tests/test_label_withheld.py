"""Labels the reading does not give (SDB-216, SDB-217, BIB-26, SDW-49).

Every sheet here is invented.
"""

from __future__ import annotations

import pytest

from sdb_reader import (
    SheetDuty,
    extraction_from_dict,
    read_extraction,
    reading_to_dict,
    sheet_duty,
    sheet_findings,
)
from sdb_reader.reading import SheetReading


def _sheet(
    revised: str, label: str, classification: str = "Skin Irrit. 2, H315"
) -> str:
    return (
        "Sicherheitsdatenblatt\n"
        "gemäß Verordnung (EG) Nr. 1907/2006\n"
        f"Überarbeitet am: {revised}    Version: 2\n"
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
        "Handelsname: Musterreiniger\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        f"2.1 Einstufung des Stoffs oder Gemischs\n{classification}\n"
        f"2.2 Kennzeichnungselemente\n{label}\n"
        "2.3 Sonstige Gefahren\nKeine bekannt.\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
    )


COMPLETE = (
    "Gefahrenpiktogramme: GHS07\nSignalwort: Achtung\nH315 Verursacht Hautreizungen."
)
WITHOUT_SIGNAL_WORD = "Gefahrenpiktogramme: GHS07\nH315 Verursacht Hautreizungen."


def _read(text: str, *, accept: bool = False) -> SheetReading:
    return read_extraction(
        extraction_from_dict(
            {"text": text, "extractor": "pymupdf", "pages_sampled": 1, "warnings": []}
        ),
        accept_incomplete_label=accept,
    )


@pytest.mark.spec("SDB-216")
@pytest.mark.parametrize("revised", ["31.05.2017", "12.03.2015"])
def test_a_sheet_of_the_rules_before_june_2017_has_no_label(revised: str) -> None:
    reading = _read(_sheet(revised, COMPLETE))
    assert reading.parser_result is not None
    sheet = reading.parser_result.sheet

    assert sheet.label_withheld == "before-2017-06"
    assert sheet.hazard_statements.hazard_codes == []
    assert sheet.product_identifier == "Musterreiniger"
    assert reading.errors == []


@pytest.mark.spec("SDB-216")
def test_a_sheet_classified_under_the_old_directives_has_no_label() -> None:
    reading = _read(
        _sheet("", "Xi Reizend\nR38 Reizt die Haut.", "Xi; R38 Reizt die Haut.")
    )
    assert reading.parser_result is not None

    assert reading.parser_result.sheet.label_withheld == "before-2017-06"


@pytest.mark.spec("SDB-216")
def test_a_sheet_from_june_2017_has_its_label() -> None:
    reading = _read(_sheet("01.06.2017", COMPLETE))
    assert reading.parser_result is not None
    sheet = reading.parser_result.sheet

    assert sheet.label_withheld is None
    assert sheet.hazard_statements.hazard_codes == ["H315"]


@pytest.mark.spec("SDB-217", "BIB-26")
def test_an_incomplete_label_is_withheld_with_an_error() -> None:
    reading = _read(_sheet("01.03.2024", WITHOUT_SIGNAL_WORD))
    assert reading.parser_result is not None
    sheet = reading.parser_result.sheet

    assert [(e.code, dict(e.params)) for e in reading.errors] == [
        ("label-incomplete", {"findings": "signal-word-not-found"})
    ]
    assert sheet.label_withheld == "incomplete"
    assert sheet.hazard_statements.hazard_codes == []


@pytest.mark.spec("SDB-217", "BIB-26")
def test_asked_for_it_the_label_is_given_as_printed_with_its_findings() -> None:
    reading = _read(_sheet("01.03.2024", WITHOUT_SIGNAL_WORD), accept=True)
    assert reading.parser_result is not None
    parsed = reading.parser_result

    assert reading.errors == []
    assert parsed.sheet.hazard_statements.hazard_codes == ["H315"]
    assert "signal-word-not-found" in [
        f.code for f in sheet_findings(parsed.sheet, parsed.warnings)
    ]


@pytest.mark.spec("SDB-217")
def test_a_complete_label_is_given() -> None:
    reading = _read(_sheet("01.03.2024", COMPLETE))
    assert reading.parser_result is not None

    assert reading.errors == []
    assert reading.parser_result.sheet.hazard_statements.hazard_codes == ["H315"]


@pytest.mark.spec("SDW-49", "SDB-216")
def test_a_withheld_label_gets_only_the_findings_on_its_age() -> None:
    reading = _read(_sheet("12.03.2015", WITHOUT_SIGNAL_WORD))
    assert reading.parser_result is not None
    parsed = reading.parser_result

    assert [f.code for f in sheet_findings(parsed.sheet, parsed.warnings)] == [
        "predates-annex-ii"
    ]


@pytest.mark.spec("SDB-218")
@pytest.mark.parametrize(
    "classification", ["Skin Irrit. 2, H315", "Das Gemisch ist nicht eingestuft."]
)
def test_an_old_sheet_is_not_checked_whatever_section_2_says(
    classification: str,
) -> None:
    reading = _read(_sheet("12.03.2015", COMPLETE, classification))
    assert reading.parser_result is not None

    assert sheet_duty(reading.parser_result.sheet) is SheetDuty.NOT_CHECKED
    assert reading_to_dict(reading)["sheet"]["sheet_duty"] == "not-checked"


@pytest.mark.spec("SDB-218")
def test_an_incomplete_label_leaves_the_classification_of_section_2() -> None:
    classified = _read(_sheet("01.06.2024", WITHOUT_SIGNAL_WORD))
    unclassified = _read(
        _sheet("01.06.2024", WITHOUT_SIGNAL_WORD, "Das Gemisch ist nicht eingestuft.")
    )
    assert classified.parser_result is not None
    assert unclassified.parser_result is not None

    assert sheet_duty(classified.parser_result.sheet) is SheetDuty.REQUIRED
    assert sheet_duty(unclassified.parser_result.sheet) is SheetDuty.NOT_CHECKED
