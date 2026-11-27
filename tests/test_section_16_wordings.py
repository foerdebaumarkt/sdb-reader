"""Sentences from section 16 for codes the label names without one (SDB-222),
and rows of codes that have their sentences elsewhere (SDB-52).

Every text here is invented.
"""

from __future__ import annotations

import re

import pytest

from sdb_reader import sheet_from_dict, sheet_to_dict, with_section_16
from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import ParsedSheet, SDSParser
from sdb_reader.statements import codes_without_wording


def _extraction(label: str, section_16: str, classification: str) -> ExtractionResult:
    text = (
        "Sicherheitsdatenblatt\n"
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
        "1.1 Produktidentifikator\nHandelsname: Musterpaste\n"
        "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
        "Musterwerk GmbH\nHafenstraße 4\n20457 Hamburg\nTelefon: +49 40 5550123\n"
        "1.4 Notrufnummer\nGiftnotruf Musterstadt: +49 30 5550100\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        f"2.1 Einstufung des Stoffs oder Gemischs\n{classification}"
        f"{label}"
        "2.3 Sonstige Gefahren\nKeine bekannt.\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
        "ABSCHNITT 16: Sonstige Angaben\n"
        f"{section_16}"
        "Legende:\nADR Europäisches Übereinkommen über die Beförderung\n"
    )
    return ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )


def _parsed(
    label: str,
    section_16: str,
    classification: str = "STOT RE 2, H373\n",
) -> ParsedSheet:
    return SDSParser(language="de").parse(
        _extraction(label, section_16, classification)
    )


CODES_ONLY = (
    "2.2 Kennzeichnungselemente\n"
    "Signalwort: Achtung\n"
    "Gefahrenhinweise: H373 (Blut), EUH210, EUH401\n"
    "Sicherheitshinweise: P102, P314, P405, P501\n"
    "* Wortlaut der H- und P-Sätze siehe Abschnitt 16.\n"
)
WORDED_IN_16 = (
    "Wortlaut der Sätze:\n"
    "H373: Kann die Organe schädigen bei längerer oder wiederholter Exposition.\n"
    "EUH210: Sicherheitsdatenblatt auf Anfrage erhältlich.\n"
    "P102: Darf nicht in die Hände von Kindern gelangen.\n"
    "P314: Bei Unwohlsein ärztlichen Rat einholen/ärztliche Hilfe hinzuziehen.\n"
    "P501: Inhalt/Behälter mit Restanhaftungen gemäß örtlicher Vorschriften der\n"
    "Entsorgung zuführen.\n"
)


@pytest.mark.spec("SDB-222")
def test_codes_without_a_sentence_get_the_one_section_16_prints() -> None:
    label = _parsed(CODES_ONLY, WORDED_IN_16).sheet.hazard_statements
    assert label.section_16_wordings == {
        "EUH210": "Sicherheitsdatenblatt auf Anfrage erhältlich.",
        "P102": "Darf nicht in die Hände von Kindern gelangen.",
        "P314": "Bei Unwohlsein ärztlichen Rat einholen/ärztliche Hilfe hinzuziehen.",
        "P501": (
            "Inhalt/Behälter mit Restanhaftungen gemäß örtlicher Vorschriften der "
            "Entsorgung zuführen."
        ),
    }
    # The statement texts stay as the label prints them.
    assert label.precautionary_text == "P102, P314, P405, P501"


@pytest.mark.spec("SDB-222")
def test_with_section_16_gives_each_code_its_line() -> None:
    label = _parsed(CODES_ONLY, WORDED_IN_16).sheet.hazard_statements
    assert with_section_16(label.precautionary_text, label.section_16_wordings) == (
        "P102: Darf nicht in die Hände von Kindern gelangen.\n"
        "P314: Bei Unwohlsein ärztlichen Rat einholen/ärztliche Hilfe hinzuziehen.\n"
        "P405\n"
        "P501: Inhalt/Behälter mit Restanhaftungen gemäß örtlicher Vorschriften "
        "der Entsorgung zuführen."
    )
    assert with_section_16(label.supplemental_text, label.section_16_wordings) == (
        "EUH210: Sicherheitsdatenblatt auf Anfrage erhältlich.\nEUH401"
    )


@pytest.mark.spec("SDB-222")
def test_a_code_with_its_sentence_on_the_label_is_not_looked_up() -> None:
    label = _parsed(
        "2.2 Kennzeichnungselemente\n"
        "Signalwort: Achtung\n"
        "Gefahrenhinweise:\n"
        "H373 Kann die Organe schädigen bei längerer oder wiederholter Exposition.\n"
        "Sicherheitshinweise:\n"
        "P102 Darf nicht in die Hände von Kindern gelangen.\n",
        WORDED_IN_16,
    ).sheet.hazard_statements
    assert label.section_16_wordings == {}
    assert with_section_16(label.precautionary_text, {"P102": "Anders."}) == (
        label.precautionary_text
    )


@pytest.mark.spec("SDB-222")
def test_a_combination_needs_the_same_combination_in_section_16() -> None:
    label = _parsed(
        "2.2 Kennzeichnungselemente\n"
        "Signalwort: Achtung\n"
        "Gefahrenhinweise: H373\n"
        "Sicherheitshinweise: P102, P305+P351+P338, P333+P313\n",
        "P102: Darf nicht in die Hände von Kindern gelangen.\n"
        "P305+P351+P338: BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang behutsam\n"
        "mit Wasser spülen. Eventuell vorhandene Kontaktlinsen nach Möglichkeit\n"
        "entfernen. Weiter spülen.\n"
        "P333: Bei Hautreizung oder -ausschlag:\n",
    ).sheet.hazard_statements
    assert set(label.section_16_wordings) == {"P102", "P305+P351+P338"}


@pytest.mark.spec("SDB-222")
def test_what_a_table_leaves_under_a_code_is_no_sentence() -> None:
    label = _parsed(
        "2.2 Kennzeichnungselemente\n"
        "Signalwort: Achtung\n"
        "Gefahrenhinweise: H373\n"
        "Sicherheitshinweise: P102\n",
        "H373 Berechnungsverfahren.\n",
    ).sheet.hazard_statements
    assert "H373" not in label.section_16_wordings


@pytest.mark.spec("SDB-222")
def test_without_section_16_a_code_stays_alone() -> None:
    label = _parsed(CODES_ONLY, "").sheet.hazard_statements
    assert label.section_16_wordings == {}
    assert with_section_16("P102, P501", {}) == "P102, P501"


@pytest.mark.spec("SDB-222")
def test_codes_without_wording_counts_a_combination_as_a_sentence() -> None:
    assert codes_without_wording(
        "H302\nH332\nH302+H332: Gesundheitsschädlich bei Verschlucken oder Einatmen.\n"
        "H314-H335\nP102, P501:"
    ) == ["H314", "H335", "P102", "P501"]
    assert codes_without_wording(None) == []


@pytest.mark.spec("SDB-222")
def test_a_stored_reading_keeps_the_section_16_wordings() -> None:
    extraction = _extraction(CODES_ONLY, WORDED_IN_16, "STOT RE 2, H373\n")
    stored = sheet_to_dict(SDSParser(language="de").parse(extraction).sheet, extraction)
    wordings = stored["hazard_statements"]["section_16_wordings"]
    assert wordings["P102"] == "Darf nicht in die Hände von Kindern gelangen."
    assert sheet_from_dict(stored).hazard_statements.section_16_wordings == wordings
    del stored["hazard_statements"]["section_16_wordings"]
    assert sheet_from_dict(stored).hazard_statements.section_16_wordings == {}


@pytest.mark.spec("SDB-52")
def test_a_row_from_2_1_goes_where_a_combination_carries_its_code() -> None:
    label = _parsed(
        "2.2 Kennzeichnungselemente\n"
        "Signalwort: Gefahr\n"
        "Gefahrenhinweise:\n"
        "H314 - Verursacht schwere Verätzungen der Haut und schwere Augenschäden.\n"
        "H302+H332 - Gesundheitsschädlich bei Verschlucken oder Einatmen.\n",
        "",
        classification=(
            "Akute Toxizität (oral), Kategorie 4\nH302\n"
            "Verätzung/Reizung der Haut, Kategorie 1A\nH314\n"
            "Schwere Augenschädigung, Kategorie 1\nH318\n"
        ),
    ).sheet.hazard_statements
    assert label.hazard_text == (
        "H314 - Verursacht schwere Verätzungen der Haut und schwere Augenschäden.\n"
        "H302+H332 - Gesundheitsschädlich bei Verschlucken oder Einatmen."
    )
    assert label.section_16_wordings == {}


@pytest.mark.spec("SDB-222")
def test_h360_and_h361_take_the_sentence_of_their_own_effect() -> None:
    label = _parsed(
        "2.2 Kennzeichnungselemente\n"
        "Signalwort: Gefahr\n"
        "Gefahrenhinweise: H361d, H373.\n",
        "H361f Kann vermutlich die Fruchtbarkeit beeinträchtigen.\n"
        "H361d Kann vermutlich das Kind im Mutterleib schädigen.\n"
        "H373 Kann die Organe schädigen bei längerer oder wiederholter Exposition.\n",
        classification="Repr. 2, H361d\nSTOT RE 2, H373\n",
    ).sheet.hazard_statements
    assert label.section_16_wordings["H361d"] == (
        "Kann vermutlich das Kind im Mutterleib schädigen."
    )
    assert "H373" in label.section_16_wordings


@pytest.mark.spec("SDB-222")
@pytest.mark.parametrize(
    "row",
    [
        "P102, P314, P405, P501.",
        "P102 / P314 / P405 / P501",
        "P102, P314, P405 und P501",
        "H361d, H373",
        "H314-H335:",
    ],
)
def test_every_form_of_a_row_is_without_a_sentence(row: str) -> None:
    assert codes_without_wording(row) == [
        code for code in re.findall(r"[HP]\d{3}d?", row)
    ]


@pytest.mark.spec("SDB-222")
def test_text_behind_a_code_counts_as_its_sentence() -> None:
    assert codes_without_wording("H373 (Blut)") == []


@pytest.mark.spec("SDB-222")
def test_a_code_with_its_sentence_elsewhere_leaves_the_row() -> None:
    assert with_section_16(
        "P102, P501\nP501: Inhalt/Behälter einer Entsorgung zuführen.",
        {"P102": "Darf nicht in die Hände von Kindern gelangen."},
    ) == (
        "P102: Darf nicht in die Hände von Kindern gelangen.\n"
        "P501: Inhalt/Behälter einer Entsorgung zuführen."
    )


@pytest.mark.spec("SDB-52")
def test_a_single_code_left_of_a_row_goes_where_it_has_its_sentence() -> None:
    label = _parsed(
        "2.2 Kennzeichnungselemente\n"
        "Signalwort: Gefahr\n"
        "Gefahrenhinweise:\n"
        "H314 - Verursacht schwere Verätzungen der Haut und schwere Augenschäden.\n",
        "",
        classification=(
            "Verätzung/Reizung der Haut, Kategorie 1A\nH314\n"
            "Schwere Augenschädigung, Kategorie 1\nH318\n"
        ),
    ).sheet.hazard_statements
    assert label.hazard_text == (
        "H314 - Verursacht schwere Verätzungen der Haut und schwere Augenschäden."
    )


@pytest.mark.spec("SDB-52")
def test_a_row_goes_where_its_code_has_text_behind_it() -> None:
    label = _parsed(
        "2.2 Kennzeichnungselemente\n"
        "Signalwort: Achtung\n"
        "Gefahrenhinweise:\n"
        "H373 (Blut)\n",
        "",
        classification="Spezifische Zielorgan-Toxizität, Kategorie 2\nH373\n",
    ).sheet.hazard_statements
    assert label.hazard_text == "H373 (Blut)"
