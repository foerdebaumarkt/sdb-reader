"""What the parser reads from section 1: product name, supplier, e-mail (SDB-49, SDB-50, SDB-131, SDB-136).

The sheets are invented; each shows one form a comparison over a body of
sheets turned up.
"""

from __future__ import annotations

from datetime import date

import pytest

from sdb_reader.compliance import sheet_findings
from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import SDSParser
from sdb_reader.schema import ContactInfo, SafetyDataSheet

SHEET = (
    "Sicherheitsdatenblatt\n"
    "{header}"
    "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
    "{identifier}"
    "1.2 Relevante identifizierte Verwendungen des Stoffs oder Gemischs\n"
    "Reinigungsmittel\n"
    "{supplier}"
    "1.4 Notrufnummer\n"
    "Giftnotruf Musterstadt: +49 30 5550100\n"
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.2 Kennzeichnungselemente\nSignalwort: Achtung\n"
    "H315 Verursacht Hautreizungen.\n"
    "2.3 Sonstige Gefahren\nKeine bekannt.\n"
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
)
IDENTIFIER = "1.1 Produktidentifikator\nHandelsname: Musterreiniger\n"
SUPPLIER = (
    "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
    "Musterchemie GmbH\n"
    "Hafenstraße 4\n"
    "20457 Hamburg\n"
    "Telefon: +49 40 5550123\n"
    "E-Mail: sdb@musterchemie.example\n"
)
HEADING_1_3 = (
    "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
)


def read(
    identifier: str = IDENTIFIER, supplier: str = SUPPLIER, header: str = ""
) -> SafetyDataSheet:
    text = SHEET.format(header=header, identifier=identifier, supplier=supplier)
    extraction = ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )
    return SDSParser(language="de").parse(extraction).sheet


def name_of(identifier: str) -> str | None:
    return read(identifier="1.1 Produktidentifikator\n" + identifier).product_identifier


class TestProductName:
    @pytest.mark.spec("SDB-131")
    @pytest.mark.parametrize(
        "identifier",
        [
            "Handelsname: Musterreiniger\n",
            "Handelsname\nMusterreiniger\n",
            "Handelsname/Bezeichnung:\nMusterreiniger\n",
            "Produktbezeichnung\nMusterreiniger\nProduktcode\n4711-22\n",
            "Produktbezeichnung Musterreiniger\n",
            "Handelsname\nProduktnummer (UVP)\nMusterreiniger\n4711\n",
            "· Handelsname: Musterreiniger\n· Artikelnummer: 4711\n",
            "Handelsname oder Bezeichnung des Gemischs: Musterreiniger\n",
            "GHS Produkt-Identifikator: Musterreiniger\n",
        ],
    )
    def test_it_stands_behind_or_below_its_label(self, identifier: str) -> None:
        assert name_of(identifier) == "Musterreiniger"

    @pytest.mark.spec("SDB-131")
    @pytest.mark.parametrize(
        "identifier",
        [
            "Musterreiniger\n",
            "Musterreiniger\nStoff- / Produktidentifikation\nPR-Nr.\n4711, 4712\n",
            "Musterreiniger\nRegistrierungsnr.\nUFI\nAB12-CD34-EF56-GH78\n",
        ],
    )
    def test_without_a_label_it_is_the_line_under_the_heading(
        self, identifier: str
    ) -> None:
        assert name_of(identifier) == "Musterreiniger"

    @pytest.mark.spec("SDB-131")
    def test_the_heading_may_stand_apart_from_its_number(self) -> None:
        sheet = read(
            identifier="1.1\nProduktidentifikator\nHandelsname\nMusterreiniger\n"
        )

        assert sheet.product_identifier == "Musterreiniger"

    @pytest.mark.spec("SDB-131")
    def test_the_label_may_carry_the_subsection_s_number(self) -> None:
        sheet = read(identifier="1.1 Handelsname: Musterreiniger\n")

        assert sheet.product_identifier == "Musterreiniger"

    @pytest.mark.spec("SDB-131")
    @pytest.mark.parametrize(
        "identifier",
        [
            "Produktform: Gemisch\nProduktname: Musterreiniger\nProduktcode: 4711\n",
            "Produktform: Gemisch\nHandelsname: Musterreiniger\nProduktart: Reiniger\n",
            "Produktform: Erzeugnis\nName: Musterreiniger\n",
        ],
    )
    def test_the_form_of_the_product_is_not_its_name(self, identifier: str) -> None:
        assert name_of(identifier) == "Musterreiniger"

    @pytest.mark.spec("SDB-131")
    def test_the_trade_name_goes_before_another_name(self) -> None:
        identifier = (
            "Name des Gemischs: Reinigungsmittel\n"
            "Synonyme: Reiniger\n"
            "Handelsnamen, UFI: Musterreiniger\n"
        )

        assert name_of(identifier) == "Musterreiniger"

    @pytest.mark.spec("SDB-131")
    @pytest.mark.parametrize(
        "identifier",
        [
            "Handelsname/Bezeichnung:\nUFI:\nAB12-CD34-EF56-GH78\n",
            "Handelsname/Bezeichnung:\nArtikel-Nr.:\n4711\n",
            "Handelsname/Bezeichnung:\nCAS-Nr.:\n7778-18-9\nEG-Nr.:\n231-900-3\n",
        ],
    )
    def test_a_label_with_nothing_under_it_gives_no_name(self, identifier: str) -> None:
        assert name_of(identifier) is None

    @pytest.mark.spec("SDB-131")
    def test_a_bullet_goes_and_a_quote_stays(self) -> None:
        assert name_of("Handelsname:\n- „Muster“ Reiniger\n") == "„Muster“ Reiniger"

    @pytest.mark.spec("SDB-131")
    def test_the_next_heading_glued_to_the_name_is_not_part_of_it(self) -> None:
        identifier = (
            "Produktname: Musterreiniger: 1.2. Relevante identifizierte "
            "Verwendungen des Stoffs oder Gemischs\n"
        )

        assert name_of(identifier) == "Musterreiniger"

    @pytest.mark.spec("SDB-131")
    def test_only_the_first_line_of_a_name_is_read(self) -> None:
        assert name_of("Handelsname: Musterreiniger Zitrone,\nLimette\n") == (
            "Musterreiniger Zitrone,"
        )

    @pytest.mark.spec("SDB-131")
    def test_below_1_1_only_a_trade_name_s_label_counts(self) -> None:
        supplier = (
            HEADING_1_3
            + "Name: Musterchemie GmbH\n"
            + "Produktsicherheit: sdb@musterchemie.example\n"
            + "Bezeichnung: Vertrieb\n"
        )

        assert (
            read(
                identifier="1.1 Produktidentifikator\n", supplier=supplier
            ).product_identifier
            is None
        )

    @pytest.mark.spec("SDB-131")
    def test_a_sheet_without_subsections_names_it_behind_its_label(self) -> None:
        sheet = read(
            identifier="Verwendung: Reiniger\n",
            supplier="Firma: Musterchemie GmbH\nHandelsname: Musterreiniger\n",
        )

        assert sheet.product_identifier == "Musterreiniger"


EMPTY_NAME_FIELD = (
    "1.1. Produktidentifikator\nHandelsname/Bezeichnung:\nUFI:\nAB12-CD34-EF56-GH78\n"
)


class TestWhatIsNoName:
    @pytest.mark.spec("SDB-131")
    @pytest.mark.parametrize(
        "identifier",
        [
            # Labels without values: the form prints the values elsewhere.
            "Handelsname\nRegistrierungsnummer (REACH)\n"
            "Eindeutiger Rezepturidentifikator (UFI)\nArtikelnummer\n",
            # A formula identifier with a character too many in two groups.
            "Handelsname/Bezeichnung:\nUFI:\nAB1C2-D3EFG-H4J5-K6L7\n",
            # The title of section 1 in another language.
            "Handelsname:\nIdentification of the substance or preparation and company\n",
            "Handelsname\nTelefon\nTelefax\nEmail-Adresse\nNotrufnummer\n",
        ],
    )
    def test_a_label_a_formula_identifier_or_a_title_is_none(
        self, identifier: str
    ) -> None:
        assert name_of(identifier) is None

    @pytest.mark.spec("SDB-131")
    @pytest.mark.parametrize("reference", ["siehe oben", "Siehe oben."])
    def test_a_reference_is_none_and_is_not_followed(self, reference: str) -> None:
        identifier = (
            "Bezeichnung der Zubereitung: Trockenmischung auf Zementbasis\n"
            "Synonyme: Musterschlämme\n"
            f"Handelsname: {reference}\n"
            "CAS: Mischung\n"
        )

        assert name_of(identifier) is None

    @pytest.mark.spec("SDB-131")
    def test_a_reference_leaves_a_labelled_name_in_the_header(self) -> None:
        sheet = read(
            header="Handelsname: Musterkalk\n",
            identifier="1.1 Produktidentifikator\nHandelsname: siehe oben\n",
        )

        assert sheet.product_identifier == "Musterkalk"

    @pytest.mark.spec("SDB-131")
    def test_a_reference_takes_no_headline_for_the_name(self) -> None:
        sheet = read(
            header="Version: 1\nSeite 1/9\nMusterputz MP 7\n",
            identifier="1.1 Produktidentifikator\nHandelsname: siehe oben\n",
        )

        assert sheet.product_identifier is None

    @pytest.mark.spec("SDB-131")
    def test_a_registration_number_with_its_substance_is_passed_over(self) -> None:
        identifier = (
            "Handelsname:\n"
            "Index-Nr.: --\n"
            "REACH-Registrierungs-Nr. von n-Butylacetat: 01-2100000000-00-0000\n"
            "Andere Bezeichnungen:--\n"
            "Musterdicht\n"
        )

        assert name_of(identifier) == "Musterdicht"

    @pytest.mark.spec("SDB-131")
    @pytest.mark.parametrize(
        "identifier",
        [
            "Handelsname\nFirma\nTelefon\nMusterkalk geperlt\n",
            "Handelsname:\nHersteller: Musterchemie GmbH; Hafenstraße 4\nMusterakku\n",
            "Handelsname:\nHersteller/Lieferant\nMusterchemie\n",
        ],
    )
    def test_a_supplier_s_label_ends_the_subsection(self, identifier: str) -> None:
        assert name_of(identifier) is None

    @pytest.mark.spec("SDB-131")
    def test_both_numbers_set_before_the_subsection_do_not_end_it(self) -> None:
        sheet = read(
            identifier=(
                "1.1\n1.2\nProduktidentifikator:\nHandelsname:\n"
                "Musterköder 25ppm\nArtikelnummer:\n4711\n"
            )
        )

        assert sheet.product_identifier == "Musterköder 25ppm"

    @pytest.mark.spec("SDB-131")
    @pytest.mark.parametrize(
        ("identifier", "name"),
        [
            ("Handelsname: Art.-Nr. 12.345 Musterdünger\n", "Musterdünger"),
            ("Handelsname: Artikel-Nr.: 4711-22 Musterdünger\n", "Musterdünger"),
            (
                "Handelsname\nMusterspray 200 ml Art.Nr.\n"
                "012340 / 400 ml Art.Nr.: 012341\nRegistrierungsnummer (REACH)\n"
                "nicht relevant (Gemisch)\n",
                "Musterspray 200 ml",
            ),
        ],
    )
    def test_an_article_number_beside_the_name_is_no_part_of_it(
        self, identifier: str, name: str
    ) -> None:
        assert name_of(identifier) == name

    @pytest.mark.spec("SDB-131")
    def test_a_name_that_ends_in_its_article_number_stays_as_printed(self) -> None:
        identifier = "Handelsname\nMusterspray 400 ml Art.Nr.: 012342\n"

        assert name_of(identifier) == "Musterspray 400 ml Art.Nr.: 012342"

    @pytest.mark.spec("SDB-131")
    def test_the_label_may_carry_a_letter_too_many(self) -> None:
        assert name_of("Handelsnamel/Bezeichnung Musteröl\n") == "Musteröl"


class TestValueBeforeLabel:
    @pytest.mark.spec("SDB-149")
    @pytest.mark.parametrize(
        "identifier",
        [
            "Produktform: Gemisch\n: Musterreiniger\nHandelsname\n",
            ": Gemisch\nProduktform\n: Musterreiniger\nHandelsname\n",
        ],
    )
    def test_the_value_above_the_trade_name_s_label_is_the_name(
        self, identifier: str
    ) -> None:
        assert name_of(identifier) == "Musterreiniger"

    @pytest.mark.spec("SDB-149")
    def test_a_label_with_its_value_below_is_read_as_before(self) -> None:
        identifier = "Produktform\n: Gemisch\nHandelsname\n: Musterreiniger\n"

        assert name_of(identifier) == "Musterreiniger"

    @pytest.mark.spec("SDB-149")
    def test_a_pair_above_an_empty_label_is_no_name(self) -> None:
        assert name_of("Produktform: Gemisch\nHandelsname\n") is None


class TestNameInTheHeader:
    @pytest.mark.spec("SDB-150")
    @pytest.mark.parametrize(
        ("header", "name"),
        [
            ("Handelsname: Musterkalk\n", "Musterkalk"),
            ("Produkt: Musterwachs\nErstellt am: 12.03.07\n", "Musterwachs"),
        ],
    )
    def test_a_label_in_the_header_names_it_where_1_1_does_not(
        self, header: str, name: str
    ) -> None:
        sheet = read(
            header=header,
            identifier="1.1 Produktidentifikator\nArtikelnummer: 4711\n",
        )

        assert sheet.product_identifier == name

    @pytest.mark.spec("SDB-150")
    def test_the_headline_above_section_1_fills_an_empty_field(self) -> None:
        header = (
            "Bearbeitungsdatum: 12.03.2022\nVersion: 1\nSeite 1/9\nMusterputz MP 7\n"
        )

        sheet = read(header=header, identifier=EMPTY_NAME_FIELD)

        assert sheet.product_identifier == "Musterputz MP 7"

    @pytest.mark.spec("SDB-150")
    @pytest.mark.parametrize(
        "header",
        [
            "",
            "Musterakkus\nErsetzt: Version 8.0\n",
            "Musterakkus\nVersion 9.0\n",
            "Musterakkus\nStand 12.03.2024\n",
            "Musterakkus\ngemäß Verordnung (EG) Nr. 1907/2006\n",
            "Musterakkus\nSeite 1 von 8\n",
            "Musterakkus\n12.03.2024\n",
        ],
    )
    def test_a_title_a_version_a_date_or_a_page_is_no_headline(
        self, header: str
    ) -> None:
        sheet = read(header=header, identifier=EMPTY_NAME_FIELD)

        assert sheet.product_identifier is None

    @pytest.mark.spec("SDB-150")
    def test_without_an_empty_field_the_headline_is_not_taken(self) -> None:
        sheet = read(
            header="Musterputz MP 7\n",
            identifier="1.1 Produktidentifikator\nArtikelnummer: 4711\n",
        )

        assert sheet.product_identifier is None

    @pytest.mark.spec("SDB-150")
    def test_the_name_of_1_1_goes_before_the_header(self) -> None:
        sheet = read(header="Produkt: Musterwachs\nMusterputz MP 7\n")

        assert sheet.product_identifier == "Musterreiniger"


class TestSupplierName:
    @pytest.mark.spec("SDB-49")
    def test_a_remark_in_brackets_behind_the_label_is_no_name(self) -> None:
        supplier = (
            HEADING_1_3
            + "Lieferant (Hersteller/Importeur/Alleinvertreter/nachgeschalteter\n"
            + "Anwender/Händler)\n"
            + "Musterchemie GmbH\nStraße: Hafenstraße 4\nPostleitzahl/Ort: 20457 Hamburg\n"
        )

        contact = read(supplier=supplier).contact_info

        assert contact.supplier_name == "Musterchemie GmbH"
        assert contact.supplier_address == "Hafenstraße 4, 20457 Hamburg"

    @pytest.mark.spec("SDB-49")
    def test_name_alone_heads_the_name(self) -> None:
        supplier = (
            HEADING_1_3
            + "Anschrift des Hersteller/Lieferanten:\n"
            + "Name\nMusterchemie GmbH\nAdresse\nHafenstraße 4\nD-20457 Hamburg\n"
            + "Telefon\n+49 40 5550123\n"
        )

        contact = read(supplier=supplier).contact_info

        assert contact.supplier_name == "Musterchemie GmbH"
        assert contact.supplier_address == "Hafenstraße 4, D-20457 Hamburg"

    @pytest.mark.spec("SDB-49")
    def test_a_second_label_s_colon_stands_before_the_name(self) -> None:
        supplier = (
            HEADING_1_3
            + "Händler Tel.:: Musterchemie GmbH\nHafenstraße 4\n20457 Hamburg\n"
        )

        contact = read(supplier=supplier).contact_info

        assert contact.supplier_name == "Musterchemie GmbH"
        assert contact.supplier_address == "Hafenstraße 4, 20457 Hamburg"

    @pytest.mark.spec("SDB-49")
    @pytest.mark.parametrize(
        "line",
        [
            "Firmenname: Birkenhof GmbH Birkenhof AG\n",
            "Firmenname: Birkenhof GmbH BIRKENHOF AG Vergiftungsinformationszentrale\n",
        ],
    )
    def test_of_two_companies_side_by_side_the_first_is_the_supplier(
        self, line: str
    ) -> None:
        supplier = HEADING_1_3 + line + "Straße: Hafenstraße 4 Seeweg 12\n"

        assert read(supplier=supplier).contact_info.supplier_name == "Birkenhof GmbH"

    @pytest.mark.spec("SDB-49")
    @pytest.mark.parametrize(
        "name",
        [
            "Musterchemie GmbH & Co Hamburg KG",
            "Dr. Muster & Co. Nachf. GmbH",
            "Holzwerk Nord Zweigniederlassung der Musterholz Vertriebsgesellschaft mbH",
        ],
    )
    def test_one_company_with_two_legal_forms_stays_whole(self, name: str) -> None:
        supplier = HEADING_1_3 + name + "\nHafenstraße 4\n20457 Hamburg\n"

        assert read(supplier=supplier).contact_info.supplier_name == name

    @pytest.mark.spec("SDB-49")
    def test_the_address_behind_dashes_is_the_address(self) -> None:
        supplier = (
            HEADING_1_3
            + "Lieferant: Musterchemie GmbH - Hafenstraße 4 - D-20457 Hamburg\n"
        )

        contact = read(supplier=supplier).contact_info

        assert contact.supplier_name == "Musterchemie GmbH"
        assert contact.supplier_address == "Hafenstraße 4, D-20457 Hamburg"

    @pytest.mark.spec("SDB-49")
    def test_half_a_legal_form_before_the_address_belongs_to_the_name(self) -> None:
        supplier = (
            "1.3 Inverkehrbringer: Musterwerk GmbH\n"
            "KG . Haselring 4 . 81602 Neufeld .\n"
            "GERMANY . www.musterwerk.example\n"
        )

        contact = read(supplier=supplier).contact_info

        assert contact.supplier_name == "Musterwerk GmbH KG"

    @pytest.mark.spec("SDB-49")
    @pytest.mark.parametrize(
        ("printed", "name"),
        [
            ("Musterchemie GmbH*", "Musterchemie GmbH"),
            ("Musterchemie GmbH..", "Musterchemie GmbH"),
            ("MUSTERCHEMIE .", "MUSTERCHEMIE"),
            ("Musterchemie Holdings B.V.,", "Musterchemie Holdings B.V."),
            ("Musterchemie GmbH & Co.", "Musterchemie GmbH & Co."),
            ("Musterchemie a.s.", "Musterchemie a.s."),
            ("Musterchemie Inc.", "Musterchemie Inc."),
        ],
    )
    def test_a_mark_at_the_name_s_end_goes_an_abbreviation_s_stop_stays(
        self, printed: str, name: str
    ) -> None:
        supplier = HEADING_1_3 + printed + "\nHafenstraße 4\n20457 Hamburg\n"

        assert read(supplier=supplier).contact_info.supplier_name == name

    @pytest.mark.spec("SDB-49")
    def test_a_label_alone_on_its_line_is_no_part_of_the_address(self) -> None:
        supplier = (
            HEADING_1_3
            + "Händler\nFirmenname\nMusterchemie GmbH\n"
            + "Geschäftsadresse\nHafenstraße 4\nPostleitzahl\nDE-20457\nOrt\nHamburg\n"
            + "Land\nDeutschland\nTel.\n+49 40 5550123\n"
        )

        contact = read(supplier=supplier).contact_info

        assert contact.supplier_name == "Musterchemie GmbH"
        assert (
            contact.supplier_address == "Hafenstraße 4, DE-20457, Hamburg, Deutschland"
        )
        assert contact.supplier_phone == "+49 40 5550123"

    @pytest.mark.spec("SDB-49")
    def test_another_title_under_1_3_is_not_the_supplier_s_block(self) -> None:
        text_before = (
            "1.1 Bezeichnung des Unternehmens\n"
            "Firma\nMusterbahnen a.s.\n"
            "Sitz\nIndustriestraße 289, 517 42 Musterdorf, Tschechische Republik\n"
            "IdNr.\n25947869\n"
            "Telefon\n+420 494 555 431\n"
        )
        supplier = (
            "1.3 Verwendung des Produkts\n"
            "Abdichtungsbahnen werden im Bauwesen als Schutz von Gebäuden angewendet.\n"
        )

        contact = read(identifier=text_before, supplier=supplier).contact_info

        assert contact.supplier_name == "Musterbahnen a.s."
        assert contact.supplier_address == (
            "Industriestraße 289, 517 42 Musterdorf, Tschechische Republik"
        )
        assert contact.supplier_phone == "+420 494 555 431"

    @pytest.mark.spec("SDB-49")
    def test_the_company_s_designation_is_a_label_of_the_supplier(self) -> None:
        supplier = (
            "Bezeichnung des Unternehmens\n"
            "Musterchemie GmbH\nHafenstraße 4\nD-20457 Hamburg\n"
        )

        assert read(supplier=supplier).contact_info.supplier_name == "Musterchemie GmbH"


class TestEmail:
    @pytest.mark.spec("SDB-50")
    def test_the_poison_centre_s_address_is_not_the_supplier_s(self) -> None:
        supplier = (
            "Bezeichnung des Unternehmens\n"
            "Musterchemie GmbH\nHafenstraße 4\nD-20457 Hamburg\n"
            "T +49 40 5550123\n"
            "Notrufnummer\n"
            "Giftnotruf Musterstadt\n"
            "Telefon: (030) 5550100\n"
            "service@giftnotruf.example\nwww.giftnotruf.example\n"
        )
        text = SHEET.replace(
            "1.4 Notrufnummer\nGiftnotruf Musterstadt: +49 30 5550100\n", ""
        )
        extraction = ExtractionResult(
            text=text.format(header="", identifier=IDENTIFIER, supplier=supplier),
            raw_text="",
            extractor="unit-test",
            pages_sampled=1,
            warnings=[],
            metadata={},
        )

        contact = SDSParser(language="de").parse(extraction).sheet.contact_info

        assert contact.supplier_name == "Musterchemie GmbH"
        assert contact.supplier_email is None
        assert contact.supplier_website is None

    @pytest.mark.spec("SDB-50")
    def test_labels_printed_before_the_values_do_not_end_the_search(self) -> None:
        supplier = (
            "Firma\nTelefon\nEmail-Adresse\nNotrufnummer\n"
            "Musterchemie GmbH\n+49 40 5550123\ninfo@musterchemie.example\n"
        )

        assert (
            read(supplier=supplier).contact_info.supplier_email
            == "info@musterchemie.example"
        )

    @pytest.mark.spec("SDB-50")
    def test_a_first_name_parted_by_a_blank_belongs_to_the_address(self) -> None:
        supplier = SUPPLIER.replace(
            "E-Mail: sdb@musterchemie.example",
            "E-Mail (fachkundige Person): Erika. Muster@musterchemie.example",
        )

        assert read(supplier=supplier).contact_info.supplier_email == (
            "Erika.Muster@musterchemie.example"
        )

    @pytest.mark.spec("SDB-50")
    def test_a_sentence_s_end_before_the_address_is_not_part_of_it(self) -> None:
        supplier = SUPPLIER.replace(
            "E-Mail: sdb@musterchemie.example",
            "Fragen zum Blatt. sdb@musterchemie.example",
        )

        assert (
            read(supplier=supplier).contact_info.supplier_email
            == "sdb@musterchemie.example"
        )

    @pytest.mark.spec("SDB-50")
    def test_a_website_glued_to_the_address_begins_at_www(self) -> None:
        supplier = SUPPLIER.replace(
            "E-Mail: sdb@musterchemie.example",
            "sdb@musterchemie.examplewww.musterchemie.example",
        )

        contact = read(supplier=supplier).contact_info

        assert contact.supplier_email == "sdb@musterchemie.example"
        assert contact.supplier_website == "www.musterchemie.example"


class TestInformationAddress:
    """The address of whoever answers for the sheet, beside the supplier's (SDB-136)."""

    @staticmethod
    def contact(lines: str) -> ContactInfo:
        supplier = (
            HEADING_1_3
            + "Musterchemie GmbH\nHafenstraße 4\n20457 Hamburg\n"
            + "Telefon: +49 40 5550123\n"
            + lines
        )
        return read(supplier=supplier).contact_info

    def email(self, lines: str) -> str | None:
        return self.contact(lines).information_email

    @pytest.mark.spec("SDB-136")
    @pytest.mark.parametrize(
        "lines",
        [
            "E-Mail: info@musterchemie.example\n"
            "E-Mail (sachkundige Person): sdb@musterchemie.example\n",
            "E-Mail: info@musterchemie.example\n"
            "Für das Sicherheitsdatenblatt zuständig:\n"
            "Erika Muster, Produktsicherheit\n"
            "E-Mail Adresse: sdb@musterchemie.example\n",
            "E-Mail: info@musterchemie.example\n"
            "E-Mail-Adresse der\nverantwortlichen\nPerson für dieses\nSDB\n"
            "sdb@musterchemie.example\n",
            "E-Mail: info@musterchemie.example\n"
            "Weitere Angaben\n"
            "E-Mail-Adresse für Fragen zum Sicherheitsdatenblatt: "
            "sdb@musterchemie.example\n",
            "E-Mail sachkundige Person:\nsdb@musterchemie.example\n"
            "info@musterchemie.example\n",
        ],
    )
    def test_the_competent_person_s_address_counts(self, lines: str) -> None:
        assert self.email(lines) == "sdb@musterchemie.example"

    @pytest.mark.spec("SDB-136")
    @pytest.mark.parametrize(
        "lines",
        [
            "E-Mail: info@musterchemie.example\n"
            "Auskunftgebender Bereich:\nAbteilung Produktsicherheit\n"
            "Telefon: +49 40 5550199\nE-Mail: sdb@musterchemie.example\n",
            "info@musterchemie.example\n"
            "Auskunftgebende Stelle\n"
            "Musterchemie AG, CH-3000 Musterlingen. E-mail: sdb@musterchemie.example\n",
            "E-Mail: info@musterchemie.example\n"
            "Ansprechpartner für Informationen sdb@musterchemie.example\n",
        ],
    )
    def test_else_the_address_of_the_office_that_gives_information(
        self, lines: str
    ) -> None:
        assert self.email(lines) == "sdb@musterchemie.example"

    @pytest.mark.spec("SDB-136")
    def test_the_competent_person_goes_before_the_information_office(self) -> None:
        lines = (
            "Technische Auskunft\nBeratung Putz und Fassade\n"
            "beratung@musterchemie.example\n"
            "E-Mail-Adresse der für das SDB zuständigen sachkundigen Person:\n"
            "sdb@musterchemie.example\n"
        )

        assert self.email(lines) == "sdb@musterchemie.example"

    @pytest.mark.spec("SDB-136")
    def test_the_first_of_several_under_the_label(self) -> None:
        lines = (
            "E-Mail: info@musterchemie.example\n"
            "Auskunftgebender Bereich: Abteilung Labor\n"
            "labor@musterchemie.example, leitung@musterchemie.example\n"
        )

        assert self.email(lines) == "labor@musterchemie.example"

    @pytest.mark.spec("SDB-136")
    @pytest.mark.parametrize(
        "lines",
        [
            "E-Mail: info@musterchemie.example\n"
            "Produktmanagement, Herr Muster\n"
            "E-Mail: max.muster@musterchemie.example\n",
            "info@musterchemie.example / info@musterchemie-schweiz.example\n",
        ],
    )
    def test_without_such_a_label_there_is_none(self, lines: str) -> None:
        contact = self.contact(lines)

        assert contact.information_email is None
        assert contact.supplier_email == "info@musterchemie.example"

    @pytest.mark.spec("SDB-136")
    def test_the_supplier_s_address_stays_the_first_of_the_block(self) -> None:
        contact = self.contact(
            "E-Mail: info@musterchemie.example\n"
            "E-Mail (sachkundige Person): sdb@musterchemie.example\n"
        )

        assert contact.supplier_email == "info@musterchemie.example"
        assert contact.information_email == "sdb@musterchemie.example"

    @pytest.mark.spec("SDB-136")
    def test_a_single_address_under_the_label_is_both(self) -> None:
        contact = self.contact(
            "E-Mail-Adresse der sachkundigen Person: sdb@musterchemie.example\n"
        )

        assert contact.supplier_email == "sdb@musterchemie.example"
        assert contact.information_email == "sdb@musterchemie.example"

    @pytest.mark.spec("SDB-136")
    def test_a_single_address_under_no_such_label_is_the_supplier_s_only(
        self,
    ) -> None:
        contact = self.contact("E-Mail: info@musterchemie.example\n")

        assert contact.supplier_email == "info@musterchemie.example"
        assert contact.information_email is None

    @pytest.mark.spec("SDB-136")
    def test_the_office_that_wrote_the_sheet_counts_where_the_label_names_it(
        self,
    ) -> None:
        lines = (
            "E-Mail: info@musterchemie.example\n"
            "Verantwortlich für das Datenblatt:\n"
            "Musterbüro AG, Seeweg 23, 35041 Marburg, info@musterbuero.example\n"
        )

        assert self.email(lines) == "info@musterbuero.example"


class TestFutureDate:
    """A revision date after the day the caller gives (SDB-137)."""

    TODAY = date(2026, 11, 18)

    def codes(self, header: str, today: date | None) -> list[str]:
        sheet = read(header=header)
        return [f.code for f in sheet_findings(sheet, [], today=today)]

    @pytest.mark.spec("SDB-137")
    def test_it_is_reported_and_the_sheet_counts_as_undated(self) -> None:
        sheet = read(header="überarbeitet am: 28.11.28\n")

        findings = sheet_findings(sheet, [], today=self.TODAY)

        assert [f.code for f in findings] == ["revised-in-future", "undated"]
        assert findings[0].params == {"revised": "2028-11-28", "today": "2026-11-18"}
        # The date stays as read.
        assert sheet.revision_date == date(2028, 11, 28)

    @pytest.mark.spec("SDB-137")
    def test_without_a_day_no_date_is_questioned(self) -> None:
        assert "revised-in-future" not in self.codes(
            "überarbeitet am: 28.11.28\n", None
        )
        assert "undated" not in self.codes("überarbeitet am: 28.11.28\n", None)

    @pytest.mark.spec("SDB-137")
    def test_the_issue_date_stands_in_where_it_is_possible(self) -> None:
        header = "überarbeitet am: 28.11.2028\nAusgabedatum: 12.03.2019\n"

        assert self.codes(header, self.TODAY) == [
            "revised-in-future",
            "predates-annex-ii",
        ]

    @pytest.mark.spec("SDB-137")
    def test_an_issue_date_in_the_future_is_reported_too(self) -> None:
        assert self.codes("Ausgabedatum: 28.11.2028\n", self.TODAY) == [
            "issued-in-future",
            "undated",
        ]
        # Beside a possible revision date it is reported and the sheet keeps
        # its age by that date.
        header = "überarbeitet am: 10.01.2023\nAusgabedatum: 28.11.2028\n"
        findings = sheet_findings(read(header=header), [], today=self.TODAY)
        assert [f.code for f in findings] == ["issued-in-future"]
        assert findings[0].params == {"issued": "2028-11-28", "today": "2026-11-18"}

    @pytest.mark.spec("SDB-137")
    def test_the_day_itself_is_not_the_future(self) -> None:
        assert "revised-in-future" not in self.codes(
            "überarbeitet am: 18.11.2026\n", self.TODAY
        )


class TestFurtherSupplierLabels:
    @pytest.mark.spec("SDB-49")
    @pytest.mark.parametrize(
        "supplier",
        [
            HEADING_1_3 + "Name: Musterchemie GmbH\nStraße: Hafenstraße 4\n"
            "Postleitzahl: 20457\nStadt: Hamburg\n",
            "Firmenidentifikation: Musterchemie GmbH\nHafenstraße 4\n20457 Hamburg\n",
        ],
    )
    def test_the_company_stands_behind_the_label(self, supplier: str) -> None:
        contact = read(supplier=supplier).contact_info

        assert contact.supplier_name == "Musterchemie GmbH"
        assert contact.supplier_address is not None
        assert contact.supplier_address.startswith("Hafenstraße 4")

    @pytest.mark.spec("SDB-49")
    def test_a_dash_parts_the_name_from_its_address(self) -> None:
        supplier = (
            HEADING_1_3
            + "Fabrik: Musterchemie srl – Via Roma 4, 20100 Musterstadt – Italy.\n"
        )

        contact = read(supplier=supplier).contact_info

        assert contact.supplier_name == "Musterchemie srl"
        assert contact.supplier_address is not None
        assert contact.supplier_address.startswith("Via Roma 4")
