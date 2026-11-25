"""The layout reader: a page's text layer in print order (SDB-42 to SDB-46).

The pages are written here with PyMuPDF, which stores text in the order it is
inserted, so a test can give the file one order and the page another -- the
way one supplier's sheets store every label, then every colon, then every value.
Helvetica at 10 points makes words 13.7 high: rows 13 apart are lines of one
paragraph, rows 20 apart are separate ones.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from sdb_reader import extraction
from sdb_reader.extraction import extract_pdf_text, normalise_pdf_text
from sdb_reader.layout import page_text
from sdb_reader.parser import SDSParser

Placed = tuple[float, float, str] | tuple[float, float, str, float]


def _write(page: pymupdf.Page, items: tuple[Placed, ...]) -> None:
    for x, y, text, *size in items:
        page.insert_text((x, y), text, fontsize=size[0] if size else 10)


def _read(*items: Placed) -> list[str]:
    """The lines the reader makes of *items*, written to the file in this order."""
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        _write(page, items)
        return page_text(page).split("\n")


def _right(x1: float, y: float, text: str, size: float = 8) -> Placed:
    """*text* set so that its words' box ends at *x1*, as a right-aligned label is.

    Measured on a scratch page: the box ends where the glyphs do, which is
    not where their advance widths add up to.
    """
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((0, 100), text, fontsize=size)
        end = max(word[2] for word in page.get_text("words"))
    return (x1 - end, y, text, size)


# one supplier's label block, stored column by column: the labels, then the
# colons, then the values.
_LABELS: tuple[Placed, ...] = (
    (23, 120, "Signalwort"),
    (23, 140, "Gefahrenhinweise"),
    (23, 160, "Sicherheitshinweise"),
    (29, 180, "Allgemein"),
    (29, 230, "Prävention"),
    (23, 250, "Ergänzende"),
    (23, 263, "Kennzeichnungselemente"),
)
_COLONS: tuple[Placed, ...] = (
    (160, 120, ":"),
    (160, 140, ":"),
    (160, 180, ":"),
    (160, 230, ":"),
    (160, 250, ":"),
)
_VALUES: tuple[Placed, ...] = (
    (170, 120, "Kein Signalwort."),
    (170, 140, "H412 - Schädlich für Wasserorganismen, mit langfristiger Wirkung."),
    (170, 180, "P102 - Darf nicht in die Hände von Kindern gelangen."),
    (170, 193, "P101 - Ist ärztlicher Rat erforderlich, Verpackung oder"),
    (170, 206, "Kennzeichnungsetikett bereithalten."),
    (170, 230, "P273 - Freisetzung in die Umwelt vermeiden."),
    (170, 250, "Enthält Octhilinon (ISO). Kann allergische Reaktionen"),
    (170, 263, "hervorrufen."),
)


@pytest.mark.spec("SDB-42")
class TestPrintOrder:
    def test_rows_follow_the_page_not_the_file(self) -> None:
        assert _read((72, 213, "Zweite Zeile"), (72, 200, "Erste Zeile")) == [
            "Erste Zeile",
            "Zweite Zeile",
        ]

    def test_the_words_of_a_cell_read_left_to_right(self) -> None:
        assert _read((100, 200, "Zeile"), (72, 200, "Erste")) == ["Erste Zeile"]

    def test_a_pictogram_glyph_is_no_part_of_its_labels_row(self) -> None:
        """DR's sheets draw GHS02 as a "d" in a symbol font at 33 points,
        centred on the line "GHS02 Flamme"."""
        assert _read((130, 600, "GHS02 Flamme"), (87, 610, "d", 33)) == [
            "GHS02 Flamme",
            "d",
        ]

    def test_a_glyph_between_a_label_and_its_value_keeps_them_together(
        self,
    ) -> None:
        assert _read(
            (23, 274.1, "Gefahrenhinweise"),
            (160, 274.6, ": H412 Schädlich für Wasserorganismen."),
            (120, 285, "d", 33),
        ) == ["Gefahrenhinweise: H412 Schädlich für Wasserorganismen.", "d"]

    def test_a_superscript_stays_in_its_row(self) -> None:
        assert _read((72, 200, "Dichte 1,2 g/cm"), (139, 196, "3", 6)) == [
            "Dichte 1,2 g/cm3"
        ]

    def test_a_word_printed_on_itself_is_read_once(self) -> None:
        """Faux bold: the same word drawn twice, half a point apart."""
        assert _read((72, 200, "ACHTUNG"), (72.5, 200, "ACHTUNG")) == ["ACHTUNG"]

    def test_narrow_words_side_by_side_are_all_kept(self) -> None:
        assert _read((72, 200, "-"), (78, 200, "-"), (84, 200, "-")) == ["- - -"]

    def test_every_word_reaches_the_text_once(self) -> None:
        """Nothing is lost or doubled: the page's letters, colons aside."""
        with pymupdf.open() as doc:
            page = doc.new_page(width=595, height=842)
            _write(page, (*_LABELS, *_COLONS, *_VALUES))
            words = "".join(w[4] for w in page.get_text("words"))
            text = page_text(page)

        def letters(value: str) -> list[str]:
            return sorted(c for c in value if not c.isspace() and c != ":")

        assert letters(text) == letters(words)

    def test_rotated_text_stands_after_the_page(self) -> None:
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text((30, 700), "Randnotiz", fontsize=10, rotate=90)
            page.insert_text((72, 100), "Oben", fontsize=10)

            assert page_text(page) == "Oben\nRandnotiz"

    def test_skewed_text_keeps_its_lines(self) -> None:
        """A page set a degree off horizontal is rotated text, line by line."""
        with pymupdf.open() as doc:
            page = doc.new_page()
            for y, line in ((100, "Erste Zeile"), (115, "Zweite Zeile")):
                page.insert_text(
                    (72, y),
                    line,
                    fontsize=10,
                    morph=(pymupdf.Point(72, y), pymupdf.Matrix(1).prerotate(1)),
                )

            assert page_text(page).split("\n") == ["Erste Zeile", "Zweite Zeile"]

    def test_text_set_at_zero_height_does_not_break_the_page(self) -> None:
        """PyMuPDF's "dict" leaves such a line out, its "words" count it."""
        with pymupdf.open() as doc:
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 100), "x", fontsize=10)
            font = page.get_fonts()[0][4]
            stream = (
                f"BT /{font} 10 Tf 1 0 0 0 72 700 Tm (flach) Tj "
                f"1 0 0 1 72 688 Tm (normale Zeile) Tj ET"
            ).encode()
            doc.update_stream(page.get_contents()[0], stream)

            assert "normale Zeile" in page_text(page)


@pytest.mark.spec("SDB-43")
class TestLabelAndValue:
    def test_a_form_stored_column_by_column_reads_pair_by_pair(self) -> None:
        assert _read(*_LABELS, *_COLONS, *_VALUES) == [
            "Signalwort: Kein Signalwort.",
            "Gefahrenhinweise: H412 - Schädlich für Wasserorganismen, mit "
            "langfristiger Wirkung.",
            "Sicherheitshinweise",
            "Allgemein: P102 - Darf nicht in die Hände von Kindern gelangen.",
            "P101 - Ist ärztlicher Rat erforderlich, Verpackung oder",
            "Kennzeichnungsetikett bereithalten.",
            "Prävention: P273 - Freisetzung in die Umwelt vermeiden.",
            "Ergänzende Kennzeichnungselemente: Enthält Octhilinon (ISO). Kann "
            "allergische Reaktionen",
            "hervorrufen.",
        ]

    def test_the_label_reaches_the_parser_whole(self, tmp_path: Path) -> None:
        """P101 and P102 stood behind the 2.3 heading in the file's order, out
        of the block SDB-4 reads as the label."""
        pdf = tmp_path / "akzo.pdf"
        with pymupdf.open() as doc:
            page = doc.new_page(width=595, height=842)
            _write(
                page,
                (
                    (17, 60, "ABSCHNITT 2: Mögliche Gefahren"),
                    (17, 90, "2.2 Kennzeichnungselemente"),
                    (17, 320, "2.3 Sonstige Gefahren"),
                    *_LABELS,
                    *_COLONS,
                    *_VALUES,
                    (17, 360, "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen"),
                ),
            )
            doc.save(pdf)

        hazards = SDSParser().parse(extract_pdf_text(pdf)).sheet.hazard_statements

        assert hazards.precautionary_codes == ["P101", "P102", "P273"]
        assert hazards.hazard_codes == ["H412"]

    def test_two_pairs_on_one_row_are_two_lines(self) -> None:
        assert _read(
            (17, 800, "Ausgabedatum/Überarbeitungsdatum", 8),
            (346, 800, "Version", 8),
            (175, 800, ": 26-1-2024", 8),
            (384, 800, ": 1", 8),
        ) == ["Ausgabedatum/Überarbeitungsdatum: 26-1-2024", "Version: 1"]

    def test_a_label_ending_in_its_colon_takes_the_cell_beside_it(self) -> None:
        assert _read((72, 200, "Telefon:"), (250, 200, "+49 551 400729")) == [
            "Telefon: +49 551 400729"
        ]

    def test_every_pair_of_a_row_takes_its_further_lines(self) -> None:
        assert _read(
            (17, 800, "Ausgabedatum/", 8),
            (120, 800, ": 26-1-2024", 8),
            (346, 800, "Version", 8),
            (384, 800, ": 1", 8),
            (17, 809, "Überarbeitungsdatum", 8),
        ) == ["Ausgabedatum/ Überarbeitungsdatum: 26-1-2024", "Version: 1"]

    def test_a_label_broken_at_a_hyphen_is_joined(self) -> None:
        assert _read(
            (23, 200, "Kennzeichnungs-"),
            (23, 213, "elemente"),
            (160, 200, ": Enthält Octhilinon."),
            (23, 240, "PBT-"),
            (23, 253, "Stoffe"),
            (160, 240, ": Keine."),
            (23, 280, "Anhang XVII -"),
            (23, 293, "Beschränkungen"),
            (160, 280, ": Nicht anwendbar."),
        ) == [
            "Kennzeichnungselemente: Enthält Octhilinon.",
            "",
            "PBT-Stoffe: Keine.",
            "",
            "Anhang XVII - Beschränkungen: Nicht anwendbar.",
        ]

    def test_a_line_left_aligned_above_a_pair_is_no_part_of_its_label(
        self,
    ) -> None:
        assert _read(
            (71, 200, "Handschutz"),
            (71, 213, "Material:"),
            (180, 213, "Nitrilkautschuk"),
        ) == ["Handschutz", "Material: Nitrilkautschuk"]

    def test_a_colon_on_each_side_is_one(self) -> None:
        assert _read((72, 200, "Telefon:"), (180, 200, ": 0551 400729")) == [
            "Telefon: 0551 400729"
        ]

    def test_a_date_is_no_page_number(self) -> None:
        assert _read((72, 200, "Stand"), (180, 200, ": 05/22")) == ["Stand: 05/22"]

    def test_a_colon_alone_is_kept(self) -> None:
        assert _read((160, 200, ":")) == [":"]

    def test_a_right_aligned_label_begins_a_row_higher(self) -> None:
        """One sheet sets "Ausgabedatum/Überarbeitungsd" above "atum:"."""
        assert _read(
            _right(280, 777, "Ausgabedatum/Überarbeitungsd"),
            (85, 786, "Version:", 8),
            (125, 786, "1.0", 8),
            _right(283, 786, "atum:"),
            (300, 786, "27.04.2020", 8),
        ) == ["Version: 1.0", "Ausgabedatum/Überarbeitungsd atum: 27.04.2020"]

    def test_a_page_number_beside_a_pair_is_a_line_of_its_own(self) -> None:
        assert _read(
            (17, 800, "Datum der letzten Ausgabe"),
            (175, 800, ": Keine frühere Validierung"),
            (346, 800, "1/20"),
        ) == ["Datum der letzten Ausgabe: Keine frühere Validierung", "1/20"]

    def test_a_page_number_is_no_labels_value(self) -> None:
        assert _read(
            (35, 117, "Überarbeitet am: 02.01.2023"),
            (270, 117, "Materialnummer:"),
            (506, 117, "Seite 2 von 13"),
        ) == ["Überarbeitet am: 02.01.2023", "Materialnummer:", "Seite 2 von 13"]


@pytest.mark.spec("SDB-44")
class TestTables:
    def test_a_heading_row_over_its_values_keeps_the_files_order(self) -> None:
        """SAP's header: each column is one cell of two lines."""
        assert _read(
            (71, 150, "Version"),
            (71, 163, "7.2"),
            (140, 150, "Überarbeitet am:"),
            (140, 163, "17.02.2025"),
            (260, 150, "SDB-Nummer:"),
            (260, 163, "6001481"),
        ) == [
            "Version",
            "7.2",
            "Überarbeitet am:",
            "17.02.2025",
            "SDB-Nummer:",
            "6001481",
        ]

    def test_a_label_without_its_value_stays_in_its_table(self) -> None:
        """SAP centres "Sicherheitshinweise :" on the middle of P101."""
        assert _read(
            (92, 760, "Sicherheitshinweise"),
            (223, 760, ":"),
            (240, 754, "P101"),
            (297, 754, "Ist ärztlicher Rat erforderlich, Verpackung oder"),
            (297, 766, "Kennzeichnungsetikett bereithalten."),
        ) == [
            "Sicherheitshinweise",
            ":",
            "P101",
            "Ist ärztlicher Rat erforderlich, Verpackung oder",
            "Kennzeichnungsetikett bereithalten.",
        ]

    def test_a_label_far_below_a_table_is_no_part_of_it(self) -> None:
        assert _read(
            (240, 100, "P101"),
            (297, 100, "Ist ärztlicher Rat erforderlich."),
            (92, 400, "Sicherheitshinweise"),
            (223, 400, ":"),
        ) == ["P101", "Ist ärztlicher Rat erforderlich.", "", "Sicherheitshinweise:"]

    def test_a_line_after_an_empty_lines_space_is_no_part_of_the_table(
        self,
    ) -> None:
        assert _read(
            (240, 100, "P101"),
            (297, 100, "Ist ärztlicher Rat erforderlich."),
            (297, 140, "1 / 12"),
        ) == ["P101", "Ist ärztlicher Rat erforderlich.", "", "1 / 12"]


@pytest.mark.spec("SDB-45")
class TestEmptyLines:
    def test_space_for_an_empty_line_is_one(self) -> None:
        assert _read((72, 200, "Oben"), (72, 240, "Unten")) == ["Oben", "", "Unten"]
        assert _read((72, 200, "Oben"), (72, 213, "Unten")) == ["Oben", "Unten"]

    def test_a_word_broken_at_the_foot_of_a_page_keeps_off_the_page_number(
        self,
    ) -> None:
        text = "\n".join(
            _read(
                (92, 767, "Ist ärztlicher Rat erforderlich, Verpackung oder Kenn-"),
                (285, 795, "1 / 12"),
            )
        )

        assert "Kenn1" not in normalise_pdf_text(text)

    def test_a_word_broken_at_a_tables_end_meets_nothing_below(self) -> None:
        text = "\n".join(
            _read(
                (92, 100, "Langfristig gewässergefähr-"),
                (285, 100, "H413"),
                (23, 113, "Signalwort"),
                (160, 113, ": Achtung"),
            )
        )

        assert "gefährSignalwort" not in normalise_pdf_text(text)

    def test_a_word_broken_at_a_cells_end_meets_no_other_cell(self) -> None:
        text = "\n".join(
            _read(
                (92, 767, "Langfristig (chronisch) gewässergefähr-"),
                (285, 767, "H413: Kann für Wasserorganismen schädlich sein,"),
            )
        )

        assert "gewässergefährH413" not in normalise_pdf_text(text)

    def test_a_word_broken_beside_its_code_runs_on_at_the_codes_column(
        self,
    ) -> None:
        """SAP wraps "P101 Ist ärztlicher Rat … Kenn-" back to the code."""
        text = "\n".join(
            _read(
                (240, 100, "P101"),
                (276, 100, "Ist ärztlicher Rat erforderlich, Verpackung oder Kenn-"),
                (240, 113, "zeichnungsetikett bereithalten."),
            )
        )

        assert "Kennzeichnungsetikett" in normalise_pdf_text(text)

    def test_a_word_broken_in_a_hanging_text_runs_on_under_it(self) -> None:
        text = "\n".join(
            _read(
                (36, 100, "EUH Sätze"),
                (
                    226,
                    100,
                    ": EUH208 - Enthält 5-Chlor-2-methyl-2H-isothiazol-3-on und Kenn-",
                ),
                (234, 113, "zeichnung."),
            )
        )

        assert "Kennzeichnung." in normalise_pdf_text(text)


@pytest.mark.spec("SDB-46")
class TestUnreadableTextLayer:
    def test_the_files_order_decides_whether_ocr_reads_the_page(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A page of single glyphs read by position comes back as rows of
        letters and would pass for text; the file's order shows what it is."""
        glyphs = "\n".join("ABSCHNITT 1 Bezeichnung des Stoffs" * 3)
        monkeypatch.setattr(
            extraction,
            "_extract_with_pymupdf",
            lambda *a, **k: ([glyphs], ["A B S C H N I T T 1 Bezeichnung"]),
        )
        monkeypatch.setattr(
            extraction,
            "_extract_with_ocr",
            lambda *a: ("ABSCHNITT 1 Bezeichnung des Stoffs " * 30, 1),
        )
        pdf = tmp_path / "glyphs.pdf"
        with pymupdf.open() as doc:
            doc.new_page()
            doc.save(pdf)

        result = extract_pdf_text(pdf)

        assert result.extractor == "pymupdf+ocr"


def _box_end(x: float, y: float, text: str) -> float:
    """Where the box of *text* ends when it is drawn at *x*."""
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((x, y), text, fontsize=10)
        return max(word[2] for word in page.get_text("words"))


def _read_pieces(lead: Placed, pieces: tuple[str, ...]) -> list[str]:
    """The lines of a page on which *pieces* follow *lead* after a space, each
    beginning where the one before ends, and are drawn last to first."""
    x, y, text = lead[:3]
    start = _box_end(x, y, text) + 3
    placed = []
    for piece in pieces:
        placed.append((start, y, piece))
        start = _box_end(start, y, piece)
    return _read(lead, *reversed(placed))


@pytest.mark.spec("SDB-42")
class TestAWordDrawnInPieces:
    """ "24", ".0", "9", ".2025" for a date."""

    def test_pieces_that_meet_are_one_word(self) -> None:
        lines = _read_pieces((40, 100, "Stand:"), ("24", ".0", "9", ".2025"))
        assert lines == ["Stand: 24.09.2025"]

    def test_words_with_a_space_between_stay_apart(self) -> None:
        assert _read((40, 100, "Seite 1 von 12")) == ["Seite 1 von 12"]
        assert _read((40, 100, "Seite"), (70, 100, "1")) == ["Seite 1"]


# A form in two columns without colons: headings and labels at the left, what
# they say at the right. Written value column first, as such files are.
_FORM: tuple[Placed, ...] = (
    (230, 100, "Muster AG", 8),
    (230, 122, "Musterweg 22", 8),
    (230, 140, "12345 Musterstadt", 8),
    (230, 160, "+49 555 0142-0", 8),
    (230, 172, "+49 555 0142-9", 8),
    (230, 184, "info@muster.example", 8),
    (230, 204, "Tel +49 555 0142-112 Giftnotruf", 8),
    (53, 100, "1,3 Einzelheiten zum Lieferanten,", 8),
    (53, 111, "der das Sicherheitsdatenblatt", 8),
    (53, 120, "bereitstellt", 8),
    (53, 160, "Telefon", 8),
    (53, 172, "Fax", 8),
    (53, 184, "E-mail", 8),
    (53, 204, "1,4 Notrufnummer", 8),
)


@pytest.mark.spec("SDB-114")
class TestFormWithoutColons:
    def test_a_heading_of_section_one_takes_what_stands_beside_it(self) -> None:
        assert _read(*_FORM) == [
            "1,3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt",
            "Muster AG",
            "Musterweg 22",
            "12345 Musterstadt",
            "",
            "Telefon: +49 555 0142-0",
            "Fax: +49 555 0142-9",
            "E-mail: info@muster.example",
            "",
            "1,4 Notrufnummer",
            "Tel +49 555 0142-112 Giftnotruf",
        ]

    def test_the_supplier_reaches_the_parser(self, tmp_path: Path) -> None:
        """In the file's order the name stood before the heading, and the
        block under 1.3 had none."""
        pdf = tmp_path / "form.pdf"
        with pymupdf.open() as doc:
            page = doc.new_page(width=595, height=842)
            _write(
                page,
                (
                    (53, 40, "Sicherheitsdatenblatt"),
                    (
                        53,
                        70,
                        "ABSCHNITT 1: Bezeichnung des Stoffs und des Unternehmens",
                    ),
                    *_FORM,
                    (53, 240, "ABSCHNITT 2: Mögliche Gefahren"),
                ),
            )
            doc.save(pdf)

        supplier = SDSParser().parse(extract_pdf_text(pdf)).sheet.contact_info

        assert supplier.supplier_name == "Muster AG"
        assert supplier.supplier_address == "Musterweg 22, 12345 Musterstadt"
        assert supplier.supplier_phone == "+49 555 0142-0"
        assert supplier.supplier_email == "info@muster.example"

    def test_a_contact_label_alone_makes_no_form(self) -> None:
        """Without a heading of section 1 beside its content the rows stay a
        table, in the file's order."""
        rows = (
            (230, 153, "+49 555 0142-0"),
            (230, 166, "+49 555 0142-9"),
            (53, 153, "Telefon"),
            (53, 166, "Fax"),
        )

        assert _read(*rows) == ["+49 555 0142-0", "+49 555 0142-9", "Telefon", "Fax"]

    def test_the_other_column_of_a_page_is_no_content_of_a_heading(self) -> None:
        """A page set in two columns of running text: what stands right of the
        heading begins at the middle and belongs to another section."""
        rows = (
            (307, 100, "6.1 Personenbezogene Vorsichtsmaßnahmen"),
            (307, 113, "Für ausreichende Belüftung sorgen."),
            (35, 100, "1.3 Einzelheiten zum Lieferanten"),
            (35, 113, "Muster AG"),
        )

        assert _read(*rows) == [
            "6.1 Personenbezogene Vorsichtsmaßnahmen",
            "Für ausreichende Belüftung sorgen.",
            "1.3 Einzelheiten zum Lieferanten",
            "Muster AG",
        ]

    def test_a_label_further_down_is_no_line_of_the_heading(self) -> None:
        """The value runs on beside nothing; the next cell at the left is
        the next label."""
        rows = (
            (53, 100, "1.3 Einzelheiten zum", 8),
            (53, 111, "Lieferanten", 8),
            (230, 100, "Muster AG", 8),
            (230, 111, "Musterweg 22", 8),
            (230, 122, "12345 Musterstadt", 8),
            (53, 133, "Ansprechpartner", 8),
            (230, 133, "Labor", 8),
        )

        assert _read(*rows)[:4] == [
            "1.3 Einzelheiten zum Lieferanten",
            "Muster AG",
            "Musterweg 22",
            "12345 Musterstadt",
        ]

    def test_a_further_line_of_a_pair_with_a_colon_stays_its_line(self) -> None:
        """ "Email-Adresse" under "Notrufnummer/" is the label's second line,
        and what stands beside it the value's."""
        rows = (
            (53, 100, "1.3 Einzelheiten zum Lieferanten", 8),
            (230, 100, "Muster AG", 8),
            (53, 140, "Notrufnummer/", 8),
            (230, 140, ": +49 555 0142-112 notfall@muster-", 8),
            (53, 151, "Email-Adresse", 8),
            (240, 151, "labor.example", 8),
        )

        assert _read(*rows)[-2:] == [
            "Notrufnummer/ Email-Adresse: +49 555 0142-112 notfall@muster-",
            "labor.example",
        ]
