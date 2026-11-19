"""A file's cover page and what its sheets say about each other.

SDB-2, SDB-138, SDB-139, SDW-30, SDW-35, SDW-36. The sheets, products and
companies are invented; each text shows one form a body of sheets turned up.
"""

from __future__ import annotations

import pytest

from sdb_reader import ask
from sdb_reader.compliance import (
    same_product,
    several_sheets_findings,
    sheet_findings,
)
from sdb_reader.extraction import ExtractionResult
from sdb_reader.messages import Message
from sdb_reader.parser import (
    ParsedSheet,
    SDSParser,
    split_cover_page,
    split_into_sheets,
)
from sdb_reader.reading import read_extraction
from sdb_reader.serialise import reading_to_dict


def _sheet(
    name: str,
    *,
    codes: str = "H315 Verursacht Hautreizungen.",
    revised: str = "03.05.2021",
    version: str = "2.0",
    supplier: str = "Muster Chemie GmbH",
) -> str:
    return (
        "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006\n"
        f"Überarbeitet am: {revised}\n"
        f"Version: {version}\n"
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
        f"1.1 Produktidentifikator\nHandelsname: {name}\n"
        "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
        f"{supplier}\nMusterweg 1\n12345 Musterstadt\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        "2.1 Einstufung des Stoffs oder Gemischs\n"
        "Einstufung gemäß Verordnung (EG) Nr. 1272/2008\n"
        "2.2 Kennzeichnungselemente\n"
        f"Signalwort: Achtung\n{codes}\n"
        "2.3 Sonstige Gefahren\nKeine.\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
        "ABSCHNITT 15: Rechtsvorschriften\nWassergefährdungsklasse: WGK 1\n"
        "ABSCHNITT 16: Sonstige Angaben\nKeine.\n"
    )


def _parse(text: str, *, pages: int = 4) -> ParsedSheet:
    return SDSParser().parse(_extraction(text, pages=pages))


def _extraction(text: str, *, pages: int = 4) -> ExtractionResult:
    return ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=pages,
        warnings=[],
        metadata={},
    )


def _record(text: str) -> dict[str, object]:
    return reading_to_dict(read_extraction(_extraction(text)))


# A cover page that lists the sheets of a pack and has no section of its own.
PACK_COVER = (
    "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006\n"
    "Musterpflege Mix-Display\n"
    "Deckblatt\n"
    "Sicherheitsdatenblätter für Kombipackungen\n"
    "Inhalt\n"
    "Musterpflege Reiniger\n"
    "Musterpflege Politur\n"
    "Überarbeitet am: 09.09.2024\n"
)
# A country's additions to a sheet, with sections of their own.
COUNTRY_COVER = (
    "Seite: 1/2\n"
    "Deckblatt zum Sicherheitsdatenblatt\n"
    "gemäß ChemV\n"
    "Druckdatum: 24.01.2022 Versionsnummer 5 überarbeitet am: 24.01.2022\n"
    "1 Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
    "1.1 Produktidentifikator\nHandelsname: Musterspray Alpin\n"
    "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
    "Alpenhandel Muster AG\nBergweg 2\n8000 Musterhausen\n"
    "1.4 Notrufnummer\nGiftnotruf Musterland: 000 000\n"
    "8 Begrenzung und Überwachung der Exposition/Persönliche Schutzausrüstungen\n"
    "MAK 500 ppm\n"
    "15 Rechtsvorschriften\nSR 813.11 Chemikalienverordnung (ChemV): beachten\n"
)
# A kit's cover page: sections of its own, numbered like a sheet's.
KIT_COVER = (
    "Musterkleber 2K\n"
    "Kit Sicherheitsinformationsblatt (SIS)\n"
    "Ausgabedatum: 07.03.2025   Version: 1.0\n"
    "ABSCHNITT 1: Kit Identifizierung\n"
    "1.1 Kit Identifikator\nHandelsname: Musterkleber 2K\n"
    "ABSCHNITT 2: Allgemeine Hinweise\nLagerung: 5 - 25°C\n"
    "ABSCHNITT 3: Kit Inhalt\n"
    "Musterkleber 2K Komponente A\nMusterkleber 2K Komponente B\n"
)
CLEANER = _sheet("Musterpflege Reiniger", revised="01.02.2021")
POLISH = _sheet(
    "Musterpflege Politur",
    codes="H319 Verursacht schwere Augenreizung.",
    revised="02.03.2022",
)


class TestCoverPage:
    @pytest.mark.spec("SDB-138")
    def test_a_cover_page_is_no_sheet_and_gives_nothing(self) -> None:
        result = _parse(PACK_COVER + CLEANER + POLISH)

        assert result.cover_page is True
        assert [part.sheet.product_identifier for part in result.parts] == [
            "Musterpflege Reiniger",
            "Musterpflege Politur",
        ]
        # The first sheet begins at its own title, not at the cover page.
        assert result.parts[0].text.startswith("Sicherheitsdatenblatt gemäß")
        assert "Deckblatt" not in result.parts[0].text
        # The cover page's date is no sheet's and not the file's.
        assert result.sheet.revision_date is not None
        assert result.sheet.revision_date.isoformat() == "2022-03-02"
        assert all(
            "Deckblatt" not in text for text in result.sheet.section_text.values()
        )

    @pytest.mark.spec("SDB-138")
    def test_the_word_for_a_display_is_given_as_printed(self) -> None:
        assert _parse(PACK_COVER + CLEANER + POLISH).display_term == "Mix-Display"
        other = PACK_COVER.replace("Mix-Display", "Thekenmixdisplay")
        assert _parse(other + CLEANER + POLISH).display_term == "Thekenmixdisplay"
        without = PACK_COVER.replace("Mix-Display", "Kombipackung")
        assert _parse(without + CLEANER + POLISH).display_term is None

    @pytest.mark.spec("SDB-138")
    def test_a_cover_page_with_sections_of_its_own_is_no_second_sheet(self) -> None:
        sheet = _sheet(
            "Musterspray", revised="23.01.2020", supplier="Muster Chemie GmbH"
        )

        result = _parse(COUNTRY_COVER + sheet)

        assert result.cover_page is True
        assert result.parts == []
        assert Message("several-sheets", {"count": 2}) not in result.warnings
        assert result.sheet.product_identifier == "Musterspray"
        assert result.sheet.revision_date is not None
        assert result.sheet.revision_date.isoformat() == "2020-01-23"
        assert result.sheet.contact_info.supplier_name == "Muster Chemie GmbH"
        assert result.sheet.countries == ["DE"]

    @pytest.mark.spec("SDB-138")
    def test_a_kit_s_cover_page_heads_sections_and_is_none_of_the_sheets(self) -> None:
        text = (
            KIT_COVER
            + _sheet("Musterkleber 2K Komponente A")
            + _sheet("Musterkleber 2K Komponente B", version="3.1")
        )

        result = _parse(text)

        assert result.cover_page is True
        assert len(result.parts) == 2
        assert result.parts[0].sheet.version == "2.0"
        assert result.sheet.version == "2.0"

    @pytest.mark.spec("SDB-138")
    @pytest.mark.parametrize(
        "title",
        [
            "SICHERHEITSDATENBLÄTTER",
            "Set aus Sicherheitsdatenblättern bestehend aus:",
            "Set von Sicherheitsdatenblättern bestehend aus:",
            "Setbestandteile",
            "Kit-Sicherheitsdatenblatt",
        ],
    )
    def test_the_titles_a_cover_page_carries(self, title: str) -> None:
        cover = f"Musterset\n{title}\nMusterpflege Reiniger\nMusterpflege Politur\n"

        found, rest = split_cover_page(cover + CLEANER + POLISH)

        assert found == cover.rstrip("\n")
        assert rest == CLEANER + POLISH

    @pytest.mark.spec("SDB-138")
    def test_the_cover_page_and_the_rest_are_the_text_again(self) -> None:
        text = PACK_COVER + CLEANER + POLISH

        assert "\n".join(split_cover_page(text)) == text
        assert "\n".join(split_into_sheets(text)) == split_cover_page(text)[1]

    @pytest.mark.spec("SDB-138")
    def test_a_sheet_without_a_cover_page_has_none(self) -> None:
        display = _sheet("Muster Display Reiniger")
        mention = CLEANER.replace(
            "Gemisch.\n",
            "Kopfteil (Deckblatt) sauber abtrennen.\nDeckblatt entfernen.\n",
        )

        for text in (CLEANER, display, mention):
            result = _parse(text)
            assert result.cover_page is False
            assert result.display_term is None
            assert split_cover_page(text) == ("", text)

    @pytest.mark.spec("SDB-138")
    def test_a_cover_page_with_no_sheet_behind_it_is_none(self) -> None:
        assert split_cover_page(COUNTRY_COVER) == ("", COUNTRY_COVER)
        assert split_cover_page(KIT_COVER) == ("", KIT_COVER)

    @pytest.mark.spec("SDB-138", "SDB-118")
    def test_a_cover_page_in_front_of_one_sheet_leaves_no_parts(self) -> None:
        result = _parse(PACK_COVER + CLEANER)

        assert result.cover_page is True
        assert result.parts == []
        assert result.sheet.revision_date is not None
        assert result.sheet.revision_date.isoformat() == "2021-02-01"


class TestWhatCountsAsASheet:
    CHANGES = (
        "Änderungen mit Version 1.6:\n"
        "Abschnitt 1: UFI\n"
        "Abschnitt 2: Einstufung/Kennzeichnungselemente\n"
        "Abschnitt 3: Zusammensetzung / Angaben zu Bestandteilen\n"
        "Abschnitt 8: Begrenzung und Überwachung der Exposition\n"
    )
    ENGLISH = (
        "SECTION 1: Identification of the substance/mixture and of the company\n"
        "1.1. Product identifier\nMusterpflege Reiniger\n"
        "SECTION 2: Hazards identification\n"
        "2.2. Label elements\nSignal word: Warning\nH315 Causes skin irritation.\n"
        "2.3. Other hazards\nNone.\n"
        "SECTION 3: Composition/information on ingredients\nMixture.\n"
        "SECTION 16: Other information\nNone.\n"
    )

    @pytest.mark.spec("SDB-2")
    def test_a_list_of_sections_that_names_the_label_is_no_sheet(self) -> None:
        text = CLEANER + self.CHANGES

        result = _parse(text)

        assert split_into_sheets(text) == [text]
        assert result.parts == []
        assert Message("several-sheets", {"count": 2}) not in result.warnings

    @pytest.mark.spec("SDB-2")
    def test_the_sheet_once_more_in_another_language_is_no_sheet(self) -> None:
        one = _parse(CLEANER + self.ENGLISH)
        two = _parse(CLEANER + self.ENGLISH + POLISH)

        assert one.parts == []
        assert [part.sheet.product_identifier for part in two.parts] == [
            "Musterpflege Reiniger",
            "Musterpflege Politur",
        ]
        # It stays with the sheet before it.
        assert "SECTION 1" in two.parts[0].text
        assert "Causes skin irritation" not in (
            two.sheet.hazard_statements.hazard_text or ""
        )

    @pytest.mark.spec("SDB-2")
    def test_section_with_the_german_title_is_a_german_sheet(self) -> None:
        second = POLISH.replace("ABSCHNITT", "SECTION")

        assert len(_parse(CLEANER + second).parts) == 2


class TestSameProduct:
    @pytest.mark.spec("SDB-139")
    @pytest.mark.parametrize(
        "names",
        [
            ["Musterkleber Komponente A", "Musterkleber Komponente B"],
            [
                "Musterharz - Komponente A (Mörtel)",
                "Musterharz - Komponente B (Härter)",
            ],
            ["MUSTERGRUND PART A", "Mustergrund Part B"],
            [
                "Mustergrund 40 DE PTA",
                "Mustergrund 40 PART BF; -25°C;",
                "Mustergrund 40 Part C",
            ],
            ["Mustergel TEIL A", "Mustergel TEIL B"],
            ["Musterschaum, Komp. A", "Musterschaum (Komp. B)"],
            ["Musterfix, Comp. A", "MUSTERFIX VINYLESTER COMP B"],
            ["Musterspachtel (Harz)", "Musterspachtel (Härter)"],
            ["Mustermix in Tuben, Harz", "Mustermix in Tuben, Härter"],
            ["Musterpolitur (Polish)", "Musterpolitur (Finish)"],
            ["Musterfarbe 6x25ml-019", "Musterfarbe 6x25ml-031"],
            ["Musterfarbe 10 x 25 ml 005", "Musterfarbe 10 x 25 ml 251"],
            ["Musterdicht Komponente A", "Musterdicht"],
            ["Komponente A Musterfrei", "Komponente B Musterfrei"],
            ["Musterdicht", "MUSTERDICHT"],
        ],
    )
    def test_parts_of_one_product(self, names: list[str]) -> None:
        assert same_product(names)

    @pytest.mark.spec("SDB-139")
    @pytest.mark.parametrize(
        "names",
        [
            ["Musterpflege Reiniger", "Musterpflege Politur"],
            ["Muster AF Unkrautfrei", "Muster Unkrautfrei"],
            ["Musterfix Bindemittel", "Musterfix Sandmischung"],
            ["Blautafel", "Gelb-Tafel"],
            ["Musterkleber Komponente A", "Musterlack Komponente A"],
        ],
    )
    def test_different_products(self, names: list[str]) -> None:
        assert not same_product(names)


class TestFindings:
    @staticmethod
    def codes(result: ParsedSheet) -> list[str]:
        return [
            finding.code
            for finding in sheet_findings(
                result.sheet, result.warnings, parts=result.parts
            )
        ]

    @pytest.mark.spec("SDW-36", "SDB-139")
    def test_sheets_of_different_products_are_reported_with_their_names(self) -> None:
        result = _parse(PACK_COVER + CLEANER + POLISH + CLEANER)

        [finding] = several_sheets_findings(result.parts)

        assert finding == Message(
            "different-products",
            {"products": ["Musterpflege Reiniger", "Musterpflege Politur"]},
        )
        assert "different-products" in self.codes(result)

    @pytest.mark.spec("SDW-36", "SDB-139")
    def test_the_parts_of_one_product_are_not(self) -> None:
        result = _parse(
            _sheet("Musterkleber Komponente A") + _sheet("Musterkleber Komponente B")
        )

        assert len(result.parts) == 2
        assert several_sheets_findings(result.parts) == []

    @pytest.mark.spec("SDW-36", "SDB-139")
    def test_nothing_is_said_where_a_name_is_not_read(self) -> None:
        nameless = POLISH.replace("Handelsname: Musterpflege Politur\n", "")

        result = _parse(CLEANER + nameless)

        assert [part.sheet.product_identifier for part in result.parts] == [
            "Musterpflege Reiniger",
            None,
        ]
        assert several_sheets_findings(result.parts) == []

    @pytest.mark.spec("BIB-20")
    def test_without_the_single_sheets_the_findings_are_as_before(self) -> None:
        result = _parse(CLEANER + POLISH)

        without = [f.code for f in sheet_findings(result.sheet, result.warnings)]

        assert "different-products" not in without
        assert "different-products" in self.codes(result)

    @pytest.mark.spec("SDW-36", "SDB-139")
    def test_editions_for_different_countries_are_compared(self) -> None:
        german = _sheet("Musterspray", version="2 / DE")
        swiss = _sheet(
            "Musterspray",
            version="2 / CH",
            codes="H315 Verursacht Hautreizungen.\nH319 Verursacht schwere Augenreizung.",
        )

        result = _parse(german + swiss)

        assert [part.sheet.countries for part in result.parts] == [["DE"], ["CH"]]
        assert several_sheets_findings(result.parts) == [
            Message("country-editions-differ", {"fields": ["hazard_codes"]})
        ]
        # The file's reading stays the union; nothing is chosen.
        assert result.sheet.hazard_statements.hazard_codes == ["H315", "H319"]

    @pytest.mark.spec("SDW-36", "SDB-139")
    def test_editions_that_agree_are_not_reported(self) -> None:
        german = _sheet("Musterspray", version="2 / DE")
        swiss = _sheet("Musterspray", version="2 / CH", revised="01.01.2022")
        same_country = _sheet("Musterspray", version="3 / DE", codes="H319 Reizt.")

        assert several_sheets_findings(_parse(german + swiss).parts) == []
        assert several_sheets_findings(_parse(german + same_country).parts) == []


class TestTheRecord:
    @pytest.mark.spec("SDW-35")
    def test_the_record_names_the_cover_page_and_the_display(self) -> None:
        with_cover = _record(PACK_COVER + CLEANER + POLISH)
        without = _record(CLEANER)

        assert (with_cover["cover_page"], with_cover["display_term"]) == (
            True,
            "Mix-Display",
        )
        assert (without["cover_page"], without["display_term"]) == (False, None)
        assert with_cover["sheet_count"] == 2
        assert "parts" not in without

    @pytest.mark.spec("SDW-35")
    def test_every_part_names_its_countries_and_its_product(self) -> None:
        record = _record(PACK_COVER + CLEANER + POLISH)

        parts = record["parts"]
        assert isinstance(parts, list)
        assert [
            (part["sheet"]["product_identifier"], part["sheet"]["countries"])
            for part in parts
        ] == [("Musterpflege Reiniger", ["DE"]), ("Musterpflege Politur", ["DE"])]

    @pytest.mark.spec("SDW-36")
    def test_the_record_carries_the_finding(self) -> None:
        record = _record(PACK_COVER + CLEANER + POLISH)

        findings = record["findings"]
        assert isinstance(findings, list)
        [finding] = [f for f in findings if f["code"] == "different-products"]
        assert finding["params"] == {
            "products": ["Musterpflege Reiniger", "Musterpflege Politur"]
        }
        assert "Musterpflege Reiniger" in finding["message"]


class TestAsking:
    @pytest.mark.spec("SDW-30", "SDB-138")
    def test_the_cover_page_is_not_sent(self) -> None:
        several = ask.build_requests(
            _extraction(PACK_COVER + CLEANER + POLISH), "pack.pdf", pages=4
        )
        one = ask.build_requests(_extraction(PACK_COVER + CLEANER), "one.pdf", pages=4)

        assert len(several) == 2
        assert len(one) == 1
        for request in (*several, one[0]):
            assert request.text.startswith("Sicherheitsdatenblatt gemäß")
            assert "Deckblatt" not in request.text
            assert request.sent == "before-section-3"

    @pytest.mark.spec("SDW-30")
    def test_the_question_is_the_same_with_and_without_a_cover_page(self) -> None:
        [with_cover] = ask.build_requests(
            _extraction(PACK_COVER + CLEANER), "a.pdf", pages=4
        )
        [without] = ask.build_requests(_extraction(CLEANER), "a.pdf", pages=4)

        assert ask.question_fingerprint(with_cover.prompt) == ask.question_fingerprint(
            without.prompt
        )
        assert with_cover.text == without.text
