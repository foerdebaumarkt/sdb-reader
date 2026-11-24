from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from sdb_reader.compliance import Classification, classification
from sdb_reader.expected import clp_expected
from sdb_reader.extraction import ExtractionResult
from sdb_reader.messages import Message
from sdb_reader.parser import (
    CLASSIFICATION_ENTRY,
    HAZARD_CODE_PATTERN,
    PLAIN_DATE_PATTERN,
    UNLABELLED_PATTERN,
    SDSParser,
    _extract_date_below_label,
    _extract_date_from_columns,
    _extract_issue_date,
    _extract_month_year_date,
    _extract_revision_date,
    _extract_short_year_date,
    _extract_version,
    _latest_dated_match,
    _parts_with_labels,
    find_label_section,
    old_classification,
    read_numbered_section_heading,
    read_signal_word,
    sheet_countries,
    split_into_sheets,
    split_sections,
    stated_classification,
    states_undetermined_labelling,
)
from sdb_reader.schema import (
    ContactInfo,
    HazardStatements,
    Section,
    StatedClassification,
)


def _build_extraction(text: str) -> ExtractionResult:
    return ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )


def _labels(text: str) -> list[str]:
    """Section 2.2 of every sheet *text* holds."""
    return [label for _, label in _parts_with_labels(text) if label is not None]


@pytest.fixture
def parser() -> SDSParser:
    return SDSParser()


def test_parser_extracts_key_fields(parser: SDSParser) -> None:
    extraction = _build_extraction(
        """ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
Produktname: Bad- und Küchenfarbe
Firma: Erlen-Farben GmbH
Straße: Musterstraße 1
12345 Musterstadt
Telefon: +49 40 153467
Notrufnummer: +49 40 987654
E-Mail: info@erlen.example

ABSCHNITT 2: Mögliche Gefahren
Version 3.3
Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006
2.2 Kennzeichnungselemente
H412: Schädlich für Wasserorganismen, mit langfristiger Wirkung.
P101: Ist ärztlicher Rat erforderlich, Verpackung oder Kennzeichnungsetikett bereithalten.
P102: Darf nicht in die Hände von Kindern gelangen.
P103: Vor Gebrauch Kennzeichnungsetikett lesen.
EUH208: Enthält Reaktionsmasse.
"""
    )

    result = parser.parse(extraction)
    sheet = result.sheet

    assert sheet.product_identifier == "Bad- und Küchenfarbe"
    assert "H412" in sheet.hazard_statements.hazard_codes
    assert {"P101", "P102", "P103"}.issubset(
        set(sheet.hazard_statements.precautionary_codes)
    )
    assert sheet.hazard_statements.hazard_text is not None
    assert "H412" in sheet.hazard_statements.hazard_text
    assert sheet.hazard_statements.precautionary_text is not None
    assert "P101" in sheet.hazard_statements.precautionary_text
    assert sheet.hazard_statements.supplemental_text is not None
    assert "EUH" in sheet.hazard_statements.supplemental_text
    assert sheet.contact_info.supplier_name == "Erlen-Farben GmbH"
    assert sheet.contact_info.supplier_phone is not None
    assert sheet.contact_info.supplier_phone.startswith("+49")
    assert sheet.contact_info.emergency_phone is not None
    assert sheet.contact_info.emergency_phone.startswith("+49")
    assert Section.IDENTIFICATION in sheet.section_text
    assert Section.HAZARDS in sheet.section_text
    assert result.warnings == []


def test_parser_handles_non_sds_document(parser: SDSParser) -> None:
    extraction = _build_extraction(
        """ABSCHNITT 1: Produktinformation
Produktname: Werbeprospekt Frühjahr
Firma: Erlen-Farben GmbH
Telefon: +49 40 153467
Notrufnummer: +49 40 987654

ABSCHNITT 2: Hinweise
Dieses Dokument enthält keine Gefahrstoffkennzeichnung.
"""
    )

    result = parser.parse(extraction)

    assert result.sheet.hazard_statements.hazard_codes == []
    assert result.sheet.hazard_statements.precautionary_codes == []
    assert result.sheet.hazard_statements.hazard_text is None
    assert result.sheet.hazard_statements.precautionary_text is None
    assert result.sheet.hazard_statements.supplemental_text is None
    assert Message("no-hazard-codes") in result.warnings


def test_parser_ignores_statements_from_other_sections(parser: SDSParser) -> None:
    extraction_text = """ABSCHNITT 1: Allgemeine Angaben
Produktname: Beispielprodukt

ABSCHNITT 2: Gefahrenbeschreibung
H200: Instabil explodierend
P210: Von Hitze fernhalten

ABSCHNITT 3: Zusammensetzung
P999: Nicht relevanter Hinweis
EUH001: Explosiv in trockener Form
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

    hazard_text = result.sheet.hazard_statements.hazard_text
    precaution_text = result.sheet.hazard_statements.precautionary_text
    supplemental_text = result.sheet.hazard_statements.supplemental_text

    assert hazard_text == "H200: Instabil explodierend"
    assert precaution_text == "P210: Von Hitze fernhalten"
    # EUH001 appears outside the hazards section and should be ignored
    assert supplemental_text is None


def test_extract_version_accepts_the_forms_suppliers_actually_use() -> None:
    """Real sheets write this four different ways.

    The pattern previously required whitespace after "Version", so the common
    "Version: 1.1" form -- and the German compounds -- never matched.
    """
    assert _extract_version("Version\n8.2 Überarbeitet am :") == "8.2"
    assert _extract_version("Ausgabedatum: 17.08.2021 Version: 1.1") == "1.1"
    assert _extract_version("Versionsnummer 1") == "1"
    assert _extract_version("Nummer der Fassung: 1.0") == "1.0"
    assert _extract_version("no version here") is None


@pytest.mark.spec("SDB-20")
def test_extract_version_prefers_the_repeated_running_header() -> None:
    """Section 16 lists superseded versions once each.

    The document's own version is the one repeated in the page footer, so a
    single mention must not outvote it.
    """
    text = "Version: 1.2\n" * 12 + "Ersetzt Fassung: 1.1\n"
    assert _extract_version(text) == "1.2"


@pytest.mark.spec("SDB-90")
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mit AGM und GEL Technologie\nSTAND: 06/2022\n", date(2022, 6, 1)),
        ("____________ Stand: Februar 2003\n\n1. STOFF", date(2003, 2, 1)),
        # Behind the revision label.
        ("Version: 2.0/CZ\nÜberarbeitet am: März 2013\nDruckdatum:", date(2013, 3, 1)),
        ("Überarbeitet am: April/2017\nDruckdatum: 18. Oktober", date(2017, 4, 1)),
        # In a footer, without a colon and with a dot.
        ("Seite 1/4\nStand 10.2013\n5. Massnahmen", date(2013, 10, 1)),
        # One supplier: alone on a line of the page header.
        ("ISO 11014 – 1)\n03 / 2012 .\nName: Spray", date(2012, 3, 1)),
        # The newest of several.
        ("Stand: 01/2019\nStand: 11/2020\n", date(2020, 11, 1)),
        # The number of a regulation is no date.
        ("Verordnung Nr. 8/1985 Slg. über", None),
        ("graničnim vrijednostima (NN 1/2021)", None),
        ("Stand: Technik 2020", None),
    ],
)
def test_a_month_and_a_year_date_a_sheet(text: str, expected: date | None) -> None:
    assert _extract_month_year_date(text) == expected


@pytest.mark.spec("SDB-90")
class TestAHeaderTableSetInColumns:
    """The values of the header table come before their labels."""

    def test_the_date_at_its_labels_place(self) -> None:
        text = (
            "EU, CH, NO\n02.01.2013\n08.04.2020\nV21 DE\n"
            "Muster Mausefalle\nGültigkeitsraum\nErstfassung\nÜberarbeitet am\n"
            "Version\n\n01 BEZEICHNUNG DES STOFFES"
        )
        assert _extract_date_from_columns(text) == date(2020, 4, 8)

    def test_one_date_for_two_labels_is_nobodys(self) -> None:
        text = "08.04.2020\nV21 DE\nErstfassung\nÜberarbeitet am\nVersion\n"
        assert _extract_date_from_columns(text) is None

    def test_a_first_issue_alone_is_no_revision(self) -> None:
        assert _extract_date_from_columns("02.01.2013\nV1\nErstfassung\n") is None

    def test_values_too_far_above_are_not_the_tables(self) -> None:
        text = (
            "02.01.2013\n08.04.2020\n"
            + "Zeile\n" * 16
            + "Erstfassung\nÜberarbeitet am\n"
        )
        assert _extract_date_from_columns(text) is None


@pytest.mark.spec("SDB-57")
def test_the_date_of_the_first_version_is_an_issue_date() -> None:
    text = "Nummer der Fassung: 1.0 Erste Fassung: 15.12.2025\nDeutschland: de Seite: 1 / 21"
    assert _extract_issue_date(text) == date(2025, 12, 15)
    assert _extract_revision_date(text) is None
    # The label alone, its value elsewhere, is left to SDB-90.
    assert _extract_issue_date("Erstfassung\nÜberarbeitet am\nVersion") is None


@pytest.mark.spec("SDB-57")
def test_the_date_of_issue_spelled_out() -> None:
    text = "Datum der Ausstellung: 5/05/2022\nDruckdatum: 05/05/2022"
    assert _extract_issue_date(text) == date(2022, 5, 5)


@pytest.mark.spec("SDB-57")
def test_a_revision_date_with_its_label_behind_it() -> None:
    text = (
        "Verursacht Hautreizungen.\n\n23.04.2024 (Überarbeitungsdatum)\nDE - de\n1/11"
    )
    assert _extract_revision_date(text) == date(2024, 4, 23)
    assert _extract_revision_date("28.02.2022 (Druckdatum)") is None


@pytest.mark.spec("SDB-57")
def test_a_date_with_its_version_behind_a_comma() -> None:
    text = "Sicherheitsdatenblatt\nINSEKTENSPRAY 150 mL.\n\n20/11/2012, version 2.\n"
    assert _extract_revision_date(text) == date(2012, 11, 20)


@pytest.mark.spec("SDB-57", "SDB-90")
def test_issued_on_labels_a_date() -> None:
    assert _extract_issue_date("Ausgestellt am 05.12.2016") == date(2016, 12, 5)
    assert _extract_short_year_date("- Ausgestellt am 05.12.16\n") == date(2016, 12, 5)


@pytest.mark.spec("SDB-57")
def test_the_date_of_a_review_not_of_the_version_it_replaces() -> None:
    text = (
        "Durchsicht Nr. 3\nvom 11/10/2023\nGedruckt am 11/10/2023\nYtong FIX N202\n"
        "Ersetzt die überarbeitete Fassung:2\n(vom: 23/06/2023)\n"
    )
    assert _extract_revision_date(text) == date(2023, 10, 11)
    assert _extract_revision_date(text.split("Gedruckt")[1]) is None


@pytest.mark.spec("SDB-90")
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Two complete cells between the label and its date.
        (
            "Überarbeitet am:\nArtikel-Nr.: 2297PR\nSeite 1 von 6\n17.07.2020\n12511",
            date(2020, 7, 17),
        ),
        # Another label without its value: the date may be that one's.
        ("überarbeitet am:\nDruckdatum:\n14.10.2020", None),
        ("Überarbeitet am:\n\n17.07.2020", None),
        # Too far below.
        ("Überarbeitet am:\na\nb\nc\n17.07.2020", None),
        # A placeholder is no date.
        ("Überarbeitet am\n00.00.0000\nPorenstein", None),
    ],
)
def test_a_revision_date_a_few_lines_below_its_label(
    text: str, expected: date | None
) -> None:
    assert _extract_date_below_label(text) == expected


@pytest.mark.spec("SDB-57")
def test_a_date_with_spaces_around_its_separators() -> None:
    text = "Durchgesehene Ausgabe Nr : 0\nDatum : 15 / 6 / 2010\n\nErsetzt : 0 / 0 / 0"
    assert _latest_dated_match(text, PLAIN_DATE_PATTERN) == date(2010, 6, 15)


def test_extract_revision_date() -> None:
    assert _extract_revision_date("Überarbeitet am: 16.11.2020") == date(2020, 11, 16)
    assert _extract_revision_date("Revisionsdatum 02.03.2021") == date(2021, 3, 2)
    assert _extract_revision_date("Druckdatum: 18.02.2015") is None


@pytest.mark.spec("SDB-20")
@pytest.mark.parametrize(
    "text",
    [
        "Ausgabedatum/Überarbeitungsd\natum:\n27.04.2020",
        # The same label read in print order, its two lines joined (SDB-43).
        "Ausgabedatum/Überarbeitungsd atum: 27.04.2020",
    ],
)
def test_a_label_broken_inside_its_word_still_dates_the_sheet(text: str) -> None:
    """One sheet prints the label right-aligned over two lines."""
    assert _extract_revision_date(text) == date(2020, 4, 27)


@pytest.mark.spec("SDB-20")
@pytest.mark.parametrize(
    "text",
    [
        "Überarbeitet Druckdatum: 13.07.2018",
        "Überarbeitungsdatum ersetzt 12.03.2019",
        "Überarbeitet\nDruckdatum: 13.07.2018",
    ],
)
def test_a_word_after_the_label_is_not_the_rest_of_it(text: str) -> None:
    assert _extract_revision_date(text) is None


def test_extract_revision_date_ignores_impossible_dates() -> None:
    assert _extract_revision_date("Überarbeitet am: 32.13.2020") is None


def test_version_falls_back_to_a_revision_number() -> None:
    """Some sheets number revisions instead of versions.

    "Rev. Nr. 4" and "Revisionsnummer 1" are the document's own count when no
    Version label is present, so they stand in for it -- but only then.
    """
    assert _extract_version("Rev. Nr. 4") == "4"
    assert _extract_version("Revisionsnummer 1") == "1"
    assert _extract_version("Ausgabenr. : 15.01") == "15.01"


def test_a_real_version_outranks_a_revision_number() -> None:
    text = "Version: 2.1\nVersion: 2.1\nRevisionsnummer 7\n"
    assert _extract_version(text) == "2.1"


def test_version_ignores_the_ghs_revision_and_bare_prose() -> None:
    """ "Fassung: GHS 1.0" is the GHS revision, not this document's version."""
    assert _extract_version("Fassung: GHS 1.0") is None
    assert _extract_version("... in der Fassung. Weitere Angaben") is None
    assert _extract_version("Version vom: 04-Jan-2024") is None


def test_revision_date_reads_dashed_month_names_day_first() -> None:
    """ "23-Nov-2023" is day-first like 23.11.2023, only punctuated differently."""
    assert _extract_revision_date("Überarbeitet am 23-Nov-2023") == date(2023, 11, 23)
    assert _extract_revision_date("Änderungsdatum: 11.11.2020") == date(2020, 11, 11)
    assert _extract_revision_date("Version vom: 04-Jan-2024") == date(2024, 1, 4)


@pytest.mark.spec("SDB-20")
def test_revision_date_takes_the_latest_when_labels_conflict() -> None:
    """Section 16 lists superseded revisions; the newest describes this sheet."""
    text = "Überarbeitet am 23-Nov-2023\nversion vom: 04-Jan-2024\n"
    assert _extract_revision_date(text) == date(2024, 1, 4)


def test_issue_date_is_separate_from_the_revision_date() -> None:
    assert _extract_issue_date("Ausstellungsdatum: 11.07.2013") == date(2013, 7, 11)
    assert _extract_issue_date("Ausgabedatum: 17.08.2021") == date(2021, 8, 17)
    assert _extract_issue_date("Überarbeitet am: 16.11.2020") is None
    assert _extract_revision_date("Ausstellungsdatum: 11.07.2013") is None


def test_revision_date_reads_spelled_out_german_months() -> None:
    """ "5.März.2024" and "17.Juli.2024" appear alongside the abbreviations."""
    assert _extract_revision_date("Überarbeitet am: 5.März.2024") == date(2024, 3, 5)
    assert _extract_revision_date("Änderungsdatum 17.Juli.2024") == date(2024, 7, 17)
    assert _extract_revision_date("Revisionsdatum: 19.September.2021") == date(
        2021, 9, 19
    )


def test_bare_rev_number_counts_as_a_version() -> None:
    """ "REV. 1 vom 14.11.2019" carries both signals in one line."""
    assert _extract_version("REV. 1 vom 14.11.2019") == "1"
    assert _extract_revision_date("REV. 1 vom 14.11.2019") == date(2019, 11, 14)


def test_a_real_version_still_outranks_a_bare_rev() -> None:
    assert _extract_version("Version: 2.1 und Rev. 9") == "2.1"


def test_datum_der_erstellung_is_an_issue_date() -> None:
    assert _extract_issue_date("Datum der Erstellung: 29.05.2020") == date(2020, 5, 29)


def test_version_accepts_a_v_prefix_and_dash_separator() -> None:
    """ "Versionsnummer: V01-02" is 01.02.

    The same supplier writes "2.01" on a later sheet, so the dash is a
    separator and the V a prefix -- and 01.02 sorts below 2.01, as it should.
    """
    assert _extract_version("Versionsnummer: V01-02") == "01.02"


@pytest.mark.spec("SDB-20")
def test_superseded_version_does_not_win() -> None:
    """ "2.01 (ersetzt Version 1.03)" repeats in the footer, so both numbers
    occur equally often and frequency alone cannot separate them."""
    line = "Versionsnummer: 2.01 (ersetzt Version 1.03)\n"
    assert _extract_version(line * 18) == "2.01"
    assert _extract_version("Versionsnummer der Vorgängerversion: 1.03") is None


def test_revisions_nr_is_the_current_version_not_the_superseded_one() -> None:
    """ "Revisions-Nr.: 1,2 - Ersetzt die Version 1,1" states both numbers.

    Without the "Revisions-Nr." label the only match was the superseded 1,1,
    so the document reported the wrong version.
    """
    assert _extract_version("Revisions-Nr.: 1,2 - Ersetzt die Version 1,1") == "1.2"


def test_superseded_marker_needs_a_word_boundary() -> None:
    """Without \\b the "alte" branch fires inside "enthalten"."""
    assert _extract_version("... enthalten Version: 3.1") == "3.1"
    assert _extract_version("Verhalten. Version: 3.1") == "3.1"


# ---------------------------------------------------------------------------
# Section 2.2 (Kennzeichnungselemente) as the source for label statements
# ---------------------------------------------------------------------------


_TWO_SECTION_SHEET = """ABSCHNITT 2: Mögliche Gefahren
2.1 Einstufung des Stoffs oder Gemischs
Akut Tox. 4, H302
Augenschäden 1, H318
Gewässergefährdend akut 1, H400
Gewässergefährdend chronisch 1, H410
2.2 Kennzeichnungselemente
Signalwort: Gefahr
H302: Gesundheitsschädlich bei Verschlucken.
H318: Verursacht schwere Augenschäden.
H410: Sehr giftig für Wasserorganismen, mit langfristiger Wirkung.
P280: Schutzhandschuhe tragen.
2.3 Sonstige Gefahren
Keine weiteren Gefahren bekannt.
"""


@pytest.mark.spec("SDB-5")
def test_label_codes_exclude_classification_only_statements(
    parser: SDSParser,
) -> None:
    """H400 sits in 2.1 but not on the label, so it must not be reported."""
    result = parser.parse(_build_extraction(_TWO_SECTION_SHEET))

    assert result.sheet.hazard_statements.hazard_codes == ["H302", "H318", "H410"]
    assert "H400" not in result.sheet.hazard_statements.hazard_codes


@pytest.mark.spec("SDB-10")
def test_statement_text_leaves_out_what_only_the_classification_says(
    parser: SDSParser,
) -> None:
    """The text is cut from all of section 2, so 2.1 reaches it as well."""
    hazard_text = parser.parse(
        _build_extraction(_TWO_SECTION_SHEET)
    ).sheet.hazard_statements.hazard_text

    assert hazard_text is not None
    assert set(HAZARD_CODE_PATTERN.findall(hazard_text)) == {"H302", "H318", "H410"}


@pytest.mark.spec("SDB-10")
def test_an_unlabelled_product_shows_no_statements_from_its_ingredients(
    parser: SDSParser,
) -> None:
    """Section 2 holds statements the label does not carry, and they stay off.

    Here the ingredient table, as it reached section 2 of a filler
    while the heading of section 3 went unread. The label carries no code and
    the model found none, and the output showed "Lebensgefahr bei Einatmen"
    for a product that is not classified.
    """
    text = (
        "ABSCHNITT 2: Mögliche Gefahren\n"
        "2.1 Einstufung des Stoffs oder Gemischs\n"
        "Nicht eingestuft.\n"
        "2.2 Kennzeichnungselemente\n"
        "Signalwort : Kein Signalwort.\n"
        "Gefahrenhinweise : Keine besonderen Wirkungen oder Gefahren bekannt.\n"
        "P501 - Inhalt/Behälter gemäß lokalen/ nationalen Vorschriften der "
        "Entsorgung zuführen.\n"
        "2.3 Sonstige Gefahren\n"
        "Keine bekannt.\n"
        "C(M)IT/MIT(3:1) CAS: 55965-84-9 <0.001\n"
        "Acute Tox. 3, H301\n"
        "Acute Tox. 2, H330\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
    )

    hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

    assert hazards.hazard_codes == []
    assert hazards.hazard_text is None
    assert hazards.precautionary_text is not None


@pytest.mark.spec("SDB-10")
def test_a_combined_statement_stays_when_the_label_carries_all_its_codes(
    parser: SDSParser,
) -> None:
    text = (
        "2.2 Kennzeichnungselemente\n"
        "Signalwort: Gefahr\n"
        "H300+H310+H330: Lebensgefahr bei Verschlucken, Hautkontakt oder "
        "Einatmen.\n"
        "2.3 Sonstige Gefahren\n"
    )

    hazard_text = parser.parse(
        _build_extraction(text)
    ).sheet.hazard_statements.hazard_text

    assert hazard_text is not None
    assert hazard_text.startswith("H300+H310+H330: Lebensgefahr bei Verschlucken")


def _pages(text: str, pages: int) -> ExtractionResult:
    return dataclasses.replace(_build_extraction(text), pages_sampled=pages)


_RUNNING_HEADER = (
    "SICHERHEITSDATENBLATT\n"
    "gemäß Verordnung (EG) Nr. 1907/2006\n"
    "MUSTER Rasendünger plus Unkrautvernichter\n"
    "Version 11.0\n"
)


@pytest.mark.spec("SDB-27")
class TestWhereAStatementEnds:
    """A statement takes what follows its code until something else begins."""

    def test_a_statement_reads_past_the_page_header(self, parser: SDSParser) -> None:
        """One sheet's shape: EUH208 breaks over a page."""
        text = (
            _RUNNING_HEADER + "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "EUH208 Enthält Harnstoff-Formaldehyd-Kondensat. Kann\n"
            + _RUNNING_HEADER
            + "2 / 17\n"
            "allergische Reaktionen hervorrufen.\n"
            "2.3 Sonstige Gefahren\n"
            + _RUNNING_HEADER
            + "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
        )

        hazards = parser.parse(_pages(text, 3)).sheet.hazard_statements

        assert hazards.supplemental_text == (
            "EUH208 Enthält Harnstoff-Formaldehyd-Kondensat. Kann allergische "
            "Reaktionen hervorrufen."
        )

    def test_a_word_broken_at_the_page_is_joined(self, parser: SDSParser) -> None:
        text = (
            _RUNNING_HEADER + "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "EUH208 Enthält 1,2-Benzisothiazol-3(2H)-on. Kann allergische Reakti-\n"
            + _RUNNING_HEADER
            + "Seite 2 von 9\n"
            "onen hervorrufen.\n" + _RUNNING_HEADER
        )

        hazards = parser.parse(_pages(text, 3)).sheet.hazard_statements

        assert hazards.supplemental_text == (
            "EUH208 Enthält 1,2-Benzisothiazol-3(2H)-on. Kann allergische "
            "Reaktionen hervorrufen."
        )

    def test_a_statement_ends_at_the_next_heading_or_code(
        self, parser: SDSParser
    ) -> None:
        """One sheet's shape: EUH401 ran on into the P statements."""
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "EUH401 Zur Vermeidung von Risiken für Mensch und Umwelt ist die\n"
            "Gebrauchsanleitung einzuhalten.\n"
            "Sicherheitshinweise: P101 Ist ärztlicher Rat erforderlich,\n"
            "Verpackung oder Kennzeichnungsetikett bereithalten.\n"
            "Prävention:\n"
            "P273 Freisetzung in die Umwelt vermeiden.\n"
            "Zusätzliche Kennzeichnung\n"
            "Nicht anwendbar.\n"
            "2.3 Sonstige Gefahren\n"
            "Keine bekannt.\n"
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.supplemental_text == (
            "EUH401 Zur Vermeidung von Risiken für Mensch und Umwelt ist die "
            "Gebrauchsanleitung einzuhalten."
        )
        assert hazards.precautionary_text == (
            "P101 Ist ärztlicher Rat erforderlich, Verpackung oder "
            "Kennzeichnungsetikett bereithalten.\n"
            "P273 Freisetzung in die Umwelt vermeiden."
        )

    def test_a_statement_ends_at_a_hazard_class(self, parser: SDSParser) -> None:
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.1 Einstufung des Stoffs oder Gemischs\n"
            "H319 Verursacht schwere Augenreizung.\n"
            "Eye Irrit. 2\n"
            "H317 Kann allergische Hautreaktionen verursachen.\n"
            "Sensibilisierung der Haut, Kategorie 1\n"
            "2.2 Kennzeichnungselemente\n"
            "H317, H319\n"
            "2.3 Sonstige Gefahren\n"
        )

        hazard_text = parser.parse(
            _build_extraction(text)
        ).sheet.hazard_statements.hazard_text

        assert hazard_text is not None
        assert hazard_text.split("\n")[:2] == [
            "H319 Verursacht schwere Augenreizung.",
            "H317 Kann allergische Hautreaktionen verursachen.",
        ]

    def test_a_page_header_line_is_no_hazard_class(self, parser: SDSParser) -> None:
        """ "Version 3" at the top of the next page; the wording follows it."""
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "EUH208\n"
            "Version 3\n"
            "Enthält Lavandinöl. Kann allergische Reaktionen hervorrufen.\n"
            "2.3 Sonstige Gefahren\n"
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.supplemental_text == (
            "EUH208 Version 3 Enthält Lavandinöl. Kann allergische Reaktionen "
            "hervorrufen."
        )

    @pytest.mark.parametrize(
        "boundary",
        [
            "2.3",
            "Kindergesicherte Verschlüsse",
            "Tastbarer Warnhinweis",
            "Anhang XVII - Beschränkungen",
            "Nicht anwendbar.",
            "Langfristig (chronisch) gewässergefährdend, Kategorie 3",
            # Read in print order: the note under P102.
            "Hinweis zur Kennzeichnung",
            "Hinweise zur Kennzeichnung",
        ],
    )
    def test_a_statement_ends_at_a_boundary(
        self, parser: SDSParser, boundary: str
    ) -> None:
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "P273 Freisetzung in die Umwelt vermeiden.\n"
            f"{boundary}\n"
            "Sonst nichts.\n"
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.precautionary_text == "P273 Freisetzung in die Umwelt vermeiden."

    def test_a_continuation_note_is_read_past(self, parser: SDSParser) -> None:
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "P280 Schutzhandschuhe / Augenschutz tragen.\n"
            "(Fortsetzung auf Seite 2)\n"
            "(Fortsetzung von Seite 1)\n"
            "P501 Inhalt/Behälter der Entsorgung zuführen.\n"
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.precautionary_text == (
            "P280 Schutzhandschuhe / Augenschutz tragen.\n"
            "P501 Inhalt/Behälter der Entsorgung zuführen."
        )

    def test_a_hyphen_after_a_capital_belongs_to_the_name(
        self, parser: SDSParser
    ) -> None:
        """One sheet's shape: "2H-" at the foot of a page."""
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "EUH208 Enthält 2-Methyl-2H-\n"
            "Seite 2 von 3\n"
            "isothiazol-3-on. Kann allergische Reaktionen hervorrufen.\n"
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.supplemental_text == (
            "EUH208 Enthält 2-Methyl-2H-isothiazol-3-on. Kann allergische "
            "Reaktionen hervorrufen."
        )

    def test_a_hyphen_after_a_digit_belongs_to_the_name(
        self, parser: SDSParser
    ) -> None:
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "EUH208 Enthält 5-Chlor-2-\n"
            "Seite 2 von 3\n"
            "methyl-2H-isothiazol-3-on. Kann allergische Reaktionen hervorrufen.\n"
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.supplemental_text == (
            "EUH208 Enthält 5-Chlor-2-methyl-2H-isothiazol-3-on. Kann allergische "
            "Reaktionen hervorrufen."
        )

    def test_the_own_heading_away_from_a_page_break_ends_the_statement(
        self, parser: SDSParser
    ) -> None:
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "P501 Inhalt/Behälter der Entsorgung zuführen.\n"
            "Sicherheitshinweise\n"
            "Keine weiteren Angaben.\n"
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.precautionary_text == (
            "P501 Inhalt/Behälter der Entsorgung zuführen."
        )

    def test_the_statements_own_heading_on_the_next_page_is_read_past(
        self, parser: SDSParser
    ) -> None:
        """One sheet's shape: P210 lost "fernhalten. Nicht rauchen." to it."""
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "P210 Von Hitze, heißen Oberflächen, Funken, offenen Flammen und "
            "anderen Zündquellen\n"
            "Sicherheitshinweise\n"
            "Seite 2 von 12\n"
            "fernhalten. Nicht rauchen.\n"
            "P233 Behälter dicht verschlossen halten.\n"
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.precautionary_text == (
            "P210 Von Hitze, heißen Oberflächen, Funken, offenen Flammen und "
            "anderen Zündquellen fernhalten. Nicht rauchen.\n"
            "P233 Behälter dicht verschlossen halten."
        )

    def test_a_repeated_line_is_the_wording_until_the_statement_has_one(
        self, parser: SDSParser
    ) -> None:
        """One sheet's shape: the wording of H319 stands four times."""
        wording = "Verursacht schwere Augenreizung.\n"
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "H319\n" + wording + "2.3 Sonstige Gefahren\n"
            "ABSCHNITT 16: Sonstige Angaben\n" + wording * 3
        )

        hazards = parser.parse(_pages(text, 4)).sheet.hazard_statements

        assert hazards.hazard_text == "H319 Verursacht schwere Augenreizung."


@pytest.mark.spec("SDB-179", "BIB-25")
def test_label_codes_drive_the_expected_pictograms(parser: SDSParser) -> None:
    """H318 -> GHS05, H302 -> GHS07 (kept, acute toxicity), H410 -> GHS09; the
    text names none, so the reading has none."""
    result = parser.parse(_build_extraction(_TWO_SECTION_SHEET))

    hazards = result.sheet.hazard_statements
    assert hazards.pictograms == []
    assert clp_expected(hazards).pictograms == ["GHS05", "GHS07", "GHS09"]


@pytest.mark.spec("SDB-4")
def test_find_label_section_stops_at_the_next_heading() -> None:
    block = find_label_section(_TWO_SECTION_SHEET)

    assert block is not None
    assert "P280" in block
    assert "Keine weiteren Gefahren" not in block


def test_find_label_section_ignores_a_date_that_looks_like_a_heading() -> None:
    """ "13.10.2024" contains "3.1"; only a heading may end the block."""
    text = (
        "2.2 Kennzeichnungselemente\n"
        "Ausgabedatum: 13.10.2024\n"
        "H226: Flüssigkeit und Dampf entzündbar.\n"
        "ABSCHNITT 3: Zusammensetzung\n"
    )

    block = find_label_section(text)

    assert block is not None
    assert "H226" in block


class TestVersionNumberInTheRunningHeader:
    """A label across a page break, with "Version / 2.3" in the header between.

    The shape of a tinting paint: section 2.2 opens at the foot
    of page 1, and everything it says follows the header of page 2.
    """

    TEXT = (
        "ABSCHNITT 2: Mögliche Gefahren\n"
        "2.2 Kennzeichnungselemente\n"
        "Kennzeichnung (VERORDNUNG (EG) Nr. 1272/2008)\n"
        "\n"
        "SICHERHEITSDATENBLATT\n"
        "Version\n"
        "2.3\n"
        "Überarbeitet am:\n"
        "20.02.2025\n"
        "2 / 19\n"
        "Signalwort\n:\nAchtung\n"
        "Gefahrenhinweise\n:\nH317\nKann allergische Hautreaktionen verursachen.\n"
        "Sicherheitshinweise\n:\nP280\nSchutzhandschuhe tragen.\n"
        "2.3 Sonstige Gefahren\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
        "Acute Tox. 2; H330\n"
    )

    def test_the_label_runs_past_the_version_number(self) -> None:
        block = find_label_section(self.TEXT)

        assert block is not None
        assert "H317" in block
        assert "H330" not in block

    def test_the_product_carries_the_label(self, parser: SDSParser) -> None:
        hazards = parser.parse(_build_extraction(self.TEXT)).sheet.hazard_statements

        assert hazards.hazard_codes == ["H317"]
        assert hazards.precautionary_codes == ["P280"]
        assert hazards.signal_word == "Achtung"
        assert clp_expected(hazards).pictograms == ["GHS07"]

    def test_a_heading_with_its_title_on_the_next_line_still_ends_it(self) -> None:
        """Section 2.3 is written this way 342 times in the corpus."""
        text = (
            "2.2 Kennzeichnungselemente\n"
            "H317 Kann allergische Hautreaktionen verursachen.\n"
            "2.3\n"
            "Sonstige Gefahren\n"
            "Acute Tox. 2; H330\n"
        )

        block = find_label_section(text)

        assert block is not None
        assert "H317" in block
        assert "H330" not in block


def test_find_label_section_absent_returns_none() -> None:
    assert find_label_section("ABSCHNITT 2: Mögliche Gefahren\nH226\n") is None


@pytest.mark.spec("SDB-4")
def test_parser_warns_and_falls_back_without_a_label_section(
    parser: SDSParser,
) -> None:
    text = "ABSCHNITT 2: Mögliche Gefahren\nH226: Flüssigkeit und Dampf entzündbar.\n"

    result = parser.parse(_build_extraction(text))

    assert "H226" in result.sheet.hazard_statements.hazard_codes
    assert Message("no-label-section") in result.warnings


def _sheet(name: str, label: str) -> str:
    return (
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs\n"
        f"Handelsname\n{name}\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        f"2.2. Kennzeichnungselemente\n{label}\n"
        "2.3. Sonstige Gefahren\n"
        "ABSCHNITT 3: Zusammensetzung/ Angaben zu Bestandteilen\n"
        "Pyrethrine: Aquatic Acute 1, H400 / Aquatic Chronic 1, H410\n"
        "ABSCHNITT 16: Sonstige Angaben\n"
    )


class TestSeveralSheetsInOneDocument:
    """A combination pack ships one PDF holding every product's sheet.

    The shape of a combination pack: the insecticide's sheet
    first, the fungicide's after it, each complete from section 1 to 16.
    """

    INSEKTENSTOPP = _sheet(
        "Insektenstopp Schädlingsfrei",
        "GHS09\nH411 Giftig für Wasserorganismen, mit langfristiger Wirkung.\n"
        "P273 Freisetzung in die Umwelt vermeiden.",
    )
    PILZSTOPP = _sheet(
        "Pilzstopp Rosen-Pilzfrei",
        "GHS09\nSignalwort\nAchtung\n"
        "H410 Sehr giftig für Wasserorganismen mit langfristiger Wirkung.\n"
        "P391 Verschüttete Mengen aufnehmen.",
    )

    @pytest.mark.spec("SDB-2")
    def test_every_sheet_gives_its_label(self) -> None:
        labels = _labels(self.INSEKTENSTOPP + self.PILZSTOPP)

        assert len(labels) == 2
        assert "H411" in labels[0]
        assert "H410" not in labels[0]
        assert "H410" in labels[1]

    def test_the_first_label_is_the_one_a_single_read_finds(self) -> None:
        text = self.INSEKTENSTOPP + self.PILZSTOPP

        assert _labels(text)[0] == find_label_section(text)

    @pytest.mark.spec("SDB-2")
    def test_the_file_s_text_is_cut_into_its_sheets(self) -> None:
        text = self.INSEKTENSTOPP + self.PILZSTOPP

        sheets = split_into_sheets(text)

        assert len(sheets) == len(_labels(text)) == 2
        assert "\n".join(sheets) == text
        assert "Insektenstopp" in sheets[0]
        assert "Pilzstopp" not in sheets[0]
        assert sheets[1].startswith("ABSCHNITT 1")

    @pytest.mark.spec("SDB-2")
    def test_a_part_without_a_label_stays_with_the_sheet_before_it(self) -> None:
        change_log = "Änderungen:\nAbschnitt 1: Handelsname\nAbschnitt 3: Gehalt\n"
        cover = "ABSCHNITT 1: Übersicht\nABSCHNITT 2: Inhalt\n"

        one = split_into_sheets(self.PILZSTOPP + change_log)
        two = split_into_sheets(
            cover + self.INSEKTENSTOPP + change_log + self.PILZSTOPP
        )

        assert one == [self.PILZSTOPP + change_log]
        assert len(two) == 2
        assert two[0].startswith(cover)
        assert two[0].endswith("Abschnitt 3: Gehalt")
        assert (
            "\n".join(two) == cover + self.INSEKTENSTOPP + change_log + self.PILZSTOPP
        )

    # What the second sheet prints at the top of its first page.
    HEAD = (
        "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006\n"
        "Pilzstopp Rosen-Pilzfrei\n"
        "Überarbeitet am: 03.05.2021\n"
        "Version: 4.0\n"
    )

    @pytest.mark.spec("SDB-2")
    def test_a_later_sheet_begins_at_the_title_above_its_section_1(self) -> None:
        footer = "Seite 4/4\n"
        text = self.INSEKTENSTOPP + footer + self.HEAD + self.PILZSTOPP

        first, second = split_into_sheets(text)

        assert second.startswith("Sicherheitsdatenblatt gemäß")
        assert "Überarbeitet am: 03.05.2021" in second
        # What stands above the title is the sheet before's.
        assert first.endswith("Seite 4/4")
        assert "\n".join([first, second]) == text
        assert len(_labels(text)) == 2

    @pytest.mark.spec("SDB-2")
    def test_the_title_nearest_to_the_heading_is_the_sheet_s(self) -> None:
        footer = "Sicherheitsdatenblatt (SDB), EU\n20.07.2022 (Überarbeitungsdatum)\n"
        text = self.INSEKTENSTOPP + footer + self.HEAD + self.PILZSTOPP

        first, second = split_into_sheets(text)

        assert first.endswith("20.07.2022 (Überarbeitungsdatum)")
        assert second.startswith("Sicherheitsdatenblatt gemäß")

    @pytest.mark.spec("SDB-2")
    def test_a_title_further_up_than_a_page_s_head_is_not_the_sheet_s(self) -> None:
        lines = "".join(f"Hinweis {number}\n" for number in range(12))
        text = self.INSEKTENSTOPP + "Sicherheitsdatenblatt\n" + lines + self.PILZSTOPP

        first, second = split_into_sheets(text)

        assert second.startswith("ABSCHNITT 1")
        assert first.endswith("Hinweis 11")

    @pytest.mark.spec("SDB-2")
    def test_a_sentence_naming_the_sheet_is_no_title(self) -> None:
        note = "Änderungen sind in diesem Sicherheitsdatenblatt am Rand markiert.\n"

        _, second = split_into_sheets(self.INSEKTENSTOPP + note + self.PILZSTOPP)

        assert second.startswith("ABSCHNITT 1")

    @pytest.mark.spec("SDB-118")
    def test_each_sheet_is_also_read_on_its_own(self, parser: SDSParser) -> None:
        head = "Sicherheitsdatenblatt\nÜberarbeitet am: 20.07.2022\nVersion: 2.1\n"
        text = head + self.INSEKTENSTOPP + self.HEAD + self.PILZSTOPP

        result = parser.parse(_build_extraction(text))

        first, second = result.parts
        assert first.sheet.hazard_statements.hazard_codes == ["H411"]
        assert first.sheet.hazard_statements.signal_word is None
        assert first.sheet.revision_date == date(2022, 7, 20)
        assert first.sheet.version == "2.1"
        assert second.sheet.hazard_statements.hazard_codes == ["H410"]
        assert second.sheet.hazard_statements.precautionary_codes == ["P391"]
        assert second.sheet.hazard_statements.signal_word == "Achtung"
        assert second.sheet.revision_date == date(2021, 5, 3)
        assert second.sheet.version == "4.0"
        assert "Pilzstopp" in second.sheet.section_text[Section.IDENTIFICATION]
        assert (
            "Insektenstopp" not in (second.sheet.section_text[Section.IDENTIFICATION])
        )
        assert [part.text for part in result.parts] == split_into_sheets(text)
        # A sheet on its own is one sheet.
        for part in result.parts:
            assert not any(w.code == "several-sheets" for w in part.warnings)

    @pytest.mark.spec("SDB-118")
    def test_the_file_s_reading_is_what_it_was_without_the_single_sheets(
        self, parser: SDSParser
    ) -> None:
        text = self.INSEKTENSTOPP + self.HEAD + self.PILZSTOPP

        result = parser.parse(_build_extraction(text))

        hazards = result.sheet.hazard_statements
        assert hazards.hazard_codes == ["H410", "H411"]
        assert hazards.signal_word == "Achtung"
        # The newest date any sheet names, as before.
        assert result.sheet.revision_date == date(2021, 5, 3)
        assert Message("several-sheets", {"count": 2}) in result.warnings

    @pytest.mark.spec("SDB-118")
    def test_a_file_that_is_one_sheet_has_no_single_sheets(
        self, parser: SDSParser
    ) -> None:
        assert parser.parse(_build_extraction(self.PILZSTOPP)).parts == []

    @pytest.mark.spec("SDB-9")
    def test_the_product_carries_both_labels(self, parser: SDSParser) -> None:
        result = parser.parse(_build_extraction(self.INSEKTENSTOPP + self.PILZSTOPP))

        hazards = result.sheet.hazard_statements
        assert hazards.hazard_codes == ["H410", "H411"]
        assert hazards.precautionary_codes == ["P273", "P391"]
        assert hazards.signal_word == "Achtung"
        assert hazards.pictograms == ["GHS09"]
        assert Message("several-sheets", {"count": 2}) in result.warnings

    @pytest.mark.spec("SDB-9")
    def test_one_sheets_stated_absence_does_not_silence_the_other(
        self, parser: SDSParser
    ) -> None:
        """Read together, "Kein Signalwort" would settle the joined block first."""
        quiet = _sheet("A", "Kein Signalwort.\nH412 Schädlich für Wasserorganismen.")
        loud = _sheet("B", "Signalwort: Gefahr\nH318 Verursacht schwere Augenschäden.")

        result = parser.parse(_build_extraction(quiet + loud))

        assert result.sheet.hazard_statements.signal_word == "Gefahr"

    @pytest.mark.spec("SDB-9")
    def test_gefahr_wins_over_achtung(self, parser: SDSParser) -> None:
        first = _sheet("A", "Signalwort: Gefahr\nH318 Verursacht schwere Augenschäden.")
        second = _sheet("B", "Signalwort: Achtung\nH315 Verursacht Hautreizungen.")

        result = parser.parse(_build_extraction(first + second))

        assert result.sheet.hazard_statements.signal_word == "Gefahr"

    @pytest.mark.spec("SDB-3")
    def test_each_section_holds_both_sheets_in_document_order(self) -> None:
        sections = split_sections(self.INSEKTENSTOPP + self.PILZSTOPP)

        hazards = sections[Section.HAZARDS]
        assert hazards.index("H411") < hazards.index("H410")
        identification = sections[Section.IDENTIFICATION]
        assert identification.index("Insektenstopp") < identification.index("Pilzstopp")

    @pytest.mark.spec("SDB-2")
    def test_a_change_log_naming_section_1_is_not_a_second_sheet(
        self, parser: SDSParser
    ) -> None:
        """Section 1 headed again after section 16, but no label follows it.

        Four sheets in the corpus end that way, listing what each revision
        changed by the section it changed.
        """
        change_log = (
            "Änderungen mit Version 1.2:\n"
            "Abschnitt 1: Handelsname/Bezeichnung\n"
            "Abschnitt 3: Gehalt von Ethylenglykol\n"
        )
        text = self.PILZSTOPP + change_log

        result = parser.parse(_build_extraction(text))

        assert len(_labels(text)) == 1
        assert result.sheet.hazard_statements.hazard_codes == ["H410"]
        assert not any(w.code == "several-sheets" for w in result.warnings)


@pytest.mark.spec("SDB-61")
class TestAReferenceThatWrapsBeforeItsSection:
    """ "… ist der volle Wortlaut in" / "Abschnitt 16 zu finden."."""

    SHEET = (
        "ABSCHNITT 2: Mögliche Gefahren\n"
        "2.1 Einstufung des Stoffs oder Gemischs\n"
        "Für die in diesem Abschnitt nicht ausgeschriebenen Einstufungen ist der volle Wortlaut in\n"
        "Abschnitt 16 zu finden.\n"
        "2.2 Kennzeichnungselemente\n"
        "H318\nVerursacht schwere Augenschäden.\n"
        "2.3 Sonstige Gefahren\n"
        "ABSCHNITT 3: Zusammensetzung\n"
    )

    def test_it_opens_no_section(self) -> None:
        sections = split_sections(self.SHEET)
        assert Section.OTHER not in sections
        assert "H318" in sections[Section.HAZARDS]

    def test_the_label_is_read(self, parser: SDSParser) -> None:
        hazards = parser.parse(_build_extraction(self.SHEET)).sheet.hazard_statements
        assert hazards.hazard_text == "H318 Verursacht schwere Augenschäden."

    @pytest.mark.parametrize(
        "heading",
        [
            "ABSCHNITT 16: Sonstige Angaben",
            "Abschnitt 16",
            "ABSCHNITT 16: sonstige Angaben",
        ],
    )
    def test_a_heading_still_opens_its_section(self, heading: str) -> None:
        sections = split_sections(
            f"ABSCHNITT 2: Mögliche Gefahren\nH318\n{heading}\nÄnderungen\n"
        )
        assert sections[Section.OTHER].endswith("Änderungen")


@pytest.mark.spec("SDB-21")
class TestSectionsOnlyMoveForward:
    """A heading numbered below the section it stands in begins nothing.

    The shape of Muster Fein-Öl: section 16 closes with a change
    list, and every line of it opens "ABSCHNITT 2". Read as headings, they put
    the deleted statements back into section 2.
    """

    FEIN_OEL = (
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs\n"
        "Handelsname\nMuster Fein-Öl\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        "2.2 Kennzeichnungselemente\n"
        "P101 Ist ärztlicher Rat erforderlich, Verpackung oder "
        "Kennzeichnungsetikett bereithalten.\n"
        "2.3 Sonstige Gefahren\n"
        "ABSCHNITT 3: Zusammensetzung/ Angaben zu Bestandteilen\n"
        "Weißes Mineralöl (Erdöl)\n"
        "ABSCHNITT 16: Sonstige Angaben\n"
        "Geänderte Positionen\n"
        "ABSCHNITT 2 gelöscht: P405 Unter Verschluss aufbewahren.\n"
        "ABSCHNITT 2 gelöscht: EUH066 Wiederholter Kontakt kann zu spröder "
        "oder rissiger Haut führen.\n"
    )

    def test_a_change_list_stays_in_section_16(self) -> None:
        sections = split_sections(self.FEIN_OEL)

        assert "gelöscht" not in sections[Section.HAZARDS]
        assert "ABSCHNITT 2 gelöscht: P405" in sections[Section.OTHER]

    def test_the_deleted_statements_are_not_the_sheets(self, parser: SDSParser) -> None:
        hazards = parser.parse(_build_extraction(self.FEIN_OEL)).sheet.hazard_statements

        assert hazards.precautionary_text is not None
        assert "P101" in hazards.precautionary_text
        assert "P405" not in hazards.precautionary_text
        assert hazards.supplemental_text is None

    def test_a_cross_reference_at_a_line_start_stays_where_it_stands(self) -> None:
        text = self.FEIN_OEL.replace(
            "Geänderte Positionen\n",
            "Die Einstufung wurde nach der Berechnungsmethode (siehe\n"
            "Abschnitt 3) bestimmt; H304 entfällt.\n",
        )

        sections = split_sections(text)

        assert "H304" not in sections[Section.COMPOSITION]
        assert "H304" in sections[Section.OTHER]

    def test_a_titled_heading_after_a_reference_to_a_later_section_begins(
        self,
    ) -> None:
        """One sheet's shape: section 6 refers to section 8 at a line start."""
        text = (
            "ABSCHNITT 6: Maßnahmen bei unbeabsichtigter Freisetzung\n"
            "Persönliche Schutzausrüstung tragen. Hinweise in\n"
            "Abschnitt 8 zu geeigneten Materialien beachten.\n"
            "ABSCHNITT 7: Handhabung und Lagerung\n"
            "In kühlen Räumen lagern.\n"
            "ABSCHNITT 8: Begrenzung und Überwachung der Exposition\n"
            "Schutzhandschuhe tragen.\n"
        )

        sections = split_sections(text)

        assert sections[Section.HANDLING_STORAGE] == (
            "Handhabung und Lagerung\nIn kühlen Räumen lagern."
        )
        assert "kühlen" not in sections[Section.EXPOSURE_PPE]

    def test_headings_out_of_order_in_the_text_layer_still_begin(self) -> None:
        """One sheet's shape: a two-column layout reads "6, 8, 7, 9"."""
        text = (
            "6 Maßnahmen bei unbeabsichtigter Freisetzung\n"
            "Mechanisch aufnehmen.\n"
            "8 Begrenzung und Überwachung der Exposition\n"
            "Schutzhandschuhe tragen.\n"
            "7 Handhabung und Lagerung\n"
            "In kühlen Räumen lagern.\n"
            "9 Physikalische und chemische Eigenschaften\n"
            "Flüssig.\n"
        )

        sections = split_sections(text)

        assert sections[Section.HANDLING_STORAGE] == "In kühlen Räumen lagern."
        assert sections[Section.EXPOSURE_PPE] == "Schutzhandschuhe tragen."

    @pytest.mark.spec("SDB-2", "SDB-3")
    def test_section_1_begins_the_next_sheet_and_its_section_2(self) -> None:
        second = _sheet(
            "Pilzstopp Rosen-Pilzfrei", "H410 Sehr giftig für Wasserorganismen."
        )

        sections = split_sections(self.FEIN_OEL + second)

        hazards = sections[Section.HAZARDS]
        assert "H410" in hazards
        assert "gelöscht" not in hazards


# ---------------------------------------------------------------------------
# Signal word: read from the sheet, derived only when it says nothing
# ---------------------------------------------------------------------------


def _label(body: str) -> str:
    return f"ABSCHNITT 2: Mögliche Gefahren\n2.2 Kennzeichnungselemente\n{body}\n2.3 Sonstige Gefahren\n"


@pytest.mark.spec("SDB-176")
def test_signal_word_is_read_from_the_label(parser: SDSParser) -> None:
    result = parser.parse(
        _build_extraction(
            _label("Signalwort: Gefahr\nH318: Verursacht schwere Augenschäden.")
        )
    )

    assert result.sheet.hazard_statements.signal_word == "Gefahr"


def test_signal_word_survives_the_two_column_layout(parser: SDSParser) -> None:
    """Row labels come first, values after -- "Gefahr" must not match
    "Gefahrenhinweise" sitting above it."""
    body = (
        "Signalwort\n:\nGefahrenhinweise\n:\nAchtung\nH315: Verursacht Hautreizungen."
    )

    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word == "Achtung"


@pytest.mark.spec("SDB-176", "SDB-180", "BIB-25")
def test_stated_absence_is_not_overridden_by_the_derivation(
    parser: SDSParser,
) -> None:
    """A sheet saying "Kein Signalwort" has answered the question."""
    body = "Signalwort\n:\nKein Signalwort.\nH412: Schädlich für Wasserorganismen."

    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word is None
    assert result.sheet.hazard_statements.states_no_signal_word


@pytest.mark.spec("SDB-176", "SDB-180", "BIB-25")
def test_a_silent_label_has_no_signal_word_but_an_expected_one(
    parser: SDSParser,
) -> None:
    """The reading keeps what is printed; the word the codes call for stands
    apart."""
    body = "H318: Verursacht schwere Augenschäden."

    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word is None
    assert clp_expected(result.sheet.hazard_statements).signal_word == "Gefahr"


@pytest.mark.spec("BIB-25")
@pytest.mark.parametrize(
    ("body", "word"),
    [
        (
            "EUH440: Reichert sich in der Umwelt und in lebenden Organismen an.",
            "Gefahr",
        ),
        (
            "EUH431: Steht in dem Verdacht, endokrine Störungen zu verursachen.",
            "Achtung",
        ),
        ("EUH208: Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.", None),
    ],
)
def test_derivation_counts_the_euh_codes_that_carry_a_signal_word(
    parser: SDSParser, body: str, word: str | None
) -> None:
    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word is None
    assert clp_expected(result.sheet.hazard_statements).signal_word == word


def test_a_read_signal_word_is_no_statement_of_none(parser: SDSParser) -> None:
    result = parser.parse(
        _build_extraction(
            _label("Signalwort: Achtung\nH315: Verursacht Hautreizungen.")
        )
    )

    assert result.sheet.hazard_statements.signal_word == "Achtung"
    assert not result.sheet.hazard_statements.states_no_signal_word


def test_absence_written_as_entfaellt(parser: SDSParser) -> None:
    body = (
        "Signalwort\nentfällt\nGefahrenhinweise\nH412: Schädlich für Wasserorganismen."
    )

    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word is None
    assert result.sheet.hazard_statements.states_no_signal_word


def test_absence_written_as_a_dash(parser: SDSParser) -> None:
    body = "Signalwort (CLP) : -\nGefahrenhinweise (CLP) : H411 - Giftig für Wasserorganismen."

    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word is None


def test_absence_written_as_nicht_erforderlich(parser: SDSParser) -> None:
    body = "Signalwort nicht erforderlich\nH412: Schädlich für Wasserorganismen."

    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word is None


def test_a_dash_after_a_hazard_code_is_not_an_absence(parser: SDSParser) -> None:
    """ "H314 - Verursacht" must not read as "Signalwort -"."""
    body = "Signalwort: Gefahr\nH314 - Verursacht schwere Verätzungen."

    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word == "Gefahr"


def test_absence_wins_over_a_word_further_down(parser: SDSParser) -> None:
    """One sheet says "Signalwort entfällt" and carries "Achtung" 570
    characters later, in an unrelated statement. The one anchored to the label
    is the answer."""
    body = (
        "Signalwort\nentfällt\nGefahrenhinweise\nEUH208 Enthält Benzisothiazolinon.\n"
        + "Fülltext " * 60
        + "\nAchtung vor Verwechslung."
    )

    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word is None


@pytest.mark.spec("SDB-176")
def test_a_sheet_that_states_it_carries_no_label_at_all(parser: SDSParser) -> None:
    """No label means no signal word. Three notations, all from real sheets."""
    for stated in (
        "Keine Kennzeichnung erforderlich",
        "Der Stoff oder das Gemisch ist nicht gefährlich gemäß Verordnung "
        "(EG) Nr. 1272/2008 (CLP).",
        "Gefahrenhinweise\nNC Nicht Eingestuft",
    ):
        assert read_signal_word(stated) == (None, True), stated


def test_an_unclassified_sheet_derives_nothing_from_its_ingredients(
    parser: SDSParser,
) -> None:
    """The label says there is none; section 3 is not the product's label.

    19 sheets in the corpus say exactly this and were given "Gefahr" from
    the hazard codes of the raw materials listed further down.
    """
    body = (
        "Kein Gefahrenpiktogramm, kein Signalwort, kein(e) Gefahrenhinweis(e), "
        "kein(e) Sicherheitshinweis(e) erforderlich.\n"
        "Zusätzliche Kennzeichnung\nEUH208 Enthält 1,2-Benzisothiazol-3(2H)-on.\n"
    )

    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word is None


def test_a_classified_sheet_is_not_read_as_unlabelled(parser: SDSParser) -> None:
    """ "nicht eingestuft" is commonplace beside a class a product does not meet.

    Inside section 2.2 it means the label is empty; the guard is that nothing
    outside 2.2 is searched. A label that carries a word keeps it.
    """
    body = "Signalwort: Gefahr\nH314 Verursacht schwere Verätzungen.\n"

    result = parser.parse(_build_extraction(_label(body)))

    assert result.sheet.hazard_statements.signal_word == "Gefahr"


def test_the_label_is_found_under_any_section_number(parser: SDSParser) -> None:
    """Sheets from before the REACH restructuring number their sections 1 to 17
    and put the label at "4. Kennzeichnungselemente"."""
    text = (
        "3. Mögliche Gefahren des Produktes\n"
        "Das Produkt ist nicht gefährlich.\n"
        "4. Kennzeichnungselemente\n"
        "Das Produkt ist nach EG-Richtlinien nicht kennzeichnungspflichtig.\n"
        "5. Erste-Hilfe-Maßnahmen\n"
        "Einatmen: Für Frischluft sorgen.\n"
    )

    block = find_label_section(text)

    assert block is not None
    assert "nicht kennzeichnungspflichtig" in block
    assert "Erste-Hilfe" not in block


def test_a_heading_without_a_boundary_yields_nothing(parser: SDSParser) -> None:
    """A block with no boundary is worth less than no block.

    Sheets in that shape often have no recognisable heading after the label, and
    the block then runs to the cap and into the ingredient table -- where
    H-statements belong to the raw materials. Four sheets measured would have
    reported H304 as their label while their label says the opposite.
    """
    text = (
        "· Kennzeichnung gemäß Verordnung (EG) Nr. 1272/2008 entfällt\n"
        "· Gefahrenpiktogramme entfällt\n"
        "· Hochraffiniertes Mineralöl Asp. Tox. 1, H304 10-<25%\n"
    )

    assert find_label_section(text) is None


def test_the_numbered_heading_still_wins_when_both_are_present(
    parser: SDSParser,
) -> None:
    """The relaxed search is a fallback, not a replacement: where 2.2 exists it
    keeps its own boundary rules, including the cap."""
    text = (
        "Inhalt: Kennzeichnungselemente siehe unten\n"
        "2.2 Kennzeichnungselemente\n"
        "Signalwort: Gefahr\nH314 Verursacht Verätzungen.\n"
        "2.3 Sonstige Gefahren\n"
    )

    block = find_label_section(text)

    assert block is not None
    assert "H314" in block
    assert "siehe unten" not in block


class TestWhatSmallerLayoutsLeaveInTheLabel:
    """Three readings a larger set of sheets got wrong."""

    @pytest.mark.spec("SDB-63")
    def test_no_pictogram_above_the_signal_word_is_no_missing_signal_word(
        self, parser: SDSParser
    ) -> None:
        """The value of the row above and the label of the next: "keine" / "Signalwort"."""
        text = _label(
            "Gefahrenpiktogramme\nkeine\nSignalwort\nACHTUNG\nGefahrenhinweise\n"
            "H229 Behälter steht unter Druck: Kann bei Erwärmung bersten."
        )
        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements
        assert hazards.signal_word == "Achtung"

    @pytest.mark.spec("SDB-63")
    def test_kein_signalwort_on_one_line_still_means_none(
        self, parser: SDSParser
    ) -> None:
        text = _label(
            "Kein Signalwort\nH412 Schädlich für Wasserorganismen, mit langfristiger Wirkung."
        )
        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements
        assert hazards.signal_word is None

    @pytest.mark.spec("SDB-63", "SDB-176")
    def test_keine_under_the_signal_word_s_label_is_the_sheet_s_answer(
        self, parser: SDSParser
    ) -> None:
        """A form prints the value below its label; nothing is derived then."""
        text = _label(
            "Gefahrenpiktogramme\nkeine\nSignalwort\nkeine\nGefahrenhinweise\n"
            "H229 Behälter steht unter Druck: Kann bei Erwärmung bersten."
        )
        result = parser.parse(_build_extraction(text))
        assert result.sheet.hazard_statements.signal_word is None
        assert result.sheet.hazard_statements.states_no_signal_word

    @pytest.mark.spec("BIB-25")
    def test_h229_alone_derives_achtung_where_the_label_is_silent(
        self, parser: SDSParser
    ) -> None:
        text = _label(
            "Gefahrenhinweise\n"
            "H229 Behälter steht unter Druck: Kann bei Erwärmung bersten."
        )
        result = parser.parse(_build_extraction(text))
        assert result.sheet.hazard_statements.signal_word is None
        assert clp_expected(result.sheet.hazard_statements).signal_word == "Achtung"

    @pytest.mark.spec("SDB-64")
    @pytest.mark.spec("SDB-155")
    @pytest.mark.parametrize(
        ("sentence", "code"),
        [
            ("Kann das Kind im Mutterleib schädigen.", "H360D"),
            ("Kann die Fruchtbarkeit beeinträchtigen.", "H360F"),
            ("Kann vermutlich das Kind im Mutterleib schädigen.", "H361d"),
            ("Kann vermutlich die Fruchtbarkeit beeinträchtigen.", "H361f"),
            (
                "Kann die Fruchtbarkeit beeinträchtigen oder das Kind im "
                "Mutterleib schädigen.",
                "H360",
            ),
            (
                "Kann die Fruchtbarkeit beeinträchtigen. "
                "Kann vermutlich das Kind im Mutterleib schädigen.",
                "H360Fd",
            ),
        ],
    )
    def test_a_label_without_codes_names_the_effect_on_reproduction(
        self, parser: SDSParser, sentence: str, code: str
    ) -> None:
        """One supplier prints the sentence of H360D and no code."""
        text = _label(
            f"Signalwort: Gefahr\nGefahrenhinweise: {sentence}\n"
            "Sicherheitshinweise\nLagerung: Unter Verschluss aufbewahren."
        )
        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements
        assert hazards.hazard_codes == [code]
        assert hazards.hazard_text == f"{code} {sentence}"

    @pytest.mark.spec("SDB-65")
    @pytest.mark.parametrize(
        "entry",
        [
            "Reproduktionstoxizität: Repr. 1B (H360D)",
            "Spezifische Zielorgan-Toxizität (wiederholte Exposition): STOT RE 1 (H372)",
            "STOT RE 1 (H372)",
        ],
    )
    def test_a_classification_entry_with_its_code_in_brackets_begins_no_statement(
        self, parser: SDSParser, entry: str
    ) -> None:
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n2.1 Einstufung des Stoffs oder Gemischs\n"
            f"{entry}\n"
            "2.2 Kennzeichnungselemente\nSignalwort: Gefahr\nGefahrenhinweise\n"
            "H360D - Kann das Kind im Mutterleib schädigen.\n"
            "H372 - Schädigt die Organe (Blut) bei längerer oder wiederholter Exposition (oral).\n"
            "2.3 Sonstige Gefahren\nKeine.\n"
        )
        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements
        assert hazards.hazard_text == (
            "H360- Kann das Kind im Mutterleib schädigen.\n"
            "H372 - Schädigt die Organe (Blut) bei längerer oder wiederholter Exposition (oral)."
        )


@pytest.mark.spec("SDB-6")
class TestCodesFromTheWordingOfTheLabel:
    """A label that prints the sentences and not the codes."""

    def test_a_label_without_codes_is_read_by_its_sentences(
        self, parser: SDSParser
    ) -> None:
        text = _label(
            "Gefahrenhinweise : Giftig für Wasserorganismen mit langfristiger "
            "Wirkung.\nSicherheitshinweise : Freisetzung in die Umwelt vermeiden."
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.hazard_codes == ["H411"]
        assert hazards.precautionary_codes == ["P273"]

    def test_a_label_with_codes_gains_none_from_its_sentences(
        self, parser: SDSParser
    ) -> None:
        text = _label(
            "H411 Giftig für Wasserorganismen mit langfristiger Wirkung.\n"
            "P273 Freisetzung in die Umwelt vermeiden.\n"
            "Verursacht schwere Augenreizung."
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.hazard_codes == ["H411"]


class TestSectionBoundaryLeadingZero:
    """248 sheets here number their sections "ABSCHNITT 01" upwards."""

    LABEL = (
        "2.2 Kennzeichnungselemente\n"
        "Kennzeichnung gemäß Verordnung (EG) Nr. 1272/2008\n"
        "Gefahrenpiktogramme entfällt\n"
        "Signalwort entfällt\n"
        "Gefahrenhinweise EUH210 Sicherheitsdatenblatt auf Anfrage erhältlich.\n"
        "ABSCHNITT 03: Zusammensetzung/Angaben zu Bestandteilen\n"
        "Gefährliche Inhaltsstoffe: 13463-67-7 Titandioxid > 1,0\n"
        "Carc. 2 - H351; EUH212\n"
    )

    def test_a_zero_padded_heading_ends_the_label(self) -> None:
        """Without it the block runs into the ingredient table.

        H351 there belongs to titanium dioxide, a raw material -- the label
        above it says the product carries no hazard statement at all. Thirteen
        sheets reported their ingredients' classifications this way.
        """
        block = find_label_section(self.LABEL)

        assert block is not None
        assert "EUH210" in block
        assert "H351" not in block
        assert "Titandioxid" not in block

    def test_an_unpadded_heading_still_ends_it(self) -> None:
        block = find_label_section(self.LABEL.replace("ABSCHNITT 03", "ABSCHNITT 3"))

        assert block is not None
        assert "H351" not in block

    def test_a_later_section_is_not_mistaken_for_the_third(self) -> None:
        """ "ABSCHNITT 13" must not end the label section."""
        text = self.LABEL.replace("ABSCHNITT 03", "ABSCHNITT 13")

        block = find_label_section(text)

        assert block is not None
        assert "Titandioxid" in block  # no boundary, so the cap applies


@pytest.mark.spec("SDB-5")
class TestClassificationEntriesAreNotLabelElements:
    """Section 2.1 reaches the label block when a two-column layout flattens."""

    def _label(self, body: str) -> str:
        return f"2.2 Kennzeichnungselemente\n{body}\nABSCHNITT 3: Zusammensetzung\n"

    def test_a_classification_beside_a_statement_is_ignored(self) -> None:
        """Article 26 is why it matters.

        A label carrying H314 may omit H318, so reading "Eye Dam. 1, H318" off
        the classification puts a statement on the product that its label
        deliberately leaves off.
        """
        text = self._label(
            "Gefahr H314 - Verursacht schwere Verätzungen der Haut.\n"
            "Spezielle Verpackungsanforderungen Skin Corr. 1, H314 Eye Dam. 1, H318\n"
        )

        block = find_label_section(text)

        assert block is not None
        assert set(
            HAZARD_CODE_PATTERN.findall(CLASSIFICATION_ENTRY.sub(" ", block))
        ) == {"H314"}

    def test_the_aquatic_pair_is_the_same_case(self) -> None:
        """H410 assigned lets the label omit H400."""
        text = "Asp. Tox. 1, H304 Aquatic Acute 1, H400 Aquatic Chronic 1, H410"

        assert HAZARD_CODE_PATTERN.findall(CLASSIFICATION_ENTRY.sub(" ", text)) == []

    def test_a_statement_is_not_mistaken_for_a_classification(self) -> None:
        """Only class-category-code is dropped, never a wording."""
        for keeper in (
            "H314 - Verursacht schwere Verätzungen der Haut.",
            "Gefahrenhinweise H290 Kann gegenüber Metallen korrosiv sein.",
            "H304: Kann bei Verschlucken tödlich sein.",
        ):
            assert CLASSIFICATION_ENTRY.search(keeper) is None

    def test_a_code_appearing_both_ways_is_kept(self) -> None:
        """The sheet lists H314 in its classification and on its label."""
        text = "Skin Corr. 1, H314 ... Gefahr H314 - Verursacht schwere Verätzungen."

        assert "H314" in HAZARD_CODE_PATTERN.findall(
            CLASSIFICATION_ENTRY.sub(" ", text)
        )


class TestLabelSectionEndsAtSonstigeGefahren:
    """Sheets that number nothing still have a section 2.3."""

    BULLETED = (
        "· Kennzeichnungselemente\n"
        "· Gefahrenpiktogramme GHS05 GHS07\n"
        "· Signalwort Gefahr\n"
        "· Gefahrenhinweise H315 Verursacht Hautreizungen. H318 Verursacht schwere "
        "Augenschäden.\n"
        "· Sonstige Gefahren\n"
        "3 Zusammensetzung/Angaben zu Bestandteilen\n"
        "Portlandzement Eye Dam. 1, H318\n"
    )

    def test_the_label_survives_a_document_that_numbers_nothing(self) -> None:
        """Without the named boundary the block is discarded for want of an end.

        "3 Zusammensetzung" carries no dot, so the numeric boundary misses it,
        and the label heading has no number either. Three sheets here lost a
        complete label -- pictograms, signal word and three statements -- that
        way.
        """
        block = find_label_section(self.BULLETED)

        assert block is not None
        assert "H315" in block
        assert "Portlandzement" not in block

    def test_the_english_heading_works_too(self) -> None:
        block = find_label_section(
            self.BULLETED.replace("Sonstige Gefahren", "Other hazards")
        )

        assert block is not None
        assert "Portlandzement" not in block

    def test_a_numbered_sheet_is_unaffected(self) -> None:
        text = (
            "2.2 Kennzeichnungselemente\n"
            "H319: Verursacht schwere Augenreizung.\n"
            "ABSCHNITT 3: Zusammensetzung\n"
        )

        block = find_label_section(text)

        assert block is not None
        assert "H319" in block


class TestRevisionDateLabels:
    """The wordings suppliers use for "when was this document last touched"."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Bearbeitungsdatum: 20.09.2017", date(2017, 9, 20)),
            ("Fassung vom 27.09.2022", date(2022, 9, 27)),
            ("Stand : 16.09.2016", date(2016, 9, 16)),
            # "Stand" without its colon is ordinary German prose, not a label.
            ("Stand der Technik 16.09.2016", None),
            # A print date says when the PDF was rendered, not when the
            # document was revised; the two are years apart on real sheets.
            ("Druckdatum: 13.07.2018", None),
            ("PDF-Druckdatum: 23.05.2022", None),
        ],
    )
    def test_revision_labels(self, text: str, expected: date | None) -> None:
        assert _extract_revision_date(text) == expected

    def test_erstellt_am_is_an_issue_date(self) -> None:
        assert _extract_issue_date("Erstellt am:26.09.2016") == date(2016, 9, 26)

    def test_the_label_may_sit_on_its_own_line(self) -> None:
        """Two-column layouts flatten into label, blank line, value."""
        assert _extract_issue_date("Erstellt am:\n\n05.12.2022") == date(2022, 12, 5)


@pytest.mark.spec("SDB-57")
class TestWhereASheetPrintsItsDate:
    """The labels and layouts a date stands behind, measured on a large set of sheets."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            # A version with its date behind it, in brackets or behind a dash.
            ("Nummer der Fassung: GHS 8.0 (10.06.2024)", date(2024, 6, 10)),
            ("Version 2.2 (18/07/2017) - Seite 1/12", date(2017, 7, 18)),
            ("Version : Nr. 1 (22/11/2019)", date(2019, 11, 22)),
            ("Revision : Nr. 2 (22/11/2019)", date(2019, 11, 22)),
            ("Rev. 14 – 19/12/2024", date(2024, 12, 19)),
            ("Revision 3. – 28/11/2024", date(2024, 11, 28)),
            ("Sicherheitsdatenblatt vom: 08/06/2023 - version 1", date(2023, 6, 8)),
            ("Überprüfung: 04.01.2021", date(2021, 1, 4)),
            # The date first, its version behind it.
            ("20/09/2021 (Version: 9.4)", date(2021, 9, 20)),
            # Year first.
            ("Überarbeitet am: 2024-08-26", date(2024, 8, 26)),
            # The version this sheet replaces is not this sheet.
            ("Ersetzt Fassung: GHS 7 (29.01.2024)", None),
            ("Ersetzt Fassung vom 01.01.2021", None),
            ("Ersetzt Fassung vom: 2024-08-22 (GHS 2)", None),
            # A number built like a date that stands behind no label.
            ("EG-Nr. 2024-08-26", None),
        ],
    )
    def test_revision_dates(self, text: str, expected: date | None) -> None:
        assert _extract_revision_date(text) == expected

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Erstelldatum: 07.04.2015", date(2015, 4, 7)),
            ("Erstellung 05.07.2013", date(2013, 7, 5)),
            ("Erstellt: 01.03.2022", date(2022, 3, 1)),
            ("Datum ausgestellt\n04.10.2016", date(2016, 10, 4)),
            ("Ausgabe:\n01.02.2026", date(2026, 2, 1)),
            ("Ausstellungsdatum: 2024-05-02", date(2024, 5, 2)),
            # The sheet before this one.
            ("Datum der letzten Ausgabe: 13.06.2017", None),
        ],
    )
    def test_issue_dates(self, text: str, expected: date | None) -> None:
        assert _extract_issue_date(text) == expected

    def test_labels_printed_as_a_row_over_their_values(self) -> None:
        """SAP's older header: the first date below is the revision's."""
        text = (
            "Version\n"
            "Überarbeitet am: Druckdatum Datum der letzten Ausgabe: 13.06.2017\n"
            "3.4\n27.02.2018\n28.11.2018\n"
            "Datum der ersten Ausgabe: 10.09.2013"
        )
        assert _extract_revision_date(text) == date(2018, 2, 27)

    def test_a_print_date_beside_the_label_is_still_none(self) -> None:
        assert (
            _extract_revision_date("Überarbeitet am: Druckdatum\nHandelsname") is None
        )

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Seite 1 von 9\nDatum: 16.05.2024\nVersion: 03", date(2024, 5, 16)),
            ("Datum : 22/11/2019 Seite 1/9", date(2019, 11, 22)),
            ("Stand 13.12.2014", date(2014, 12, 13)),
            # Not at the start of its line: the date of a list of limit values.
            ("AGW (TRGS 900, Stand 29.01.2018)", None),
            ("Druckdatum: 13.07.2018", None),
        ],
    )
    def test_a_date_without_a_telling_label_dates_a_sheet_that_has_no_other(
        self, parser: SDSParser, text: str, expected: date | None
    ) -> None:
        assert parser.parse(_build_extraction(text)).sheet.revision_date == expected

    def test_a_date_without_a_telling_label_stands_last(
        self, parser: SDSParser
    ) -> None:
        sheet = parser.parse(
            _build_extraction("gültig ab: 18.07.2022\nDatum: 16.05.2024")
        ).sheet
        assert sheet.revision_date == date(2022, 7, 18)

    def test_it_does_not_displace_an_issue_date(self, parser: SDSParser) -> None:
        sheet = parser.parse(
            _build_extraction("Erstellt am: 05.12.2022\nDatum: 16.05.2024")
        ).sheet
        assert sheet.revision_date is None
        assert sheet.issue_date == date(2022, 12, 5)


class TestEffectiveDateIsOnlyAFallback:
    """ "Tritt in Kraft ab" dates a document but does not date its revision."""

    def test_it_is_read_when_nothing_else_dates_the_sheet(
        self, parser: SDSParser
    ) -> None:
        sheet = parser.parse(
            _build_extraction(
                "Tritt in Kraft ab: 23.05.2022\nPDF-Druckdatum: 23.05.2022"
            )
        ).sheet
        assert sheet.revision_date == date(2022, 5, 23)

    def test_gueltig_ab_works_the_same_way(self, parser: SDSParser) -> None:
        sheet = parser.parse(_build_extraction("gültig ab: 18.07.2022")).sheet
        assert sheet.revision_date == date(2022, 7, 18)

    def test_it_never_overrides_a_stated_revision_date(self, parser: SDSParser) -> None:
        """A sheet revised on one day takes effect on another.

        Ranking revisions on the later of the two would pick the wrong sheet,
        so the stated revision date wins even though it is earlier.
        """
        sheet = parser.parse(
            _build_extraction(
                "Überarbeitungsdatum: 30/09/2021\nTritt in Kraft ab: 01/10/2021"
            )
        ).sheet
        assert sheet.revision_date == date(2021, 9, 30)

    def test_it_does_not_override_an_issue_date_either(self, parser: SDSParser) -> None:
        sheet = parser.parse(
            _build_extraction("Erstellt am: 05.12.2022\ngültig ab: 09.12.2022")
        ).sheet
        assert sheet.revision_date is None
        assert sheet.issue_date == date(2022, 12, 5)


def test_an_ocr_line_break_inside_the_label_still_dates_the_sheet() -> None:
    """One sheet reads "Überarbeitungsd\natum:\n01.10.2021"."""
    assert _extract_revision_date("Überarbeitungsd\natum:\n01.10.2021") == date(
        2021, 10, 1
    )


def test_the_break_tolerance_does_not_eat_the_day() -> None:
    """An earlier draft matched \\w here, which also matches digits.

    "Überarbeitet am:\n25.08.2020" then bound "25" as the continuation of the
    label and read the date as 05.08.2020 -- on 37 sheets.
    """
    assert _extract_revision_date("Überarbeitet am:\n25.08.2020") == date(2020, 8, 25)


def test_a_page_marker_between_the_label_and_the_date_is_stepped_over() -> None:
    """Footer layouts interleave the page number with the date they carry."""
    assert _extract_revision_date(
        "Ausgabedatum/\nÜberarbeitungsdatum\n:\nSeite: 1/13\n10-2-2021"
    ) == date(2021, 2, 10)


def test_only_a_page_marker_may_intervene() -> None:
    """Anything else between label and date means they are not related."""
    assert _extract_revision_date("Überarbeitet am:\nHandelsname X\n10-2-2021") is None


class TestTwoDigitYears:
    """ "Überarbeitung 29.06.11" -- a guess that may not displace a certainty."""

    def test_it_dates_a_sheet_that_yielded_nothing_else(
        self, parser: SDSParser
    ) -> None:
        sheet = parser.parse(
            _build_extraction(
                "Sicherheitsdatenblatt\nÜberarbeitung\n29.06.11\nVersion\n3"
            )
        ).sheet
        assert sheet.revision_date == date(2011, 6, 29)

    def test_a_four_digit_year_is_not_read_as_a_short_one(
        self, parser: SDSParser
    ) -> None:
        """Without the digit guard, "29.06.2011" reads as the 29th of June 20."""
        sheet = parser.parse(_build_extraction("Überarbeitet am 29.06.2011")).sheet
        assert sheet.revision_date == date(2011, 6, 29)

    def test_it_never_displaces_a_full_date(self, parser: SDSParser) -> None:
        sheet = parser.parse(
            _build_extraction("Überarbeitet am: 16.11.2020\nAusgabedatum 29.06.11")
        ).sheet
        assert sheet.revision_date == date(2020, 11, 16)

    def test_the_century_boundary_sits_at_ninety(self, parser: SDSParser) -> None:
        """Fixed, not pegged to today, so the same sheet reads the same next year."""
        assert parser.parse(
            _build_extraction("Überarbeitung 11.10.94")
        ).sheet.revision_date == date(1994, 10, 11)
        assert parser.parse(
            _build_extraction("Überarbeitung 11.10.24")
        ).sheet.revision_date == date(2024, 10, 11)


@pytest.mark.spec("SDB-89")
class TestTheSectionOrderBeforeReach:
    """One supplier's sheet of 2023: the composition before the hazards."""

    SHEET = (
        "SICHERHEITSDATENBLATT\n"
        "1. Stoff-/Zubereitung -und Firmenbezeichnung\n"
        "1.1 Handelsname: UNIMUSTER\n"
        "2. Zusammensetzung / Angaben zu den Bestandteilen\n"
        "2.3 Gefährliche Inhaltsstoffe: keine\n"
        "3. Mögliche Gefahren\n"
        "3.1 Gefahrenbezeichnung: entfällt\n"
        "4. Erste-Hilfe-Maßnahmen\n"
        "4.1 Allgemeine Hinweise: keine besonderen Maßnahmen erforderlich\n"
    )

    def test_the_title_says_which_section_it_is(self) -> None:
        sections = split_sections(self.SHEET)
        assert sections[Section.COMPOSITION] == "2.3 Gefährliche Inhaltsstoffe: keine"
        assert sections[Section.HAZARDS] == "3.1 Gefahrenbezeichnung: entfällt"
        assert sections[Section.IDENTIFICATION] == "1.1 Handelsname: UNIMUSTER"

    def test_the_classification_is_read_from_it(self) -> None:
        hazards = split_sections(self.SHEET)[Section.HAZARDS]
        assert stated_classification(hazards) is StatedClassification.NOT_CLASSIFIED

    def test_a_number_with_another_title_is_no_heading(self) -> None:
        """Only sections 2 and 3 changed places."""
        assert read_numbered_section_heading("2. Zusammensetzung") == 3
        assert read_numbered_section_heading("3. Mögliche Gefahren") == 2
        assert read_numbered_section_heading("4. Mögliche Gefahren") is None
        assert read_numbered_section_heading("2. Mögliche Gefahren") == 2


@pytest.mark.spec("SDB-58")
class TestASubsectionOpensASectionWhoseHeadingIsMissing:
    """One supplier's headings are white on a dark bar, and OCR does not read them."""

    SHEET = (
        "Sicherheitsdatenblatt\n"
        "1.1. Produktidentifikator\n"
        "Handelsname: Muster Mörtel\n"
        "1.3. Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
        "Muster GmbH\n"
        "2.1. Einstufung des Stoffs oder Gemischs\n"
        "Skin Irrit. 2 H315\n"
        "2.2. Kennzeichnungselemente\n"
        "H315 Verursacht Hautreizungen.\n"
        "3.2. Gemische\n"
        "Portlandzement H318\n"
        "ABSCHNITT 4: Erste-Hilfe-Maßnahmen\n"
        "Arzt rufen.\n"
    )

    def test_the_first_subsection_opens_sections_one_and_three(self) -> None:
        sections = split_sections(self.SHEET)
        assert sections[Section.IDENTIFICATION].startswith("1.1. Produktidentifikator")
        assert "Muster GmbH" in sections[Section.IDENTIFICATION]
        assert sections[Section.HAZARDS].endswith("H315 Verursacht Hautreizungen.")
        assert sections[Section.COMPOSITION] == "3.2. Gemische\nPortlandzement H318"

    def test_a_section_that_has_its_heading_is_not_opened_again(self) -> None:
        text = (
            "ABSCHNITT 1: Bezeichnung des Stoffs\n"
            "1.1 Produktidentifikator\n"
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "Siehe auch\n"
            "1.3 Einzelheiten zum Lieferanten\n"
            "ABSCHNITT 3: Zusammensetzung\n"
        )
        sections = split_sections(text)
        assert sections[Section.IDENTIFICATION].endswith("1.1 Produktidentifikator")
        assert "1.3 Einzelheiten zum Lieferanten" in sections[Section.HAZARDS]

    def test_a_subsection_of_an_earlier_section_does_not_reach_back(self) -> None:
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "H315 Verursacht Hautreizungen.\n"
            "1.1 Produktidentifikator\n"
        )
        sections = split_sections(text)
        assert Section.IDENTIFICATION not in sections

    def test_only_the_titles_of_the_subsections_count(self) -> None:
        text = "3.2 Gemische und Zubereitungen\nABSCHNITT 4: Erste-Hilfe-Maßnahmen\nx"
        assert Section.COMPOSITION in split_sections(text)
        assert Section.COMPOSITION not in split_sections(
            "3.2 mg/l\nABSCHNITT 4: Erste-Hilfe-Maßnahmen\nx"
        )

    @pytest.mark.parametrize(
        "heading",
        [
            "* 1 Abschnitt 1: Bezeichnung des Stoffs beziehungsweise des Gemischs",
            "* 1 Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens",
        ],
    )
    def test_a_mark_for_a_changed_section_stands_before_the_heading(
        self, heading: str
    ) -> None:
        sections = split_sections(f"{heading}\nHandelsname: Muster\n")
        assert sections[Section.IDENTIFICATION].endswith("Handelsname: Muster")


@pytest.mark.spec("SDB-1")
class TestPlainlyNumberedSectionHeadings:
    """Headings written "2. Mögliche Gefahren", without the word "Abschnitt"."""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("2. Mögliche Gefahren", 2),
            ("2 Mögliche Gefahren", 2),
            ("2. MÖGLICHE GEFAHREN", 2),
            ("3 Zusammensetzung/Angaben zu Bestandteilen", 3),
            ("16. Sonstige Angaben", 16),
            # A subsection is not a section.
            ("2.1 Einstufung des Stoffs oder Gemischs", None),
            # The title has to agree with the number, or every numbered list
            # item inside a section would start a new one.
            ("1. Bei Verschlucken sofort ärztlichen Rat einholen", None),
            ("2. Personen, die mit dem Produkt umgehen", None),
            ("8. Januar 2024", None),
            # There is no section 17.
            ("17. Sonstige Angaben", None),
            # The other pattern reads this one.
            ("ABSCHNITT 2: Mögliche Gefahren", None),
        ],
    )
    def test_headings_are_recognised_by_number_and_title(
        self, line: str, expected: int | None
    ) -> None:
        assert read_numbered_section_heading(line) == expected

    def test_a_sheet_numbered_without_abschnitt_is_split(self) -> None:
        sections = split_sections(
            "\n".join(
                [
                    "1 Bezeichnung des Stoffs",
                    "Portlandzement",
                    "2 Mögliche Gefahren",
                    "H318 Verursacht schwere Augenschäden.",
                    "3 Zusammensetzung/Angaben zu Bestandteilen",
                    "Portlandzementklinker",
                ]
            )
        )
        assert sections[Section.HAZARDS] == "H318 Verursacht schwere Augenschäden."
        assert sections[Section.COMPOSITION] == "Portlandzementklinker"

    def test_a_cross_reference_does_not_open_a_section(self) -> None:
        """A mention of "Abschnitt 8" in prose used to file the rest under 8.

        The heading pattern is anchored at the start of the line, so prose that
        names a section no longer opens one. Before that it did, and the damage
        was not one stray line: everything up to the next real heading went with
        it.
        """
        sections = split_sections(
            "\n".join(
                [
                    "2. Mögliche Gefahren",
                    "Persönliche Schutzausrüstung siehe unter Abschnitt 8.",
                    "3. Zusammensetzung/Angaben zu Bestandteilen",
                    "Portlandzementklinker",
                ]
            )
        )
        assert "siehe unter Abschnitt 8" in sections[Section.HAZARDS]
        assert Section.EXPOSURE_PPE not in sections
        assert "Portlandzementklinker" in sections[Section.COMPOSITION]

    def test_a_heading_is_not_taken_as_the_value_of_an_empty_key(self) -> None:
        """A filler, as pymupdf read the end of its section 2.

        The last key of 2.3 has no value, so the line after its colon is the
        heading of section 3. Joined to the key it stood mid-line, section 3
        opened a page later at the running header, and the ingredient table --
        H301, H310, H330 from a preservative below 0.001% -- sat in section 2.
        """
        sections = split_sections(
            "\n".join(
                [
                    "ABSCHNITT 2: Mögliche Gefahren",
                    "Das Produkt entspricht",
                    "den Kriterien für PBT- oder",
                    "vPvB-Stoffen gemäß",
                    "Anhang XIII der",
                    "Verordnung (EG) Nr.",
                    "1907/2006",
                    ":",
                    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen",
                    "C(M)IT/MIT(3:1)",
                    "Acute Tox. 2, H330",
                ]
            )
        )

        assert sections[Section.HAZARDS].endswith("1907/2006:")
        assert "H330" not in sections[Section.HAZARDS]
        assert "H330" in sections[Section.COMPOSITION]

    def test_the_label_survives_a_cross_reference_above_it(self) -> None:
        """The case the model felt: 152 sheets lost 2.2 to a sentence.

        "Der Wortlaut ... ist dem Abschnitt 16 zu entnehmen." sits between 2.1
        and 2.2. With the pattern unanchored it opened section 16 there, so the
        label -- the one part of section 2 the prompt actually asks for -- was
        filed under 16 and never reached the model.
        """
        sections = split_sections(
            "\n".join(
                [
                    "ABSCHNITT 2: Mögliche Gefahren",
                    "2.1 Einstufung des Stoffes oder Gemischs",
                    "Aquatic Chronic 3 H412 Schädlich für Wasserorganismen.",
                    "Der Wortlaut der angeführten Gefahrenhinweise ist dem "
                    "Abschnitt 16 zu entnehmen.",
                    "2.2 Kennzeichnungselemente",
                    "Gefahrenhinweise H412 Schädlich für Wasserorganismen.",
                    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen",
                    "Portlandzementklinker",
                ]
            )
        )
        assert "2.2 Kennzeichnungselemente" in sections[Section.HAZARDS]
        assert "Portlandzementklinker" in sections[Section.COMPOSITION]

    def test_an_exclamation_mark_before_the_word_is_still_a_heading(self) -> None:
        """96 sheets head their first section "!ABSCHNITT 1:".

        Enumerating the punctuation a heading may carry missed this one and cost
        them their section 1 -- and the loss was invisible in a label
        measurement, because find_label_section reads the raw text rather than
        the sections. Counted over the corpus, what precedes a heading is
        punctuation and what precedes a cross-reference is a word, so that is
        the rule now.
        """
        sections = split_sections(
            "\n".join(
                [
                    "!ABSCHNITT 1: Bezeichnung des Stoffs",
                    "Lieferant GmbH, Musterweg 1, 23014 Kiel",
                    "(ABSCHNITT 2: Mögliche Gefahren",
                    "H318 Verursacht schwere Augenschäden.",
                ]
            )
        )
        assert "Lieferant GmbH" in sections[Section.IDENTIFICATION]
        assert "H318 Verursacht schwere Augenschäden." in sections[Section.HAZARDS]

    def test_a_word_before_the_number_is_still_a_cross_reference(self) -> None:
        """The rule cuts between punctuation and letters, so prose stays prose."""
        sections = split_sections(
            "\n".join(
                [
                    "ABSCHNITT 2: Mögliche Gefahren",
                    "Angabe der Notrufnummer Österreich in Abschnitt 1.4.",
                    "H318 Verursacht schwere Augenschäden.",
                ]
            )
        )
        assert Section.IDENTIFICATION not in sections
        assert "H318 Verursacht schwere Augenschäden." in sections[Section.HAZARDS]

    def test_a_bulleted_heading_is_still_a_heading(self) -> None:
        """Sheets write "· ABSCHNITT 2" and "* ABSCHNITT 2" as often as the word."""
        sections = split_sections(
            "\n".join(
                [
                    "· ABSCHNITT 2: Mögliche Gefahren",
                    "H318 Verursacht schwere Augenschäden.",
                    "* ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen",
                    "Portlandzementklinker",
                ]
            )
        )
        assert "H318 Verursacht schwere Augenschäden." in sections[Section.HAZARDS]
        assert "Portlandzementklinker" in sections[Section.COMPOSITION]

    def test_an_english_heading_is_read_beside_german_ones(self) -> None:
        """Sheets are not reliably monolingual.

        Four sheets here head every section "ABSCHNITT n" and section 2 alone
        "SECTION 2: Hazards identification".
        """
        sections = split_sections(
            "\n".join(
                [
                    "ABSCHNITT 1: Bezeichnung des Stoffs",
                    "Portlandzement",
                    "SECTION 2: Hazards identification",
                    "H318 Verursacht schwere Augenschäden.",
                    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen",
                    "Portlandzementklinker",
                ]
            )
        )
        assert "H318 Verursacht schwere Augenschäden." in sections[Section.HAZARDS]
        assert "Portlandzementklinker" in sections[Section.COMPOSITION]

    def test_a_zero_padded_plain_number_is_a_heading(self) -> None:
        sections = split_sections(
            "\n".join(
                [
                    "01 Bezeichnung des Stoffs",
                    "Portlandzement",
                    "02 MÖGLICHE GEFAHREN",
                    "H318 Verursacht schwere Augenschäden.",
                ]
            )
        )
        assert sections[Section.HAZARDS] == "H318 Verursacht schwere Augenschäden."

    def test_a_heading_split_across_two_lines_is_joined(self) -> None:
        """Two sheets read "2" and "Mögliche Gefahren" on separate lines."""
        sections = split_sections(
            "\n".join(
                [
                    "1",
                    "Bezeichnung des Stoffs",
                    "Portlandzement",
                    "2",
                    "Mögliche Gefahren",
                    "Gefahrenbezeichnung: entfällt",
                ]
            )
        )
        assert sections[Section.HAZARDS] == "Gefahrenbezeichnung: entfällt"

    def test_a_bare_number_whose_next_line_is_not_a_title_is_left_alone(self) -> None:
        """A lone "2" is one of the commonest lines in a data sheet.

        The join is only taken when the result reads as a heading, so a number
        sitting in a table stays where it is.
        """
        sections = split_sections(
            "\n".join(
                [
                    "2. Mögliche Gefahren",
                    "Bestandteile:",
                    "2",
                    "Titandioxid",
                    "3. Zusammensetzung/Angaben zu Bestandteilen",
                    "Portlandzementklinker",
                ]
            )
        )
        assert "Titandioxid" in sections[Section.HAZARDS]
        assert sections[Section.COMPOSITION] == "Portlandzementklinker"

    def test_subsections_stand_in_for_a_missing_section_two_heading(self) -> None:
        """One sheet carries 2.1, 2.2 and 2.3 but no heading above them."""
        sections = split_sections(
            "\n".join(
                [
                    "ABSCHNITT 1: Bezeichnung des Stoffs",
                    "Portlandzement",
                    "2.1 Einstufung des Stoffs oder der Zubereitung",
                    "Das Produkt ist gemäß CLP-Verordnung nicht eingestuft.",
                    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen",
                    "Portlandzementklinker",
                ]
            )
        )
        assert "nicht eingestuft" in sections[Section.HAZARDS]
        assert "Portlandzementklinker" in sections[Section.COMPOSITION]

    def test_a_subsection_after_a_real_heading_does_not_reopen_section_two(
        self,
    ) -> None:
        """The stand-in is consulted only while section 2 has not been seen."""
        sections = split_sections(
            "\n".join(
                [
                    "ABSCHNITT 2: Mögliche Gefahren",
                    "H318 Verursacht schwere Augenschäden.",
                    "ABSCHNITT 16: Sonstige Angaben",
                    "2.2 Kennzeichnungselemente siehe oben",
                    "Wortlaut der H-Sätze",
                ]
            )
        )
        assert "Wortlaut der H-Sätze" in sections[Section.OTHER]
        assert "Wortlaut der H-Sätze" not in sections[Section.HAZARDS]

    def test_the_label_is_read_from_a_plainly_numbered_sheet(
        self, parser: SDSParser
    ) -> None:
        result = parser.parse(
            _build_extraction(
                "\n".join(
                    [
                        "1 Bezeichnung des Stoffs",
                        "Portlandzement",
                        "2 Mögliche Gefahren",
                        "Kennzeichnungselemente",
                        "Signalwort Gefahr",
                        "H315 Verursacht Hautreizungen.",
                        "H318 Verursacht schwere Augenschäden.",
                        "3 Zusammensetzung/Angaben zu Bestandteilen",
                        "Portlandzementklinker",
                    ]
                )
            )
        )
        hazards = result.sheet.hazard_statements
        assert hazards.signal_word == "Gefahr"
        assert hazards.hazard_codes == ["H315", "H318"]


class TestUndeterminedLabelling:
    """ "Nicht bestimmt" is neither a classification nor its absence."""

    def test_it_is_read_at_the_top_of_the_label_block(self) -> None:
        assert states_undetermined_labelling(
            "2.2.1 Kennzeichnung gemäß der Verordnung (EG) Nr. 1272/2008 (CLP)\n"
            "Nicht bestimmt\n"
        )

    def test_a_physical_property_further_down_does_not_count(self) -> None:
        """Section 9 says "nicht bestimmt" about properties nobody measured.

        A label block whose boundary failed runs on for
        LABEL_SECTION_MAX_CHARS, so the phrase has to be near the heading to
        be about the labelling.
        """
        assert not states_undetermined_labelling(
            "2.2 Kennzeichnungselemente\nSignalwort Gefahr\n"
            + "H315 Verursacht Hautreizungen.\n" * 12
            + "Geruchsschwelle: nicht bestimmt\n"
        )

    def test_a_stated_absence_is_something_else(self) -> None:
        """UNLABELLED_PATTERN reads a determination; this reads the lack of one.

        Conflating them would have us assert "no signal word" on a sheet that
        never said so.
        """
        block = "2.2 Kennzeichnungselemente\nKeine Kennzeichnung erforderlich\n"
        assert not states_undetermined_labelling(block)
        assert UNLABELLED_PATTERN.search(block)


def test_an_undetermined_label_is_warned_about_separately(
    parser: SDSParser,
) -> None:
    """ "No codes found" covers two very different sheets.

    One states the product carries no label. The other states that nobody
    worked out what its label should be -- which is not a product without
    hazards but a sheet without an answer, and a product resting on one belongs
    on the list of sheets the supplier owes a replacement for.
    """
    result = parser.parse(
        _build_extraction(
            "2.2 Kennzeichnungselemente\n"
            "2.2.1 Kennzeichnung gemäß der Verordnung (EG) Nr. 1272/2008 (CLP)\n"
            "Nicht bestimmt\n"
            "2.3 Sonstige Gefahren\n"
        )
    )
    # In the form the document checks read it back.
    assert classification([], None, result.warnings) is Classification.UNDETERMINED


def test_a_stated_absence_is_not_warned_about_that_way(parser: SDSParser) -> None:
    result = parser.parse(
        _build_extraction(
            "2.2 Kennzeichnungselemente\nKeine Kennzeichnung erforderlich\n"
            "2.3 Sonstige Gefahren\n"
        )
    )
    assert classification([], None, result.warnings) is (Classification.NOT_CLASSIFIED)


class TestEuhStatementsByTheirWording:
    """A label that prints an EUH statement without its code (SDB-28)."""

    @pytest.mark.spec("SDB-28")
    def test_the_code_is_read_and_the_text_carries_it(self, parser: SDSParser) -> None:
        text = _label(
            "Signalwort: Kein Signalwort.\n"
            "Ergänzende Kennzeichnungselemente: Enthält 1,2-Benzisothiazol-3(2H)-on."
            " Kann allergische Reaktionen hervorrufen."
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.supplemental_codes == ["EUH208"]
        assert hazards.supplemental_text == (
            "EUH208: Enthält 1,2-Benzisothiazol-3(2H)-on. "
            "Kann allergische Reaktionen hervorrufen."
        )

    @pytest.mark.spec("SDB-28")
    def test_the_supplemental_block_counts_behind_2_3(self, parser: SDSParser) -> None:
        """Set in two columns, one supplier's block reaches the text layer after
        2.3."""
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n2.2 Kennzeichnungselemente\n"
            "Signalwort: Kein Signalwort.\n"
            "H412 - Schädlich für Wasserorganismen, mit langfristiger Wirkung.\n"
            "2.3 Sonstige Gefahren\n"
            "Diese Mischung enthält keine Substanzen, die als PBT- oder vPvB-Stoffe "
            "eingestuft werden.\n"
            "Ergänzende\nKennzeichnungselemente: Wiederholter Kontakt kann zu "
            "spröder oder rissiger Haut führen.\n"
            "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
        )

        result = parser.parse(_build_extraction(text))

        assert result.sheet.hazard_statements.supplemental_codes == ["EUH066"]
        assert not any(w.code == "euh-wording-outside-label" for w in result.warnings)

    @pytest.mark.spec("SDB-28")
    def test_a_wording_outside_the_label_is_reported_not_read(
        self, parser: SDSParser
    ) -> None:
        """One supplier describes an effect under 2.3."""
        text = _label("H319 Verursacht schwere Augenreizung.") + (
            "Mögliche schädliche Wirkungen auf den Menschen und mögliche Symptome:\n"
            "Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
        )

        result = parser.parse(_build_extraction(text))

        assert result.sheet.hazard_statements.supplemental_codes == []
        assert (
            Message(
                "euh-wording-outside-label",
                {
                    "statement": "EUH066",
                    "sentence": (
                        "Wiederholter Kontakt kann zu spröder oder rissiger Haut "
                        "führen."
                    ),
                },
            )
            in result.warnings
        )

    @pytest.mark.spec("SDB-219")
    def test_a_wording_in_running_text_is_not_reported(self, parser: SDSParser) -> None:
        """One supplier describes the effects of dust under 2.3."""
        text = _label("H319 Verursacht schwere Augenreizung.") + (
            "Durch mechanische Einwirkungen können Schädigungen erfolgen. "
            "Wiederholter Kontakt\nkann zu spröder oder rissiger Haut führen. "
            "Staub kann die Augen reizen.\n"
            "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
        )

        result = parser.parse(_build_extraction(text))

        assert result.sheet.hazard_statements.supplemental_codes == []
        assert not any(w.code == "euh-wording-outside-label" for w in result.warnings)

    @pytest.mark.spec("SDB-28")
    def test_a_printed_code_is_read_once(self, parser: SDSParser) -> None:
        text = _label(
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen."
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.supplemental_codes == ["EUH066"]
        assert hazards.supplemental_text == (
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen."
        )

    @pytest.mark.spec("SDB-28")
    def test_a_worded_statement_leaves_the_one_it_ran_into(
        self, parser: SDSParser
    ) -> None:
        text = _label(
            "EUH210 Sicherheitsdatenblatt auf Anfrage erhältlich.\n"
            "Enthält Linalool. Kann allergische Reaktionen hervorrufen."
        )

        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.supplemental_text == (
            "EUH210 Sicherheitsdatenblatt auf Anfrage erhältlich.\n"
            "EUH208: Enthält Linalool. Kann allergische Reaktionen hervorrufen."
        )

    @pytest.mark.spec("SDB-28")
    def test_half_a_statement_outside_the_label_is_reported(
        self, parser: SDSParser
    ) -> None:
        """Under 2.4."""
        text = _label("EUH210 Sicherheitsdatenblatt auf Anfrage erhältlich.") + (
            "2.4 Zusätzliche Hinweise\nDas Produkt ist kein gefährlicher Stoff. "
            "Kann allergische Reaktionen hervorrufen. 2-Butanonoxim.\n"
            "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
        )

        result = parser.parse(_build_extraction(text))

        assert result.sheet.hazard_statements.supplemental_codes == ["EUH210"]
        assert (
            Message(
                "euh-wording-outside-label",
                {
                    "statement": "EUH208",
                    "sentence": "Kann allergische Reaktionen hervorrufen.",
                },
            )
            in result.warnings
        )


@pytest.mark.spec("SDB-41")
class TestClassificationEntries:
    """A hazard class before the first code is 2.1's classification, not a statement."""

    # one supplier's two-column layout: 2.1's entry and its boilerplate stand
    # behind the 2.2 heading in the text layer.
    SECTION_2 = (
        "ABSCHNITT 2: Mögliche Gefahren\n"
        "2.1 Einstufung des Stoffs oder Gemischs\n"
        "Produktdefinition: Gemisch\n"
        "2.2 Kennzeichnungselemente\n"
        "Signalwort: Kein Signalwort.\n"
        "Aquatic Chronic 3, H412\n"
        "Das Produkt ist als gefährlich eingestuft gemäß der Verordnung (EG) "
        "1272/2008 und deren Änderungen.\n"
        "Ausgabedatum/Überarbeitungsdatum: 6-6-2023\n"
        "Gefahrenhinweise:\n"
        "H412 - Schädlich für Wasserorganismen, mit langfristiger Wirkung.\n"
        "P273 - Freisetzung in die Umwelt vermeiden.\n"
        "2.3 Sonstige Gefahren\n"
        "Keine bekannt.\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
    )

    def test_it_begins_no_statement_wherever_it_stands(self, parser: SDSParser) -> None:
        sheet = parser.parse(_build_extraction(self.SECTION_2)).sheet

        assert sheet.hazard_statements.hazard_text == (
            "H412 - Schädlich für Wasserorganismen, mit langfristiger Wirkung."
        )
        assert sheet.hazard_statements.hazard_codes == ["H412"]

    def test_the_text_after_it_belongs_to_no_statement(self, parser: SDSParser) -> None:
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.2 Kennzeichnungselemente\n"
            "Signalwort: Achtung\n"
            "H315 Verursacht Hautreizungen.\n"
            "Skin Irrit. 2, H315\n"
            "Einstufung nach Berechnungsverfahren.\n"
            "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
        )

        sheet = parser.parse(_build_extraction(text)).sheet

        assert sheet.hazard_statements.hazard_text == "H315 Verursacht Hautreizungen."


def _supplier(section_1: str) -> ContactInfo:
    text = (
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
        + section_1
        + "\nABSCHNITT 2: Mögliche Gefahren\n2.2 Kennzeichnungselemente\nKein Signalwort.\n"
    )
    return SDSParser().parse(_build_extraction(text)).sheet.contact_info


@pytest.mark.spec("SDB-49", "SDB-50")
class TestSupplier:
    """The supplier of section 1.3, read without the model."""

    def test_a_name_under_the_heading_without_a_label(self) -> None:
        """One supplier's layout: the poison centre's number under 1.4 is not the supplier's."""
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
            "Südwerk Deco GmbH\nAm Mühlrad 2\nD-59280 Köln\nDeutschland,\n"
            "Telefon: +49 (0)551 / 400 729 05\nTelefax: +49 (0)551 / 400 729 15\n"
            "www.holzlasur.example\n"
            "E-Mail-Adresse der verantwortlichen Person für dieses SDB: sidainfo@suedwerk.example\n"
            "1.4 Notrufnummer\nTelefonnummer: (0551) 19240"
        )

        assert supplier.supplier_name == "Südwerk Deco GmbH"
        assert supplier.supplier_address == "Am Mühlrad 2, D-59280 Köln, Deutschland"
        assert supplier.supplier_phone == "+49 (0)551 / 400 729 05"
        assert supplier.supplier_email == "sidainfo@suedwerk.example"
        assert supplier.supplier_website == "www.holzlasur.example"

    def test_a_label_with_the_name_on_the_next_line(self) -> None:
        supplier = _supplier(
            "· 1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
            "· Hersteller/Lieferant:\nESCHENWERK CHEMIE GmbH\nBruno-Muster-Waldweg 20\n"
            "49731 Talstadt / Unterland\nTel. +49 (0)5173 – 950 90-0\n"
            "Fax +49 (0)5173 – 950 90-120\nE-Mail: service@eschenwerk.example\n"
            "Internet: www.eschenwerk.example\n· Auskunftgebender Bereich:\n"
            "Abteilung Regulatory Affairs\nE-Mail: labor@eschenwerk.example"
        )

        assert supplier.supplier_name == "ESCHENWERK CHEMIE GmbH"
        assert supplier.supplier_address == (
            "Bruno-Muster-Waldweg 20, 49731 Talstadt / Unterland"
        )
        assert supplier.supplier_phone == "+49 (0)5173 – 950 90-0"
        assert supplier.supplier_email == "service@eschenwerk.example"
        assert supplier.information_email == "labor@eschenwerk.example"
        assert supplier.supplier_website == "www.eschenwerk.example"

    def test_a_name_without_legal_form_goes_on_and_address_labels_go(self) -> None:
        supplier = _supplier(
            "1.3. Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
            "Firmenname: MUSTERWERK\nProduktions- u. Handelsges. chem. techn. Artikel mbH\n"
            "Straße: Seeuferstraße 4\nOrt: D-46535 Essen\n"
            "Telefon: +49 (0)501-65354-0 Telefax: +49 (0)501-65354-131\n"
            "Giftnotruf Erfurt: +49 (0)361 - 730730"
        )

        assert supplier.supplier_name == (
            "MUSTERWERK Produktions- u. Handelsges. chem. techn. Artikel mbH"
        )
        assert supplier.supplier_address == "Seeuferstraße 4, D-46535 Essen"
        assert supplier.supplier_phone == "+49 (0)501-65354-0"

    def test_a_number_on_the_line_below_its_label(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
            "Adresse\nLAUBWERK GmbH & Co. KG\nGroßer Kamp 1\nD-22885\nBarsbüttel\n"
            "Telefon-Nr.\n+49 (0)40 794 02-0\nFax-Nr.\n+49 (0)40 794 02-109"
        )

        assert supplier.supplier_name == "LAUBWERK GmbH & Co. KG"
        assert supplier.supplier_phone == "+49 (0)40 794 02-0"

    def test_a_poison_centre_is_no_supplier_phone(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nFirma: Muster GmbH\nMusterweg 1\n"
            "12345 Musterstadt\nGiftnotruf Berlin\nTelefon: 030/19240"
        )

        assert supplier.supplier_phone is None

    def test_without_the_heading_from_the_first_label(self) -> None:
        supplier = _supplier(
            "Handelsname\nKokos Blumenerde\nHersteller / Lieferant\nW. Weidenhof GmbH KG\n"
            "An der Mühle 3, D-30681 Mühlthal\n"
            "Telefon 06166/754-0 (Zentrale), Telefax 06166/7010\nE-Mail info@weidenhof.example"
        )

        assert supplier.supplier_name == "W. Weidenhof GmbH KG"
        assert supplier.supplier_phone == "06166/754-0"
        assert supplier.supplier_email == "info@weidenhof.example"

    def test_an_empty_block_hands_over_to_the_first_label(self) -> None:
        """One supplier prints 1.3's content as a table after 1.4."""
        supplier = _supplier(
            "1.3. Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
            "1.4. Notrufnummer\nLand\nOrganisation/Firma\nAnschrift\nNotrufnummer\n"
            "Deutschland\nGiftnotruf Mainz\nLieferant\nLindhof Garten Deutschland GmbH\n"
            "Walter-Theo-Muster-Straße 30\n50315 Mainz - Deutschland\nT +49 (0)1806 280 300"
        )

        assert supplier.supplier_name == "Lindhof Garten Deutschland GmbH"
        assert supplier.supplier_phone == "+49 (0)1806 280 300"

    @pytest.mark.parametrize(
        ("line", "name", "address"),
        [
            (
                "Ahornwerk Germany AG; Auenweg 22; 95044 Seestadt / Fluss",
                "Ahornwerk Germany AG",
                "Auenweg 22, 95044 Seestadt / Fluss",
            ),
            (
                "Buchfeld GmbH, Am Hafen 74, D- 29327 Feldstadt",
                "Buchfeld GmbH",
                "Am Hafen 74, D- 29327 Feldstadt",
            ),
        ],
    )
    def test_a_name_line_with_the_address_on_it(
        self, line: str, name: str, address: str
    ) -> None:
        supplier = _supplier(f"1.3 Einzelheiten zum Lieferanten\nHersteller: {line}")

        assert supplier.supplier_name == name
        assert supplier.supplier_address == address

    def test_a_kit_names_the_block_under_another_number(self) -> None:
        supplier = _supplier(
            "1.2 Einzelheiten zum Lieferanten der das Kit-Sicherheitsdatenblatt bereitstellt\n"
            "dübelwerke GmbH & Co. KG\nKarl-Muster-Straße 1\n78127 Waldfeld - Deutschland\n"
            "T +49(0)2443 15-0 - F +49(0)2443 15-4555\ninfo-sdb@duebelwerk.example - www.duebelwerk.example"
        )

        assert supplier.supplier_name == "dübelwerke GmbH & Co. KG"
        assert supplier.supplier_phone == "+49(0)2443 15-0"
        assert supplier.supplier_website == "www.duebelwerk.example"

    def test_a_pictogram_for_a_label_leaves_address_and_number_on_one_line(
        self,
    ) -> None:
        """One supplier prints a telephone pictogram, and the reader pairs the row."""
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
            "Hersteller/Lieferant\nESCHENWERK CHEMIE GmbH\nBruno-Muster-Waldweg 20\n"
            "D-49731 Talstadt (Unterland): +49 (0) 5173 / 960 90 999\n"
            ": service@eschenwerk.example: www.eschenwerk.example\n"
            "1.4 Notrufnummer\nGiftnotruf Berlin (24 h): +49 (0) 30 / 30 68 67 00"
        )

        assert supplier.supplier_address == (
            "Bruno-Muster-Waldweg 20, D-49731 Talstadt (Unterland)"
        )
        assert supplier.supplier_phone == "+49 (0) 5173 / 960 90 999"

    def test_a_number_without_any_label_is_the_telephone(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nHersteller/Lieferant:\nRECYCLING Medizin GmbH\n"
            "Felix-Muster-Straße 4\n97809 Erfurt\n+49 (0) 371/764693-0\n"
            "+49 (0) 371/764693-20\ntechnik@huegel-chemie.example"
        )

        assert supplier.supplier_phone == "+49 (0) 371/764693-0"

    def test_the_office_number_comes_before_a_service_number(self) -> None:
        """One supplier prints its paid hotline first."""
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nHersteller\nKalkwerk Bauprodukte GmbH & Co. KG\n"
            "Am Kalkofen 7\n96437 Kalkfeld - Deutschland\nTechnische Auskunft\n"
            "T +49 (0) 1806/31-9000 (0,14 €/Min. aus dem deutschen Festnetz,\n"
            "Mobilfunk max. 0,42€/Min. möglich)\nT +49 9353 31-0 - F +49 9353 31-353"
        )

        assert supplier.supplier_phone == "+49 9353 31-0"

    def test_a_service_number_is_taken_where_it_is_the_only_one(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nLindhof Garten Deutschland GmbH\n"
            "Walter-Theo-Muster-Straße 30\nD-50315 Mainz\n"
            "Nicht-Notfall-Rufnummern\n+49 (0)1806 280300 (DE): 0,14 € min"
        )

        assert supplier.supplier_phone == "+49 (0)1806 280300"

    @pytest.mark.parametrize(
        "line",
        [
            "Tel. Giftnotruf Berlin: +49 30 30686700",
            "Telefax:/Telefon: 0551 153467",
            "Telefon:\nStand 01.02.2023",
        ],
    )
    def test_a_line_that_is_not_the_offices_gives_no_number(self, line: str) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nMuster GmbH\nHauptstraße 1\n12345 Musterstadt\n"
            + line
        )

        assert supplier.supplier_phone is None

    def test_lines_set_side_by_side_are_parted_at_the_bar(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nHersteller/Lieferant:\n"
            "XY Group Deutschland GmbH\nHafenstr. 68 | 70423 Weidlingen\n"
            "GERMANY | Tel. +49 2054 4048-70, Fax. +49 2054 4048-790"
        )

        assert supplier.supplier_address == "Hafenstr. 68, 70423 Weidlingen, GERMANY"
        assert supplier.supplier_phone == "+49 2054 4048-70"

    def test_a_legal_form_on_the_next_line_ends_the_name(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nHersteller/Lieferant\n"
            "Liquida - Flüssige Produkte Abfüll- und Verpackungs GmbH & Co.\nKG\n"
            "Am Buchsberg 6\nDE 37511 Weststadt"
        )

        assert supplier.supplier_name == (
            "Liquida - Flüssige Produkte Abfüll- und Verpackungs GmbH & Co. KG"
        )
        assert supplier.supplier_address == "Am Buchsberg 6, DE 37511 Weststadt"

    def test_a_label_with_the_company_behind_it_and_no_colon(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nHersteller/Lieferant Haselwerk AG & Co. KGaA\n"
            "Haselwerkstr. 76\n49850 Düsseldorf"
        )

        assert supplier.supplier_name == "Haselwerk AG & Co. KGaA"
        assert supplier.supplier_address == "Haselwerkstr. 76, 49850 Düsseldorf"

    def test_a_heading_of_section_1_is_no_name(self) -> None:
        """One supplier's table reaches the text apart from its headings."""
        supplier = _supplier(
            "1,3 Einzelheiten zum Lieferanten,\nder das Sicherheitsdatenblatt\nbereitstellt\n"
            "Relevante identifizierte\nVerwendungen\n9000 St. Bergen\nSwitzerland\n"
            "quality@alpeninno.example"
        )

        assert supplier.supplier_name is None
        assert supplier.supplier_address == "9000 St. Bergen, Switzerland"

    def test_a_weight_is_not_the_heading(self) -> None:
        supplier = _supplier(
            "1.1 Produktidentifikator\nHandelsname: Wandfarbe\n1,3 kg\nEimer weiß\n"
            "1.3 Einzelheiten zum Lieferanten\nMuster GmbH\nHauptstraße 1"
        )

        assert supplier.supplier_name == "Muster GmbH"

    def test_one_company_of_several_listed_by_country(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\n(DE) Pappel Flora GmbH\n"
            "Walter-Theo-Muster-Straße 30\nMainz, 50315\n"
            "(AT) Pappel FLORA Handelsgesellschaft mbH,\nKastanienstrasse 7 B\n"
            "Salzburg, 5020"
        )

        assert supplier.supplier_name == "Pappel Flora GmbH"
        assert supplier.supplier_address == (
            "Walter-Theo-Muster-Straße 30, Mainz, 50315"
        )

    def test_a_pictogram_stands_for_its_label(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nHersteller/Lieferant\nESCHENWERK CHEMIE GmbH\n"
            "Bruno-Muster-Waldweg 20\nD-49731 Talstadt (Unterland)\n"
            "📞: +49 (0) 5173 / 960 90 999\n📧: service@eschenwerk.example\n🌐: www.eschenwerk.example"
        )

        assert supplier.supplier_address == (
            "Bruno-Muster-Waldweg 20, D-49731 Talstadt (Unterland)"
        )
        assert supplier.supplier_phone == "+49 (0) 5173 / 960 90 999"

    def test_address_labels_joined_by_slashes_are_dropped(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\n"
            "Hersteller/Lieferant: Fugenwerk Dichtstoffe GmbH & Co. KG\n"
            "Straße/Postfach: Rolf-Muster-Str. 12\n"
            "Nat.-Kenn./PLZ/Ort: D-53455 Bad Waldstadt\nTelefon: +49 721 950016-0"
        )

        assert supplier.supplier_address == "Rolf-Muster-Str. 12, D-53455 Bad Waldstadt"
        assert supplier.supplier_phone == "+49 721 950016-0"

    def test_the_town_behind_a_line_of_the_column_beside_it(self) -> None:
        supplier = _supplier(
            "1.3. Einzelheiten zum Lieferanten\nHersteller/Lieferant\nA.B.C. GmbH\n"
            "Haselring 4\nE-Mail sachkundige Person:\nsds@sdb-dienst.example\n"
            "81602 Neufeld - Germany\nT +49 (0)89 246075-0 - F +49 (0)89 246075-99"
        )

        assert supplier.supplier_address == "Haselring 4, 81602 Neufeld - Germany"
        assert supplier.supplier_phone == "+49 (0)89 246075-0"

    def test_a_second_supplier_label_ends_the_first_company(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nLieferant\n"
            "Lindhof Garten Deutschland GmbH\nWalter-Theo-Muster-Straße 30\n"
            "50315 Mainz - Deutschland\nT +49 (0)1806 280 300 (14 ct/Min.)\n"
            "Lieferant\nLindhof Garten Österreich GmbH\nFritz-Muster-Straße 11-13\n"
            "5170 Wald-Feldheim - Österreich\nT +43 775 436216-0"
        )

        assert supplier.supplier_name == "Lindhof Garten Deutschland GmbH"
        assert supplier.supplier_phone == "+49 (0)1806 280 300"

    def test_a_town_further_down_is_somebody_elses(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nMuster GmbH\nHugo-Muster-Straße 40\n"
            "Telefon: +49 231 153467\nE-Mail: info@muster.example\nInternet: www.muster.example\n"
            "Vergiftungsinformationszentrale\n1010 Wien"
        )

        assert supplier.supplier_address == "Hugo-Muster-Straße 40"

    def test_a_second_companys_town_is_not_the_first_ones(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nMuster Danmark A/S\nMustervej 300\n"
            "2860 Søborg\nTel: +46 (0)67 74 60 00\nNationaler Kontakt\n"
            "Muster Austria GmbH\nIndustriestraße 1\nA-1032 Wien"
        )

        assert supplier.supplier_address == "Mustervej 300, 2860 Søborg"

    @pytest.mark.parametrize("label", ["Tel./Fax:", "Telefon/Telefax:"])
    def test_one_label_for_telephone_and_fax(self, label: str) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nMuster GmbH\nHauptstraße 1\n12345 Musterstadt\n"
            f"{label} 0551 153467"
        )

        assert supplier.supplier_phone == "0551 153467"

    @pytest.mark.parametrize(
        "heading", ["1.3: Lieferant", "1.3 - Angaben zum Lieferanten"]
    )
    def test_the_heading_with_a_colon_or_a_dash(self, heading: str) -> None:
        supplier = _supplier(
            f"{heading}\nMuster GmbH\nHauptstraße 1\n12345 Musterstadt"
        )

        assert supplier.supplier_name == "Muster GmbH"

    def test_a_page_break_inside_the_block_is_read_past(self) -> None:
        header = (
            "Sicherheitsdatenblatt\ngemäß der Verordnung (EG) Nr. 1907/2006 (REACH)\n"
        )
        text = (
            "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
            "1.3 Einzelheiten zum Lieferanten\nAPPLICATION DES GAZ\n219, Route de Brignais\n"
            "FR– 63659 ST MUSTER VILLE\n1/3\n" + header + "FRANCE\n"
            "T + 33 (0) 4 78 86 88 94\n"
            "ABSCHNITT 2: Mögliche Gefahren\n2.2 Kennzeichnungselemente\nKein Signalwort.\n"
            "2/3\n" + header + "ABSCHNITT 3: Zusammensetzung\n3/3\n" + header
        )

        supplier = SDSParser().parse(_pages(text, 3)).sheet.contact_info

        assert supplier.supplier_address == (
            "219, Route de Brignais, FR– 63659 ST MUSTER VILLE, FRANCE"
        )


@pytest.mark.spec("SDB-60")
class TestSupplierBlocksOfOtherSuppliers:
    """Layouts of section 1.3 found on a larger set of sheets."""

    HEADING = (
        "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
    )

    def test_a_name_that_begins_with_an_initial_is_no_fax_number(self) -> None:
        """ "Hersteller" alone, then "F.W.Kiefer"."""
        supplier = _supplier(
            self.HEADING + "Hersteller\nF.W.Kiefer\nHauptstraße 20\nD-88614 Ahorn\n"
            "Telefon +49 (0) 8244 97 99 10\nTelefax + 49 (0) 8744 96 99 96\n"
            "1.4 Notrufnummer"
        )
        assert supplier.supplier_name == "F.W.Kiefer"
        assert supplier.supplier_address == "Hauptstraße 20, D-88614 Ahorn"
        assert supplier.supplier_phone == "+49 (0) 8244 97 99 10"

    @pytest.mark.parametrize(
        ("line", "phone"),
        [
            ("T +49 8621 400", "+49 8621 400"),
            ("T UK FREEPHONE 0800 006 1010", "0800 006 1010"),
            ("Tlf.: +46 39 62 94 00", "+46 39 62 94 00"),
        ],
    )
    def test_a_letter_before_a_number_is_its_label(self, line: str, phone: str) -> None:
        supplier = _supplier(
            self.HEADING + f"Muster GmbH\nMusterweg 1\n12345 Musterstadt\n{line}\n"
        )
        assert supplier.supplier_phone == phone

    @pytest.mark.spec("SDB-50")
    @pytest.mark.parametrize(
        ("line", "phone"),
        [
            # The country code in brackets, plus included: printed like that.
            ("Telefon: (+49) 0555-0142-0", "(+49) 0555-0142-0"),
            ("Tel.: (+49 555) 0142-0", "(+49 555) 0142-0"),
            ("Tel.: (0555) 0142-0", "(0555) 0142-0"),
            # The whole number in brackets: they are not part of it.
            ("Telefon (+49 555 0142-0)", "+49 555 0142-0"),
            # A bracket behind the number opens a remark.
            ("Tel.: (+49) 0555-0142-0 (Mo-Fr 8-16 Uhr)", "(+49) 0555-0142-0"),
        ],
    )
    def test_a_bracket_around_the_country_code_stays(
        self, line: str, phone: str
    ) -> None:
        supplier = _supplier(
            self.HEADING + f"Muster GmbH\nMusterweg 1\n12345 Musterstadt\n{line}\n"
        )
        assert supplier.supplier_phone == phone

    @pytest.mark.spec("SDB-50")
    def test_a_line_that_is_only_such_a_number_ends_the_address(self) -> None:
        supplier = _supplier(
            self.HEADING + "Muster GmbH\nMusterweg 1\n12345 Musterstadt\n"
            "(+49) 0555-0142-0\n"
        )
        assert supplier.supplier_address == "Musterweg 1, 12345 Musterstadt"
        assert supplier.supplier_phone == "(+49) 0555-0142-0"

    def test_the_end_of_the_heading_beside_the_address(self) -> None:
        """One supplier: the title breaks at "bereit-", and "stellt:" stands in
        front of the street."""
        supplier = _supplier(
            "1.3\nEinzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereit-\n"
            "F. Eichhof GmbH & Co. KG\nstellt: Erlenweg 48\nD-36018 Braunschweig\n"
            "Fon +49 631-5 38 030\nFax +49 631-5 38 03 60\n1.4\nNotruf-Nr."
        )
        assert supplier.supplier_name == "F. Eichhof GmbH & Co. KG"
        assert supplier.supplier_address == "Erlenweg 48, D-36018 Braunschweig"
        assert supplier.supplier_phone == "+49 631-5 38 030"

    def test_the_heading_over_three_lines(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum\nLieferanten, der das\nSicherheitsdatenblatt\n"
            "bereitstellt\nAbo SE & Co. KGaA\nEichenbachstr. 1\nD - 70879 Brückingen\n"
        )
        assert supplier.supplier_name == "Abo SE & Co. KGaA"
        assert supplier.supplier_address == "Eichenbachstr. 1, D - 70879 Brückingen"

    def test_a_remark_in_brackets_under_the_heading_is_nobodys_name(self) -> None:
        supplier = _supplier(
            self.HEADING
            + "(Hersteller/Importeur/Alleinvertreter/nachgeschalteter Anwender/Händler)\n"
            "Firmenbezeichnung:\nGroß GmbH\nZum Lindenhof 34\nD-61329 Eichenberg\n"
            "Telefon: 02563-934276\n"
        )
        assert supplier.supplier_name == "Groß GmbH"
        assert supplier.supplier_address == "Zum Lindenhof 34, D-61329 Eichenberg"
        assert supplier.supplier_phone == "02563-934276"

    def test_a_numbered_label_without_the_heading(self) -> None:
        """No 1.3, and the parts of the address set apart by dots."""
        supplier = _supplier(
            "1.1 Handelsname: ZITRUSMUSTER 2/8 mm\n"
            "1.2 Inverkehrbringer: Birk Creations GmbH . Buchenstr. 2–10\n"
            "93150 Tannendorf . GERMANY .\nwww.pflanzgefaess.example\n"
        )
        assert supplier.supplier_name == "Birk Creations GmbH"
        assert supplier.supplier_address == (
            "Buchenstr. 2–10, 93150 Tannendorf . GERMANY ."
        )
        assert supplier.supplier_website == "www.pflanzgefaess.example"

    @pytest.mark.parametrize(
        "label",
        [
            "Angaben zum Hersteller:",
            "Angaben zum Lieferanten:",
            "Angaben zum Hersteller / Lieferant:",
        ],
    )
    def test_a_label_that_begins_angaben_zum(self, label: str) -> None:
        supplier = _supplier(
            f"Handelsname: Muster\n{label} Dörnfeld GmbH\nUlmenstrasse 08\n06508 Südstadt\n"
            "Telefon: 0049 326 52122 20\n"
        )
        assert supplier.supplier_name == "Dörnfeld GmbH"
        assert supplier.supplier_address == "Ulmenstrasse 08, 06508 Südstadt"
        assert supplier.supplier_phone == "0049 326 52122 20"

    def test_a_name_that_begins_like_a_postcode(self) -> None:
        supplier = _supplier(
            self.HEADING + "Firma: 2022 XS Deutschland GmbH\nAnton-Muster Straße 50\n"
            "49870 Nordstadt am Fluss, Germany\nTelefon: +49 5123 9936539\n"
        )
        assert supplier.supplier_name == "2022 XS Deutschland GmbH"
        assert supplier.supplier_address == (
            "Anton-Muster Straße 50, 49870 Nordstadt am Fluss, Germany"
        )

    def test_name_address_and_telephone_on_one_line(self) -> None:
        """The colon belongs to the telephone, not to a label of the line."""
        supplier = _supplier(
            "Bezeichnung der Zubereitung:\nAlgol\nFirmenbezeichnung:\n"
            "XYZ GmbH & Co. KG, Motorstr. 3, D-61417 Birkenhofen, Tel.: +49 7537 4180 0\n"
            "Notfallauskunft/Notfallnummer:\n+49 7537 4180 0\n"
        )
        assert supplier.supplier_name == "XYZ GmbH & Co. KG"
        assert supplier.supplier_address == "Motorstr. 3, D-61417 Birkenhofen"
        assert supplier.supplier_phone == "+49 7537 4180 0"

    def test_the_telephone_behind_the_town_on_the_name_line(self) -> None:
        """The German company's number, not the Swiss office's below."""
        supplier = _supplier(
            "1.3 Hersteller / Lieferant: Lärchen Morgen Düngerwerke GmbH, Auerhahnweg 35, "
            "D-91140 Nürnberg. Tel.: +49 (0)911 9410000 0\n"
            "Auskunftgebende Stelle\n"
            "Lärchen LHD Dünger AG, CH-3752 Grossfeldern. Tel.: ++041(0) 35 389 10 10\n"
            "Tel.: ++ 41 32 389 10 10 E-mail: info@laerchen.example\n1.4 Notrufnummer"
        )
        assert supplier.supplier_name == "Lärchen Morgen Düngerwerke GmbH"
        assert supplier.supplier_address == "Auerhahnweg 35, D-91140 Nürnberg"
        assert supplier.supplier_phone == "+49 (0)911 9410000 0"

    def test_a_telephone_label_inside_a_line_and_the_next_company(self) -> None:
        """A free number is the German company's only one, and
        the Swiss company below has its own."""
        supplier = _supplier(
            self.HEADING + "Hersteller/Lieferant:\n"
            "Jonas Hartig Europe GmbH, Birken-Platz 1, D- 44740 Düsseldorf,\n"
            "Deutschland Telefon: 0800 - 6536776, Fax: 0800 - 6367628\n"
            "sdb@jonashartig.example\n"
            "Gipswerk GmbH Schweiz, Seestrasse 4, 3011 Bergingen, Schweiz Telefon: "
            "+41 (0) 31 25450 50,\n1.4 Notrufnummer:"
        )
        assert supplier.supplier_name == "Jonas Hartig Europe GmbH"
        assert supplier.supplier_phone == "0800 - 6536776"

    def test_a_number_on_its_own_line_stands_before_one_inside_a_line(self) -> None:
        """POLIERGUT: the office's bare number, not the laboratory's."""
        supplier = _supplier(
            self.HEADING + "Hersteller/Lieferant:\nPOLIERGUT\nBerg & Tal GmbH\n"
            "Tournéestr. 5\n25688 Lilienfeld\ninfo@poliergut.example\n+49(0)4598-4775-0\n"
            "Auskunftgebender Bereich:\n"
            "POLIERGUT Abteilung Labor Tel.: +49(0)4598-4775-71\n"
        )
        assert supplier.supplier_name == "POLIERGUT Berg & Tal GmbH"
        assert supplier.supplier_phone == "+49(0)4598-4775-0"

    def test_numbers_of_the_subsection_inside_the_block(self) -> None:
        """One supplier: "1.2.1" before "Anschrift:" does not end the block."""
        supplier = _supplier(
            "1.2\nHersteller / Lieferant:\ntannol feldina® GmbH\n1.2.1\nAnschrift:\n"
            "Hauptsitz:\nEschener Straße 145\n09054 Hafenstadt\nDeutschland\n"
            "Tel.: 034505 / 76300\nFax: 034505 / 76309\n1.3\nNotrufnummer"
        )
        assert supplier.supplier_name == "tannol feldina® GmbH"
        assert supplier.supplier_address == (
            "Eschener Straße 145, 09054 Hafenstadt, Deutschland"
        )
        assert supplier.supplier_phone == "034505 / 76300"

    def test_one_point_three_without_its_title_on_an_old_sheet(self) -> None:
        """1.3 is the preparation, the supplier stands under 1.4."""
        supplier = _supplier(
            "1.3\nZubereitung: Mineralischer NPK-Dünger mit\nEisensulfat\n1.4\n"
            "Hersteller/Lieferant: BACHMANN & BREUER GmbH\nTelefon: 0 42 44/92 74 – 0\n"
            "1.5\nNotfallauskunft: siehe Hersteller/Lieferant"
        )
        assert supplier.supplier_name == "BACHMANN & BREUER GmbH"
        assert supplier.supplier_phone == "0 42 44/92 74 – 0"

    def test_the_number_alone_under_a_label_is_no_name(self) -> None:
        supplier = _supplier(
            "Angaben zum Hersteller/Lieferanten\n1.3\nZedernwerk GmbH\n"
            "Kleinberghausen 6b\n49582 Remsfeld\nTelefon: +49 (0) 51 91-389090\n"
        )
        assert supplier.supplier_name == "Zedernwerk GmbH"

    def test_a_label_where_a_name_would_stand_is_none(self) -> None:
        """OCR reads a bullet as a colon: ": Auskunftgebender Bereich:"."""
        supplier = _supplier(
            self.HEADING + "Hersteller/Lieferant:\n: Auskunftgebender Bereich:\n"
        )
        assert supplier.supplier_name is None


@pytest.mark.spec("SDB-62")
class TestStatementsSetAsRunningText:
    """Several statements to a line, and codes in brackets behind their sentences."""

    @staticmethod
    def _texts(label: str) -> tuple[str | None, str | None, str | None]:
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n2.2 Kennzeichnungselemente\n"
            + label
            + "\n2.3 Sonstige Gefahren\nKeine.\n"
        )
        hazards = SDSParser().parse(_build_extraction(text)).sheet.hazard_statements
        return (
            hazards.hazard_text,
            hazards.precautionary_text,
            hazards.supplemental_text,
        )

    def test_a_statement_ends_on_the_line_of_the_next(self) -> None:
        """The paragraph wraps inside P251, and P261 follows on the line."""
        _, precautionary, _ = self._texts(
            "P211-Nicht gegen offene Flamme oder andere Zündquelle sprühen. "
            "P251-Nicht durchstechen oder verbrennen, auch nicht nach\n"
            "Gebrauch. P261-Einatmen von Dampf oder Aerosol vermeiden. "
            "P273-Freisetzung in die Umwelt vermeiden."
        )
        assert precautionary == (
            "P211-Nicht gegen offene Flamme oder andere Zündquelle sprühen.\n"
            "P251-Nicht durchstechen oder verbrennen, auch nicht nach Gebrauch.\n"
            "P261-Einatmen von Dampf oder Aerosol vermeiden.\n"
            "P273-Freisetzung in die Umwelt vermeiden."
        )

    def test_hazard_statements_as_a_paragraph(self) -> None:
        hazard, _, _ = self._texts(
            "Gefahrenhinweise\n"
            "H224 Flüssigkeit und Dampf extrem entzündbar. H304 Kann bei Verschlucken\n"
            "und Eindringen in die Atemwege tödlich sein. H315 Verursacht Hautreizungen."
        )
        assert hazard == (
            "H224 Flüssigkeit und Dampf extrem entzündbar.\n"
            "H304 Kann bei Verschlucken und Eindringen in die Atemwege tödlich sein.\n"
            "H315 Verursacht Hautreizungen."
        )

    def test_a_label_before_the_code_is_no_end_of_a_statement(self) -> None:
        _, precautionary, _ = self._texts(
            "P102 Darf nicht in die Hände von Kindern\n"
            "Prävention: P261 Einatmen von Dampf vermeiden."
        )
        assert precautionary == (
            "P102 Darf nicht in die Hände von Kindern\nP261 Einatmen von Dampf vermeiden."
        )

    def test_text_before_a_code_behind_a_finished_statement_is_not_its_end(
        self,
    ) -> None:
        _, precautionary, _ = self._texts(
            "P102 Darf nicht in die Hände von Kindern gelangen.\n"
            "Nur für gewerbliche Anwender. P261 Einatmen von Dampf vermeiden."
        )
        assert precautionary == (
            "P102 Darf nicht in die Hände von Kindern gelangen.\n"
            "P261 Einatmen von Dampf vermeiden."
        )

    def test_codes_in_brackets_behind_their_sentences(self) -> None:
        """A sheet that prints every statement before its code."""
        hazard, precautionary, _ = self._texts(
            "Gefahrenhinweise\n"
            "Extrem entzündbares Aerosol. Behälter steht unter Druck: Kann bei "
            "Erwärmung bersten. (H222, H229)\n"
            "Verursacht schwere Augenreizung. (H319)\n"
            "Sicherheitshinweise\nPrävention\n"
            "Von Hitze, heißen Oberflächen, Funken, offenen Flammen sowie anderen "
            "Zündquellenarten fernhalten. Nicht rauchen.\n(P210)\n"
            "Reaktion\n"
            "BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang behutsam mit Wasser spülen. "
            "Eventuell vorhandene\n"
            "Kontaktlinsen nach Möglichkeit entfernen. Weiter spülen. (P305+P351+P338)\n"
            "Bei anhaltender Augenreizung: Ärztlichen Rat einholen/ärztliche Hilfe "
            "hinzuziehen. (P337+P313)\nLagerung"
        )
        assert hazard == (
            "H222, H229 Extrem entzündbares Aerosol. Behälter steht unter Druck: "
            "Kann bei Erwärmung bersten.\n"
            "H319 Verursacht schwere Augenreizung."
        )
        assert precautionary == (
            "P210 Von Hitze, heißen Oberflächen, Funken, offenen Flammen sowie anderen "
            "Zündquellenarten fernhalten. Nicht rauchen.\n"
            "P305+P351+P338 BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang behutsam mit "
            "Wasser spülen. Eventuell vorhandene Kontaktlinsen nach Möglichkeit "
            "entfernen. Weiter spülen.\n"
            "P337+P313 Bei anhaltender Augenreizung: Ärztlichen Rat einholen/ärztliche "
            "Hilfe hinzuziehen."
        )

    def test_brackets_alone_under_a_heading_give_no_statement(self) -> None:
        _, precautionary, _ = self._texts("Prävention\n(P210)\nLagerung")
        assert precautionary is None


@pytest.mark.spec("SDB-55")
class TestTheGermanCompanyIsTheSupplier:
    """Of several companies under 1.3, the supplier is the German one."""

    def test_the_national_contact_behind_a_foreign_maker(self) -> None:
        """One supplier names its Danish maker first, with its telephone behind "Tlf."."""
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
            "Nordwerk Farben Danmark A/S\nMustervej 300\nDK-2860 Søborg\n"
            "Tlf.: +46 39 62 94 00\n"
            "E-Mail-Adresse der verantwortlichen Person für dieses SDB: "
            "Produkt.Sicherheit.Europa@nordwerk.example\n"
            "Nationaler Kontakt\nNordwerk Farben Deutschland GmbH\nFeldstr. 5 A\n"
            "47684 Bochum\nTel: +49 (0)534 879 0\nFax: +49 (0)534 879 376\n"
            "1.4 Notrufnummer\n(+49) - (030) 30686 700 (Giftnotrufzentrale Berlin)"
        )

        assert supplier.supplier_name == "Nordwerk Farben Deutschland GmbH"
        assert supplier.supplier_address == "Feldstr. 5 A, 47684 Bochum"
        assert supplier.supplier_phone == "+49 (0)534 879 0"
        # The German part names no e-mail: the first company's stays.
        assert supplier.supplier_email == "Produkt.Sicherheit.Europa@nordwerk.example"

    def test_a_german_company_below_without_a_heading(self) -> None:
        """One supplier lists a first company, then a second with contacts of its own."""
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\n· Hersteller/Lieferant:\nWisent International\n"
            "Dr.A.B.Musterstraat 9\nNL-4264 EW Stad\ntel. +31 88 3536200\n"
            "e mail: sds@wisent.example\nwww.wisent.example\nULM GmbH\nHofmannstraße 7\n"
            "D-75187 Buchen (Baden)\nTel.:0049-(0)2553-584-0\nemail: sds@ulm.example\n"
            "www.ulm.example\n· Auskunftgebender Bereich: QSUM"
        )

        assert supplier.supplier_name == "ULM GmbH"
        assert supplier.supplier_address == "Hofmannstraße 7, D-75187 Buchen (Baden)"
        assert supplier.supplier_phone == "0049-(0)2553-584-0"
        assert supplier.supplier_email == "sds@ulm.example"
        assert supplier.supplier_website == "www.ulm.example"

    def test_a_german_company_behind_a_second_label(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nHersteller: Muster AG\nIndustriestrasse 1\n"
            "CH-8000 Zürich\nTel.: +41 44 153 46 72\n"
            "Lieferant: Muster Deutschland GmbH\nHauptstraße 1\nDE-12345 Musterstadt\n"
            "Tel.: +49 30 1534672"
        )

        assert supplier.supplier_name == "Muster Deutschland GmbH"
        assert supplier.supplier_address == "Hauptstraße 1, DE-12345 Musterstadt"
        assert supplier.supplier_phone == "+49 30 1534672"

    @pytest.mark.parametrize(
        "town",
        [
            "D-42426 Oststadt",
            "42426 Oststadt",
            "D - 42426 Oststadt",
            "Oststadt\nGermany",
        ],
    )
    def test_a_german_company_first_stays(self, town: str) -> None:
        """One supplier lists its Swiss parent below."""
        supplier = _supplier(
            f"1.3 Einzelheiten zum Lieferanten\nUlmenwerk GmbH\nMüllerstraße 8\n{town}\n"
            "Tel.: +49(0)5041 79090\nMuster Deutschland GmbH\nHauptstraße 1\n"
            "12345 Musterstadt\nTel.: +49 30 1534672"
        )

        assert supplier.supplier_name == "Ulmenwerk GmbH"
        assert supplier.supplier_phone == "+49(0)5041 79090"

    def test_no_german_company_leaves_the_first(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nMuster B.V.\nMusterstraat 11\n"
            "4309 RC Oosterstad\nTel.: +31 175 491 000\nMuster Trading Ltd.\n"
            "Mill House, Old Mill Road\nHigh Muster, HM13 6XY\nTel.: +44 8000 363327"
        )

        assert supplier.supplier_name == "Muster B.V."
        assert supplier.supplier_address == "Musterstraat 11, 4309 RC Oosterstad"

    def test_a_first_company_without_an_address_stays(self) -> None:
        """Where it lies is unknown: nothing says it is abroad."""
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nMuster International\nTel.: +31 175 491 000\n"
            "Muster Deutschland GmbH\nHauptstraße 1\n12345 Musterstadt"
        )

        assert supplier.supplier_name == "Muster International"

    def test_a_company_of_the_emergency_part_is_not_the_supplier(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nMuster B.V.\nMusterstraat 11\n"
            "4309 RC Oosterstad\nTel.: +31 175 491 000\n"
            "Notrufnummer\nGiftinformation Muster GmbH\nKlinikstraße 1\n12345 Musterstadt"
        )

        assert supplier.supplier_name == "Muster B.V."

    def test_a_department_named_with_a_colon_is_no_company(self) -> None:
        supplier = _supplier(
            "1.3 Einzelheiten zum Lieferanten\nMuster B.V.\nMusterstraat 11\n"
            "4309 RC Oosterstad\nTel.: +31 175 491 000\n"
            "Auskunftgebender Bereich: Chemieberatung GmbH\nOskar-Muster-Str. 36\n"
            "D-41618 Münster"
        )

        assert supplier.supplier_name == "Muster B.V."


@pytest.mark.spec("SDB-50")
def test_a_poison_centres_number_is_never_the_suppliers() -> None:
    """One supplier's section 1 reaches the text out of order, with no label above it."""
    supplier = _supplier(
        "1.3 Einzelheiten zum Lieferanten\nFirma: ALPENINNO SOLUTIONS AG\n"
        "9000 St. Bergen, Switzerland\n+41 71 556 40 17\nTel.: +49 (0)30 19240"
    )

    assert supplier.supplier_address == "9000 St. Bergen, Switzerland"
    assert supplier.supplier_phone is None


@pytest.mark.spec("SDB-51")
class TestAStatementEndsWithItsWording:
    """Where the regulation's wording ends, the statement does."""

    @staticmethod
    def _texts(label: str) -> tuple[str | None, str | None, str | None]:
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n2.2 Kennzeichnungselemente\n"
            + label
            + "\n2.3 Sonstige Gefahren\nKeine.\n"
        )
        hazards = SDSParser().parse(_build_extraction(text)).sheet.hazard_statements
        return (
            hazards.hazard_text,
            hazards.precautionary_text,
            hazards.supplemental_text,
        )

    def test_text_behind_the_wording_belongs_to_no_statement(self) -> None:
        _, precautionary, supplemental = self._texts(
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen.\n"
            "Beratung für Allergiker: Hotline 0180 / 630 89 58\n"
            "P501 Inhalt/Behälter einer anerkannten Abfallentsorgungsanlage zuführen.\n"
            "Enthält Aluminiumsulfat, Eisensulfat Heptahydrat."
        )

        assert supplemental == (
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen."
        )
        assert precautionary == (
            "P501 Inhalt/Behälter einer anerkannten Abfallentsorgungsanlage zuführen."
        )

    def test_a_choice_ends_at_its_fixed_words(self) -> None:
        _, precautionary, _ = self._texts(
            "P280 Schutzhandschuhe/Augenschutz tragen.\nGefährliche Inhaltsstoffe: Aceton"
        )

        assert precautionary == "P280 Schutzhandschuhe/Augenschutz tragen."

    def test_the_sheets_own_sentence_on_the_line_stays(self) -> None:
        """One sheet's P501 and another's P280 say more than the regulation."""
        _, precautionary, _ = self._texts(
            "P280 Schutzhandschuhe tragen. Augenschutz oder Gesichtsschutz tragen.\n"
            "P501\n"
            "Behälter nur völlig restentleert der Wertstoffsammlung zuführen! Größere "
            "Produktreste zur Problemstoffsammelstelle\nbringen.\nKeine weiteren Angaben."
        )

        assert precautionary == (
            "P280 Schutzhandschuhe tragen. Augenschutz oder Gesichtsschutz tragen.\n"
            "P501 Behälter nur völlig restentleert der Wertstoffsammlung zuführen! "
            "Größere Produktreste zur Problemstoffsammelstelle bringen."
        )

    def test_a_wording_that_begins_again_and_does_not_end_is_none(self) -> None:
        _, _, supplemental = self._texts(
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen.\n"
            "Enthält Aluminiumsulfat, Eisensulfat Heptahydrat"
        )

        assert supplemental == (
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen."
        )

    def test_a_bracket_behind_the_wording_is_part_of_it(self) -> None:
        _, precautionary, _ = self._texts(
            "P321 Besondere Behandlung (siehe zusätzliche Erste-Hilfe-Angaben auf "
            "diesem Kennzeichnungsetikett).\nWeiteres."
        )

        assert precautionary is not None
        assert precautionary.endswith("Kennzeichnungsetikett).")

    @pytest.mark.spec("SDB-53")
    def test_a_code_in_brackets_behind_its_sentence(self) -> None:
        _, _, supplemental = self._texts(
            "Zur Vermeidung von Risiken für Mensch und Umwelt die Gebrauchsanleitung "
            "einhalten. (EUH401)\nMittel nicht in Gewässer gelangen lassen. (SP1)"
        )

        assert supplemental == (
            "EUH401 Zur Vermeidung von Risiken für Mensch und Umwelt die "
            "Gebrauchsanleitung einhalten."
        )

    @pytest.mark.spec("SDB-53")
    def test_a_suppliers_mark_on_the_code_goes(self) -> None:
        _, precautionary, supplemental = self._texts(
            "P264.1 Nach Gebrauch Hände gründlich waschen.\n"
            "(EUH208) Enthält Linalool. Kann allergische Reaktionen hervorrufen."
        )

        assert precautionary == "P264 Nach Gebrauch Hände gründlich waschen."
        assert supplemental == (
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen."
        )

    @pytest.mark.spec("SDB-54")
    def test_a_names_own_hyphen_survives_the_page_break(self) -> None:
        _, _, supplemental = self._texts(
            "EUH208 Enthält 5-Chlor-2-methyl-2H-isothiazol-3-on und 2-Methyl-\n"
            "Seite 2 von 9\n"
            "2H-isothiazol-3-on (3:1). Kann allergische Reaktionen hervorrufen."
        )

        assert supplemental is not None
        assert "2-Methyl-2H-isothiazol-3-on" in supplemental

    @pytest.mark.spec("SDB-54")
    @pytest.mark.parametrize(
        ("printed", "joined"),
        [
            (
                "EUH208 Enthält 2-Methyl-1,2-benzothiazol-3\n(2H)-on. Kann allergische "
                "Reaktionen hervorrufen.",
                "2-Methyl-1,2-benzothiazol-3(2H)-on.",
            ),
            (
                "P280 Haut-\nund Augenschutz tragen.",
                "P280 Haut- und Augenschutz tragen.",
            ),
        ],
    )
    def test_a_name_broken_at_the_line_end_is_joined(
        self, printed: str, joined: str
    ) -> None:
        _, precautionary, supplemental = self._texts(printed)

        assert joined in (precautionary or supplemental or "")

    def test_a_wording_begun_again_has_to_end_again(self) -> None:
        """It is no second substance of EUH208: a sentence of its own (SDB-56)."""
        _, _, supplemental = self._texts(
            "EUH208 Enthält D-Limonene. Kann allergische Reaktionen hervorrufen.\n"
            "Enthält 6,8 Massenprozent entzündbare Bestandteile."
        )

        assert supplemental == (
            "EUH208 Enthält D-Limonene. Kann allergische Reaktionen hervorrufen.\n"
            "Enthält 6,8 Massenprozent entzündbare Bestandteile."
        )

    def test_a_second_substance_behind_a_page_break_goes_on(self) -> None:
        _, _, supplemental = self._texts(
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen.\n"
            "3 / 12\n"
            "Enthält Citral. Kann allergische Reaktionen hervorrufen."
        )

        assert supplemental == (
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen. "
            "Enthält Citral. Kann allergische Reaktionen hervorrufen."
        )

    @pytest.mark.spec("SDB-53")
    def test_a_sentence_over_two_lines_with_its_code_behind_it(self) -> None:
        _, _, supplemental = self._texts(
            "Besondere Vorschriften\n"
            "Zur Vermeidung von Risiken für Mensch und Umwelt die\n"
            "Gebrauchsanleitung einhalten. (EUH401)"
        )

        assert supplemental == (
            "EUH401 Zur Vermeidung von Risiken für Mensch und Umwelt die "
            "Gebrauchsanleitung einhalten."
        )

    @pytest.mark.spec("SDB-53")
    def test_a_mark_alone_on_the_codes_line_leaves_one_space(self) -> None:
        hazard, precautionary, _ = self._texts(
            "H361d-Kann vermutlich das Kind im Mutterleib schädigen.\n"
            "P264.1\nNach Gebrauch Hände gründlich waschen."
        )

        assert hazard == "H361-Kann vermutlich das Kind im Mutterleib schädigen."
        assert precautionary == "P264 Nach Gebrauch Hände gründlich waschen."

    def test_a_second_substance_goes_on(self) -> None:
        _, _, supplemental = self._texts(
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen. "
            "Enthält Citral. Kann allergische Reaktionen hervorrufen."
        )

        assert supplemental == (
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen. "
            "Enthält Citral. Kann allergische Reaktionen hervorrufen."
        )

    def test_the_holes_content_behind_a_colon_goes_on(self) -> None:
        _, precautionary, _ = self._texts(
            "P370+P378 Bei Brand: Zum Löschen verwenden: Wassernebel, Schaum."
        )

        assert precautionary == (
            "P370+P378 Bei Brand: Zum Löschen verwenden: Wassernebel, Schaum."
        )

    def test_a_list_ends_with_its_last_codes_wording(self) -> None:
        hazard, _, _ = self._texts(
            "H222, H229: Extrem entzündbares Aerosol. Behälter steht unter Druck: "
            "Kann bei Erwärmung bersten.\nGHS07"
        )

        assert hazard == (
            "H222, H229: Extrem entzündbares Aerosol. Behälter steht unter Druck: "
            "Kann bei Erwärmung bersten."
        )

    @pytest.mark.parametrize(
        "printed", ["P305+P351+\nP338 BEI KONTAKT", "P305 + P351\n+ P338\nBEI KONTAKT"]
    )
    def test_a_combination_broken_over_two_lines_is_one(self, printed: str) -> None:
        _, precautionary, _ = self._texts(
            printed + " MIT DEN AUGEN: Einige Minuten lang behutsam mit Wasser spülen."
        )

        assert precautionary is not None
        assert precautionary.startswith("P305")
        assert "P338" in precautionary.split("\n")[0]
        assert len(precautionary.split("\n")) == 1


@pytest.mark.spec("SDB-51")
def test_a_second_statement_on_the_line_stands_on_its_own() -> None:
    text = (
        "ABSCHNITT 2: Mögliche Gefahren\n2.2 Kennzeichnungselemente\n"
        "P101: Ist ärztlicher Rat erforderlich, Verpackung oder Kennzeichnungsetikett "
        "bereithalten. P102: Darf nicht in die Hände von Kindern gelangen.\n"
        "2.3 Sonstige Gefahren\n"
    )

    hazards = SDSParser().parse(_build_extraction(text)).sheet.hazard_statements

    assert hazards.precautionary_text == (
        "P101: Ist ärztlicher Rat erforderlich, Verpackung oder "
        "Kennzeichnungsetikett bereithalten.\n"
        "P102: Darf nicht in die Hände von Kindern gelangen."
    )


def _statement_texts(label: str) -> tuple[str | None, str | None, str | None]:
    text = (
        "ABSCHNITT 2: Mögliche Gefahren\n2.2 Kennzeichnungselemente\n"
        + label
        + "\n2.3 Sonstige Gefahren\nKeine.\n"
    )
    hazards = SDSParser().parse(_build_extraction(text)).sheet.hazard_statements
    return hazards.hazard_text, hazards.precautionary_text, hazards.supplemental_text


@pytest.mark.spec("SDB-52")
class TestCodesPrintedApartFromTheirWordings:
    """A row or a column of codes takes the sheet's sentences, all or none."""

    def test_a_column_of_codes_over_the_paragraph_of_their_wordings(self) -> None:
        """The paragraph was read as P501's wording."""
        _, precautionary, _ = _statement_texts(
            "Sicherheitshinweise\nP101\nP102\nP264\nP501\n"
            "Ist ärztlicher Rat erforderlich, Verpackung oder Kennzeichnungsetikett "
            "bereithalten. Darf\nnicht in die Hände von Kindern gelangen.\n"
            "Nach Gebrauch Hände gründlich waschen.\n"
            "Inhalt/Behälter in Übereinstimmung mit örtlichen Vorschriften der "
            "Entsorgung zuführen."
        )

        assert precautionary == (
            "P101 Ist ärztlicher Rat erforderlich, Verpackung oder "
            "Kennzeichnungsetikett bereithalten.\n"
            "P102 Darf nicht in die Hände von Kindern gelangen.\n"
            "P264 Nach Gebrauch Hände gründlich waschen.\n"
            "P501 Inhalt/Behälter in Übereinstimmung mit örtlichen Vorschriften der "
            "Entsorgung zuführen."
        )

    def test_a_list_of_codes_under_the_wordings(self) -> None:
        """The wordings stand under the label's own headings."""
        _, precautionary, _ = _statement_texts(
            "Sicherheitshinweise\n"
            "Allgemein: Darf nicht in die Hände von Kindern gelangen.\n"
            "Prävention: Schutzhandschuhe tragen. Augenschutz oder Gesichtsschutz tragen. Nach\n"
            "Gebrauch gründlich waschen.\n"
            "Reaktion: BEI EINATMEN: Bei Unwohlsein GIFTINFORMATIONSZENTRUM oder Arzt anrufen.\n"
            "Lagerung: An einem gut belüfteten Ort aufbewahren. Behälter dicht\n"
            "verschlossen halten.\n"
            "Entsorgung: Inhalt und Behälter in Übereinstimmung mit allen lokalen "
            "Gesetzen entsorgen.\n"
            "P102, P280, P264, P304 + P312,\nP403 + P233, P501\n"
            "Gefährliche Inhaltsstoffe: Aceton"
        )

        assert precautionary == (
            "P102 Darf nicht in die Hände von Kindern gelangen.\n"
            "P280 Schutzhandschuhe tragen. Augenschutz oder Gesichtsschutz tragen.\n"
            "P264 Nach Gebrauch gründlich waschen.\n"
            "P304+P312 BEI EINATMEN: Bei Unwohlsein GIFTINFORMATIONSZENTRUM oder Arzt "
            "anrufen.\n"
            "P403+P233 An einem gut belüfteten Ort aufbewahren. Behälter dicht "
            "verschlossen halten.\n"
            "P501 Inhalt und Behälter in Übereinstimmung mit allen lokalen Gesetzen "
            "entsorgen."
        )

    def test_a_list_keeps_its_line_where_a_wording_is_missing(self) -> None:
        _, precautionary, _ = _statement_texts(
            "Allgemein: Darf nicht in die Hände von Kindern gelangen.\n"
            "P102, P501\nGefährliche Inhaltsstoffe: Nicht anwendbar."
        )

        assert precautionary == "P102, P501"

    def test_a_row_of_codes_goes_where_each_has_its_statement(self) -> None:
        _, precautionary, _ = _statement_texts(
            "P102-P280-P501\n"
            "P102 Darf nicht in die Hände von Kindern gelangen.\n"
            "P280 Schutzhandschuhe tragen.\n"
            "P501 Inhalt/Behälter der Problemabfallentsorgung zuführen."
        )

        assert precautionary == (
            "P102 Darf nicht in die Hände von Kindern gelangen.\n"
            "P280 Schutzhandschuhe tragen.\n"
            "P501 Inhalt/Behälter der Problemabfallentsorgung zuführen."
        )

    def test_the_sheets_sentence_under_a_row_stays_with_it(self) -> None:
        hazard, _, _ = _statement_texts(
            "H222-H229\nExtrem entzündbares Aerosol. Behälter steht unter Druck: "
            "Kann bei Erwärmung bersten.\nGHS02"
        )

        assert hazard == (
            "H222-H229 Extrem entzündbares Aerosol. Behälter steht unter Druck: "
            "Kann bei Erwärmung bersten."
        )

    def test_a_label_without_codes_gives_its_sentences(self) -> None:
        """One supplier prints the H statements as sentences alone (SDB-6)."""
        hazard, precautionary, _ = _statement_texts(
            "Gefahrenhinweise: Extrem entzündbares Aerosol. Behälter steht unter Druck: "
            "Kann bei Erwärmung bersten.\nVerursacht schwere Augenreizung.\n"
            "Sicherheitshinweise\n"
            "Allgemein: Darf nicht in die Hände von Kindern gelangen."
        )

        assert hazard == (
            "H222 Extrem entzündbares Aerosol.\n"
            "H229 Behälter steht unter Druck: Kann bei Erwärmung bersten.\n"
            "H319 Verursacht schwere Augenreizung."
        )
        assert precautionary == "P102 Darf nicht in die Hände von Kindern gelangen."

    def test_a_statement_ends_before_the_next_label(self) -> None:
        _, precautionary, _ = _statement_texts(
            "Allgemein: Darf nicht in die Hände von Kindern gelangen.\n"
            "Entsorgung: Inhalt und Behälter gemäß den Gesetzen entsorgen.\n"
            "Gefährliche Inhaltsstoffe: Kohlenwasserstoffe, C11-C14\n"
            "Ergänzende Kennzeichnungselemente: Nicht anwendbar.\n"
            "P102, P501"
        )

        assert precautionary == (
            "P102 Darf nicht in die Hände von Kindern gelangen.\n"
            "P501 Inhalt und Behälter gemäß den Gesetzen entsorgen."
        )

    def test_a_sentence_under_2_3_is_nobodys(self) -> None:
        """ "Behälter kann …" begins like P501 and is not on the label."""
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n2.2 Kennzeichnungselemente\n"
            "Allgemein: Darf nicht in die Hände von Kindern gelangen.\n"
            "Entsorgung des Inhalts/des Behälters gemäß den Vorschriften.\n"
            "P102, P501\n"
            "2.3 Sonstige Gefahren\n"
            "Behälter kann bei Erwärmung über 50 °C bersten.\n"
        )

        hazards = SDSParser().parse(_build_extraction(text)).sheet.hazard_statements

        assert hazards.precautionary_text == "P102, P501"

    def test_a_wording_wrapped_before_its_colon_stays_whole(self) -> None:
        _, precautionary, _ = _statement_texts(
            "Allgemein: Darf nicht in die Hände von Kindern gelangen.\n"
            "Reaktion: Bei Unwohlsein Arzt anrufen. BEI KONTAKT MIT DEN\n"
            "AUGEN: Einige Minuten lang behutsam mit Wasser spülen. Eventuell vorhandene "
            "Kontaktlinsen nach Möglichkeit entfernen. Weiter spülen.\n"
            "P102, P305 + P351 + P338"
        )

        assert precautionary == (
            "P102 Darf nicht in die Hände von Kindern gelangen.\n"
            "P305+P351+P338 BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang behutsam mit "
            "Wasser spülen. Eventuell vorhandene Kontaktlinsen nach Möglichkeit "
            "entfernen. Weiter spülen."
        )

    def test_a_column_of_two_codes(self) -> None:
        hazard, _, _ = _statement_texts(
            "H315\nH319\nVerursacht Hautreizungen.\nVerursacht schwere Augenreizung."
        )

        assert hazard == (
            "H315 Verursacht Hautreizungen.\nH319 Verursacht schwere Augenreizung."
        )

    def test_a_row_stays_where_a_table_left_the_only_wording(self) -> None:
        hazard, _, _ = _statement_texts("H319\nBerechnungsverfahren.\n\nH319, H410")

        assert hazard == "H319 Berechnungsverfahren.\nH319, H410"


@pytest.mark.spec("SDB-56")
class TestAWholeSentenceWithoutACodeBehindAnEuhStatement:
    """Label text without a code stays, on a line of its own."""

    def test_a_sentence_between_two_statements(self) -> None:
        """A spray paint."""
        _, _, supplemental = _statement_texts(
            "· Zusätzliche Angaben:\n"
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "Ohne ausreichende Lüftung Bildung explosionsfähiger Gemische möglich.\n"
            "EUH211 Achtung! Beim Sprühen können gefährliche lungengängige Tröpfchen "
            "entstehen. Aerosol oder Nebel\nnicht einatmen."
        )

        assert supplemental == (
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "Ohne ausreichende Lüftung Bildung explosionsfähiger Gemische möglich.\n"
            "EUH211 Achtung! Beim Sprühen können gefährliche lungengängige Tröpfchen "
            "entstehen. Aerosol oder Nebel nicht einatmen."
        )

    def test_a_sentence_over_two_lines(self) -> None:
        """The warning every grill lighter carries."""
        _, _, supplemental = _statement_texts(
            "Besondere Kennzeichnung bestimmter Gemische\nEUH066\n"
            "Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "Bereits ein kleiner Schluck flüssiger Grillanzünder kann zu einer "
            "lebensbedrohlichen\nSchädigung der Lunge führen."
        )

        assert supplemental == (
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "Bereits ein kleiner Schluck flüssiger Grillanzünder kann zu einer "
            "lebensbedrohlichen Schädigung der Lunge führen."
        )

    def test_the_list_of_biocides_stays_without_a_sentence_end(self) -> None:
        """It begins like EUH208 and is none."""
        _, _, supplemental = _statement_texts(
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen.\n"
            "Enthält Biozidprodukte: Pyridin-2-thiol-1-oxid, Natriumsalz (SODIUM "
            "PYRITHIONE), METHYLCHLOROISOTHIAZOLINONE/\nMETHYLISOTHIAZOLINONE (3:1)\n"
            "(Fortsetzung auf Seite 2)\nSicherheitsdatenblatt Muster\nSeite 2 von 9"
        )

        assert supplemental == (
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen.\n"
            "Enthält Biozidprodukte: Pyridin-2-thiol-1-oxid, Natriumsalz (SODIUM "
            "PYRITHIONE), METHYLCHLOROISOTHIAZOLINONE/ METHYLISOTHIAZOLINONE (3:1)"
        )

    @pytest.mark.parametrize(
        "behind",
        [
            "Ethandiol",
            "UFI: X153-UM4X-M6Q6-K1SE",
            "Reiniger, 648/2004/EG, enthält: < 5% nichtionische Tenside\nDuftstoffe",
            "Beratung für Allergiker: Hotline 0180 / 630 89 58 (0,14 €/ Min)",
            "Kohlenwasserstoffe, C10-C13, n-Alkane, Isoalkane, Cycloalkane, <2% Aromaten",
            "01.06.2017 (D) Version 2.9",
            "Nicht anwendbar.",
        ],
    )
    def test_what_is_no_whole_sentence_goes(self, behind: str) -> None:
        _, _, supplemental = _statement_texts(
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen.\n"
            + behind
        )

        assert supplemental == (
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen."
        )

    def test_a_line_of_one_word_begins_no_sentence(self) -> None:
        _, _, supplemental = _statement_texts(
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen.\n"
            "Bemerkung\nVon Nahrungsmitteln, Getränken und Futtermitteln fernhalten."
        )

        assert supplemental == (
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen.\n"
            "Von Nahrungsmitteln, Getränken und Futtermitteln fernhalten."
        )

    def test_a_sentence_follows_what_is_none(self) -> None:
        """What reaches no sentence end runs into the sentence below it."""
        _, _, supplemental = _statement_texts(
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "Mit Konservierungsmittel behandelte Ware.\n"
            "Enthält: Gemisch aus zwei Isothiazolinonen (3:1)."
        )

        assert supplemental == (
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "Mit Konservierungsmittel behandelte Ware.\n"
            "Enthält: Gemisch aus zwei Isothiazolinonen (3:1)."
        )

    def test_a_heading_ends_what_is_read(self) -> None:
        _, _, supplemental = _statement_texts(
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "Ohne ausreichende Lüftung Bildung explosionsfähiger Gemische möglich.\n"
            "Gefahrbestimmende Komponenten zur Etikettierung:\n"
            "Dieser Satz steht unter einer anderen Überschrift."
        )

        assert supplemental == (
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "Ohne ausreichende Lüftung Bildung explosionsfähiger Gemische möglich."
        )

    def test_a_page_break_ends_what_is_read(self) -> None:
        _, _, supplemental = _statement_texts(
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "Ohne ausreichende Lüftung Bildung explosionsfähiger Gemische möglich.\n"
            "Seite 2 von 9\nDieser Satz steht auf der nächsten Seite."
        )

        assert supplemental == (
            "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n"
            "Ohne ausreichende Lüftung Bildung explosionsfähiger Gemische möglich."
        )

    def test_a_sentence_behind_a_p_statement_is_not_kept(self) -> None:
        _, precautionary, _ = _statement_texts(
            "P102 Darf nicht in die Hände von Kindern gelangen.\n"
            "Ohne ausreichende Lüftung Bildung explosionsfähiger Gemische möglich."
        )

        assert precautionary == "P102 Darf nicht in die Hände von Kindern gelangen."

    def test_a_statement_that_is_not_whole_takes_the_line(self) -> None:
        """SDB-27 still holds before the wording is complete."""
        _, _, supplemental = _statement_texts(
            "EUH208 Enthält Linalool. Kann allergische\nReaktionen hervorrufen."
        )

        assert supplemental == (
            "EUH208 Enthält Linalool. Kann allergische Reaktionen hervorrufen."
        )


@pytest.mark.spec("SDB-53")
class TestWhatATableLeavesUnderACode:
    def test_a_line_that_does_not_begin_the_wording_goes(self) -> None:
        """2.1's table in the file's order: "H410" over "Berechnungsverfahren."."""
        hazard, _, _ = _statement_texts(
            "H410\nBerechnungsverfahren.\n\n"
            "Gefahrenhinweise\n"
            "H410 Sehr giftig für Wasserorganismen mit langfristiger Wirkung."
        )

        assert (
            hazard == "H410 Sehr giftig für Wasserorganismen mit langfristiger Wirkung."
        )

    def test_it_stays_where_the_code_has_no_other_statement(self) -> None:
        hazard, _, _ = _statement_texts("H410\nBerechnungsverfahren.")

        assert hazard == "H410 Berechnungsverfahren."

    def test_the_first_half_of_a_statement_cut_by_a_column_goes(self) -> None:
        hazard, _, _ = _statement_texts(
            "H410 Sehr giftig für Wasserorganismen, mit lang-\n\n"
            "H410 Sehr giftig für Wasserorganismen, mit langfristiger Wirkung."
        )

        assert hazard == (
            "H410 Sehr giftig für Wasserorganismen, mit langfristiger Wirkung."
        )

    def test_a_whole_statement_stays_beside_a_longer_one(self) -> None:
        hazard, _, _ = _statement_texts(
            "H315 Verursacht Hautreizungen.\n\n"
            "H315 Verursacht Hautreizungen. Nicht eingestuft nach GHS."
        )

        assert hazard == (
            "H315 Verursacht Hautreizungen.\n"
            "H315 Verursacht Hautreizungen. Nicht eingestuft nach GHS."
        )

    @pytest.mark.spec("SDB-108")
    def test_a_wording_that_ends_in_a_hole_ends_with_its_sentence(self) -> None:
        """2.1's table sets the method and the next class under the statement."""
        hazard, _, _ = _statement_texts(
            "H373: Kann die Organe schädigen bei längerer\n"
            "oder wiederholter Exposition.\nBerechnung\n"
            "Akute Toxizität (oral) (Acute Tox. 4)\n"
            "H302: Gesundheitsschädlich bei Verschlucken."
        )

        assert hazard == (
            "H373: Kann die Organe schädigen bei längerer oder wiederholter "
            "Exposition.\nH302: Gesundheitsschädlich bei Verschlucken."
        )

    @pytest.mark.spec("SDB-108")
    @pytest.mark.parametrize(
        "filling",
        [
            "(Zielorgan(e): Nieren;\nExpositionsweg(e): Einatmen, Hautkontakt.)",
            "Blut\nExpositionsweg: oral",
        ],
    )
    def test_what_fills_the_hole_stays(self, filling: str) -> None:
        hazard, _, _ = _statement_texts(
            "H373\nKann die Organe schädigen bei längerer oder wiederholter "
            f"Exposition.\n{filling}\nSicherheitshinweise\nP102 Darf nicht in die "
            "Hände von Kindern gelangen."
        )

        assert hazard == (
            "H373 Kann die Organe schädigen bei längerer oder wiederholter "
            "Exposition. " + filling.replace("\n", " ")
        )

    @pytest.mark.spec("SDB-108")
    def test_a_line_of_statements_is_split_behind_such_a_wording(self) -> None:
        hazard, _, _ = _statement_texts(
            "H226-Flüssigkeit und Dampf entzündbar. H373-Kann die Organe schädigen "
            "bei längerer oder wiederholter Exposition. H319-Verursacht schwere "
            "Augenreizung."
        )

        assert hazard == (
            "H226-Flüssigkeit und Dampf entzündbar.\n"
            "H373-Kann die Organe schädigen bei längerer oder wiederholter "
            "Exposition.\nH319-Verursacht schwere Augenreizung."
        )

    @pytest.mark.spec("SDB-108")
    def test_of_two_readings_the_one_that_fills_the_hole_stays(self) -> None:
        hazard, _, _ = _statement_texts(
            "H373: Kann die Organe schädigen bei längerer oder wiederholter "
            "Exposition.\n\n"
            "H373 Kann die Organe schädigen bei längerer oder wiederholter "
            "Exposition durch Verschlucken."
        )

        assert hazard == (
            "H373 Kann die Organe schädigen bei längerer oder wiederholter "
            "Exposition durch Verschlucken."
        )

    @pytest.mark.spec("SDB-109")
    def test_a_statement_ends_before_listed_codes_of_another_kind(self) -> None:
        hazard, _, supplemental = _statement_texts(
            "Gefahrenhinweise: H373 (Blut), EUH210, EUH401"
        )

        assert hazard == "H373 (Blut)"
        assert supplemental == "EUH210, EUH401"

    @pytest.mark.spec("SDB-110")
    def test_the_rest_of_a_broken_label_is_no_word_of_the_statement(self) -> None:
        """ "Ergänzende Gefahrenhin-" before the page break, "weise" after."""
        _, _, supplemental = _statement_texts(
            "Ergänzende Gefahrenhin-: EUH401 Zur Vermeidung von Risiken für Mensch und\n"
            "weise\nUmwelt ist die Gebrauchsanleitung einzuhalten."
        )

        assert supplemental == (
            "EUH401 Zur Vermeidung von Risiken für Mensch und Umwelt ist die "
            "Gebrauchsanleitung einzuhalten."
        )

    def test_the_letter_of_the_effect_behind_the_code_goes(self) -> None:
        hazard, _, _ = _statement_texts(
            "H226 Flüssigkeit und Dampf entzündbar.\n"
            "H361d Kann vermutlich das Kind im Mutterleib schädigen."
        )

        assert hazard == (
            "H226 Flüssigkeit und Dampf entzündbar.\n"
            "H361 Kann vermutlich das Kind im Mutterleib schädigen."
        )


_OLD_SHEET = (
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.1 Einstufung des Stoffs oder Gemischs\n"
    "Einstufung gemäß Richtlinie 67/548/EWG oder Richtlinie 1999/45/EG\n"
    "Xn; Gesundheitsschädlich\n"
    "R20/21/22: Gesundheitsschädlich beim Einatmen, Verschlucken und Berührung mit der Haut.\n"
    "2.2 Kennzeichnungselemente\n"
    "Kennbuchstabe und Gefahrenbezeichnung des Produktes:\n"
    "Xn Gesundheitsschädlich\n"
    "R-Sätze:\n"
    "33\n"
    "Gefahr kumulativer Wirkungen.\n"
    "S-Sätze:\n"
    "28\n"
    "Bei Berührung mit der Haut sofort abwaschen mit viel Wasser\n"
    "2.3 Sonstige Gefahren\n"
    "Keine.\n"
)


@pytest.mark.spec("SDB-73")
class TestASheetClassifiedUnderTheOldDirectives:
    """Before CLP a sheet stated its hazards as R phrases and hazard symbols."""

    def test_no_label_is_read_out_of_r_and_s_phrases(self, parser: SDSParser) -> None:
        """ "Gefahr kumulativer Wirkungen" gave the signal word, the S phrase P302."""
        hazards = parser.parse(_build_extraction(_OLD_SHEET)).sheet.hazard_statements
        assert hazards == HazardStatements()

    def test_the_parser_says_what_it_found(self, parser: SDSParser) -> None:
        warnings = parser.parse(_build_extraction(_OLD_SHEET)).warnings
        assert [w for w in warnings if w.code == "classified-before-clp"] == [
            Message("classified-before-clp", {"basis": "R20/21/22"})
        ]

    @pytest.mark.parametrize(
        ("section", "found"),
        [
            (
                "Einstufung\nXi - Reizend\nWichtigste Gefahren\nReizt die Augen.",
                "Xi - Reizend",
            ),
            ("R-Sätze:\n11\nLeichtentzündlich.", "R-Sätze: 11"),
            (
                "Einstufung gemäß Richtlinie 1999/45/EG\nEisensulfat 10 - 25% Xn;R22",
                "R22",
            ),
            (
                "Reizend\nXi\nR11\nLeichtentzündlich\nR19\nKann explosionsfähige Peroxide bilden",
                "R11",
            ),
        ],
    )
    def test_the_forms_of_an_old_classification(self, section: str, found: str) -> None:
        assert old_classification(section) == found

    @pytest.mark.parametrize(
        "section",
        [
            # Names the old rules and states no hazard under them.
            "Einstufung gemäß Richtlinien 67/548/EWG und 1999/45/EG:\nR0\nkeine R-Sätze",
            "Gefahrensymbole: Entfällt\nR-Sätze:: ---\nS-Sätze:",
            # A product's name and a refrigerant are no R phrase.
            "ABCDE R 1\nSicherheitsdatenblatt\ngemäß Verordnung (EU) 2015/830",
            "Kältemittel R22 und R32",
        ],
    )
    def test_what_is_no_old_classification(self, section: str) -> None:
        assert old_classification(section) is None

    def test_a_sheet_of_both_systems_keeps_its_clp_label(
        self, parser: SDSParser
    ) -> None:
        """Between 2010 and 2015 sheets printed both; the CLP label is the one to read."""
        text = (
            "ABSCHNITT 2: Mögliche Gefahren\n"
            "2.1 Einstufung des Stoffs oder Gemischs\n"
            "Einstufung gemäß Richtlinie 1999/45/EG\n"
            "Entzündlich R10\n"
            "2.2 Kennzeichnungselemente\n"
            "R-Sätze (1999/45/EG)\n"
            "R 10 Entzündlich.\n"
            "Signalwort: Achtung\n"
            "H226 Flüssigkeit und Dampf entzündbar.\n"
            "P210 Von Hitze, heißen Oberflächen, Funken, offenen Flammen und anderen Zündquellen fernhalten. Nicht rauchen.\n"
            "2.3 Sonstige Gefahren\n"
            "Keine.\n"
        )
        result = parser.parse(_build_extraction(text))
        assert result.sheet.hazard_statements.hazard_codes == ["H226"]
        assert result.sheet.hazard_statements.signal_word == "Achtung"
        assert not [w for w in result.warnings if w.code == "classified-before-clp"]

    def test_a_sheet_without_an_r_phrase_keeps_what_its_label_prints(
        self, parser: SDSParser
    ) -> None:
        text = _label(
            "Einstufung gemäß Richtlinie 67/548/EWG: entfällt\n"
            "R-Sätze: keine\n"
            "P102 Darf nicht in die Hände von Kindern gelangen."
        )
        hazards = parser.parse(_build_extraction(text)).sheet.hazard_statements
        assert hazards.precautionary_codes == ["P102"]


@pytest.mark.spec("SDB-75")
class TestWhatSection2SaysAboutTheClassification:
    """REACH Article 31(1) asks whether the product is classified; 2.1 answers."""

    @pytest.mark.parametrize(
        "part",
        [
            "Einstufung gemäß Verordnung (EG) Nr. 1272/2008\nEye Irrit. 2 H319 Verursacht schwere Augenreizung.",
            "Aquatic Chronic 3: H412 Schädlich für Wasserorganismen, mit langfristiger Wirkung.",
            "Sensibilisierung der Haut\nKategorie 1\nH317 Kann allergische Hautreaktionen verursachen.",
            "Skin Corr. 1B\nEye Dam. 1",
            "Gefahrenkategorien:\nEntzündbare Flüssigkeiten: Entz. Fl. 2\nSchwere Augenschädigung/Augenreizung: Augenreiz. 2",
        ],
    )
    def test_a_hazard_class_says_classified(self, part: str) -> None:
        section = (
            "Mögliche Gefahren\n2.1 Einstufung des Stoffs oder Gemischs\n"
            f"{part}\n2.2 Kennzeichnungselemente\nSignalwort: Achtung\n"
        )
        assert stated_classification(section) is StatedClassification.CLASSIFIED

    @pytest.mark.parametrize(
        "part",
        [
            "Der Stoff ist gemäß CLP-Verordnung nicht eingestuft.",
            "Das Gemisch erfüllt nicht die Kriterien für die Einstufung gemäß der Verordnung (EG) Nr. 1272/2008 [CLP].",
            "Dieses Produkt ist keiner Gefahrenkategorie zugeordnet.",
            "Keine gefährliche Substanz oder Mischung.",
            "Der Stoff ist als nicht gefährlich eingestuft im Sinne der Verordnung (EG) Nr. 1272/2008 [CLP].",
            "Das Produkt wird gemäß CLP-Verordnung 1272/2008/EG nicht als gefährlich erachtet.",
            "Einstufung gemäß Verordnung (EG) Nr. 1272/2008 entfällt",
            "Es handelt sich um ein Erzeugnis.",
            "Verordnung (EG) Nr. 1272/2008: Keine",
            "Keine.",
            "nicht relevant",
        ],
    )
    def test_the_known_wordings_say_not_classified(self, part: str) -> None:
        section = (
            "Mögliche Gefahren\n2.1 Einstufung des Stoffs oder Gemischs\n"
            f"{part}\n2.2 Kennzeichnungselemente\nGefahrenhinweise: keine\n"
        )
        assert stated_classification(section) is StatedClassification.NOT_CLASSIFIED

    @pytest.mark.parametrize(
        "part",
        [
            # About the ingredients, not the product (SDB-80).
            "Das Produkt enthält Stoffe, die als Akut Toxisch (Gefahrenkategorie 4) gelten.",
            # The bare word is no entry.
            "Zur Kategorie 2 liegen keine Angaben vor.",
        ],
    )
    def test_the_parser_does_not_guess(self, part: str) -> None:
        section = (
            "Mögliche Gefahren\n2.1 Einstufung des Stoffs oder Gemischs\n"
            f"{part}\n2.2 Kennzeichnungselemente\n"
        )
        assert stated_classification(section) is StatedClassification.NOT_STATED

    @pytest.mark.spec("SDB-80")
    @pytest.mark.parametrize(
        "part",
        [
            "CLP Einstufung (1272/2008/EG): Reizwirkung auf die Haut, Kategorie 2. Sensibilisierung der Haut, kategorie 1.",
            "nach Verordnung (EG) Nr. 1272/2008\nKorrosiv gegenüber Metallen (Kategorie 1)\nSchwere Augenreizung (Kategorie 2)",
            "Akute Toxizität, Kategorie 4",
            "Das gemischte Produkt ist gemäß VO1272/2008EG als Hautreizend (Gefahrenkategorie 2)\neingestuft.",
        ],
    )
    def test_a_hazard_class_written_out_says_classified(self, part: str) -> None:
        section = (
            "Mögliche Gefahren\n2.1 Einstufung des Stoffs oder Gemischs\n"
            f"{part}\n2.2 Kennzeichnungselemente\n"
        )
        assert stated_classification(section) is StatedClassification.CLASSIFIED

    @pytest.mark.spec("SDB-80")
    def test_a_category_of_the_ingredients_does_not_classify_the_product(self) -> None:
        """The product is not classified, some of what it holds is."""
        section = (
            "Mögliche Gefahren\n"
            "Das Produkt hat gemäß VO1272/2008EG keine Gefahreneinstufung.\n"
            "Das Produkt enthält in geringen Konzentrationen Stoffe, die gemäß Richtlinie 1272/2008EG als\n"
            "Akut Toxisch (Gefahrenkategorie 4), sowie Reizend für Haut und Augen (Gefahrenkategorie 2)\n"
            "eingestuft sind.\n"
        )
        assert stated_classification(section) is StatedClassification.NOT_CLASSIFIED

    @pytest.mark.spec("SDB-81")
    @pytest.mark.parametrize(
        "part",
        [
            # The category in a table cell of its own.
            "Einstufung (VERORDNUNG (EG) Nr. 1272/2008)\nÄtz-/Reizwirkung auf die Haut, 2\nSchwere Augenschädigung/-reizung,\nKategorie 1",
            "Ätz-/Reizwirkung auf die Haut, Kategorie\n2",
            "Gefahreneinstufung\nAerosol\nKategorie 1\nExtrem entzündbares Aerosol.",
            "Gefahrenkategorien:\nEntzündbare Feststoffe: Entz. Festst. 1\nGefahrenhinweise:\nEntzündbarer Feststoff.",
            "Gefahrenkategorien:\nGewässergefährdend: Aqu. chron. 3",
            "Gefahrklasse: Eye Irrit. Gefahrenkategorie 2",
            "Das Gemisch ist als gefährlich eingestuft im Sinne der Verordnung (EG) Nr. 1272/2008 [CLP].",
        ],
    )
    def test_more_forms_of_a_classification(self, part: str) -> None:
        section = (
            "Mögliche Gefahren\n2.1 Einstufung des Stoffs oder Gemischs\n"
            f"{part}\n2.2 Kennzeichnungselemente\n"
        )
        assert stated_classification(section) is StatedClassification.CLASSIFIED

    @pytest.mark.spec("SDB-80")
    @pytest.mark.parametrize(
        ("part", "expected"),
        [
            # The category as a bare number.
            (
                "Einstufung (VERORDNUNG (EG) Nr. 1272/2008)\n"
                "Ätz-/Reizwirkung auf die Haut, 2\nSchwere Augenschädigung/-reizung, 1",
                StatedClassification.CLASSIFIED,
            ),
            (
                "Spezifische Zielorgan-Toxizität - einmalige Exposition, 3",
                StatedClassification.CLASSIFIED,
            ),
            # Not a line of its own, and a sentence.
            (
                "Das Produkt ist nicht eingestuft, 2 Gebinde.",
                StatedClassification.NOT_CLASSIFIED,
            ),
            # About its ingredients (SDB-80).
            (
                "Nicht eingestuft. Das Produkt enthält\nReizwirkung auf die Haut, 2",
                StatedClassification.NOT_CLASSIFIED,
            ),
        ],
    )
    def test_a_hazard_class_with_a_bare_number(
        self, part: str, expected: StatedClassification
    ) -> None:
        section = (
            "Mögliche Gefahren\n2.1 Einstufung des Stoffs oder Gemischs\n"
            f"{part}\n2.2 Kennzeichnungselemente\n"
        )
        assert stated_classification(section) is expected

    @pytest.mark.spec("SDB-81")
    @pytest.mark.parametrize(
        "part",
        [
            "Bei diesem Produkt handelt es sich um ein kosmetisches Mittel, das als Fertigerzeugnis für den\nVerbraucher bestimmt ist.",
            "Verordnung Nr. 1272/2008 (CLP): Keine gefährliche Zubereitung im Sinne der gültigen Fassung",
            "Richtlinie 67/548/EWG bzw. 1999/45/EG\n-\nVerordnung (EG) Nr. 1272/2008 (GHS)\n-",
            "Gefahrenbezeichnung: keine gemäß CLP-Verordnung (EG) Nr. 1272/2008",
            "Keine besonderen Gefahren bekannt.",
            "Das Produkt hat bei Beachtung der Anwendungshinweise keine gesundheitsschädliche Wirkung.",
            "Das Gemisch ist nicht als gefährlich eingestuft im Sinne der Verordnung (EG) Nr. 1272/2008.",
        ],
    )
    def test_more_forms_of_no_classification(self, part: str) -> None:
        section = (
            "Mögliche Gefahren\n2.1 Einstufung des Stoffs oder Gemischs\n"
            f"{part}\n2.2 Kennzeichnungselemente\n"
        )
        assert stated_classification(section) is StatedClassification.NOT_CLASSIFIED

    @pytest.mark.spec("SDB-81", "SDB-77")
    def test_not_subject_to_classification(self) -> None:
        """Charvát's bitumen sheeting: no classification heading, and "Gefahr"
        only in running text."""
        section = (
            "Bitumenabdichtungsbahnen als Fertigprodukt unterliegen nicht der\n"
            "Einstufung gemäß der VERORDNUNG (EG) Nr. 1272/2008.\n"
            "2.1 Sonstige Gefahren\n"
            "Beim Handling besteht die Gefahr von Hautverletzungen.\n"
        )
        assert stated_classification(section) is StatedClassification.NOT_CLASSIFIED

    @pytest.mark.spec("SDB-81", "SDB-77")
    def test_not_applicable_as_the_classification(self) -> None:
        """One supplier's alkaline batteries: the old layout, headings that read like
        signal words, and "N/A" where the classification would stand."""
        section = (
            "Achtung:\n\nDie in diesem Materialsicherheitsdatenblatt beschriebenen "
            "Batterien sind dicht verschlossen.\n\nWarnung:\n\nBatterien nicht "
            "aufladen.\n\nGHS Einstufung:\n\nN/A\n"
        )
        assert stated_classification(section) is StatedClassification.NOT_CLASSIFIED

    @pytest.mark.spec("SDB-75")
    @pytest.mark.parametrize(
        ("part", "expected"),
        [
            # H412 in the regulation's words, without its code.
            (
                "Verordnung (EG) Nr. 1272/2008\nGefahrenhinweise: Schädlich für "
                "Wasserorganismen, mit langfristiger Wirkung.",
                StatedClassification.CLASSIFIED,
            ),
            # The sheet's own answer stands.
            (
                "Nicht eingestuft. Verursacht Hautreizungen bei empfindlichen Personen.",
                StatedClassification.NOT_CLASSIFIED,
            ),
            # A precautionary sentence classifies nothing.
            (
                "Darf nicht in die Hände von Kindern gelangen.",
                StatedClassification.NOT_STATED,
            ),
        ],
    )
    def test_the_wording_of_a_hazard_statement_without_its_code(
        self, part: str, expected: StatedClassification
    ) -> None:
        section = (
            "Mögliche Gefahren\n2.1. Einstufung des Stoffs oder Gemischs\n"
            f"{part}\n2.2. Kennzeichnungselemente\n"
        )
        assert stated_classification(section) is expected

    @pytest.mark.spec("SDB-107")
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            # No 2.1 at all.
            (
                "Hinweis zur Kennzeichnung\nDer Stoff ist als nicht gefährlich "
                "eingestuft im Sinne der Verordnung (EG) Nr. 1272/2008 [CLP].",
                StatedClassification.NOT_CLASSIFIED,
            ),
            ("Nicht kennzeichnungspflichtig.", StatedClassification.NOT_CLASSIFIED),
            # A hazard code beside it: no verdict.
            (
                "Nicht kennzeichnungspflichtig.\nH315 Verursacht Hautreizungen.",
                StatedClassification.NOT_STATED,
            ),
            # Nothing of the kind under 2.2.
            (
                "Besondere Kennzeichnung bestimmter Gemische\nEnthält "
                "1,2-benzisothiazolin-3-one. Kann allergische Reaktionen hervorrufen.",
                StatedClassification.NOT_STATED,
            ),
            ("", StatedClassification.NOT_STATED),
        ],
    )
    def test_without_the_heading_the_label_part_answers(
        self, label: str, expected: StatedClassification
    ) -> None:
        section = (
            "Mögliche Gefahren\n2.2. Kennzeichnungselemente\n"
            f"{label}\n2.3. Sonstige Gefahren\nNicht kennzeichnungspflichtig.\n"
        )
        if not label:
            section = section.replace("Nicht kennzeichnungspflichtig.", "Keine.")
        assert stated_classification(section) is expected

    @pytest.mark.spec("SDB-81")
    def test_no_classification_per_kind_of_hazard(self) -> None:
        """With the page header inside the part."""
        section = (
            "2.1 Einstufung des Stoffs oder Gemischs\n"
            "Einstufung gemäß Verordnung (EG) Nr. 1272/2008.\nMUSTER LIFE SCIENCE\n"
            "Physikalische Gefahren:\nKeine Klassifizierung für physikalische Gefahren.\n"
            "Umweltgefahren :\nKeine Klassifizierung für Umweltgefahren.\n"
            "2.2 Kennzeichnungselemente\nNicht kennzeichnungspflichtig.\n"
        )
        assert stated_classification(section) is StatedClassification.NOT_CLASSIFIED

    @pytest.mark.spec("SDB-75")
    @pytest.mark.parametrize(
        ("part", "label", "expected"),
        [
            # Nothing but P102 on its label.
            (
                "Es liegen keine Informationen vor.",
                "Sicherheitshinweise\nP102 Darf nicht in die Hände von Kindern gelangen.",
                StatedClassification.NOT_CLASSIFIED,
            ),
            # The software's sentence in every empty field.
            (
                "Keine Daten verfügbar",
                "Keine Daten verfügbar",
                StatedClassification.NOT_CLASSIFIED,
            ),
            (
                "n.a.",
                "Kennzeichnungspflichtig nach Verordnung (EG) 1272/2008: Nein.",
                StatedClassification.NOT_CLASSIFIED,
            ),
            # Something else stands under the classification.
            (
                "Bemerkung Einstufung und Kennzeichnung basieren auf Untersuchungen. n.a.",
                "Keine Kennzeichnung erforderlich.",
                StatedClassification.NOT_STATED,
            ),
            # Nothing at all under it is no answer either.
            ("", "Keine Daten verfügbar", StatedClassification.NOT_STATED),
        ],
    )
    def test_no_information_on_the_classification(
        self, part: str, label: str, expected: StatedClassification
    ) -> None:
        section = (
            "Mögliche Gefahren\n2.1. Einstufung des Stoffs oder Gemischs\n"
            f"{part}\n2.2. Kennzeichnungselemente\n{label}\n"
        )
        assert stated_classification(section) is expected

    @pytest.mark.spec("SDB-75", "SDB-81")
    @pytest.mark.parametrize(
        ("section", "expected"),
        [
            # Nothing but an EUH code under the classification.
            (
                "2.1 Einstufung des Stoffs oder Gemischs\n"
                "Einstufung gemäß Verordnung (EG) Nr. 1272/2008\nEUH208\n"
                "2.2 Kennzeichnungselemente\nEUH208 - Enthält Terpentinöl.\n",
                StatedClassification.NOT_CLASSIFIED,
            ),
            # A hazard class beside it classifies.
            (
                "2.1 Einstufung des Stoffs oder Gemischs\nSkin Sens. 1 H317\nEUH208\n"
                "2.2 Kennzeichnungselemente\n",
                StatedClassification.CLASSIFIED,
            ),
            # Without the heading the part is the whole section: no verdict.
            (
                "Hochentzündlich. Reizend.\nEUH066 Wiederholter Kontakt kann zu "
                "spröder Haut führen.\n",
                StatedClassification.NOT_STATED,
            ),
            (
                "2.1. Einstufung des Stoffs oder Gemischs\n"
                "Einstufung gemäß Verordnung (EG) Nr. 1272/2008 [CLP]\n"
                "Aufgrund der verfügbaren Daten sind die Einstufungskriterien nicht "
                "erfüllt\n2.2. Kennzeichnungselemente\n",
                StatedClassification.NOT_CLASSIFIED,
            ),
        ],
    )
    def test_an_euh_code_alone_and_criteria_not_met(
        self, section: str, expected: StatedClassification
    ) -> None:
        assert stated_classification(section) is expected

    def test_the_label_is_not_part_of_the_classification(self) -> None:
        """A quartz sand: not classified, and H statements only as advice
        would stand under the label's heading."""
        section = (
            "2.1 Einstufung des Stoffs oder Gemischs\n"
            "Der Stoff ist gemäß CLP-Verordnung nicht eingestuft.\n"
            "2.2 Kennzeichnungselemente\nGefahrenhinweise\nH319 Verursacht schwere Augenreizung.\n"
        )
        assert stated_classification(section) is StatedClassification.NOT_CLASSIFIED

    def test_the_heading_counts_not_its_number(self) -> None:
        section = (
            "2 Mögliche Gefahren\n· Einstufung des Stoffs oder Gemischs\n"
            "· Einstufung gemäß Verordnung (EG) Nr. 1272/2008\n"
            "Eye Dam. 1 H318 Verursacht schwere Augenschäden.\n· Kennzeichnungselemente\n"
        )
        assert stated_classification(section) is StatedClassification.CLASSIFIED

    def test_a_section_without_the_heading_is_read_up_to_the_label(self) -> None:
        section = "Mögliche Gefahren\nDas Produkt hat gemäß VO1272/2008EG keine Gefahreneinstufung.\n"
        assert stated_classification(section) is StatedClassification.NOT_CLASSIFIED

    def test_of_several_sheets_one_classifies_the_product(self) -> None:
        """One supplier's two-component adhesive: one component is not hazardous."""
        section = (
            "2.1. Einstufung des Stoffs oder Gemischs\nEinstufung (CLP):\n"
            "Der Stoff oder das Gemisch ist nicht gefährlich gemäß Verordnung (EG) Nr. 1272/2008 (CLP).\n"
            "2.2. Kennzeichnungselemente\nnicht gefährlich\n"
            "2.1. Einstufung des Stoffs oder Gemischs\nEinstufung (CLP):\n"
            "Akute Toxizität\nKategorie 4\nH332 Gesundheitsschädlich bei Einatmen.\n"
            "2.2. Kennzeichnungselemente\nSignalwort: Achtung\n"
        )
        assert stated_classification(section) is StatedClassification.CLASSIFIED

    @pytest.mark.spec("SDB-73")
    def test_a_classification_under_the_old_directives(self) -> None:
        section = (
            "2.1 Einstufung des Stoffs oder Gemischs\n"
            "Einstufung gemäß Richtlinie 67/548/EWG oder 1999/45/EG\nXi; Reizend\nR36/38\n"
            "2.2 Kennzeichnungselemente\n"
        )
        assert stated_classification(section) is StatedClassification.OLD_SYSTEM

    def test_an_empty_section_states_nothing(self) -> None:
        assert stated_classification("") is StatedClassification.NOT_STATED


_UNCLASSIFIED = (
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.1 Einstufung des Stoffs oder Gemischs\n"
    "Das Gemisch ist nicht als gefährlich eingestuft im Sinne der Verordnung (EG) Nr. 1272/2008.\n"
    "2.2 Kennzeichnungselemente\n"
    "{label}"
    "2.3 Sonstige Gefahren\nKeine.\n"
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
)


class TestALabelOnAnUnclassifiedSheet:
    @pytest.mark.spec("SDB-77")
    @pytest.mark.parametrize(
        "label",
        [
            "Hinweis zur Kennzeichnung\nEs besteht keine Gefahr, wenn die Maßnahmen für die Handhabung eingehalten werden.\n",
            "Gefahr bestimmende Komponente zur Etikettierung\nNicht erforderlich.\n",
        ],
    )
    def test_a_word_of_the_text_is_no_signal_word(
        self, parser: SDSParser, label: str
    ) -> None:
        result = parser.parse(_build_extraction(_UNCLASSIFIED.format(label=label)))

        assert result.sheet.hazard_statements.signal_word is None
        assert any(w.code == "signal-word-not-taken" for w in result.warnings)

    @pytest.mark.spec("SDB-77")
    def test_a_signal_word_beside_a_hazard_statement_stays(
        self, parser: SDSParser
    ) -> None:
        """Where the label prints an H statement, section 2 was read wrongly, not
        the label; the library reports it (SDB-79)."""
        label = "Signalwort: Achtung\nH319 Verursacht schwere Augenreizung.\n"

        result = parser.parse(_build_extraction(_UNCLASSIFIED.format(label=label)))

        assert result.sheet.hazard_statements.signal_word == "Achtung"
        assert result.sheet.hazard_statements.hazard_codes == ["H319"]

    @pytest.mark.spec("SDB-78")
    def test_a_label_the_sheet_declines_is_none(self, parser: SDSParser) -> None:
        """Two suppliers explain why their sealant carries no H317."""
        label = (
            "EUH210\nSicherheitsdatenblatt auf Anfrage erhältlich.\n"
            "Hinweis zur Kennzeichnung\n"
            "OIT liegt in verkapselter Form vor. Eine Kennzeichnung des Silikons mit\n"
            "GHS 07/Achtung/H317 erfolgt daher nicht.\n"
        )

        result = parser.parse(_build_extraction(_UNCLASSIFIED.format(label=label)))

        hazards = result.sheet.hazard_statements
        assert hazards.hazard_codes == []
        assert hazards.signal_word is None
        assert hazards.pictograms == []
        assert hazards.supplemental_codes == ["EUH210"]


@pytest.mark.spec("SDB-69")
class TestTheCountriesASheetIsIssuedFor:
    """Annex II asks for the limits, rules and advisory body of the country of sale."""

    @pytest.mark.parametrize(
        ("text", "countries"),
        [
            ("15.1 Wassergefährdungsklasse: 1 (AwSV)", ["DE"]),
            ("8.1 Arbeitsplatzgrenzwerte nach TRGS 900", ["DE"]),
            ("Expositionsgrenzwerte\nMAK (GKV 2003)", ["AT"]),
            ("Expositionsgrenzwerte\nSUVA", ["CH"]),
            ("TRGS 900 (DE), GKV (AT), SUVA (CH)", ["AT", "CH", "DE"]),
            ("15.1 Vorschriften der Union", []),
        ],
    )
    def test_the_national_rules_name_the_country(
        self, text: str, countries: list[str]
    ) -> None:
        assert sheet_countries(text, "") == countries

    def test_a_printed_country_code_decides_alone(self) -> None:
        """One supplier's Austrian version still prints "Lagerklasse nach TRGS 510"."""
        text = "Version: 3 / AT\nErsetzt Version: - / AT\nLagerklasse nach TRGS 510\n"
        assert sheet_countries(text, "") == ["AT"]

    @pytest.mark.parametrize(
        ("identification", "countries"),
        [
            ("1.4 Notrufnummer\nGiftnotruf Berlin 030/19240", ["DE"]),
            (
                "1.4 Notrufnummer\nVergiftungsinformationszentrale +43 1 406 43 43",
                ["AT"],
            ),
            ("1.4 Notrufnummer\nTox Info Suisse: 145", ["CH"]),
            (
                "Giftnotruf Berlin +49 30 19240\nGiftnotruf Österreich +43 1 406 43 43",
                ["AT", "DE"],
            ),
        ],
    )
    def test_the_advisory_body_of_section_1_names_the_country(
        self, identification: str, countries: list[str]
    ) -> None:
        assert sheet_countries("", identification) == countries

    def test_the_wording_of_a_p_statement_names_no_advisory_body(self) -> None:
        text = "P312 Bei Unwohlsein GIFTINFORMATIONSZENTRUM/Arzt anrufen."
        assert sheet_countries(text, "1.4 Notrufnummer: keine Angaben") == []

    def test_the_parser_puts_them_on_the_sheet(self, parser: SDSParser) -> None:
        text = (
            "ABSCHNITT 1: Bezeichnung des Stoffs\n1.4 Notrufnummer\nGiftnotruf Berlin 030/19240\n"
            + _label("H315 Verursacht Hautreizungen.")
            + "ABSCHNITT 15: Rechtsvorschriften\nWassergefährdungsklasse: 1\n"
        )
        assert parser.parse(_build_extraction(text)).sheet.countries == ["DE"]


@pytest.mark.spec("SDB-117")
class TestTheEmergencyNumber:
    """Subsection 1.4, as sheets print it."""

    SUPPLIER = (
        "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
        "Muster GmbH\nMusterweg 1\n12345 Musterstadt\nTelefon: +49 555 0142-0\n"
    )

    @pytest.mark.parametrize(
        ("block", "number"),
        [
            # Behind the label on its line, as before.
            ("1.4 Notrufnummer: +49 555 0199-0 (24 h)", "+49 555 0199-0 (24 h)"),
            (
                "· Notrufnummer: Giftnotruf Musterstadt +49 555 0190",
                "Giftnotruf Musterstadt +49 555 0190",
            ),
            (
                "Notrufnummer: +49 555 0199-0 (08:30 - 16:30)",
                "+49 555 0199-0 (08:30 - 16:30)",
            ),
            # Under the heading: the first line that carries a number.
            ("1.4 Notrufnummer\n+49 555 0199-0", "+49 555 0199-0"),
            ("1,4 Notrufnummer\nTel +49 555 0199-0", "+49 555 0199-0"),
            (
                "1.4. Notrufnummer\nNotfallinformationsdienst\n+49 555 0199-0\nMo-Fr 08:00 bis 16:00",
                "+49 555 0199-0",
            ),
            (
                "1.4 Notrufnummer\nGiftnotruf Musterstadt (24 h): +49 555 0190",
                "Giftnotruf Musterstadt (24 h): +49 555 0190",
            ),
            # A telephone label goes, a fax behind the number too.
            (
                "Notfallauskunft\nTel.: (05 55) 01 99 0 - Fax: (05 55) 01 99 9",
                "(05 55) 01 99 0",
            ),
            # The label names nobody's number; the line below does.
            (
                "1.4 Notrufnummer: Muster Notdienst GmbH\n+49 555 0199-0",
                "+49 555 0199-0",
            ),
            ("1.4 Notrufnummer\nNotruf in Europa: 112", "112"),
        ],
    )
    def test_it_is_read_from_the_heading_or_the_lines_below(
        self, block: str, number: str
    ) -> None:
        contact = _supplier(self.SUPPLIER + block + "\n")

        assert contact.emergency_phone == number
        assert contact.supplier_phone == "+49 555 0142-0"

    @pytest.mark.parametrize(
        "block",
        [
            "1.4 Notrufnummer: Muster Notdienst GmbH",
            "1.4 Notrufnummer\nsiehe Abschnitt 1.3",
            "1.4 Notrufnummer: nicht notwendig (kein Gefahrstoff)",
            # A registration number, a date and the regulation are no telephone.
            "1.4 Notrufnummer\nRegistrierungsnummer 01-2100000000-00-0000\nStand 01.02.2023\nVerordnung (EG) Nr. 1907/2006",
        ],
    )
    def test_without_a_telephone_number_there_is_none(self, block: str) -> None:
        text = (
            "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
            + self.SUPPLIER
            + block
            + "\nABSCHNITT 2: Mögliche Gefahren\n2.2 Kennzeichnungselemente\nKein Signalwort.\n"
        )
        result = SDSParser().parse(_build_extraction(text))

        assert result.sheet.contact_info.emergency_phone is None
        assert "no-emergency-phone" in [w.code for w in result.warnings]

    def test_the_number_on_the_labels_line_goes_before_lines_under_a_heading(
        self,
    ) -> None:
        """Some files draw the heading of 1.4 above the supplier's block: what
        stands below it then is the office's."""
        contact = _supplier(
            "1.4 Notrufnummer\nBeratung\n"
            + self.SUPPLIER
            + "Notrufnummer: +49 555 0199-0 (24 h)\n"
        )

        assert contact.emergency_phone == "+49 555 0199-0 (24 h)"
        assert contact.supplier_phone == "+49 555 0142-0"

    def test_the_search_ends_at_another_subsections_heading(self) -> None:
        contact = _supplier("1.4 Notrufnummer\n" + self.SUPPLIER)

        assert contact.emergency_phone is None
        assert contact.supplier_phone == "+49 555 0142-0"


@pytest.mark.spec("SDB-175")
def test_a_heading_may_number_its_section_with_a_colon() -> None:
    text = (
        "Sicherheitsdatenblatt\n"
        "ABSCHNITT 1: Bezeichnung des Gemischs und des Unternehmens\n"
        "Handelsname: Musterdünger\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        "Das Gemisch ist nach CLP-Verordnung nicht eingestuft.\n"
        "3: Zusammensetzung / Angaben zu den Bestandteilen\n"
        "Eisen(II)sulfat Monohydrat (2,5-5 %)\n"
        "Akute Toxizität oral, Kategorie 4, H302\n"
    )

    sections = split_sections(text)

    assert "H302" not in sections[Section.HAZARDS]
    assert sections[Section.COMPOSITION].startswith("Eisen(II)sulfat")
    assert read_numbered_section_heading("3: Zusammensetzung") == 3
    # The title still has to agree with the number.
    assert read_numbered_section_heading("4: Zusammensetzung") is None
    assert read_numbered_section_heading("1: Kategorie 2") is None


@pytest.mark.spec("SDB-152")
@pytest.mark.parametrize("mark", ["!", "*"])
def test_a_heading_may_carry_the_mark_of_a_changed_section(mark: str) -> None:
    text = (
        "Sicherheitsdatenblatt\n"
        f"{mark} 1. Bezeichnung des Stoffs und des Unternehmens\n"
        "Handelsname: Musterpflege\n"
        f"{mark} 2. Mögliche Gefahren\n"
        "Einstufung gemäß 67/548/EWG oder 1999/45/EG\n"
        "R10\n"
        f"{mark} R-Sätze\n"
        "10\n"
        "Entzündlich.\n"
        "3. Zusammensetzung/Angaben zu Bestandteilen\n"
        "Gemisch.\n"
    )

    sections = split_sections(text)

    assert sections[Section.HAZARDS].startswith("Einstufung gemäß 67/548/EWG")
    assert old_classification(sections[Section.HAZARDS]) == "R-Sätze 10"


@pytest.mark.spec("SDB-184")
class TestAHeadingSetIntoAStatement:
    """The label's column heading between a statement's lines."""

    def test_a_heading_inside_the_wording_is_passed_over(self) -> None:
        _, _, supplemental = _statement_texts(
            "EUH401 - Zur Vermeidung von Risiken für Mensch und Umwelt die "
            "Gebrauchsanleitung\nEUH Sätze\neinhalten.\n"
            "EUH208 - Enthält Musterol. Kann allergische Reaktionen hervorrufen."
        )

        assert supplemental == (
            "EUH401 - Zur Vermeidung von Risiken für Mensch und Umwelt die "
            "Gebrauchsanleitung einhalten.\n"
            "EUH208 - Enthält Musterol. Kann allergische Reaktionen hervorrufen."
        )

    def test_a_precautionary_statement_too(self) -> None:
        _, precautionary, _ = _statement_texts(
            "P210\nVon Hitze, heißen Oberflächen, Funken, offenen Flammen und "
            "anderen Zündquellen\nSicherheitshinweise\nfernhalten. Nicht rauchen.\n"
            "P280\nSchutzhandschuhe tragen."
        )

        assert precautionary is not None
        assert precautionary.startswith(
            "P210 Von Hitze, heißen Oberflächen, Funken, offenen Flammen und "
            "anderen Zündquellen fernhalten. Nicht rauchen.\n"
        )

    def test_a_heading_after_a_whole_statement_still_ends_it(self) -> None:
        hazard, _, _ = _statement_texts(
            "H315 Verursacht Hautreizungen.\nSicherheitshinweise\nWeiteres Wort."
        )

        assert hazard == "H315 Verursacht Hautreizungen."

    def test_a_heading_the_next_line_does_not_finish_ends_it(self) -> None:
        hazard, _, _ = _statement_texts(
            "H290 Kann gegenüber Metallen\nSicherheitshinweise\nNach Gebrauch waschen."
        )

        assert hazard == "H290 Kann gegenüber Metallen"


@pytest.mark.spec("SDB-200")
class TestAHeadingWithAColonInsideAStatement:
    """The label's column heading with the statement's last words behind it."""

    def test_the_words_behind_the_heading_finish_the_statement(self) -> None:
        _, precautionary, _ = _statement_texts(
            "P101 Ist ärztlicher Rat erforderlich, Verpackung oder\n"
            "Sicherheitshinweise: Kennzeichnungsetikett bereithalten.\n"
            "P102 Darf nicht in die Hände von Kindern gelangen."
        )

        assert precautionary == (
            "P101 Ist ärztlicher Rat erforderlich, Verpackung oder "
            "Kennzeichnungsetikett bereithalten.\n"
            "P102 Darf nicht in die Hände von Kindern gelangen."
        )

    def test_words_that_do_not_finish_it_end_it(self) -> None:
        _, precautionary, _ = _statement_texts(
            "P101 Ist ärztlicher Rat erforderlich, Verpackung oder\n"
            "Sicherheitshinweise: Nach Gebrauch waschen."
        )

        assert precautionary == "P101 Ist ärztlicher Rat erforderlich, Verpackung oder"


@pytest.mark.spec("SDB-185")
class TestATableCellInsideAStatement:
    def test_it_goes_beside_the_labels_whole_statement(self) -> None:
        hazard, _, _ = _statement_texts(
            "H317: Kann allergische Hautreaktionen | Berechnungsmethode. "
            "(Skin Sens. 1) verursachen.\n\n"
            "Gefahrenhinweise\nH317 Kann allergische Hautreaktionen verursachen."
        )

        assert hazard == "H317 Kann allergische Hautreaktionen verursachen."

    def test_it_stays_where_the_code_has_no_whole_statement(self) -> None:
        hazard, _, _ = _statement_texts(
            "H317: Kann allergische Hautreaktionen | Berechnungsmethode. "
            "(Skin Sens. 1) verursachen."
        )

        assert hazard == (
            "H317: Kann allergische Hautreaktionen | Berechnungsmethode. "
            "(Skin Sens. 1) verursachen."
        )

    def test_a_statement_that_lacks_a_word_stays(self) -> None:
        """A deviation of the label is no table cell: it lacks a word."""
        hazard, _, _ = _statement_texts(
            "H317: Kann allergische Hautreaktionen verursachen.\n\n"
            "Gefahrenhinweise\nH317 Kann allergische Hautreaktionen hervorrufen."
        )

        assert hazard == (
            "H317: Kann allergische Hautreaktionen verursachen.\n"
            "H317 Kann allergische Hautreaktionen hervorrufen."
        )


@pytest.mark.spec("SDB-186")
def test_a_misprinted_code_left_alone_goes() -> None:
    _, _, supplemental = _statement_texts(
        "EUH401 Zur Vermeidung von Risiken für Mensch und Umwelt die "
        "Gebrauchsanleitung einhalten.\n"
        "EU208 - Enthält Musterol. Kann\nallergische Reaktionen hervorrufen."
    )

    assert supplemental is not None
    assert "EU208" not in supplemental
    assert "EUH208: Enthält Musterol. Kann allergische Reaktionen hervorrufen." in (
        supplemental
    )


@pytest.mark.spec("SDB-186")
def test_a_code_of_the_regulation_left_alone_stays() -> None:
    _, _, supplemental = _statement_texts(
        "EUH401 Zur Vermeidung von Risiken für Mensch und Umwelt die "
        "Gebrauchsanleitung einhalten.\n"
        "EUH204: Enthält Musterol. Kann\nallergische Reaktionen hervorrufen."
    )

    assert supplemental is not None
    assert "EUH204" in supplemental


@pytest.mark.spec("SDB-201")
class TestADateMonthFirst:
    def test_a_date_only_month_first_is_read_so(self) -> None:
        assert _extract_issue_date("Ausgabedatum: 08/31/2020") == date(2020, 8, 31)

    def test_a_date_either_way_is_read_day_first(self) -> None:
        assert _extract_issue_date("Ausgabedatum: 08/06/2020") == date(2020, 6, 8)

    def test_the_label_split_around_its_date(self) -> None:
        text = "Ausgabedatum/: 08/31/2020\nSeite: 1/19\nÜberarbeitungsdatum"

        assert _extract_issue_date(text) == date(2020, 8, 31)
