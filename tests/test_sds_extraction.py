from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pymupdf
import pytest

from sdb_reader import extraction
from sdb_reader.extraction import (
    ExtractionError,
    extract_pdf_text,
    normalise_pdf_text,
)
from sdb_reader.messages import Message


def _write_pdf(path: Path, text: str) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


def _write_pages(path: Path, pages: list[str]) -> Path:
    doc = pymupdf.open()
    for content in pages:
        page = doc.new_page()
        page.insert_text((72, 72), content)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def sds_sample(tmp_path: Path) -> Path:
    return _write_pdf(
        tmp_path / "0000000000000_00000_SD_6.pdf",
        "SICHERHEITSDATENBLATT\nAbschnitt 1\nProduktname Beispielreiniger",
    )


def test_extract_pdf_text_uses_pymupdf_by_default(sds_sample: Path) -> None:
    result = extract_pdf_text(sds_sample, max_pages=1)

    assert result.extractor == "pymupdf"
    assert "SICHERHEITSDATENBLATT" in result.text.upper()
    assert result.pages_sampled == 1
    assert result.metadata["character_count"] > 0
    assert isinstance(result.warnings, list)
    assert result.text


def test_extract_pdf_text_raises_when_pymupdf_fails(
    monkeypatch: pytest.MonkeyPatch,
    sds_sample: Path,
) -> None:
    from sdb_reader import extraction

    def raise_error(
        path: Path, max_pages: int | None
    ) -> tuple[list[str], list[str]]:  # pragma: no cover - patched in tests
        raise RuntimeError("PyMuPDF extraction failed")

    monkeypatch.setattr(extraction, "_extract_with_pymupdf", raise_error)

    with pytest.raises(ExtractionError) as failure:
        extract_pdf_text(sds_sample, max_pages=1)
    assert failure.value.message == Message(
        "pdf-unreadable", {"detail": "PyMuPDF extraction failed"}
    )


def test_extract_pdf_text_raises_when_no_text_extracted(
    monkeypatch: pytest.MonkeyPatch,
    sds_sample: Path,
) -> None:
    """With the OCR fallback declined, an empty text layer is still a failure."""
    from sdb_reader import extraction

    monkeypatch.setattr(
        extraction, "_extract_with_pymupdf", lambda path, max_pages: ([], [])
    )

    with pytest.raises(ExtractionError) as failure:
        extract_pdf_text(sds_sample, max_pages=1, ocr=False)
    assert failure.value.message == Message("no-text-layer", {"pages": 0})


def test_normalise_pdf_text_handles_hyphenated_line_breaks() -> None:
    raw = "Gefahrenbe-\nzeichnung"

    normalised = normalise_pdf_text(raw)

    assert normalised == "Gefahrenbezeichnung"


@pytest.mark.spec("SDB-32")
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Gefahrenbe-\nzeichnung", "Gefahrenbezeichnung"),
        # A name broken at one of its own hyphens keeps it
        (
            "5-Chlor-2-methyl-2H-\nisothiazol-3-on",
            "5-Chlor-2-methyl-2H-isothiazol-3-on",
        ),
        ("2-\nMethyl-2H-isothiazol-3-on", "2-Methyl-2H-isothiazol-3-on"),
        ("1,2-Benzisothiazol-3(2H)-\non", "1,2-Benzisothiazol-3(2H)-on"),
        ("UN-\nVersandbezeichnung", "UN-Versandbezeichnung"),
    ],
)
def test_a_names_own_hyphen_stays_at_the_line_end(raw: str, expected: str) -> None:
    assert normalise_pdf_text(raw) == expected


@pytest.mark.spec("SDB-32")
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Gefahrenbe-\nzeichnung", "Gefahrenbezeichnung"),
        # A digit follows the hyphen
        ("5-tert-butyl-\n4-hydroxyphenyl", "5-tert-butyl-4-hydroxyphenyl"),
        ("isothiazol-\n3-on", "isothiazol-3-on"),
        ("Erste-Hilfe-\nMaßnahmen", "Erste-Hilfe-Maßnahmen"),
        (
            "benzotriazol-2-yl)-5-\n(1,1-dimethylethyl)",
            "benzotriazol-2-yl)-5-(1,1-dimethylethyl)",
        ),
        # the hyphen stands for the shared part of the word
        ("Haut-\nund Augenschutz", "Haut-\nund Augenschutz"),
        ("PBT-\noder vPvB-Stoff", "PBT-\noder vPvB-Stoff"),
    ],
)
def test_a_hyphen_at_the_line_end_goes_only_between_two_lower_case_letters(
    raw: str, expected: str
) -> None:
    assert normalise_pdf_text(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The code at the end of one line, its wording on the next
        (
            "Exposition. H319-\nVerursacht schwere Augenreizung.",
            "Exposition. H319-Verursacht schwere Augenreizung.",
        ),
        (
            "P233-\nBehälter dicht verschlossen halten.",
            "P233-Behälter dicht verschlossen halten.",
        ),
        ("EUH208-\nEnthält Isothiazolinon.", "EUH208-Enthält Isothiazolinon."),
    ],
)
def test_a_hyphen_after_a_hazard_code_is_kept(raw: str, expected: str) -> None:
    """It separates the code from its wording; it does not break a word."""
    assert normalise_pdf_text(raw) == expected


class TestOcrFallback:
    """A PDF with no text layer is rendered and read."""

    def test_a_missing_tesseract_fails_like_any_extraction_error(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """A machine without it behaves exactly as before rather than breaking."""
        monkeypatch.setattr(
            extraction, "_extract_with_pymupdf", lambda *a, **k: ([""] * 3, [""] * 3)
        )

        def no_binary(*args: Any, **kwargs: Any) -> Any:
            raise FileNotFoundError("tesseract")

        monkeypatch.setattr(extraction.subprocess, "run", no_binary)
        pdf = _write_pdf(tmp_path / "scan.pdf", "irrelevant")

        with pytest.raises(extraction.ExtractionError) as failure:
            extraction.extract_pdf_text(pdf)
        assert failure.value.message == Message("ocr-unavailable")
        # In a traceback the reason reads in English.
        assert "tesseract is not installed" in str(failure.value)

    def test_ocr_is_skipped_when_the_caller_declines_it(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr(
            extraction, "_extract_with_pymupdf", lambda *a, **k: ([""] * 3, [""] * 3)
        )
        called: list[object] = []
        monkeypatch.setattr(
            extraction, "_extract_with_ocr", lambda *a: called.append(a) or ("x", 1)
        )
        pdf = _write_pdf(tmp_path / "scan.pdf", "irrelevant")

        with pytest.raises(extraction.ExtractionError) as failure:
            extraction.extract_pdf_text(pdf, ocr=False)
        assert failure.value.message == Message("no-text-layer", {"pages": 3})
        assert called == []

    def test_the_record_says_the_document_was_read_by_ocr(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr(
            extraction, "_extract_with_pymupdf", lambda *a, **k: ([""] * 2, [""] * 2)
        )
        monkeypatch.setattr(
            extraction,
            "_extract_with_ocr",
            lambda *a: ("ABSCHNITT 1 Sicherheitsdatenblatt " * 30, 2),
        )
        pdf = _write_pdf(tmp_path / "scan.pdf", "irrelevant")

        result = extraction.extract_pdf_text(pdf)

        assert result.extractor == "pymupdf+ocr"
        assert Message("read-by-ocr-no-text-layer") in result.warnings


class TestOcrRepairs:
    """Two artefacts of reading a page image rather than a text layer."""

    def test_letters_are_turned_back_into_digits_inside_codes(self) -> None:
        """A scanned GHS05 comes back as GHSO5 often enough to matter, and the
        pictogram pattern then matches nothing."""
        assert extraction._repair_codes("Piktogramm GHSO5 und H3l5") == (
            "Piktogramm GHS05 und H315"
        )

    def test_running_text_is_left_alone(self) -> None:
        """ "Sol" is not "501"; repairing everywhere would corrupt words."""
        text = "Die Lösung ist stabil. Bei Kontakt Sol und IBC beachten."
        assert extraction._repair_codes(text) == text

    def test_the_header_repeated_on_every_page_is_dropped(self) -> None:
        """OCR puts page furniture in the reading order, where it cuts section
        2.2 short -- one sheet lost its H-statements exactly that way."""
        pages = [
            "SICHERHEITSDATENBLATT\nSeite 1\n2.2 Kennzeichnungselemente",
            "SICHERHEITSDATENBLATT\nSeite 2\nH315 Verursacht Hautreizungen.",
            "SICHERHEITSDATENBLATT\nSeite 3\nAbschnitt 3",
        ]

        joined = extraction._clean_ocr_pages(pages)

        # The copy that would cut section 2.2 short is the one on page 2, and
        # it is gone. The copy on page 1 stands ahead of the 2.2 heading, so it
        # cuts nothing -- and it is the line the revision date is printed on.
        assert joined.count("SICHERHEITSDATENBLATT") == 1
        assert joined.index("SICHERHEITSDATENBLATT") < joined.index(
            "2.2 Kennzeichnungselemente"
        )
        assert "H315 Verursacht Hautreizungen." in joined
        assert "Seite 1" in joined  # varies per page, so not furniture

    def test_a_single_page_has_no_repetition_to_go_on(self) -> None:
        pages = ["SICHERHEITSDATENBLATT\nH315 Verursacht Hautreizungen."]

        assert "SICHERHEITSDATENBLATT" in extraction._clean_ocr_pages(pages)

    def test_keep_first_leaves_one_copy_standing(self) -> None:
        """A line can be furniture and content at once.

        One sheet in the corpus prints "Tannhof Bergfeld GmbH" as its running
        header and as the supplier in section 1. Dropping every occurrence
        dropped the answer with the noise; keeping the first still removes
        three of four.
        """
        pages = [
            "Tannhof Bergfeld GmbH\n1.3 Lieferant\nTannhof Bergfeld GmbH",
            "Tannhof Bergfeld GmbH\n2.2 Kennzeichnungselemente",
            "Tannhof Bergfeld GmbH\nAbschnitt 3",
            "Tannhof Bergfeld GmbH\nAbschnitt 4",
        ]

        kept = extraction.strip_page_furniture(pages, keep_first=True)

        assert kept.count("Tannhof Bergfeld GmbH") == 1
        assert "2.2 Kennzeichnungselemente" in kept

    def test_ocr_removes_every_copy_but_the_first(self) -> None:
        """The repetition is the damage; the first occurrence is not.

        A header standing inside section 2.2 ends the section at that line, so
        every repeat has to go. The first one sits at the top of page one, ahead
        of section 1, and ends nothing -- while for OCR this output *is* the
        record's text, with no unstripped copy behind it. Dropping that first
        line took the revision date with it: two sheets in the corpus
        went out undated for exactly this reason.
        """
        pages = [
            "SICHERHEITSDATENBLATT\nüberarbeitet am: 16.07.2019\n2.2 Kennzeichnungselemente",
            "SICHERHEITSDATENBLATT\nüberarbeitet am: 16.07.2019\nH315 Verursacht Hautreizungen.",
        ]

        cleaned = extraction._clean_ocr_pages(pages)

        assert cleaned.count("SICHERHEITSDATENBLATT") == 1
        assert cleaned.count("überarbeitet am: 16.07.2019") == 1
        assert "H315 Verursacht Hautreizungen." in cleaned

    def test_a_repeat_inside_the_label_section_is_still_dropped(self) -> None:
        """The reason the OCR path strips at all, unchanged."""
        pages = [
            "ABSCHNITT 1\nRunning header",
            "Running header\n2.2 Kennzeichnungselemente\nSignalwort Gefahr",
            "Running header\nABSCHNITT 3",
        ]

        cleaned = extraction._clean_ocr_pages(pages)

        assert cleaned.count("Running header") == 1
        assert cleaned.index("Running header") < cleaned.index(
            "2.2 Kennzeichnungselemente"
        )

    def test_the_record_keeps_the_text_the_prompt_does_not_get(
        self, tmp_path: Path
    ) -> None:
        """Stripping is a narrower input for one caller, not a smaller document.

        The version and both dates are read from exactly these lines, so the
        extraction result has to carry them even though the model never sees
        them.
        """
        pdf = _write_pages(
            tmp_path / "sheet.pdf",
            [
                "Version 3.1\n1.3 Lieferant\nACME GmbH",
                "Version 3.1\n2.2 Kennzeichnungselemente\nH315",
            ],
        )

        result = extraction.extract_pdf_text(pdf, max_pages=4)

        assert "Version 3.1" in result.text
        pages = result.metadata["pages"]
        assert isinstance(pages, list)
        assert "Version 3.1" not in extraction.strip_page_furniture(
            [str(page) for page in pages], keep_first=True
        ).replace("Version 3.1", "", 1)


class TestATextLayerSplitIntoCharacters:
    """Some PDFs place every glyph as its own element.

    The text layer then comes back one character per line -- "ABSCHNITT" as
    "A\nB\nS\nC\nH\nN\nI\nT\nT". There is plenty of text and none of it can be
    searched, and nothing repairs it: the word boundaries are not in the file,
    so joining the lines gives "Erstelltam22.11.2010". For reading purposes the
    page is a picture of a document, so it is read like one.
    """

    @staticmethod
    def _split(zeilen: int) -> str:
        return "\n".join("x" for _ in range(zeilen))

    def test_the_signature_is_recognised(self) -> None:
        assert extraction._is_split_into_characters(self._split(40))

    def test_an_ordinary_text_layer_is_not(self) -> None:
        """Real sheets sit under 20%; the threshold is 40%."""
        text = "\n".join(
            f"Abschnitt {i}: eine Zeile mit richtigen Woertern" for i in range(40)
        )
        assert not extraction._is_split_into_characters(text)

    def test_a_short_document_is_never_judged(self) -> None:
        """Two single-character lines are not evidence of anything."""
        assert not extraction._is_split_into_characters("A\nB\nC")

    def test_a_mixture_below_the_threshold_is_left_alone(self) -> None:
        zeilen = ["x"] * 15 + ["eine ganz normale Textzeile"] * 25
        assert not extraction._is_split_into_characters("\n".join(zeilen))

    def test_such_a_page_is_read_by_ocr(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole point: the trigger is no longer "no text at all"."""
        pdf = _write_pdf(tmp_path / "zerlegt.pdf", "\n".join("x" for _ in range(60)))
        gerufen: dict[str, Any] = {}

        def fake_ocr(path: Path, max_pages: Any) -> tuple[str, int]:
            gerufen["path"] = path
            return "SICHERHEITSDATENBLATT Abschnitt 1 Bezeichnung", 1

        monkeypatch.setattr(extraction, "_extract_with_ocr", fake_ocr)
        res = extract_pdf_text(pdf, max_pages=8)

        assert gerufen["path"] == pdf, "OCR must have been asked"
        assert res.extractor == "pymupdf+ocr"
        assert "SICHERHEITSDATENBLATT" in res.text
        assert Message("read-by-ocr-single-characters") in res.warnings

    def test_a_readable_page_is_not_sent_to_ocr(
        self, sds_sample: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_ocr(path: Path, max_pages: Any) -> tuple[str, int]:
            raise AssertionError("a readable text layer must not cost an OCR pass")

        monkeypatch.setattr(extraction, "_extract_with_ocr", fail_ocr)
        res = extract_pdf_text(sds_sample, max_pages=8)
        assert res.extractor == "pymupdf"


def _write_scan_then_text(path: Path, *, picture: bool) -> Path:
    """A first page without text, with or without a picture, then a text page."""
    doc = pymupdf.open()
    first = doc.new_page()
    if picture:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40))
        pixmap.clear_with(200)
        first.insert_image(pymupdf.Rect(72, 72, 300, 300), pixmap=pixmap)
    doc.new_page().insert_text(
        (72, 72), "ABSCHNITT 4: Erste-Hilfe-Maßnahmen " + "Arzt rufen. " * 20
    )
    doc.save(path)
    doc.close()
    return path


@pytest.mark.spec("SDB-46")
class TestAPageThatIsAPictureAmongPagesWithText:
    """Page 1 is a scan, pages 2 to 5 are text."""

    SCANNED = "Ausgabedatum: 06.10.2017 Überarbeitungsdatum: 06.10.2017"

    def test_the_page_is_read_by_ocr_in_its_place(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pdf = _write_scan_then_text(tmp_path / "sheet.pdf", picture=True)
        monkeypatch.setattr(extraction, "_run_tesseract", lambda *a: self.SCANNED)

        result = extract_pdf_text(pdf)

        assert result.text.index("Überarbeitungsdatum") < result.text.index(
            "ABSCHNITT 4"
        )
        assert result.extractor == "pymupdf+ocr"
        assert Message("pages-read-by-ocr", {"pages": 1}) in result.warnings

    def test_an_empty_page_without_a_picture_is_left_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pdf = _write_scan_then_text(tmp_path / "sheet.pdf", picture=False)

        def fail(*args: Any) -> str:
            raise AssertionError("a blank page costs no OCR pass")

        monkeypatch.setattr(extraction, "_run_tesseract", fail)

        assert extract_pdf_text(pdf).extractor == "pymupdf"

    def test_a_caller_that_declines_ocr_gets_the_text_layer_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pdf = _write_scan_then_text(tmp_path / "sheet.pdf", picture=True)
        monkeypatch.setattr(extraction, "_run_tesseract", lambda *a: self.SCANNED)

        result = extract_pdf_text(pdf, ocr=False)

        assert "Überarbeitungsdatum" not in result.text
        assert result.extractor == "pymupdf"


class _Asked:
    """What ``tesseract --version`` and ``--list-langs`` print."""

    def __init__(self, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.stdout, self.stderr, self.returncode = stdout, stderr, 0


@pytest.mark.real_tesseract
@pytest.mark.spec("SDB-116")
class TestTheInstalledTesseract:
    @pytest.fixture(autouse=True)
    def _forget(self) -> Iterator[None]:
        extraction._tesseract_version.cache_clear()
        yield
        extraction._tesseract_version.cache_clear()

    @staticmethod
    def _installed(
        monkeypatch: pytest.MonkeyPatch, version: _Asked, languages: bytes
    ) -> None:
        def run(command: list[str], **_: object) -> _Asked:
            return version if "--version" in command else _Asked(stdout=languages)

        monkeypatch.setattr(extraction.subprocess, "run", run)

    def test_version_five_with_german_data_is_taken(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._installed(
            monkeypatch,
            _Asked(stdout=b"tesseract 5.5.4\n leptonica-1.87.0\n"),
            b'List of available languages in "/usr/share/tessdata/" (3):\ndeu\neng\nosd\n',
        )

        assert extraction._tesseract_version() == "5.5.4"

    def test_an_older_program_is_refused_with_its_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Version 4 printed its version to stderr."""
        self._installed(monkeypatch, _Asked(stderr=b"tesseract 4.1.1\n"), b"deu\n")

        with pytest.raises(ExtractionError) as refused:
            extraction._tesseract_version()

        assert refused.value.message == Message(
            "ocr-too-old", {"version": "4.1.1", "minimum": "5"}
        )

    def test_missing_german_data_is_named(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._installed(monkeypatch, _Asked(stdout=b"tesseract 5.3.0\n"), b"eng\nosd\n")

        with pytest.raises(ExtractionError) as refused:
            extraction._tesseract_version()

        assert refused.value.message == Message(
            "ocr-language-missing", {"language": "deu"}
        )

    def test_a_missing_program_is_said_as_before(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def run(*_: object, **__: object) -> _Asked:
            raise FileNotFoundError("tesseract")

        monkeypatch.setattr(extraction.subprocess, "run", run)

        with pytest.raises(ExtractionError) as refused:
            extraction._tesseract_version()

        assert refused.value.message == Message("ocr-unavailable")


@pytest.mark.spec("BIB-2")
def test_a_file_that_is_no_pdf_is_refused_without_its_path(tmp_path: Path) -> None:
    """The PDF library names the file in what it says; the reason does not,
    and reads as a sentence without it."""
    notes = tmp_path / "notes.pdf"
    notes.write_text("just a text file", encoding="utf-8")

    with pytest.raises(ExtractionError) as refused:
        extract_pdf_text(notes)

    assert refused.value.message.code == "pdf-unreadable"
    detail = refused.value.message.params["detail"]
    assert str(tmp_path) not in detail
    assert "notes.pdf" not in detail
    assert "the file" not in detail
    assert "  " not in detail


@pytest.mark.spec("BIB-3")
def test_all_pages_are_read_unless_a_number_is_given(tmp_path: Path) -> None:
    """As read_sheet reads them: a text kept from the default call is whole."""
    pdf = tmp_path / "long.pdf"
    with pymupdf.open() as doc:
        for number in range(1, 9):
            doc.new_page().insert_text((72, 72), f"Seite {number} von acht Seiten Text")
        doc.save(pdf)

    assert extract_pdf_text(pdf).pages_sampled == 8
    assert extract_pdf_text(pdf, max_pages=3).pages_sampled == 3
