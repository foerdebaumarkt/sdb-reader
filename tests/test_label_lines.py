"""Lines of the label the parser assigns to nothing (SDB-165), and P501 by
its disposal sentence (SDB-166).

Every text here is invented.
"""

from __future__ import annotations

import pytest

from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import LABEL_LINE_UNASSIGNED, ParsedSheet, SDSParser


def _parsed(label: str) -> ParsedSheet:
    text = (
        "Sicherheitsdatenblatt\n"
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
        "1.1 Produktidentifikator\nHandelsname: Musterkleber\n"
        "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
        "Musterwerk GmbH\nHafenstraße 4\n20457 Hamburg\nTelefon: +49 40 5550123\n"
        "1.4 Notrufnummer\nGiftnotruf Musterstadt: +49 30 5550100\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        "2.1 Einstufung des Stoffs oder Gemischs\nSkin Irrit. 2, H315\n"
        f"{label}"
        "2.3 Sonstige Gefahren\nKeine bekannt.\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
    )
    extraction = ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )
    return SDSParser(language="de").parse(extraction)


def _unassigned(parsed: ParsedSheet) -> list[str]:
    return [
        m.params["line"] for m in parsed.warnings if m.code == LABEL_LINE_UNASSIGNED
    ]


FULL_LABEL = (
    "2.2 Kennzeichnungselemente\n"
    "Kennzeichnung gemäß Verordnung (EG) Nr. 1272/2008\n"
    "Gefahrenpiktogramme\n"
    "GHS07\n"
    "Signalwort: Achtung\n"
    "Gefahrenhinweise:\n"
    "H315 Verursacht\n"
    "Hautreizungen.\n"
    "Sicherheitshinweise:\n"
    "P280 Schutzhandschuhe tragen.\n"
    "P302+P352 BEI BERÜHRUNG MIT DER HAUT: Mit viel Wasser\n"
    "waschen.\n"
    "Gefahrbestimmende Komponenten zur Etikettierung:\n"
    "Musterharz\n"
    "Ergänzende Gefahrenmerkmale: nicht anwendbar\n"
    "Tastbarer Warnhinweis: Nicht anwendbar.\n"
)


@pytest.mark.spec("SDB-165")
def test_a_label_the_parser_reads_whole_leaves_no_line() -> None:
    assert _unassigned(_parsed(FULL_LABEL)) == []


@pytest.mark.spec("SDB-165")
def test_a_sentence_of_the_suppliers_own_is_named() -> None:
    parsed = _parsed(FULL_LABEL + "Nur für den Gebrauch durch Erwachsene.\n")
    assert _unassigned(parsed) == ["Nur für den Gebrauch durch Erwachsene."]


@pytest.mark.spec("SDB-165")
def test_a_statement_in_words_the_parser_does_not_know_is_named() -> None:
    line = "Beim Streichen Fenster weit öffnen."
    parsed = _parsed(FULL_LABEL + line + "\n")
    assert _unassigned(parsed) == [line]
    # The reading is what it was: the line is named, never read.
    assert parsed.sheet.hazard_statements.precautionary_codes == [
        "P280",
        "P302",
        "P352",
    ]


@pytest.mark.spec("SDB-165")
def test_page_numbers_and_empty_lines_are_not_named() -> None:
    parsed = _parsed(FULL_LABEL + "\nSeite 2 von 9\n   \n")
    assert _unassigned(parsed) == []


@pytest.mark.spec("SDB-165")
def test_a_declaration_about_the_label_is_not_named() -> None:
    parsed = _parsed(
        FULL_LABEL
        + "Das Gemisch ist gemäß CLP-Verordnung eingestuft und gekennzeichnet.\n"
    )
    assert _unassigned(parsed) == []


@pytest.mark.spec("SDB-165")
def test_the_message_carries_the_line_and_says_it_in_both_languages() -> None:
    from sdb_reader import shipped_catalog

    parsed = _parsed(FULL_LABEL + "Nur für den Gebrauch durch Erwachsene.\n")
    message = next(m for m in parsed.warnings if m.code == LABEL_LINE_UNASSIGNED)
    assert message.params == {"line": "Nur für den Gebrauch durch Erwachsene."}
    for language in ("de", "en"):
        assert "Nur für den Gebrauch durch Erwachsene." in shipped_catalog(
            language
        ).render(message)


def _codes_and_text(parsed: ParsedSheet) -> tuple[list[str], str | None]:
    hazards = parsed.sheet.hazard_statements
    return hazards.precautionary_codes, hazards.precautionary_text


@pytest.mark.spec("SDB-166")
def test_the_disposal_sentence_beside_other_codes_is_p501() -> None:
    parsed = _parsed(
        FULL_LABEL
        + "Zusätzliche Sätze: Inhalt/Behälter gemäß den örtlichen Vorschriften entsorgen.\n"
    )
    codes, text = _codes_and_text(parsed)
    assert codes == ["P280", "P302", "P352", "P501"]
    assert text is not None
    assert text.endswith(
        "P501 Inhalt/Behälter gemäß den örtlichen Vorschriften entsorgen."
    )
    assert _unassigned(parsed) == []


@pytest.mark.spec("SDB-166")
def test_the_sentence_over_two_lines_with_und() -> None:
    parsed = _parsed(
        FULL_LABEL
        + "Entsorgung: Inhalt und Behälter in Übereinstimmung mit den örtlichen\n"
        + "Vorschriften entsorgen.\n"
    )
    codes, _ = _codes_and_text(parsed)
    assert "P501" in codes


@pytest.mark.spec("SDB-166")
def test_a_printed_p501_is_not_read_twice() -> None:
    parsed = _parsed(
        FULL_LABEL
        + "P501 Inhalt/Behälter einer zugelassenen Entsorgungsanlage zuführen.\n"
        + "Inhalt/Behälter gemäß den örtlichen Vorschriften entsorgen.\n"
    )
    codes, text = _codes_and_text(parsed)
    assert codes.count("P501") == 1
    assert text is not None and text.count("P501") == 1


@pytest.mark.spec("SDB-166")
def test_empty_containers_in_the_household_waste_are_no_p501() -> None:
    parsed = _parsed(
        FULL_LABEL + "Leere Behälter können über den Hausmüll entsorgt werden.\n"
    )
    codes, _ = _codes_and_text(parsed)
    assert "P501" not in codes


@pytest.mark.spec("SDB-166")
def test_a_label_without_a_hazard_statement_gets_no_p501() -> None:
    parsed = _parsed(
        "2.2 Kennzeichnungselemente\n"
        "Kennzeichnung gemäß Verordnung (EG) Nr. 1272/2008: entfällt\n"
        "Inhalt/Behälter gemäß den örtlichen Vorschriften entsorgen.\n"
    )
    codes, _ = _codes_and_text(parsed)
    assert "P501" not in codes
