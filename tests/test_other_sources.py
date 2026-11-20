"""Layouts and spellings from sheets outside the corpus (SDB-155 to SDB-162).

Every text here is invented; it keeps only the shape that tripped the parser.
"""

from __future__ import annotations

from datetime import date

import pytest

from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import SDSParser, _read_section_heading, read_signal_word
from sdb_reader.pictograms import get_signal_word, pictograms_for
from sdb_reader.schema import SafetyDataSheet
from sdb_reader.statements import canonical_text, lettered_code, with_effects_joined

IDENTIFIER = "1.1 Produktidentifikator\nHandelsname: Musterlack\n"
SUPPLIER = (
    "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
    "Musterwerk GmbH\nHafenstraße 4\n20457 Hamburg\nTelefon: +49 40 5550123\n"
)
LABEL = (
    "2.2 Kennzeichnungselemente\nSignalwort: Achtung\nH315 Verursacht Hautreizungen.\n"
)


def _sheet(
    *,
    header: str = "",
    identifier: str = IDENTIFIER,
    supplier: str = SUPPLIER,
    label: str = LABEL,
) -> SafetyDataSheet:
    text = (
        "Sicherheitsdatenblatt\n"
        f"{header}"
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
        f"{identifier}"
        "1.2 Relevante identifizierte Verwendungen des Stoffs oder Gemischs\n"
        "Lack\n"
        f"{supplier}"
        "1.4 Notrufnummer\nGiftnotruf Musterstadt: +49 30 5550100\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
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
    return SDSParser(language="de").parse(extraction).sheet


class TestLetteredReproductionCodes:
    @pytest.mark.spec("SDB-155")
    @pytest.mark.parametrize(
        ("printed", "code"),
        [
            ("H360D", "H360D"),
            ("H360FD", "H360FD"),
            ("H360DF", "H360FD"),
            ("H360Df", "H360Df"),
            ("H360Fd", "H360Fd"),
            ("H361d", "H361d"),
            ("H361D", "H361d"),
            ("H361FD", "H361fd"),
            ("H360d", "H360"),
            ("H360", "H360"),
        ],
    )
    def test_the_letters_of_an_effect_stay_with_the_code(
        self, printed: str, code: str
    ) -> None:
        label = (
            "2.2 Kennzeichnungselemente\nSignalwort: Gefahr\n"
            f"{printed}: Kann das Kind im Mutterleib schädigen.\n"
        )
        hazards = _sheet(label=label).hazard_statements
        assert hazards.hazard_codes == [code]
        assert hazards.pictograms == ["GHS08"]
        assert hazards.signal_word == "Gefahr"

    @pytest.mark.spec("SDB-155")
    def test_two_effects_are_the_joined_code(self) -> None:
        assert with_effects_joined({"H360F", "H360D"}) == {"H360FD"}
        assert with_effects_joined({"H360D", "H361f"}) == {"H360Df"}
        assert with_effects_joined({"H361f", "H361d"}) == {"H361fd"}
        assert with_effects_joined({"H360", "H360D", "H315"}) == {"H360D", "H315"}

    @pytest.mark.spec("SDB-155")
    def test_the_lettered_code_has_the_wording_of_annex_vi(self) -> None:
        assert canonical_text("H360D") == "Kann das Kind im Mutterleib schädigen."
        assert canonical_text("H361fd") == (
            "Kann vermutlich die Fruchtbarkeit beeinträchtigen. "
            "Kann vermutlich das Kind im Mutterleib schädigen."
        )
        assert canonical_text("H360") is None

    @pytest.mark.spec("SDB-155")
    def test_pictogram_and_signal_word_do_not_depend_on_the_letter(self) -> None:
        assert pictograms_for({"H360FD"}) == pictograms_for({"H360"})
        assert get_signal_word({"H361d"}) == get_signal_word({"H361"})
        assert lettered_code("H315") == "H315"


@pytest.mark.spec("SDB-156")
def test_a_label_numbering_its_own_parts_goes_on_past_2_3() -> None:
    label = (
        "2.2 Kennzeichnungselemente\nGHS02 GHS07\nSignalwort: Gefahr\n"
        "2.3\nGefahrbestimmende Komponenten zur Etikettierung:\nMusteracrylat\n"
        "2.4\nGefahrenhinweise:\nH225: Flüssigkeit und Dampf leicht entzündbar.\n"
        "H315: Verursacht Hautreizungen.\n"
        "2.5\nSicherheitshinweise:\nP210: Von Hitze fernhalten.\n"
    )
    hazards = _sheet(label=label).hazard_statements
    assert hazards.hazard_codes == ["H225", "H315"]
    assert hazards.precautionary_codes == ["P210"]


@pytest.mark.spec("SDB-157")
def test_a_named_signal_word_before_a_negation_for_the_diluted_product() -> None:
    label = (
        "Produkt wie verkauft\nSignalwort: Achtung\nH319 Verursacht schwere Augenreizung.\n"
        "Produkt in der Anwendungskonzentration\n"
        "Kein Gefahrenpiktogramm, kein Signalwort erforderlich.\n"
    )
    assert read_signal_word(label) == ("Achtung", True)
    assert read_signal_word("Signalwort entfällt\nAchtung ist geboten.") == (None, True)


class TestNoProductName:
    @pytest.mark.spec("SDB-158")
    @pytest.mark.parametrize(
        ("identifier", "name"),
        [
            (
                "Artikelnr. (Hersteller/Lieferant): 12-345\n"
                "Bezeichnung des Stoffes oder des Gemischs\nMusterlack\nseidenmatt\n",
                "Musterlack",
            ),
            (
                "Artikelnr. (Hersteller/Lieferant)\nHandelsname/Bezeichnung\n"
                "4711M\nMusterpflegeöl\n",
                "Musterpflegeöl",
            ),
            (
                "· Bezeichnung des Stoffes oder des Gemisches: MUSTERSCHAUM\n",
                "MUSTERSCHAUM",
            ),
            (
                "Produktform\nGemisch\nProduktbezeichnung\nMusterspülmittel\n",
                "Musterspülmittel",
            ),
        ],
    )
    def test_the_name_past_numbers_and_kinds(self, identifier: str, name: str) -> None:
        sheet = _sheet(identifier="1.1 Produktidentifikator\n" + identifier)
        assert sheet.product_identifier == name


class TestSupplierLabels:
    @pytest.mark.spec("SDB-159")
    @pytest.mark.parametrize(
        ("block", "name"),
        [
            (
                "Name der Firma: Musterwerk GmbH\nHafenstr. 1-11\n12345 Musterstadt\n",
                "Musterwerk GmbH",
            ),
            (
                "Name des Herstellerunternehmens: Musterwerk AG & Co KG\n"
                "Musterstr. 103\n12345 Musterstadt\n",
                "Musterwerk AG & Co KG",
            ),
            (
                "Herstellerin\nFirmenname: Musterwerk GmbH & Co. KG\nStrasse: Weg 7\n",
                "Musterwerk GmbH & Co. KG",
            ),
            (
                "Informationen zu Hersteller/Importeur/Lieferant/Verteiler\nName der Firma: Musterwerk B.V.\n",
                "Musterwerk B.V.",
            ),
            (
                "Musterwerk KGaA * 12345 Musterstadt * Deutschland * Tel: +49 30 5550100\n",
                "Musterwerk KGaA",
            ),
            ("Musterwerk GmbH Musterstr. 40 12345 Musterstadt\n", "Musterwerk GmbH"),
            (
                "Firmendetails: MUSTERWERK GmbH Notrufnummer (mit Bedienungszeiten)\nHafenweg 6\n",
                "MUSTERWERK GmbH",
            ),
            (
                "MUSTERWERK IBERICA SA\nCalle Mayor 1\n08000 Musterstadt\n",
                "MUSTERWERK IBERICA SA",
            ),
        ],
    )
    def test_the_supplier_behind_other_labels(self, block: str, name: str) -> None:
        supplier = (
            "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
            + block
        )
        assert _sheet(supplier=supplier).contact_info.supplier_name == name

    @pytest.mark.spec("SDB-159")
    def test_the_company_behind_the_headings_colon(self) -> None:
        supplier = (
            "1.3 Einzelheiten zum: Musterwerk GmbH\nLieferanten, der das\n"
            "Sicherheitsdatenblatt bereitstellt\nMusterweg 25\n12345 Musterstadt\n"
        )
        contact = _sheet(supplier=supplier).contact_info
        assert contact.supplier_name == "Musterwerk GmbH"
        assert contact.supplier_address == "Musterweg 25, 12345 Musterstadt"

    @pytest.mark.spec("SDB-159")
    def test_name_or_trade_name_over_the_company(self) -> None:
        supplier = (
            "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt "
            "bereitstellt\nHersteller\nName oder Handelsname\nMusterwerk B.V.\n"
            "Adresse\nMusterweg 18, 6900 AB Musterstad\n"
        )
        assert _sheet(supplier=supplier).contact_info.supplier_name == "Musterwerk B.V."

    @pytest.mark.spec("SDB-159")
    def test_a_pointer_elsewhere_is_nobodys_name(self) -> None:
        supplier = "1.3\nHersteller/Lieferant: siehe Kapitel 16 (Ansprechpartner)\n"
        assert _sheet(supplier=supplier).contact_info.supplier_name is None


@pytest.mark.spec("SDB-160")
def test_a_reference_to_a_subsection_is_no_heading() -> None:
    assert _read_section_heading("Abschnitt 7.3 angegeben") is None
    assert _read_section_heading("ABSCHNITT 7: Handhabung und Lagerung") is not None


class TestDates:
    @pytest.mark.spec("SDB-161")
    @pytest.mark.parametrize(
        ("line", "revised", "issued"),
        [
            (
                "Datum der Zusammenstellung/Überarbei tung: 06.03.2025\n",
                date(2025, 3, 6),
                None,
            ),
            ("Revisionsdatum: Mittwoch, 13. Mai 2015\n", date(2015, 5, 13), None),
            ("Datum der Ausgabe: 06.01.2021\n", None, date(2021, 1, 6)),
        ],
    )
    def test_dates_in_other_forms(
        self, line: str, revised: date | None, issued: date | None
    ) -> None:
        sheet = _sheet(header=line)
        assert sheet.revision_date == revised
        assert sheet.issue_date == issued


@pytest.mark.spec("SDB-162")
def test_a_pictogram_code_behind_a_statement_is_not_its_wording() -> None:
    label = (
        "2.2 Kennzeichnungselemente\nSignalwort: Achtung\n"
        "H335 Kann die Atemwege reizen. GHS07\n"
    )
    hazards = _sheet(label=label).hazard_statements
    assert hazards.hazard_text is not None
    assert "GHS07" not in hazards.hazard_text
