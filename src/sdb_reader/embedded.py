"""The eSDScom data a supplier embedded in the PDF, and where the sheet read from
the printed text differs from it (SDW-11).

eSDScom is the XML exchange format for safety data sheets; an authoring system
can attach its export to the PDF it prints. That export is the supplier's own
statement of the sheet's fields, so it is a second reading that owes nothing to
this parser. It is compared, never used: what counts is the printed text, and
the exports seen so far leave out the classification as often as not.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from defusedxml import DefusedXmlException, ElementTree as SafeET

from .messages import Message
from .schema import SafetyDataSheet

# The root element of an eSDScom file, with or without the standard's namespace:
# CHEMDOX writes none.
_ROOT = "DatasheetFeed"

# Larger than any export seen (160 kB); an attachment beyond it is something
# else or an attempt.
_MAX_BYTES = 20 * 1024 * 1024

_SIGNAL_WORDS = {"DGR": "Gefahr", "WNG": "Achtung"}

_EUH_IN_TEXT = re.compile(r"\bEUH\d{3}[A-Z]?\b")


@dataclass(frozen=True)
class EmbeddedSheet:
    """The fields of an embedded eSDScom file that are compared."""

    format_version: str | None = None
    authoring_system: str | None = None
    # As the file writes it, an ISO date: "2023-09-19".
    date: str | None = None
    signal_word: str | None = None
    pictograms: frozenset[str] = frozenset()
    hazard_codes: frozenset[str] = frozenset()
    precautionary_codes: frozenset[str] = frozenset()
    supplemental_codes: frozenset[str] = frozenset()
    supplier_name: str | None = None
    supplier_email: str | None = None


@dataclass(frozen=True)
class Difference:
    """One field in which the embedded data and the sheet as read disagree."""

    field: str
    embedded: str | list[str] | None
    read: str | list[str] | None


@dataclass(frozen=True)
class EmbeddedData:
    """What a PDF's embedded eSDScom file says, or why it could not be read."""

    filename: str
    sheet: EmbeddedSheet | None = None
    unreadable: Message | None = None
    # The file itself, byte for byte, and only where it was read (SDW-13).
    content: bytes | None = None


def read_embedded(path: Path) -> EmbeddedData | None:
    """The first embedded eSDScom file of the PDF at *path*; None without one."""
    with pymupdf.open(path) as document:
        for index in range(document.embfile_count()):
            name = str(document.embfile_names()[index])
            content = document.embfile_get(index)
            if _ROOT.encode() not in content[:4096]:
                continue
            return parse_embedded(name, content)
    return None


def parse_embedded(name: str, content: bytes) -> EmbeddedData:
    """An eSDScom file's *content*, as ``read_embedded`` reads it out of a PDF.

    For a file that was taken out of its PDF before (``sdb-reader xml``).
    *name* is the file's name. A file that is too large, carries a document
    type declaration or is no eSDScom file comes back with ``unreadable`` set.

    >>> data = parse_embedded(
    ...     "sds.xml",
    ...     b"<DatasheetFeed><Datasheet><HazardIdentification><HazardLabelling>"
    ...     b"<ClpLabellingInfo><ClpHazardStatement><PhraseCode>315</PhraseCode>"
    ...     b"</ClpHazardStatement></ClpLabellingInfo></HazardLabelling>"
    ...     b"</HazardIdentification></Datasheet></DatasheetFeed>",
    ... )
    >>> sorted(data.sheet.hazard_codes)
    ['H315']
    >>> parse_embedded("other.xml", b"<other/>").unreadable.code
    'embedded-wrong-root'
    """
    if len(content) > _MAX_BYTES:
        return EmbeddedData(
            name, unreadable=Message("embedded-too-large", {"limit_bytes": _MAX_BYTES})
        )
    try:
        # No document type, no entity, no external reference, whatever the
        # file's encoding (SDW-11): the standard library's parser expands
        # internal entities, and a check of the bytes misses them in UTF-16.
        root = SafeET.fromstring(
            content, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
    except DefusedXmlException:
        return EmbeddedData(name, unreadable=Message("embedded-doctype"))
    except ET.ParseError as exc:
        return EmbeddedData(
            name, unreadable=Message("embedded-not-xml", {"detail": str(exc)})
        )
    if _local(root.tag) != _ROOT:
        return EmbeddedData(
            name,
            unreadable=Message("embedded-wrong-root", {"root": _local(root.tag)}),
        )
    datasheet = _first(root, "Datasheet")
    if datasheet is None:
        return EmbeddedData(name, unreadable=Message("embedded-no-datasheet"))
    return EmbeddedData(name, sheet=_sheet_of(datasheet), content=content)


def _sheet_of(datasheet: ET.Element) -> EmbeddedSheet:
    exporting = _first(datasheet, "InformationFromExportingSystem")
    identification = _first(datasheet, "IdentificationSubstPrep")
    supplier = _first(identification, "SupplierInformation")
    label = _first(datasheet, "ClpLabellingInfo")
    system = _first(exporting, "SystemUsedInPreparation")
    supplemental = _codes(label, "ClpSpecialSupplementalLabelInfoMixtures", "EUH")
    # epos prints a further EUH statement as free text: "EUH211: Achtung! …".
    for extra in _all(label, "ClpAdditionalLabellingInfo"):
        supplemental |= set(_EUH_IN_TEXT.findall(_text(extra, "FullText") or ""))
    signal = _first(label, "ClpSignalWord")
    return EmbeddedSheet(
        format_version=_text(exporting, "XmlStandardVersionNo"),
        authoring_system=_joined_text(system),
        date=_text(identification, "RevisionDate")
        or _text(identification, "IssueDate"),
        signal_word=_SIGNAL_WORDS.get(_text(signal, "PhraseCode") or "")
        or _text(signal, "FullText"),
        pictograms=frozenset(
            code
            for pictogram in _all(label, "ClpHazardPictogram")
            if (code := _text(pictogram, "PhraseCode"))
        ),
        hazard_codes=frozenset(_codes(label, "ClpHazardStatement", "H")),
        precautionary_codes=frozenset(_codes(label, "ClpPrecautionaryStatement", "P")),
        supplemental_codes=frozenset(supplemental),
        supplier_name=_text(supplier, "Name"),
        supplier_email=_text(supplier, "Email"),
    )


def differences(embedded: EmbeddedSheet, sheet: SafetyDataSheet) -> list[Difference]:
    """The compared fields in which *sheet* as read differs from *embedded*."""
    statements = sheet.hazard_statements
    contact = sheet.contact_info
    found: list[Difference] = []

    def compare_sets(name: str, want: frozenset[str], got: set[str]) -> None:
        if want != got:
            found.append(Difference(name, sorted(want), sorted(got)))

    def compare_text(name: str, want: str | None, got: str | None) -> None:
        if _folded(want) != _folded(got):
            found.append(Difference(name, want or None, got or None))

    # A first issue has no revision, and the export then repeats the issue
    # date as the revision's.
    read_date = sheet.revision_date or sheet.issue_date
    read_text = read_date.isoformat() if read_date else None
    if (embedded.date or "")[:10] != (read_text or ""):
        found.append(Difference("date", embedded.date, read_text))
    compare_text("signal_word", embedded.signal_word, statements.signal_word)
    compare_sets("pictograms", embedded.pictograms, set(statements.pictograms))
    compare_sets("hazard_codes", embedded.hazard_codes, _parts(statements.hazard_codes))
    compare_sets(
        "precautionary_codes",
        embedded.precautionary_codes,
        _parts(statements.precautionary_codes),
    )
    compare_sets(
        "supplemental_codes",
        embedded.supplemental_codes,
        _parts(statements.supplemental_codes),
    )
    compare_text("supplier_name", embedded.supplier_name, contact.supplier_name)
    compare_text("supplier_email", embedded.supplier_email, contact.supplier_email)
    return found


def _parts(codes: list[str]) -> set[str]:
    """Each code of a joined one on its own: "P305+P351" is P305 and P351."""
    return {part.strip() for code in codes for part in code.split("+") if part.strip()}


def _codes(parent: ET.Element | None, name: str, prefix: str) -> set[str]:
    """The codes under *parent*; eSDScom writes "305+351+338" without the letter."""
    found: set[str] = set()
    for statement in _all(parent, name):
        for part in (_text(statement, "PhraseCode") or "").split("+"):
            part = part.strip()
            if part:
                found.add(part if part[0].isalpha() else prefix + part)
    return found


def _folded(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _all(parent: ET.Element | None, name: str) -> list[ET.Element]:
    if parent is None:
        return []
    return [element for element in parent.iter() if _local(element.tag) == name]


def _first(parent: ET.Element | None, name: str) -> ET.Element | None:
    found = _all(parent, name)
    return found[0] if found else None


def _text(parent: ET.Element | None, name: str) -> str | None:
    """The text of *parent*'s own child *name*.

    Its own child only: a supplier's "Name" has its contact person's below it.
    """
    if parent is None:
        return None
    element = next((child for child in parent if _local(child.tag) == name), None)
    text = (element.text or "").strip() if element is not None else ""
    return text or None


def _joined_text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    return " ".join(part.strip() for part in element.itertext() if part.strip()) or None
