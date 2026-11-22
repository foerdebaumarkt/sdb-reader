"""Reading one safety data sheet: its text, whether it is one, and what it says.

The entry point of the library. A file goes in; what comes back is the text
read from it, the verdict whether it is a safety data sheet and, if it is, the
parsed sheet -- or the errors that stopped the reading. Storing the result,
and knowing which file it belongs to, is the caller's (BIB-2).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from .extraction import ExtractionError, ExtractionResult, extract_pdf_text
from .label_blocks import SMALL_PACKAGE_HEADING
from .label_images import LabelImages, LabelImagesStatus, read_label_images
from .messages import Message
from .parser import ParsedSheet, SDSParser
from .schema import FurtherLabel, LabelKind, SafetyDataSheet
from .verification import DocumentKind, SDSVerifier, Verification

LINE_TOO_LONG = "line-too-long"
# The label was not looked at as a picture, and why (SDB-179).
LABEL_IMAGES_NOT_READ = "label-images-not-read"
# Red diamonds in the label that no reference matched (SDB-179).
PICTOGRAMS_NOT_RECOGNISED = "pictograms-not-recognised"
# Why the pictograms of a label's drawing are not in a sheet's reading, beside
# the LabelImagesStatus values: a file's labels on the pages and its sheets do
# not pair up.
LABELS_NOT_PAIRED = "labels-not-paired"
# The longest line a sheet prints, with room: the longest of the measured
# collection has 837 characters (SDB-167).
MAX_LINE_CHARACTERS = 2_000


@dataclass(slots=True)
class SheetReading:
    """What reading one file found."""

    verification: Verification
    # None when the file could not be read at all; *errors* says why.
    extraction: ExtractionResult | None = None
    # None unless the file is a German safety data sheet.
    parser_result: ParsedSheet | None = None
    # What the label shows as pictures, where the PDF was looked at (SDB-179);
    # a caller that keeps the text keeps this beside it.
    label_images: LabelImages | None = None
    warnings: list[Message] = field(default_factory=list)
    errors: list[Message] = field(default_factory=list)


def read_sheet(path: Path, *, max_pages: int | None = None) -> SheetReading:
    """Read the PDF at *path*, judge what kind of document it is, and parse a sheet.

    The file is judged by its content alone; its name says nothing. *max_pages*
    bounds how many pages are read, by default all. A file that cannot be read
    gives a reading with ``extraction`` None and the reason in ``errors``.
    """
    # Read the document once: the verdict and the parser work on the same text.
    try:
        extraction = extract_pdf_text(path, max_pages=max_pages)
    except ExtractionError as exc:
        errors = [exc.message]
        return SheetReading(
            verification=SDSVerifier().refuse_unreadable(errors),
            # No text, so nothing was judged: the file is not known to be
            # anything.
            warnings=[Message("unreadable")],
            errors=errors,
        )
    return _read(extraction, lambda: read_label_images(path, max_pages=max_pages))


def read_extraction(
    extraction: ExtractionResult, label_images: LabelImages | None = None
) -> SheetReading:
    """Judge and parse a text that was read from a PDF before (BIB-3).

    Gives what ``read_sheet`` gives for the file the text came from, when
    *label_images* is what ``read_label_images`` found in that file. Reading a
    PDF takes nearly all the time of a reading; a caller that keeps the text
    (``extraction_to_dict``) and the pictograms (``label_images_to_dict``)
    reads a sheet again in milliseconds. Without *label_images* the reading
    has only the pictograms the text names, and ``drawing_read`` says that
    the label was not looked at as drawn.

    >>> from sdb_reader import extraction_from_dict
    >>> text = (
    ...     "Sicherheitsdatenblatt\\n"
    ...     "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs\\n"
    ...     "Produktname: Musterfarbe\\n"
    ...     "ABSCHNITT 2: Mögliche Gefahren\\n"
    ...     "Verordnung (EG) Nr. 1907/2006\\n"
    ...     "Signalwort: Achtung\\n"
    ...     "H315: Verursacht Hautreizungen.\\n"
    ... )
    >>> reading = read_extraction(
    ...     extraction_from_dict(
    ...         {"text": text, "extractor": "pymupdf", "pages_sampled": 1, "warnings": []}
    ...     )
    ... )
    >>> reading.verification.kind.value
    'safety-data-sheet'
    >>> label = reading.parser_result.sheet.hazard_statements
    >>> label.hazard_codes, label.signal_word
    (['H315'], 'Achtung')
    """
    return _read(extraction, lambda: label_images)


def _read(
    extraction: ExtractionResult, label_images: Callable[[], LabelImages | None]
) -> SheetReading:
    """The reading of *extraction*; the label's drawing is looked at only for
    a German safety data sheet."""
    checked, too_long = within_line_limit(extraction)
    verification = SDSVerifier().verify(checked)
    if verification.kind is not DocumentKind.SAFETY_DATA_SHEET:
        return SheetReading(
            verification=verification,
            extraction=extraction,
            warnings=[Message("not-a-sheet"), *too_long],
        )
    parsed = SDSParser().parse(checked)
    parsed.warnings[:0] = too_long
    images = label_images()
    with_label_images(parsed, images)
    return SheetReading(
        verification=verification,
        extraction=extraction,
        parser_result=parsed,
        label_images=images,
    )


def with_label_images(parsed: ParsedSheet, images: LabelImages | None) -> None:
    """Add to *parsed* the pictograms its labels show as pictures (SDB-179).

    The file's reading gets those of every label on the pages; each sheet of a
    file that holds several gets those of its own label, where the labels on
    the pages are as many as the sheets, else a warning. Where the label could
    not be looked at, a warning says why. Without *images* nothing changes.
    """
    if images is None:
        return
    if images.status is not LabelImagesStatus.READ:
        reason = images.status.value
        for warnings in (parsed.warnings, *(part.warnings for part in parsed.parts)):
            warnings.append(Message(LABEL_IMAGES_NOT_READ, {"reason": reason}))
        return
    _add_pictograms(
        parsed.sheet, set().union(*images.labels), read=not any(images.unrecognised)
    )
    _add_small_packages(
        parsed.sheet,
        [codes for label in images.small_packages for codes in label],
        [count for label in images.small_packages_unrecognised for count in label],
    )
    if missed := sum(images.unrecognised):
        parsed.warnings.append(Message(PICTOGRAMS_NOT_RECOGNISED, {"count": missed}))
    if not parsed.parts:
        return
    if len(images.labels) != len(parsed.parts):
        for part in parsed.parts:
            part.warnings.append(
                Message(LABEL_IMAGES_NOT_READ, {"reason": LABELS_NOT_PAIRED})
            )
        return
    for part, codes, missed, small, small_missed in zip(
        parsed.parts,
        images.labels,
        images.unrecognised,
        images.small_packages,
        images.small_packages_unrecognised,
        strict=True,
    ):
        _add_pictograms(part.sheet, set(codes), read=not missed)
        _add_small_packages(part.sheet, small, small_missed)
        if missed:
            part.warnings.append(Message(PICTOGRAMS_NOT_RECOGNISED, {"count": missed}))


def _add_pictograms(sheet: SafetyDataSheet, codes: set[str], *, read: bool) -> None:
    label = sheet.hazard_statements
    label.pictograms = sorted(set(label.pictograms) | codes)
    label.drawing_read = read


def _drawn(further: FurtherLabel) -> bool:
    """Whether *further* is a small package's label under a heading, which the
    drawing finds too (SDB-188), and not a sentence of SDB-189."""
    return further.kind is LabelKind.SMALL_PACKAGE and bool(
        SMALL_PACKAGE_HEADING.match(further.heading)
    )


def _add_small_packages(
    sheet: SafetyDataSheet, codes: list[list[str]], unrecognised: list[int]
) -> None:
    """Give each small package's label of *sheet* the pictograms of its
    drawing (SDB-188), where the drawing found as many as the text; else
    none is read as drawn."""
    drawn = [f for f in sheet.hazard_statements.further_labels if _drawn(f)]
    if len(drawn) != len(codes):
        return
    for further, found, missed in zip(drawn, codes, unrecognised, strict=True):
        label = further.label
        label.pictograms = sorted(set(label.pictograms) | set(found))
        label.drawing_read = not missed


def within_line_limit(
    extraction: ExtractionResult,
) -> tuple[ExtractionResult, list[Message]]:
    """*extraction* with each line longer than a sheet prints left empty (SDB-167).

    The text a sheet prints has short lines; a line of thousands of characters
    is something built, and some steps of the reading take long on it. The
    extraction itself stays as it was read, so a kept text stays valid.
    """
    lines = extraction.text.split("\n")
    lengths = [len(line) for line in lines if len(line) > MAX_LINE_CHARACTERS]
    if not lengths:
        return extraction, []
    text = "\n".join("" if len(line) > MAX_LINE_CHARACTERS else line for line in lines)
    message = Message(LINE_TOO_LONG, {"count": len(lengths), "length": max(lengths)})
    return replace(extraction, text=text), [message]
