"""Reading one safety data sheet: its text, whether it is one, and what it says.

The entry point of the library. A file goes in; what comes back is the text
read from it, the verdict whether it is a safety data sheet and, if it is, the
parsed sheet -- or the errors that stopped the reading. Storing the result,
and knowing which file it belongs to, is the caller's (BIB-2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .extraction import ExtractionError, ExtractionResult, extract_pdf_text
from .messages import Message
from .parser import ParsedSheet, SDSParser
from .verification import DocumentKind, SDSVerifier, Verification


@dataclass(slots=True)
class SheetReading:
    """What reading one file found."""

    verification: Verification
    # None when the file could not be read at all; *errors* says why.
    extraction: ExtractionResult | None = None
    # None unless the file is a German safety data sheet.
    parser_result: ParsedSheet | None = None
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
    return read_extraction(extraction)


def read_extraction(extraction: ExtractionResult) -> SheetReading:
    """Judge and parse a text that was read from a PDF before (BIB-3).

    Gives what ``read_sheet`` gives for the file the text came from. Reading a
    PDF's text takes nearly all the time of a reading; a caller that keeps the
    text (``extraction_to_dict``) reads a sheet again in milliseconds.

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
    verification = SDSVerifier().verify(extraction)
    if verification.kind is not DocumentKind.SAFETY_DATA_SHEET:
        return SheetReading(
            verification=verification,
            extraction=extraction,
            warnings=[Message("not-a-sheet")],
        )
    return SheetReading(
        verification=verification,
        extraction=extraction,
        parser_result=SDSParser().parse(extraction),
    )
