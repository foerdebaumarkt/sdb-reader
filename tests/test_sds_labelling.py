"""What the parser reads as a sheet's labelling (SDB-4, SDB-78, SDB-119 to SDB-127).

The sheets are invented; each shows one form a comparison over a body of
sheets turned up.
"""

from __future__ import annotations

import pytest

from sdb_reader.compliance import requires_sheet
from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import ParsedSheet, SDSParser
from sdb_reader.schema import HazardStatements, StatedClassification
from sdb_reader.statements import (
    codes_from_wording,
    label_statements,
    normalize_statements,
)

SHEET = (
    "Sicherheitsdatenblatt\n"
    "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
    "1.1 Produktidentifikator\nHandelsname: Musterprodukt\n"
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "{section_2}"
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n{section_3}"
    "ABSCHNITT 4: Erste-Hilfe-Maßnahmen\nKeine besonderen Maßnahmen.\n"
)
CLASSIFIED = (
    "2.1 Einstufung des Stoffs oder Gemischs\n"
    "Einstufung gemäß Verordnung (EG) Nr. 1272/2008\n"
    "Skin Irrit. 2\nH315\nVerursacht Hautreizungen.\n"
    "Eye Dam. 1\nH318\nVerursacht schwere Augenschäden.\n"
)
UNCLASSIFIED = (
    "2.1 Einstufung des Stoffs oder Gemischs\n"
    "Das Gemisch ist nicht als gefährlich eingestuft im Sinne der Verordnung "
    "(EG) Nr. 1272/2008.\n"
)


def read(section_2: str, section_3: str = "Gemisch.\n") -> HazardStatements:
    return _parse(section_2, section_3).sheet.hazard_statements


def _parse(section_2: str, section_3: str = "Gemisch.\n") -> ParsedSheet:
    text = SHEET.format(section_2=section_2, section_3=section_3)
    return SDSParser().parse(
        ExtractionResult(
            text=text,
            raw_text=text,
            extractor="unit-test",
            pages_sampled=1,
            warnings=[],
            metadata={},
        )
    )


@pytest.mark.spec("SDB-4")
@pytest.mark.parametrize("bullet", ["· ", "• ", "∙ ", ""])
def test_a_heading_of_2_3_behind_a_bullet_ends_the_label(bullet: str) -> None:
    """Without the end the label ran on into the table of ingredients."""
    label = read(
        CLASSIFIED
        + f"{bullet}2.2 Kennzeichnungselemente\n"
        + "Signalwort: Gefahr\n"
        + "Gefahrenhinweise\nH315 Verursacht Hautreizungen.\n"
        + "H318 Verursacht schwere Augenschäden.\n"
        + f"{bullet}2.3 Sonstige Gefahren\nKeine.\n"
        + "3 Zusammensetzung/Angaben zu Bestandteilen\n"
        + "Dimethylether\nFlam. Gas 1A, H220; Press. Gas (Comp.), H280\n25-<50%\n"
    )

    assert label.hazard_codes == ["H315", "H318"]


@pytest.mark.spec("SDB-119")
def test_a_label_that_refers_to_2_1_carries_its_statements() -> None:
    label = read(
        CLASSIFIED
        + "2.2 Kennzeichnungselemente\n"
        + "Gefahrenpiktogramm/e:\nGHS05\nSignalwort:\nGefahr\n"
        + "Gefahrenhinweis/e: siehe Abschnitt 2.1\n"
        + "Sicherheitshinweis/e:\nP280 Schutzhandschuhe tragen.\n"
        + "2.3 Sonstige Gefahren\nKeine.\n"
    )

    assert label.hazard_codes == ["H315", "H318"]
    assert label.hazard_text == (
        "H315 Verursacht Hautreizungen.\nH318 Verursacht schwere Augenschäden."
    )
    assert label.signal_word == "Gefahr"


@pytest.mark.spec("SDB-119")
def test_the_classification_stays_out_of_a_label_that_does_not_refer_to_it() -> None:
    label = read(
        CLASSIFIED
        + "2.2 Kennzeichnungselemente\n"
        + "Signalwort: Gefahr\n"
        + "Gefahrenhinweise\nH318 Verursacht schwere Augenschäden.\n"
        + "2.3 Sonstige Gefahren\nKeine.\n"
    )

    assert label.hazard_codes == ["H318"]


@pytest.mark.spec("SDB-78")
def test_a_note_that_a_statement_is_not_required_is_not_the_statement() -> None:
    label = read(
        CLASSIFIED
        + "2.2 Kennzeichnungselemente\n"
        + "Die Kennzeichnung einer Aspirationsgefahr (Asp. Tox. 1 H304) ist für "
        + "Aerosolpackungen und Behälter mit\n"
        + "versiegelter Sprühvorrichtung nicht vorgeschrieben (Verordnung (EG) "
        + "1272/2008, Anhang 1, 1.3.3).\n"
        + "Signalwort Gefahr\n"
        + "Gefahrenhinweise\nH315 Verursacht Hautreizungen.\n"
        + "2.3 Sonstige Gefahren\nKeine.\n"
    )

    assert label.hazard_codes == ["H315"]
    assert label.hazard_text == "H315 Verursacht Hautreizungen."


class TestPhrasesOfTheOldRules:
    @pytest.mark.spec("SDB-120")
    @pytest.mark.parametrize(
        "phrases",
        [
            "S-Sätze: Darf nicht in die Hände von Kindern gelangen.(S2)\n"
            "Bei Verschlucken sofort ärztlichen Rat einholen.(S46)\n",
            "S - Sätze :\nS 2: Darf nicht in die Hände von Kindern gelangen.\n",
            "S-Sätze\n02\nDarf nicht in die Hände von Kindern gelangen.\n",
        ],
    )
    def test_an_s_phrase_worded_like_a_statement_is_none(self, phrases: str) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + phrases
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.precautionary_codes == []
        assert label.hazard_codes == []

    @pytest.mark.spec("SDB-6")
    def test_the_same_sentence_on_a_label_without_old_phrases_is_read(self) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Sicherheitshinweise: Darf nicht in die Hände von Kindern gelangen.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.precautionary_codes == ["P102"]

    @pytest.mark.spec("SDB-120")
    def test_a_bare_designation_of_the_old_rules_classifies_by_them(self) -> None:
        """Its sentence is the old phrase, worded like H400."""
        result = _parse(
            "2.1\nFür den Menschen :\nHochentzündlich. Reizend.\n"
            "2.2\nFür die Umwelt :\nUmweltgefährlich\n"
            "Sehr giftig für Wasserorganismen.\n"
        )

        hazards = result.sheet.hazard_statements
        assert hazards.hazard_codes == []
        assert hazards.signal_word is None
        assert result.sheet.stated_classification is StatedClassification.OLD_SYSTEM
        assert "classified-before-clp" in [w.code for w in result.warnings]


class TestCodesAsTheSheetWritesThem:
    @pytest.mark.spec("SDB-121")
    def test_a_joined_code_broken_inside_its_number_is_whole(self) -> None:
        label = read(
            CLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Gefahrenhinweise\nH318 Verursacht schwere Augenschäden.\n"
            + "Sicherheitshinweise\n"
            + "P305+P351+P33 BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang behutsam "
            + "mit Wasser spülen. Eventuell vorhandene\n"
            + "8\n"
            + "Kontaktlinsen nach Möglichkeit entfernen. Weiter spülen.\n"
            + "P312\nBei Unwohlsein GIFTINFORMATIONSZENTRUM anrufen.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.precautionary_codes == ["P305", "P312", "P338", "P351"]
        assert label.precautionary_text == (
            "P305+P351+P338 BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang behutsam "
            "mit Wasser spülen. Eventuell vorhandene Kontaktlinsen nach Möglichkeit "
            "entfernen. Weiter spülen.\n"
            "P312 Bei Unwohlsein GIFTINFORMATIONSZENTRUM anrufen."
        )

    @pytest.mark.spec("SDB-121")
    def test_a_number_below_a_whole_code_is_left_alone(self) -> None:
        label = read(
            CLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Sicherheitshinweise\n"
            + "P305+P351+P338 BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang spülen.\n"
            + "8\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.precautionary_codes == ["P305", "P338", "P351"]

    @pytest.mark.spec("SDB-121")
    def test_euh_and_its_number_apart_are_the_code(self) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Gefahrenhinweise:\n"
            + "EUH 208: Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.\n"
            + "EUH 210: Sicherheitsdatenblatt auf Anfrage erhältlich.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.supplemental_codes == ["EUH208", "EUH210"]
        assert label.supplemental_text == (
            "EUH208: Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.\n"
            "EUH210: Sicherheitsdatenblatt auf Anfrage erhältlich."
        )

    @pytest.mark.spec("SDB-121")
    def test_a_letter_and_a_number_in_a_products_name_are_no_code(self) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Handelsname: Musterschaum P 750\n"
            + "Keine Kennzeichnung erforderlich.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.precautionary_codes == []


class TestCodesPrintedWithASpace:
    @pytest.mark.spec("SDB-164")
    def test_spaced_codes_with_their_sentences_are_the_codes(self) -> None:
        label = read(
            CLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Signalwort: Gefahr\n"
            + "Gefahrenhinweise\n"
            + "H 315: Verursacht Hautreizungen.\n"
            + "H 318\nVerursacht schwere Augenschäden.\n"
            + "Sicherheitshinweise\n"
            + "P 102 Darf nicht in die Hände von Kindern gelangen.\n"
            + "P 280 Schutzhandschuhe/Augenschutz tragen.\n"
            + "P 305 + P 351 + P 338 BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang "
            + "behutsam mit Wasser spülen. Eventuell vorhandene Kontaktlinsen nach "
            + "Möglichkeit entfernen. Weiter spülen.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.hazard_codes == ["H315", "H318"]
        assert label.precautionary_codes == ["P102", "P280", "P305", "P338", "P351"]
        assert "P305 + P351 + P338 BEI KONTAKT" in label.precautionary_text

    @pytest.mark.spec("SDB-164")
    def test_a_spaced_code_opening_its_line_with_the_sheets_own_sentence(
        self,
    ) -> None:
        label = read(
            CLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Gefahrenhinweise\n"
            + "H 226 Entzündliche Flüssigkeit (Paste) und Dampf\n"
            + "H 336 Kann Schläfrigkeit verursachen\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.hazard_codes == ["H226", "H336"]

    @pytest.mark.spec("SDB-164")
    def test_the_letters_of_an_effect_belong_to_a_spaced_code(self) -> None:
        label = read(
            "2.1 Einstufung des Stoffs oder Gemischs\n"
            + "Repr. 1B\nH360D\nKann das Kind im Mutterleib schädigen.\n"
            + "2.2 Kennzeichnungselemente\n"
            + "Signalwort: Gefahr\n"
            + "Gefahrenhinweise\n"
            + "H 360 D Kann das Kind im Mutterleib schädigen.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.hazard_codes == ["H360D"]

    @pytest.mark.spec("SDB-164")
    def test_a_measure_a_value_or_a_name_is_no_code(self) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Handelsname: Musterbehälter H 330 mm\n"
            + "Abmessungen: H 229 x 113 x 38 cm\n"
            + "Prüfdruck P 100 bar, Ausführung P 135 L\n"
            + "Keine Kennzeichnung erforderlich.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.hazard_codes == []
        assert label.precautionary_codes == []

    @pytest.mark.spec("SDB-164")
    def test_a_spaced_number_in_running_text_outside_the_label_is_no_code(
        self,
    ) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\nKeine Kennzeichnung erforderlich.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n",
            "Prüfwert P 250 mg/kg, Messpunkt H 2,5 m.\nH 315\nP 280\n",
        )

        assert label.hazard_codes == []
        assert label.precautionary_codes == []


@pytest.mark.spec("SDB-122")
def test_the_words_of_a_condition_alone_are_no_precautionary_statement() -> None:
    label = read(
        UNCLASSIFIED
        + "2.2 Kennzeichnungselemente\n"
        + "Sicherheitshinweise\n-\n"
        + "Hinweise zur Kennzeichnung\n"
        + "Das Produkt stellt keine Gefahr für die menschliche Gesundheit\n"
        + "bei Einatmen, Verschlucken oder Hautkontakt dar.\n"
        + "2.3 Sonstige Gefahren\nKeine.\n"
    )

    assert label.precautionary_codes == []


@pytest.mark.spec("SDB-122")
def test_a_condition_beside_a_statement_is_read_with_it() -> None:
    assert codes_from_wording("BEI VERSCHLUCKEN: Mund ausspülen.") == {"P301", "P330"}
    assert codes_from_wording("keine Gefahr bei Einatmen oder Hautkontakt") == set()


class TestTheOldDirectivesRequestSentence:
    SENTENCE = "Sicherheitsdatenblatt auf Anfrage für berufsmäßige {reader} erhältlich."

    @pytest.mark.spec("SDB-123")
    @pytest.mark.parametrize("reader", ["Verwender", "Benutzer", "Anwender"])
    def test_under_a_clp_heading_too_it_gets_no_code(self, reader: str) -> None:
        sentence = self.SENTENCE.format(reader=reader)
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Kennzeichnung gemäß Verordnung (EG) Nr. 1272/2008\n"
            + "Besondere Kennzeichnung bestimmter Gemische:\n"
            + sentence
            + "\n2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.supplemental_codes == []
        assert label.supplemental_text == sentence

    @pytest.mark.spec("SDB-123")
    @pytest.mark.parametrize(
        "old_label",
        [
            # Its lists of phrases are empty, and the CLP label is undetermined.
            "2.2.1 Kennzeichnung gemäß der Verordnung (EG) Nr. 1272/2008 (CLP)\n"
            "Nicht bestimmt\n"
            "2.2.2 Kennzeichnung gemäß der Richtlinien 67/548/EWG und 1999/45/EG\n"
            "Gefahrensymbole: Entfällt\nR-Sätze:\nS-Sätze:\nZusätze:\n",
            "Kennzeichnung nach EWG-Richtlinien:\n"
            "Das Produkt ist nach EG-Richtlinien/GefStoffV nicht "
            "kennzeichnungspflichtig.\n"
            "Besondere Kennzeichnung bestimmter Gemische:\n",
        ],
    )
    def test_in_a_label_by_the_old_directives_it_stays_as_printed(
        self, old_label: str
    ) -> None:
        result = _parse(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + old_label
            + self.SENTENCE.format(reader="Verwender")
            + "\n2.3 Sonstige Gefahren\nKeine.\n"
        )

        label = result.sheet.hazard_statements
        assert label.supplemental_codes == []
        assert label.supplemental_text == self.SENTENCE.format(reader="Verwender")

    @pytest.mark.spec("SDB-76")
    def test_the_sentence_asks_for_a_sheet_under_either_law(self) -> None:
        sentence = self.SENTENCE.format(reader="Verwender")
        result = _parse(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Kennzeichnung gemäß der Richtlinien 67/548/EWG und 1999/45/EG\n"
            + "R-Sätze:\nS-Sätze:\nZusätze:\n"
            + sentence
            + "\n2.3 Sonstige Gefahren\nKeine.\n"
        )
        label = result.sheet.hazard_statements

        assert result.sheet.stated_classification is StatedClassification.NOT_CLASSIFIED
        assert label.supplemental_codes == []
        assert label.supplemental_text == sentence
        assert requires_sheet(result.sheet)
        result.sheet.hazard_statements = HazardStatements(
            supplemental_text="Kein Blatt erforderlich."
        )
        assert requires_sheet(result.sheet) is False
        result.sheet.hazard_statements = HazardStatements(
            supplemental_text="Sicherheitsdatenblatt auf Anfrage erhältlich."
        )
        assert requires_sheet(result.sheet)

    @pytest.mark.spec("SDB-123")
    def test_a_sheet_that_prints_the_code_under_clp_keeps_it(self) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Kennzeichnung gemäß Verordnung (EG) Nr. 1272/2008\n"
            + "EUH210\nSicherheitsdatenblatt auf Anfrage erhältlich.\n"
            + "Kennzeichnung gemäß EG-Richtlinien: 1999/45/EG\n"
            + "Besondere Kennzeichnung bestimmter Gemische: "
            + self.SENTENCE.format(reader="Verwender")
            + "\n2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.supplemental_codes == ["EUH210"]
        assert label.supplemental_text == (
            "EUH210 Sicherheitsdatenblatt auf Anfrage erhältlich.\n"
            + self.SENTENCE.format(reader="Verwender")
        )


class TestSupplementalStatementsBehindTheLabel:
    @pytest.mark.spec("SDB-124")
    def test_a_code_named_in_running_text_is_no_statement(self) -> None:
        label = read(
            CLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Gefahrenhinweise\nH318 Verursacht schwere Augenschäden.\n"
            + "2.3 Sonstige Gefahren\n"
            + "Das Produkt enthält Chromatreduzierer; eine sensibilisierende Wirkung "
            + "ist bei sachgerechter Lagerung nicht zu erwarten (H317 und\n"
            + "EUH203 können daher entfallen).\n"
        )

        assert label.supplemental_codes == []
        assert label.supplemental_text is None

    @pytest.mark.spec("SDB-124")
    def test_a_statement_with_its_wording_under_2_3_is_the_labels(self) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Sicherheitshinweise:\nNicht anwendbar\n"
            + "2.3 Sonstige Gefahren\n"
            + "EUH210: Sicherheitsdatenblatt auf Anfrage erhältlich.\n"
        )

        assert label.supplemental_codes == ["EUH210"]
        assert label.supplemental_text == (
            "EUH210: Sicherheitsdatenblatt auf Anfrage erhältlich."
        )


class TestTheSubstancesOfEuh208:
    @pytest.mark.spec("SDB-125")
    def test_they_stand_before_the_code_on_its_line(self) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Besondere Kennzeichnung\n"
            + "Enthält: Musterstoff A, Musterstoff B. EUH208 Kann allergische "
            + "Reaktionen hervorrufen.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.supplemental_codes == ["EUH208"]
        assert label.supplemental_text == (
            "EUH208 Enthält: Musterstoff A, Musterstoff B. Kann allergische "
            "Reaktionen hervorrufen."
        )

    @pytest.mark.spec("SDB-125")
    def test_the_code_stands_between_two_halves_of_a_name(self) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Besondere Kennzeichnung bestimmter Gemische\n"
            + "Enthält Reaktionsmasse aus Musterstoff A und\n"
            + "EUH208\n"
            + "Musterstoff B (3:1). Kann allergische Reaktionen hervorrufen.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.supplemental_text == (
            "EUH208 Enthält Reaktionsmasse aus Musterstoff A und Musterstoff B "
            "(3:1). Kann allergische Reaktionen hervorrufen."
        )

    @pytest.mark.spec("SDB-125")
    def test_a_statement_that_names_them_behind_its_code_stays(self) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Enthält: Tenside.\n"
            + "EUH208 Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.supplemental_text == (
            "EUH208 Enthält Musterstoff. Kann allergische Reaktionen hervorrufen."
        )


class TestACodeWithSomethingHungOnIt:
    @pytest.mark.spec("SDB-126")
    def test_a_statement_begins_before_it_on_a_line_of_its_own(self) -> None:
        assert normalize_statements(
            "H317: Kann allergische Hautreaktionen verursachen. "
            "H360FD: Kann die Fruchtbarkeit beeinträchtigen. "
            "H361d Kann vermutlich das Kind im Mutterleib schädigen.",
            ("H", "EUH"),
        ) == (
            "H317: Kann allergische Hautreaktionen verursachen.\n"
            "H360FD: Kann die Fruchtbarkeit beeinträchtigen.\n"
            "H361d: Kann vermutlich das Kind im Mutterleib schädigen."
        )
        assert normalize_statements(
            "P103: Vor Gebrauch Kennzeichnungsetikett lesen. "
            "P501.9: Inhalt/Behälter der Problemabfallentsorgung zuführen. "
            "P312a Bei Unwohlsein Arzt anrufen.",
            ("P",),
        ) == (
            "P103: Vor Gebrauch Kennzeichnungsetikett lesen.\n"
            "P501.9: Inhalt/Behälter der Problemabfallentsorgung zuführen.\n"
            "P312a: Bei Unwohlsein Arzt anrufen."
        )

    @pytest.mark.spec("SDB-126")
    def test_it_is_no_part_of_the_wording_and_none_of_the_code(self) -> None:
        statements = label_statements(
            HazardStatements(
                hazard_codes=["H317", "H360"],
                precautionary_codes=["P103", "P501"],
                hazard_text=(
                    "H317: Kann allergische Hautreaktionen verursachen. "
                    "H360FD: Kann die Fruchtbarkeit beeinträchtigen."
                ),
                precautionary_text=(
                    "P103: Vor Gebrauch Kennzeichnungsetikett lesen. "
                    "P501.9: Inhalt/Behälter der Problemabfallentsorgung zuführen."
                ),
            )
        )

        assert [(s.code, s.sheet) for s in statements] == [
            ("H317", "Kann allergische Hautreaktionen verursachen."),
            ("H360", "Kann die Fruchtbarkeit beeinträchtigen."),
            ("P103", "Vor Gebrauch Kennzeichnungsetikett lesen."),
            ("P501", "Inhalt/Behälter der Problemabfallentsorgung zuführen."),
        ]

    @pytest.mark.spec("SDB-126")
    def test_a_word_set_against_a_code_is_no_suffix(self) -> None:
        assert (
            normalize_statements("H315-Verursacht Hautreizungen.", ("H",))
            == "H315: Verursacht Hautreizungen."
        )


class TestWhereAStatementEnds:
    LABEL = (
        CLASSIFIED
        + "2.2 Kennzeichnungselemente\n"
        + "Gefahrenhinweise\nH318 Verursacht schwere Augenschäden.\n"
        + "Sicherheitshinweise\n{statements}"
        + "2.3 Sonstige Gefahren\nKeine.\n"
    )

    @pytest.mark.spec("SDB-127")
    @pytest.mark.parametrize(
        "behind",
        [
            "Enthält: Zement, Portland, Klinker\n",
            "Andere Kennzeichnung\n",
            "Kindersicherung\nJa\nTaktive Warnzeichen\nJa\n",
            "Besondere Gefahrenhinweise für Mensch und Umwelt: Die Bestimmungen "
            "der Berufsgenossenschaft beachten.\n",
            "Ergebnisse der PBT- und vPvB-Beurteilung: nicht anwendbar\n",
        ],
    )
    def test_what_begins_something_else_is_not_its_end(self, behind: str) -> None:
        label = read(
            self.LABEL.format(
                statements="P501\nEntsorgung gemäß den behördlichen Vorschriften.\n"
                + behind
            )
        )

        assert label.precautionary_text == (
            "P501 Entsorgung gemäß den behördlichen Vorschriften."
        )

    @pytest.mark.spec("SDB-127")
    def test_a_hazard_statement_that_begins_with_the_word_stays_whole(self) -> None:
        label = read(
            "2.1 Einstufung des Stoffs oder Gemischs\nGase unter Druck, Kategorie 1\n"
            "2.2 Kennzeichnungselemente\nSignalwort: Achtung\n"
            "Gefahrenhinweise\nH280\n"
            "Enthält Gas unter Druck; kann bei Erwärmung explodieren.\n"
            "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.hazard_text == (
            "H280 Enthält Gas unter Druck; kann bei Erwärmung explodieren."
        )

    @pytest.mark.spec("SDB-127")
    @pytest.mark.parametrize(
        "printed",
        [
            "P280 gloves\nSchutzhandschuhe tragen.\n",
            "P280 gloves Schutzhandschuhe tragen.\n",
            "P280 hands\ngloves\nSchutzhandschuhe tragen.\n",
        ],
    )
    def test_the_words_of_a_pictogram_are_none_of_the_statements(
        self, printed: str
    ) -> None:
        label = read(self.LABEL.format(statements=printed))

        assert label.precautionary_text == "P280 Schutzhandschuhe tragen."

    @pytest.mark.spec("SDB-127")
    def test_a_page_marker_with_the_count_in_brackets_is_read_past(self) -> None:
        label = read(
            self.LABEL.format(
                statements="P101\nIst ärztlicher Rat erforderlich, Verpackung oder "
                "Kennzeichnungsetikett\nSeite: 1 (11)\nbereithalten.\n"
            )
        )

        assert label.precautionary_text == (
            "P101 Ist ärztlicher Rat erforderlich, Verpackung oder "
            "Kennzeichnungsetikett bereithalten."
        )

    @pytest.mark.spec("SDB-127")
    def test_a_footnotes_number_behind_the_full_stop_goes(self) -> None:
        label = read(
            UNCLASSIFIED
            + "2.2 Kennzeichnungselemente\n"
            + "Ergänzende Informationen\n"
            + "EUH208: Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.6\n"
            + "EUH210: Sicherheitsdatenblatt auf Anfrage erhältlich.\n"
            + "2.3 Sonstige Gefahren\nKeine.\n"
        )

        assert label.supplemental_text == (
            "EUH208: Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.\n"
            "EUH210: Sicherheitsdatenblatt auf Anfrage erhältlich."
        )
