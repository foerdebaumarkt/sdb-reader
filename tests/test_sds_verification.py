from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from sdb_reader.extraction import ExtractionResult, extract_pdf_text
from sdb_reader.messages import Message
from sdb_reader.verification import DocumentKind, SDSVerifier, Verification


def _write_pdf(path: Path, text: str) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    _write_pdf(
        tmp_path / "0000000000000_00000_SD_6.pdf",
        """Sicherheitsdatenblatt
ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
Produktname: Bad- und Küchenfarbe
ABSCHNITT 2: Mögliche Gefahren
Verordnung (EG) Nr. 1907/2006
H412: Schädlich für Wasserorganismen, mit langfristiger Wirkung.
P101: Ist ärztlicher Rat erforderlich, Verpackung oder Kennzeichnungsetikett bereithalten.
""",
    )
    _write_pdf(
        tmp_path / "0000000000000_00000_UP_2.pdf",
        """Produktprospekt
ABSCHNITT 1: Allgemeine Hinweise
Dekorativer Anstrich für Innenräume.
""",
    )
    return tmp_path


@pytest.fixture
def verifier() -> SDSVerifier:
    return SDSVerifier()


def test_verifier_accepts_genuine_sds(verifier: SDSVerifier, data_dir: Path) -> None:
    result = verifier.verify(
        extract_pdf_text(data_dir / "0000000000000_00000_SD_6.pdf")
    )

    assert result.kind is DocumentKind.SAFETY_DATA_SHEET
    assert result.errors == []
    assert "no-title-keywords" not in [warning.code for warning in result.warnings]


def test_verifier_rejects_negative_control(
    verifier: SDSVerifier, data_dir: Path
) -> None:
    result = verifier.verify(
        extract_pdf_text(data_dir / "0000000000000_00000_UP_2.pdf")
    )

    assert result.kind is DocumentKind.DOCUMENT
    assert result.errors


def test_an_unreadable_document_is_refused(verifier: SDSVerifier) -> None:
    """A file that cannot be read never reaches verify; the verdict still
    comes from here."""
    reason = Message("pdf-unreadable", {"detail": "damaged"})
    result = verifier.refuse_unreadable([reason])

    assert result.kind is DocumentKind.DOCUMENT
    assert result.errors == [reason]


@pytest.mark.spec("SDB-59")
class TestTitleLine:
    """The words must stand as a title, not merely occur in the text."""

    @staticmethod
    def _verify(text: str) -> bool:
        extraction = ExtractionResult(
            text=text,
            raw_text=text,
            extractor="unit-test",
            pages_sampled=1,
            warnings=[],
            metadata={},
        )
        return SDSVerifier().verify(extraction).kind is DocumentKind.SAFETY_DATA_SHEET

    def test_a_document_naming_it_only_in_running_text_is_refused(self) -> None:
        """One supplier's battery "Sicherheitsinformationen": the word appears in a
        contact line and in the sentence saying no sheet is required."""
        text = (
            "Sicherheitsinformationen\n"
            "ABSCHNITT 1: Bezeichnung\n"
            "Verantwortlich für das Sicherheitsdatenblatt: sds@example.com\n"
            "Daher besteht keine Verpflichtung, ein Sicherheitsdatenblatt\n"
            "gemäß Artikel 31 zur Verfügung zu stellen.\n"
        )

        assert self._verify(text) is False

    @pytest.mark.parametrize(
        "title",
        [
            "Sicherheitsdatenblatt",
            "EG-SICHERHEITSDATENBLATT (VERORDNUNG (EG) n° 1907/2006 - REACH)",
            "Produkt-Sicherheitsdatenblatt",
            "• Sicherheitsdatenblatt gemäß EU-Verordnung 2015/830",
        ],
    )
    def test_a_title_line_passes(self, title: str) -> None:
        assert self._verify(f"Seite 1/8\n{title}\nABSCHNITT 1: Bezeichnung\n") is True

    @pytest.mark.parametrize(
        "line",
        [
            # EUH210, on its own line in a technical data sheet.
            "Sicherheitsdatenblatt auf Anfrage erhältlich.",
            "Sicherheitsdatenblatt auf Anfrage",
            "Safety data sheet available on request.",
            # The end of a sentence that wraps before the word.
            "Sicherheitsdatenblatt.",
        ],
    )
    def test_a_sentence_beginning_its_line_with_the_word_is_no_title(
        self, line: str
    ) -> None:
        text = (
            "Technisches Merkblatt\n"
            "Hinweise zur Entsorgung entnehmen Sie bitte dem\n"
            f"{line}\n"
            "Entsorgung\n"
        )
        assert self._verify(text) is False

    @pytest.mark.spec("SDB-66")
    def test_without_the_title_sections_and_the_regulation_make_no_sheet(self) -> None:
        text = (
            "ABSCHNITT 1: Bezeichnung des Stoffs\ngemäß Verordnung (EG) Nr. 1907/2006\n"
        )
        assert self._verify(text) is False

    @pytest.mark.spec("SDB-68")
    def test_the_english_title_alone_makes_no_german_sheet(self) -> None:
        assert (
            self._verify("Page 1/8\nSAFETY DATA SHEET\nSECTION 1: Identification\n")
            is False
        )


def _judge(text: str) -> Verification:
    extraction = ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )
    return SDSVerifier().verify(extraction)


_TITLES = [
    "Bezeichnung des Stoffs beziehungsweise des Gemischs und des Unternehmens",
    "Mögliche Gefahren",
    "Zusammensetzung/Angaben zu Bestandteilen",
    "Erste-Hilfe-Maßnahmen",
    "Maßnahmen zur Brandbekämpfung",
    "Maßnahmen bei unbeabsichtigter Freisetzung",
    "Handhabung und Lagerung",
    "Begrenzung und Überwachung der Exposition/Persönliche Schutzausrüstungen",
    "Physikalische und chemische Eigenschaften",
    "Stabilität und Reaktivität",
    "Toxikologische Angaben",
    "Umweltbezogene Angaben",
    "Hinweise zur Entsorgung",
    "Angaben zum Transport",
    "Rechtsvorschriften",
    "Sonstige Angaben",
]


def _laid_out(heading: str = "ABSCHNITT", sections: int = 16) -> str:
    """The body of a document in the layout of a safety data sheet."""
    return "".join(
        f"{heading} {n}: {_TITLES[n - 1]}\n{n}.1 Angaben\nText zu Abschnitt {n}.\n"
        for n in range(1, sections + 1)
    )


class TestWhatAFileIs:
    """Its name decides the kind, its layout what else it may be."""

    @pytest.mark.spec("SDB-66")
    def test_the_german_title_makes_a_safety_data_sheet(self) -> None:
        result = _judge("Sicherheitsdatenblatt\n" + _laid_out())
        assert result.kind is DocumentKind.SAFETY_DATA_SHEET
        assert result.prints_statement_codes is None

    @pytest.mark.spec("SDB-66")
    def test_a_misspelled_title_is_a_title(self) -> None:
        """One supplier files a sheet titled "Sichheitsdatenblatt"."""
        result = _judge(
            "Sichheitsdatenblatt\nGemäß 1907/2006 EG, Artikel 31\n" + _laid_out()
        )
        assert result.kind is DocumentKind.SAFETY_DATA_SHEET

    @pytest.mark.spec("SDB-66")
    def test_another_word_of_its_length_is_no_title(self) -> None:
        result = _judge("Sicherheitsinformationen\n" + _laid_out())
        assert result.kind is DocumentKind.SAFETY_INFORMATION

    @pytest.mark.spec("SDB-66")
    def test_the_layout_without_the_title_is_a_safety_information(self) -> None:
        """A battery information sheet, a notice under Article 32."""
        result = _judge(
            "Produkt-Sicherheitshinweis\ngemäß REACH (Artikel 32)\n" + _laid_out()
        )
        assert result.kind is DocumentKind.SAFETY_INFORMATION
        assert result.prints_statement_codes is None
        assert [error.code for error in result.errors] == ["safety-information"]

    @pytest.mark.spec("SDB-105")
    def test_the_title_over_no_section_is_a_cover(self) -> None:
        """One adhesive kit: one page, the title, "Set/Mehr-Komponenten
        Produkt", and nothing else."""
        result = _judge(
            "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006\n"
            "Seite 1 von 1\nTangit M3000 FTTH\nüberarbeitet am: 02.01.2026\n"
            "Set/Mehr-Komponenten Produkt\n"
        )
        assert result.kind is DocumentKind.DOCUMENT
        assert [error.code for error in result.errors] == ["cover-only"]

    @pytest.mark.spec("SDB-105")
    def test_the_title_over_one_section_is_a_sheet(self) -> None:
        result = _judge(
            "Sicherheitsdatenblatt\nABSCHNITT 2: Mögliche Gefahren\n"
            "2.1 Einstufung des Stoffs oder Gemischs\nNicht eingestuft.\n"
        )
        assert result.kind is DocumentKind.SAFETY_DATA_SHEET

    @pytest.mark.spec("SDB-66")
    def test_eleven_sections_are_no_layout(self) -> None:
        result = _judge(
            "Merkblatt\n" + _laid_out(sections=11).replace(".1 Angaben", " Angaben")
        )
        assert result.kind is DocumentKind.DOCUMENT

    @pytest.mark.spec("SDB-68")
    def test_the_numbering_makes_a_sheet_in_another_language(self) -> None:
        """Whatever the language: the numbers of Annex II are the same in all."""
        text = "Scheda di dati di sicurezza\n" + "".join(
            f"SEZIONE {n}: titolo\n{n}.1 Informazioni\nTesto.\n" for n in range(1, 17)
        )
        result = _judge(text)
        assert result.kind is DocumentKind.FOREIGN_SAFETY_DATA_SHEET

    @pytest.mark.spec("SDB-68")
    def test_sections_under_english_headings_are_no_german_layout(self) -> None:
        result = _judge("Product data sheet\n" + _laid_out(heading="SECTION"))
        assert result.kind is DocumentKind.FOREIGN_SAFETY_DATA_SHEET

    @pytest.mark.spec("SDB-68")
    @pytest.mark.parametrize(
        ("codes", "printed"),
        [
            ("H317 / P261-P272-P280", True),
            ("H317 und P261", False),
            ("Betonmischer BM P150 L", False),
        ],
    )
    def test_three_different_codes_say_the_product_is_labelled(
        self, codes: str, printed: bool
    ) -> None:
        result = _judge(f"Bestätigung\nWarnhinweise\n{codes}\n")
        assert result.kind is DocumentKind.DOCUMENT
        assert result.prints_statement_codes is printed


def _leaflet_body() -> str:
    """Sixteen sections in a leaflet's own order, with its ingredients' codes."""
    titles = [
        "Stoff / Zusammensetzungs- und Firmenbezeichnung",
        "Gefahrenstoffe",
        "Mögliche Gefahren",
        "Erste Hilfe Maßnahmen",
        "Maßnahmen zur Brandbekämpfung",
        "Maßnahmen zur unbeabsichtigten Freisetzung",
        "Handhabung und Lagerung",
        "Expositionsbegrenzung und persönliche Schutzausrüstung",
        "Physikalische und chemische Eigenschaften",
        "Stabilität und Reaktivität",
        "Angabe zur Toxikologie der Inhaltsstoffe",
        "Angaben zur Ökologie der Inhaltsstoffe",
        "Hinweise zur Verwertung",
        "Transportvorschriften",
        "Kennzeichnung",
        "Sonstige Angaben",
    ]
    lines = []
    for number, title in enumerate(titles, start=1):
        lines.append(f"{number}  {title}")
        lines.append(
            "Schwefelsäure 29 Gew. % Einstufung nach EG1272/2008 CLP H290 H314"
            if number == 2
            else f"Angaben zu Abschnitt {number}."
        )
    return "\n".join(lines) + "\n"


class TestALineThatIsNoTitle:
    """The word at a line's start is not always what the file calls itself."""

    @pytest.mark.spec("SDB-140")
    @pytest.mark.parametrize(
        ("before", "line"),
        [
            (
                "Der Anwender hat die in diesem",
                "Sicherheitsdatenblatt enthaltenen Daten",
            ),
            (
                "Wortlaut aller Abkürzungen im vorliegenden",
                "Sicherheitsdatenblatt sind wie folgt:",
            ),
        ],
    )
    def test_a_sentence_that_wraps_before_the_word_is_no_title(
        self, before: str, line: str
    ) -> None:
        result = _judge(
            "Merkblatt zur sicheren Verwendung\n"
            + _laid_out()
            + f"{before}\n{line} zu beachten.\n"
        )
        assert result.kind is DocumentKind.SAFETY_INFORMATION
        assert [error.code for error in result.errors] == ["safety-information"]

    @pytest.mark.spec("SDB-140")
    def test_without_the_layout_such_a_file_is_a_document(self) -> None:
        result = _judge(
            "Technisches Merkblatt\nBeachten Sie die in diesem\n"
            "Sicherheitsdatenblatt enthaltenen Daten.\n"
        )
        assert result.kind is DocumentKind.DOCUMENT
        assert [error.code for error in result.errors] == ["title-in-running-text"]

    @pytest.mark.spec("SDB-140")
    @pytest.mark.parametrize(
        "title",
        [
            "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006",
            "Sicherheitsdatenblatt gemäss 1907/2006/EG",
            "Sicherheitsdatenblatt nach Verordnung (EG) Nr. 1907/2006",
            "Sicherheitsdatenblatt in Anlehnung an Verordnung (EG) Nr. 1907/2006",
            "Sicherheitsdatenblatt für Dünnbettmörtel",
            "Sicherheitsdatenblatt vom: 03.05.2021",
        ],
    )
    def test_a_title_under_a_name_in_lower_case_stays_a_title(self, title: str) -> None:
        result = _judge(f"Fugenmasse weiß\n{title}\n" + _laid_out())
        assert result.kind is DocumentKind.SAFETY_DATA_SHEET

    @pytest.mark.spec("SDB-140")
    def test_a_sentence_that_begins_with_the_word_stays_a_title(self) -> None:
        """Only a line the sentence before runs into is none."""
        result = _judge(
            "Angaben nach bestem Wissen. Dieses\n"
            "Sicherheitsdatenblatt beschreibt Produkte im Hinblick auf Sicherheit.\n"
            + _laid_out()
        )
        assert result.kind is DocumentKind.SAFETY_DATA_SHEET

    @pytest.mark.spec("SDB-140")
    def test_one_real_title_is_enough(self) -> None:
        result = _judge(
            "Sicherheitsdatenblatt\n"
            + _laid_out()
            + "Die in diesem\nSicherheitsdatenblatt enthaltenen Daten gelten.\n"
        )
        assert result.kind is DocumentKind.SAFETY_DATA_SHEET

    @pytest.mark.spec("SDB-141")
    @pytest.mark.parametrize(
        "title",
        [
            "Sicherheitsdatenblatt\nzum sicheren Umgang mit Bleibatterien\nSTAND: 06/2022",
            "Sicherheitsdatenblatt zum sicheren Umgang mit Batterien",
            "Sicherheitsdatenblatt\n\nzum sicheren Umgang mit Akkumulatoren",
        ],
    )
    def test_a_leaflet_on_handling_an_article_is_a_safety_information(
        self, title: str
    ) -> None:
        result = _judge(f"{title}\n" + _leaflet_body())
        assert result.kind is DocumentKind.SAFETY_INFORMATION
        assert result.prints_statement_codes is None
        assert [error.code for error in result.errors] == ["leaflet-title"]

    @pytest.mark.spec("SDB-141")
    def test_a_leaflet_without_the_layout_is_a_document(self) -> None:
        result = _judge(
            "Sicherheitsdatenblatt\nzum sicheren Umgang mit Batterien\n"
            "1  Angaben zum Produkt\nBatterie, gefüllt.\n"
        )
        assert result.kind is DocumentKind.DOCUMENT
        assert [error.code for error in result.errors] == ["leaflet-title"]

    @pytest.mark.spec("SDB-141")
    def test_a_sheet_that_names_the_regulation_stays_a_sheet(self) -> None:
        result = _judge(
            "Sicherheitsdatenblatt\nzum sicheren Umgang mit Batterien\n"
            "gemäß Verordnung (EG) Nr. 1907/2006\n" + _laid_out()
        )
        assert result.kind is DocumentKind.SAFETY_DATA_SHEET

    @pytest.mark.spec("SDB-141")
    def test_the_words_further_down_make_no_leaflet(self) -> None:
        """A heading of section 7 under the page header is not the title's rest."""
        result = _judge(
            "Sicherheitsdatenblatt\nHaftgrund 5 l\n"
            "7.1 Schutzmaßnahmen zum sicheren Umgang mit dem Produkt\n" + _laid_out()
        )
        assert result.kind is DocumentKind.SAFETY_DATA_SHEET

    @pytest.mark.spec("SDB-141")
    def test_another_title_line_keeps_the_sheet(self) -> None:
        result = _judge(
            "Sicherheitsdatenblatt\nzum sicheren Umgang mit Batterien\n"
            + _leaflet_body()
            + "EG-Sicherheitsdatenblatt\nSeite 2\n"
        )
        assert result.kind is DocumentKind.SAFETY_DATA_SHEET
