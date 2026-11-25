"""PDF text extraction helpers for Sicherheitsdatenblatt processing."""

from __future__ import annotations

import functools
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

from .layout import FLAGS, page_text
from .line_breaks import join_broken_words
from .messages import Message, shipped_catalog

# Reject PDFs larger than 50 MB to guard against decompression bombs.
MAX_PDF_SIZE_BYTES: int = 50 * 1024 * 1024

# Safety data sheets in the corpus are German.
OCR_LANGUAGE: str = "deu"

# OCR runs at roughly a second a page against milliseconds for a text layer, so
# it is capped even when the caller asked for the whole document. Everything the
# parser needs -- the label section, the classification, the supplier -- is in
# the first pages; a sheet whose section 2.2 is on page 9 is not a case the
# corpus has.
OCR_MAX_PAGES: int = 8

# A safety data sheet runs to thousands of characters. Below this, something went
# wrong on the way from the file to the text -- the reading did not fail outright,
# which is why it is a warning, but what came back cannot be the document.
#
# A caller recognises it by its code, "short-text".
SHORT_TEXT_THRESHOLD: int = 600

# Some PDFs place every glyph as its own text element, so the text layer comes
# back one character per line -- "ABSCHNITT" as "A\nB\nS\nC\nH\nN\nI\nT\nT".
# There is plenty of text and none of it can be searched: no keyword matches, no
# H-code, no section marker. Nothing repairs it either, because the word
# boundaries are not in the file; joining the lines gives "Erstelltam22.11.2010".
#
# Such a page is a picture of a document as far as reading goes, so it is read
# like one. Measured over 3,344 PDFs: 3,250 sit below 20%, a further
# 27 below 40%, and 11 are at 50% or above -- every one of those 11 already
# refused by the verifier, so nothing that works today is touched. Two of them
# are a genuine safety data sheet at 100%, which OCR then recognises;
# the other nine stay refused, as they should.
CHARACTER_PER_LINE_RATIO: float = 0.4

# Below this many lines the ratio says nothing: a two-line document is not
# evidence of anything.
CHARACTER_PER_LINE_MIN_LINES: int = 20

# 300 dpi is what the tables need; 150 loses the smaller table type.
OCR_DPI: int = 300

# A page that takes longer than this is not going to produce anything useful.
OCR_PAGE_TIMEOUT_SECONDS: int = 120


class ExtractionError(RuntimeError):
    """Raised when text cannot be extracted from an SDS PDF.

    ``message`` says why, as a code and its values; ``str()`` of the error is
    that message in English, for a traceback.
    """

    def __init__(self, message: Message) -> None:
        super().__init__(shipped_catalog("en").render(message))
        self.message = message


@dataclass(slots=True)
class ExtractionResult:
    """Details about a text extraction attempt."""

    text: str
    raw_text: str
    extractor: str
    pages_sampled: int
    warnings: list[Message]
    metadata: dict[str, object]


def extract_pdf_text(
    path: Path,
    *,
    max_pages: int | None = None,
    ocr: bool = True,
) -> ExtractionResult:
    """Extract text from *path* using PyMuPDF, in the order the pages print it.

    A text layer is read by the position of its words (layout.page_text,
    SDB-42 to SDB-45); a file without a readable one goes to OCR (SDB-46).

    All pages are read, as ``read_sheet`` reads them; *max_pages* bounds how
    many. With *ocr* off, a PDF without a text layer is not handed to
    text recognition: the call fails with ``no-text-layer`` instead.
    """

    if not path.exists():
        raise ExtractionError(Message("pdf-not-found"))

    file_size = path.stat().st_size
    if file_size > MAX_PDF_SIZE_BYTES:
        raise ExtractionError(
            Message(
                "pdf-too-large",
                {"size_bytes": file_size, "limit_bytes": MAX_PDF_SIZE_BYTES},
            )
        )

    warnings: list[Message] = []

    try:
        stored, pages = _extract_with_pymupdf(path, max_pages)
    except Exception as exc:
        # The library names the file in what it says; a reading does not
        # (BIB-2): "Failed to open file '/a/b.pdf' as type pdf." loses the
        # path with its quotes.
        named = r"\s*['\"]?" + re.escape(str(path)) + r"['\"]?"
        detail = " ".join(re.sub(named, "", str(exc)).split())
        raise ExtractionError(Message("pdf-unreadable", {"detail": detail})) from exc

    extractor = "pymupdf"
    pages_sampled = len(pages)
    # Whether the text layer can be read at all is judged on the file's own
    # order, the one the thresholds below were measured on: read by position,
    # a page of single glyphs comes back as rows of letters spaced apart and
    # no longer looks like what it is.
    linear = "\n".join(stored)
    zerlegt = _is_split_into_characters(linear)
    text = "\n".join(pages)
    if not linear.strip() or zerlegt:
        # No usable text layer. Either there is none at all -- a scan or a set
        # of exported images, 55 of those PDFs -- or there is one and it
        # is unreadable because every glyph stands on its own line. A person
        # can read both; the extractor can read neither, so the page is
        # rendered and read instead.
        if not ocr:
            raise ExtractionError(Message("no-text-layer", {"pages": pages_sampled}))
        text, pages_sampled = _extract_with_ocr(path, max_pages)
        # _clean_ocr_pages has already stripped the furniture from these, so
        # there is nothing left for the prompt path to strip a second time.
        pages = []
        extractor = "pymupdf+ocr"
        warnings.append(
            Message(
                "read-by-ocr-single-characters"
                if zerlegt
                else "read-by-ocr-no-text-layer"
            )
        )

    elif ocr and (read := _read_image_pages(path, stored, pages)):
        # A page that is a picture among pages with text (SDB-46): the first
        # page of a sheet, scanned, holds its date, its supplier and its
        # classification.
        text = "\n".join(pages)
        extractor = "pymupdf+ocr"
        warnings.append(Message("pages-read-by-ocr", {"pages": read}))

    if not text.strip():
        raise ExtractionError(
            Message("no-text", {"pages": pages_sampled, "extractor": extractor})
        )

    raw_text = text
    normalized_text = normalise_pdf_text(raw_text)

    char_count = len(normalized_text)
    if char_count < SHORT_TEXT_THRESHOLD:
        warnings.append(Message("short-text"))

    metadata: dict[str, object] = {
        "character_count": char_count,
        # Kept for strip_page_furniture, which cannot find a running header once
        # the pages are joined. Not persisted: see persistence.build_persistent_payload.
        "pages": pages,
    }
    if extractor == "pymupdf+ocr":
        # The program's version belongs to a text it read (SDB-116).
        metadata["tesseract"] = _tesseract_version()

    return ExtractionResult(
        text=normalized_text,
        raw_text=raw_text,
        extractor=extractor,
        pages_sampled=pages_sampled,
        warnings=warnings,
        metadata=metadata,
    )


def _extract_with_pymupdf(
    path: Path, max_pages: int | None
) -> tuple[list[str], list[str]]:
    """Read the text layer of each page: in the file's order, and as printed.

    The text is the printed one (SDB-42): layout.page_text puts the words where
    the page shows them, where the file's order reads a two-column form label
    by label and value by value. The file's order is returned beside it for
    the one question it still answers, whether the text layer is readable at
    all.

    Page by page, because joining them loses where one ends: strip_page_furniture
    needs the boundaries to tell a running header from a line that happens to
    occur twice.
    """
    stored: list[str] = []
    printed: list[str] = []
    with pymupdf.open(path) as doc:
        for number, page in enumerate(doc):
            if max_pages is not None and number >= max_pages:
                break
            # One extraction serves both: FLAGS are page.get_text()'s own.
            textpage = page.get_textpage(flags=FLAGS)
            stored.append(page.get_text(textpage=textpage) or "")
            printed.append(page_text(page, textpage))
    return stored, printed


def _is_split_into_characters(text: str) -> bool:
    """Whether the text layer came back one character per line.

    The signature is unambiguous where it occurs: the two genuine sheets in the
    corpus are at 100%, the nine other candidates at 50-53%, and the next
    document down is at 40%. Ordinary sheets sit under 20%. The threshold has
    room on both sides, so it does not need to be exact -- 0.3 or 0.6 would
    select the same eleven files.
    """
    lines = text.split("\n")
    if len(lines) < CHARACTER_PER_LINE_MIN_LINES:
        return False
    single = sum(1 for line in lines if len(line.strip()) == 1)
    return single / len(lines) >= CHARACTER_PER_LINE_RATIO


def _extract_with_ocr(path: Path, max_pages: int | None) -> tuple[str, int]:
    """Read a PDF that carries no text layer, by recognising the page image.

    The page is rendered here and handed to the ``tesseract`` binary directly,
    rather than through PyMuPDF's ``get_textpage_ocr``. The wrapper drops table
    rows: on one sheet measured it returned 49 lines against the binary's 79,
    and among the missing ones were

        Gefahrenhinweise für Gesundheitsgefahren
        H315 Verursacht Hautreizungen.
        H318 Verursacht schwere Augenschäden.

    -- the label's entire hazard statement table. A record built from that would
    have claimed a corrosive product carries no hazard statements at all, which
    is worse than having no record: it looks complete.

    German only: every sheet in the corpus is, and a language guess would be
    a knob nobody could set correctly. Where tesseract is missing the failure is
    reported as an extraction error like any other, so a machine without it
    behaves exactly as before rather than breaking.
    """
    limit = OCR_MAX_PAGES if max_pages is None else min(max_pages, OCR_MAX_PAGES)

    chunks: list[str] = []
    pages = 0
    with pymupdf.open(path) as doc:
        for number in range(min(len(doc), limit)):
            image = doc[number].get_pixmap(dpi=OCR_DPI).tobytes("png")
            chunks.append(_run_tesseract(image))
            pages += 1

    return _clean_ocr_pages(chunks), pages


def _read_image_pages(path: Path, stored: list[str], pages: list[str]) -> int:
    """Fill the pages that carry a picture and no text, by OCR; how many.

    *stored* says which pages have no text layer, *pages* gets their text. At
    most OCR_MAX_PAGES of them, as for a file without any text layer.
    """
    empty = [number for number, text in enumerate(stored) if not text.strip()]
    if not empty:
        return 0
    read = 0
    with pymupdf.open(path) as doc:
        for number in empty:
            if read >= OCR_MAX_PAGES or not doc[number].get_images():
                continue
            image = doc[number].get_pixmap(dpi=OCR_DPI).tobytes("png")
            pages[number] = _repair_codes(_run_tesseract(image))
            read += 1
    return read


# What the text recognition reads depends on the program: below this version
# the same picture gives another text (SDB-116).
TESSERACT_MINIMUM: int = 5
_TESSERACT_VERSION = re.compile(r"tesseract\s+v?(\d+(?:\.\d+)*)")


@functools.cache
def _tesseract_version() -> str:
    """The installed tesseract's version, checked once (SDB-116).

    Raises ExtractionError where the program is missing, older than the
    minimum, or without the German language data: each is a reason the file
    cannot be read. A failure is not remembered, so installing the program
    helps without a restart.
    """
    try:
        asked = subprocess.run(
            ["tesseract", "--version"],  # noqa: S607 -- tesseract from PATH (SDB-116)
            capture_output=True,
            timeout=30,
            check=False,
        )
        languages = subprocess.run(
            ["tesseract", "--list-langs"],  # noqa: S607 -- tesseract from PATH (SDB-116)
            capture_output=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ExtractionError(Message("ocr-unavailable")) from exc
    except subprocess.TimeoutExpired as exc:
        raise ExtractionError(Message("ocr-timeout")) from exc

    # Older builds print their version to stderr.
    said = (asked.stdout + asked.stderr).decode("utf-8", "replace")
    found = _TESSERACT_VERSION.search(said)
    if found is None:
        raise ExtractionError(Message("ocr-failed", {"detail": said.strip()[:200]}))
    version = found.group(1)
    if int(version.split(".")[0]) < TESSERACT_MINIMUM:
        raise ExtractionError(
            Message(
                "ocr-too-old", {"version": version, "minimum": str(TESSERACT_MINIMUM)}
            )
        )
    listed = (languages.stdout + languages.stderr).decode("utf-8", "replace")
    if OCR_LANGUAGE not in {line.strip() for line in listed.splitlines()}:
        raise ExtractionError(
            Message("ocr-language-missing", {"language": OCR_LANGUAGE})
        )
    return version


def _run_tesseract(image: bytes, *, words: bool = False) -> str:
    """Hand one rendered page to the binary and return what it read: the text,
    or with *words* a table of the words with their positions (tsv)."""
    _tesseract_version()
    output = ["tsv"] if words else []
    try:
        result = subprocess.run(  # noqa: S603 -- fixed arguments, no shell
            ["tesseract", "stdin", "stdout", "-l", OCR_LANGUAGE, "--psm", "3", *output],  # noqa: S607 -- tesseract from PATH (SDB-116)
            input=image,
            capture_output=True,
            timeout=OCR_PAGE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise ExtractionError(Message("ocr-unavailable")) from exc
    except subprocess.TimeoutExpired as exc:
        raise ExtractionError(Message("ocr-timeout")) from exc

    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()[:200]
        raise ExtractionError(Message("ocr-failed", {"detail": detail}))
    return result.stdout.decode("utf-8", "replace")


# O for zero, l or I for one, S for five, B for eight. Applied only inside a
# hazard code, never to running text: "H3l5" is certainly H315, but "Sol" is not
# "501" and repairing it everywhere would corrupt words.
_OCR_DIGITS = str.maketrans(
    {"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "B": "8"}
)
_CODE_SHAPES = re.compile(r"\b(GHS|EUH|H|P)([0-9OolISB]{2,3})\b")


def _repair_codes(text: str) -> str:
    """Undo the letter-for-digit confusions OCR makes inside hazard codes.

    A scanned ``GHS05`` comes back as ``GHSO5`` often enough to matter -- one of
    the sheets measured had exactly that, and the pictogram pattern then matched
    nothing. The same happens to H- and P-statements.
    """
    return _CODE_SHAPES.sub(
        lambda m: m.group(1) + m.group(2).translate(_OCR_DIGITS), text
    )


def strip_page_furniture(pages: list[str], *, keep_first: bool = False) -> str:
    """Join *pages*, dropping the boilerplate that repeats across them.

    Repetition is what identifies furniture, rather than position on the page: a
    line that appears on most pages is a header or a footer whatever its
    coordinates, and this needs no geometry. A document of one page has no
    repetition to go on and is left alone.

    Two callers, for two different reasons.

    **OCR**, where it is a correctness fix. In the file's order a text layer
    usually keeps page furniture apart; OCR does not, so the running header
    lands in the middle of section 2.2 -- and find_label_section, which ends the
    section at a heading, stops there. The layout reader puts the header where
    the page prints it too (SDB-42); measured over the 1,991 local sheets with a
    text layer, that cuts no label block short of its codes. One sheet measured lost its H-statements exactly this
    way: the label block was cut after 507 characters by a "SICHERHEITSDATENBLATT
    ... Seite 2/9" line, and the codes sat behind it.

    **The model prompt**, where it is economy. Measured over 297 sheets the
    repeated lines are 16.8% of the text at the median and over 20% for a
    quarter of them -- "Version", "DE / DE", "Datum der ersten Ausgabe:
    10.12.2019". The prompt asks for the supplier and the label statements and
    for nothing that lives in a running header, so none of it can be missed.

    What is dropped here is not lost: the version and both dates are read from
    exactly these lines, and the record keeps the unstripped text. This is a
    narrower input for one caller, not a smaller document.

    *keep_first* leaves one copy of each repeated line standing. A line can be
    furniture and content at once -- one sheet in the corpus prints "Tannhof
    Bergfeld GmbH" as its running header and as the supplier in section 1, so
    dropping every occurrence dropped the answer along with the noise. Keeping
    the first still removes the other three of four.

    Both callers pass it now. The OCR path used not to, on the reasoning that
    the repetition is itself the damage: a header standing inside section 2.2
    ends the section there. That reasoning holds for the second occurrence
    onwards, which is still dropped. It does not hold for the first, which sits
    at the top of page one ahead of section 1 -- and dropping that one took the
    revision date with it, because for OCR this function's output is the record's
    text and no unstripped copy survives behind it. Measured over all 36 OCR'd
    sheets in the corpus: two gain a date, none lose a hazard statement, a
    signal word or a label section.
    """
    if len(pages) < 2:
        return "\n".join(pages)

    counts: dict[str, int] = {}
    for page in pages:
        for line in {ln.strip() for ln in page.split("\n") if len(ln.strip()) > 3}:
            counts[line] = counts.get(line, 0) + 1

    threshold = max(2, (len(pages) + 1) // 2)
    furniture = {line for line, n in counts.items() if n >= threshold}

    seen: set[str] = set()

    def _keep(line: str) -> bool:
        stripped = line.strip()
        if stripped not in furniture:
            return True
        if not keep_first or stripped in seen:
            return False
        seen.add(stripped)
        return True

    kept = ["\n".join(ln for ln in page.split("\n") if _keep(ln)) for page in pages]
    return "\n".join(kept)


def _clean_ocr_pages(pages: list[str]) -> str:
    """Strip furniture from OCR'd pages and repair the codes OCR mangles.

    ``keep_first`` matters here for a reason the text-layer path never has: what
    this function returns *is* the record's text. There is no unstripped copy
    behind it, so a line dropped here is gone for good -- and the running header
    is where the revision date lives. Two sheets went out
    undated because of it, one of them stating "überarbeitet am: 16.07.2019"
    plainly on its first page.
    """
    return _repair_codes(strip_page_furniture(pages, keep_first=True))


_CODE_BEFORE_LINE_BREAK = re.compile(r"\b((?:EUH|H|P)\d{3})-\n")


def normalise_pdf_text(text: str) -> str:
    """Normalise raw PDF text while preserving paragraph structure."""

    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\u00ad", "", text)  # remove soft hyphen characters
    # A hyphen after a hazard code separates the code from its wording; it is
    # not a word broken across lines. "H319-" at the end of one line and
    # "Verursacht schwere Augenreizung." on the next became "H319Verursacht"
    # under the rule below, and a reader that ends a code at a word boundary
    # no longer saw H319. The line is joined, the hyphen kept.
    text = _CODE_BEFORE_LINE_BREAK.sub(r"\1-", text)
    # A word broken at the line end loses its hyphen only between two
    # lower-case letters (SDB-32): "5-Chlor-2-methyl-2H-" /
    # "isothiazol-3-on" became "2Hisothiazol" and "2-" / "Methyl" "2Methyl"
    # , "tert-butyl-" / "4-hydroxyphenyl" "butyl4-hydroxyphenyl".
    text = join_broken_words(text)

    normalised_lines: list[str] = []
    blank_run = 0
    for raw_line in text.split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            blank_run += 1
            if blank_run <= 2:
                normalised_lines.append("")
            continue

        blank_run = 0
        cleaned = re.sub(r"\s+", " ", stripped)
        normalised_lines.append(cleaned)

    normalised_text = "\n".join(normalised_lines)
    normalised_text = re.sub(r"\n{3,}", "\n\n", normalised_text)
    return normalised_text.strip()


def ocr_lines(page: pymupdf.Page) -> list[tuple[float, float, str]]:
    """The lines text recognition reads on *page*, a picture without a text
    layer: the top and bottom of each in points and its text, from the top
    down (SDB-204).

    Raises ExtractionError where tesseract is missing or fails, as for the text.
    """
    table = _run_tesseract(page.get_pixmap(dpi=OCR_DPI).tobytes("png"), words=True)
    scale = 72 / OCR_DPI
    rows: dict[tuple[str, str, str], list[Any]] = {}
    for record in table.splitlines()[1:]:
        fields = record.split("\t")
        if len(fields) < 12 or not fields[11].strip():
            continue
        top, height = int(fields[7]), int(fields[9])
        row = rows.setdefault(
            (fields[2], fields[3], fields[4]), [top, top + height, []]
        )
        row[0], row[1] = min(row[0], top), max(row[1], top + height)
        row[2].append(fields[11])
    return sorted((t * scale, b * scale, " ".join(w)) for t, b, w in rows.values())
