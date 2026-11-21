"""Whether the label prints a statement's code or the parser assigned it (SDB-174).

Every text here is invented.
"""

from __future__ import annotations

from typing import Any

import pytest

from sdb_reader import as_printed, label_statements, sheet_from_dict, sheet_to_dict
from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import ParsedSheet, SDSParser


def _extraction(label: str, classification: str) -> ExtractionResult:
    text = (
        "Sicherheitsdatenblatt\n"
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
        "1.1 Produktidentifikator\nHandelsname: Musterkleber\n"
        "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
        "Musterwerk GmbH\nHafenstraße 4\n20457 Hamburg\nTelefon: +49 40 5550123\n"
        "1.4 Notrufnummer\nGiftnotruf Musterstadt: +49 30 5550100\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        f"2.1 Einstufung des Stoffs oder Gemischs\n{classification}"
        f"{label}"
        "2.3 Sonstige Gefahren\nKeine bekannt.\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
    )
    return ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )


def _parsed(label: str, classification: str = "Skin Irrit. 2, H315\n") -> ParsedSheet:
    return SDSParser(language="de").parse(_extraction(label, classification))


def _stored(label: str) -> dict[str, Any]:
    extraction = _extraction(label, "Skin Irrit. 2, H315\n")
    return sheet_to_dict(SDSParser(language="de").parse(extraction).sheet, extraction)


PRINTED_CODES = (
    "2.2 Kennzeichnungselemente\n"
    "Signalwort: Achtung\n"
    "Gefahrenhinweise:\n"
    "H315 Verursacht Hautreizungen.\n"
    "Sicherheitshinweise:\n"
    "P280 Schutzhandschuhe tragen.\n"
)


def _sources(parsed: ParsedSheet) -> dict[str, str]:
    return {
        s.code: s.code_source for s in label_statements(parsed.sheet.hazard_statements)
    }


@pytest.mark.spec("SDB-174")
def test_printed_codes_are_printed() -> None:
    parsed = _parsed(PRINTED_CODES)
    assert parsed.sheet.hazard_statements.codes_from_wording == []
    assert _sources(parsed) == {"H315": "printed", "P280": "printed"}


@pytest.mark.spec("SDB-174")
def test_the_disposal_sentence_gives_p501_from_its_wording() -> None:
    parsed = _parsed(
        PRINTED_CODES
        + "Zusätzliche Sätze: Inhalt/Behälter gemäß den örtlichen Vorschriften entsorgen.\n"
    )
    label = parsed.sheet.hazard_statements
    assert "P501" in label.precautionary_codes
    assert label.codes_from_wording == ["P501"]
    assert _sources(parsed)["P501"] == "from_wording"
    assert _sources(parsed)["P280"] == "printed"
    printed = as_printed(label.precautionary_text, label.codes_from_wording)
    assert printed is not None
    assert "P501" not in printed
    assert printed.endswith(
        "Inhalt/Behälter gemäß den örtlichen Vorschriften entsorgen."
    )
    assert printed.startswith("P280")


@pytest.mark.spec("SDB-174")
def test_a_label_of_sentences_only_has_every_code_from_its_wording() -> None:
    parsed = _parsed(
        "2.2 Kennzeichnungselemente\n"
        "Gefahrenhinweise:\n"
        "Verursacht Hautreizungen.\n"
        "Sicherheitshinweise:\n"
        "Darf nicht in die Hände von Kindern gelangen.\n"
    )
    label = parsed.sheet.hazard_statements
    assert label.hazard_codes == ["H315"]
    assert "P102" in label.precautionary_codes
    assert set(label.codes_from_wording) == {"H315", *label.precautionary_codes}
    assert set(_sources(parsed).values()) == {"from_wording"}
    assert as_printed(label.hazard_text, label.codes_from_wording) == (
        "Verursacht Hautreizungen."
    )


@pytest.mark.spec("SDB-174")
def test_an_euh_sentence_without_its_code_is_from_its_wording() -> None:
    parsed = _parsed(
        PRINTED_CODES + "Enthält Musterol. Kann allergische Reaktionen hervorrufen.\n"
    )
    label = parsed.sheet.hazard_statements
    assert label.supplemental_codes == ["EUH208"]
    assert label.codes_from_wording == ["EUH208"]
    assert as_printed(label.supplemental_text, label.codes_from_wording) == (
        "Enthält Musterol. Kann allergische Reaktionen hervorrufen."
    )


@pytest.mark.spec("SDB-174")
def test_a_printed_euh_code_is_printed() -> None:
    parsed = _parsed(
        PRINTED_CODES
        + "EUH208 Enthält Musterol. Kann allergische Reaktionen hervorrufen.\n"
    )
    label = parsed.sheet.hazard_statements
    assert label.supplemental_codes == ["EUH208"]
    assert label.codes_from_wording == []


@pytest.mark.spec("SDB-174")
def test_the_code_lists_keep_both_kinds() -> None:
    with_sentence = _parsed(
        PRINTED_CODES
        + "Zusätzliche Sätze: Inhalt/Behälter gemäß den örtlichen Vorschriften entsorgen.\n"
    )
    with_code = _parsed(
        PRINTED_CODES
        + "P501 Inhalt/Behälter gemäß den örtlichen Vorschriften entsorgen.\n"
    )
    assert (
        with_sentence.sheet.hazard_statements.precautionary_codes
        == with_code.sheet.hazard_statements.precautionary_codes
    )
    assert with_code.sheet.hazard_statements.codes_from_wording == []


@pytest.mark.spec("SDB-174")
def test_a_stored_reading_keeps_the_codes_from_wording() -> None:
    stored = _stored(
        PRINTED_CODES
        + "Zusätzliche Sätze: Inhalt/Behälter gemäß den örtlichen Vorschriften entsorgen.\n"
    )
    assert stored["hazard_statements"]["codes_from_wording"] == ["P501"]
    assert sheet_from_dict(stored).hazard_statements.codes_from_wording == ["P501"]


@pytest.mark.spec("SDB-174")
def test_a_reading_stored_before_reads_back_with_none() -> None:
    stored = _stored(PRINTED_CODES)
    del stored["hazard_statements"]["codes_from_wording"]
    assert sheet_from_dict(stored).hazard_statements.codes_from_wording == []


@pytest.mark.spec("SDB-174")
def test_as_printed_leaves_a_combination_with_a_printed_part() -> None:
    text = "P305+P351+P338: BEI KONTAKT MIT DEN AUGEN: Behutsam spülen."
    assert as_printed(text, ["P338"]) == text
    assert as_printed(text, ["P305", "P351", "P338"]) == (
        "BEI KONTAKT MIT DEN AUGEN: Behutsam spülen."
    )


@pytest.mark.spec("SDB-174")
def test_as_printed_without_assigned_codes_changes_nothing() -> None:
    assert as_printed("H315: Verursacht Hautreizungen.", []) == (
        "H315: Verursacht Hautreizungen."
    )
    assert as_printed(None, ["H315"]) is None


@pytest.mark.spec("SDW-43")
def test_the_record_names_each_codes_source() -> None:
    from sdb_reader import read_extraction, reading_to_dict

    extraction = _extraction(
        PRINTED_CODES
        + "Zusätzliche Sätze: Inhalt/Behälter gemäß den örtlichen Vorschriften entsorgen.\n",
        "Skin Irrit. 2, H315\n",
    )
    record = reading_to_dict(read_extraction(extraction))
    sources = {s["code"]: s["code_source"] for s in record["statements"]}
    assert sources == {"H315": "printed", "P280": "printed", "P501": "from_wording"}
    assert record["sheet"]["hazard_statements"]["codes_from_wording"] == ["P501"]
