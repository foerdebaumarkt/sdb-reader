"""Read German safety data sheets (Sicherheitsdatenblätter) from PDF files.

It works on one PDF at a time and knows nothing about products or about the
other files a product has. Which of several sheets is the current one it
chooses from plain data a caller hands it (``current_state``); what follows
from that is for the program that uses it.

    >>> from pathlib import Path
    >>> from sdb_reader import read_sheet, reading_to_dict
    >>> reading = read_sheet(Path("sheet.pdf"))  # doctest: +SKIP
    >>> reading.verification.kind  # doctest: +SKIP
    <DocumentKind.SAFETY_DATA_SHEET: 'safety-data-sheet'>
    >>> record = reading_to_dict(reading)  # doctest: +SKIP

The names this package exports are its interface (BIB-1); they change only
with notice. Everything reached through a submodule is internal and may change
with any release, the parts that ask a language model included.

- Reading: ``read_sheet`` reads a PDF, ``extract_pdf_text`` only its text,
  ``read_label_images`` only the pictograms its labels show as pictures
  (``LabelImages``, ``LabelImagesStatus``), ``read_extraction`` a text read
  before. ``SheetReading`` is what comes back;
  for a file that holds several sheets its parsed result names each one read
  on its own as a ``SheetPart``.
- The reading: a ``SafetyDataSheet`` with its label (``HazardStatements``),
  supplier (``ContactInfo``), sections (``Section``) and what section 2 says
  of the classification (``StatedClassification``); the blocks of 2.2 beside
  the label as ``FurtherLabel`` of a ``LabelKind``, and whom a label or a
  statement applies to as ``LabelCondition``.
- Keeping: ``reading_to_dict``, ``sheet_to_dict`` and ``verification_to_dict``
  give JSON, ``sheet_from_dict`` reads a stored sheet back;
  ``extraction_to_dict`` and ``extraction_from_dict`` store a text,
  ``label_images_to_dict`` and ``label_images_from_dict`` its pictograms.
  ``EXTRACTION_VERSION``, ``LABEL_IMAGES_VERSION``, ``PARSER_VERSION``,
  ``extraction_stage`` and ``label_images_stage`` say whether what was kept
  still holds.
- Judging a sheet: ``sheet_findings`` and the checks it is made of,
  ``classification`` and ``sheet_duty`` (``SheetDuty``); ``clp_expected`` gives the
  signal word and pictograms a label's codes call for and where the reading
  differs (``ClpExpected``).
- Statements and pictograms: ``label_statements`` with the regulation's
  wording (``canonical_text``) and whether the label prints each code, the
  statement texts tidied and rendered, ``as_printed`` for the texts without
  the codes the label does not print, the pictograms that follow from H
  statements.
- Embedded data: ``read_embedded``, ``parse_embedded`` and
  ``embedded_differences``.
- Messages: what the library notes about a file is a ``Message`` with a
  code from ``MESSAGE_CODES``; ``shipped_catalog`` and ``load_catalog`` give
  the ``Catalog`` that words it, German unless asked.
- Several sheets: ``current_state`` chooses the current one among
  ``SheetState`` values and says why (``Choice``, ``ChoiceReason``).
"""

from .compliance import (
    Classification,
    SheetDuty,
    classification,
    contradicts_label,
    euh_outside_label,
    predates_annex_ii,
    predates_clp,
    sheet_duty,
    sheet_findings,
)
from .current import Choice, ChoiceReason, SheetState, current_state
from .embedded import (
    Difference as EmbeddedDifference,
    EmbeddedData,
    EmbeddedSheet,
    differences as embedded_differences,
    parse_embedded,
    read_embedded,
)
from .expected import ClpExpected, clp_expected
from .extraction import (
    ExtractionError,
    ExtractionResult,
    extract_pdf_text,
)
from .label_images import (
    LabelImages,
    LabelImagesStatus,
    label_images_from_dict,
    label_images_to_dict,
    read_label_images,
)
from .messages import (
    MESSAGE_CODES,
    Catalog,
    Message,
    load_catalog,
    shipped_catalog,
)
from .parser import ParsedSheet, SheetPart
from .pictograms import pictograms_for
from .reading import SheetReading, read_extraction, read_sheet
from .schema import (
    ContactInfo,
    FurtherLabel,
    HazardStatements,
    LabelCondition,
    LabelKind,
    SafetyDataSheet,
    Section,
    StatedClassification,
)
from .serialise import (
    extraction_from_dict,
    extraction_to_dict,
    reading_to_dict,
    sheet_from_dict,
    sheet_to_dict,
    verification_to_dict,
)
from .statements import (
    StatementWording,
    as_printed,
    canonical_text,
    label_statements,
    normalize_statements,
    render_statements,
    tidy_statements,
)
from .verification import DocumentKind, Verification
from .versions import (
    EXTRACTION_VERSION,
    LABEL_IMAGES_VERSION,
    PARSER_VERSION,
    extraction_stage,
    label_images_stage,
)

__all__ = [
    "EXTRACTION_VERSION",
    "LABEL_IMAGES_VERSION",
    "MESSAGE_CODES",
    "PARSER_VERSION",
    "Catalog",
    "Choice",
    "ChoiceReason",
    "Classification",
    "ClpExpected",
    "ContactInfo",
    "DocumentKind",
    "EmbeddedData",
    "EmbeddedDifference",
    "EmbeddedSheet",
    "ExtractionError",
    "ExtractionResult",
    "FurtherLabel",
    "HazardStatements",
    "LabelCondition",
    "LabelImages",
    "LabelImagesStatus",
    "LabelKind",
    "Message",
    "ParsedSheet",
    "SafetyDataSheet",
    "Section",
    "SheetDuty",
    "SheetPart",
    "SheetReading",
    "SheetState",
    "StatedClassification",
    "StatementWording",
    "Verification",
    "as_printed",
    "canonical_text",
    "classification",
    "clp_expected",
    "contradicts_label",
    "current_state",
    "embedded_differences",
    "euh_outside_label",
    "extract_pdf_text",
    "extraction_from_dict",
    "extraction_stage",
    "extraction_to_dict",
    "label_images_from_dict",
    "label_images_stage",
    "label_images_to_dict",
    "label_statements",
    "load_catalog",
    "normalize_statements",
    "parse_embedded",
    "pictograms_for",
    "predates_annex_ii",
    "predates_clp",
    "read_embedded",
    "read_extraction",
    "read_label_images",
    "read_sheet",
    "reading_to_dict",
    "render_statements",
    "sheet_duty",
    "sheet_findings",
    "sheet_from_dict",
    "sheet_to_dict",
    "shipped_catalog",
    "tidy_statements",
    "verification_to_dict",
]
