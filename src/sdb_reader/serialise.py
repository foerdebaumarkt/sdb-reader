"""Readings and texts as JSON: what the command prints and what a caller stores."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict
from datetime import date
from typing import Any

from .compliance import (
    age_findings,
    oldest_sheet,
    requires_sheet,
    sheet_findings,
    usable_dates,
)
from .embedded import EmbeddedData, differences
from .expected import clp_expected
from .extraction import ExtractionResult
from .messages import Catalog, Message, shipped_catalog
from .reading import SheetReading
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
from .statements import label_statements
from .verification import DocumentKind, Verification
from .versions import extraction_stage


def _content_hash(extraction: ExtractionResult) -> str | None:
    """Fingerprint the document by its extracted text.

    Hashing the PDF bytes does not work: every write gets a fresh /ID, so the
    same document exported three times yields three different byte hashes at
    identical length. The extracted text is the same across all three.

    Returns None for an empty extraction -- a document we could not read is not
    evidence of being the same as another one we could not read.
    """
    return _text_hash(extraction.text)


def _text_hash(text: str | None) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sheet_to_dict(
    sheet: SafetyDataSheet, extraction: ExtractionResult
) -> dict[str, Any]:
    """The parsed sheet as JSON: the ``sheet`` part of what the command prints.

    *extraction* is the text the sheet was parsed from; its fingerprint goes
    into the record. Every value stands once (SDW-18).
    """
    return _sheet_fields(sheet, _content_hash(extraction))


def _sheet_fields(sheet: SafetyDataSheet, content_hash: str | None) -> dict[str, Any]:
    return {
        # The document's own version, as printed in the sheet.
        "version": sheet.version,
        # Identifies the document by content, so copies filed under several
        # names can be recognised as one. See _content_hash.
        "content_hash": content_hash,
        "product_identifier": sheet.product_identifier,
        "issue_date": sheet.issue_date.isoformat() if sheet.issue_date else None,
        "revision_date": sheet.revision_date.isoformat()
        if sheet.revision_date
        else None,
        "language": sheet.language,
        # The countries the sheet is issued for (SDB-69), what section 2 says
        # about the classification (SDB-75), and whether the product needs a
        # sheet by it (SDB-76): a sheet for one that does not is voluntary.
        "countries": list(sheet.countries),
        "stated_classification": sheet.stated_classification.value,
        # Whether the sheet calls itself voluntary or not prescribed, and its
        # product an article beside that (SDB-142): an article needs no sheet
        # whatever the label prints, an unclassified mixture none either.
        "stated_voluntary": sheet.stated_voluntary,
        "stated_article": sheet.stated_article,
        "sheet_required": requires_sheet(sheet),
        "hazard_statements": _label_fields(sheet.hazard_statements),
        "contact_info": {
            "supplier_name": sheet.contact_info.supplier_name,
            "supplier_address": sheet.contact_info.supplier_address,
            "supplier_phone": sheet.contact_info.supplier_phone,
            "emergency_phone": sheet.contact_info.emergency_phone,
            "supplier_email": sheet.contact_info.supplier_email,
            "supplier_website": sheet.contact_info.supplier_website,
            "information_email": sheet.contact_info.information_email,
        },
        "section_text": {
            section.value: text for section, text in sheet.section_text.items()
        },
    }


def _label_fields(label: HazardStatements, *, further: bool = True) -> dict[str, Any]:
    """*label* as the record holds it; a further label's own label carries no
    further labels (SDW-51)."""
    fields: dict[str, Any] = {
        "hazard_codes": label.hazard_codes,
        "precautionary_codes": label.precautionary_codes,
        "supplemental_codes": label.supplemental_codes,
        "signal_word": label.signal_word,
        "pictograms": label.pictograms,
        "hazard_text": label.hazard_text,
        "precautionary_text": label.precautionary_text,
        "supplemental_text": label.supplemental_text,
        "codes_from_wording": label.codes_from_wording,
        "drawing_read": label.drawing_read,
        "states_no_signal_word": label.states_no_signal_word,
        "states_no_pictograms": label.states_no_pictograms,
        # Whom the label and single statements apply to (SDB-191, SDB-192).
        "condition": None if label.condition is None else label.condition.value,
        "condition_text": label.condition_text,
        "statement_conditions": {
            code: said.value for code, said in label.statement_conditions.items()
        },
    }
    if further:
        # The blocks of 2.2 beside the label (SDB-188 to SDB-190).
        fields["further_labels"] = [
            {
                "kind": block.kind.value,
                "heading": block.heading,
                "text": block.text,
                "omitted_codes": block.omitted_codes,
                "label": _label_fields(block.label, further=False),
            }
            for block in label.further_labels
        ]
    return fields


def _label_from_dict(label: Mapping[str, Any]) -> HazardStatements:
    """The label ``_label_fields`` stored. The keys of SDB-174, SDB-179,
    SDB-180 and SDB-188 to SDB-192 are not in a reading stored before them."""
    condition = label.get("condition")
    return HazardStatements(
        hazard_codes=_texts(label["hazard_codes"]),
        precautionary_codes=_texts(label["precautionary_codes"]),
        supplemental_codes=_texts(label["supplemental_codes"]),
        signal_word=_optional_text(label["signal_word"]),
        pictograms=_texts(label["pictograms"]),
        hazard_text=_optional_text(label["hazard_text"]),
        precautionary_text=_optional_text(label["precautionary_text"]),
        supplemental_text=_optional_text(label["supplemental_text"]),
        codes_from_wording=_texts(label.get("codes_from_wording", [])),
        drawing_read=label.get("drawing_read", False) is True,
        states_no_signal_word=label.get("states_no_signal_word", False) is True,
        states_no_pictograms=label.get("states_no_pictograms", False) is True,
        condition=None if condition is None else LabelCondition(_text(condition)),
        condition_text=_optional_text(label.get("condition_text")),
        statement_conditions={
            _text(code): LabelCondition(_text(said))
            for code, said in label.get("statement_conditions", {}).items()
        },
        further_labels=[
            FurtherLabel(
                kind=LabelKind(_text(block["kind"])),
                heading=_text(block["heading"]),
                text=_optional_text(block["text"]),
                omitted_codes=_texts(block["omitted_codes"]),
                label=_label_from_dict(block["label"]),
            )
            for block in label.get("further_labels", [])
        ],
    )


def sheet_from_dict(stored: Mapping[str, Any]) -> SafetyDataSheet:
    """The sheet ``sheet_to_dict`` stored, to judge it again (BIB-21).

    Reads what this version writes: the ``sheet`` part of a record of
    ``read``, or of one of its ``parts``. ``content_hash`` and
    ``sheet_required`` are not part of a sheet and are left out;
    ``requires_sheet`` gives the second again. A key this version does not
    know is ignored.

    A record that lacks a key, or holds a value of another kind, was stored
    by another version and is refused with ``ValueError``: make the reading
    again from the stored text (``read_extraction``) instead. Whether a
    record still holds is the caller's to compare with ``PARSER_VERSION``.

    >>> stored = {
    ...     "version": "2.0", "product_identifier": "Musterfarbe",
    ...     "issue_date": None, "revision_date": "2024-03-01", "language": "de",
    ...     "countries": ["DE"], "stated_classification": "classified",
    ...     "stated_voluntary": False, "stated_article": False,
    ...     "hazard_statements": {
    ...         "hazard_codes": ["H315"], "precautionary_codes": [],
    ...         "supplemental_codes": [], "signal_word": "Achtung",
    ...         "pictograms": ["GHS07"], "hazard_text": None,
    ...         "precautionary_text": None, "supplemental_text": None,
    ...     },
    ...     "contact_info": {
    ...         "supplier_name": "Nordwerk GmbH", "supplier_address": None,
    ...         "supplier_phone": None, "emergency_phone": None,
    ...         "supplier_email": None, "supplier_website": None,
    ...         "information_email": None,
    ...     },
    ...     "section_text": {"section_2": "Signalwort: Achtung"},
    ... }
    >>> sheet = sheet_from_dict(stored)
    >>> sheet.revision_date, sheet.hazard_statements.signal_word
    (datetime.date(2024, 3, 1), 'Achtung')
    >>> requires_sheet(sheet)
    True
    """
    try:
        label = stored["hazard_statements"]
        contact = stored["contact_info"]
        return SafetyDataSheet(
            product_identifier=_optional_text(stored["product_identifier"]),
            issue_date=_stored_date(stored["issue_date"]),
            revision_date=_stored_date(stored["revision_date"]),
            version=_optional_text(stored["version"]),
            language=_text(stored["language"]),
            hazard_statements=_label_from_dict(label),
            contact_info=ContactInfo(
                supplier_name=_optional_text(contact["supplier_name"]),
                supplier_address=_optional_text(contact["supplier_address"]),
                supplier_phone=_optional_text(contact["supplier_phone"]),
                emergency_phone=_optional_text(contact["emergency_phone"]),
                supplier_email=_optional_text(contact["supplier_email"]),
                supplier_website=_optional_text(contact["supplier_website"]),
                information_email=_optional_text(contact["information_email"]),
            ),
            section_text={
                Section(name): _text(text)
                for name, text in stored["section_text"].items()
            },
            countries=_texts(stored["countries"]),
            stated_classification=StatedClassification(stored["stated_classification"]),
            stated_voluntary=_flag(stored["stated_voluntary"]),
            stated_article=_flag(stored["stated_article"]),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError(
            "not a sheet as this version stores it "
            f"({type(exc).__name__}: {exc}); read the stored text again"
        ) from exc


def _text(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"expected text, found {type(value).__name__}")
    return value


def _optional_text(value: Any) -> str | None:
    return None if value is None else _text(value)


def _texts(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"expected a list, found {type(value).__name__}")
    return [_text(item) for item in value]


def _flag(value: Any) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"expected true or false, found {type(value).__name__}")
    return value


def _stored_date(value: Any) -> date | None:
    return None if value is None else date.fromisoformat(_text(value))


def _shown(messages: list[Message], catalog: Catalog | None) -> list[dict[str, Any]]:
    """Each message as code, values and sentence (SDW-17); German unless asked."""
    chosen = catalog or shipped_catalog()
    return [chosen.to_dict(message) for message in messages]


def verification_to_dict(
    verification: Verification, *, catalog: Catalog | None = None
) -> dict[str, Any]:
    """The verdict as a record stores it; *catalog* words its messages."""
    return {
        "kind": verification.kind.value,
        "prints_statement_codes": verification.prints_statement_codes,
        "warnings": _shown(verification.warnings, catalog),
        "errors": _shown(verification.errors, catalog),
    }


def _clp_expected(sheet: SafetyDataSheet) -> dict[str, Any]:
    """What ``clp_expected`` says of *sheet*'s label, as the record holds it
    (SDW-48)."""
    return asdict(clp_expected(sheet.hazard_statements))


def reading_to_dict(
    reading: SheetReading,
    *,
    include_raw_text: bool = False,
    embedded: EmbeddedData | None = None,
    catalog: Catalog | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """What reading one file found, as ``sdb-reader read`` prints it.

    *today* is the day the findings take as the present (``sheet_findings``);
    the command passes the machine's date. Without it no date is questioned,
    and the record is the same on any day.

    Without the file itself: the command puts its path, name and size in
    front. *embedded* is what ``read_embedded`` found in the PDF; with it the
    record lists where the embedded data and the sheet as read differ (SDW-11).
    Every message stands as its code, its values and a sentence from
    *catalog*: the shipped German one unless another is given (SDW-17).
    """
    # Every record has the same keys for its kind (SDW-19): the three lists
    # are there for every file, empty where there is nothing to say.
    record: dict[str, Any] = {
        "verification": verification_to_dict(reading.verification, catalog=catalog),
        "warnings": _shown(reading.warnings, catalog),
        "errors": _shown(reading.errors, catalog),
        "findings": [],
    }
    if reading.extraction is not None:
        record["extraction"] = _extraction_to_dict(
            reading.extraction, include_raw_text=include_raw_text, catalog=catalog
        )
        if reading.parser_result is not None:
            record["sheet"] = sheet_to_dict(
                reading.parser_result.sheet, reading.extraction
            )
            _dates_that_can_be_right(
                record["sheet"],
                usable_dates(
                    reading.parser_result.sheet, today, reading.parser_result.parts
                ),
            )
            record["parser"] = {
                "warnings": _shown(reading.parser_result.warnings, catalog)
            }
            sheet = reading.parser_result.sheet
            record["statements"] = _statements(sheet)
            # What the codes call for, apart from the reading (SDW-48).
            record["clp_expected"] = _clp_expected(sheet)
            # How many sheets the file holds, and each one read on its own
            # where it holds several (SDW-32); the keys above are the file's.
            parts = reading.parser_result.parts
            record["sheet_count"] = len(parts) or 1
            # A cover page in front of the sheets, and the word on it that
            # names a display (SDW-35); it is read for nothing else.
            record["cover_page"] = reading.parser_result.cover_page
            record["display_term"] = reading.parser_result.display_term
            if parts:
                record["parts"] = [
                    {
                        "sheet": _dates_that_can_be_right(
                            _sheet_fields(part.sheet, _text_hash(part.text)),
                            usable_dates(part.sheet, today),
                        ),
                        "statements": _statements(part.sheet),
                        "clp_expected": _clp_expected(part.sheet),
                        "warnings": _shown(part.warnings, catalog),
                        # Each sheet's age on its own dates (SDW-46).
                        "findings": _shown(age_findings(part.sheet, today), catalog),
                    }
                    for part in parts
                ]
                # The sheet with the oldest date, for whoever judges the
                # file by it (SDW-45); the file's own date stays the newest.
                oldest = oldest_sheet(parts, today)
                record["oldest_sheet"] = (
                    None
                    if oldest is None
                    else {
                        "sheet": oldest[0],
                        "date": oldest[1].isoformat(),
                        "dated_by": oldest[2],
                    }
                )
            record["findings"] = _shown(
                sheet_findings(
                    sheet, reading.parser_result.warnings, today=today, parts=parts
                ),
                catalog,
            )
    if reading.verification.kind is DocumentKind.FOREIGN_SAFETY_DATA_SHEET:
        # One file says nothing about the product's other sheets (SDW-8).
        record["findings"] = _shown([Message("not-german")], catalog)
    if embedded is not None:
        record["embedded_data"] = _embedded_to_dict(embedded, reading, catalog)
    return record


def _dates_that_can_be_right(
    fields: dict[str, Any], dates: tuple[date | None, date | None]
) -> dict[str, Any]:
    """*fields* with the revision and issue date that can be right (SDB-137).

    A date after the day of the run is no date; the finding
    ``revised-in-future`` names it as printed.
    """
    revision, issue = dates
    fields["revision_date"] = revision.isoformat() if revision else None
    fields["issue_date"] = issue.isoformat() if issue else None
    return fields


def _statements(sheet: SafetyDataSheet) -> list[dict[str, Any]]:
    """The label's statements, each with both wordings (SDW-5)."""
    return [
        {
            "code": s.code,
            "sheet": s.sheet,
            "regulation": s.regulation,
            "code_source": s.code_source,
        }
        for s in label_statements(sheet.hazard_statements)
    ]


def _embedded_to_dict(
    embedded: EmbeddedData, reading: SheetReading, catalog: Catalog | None
) -> dict[str, Any]:
    """The embedded eSDScom file and where the sheet as read differs (SDW-11).

    ``differences`` is always there; ``compared`` says whether there was
    anything to compare: a readable embedded file and a German sheet (SDW-18).
    """
    payload: dict[str, Any] = {
        "format": "eSDScom",
        "filename": embedded.filename,
        "compared": False,
        "differences": [],
    }
    if embedded.sheet is None:
        if embedded.unreadable is not None:
            payload["unreadable"] = _shown([embedded.unreadable], catalog)[0]
        return payload
    payload["version"] = embedded.sheet.format_version
    payload["system"] = embedded.sheet.authoring_system
    if reading.parser_result is not None:
        payload["compared"] = True
        payload["differences"] = [
            {"field": d.field, "embedded": d.embedded, "read": d.read}
            for d in differences(embedded.sheet, reading.parser_result.sheet)
        ]
    return payload


def _extraction_to_dict(
    extraction: ExtractionResult, *, include_raw_text: bool, catalog: Catalog | None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        # The stage the text comes from: a stored text names its own, a text
        # read from the PDF just now is of this library's (SDW-27).
        "stage": extraction.metadata.get("stage") or extraction_stage(),
        "extractor": extraction.extractor,
        "pages_sampled": extraction.pages_sampled,
        "warnings": _shown(extraction.warnings, catalog),
        "character_count": extraction.metadata.get("character_count"),
    }
    if extraction.metadata.get("tesseract"):
        payload["tesseract"] = extraction.metadata["tesseract"]
    if include_raw_text:
        payload["raw_text"] = extraction.raw_text
    return payload


def extraction_to_dict(extraction: ExtractionResult) -> dict[str, Any]:
    """The text read from a PDF, in a form to store as JSON (BIB-3).

    Holds what a reading needs and names the stage it comes from. The text
    before tidying and the single pages are not kept.

    >>> text = "Sicherheitsdatenblatt\\nABSCHNITT 1: Bezeichnung des Stoffs\\n"
    >>> stored = extraction_to_dict(
    ...     extraction_from_dict(
    ...         {"text": text, "extractor": "pymupdf", "pages_sampled": 1, "warnings": []}
    ...     )
    ... )
    >>> sorted(stored)
    ['extractor', 'pages_sampled', 'stage', 'text', 'warnings']
    >>> stored["stage"] == extraction_stage()
    True
    """
    return {
        "stage": extraction_stage(),
        "text": extraction.text,
        "extractor": extraction.extractor,
        "pages_sampled": extraction.pages_sampled,
        # Code and values, no sentence: a stored text has no language.
        "warnings": [message.to_dict() for message in extraction.warnings],
        # Only for a text the text recognition read (SDB-116).
        **(
            {"tesseract": extraction.metadata["tesseract"]}
            if extraction.metadata.get("tesseract")
            else {}
        ),
    }


# The warnings of the reading stage as they were written before they had
# codes. A text stored then is still read (BIB-3).
_WARNINGS_BEFORE_CODES: tuple[tuple[re.Pattern[str], str, str | None], ...] = (
    (
        re.compile(r"^Text layer split into single characters; read by OCR"),
        "read-by-ocr-single-characters",
        None,
    ),
    (re.compile(r"^No text layer; read by OCR"), "read-by-ocr-no-text-layer", None),
    (
        re.compile(r"^(\d+) page\(s\) without a text layer read by OCR\.$"),
        "pages-read-by-ocr",
        "pages",
    ),
    (re.compile(r"^Extracted text is unusually short; "), "short-text", None),
)


def _stored_warning(stored: Any) -> Message:
    """A stored warning as a message: code and values, or a sentence of old."""
    if isinstance(stored, Mapping):
        try:
            return Message.from_dict(stored)
        # Stored by another version: a code that has gone since, or values
        # that no longer fit it. A stored text outlives the codes of its day.
        except (KeyError, TypeError, ValueError):
            return Message(
                "unknown",
                {"text": json.dumps(stored, ensure_ascii=False, sort_keys=True)},
            )
    for pattern, code, counted in _WARNINGS_BEFORE_CODES:
        found = pattern.match(str(stored))
        if found:
            return Message(code, {counted: int(found.group(1))} if counted else {})
    # Not dropped: it says something about the text, even if not in a code.
    return Message("unknown", {"text": str(stored)})


def extraction_from_dict(stored: Mapping[str, Any]) -> ExtractionResult:
    """The text ``extraction_to_dict`` stored, for ``read_extraction`` (BIB-3).

    Whether the stored stage still holds is the caller's to compare with
    ``extraction_stage()``; a text of another stage is read all the same. A
    warning stored as a sentence, before warnings had codes, gets the code of
    that sentence, or "unknown" with the sentence as its value; so does a
    warning with a code this version does not know.

    >>> extraction = extraction_from_dict(
    ...     {"text": "Sicherheitsdatenblatt", "extractor": "pymupdf",
    ...      "pages_sampled": 1, "warnings": []}
    ... )
    >>> extraction.text, extraction.pages_sampled
    ('Sicherheitsdatenblatt', 1)
    """
    text = stored["text"]
    return ExtractionResult(
        text=text,
        raw_text=text,
        extractor=stored["extractor"],
        pages_sampled=stored["pages_sampled"],
        warnings=[_stored_warning(warning) for warning in stored["warnings"]],
        metadata={
            "character_count": len(text),
            **({"stage": str(stored["stage"])} if stored.get("stage") else {}),
            **({"tesseract": stored["tesseract"]} if stored.get("tesseract") else {}),
        },
    )
