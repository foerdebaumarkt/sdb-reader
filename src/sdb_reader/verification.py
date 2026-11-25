"""Verification helpers for Sicherheitsdatenblatt (SDS) PDFs."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum

from .extraction import ExtractionResult
from .messages import Message
from .parser import split_sections
from .schema import Section

HEADER_KEYWORDS: tuple[str, ...] = (
    "sicherheitsdatenblatt",
    "safety data sheet",
    "material safety data sheet",
)

SECTION_MARKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"abschnitt\s+1", re.IGNORECASE),
    re.compile(r"section\s+1", re.IGNORECASE),
)

# The words standing as a title: at the start of a line, alone or as the end
# of a compound ("EG-Sicherheitsdatenblatt", "Produkt-Sicherheitsdatenblatt").
# A real sheet carries one, usually on every page. The keywords above match
# them anywhere, and the word alone was enough to pass: One supplier's "Sicherheits-
# informationen" for its batteries passed on "Verantwortlich fuer das
# Sicherheitsdatenblatt" and on the sentence stating that no Sicherheits-
# datenblatt is required for them. Measured over 3191 documents
# that passed with their text kept, that document is the only one without a
# title line; the nine that cite no REACH article and the three written
# voluntarily for unclassified mixtures all carry one.
#
# It reads lines, so it depends on where the extractor breaks them: running
# text that happens to wrap just before the word passes, and a title the
# extractor joins onto the line before it ("Seite 1/8 Sicherheitsdatenblatt")
# does not. Neither occurs in the corpus today. The prefixes are the ones it
# holds, with every hyphen a PDF may carry.
#
# A sentence that happens to begin its line with the word is no title either.
# EUH210 reads "Sicherheitsdatenblatt auf Anfrage erhältlich." and stands on
# its own line in technical data sheets (26 of one supplier passed), and
# running text wraps before the word: "… entnehmen Sie bitte dem" /
# "Sicherheitsdatenblatt.".
#
# Only the German word (SDB-66): a sheet in another language is no German
# safety data sheet, whatever it is titled.
GERMAN_TITLE_PATTERN = re.compile(
    r"(?im)^[^\S\n]*[\W\d]{0,4}"
    r"(?:(?:eg|eu|ec|produkt)[^\S\n]*[-‐‑–][^\S\n]*|(?:eg|eu|ec)[^\S\n]+)?"
    r"sicherheitsdatenblatt"
    r"(?![^\S\n]*(?:\.|auf\s+Anfrage))"
)
# A misspelled title is a title (SDB-66): "Sichheitsdatenblatt". The word where
# a title stands, at most two letters off and no longer than the word itself,
# so that an inflected form at the start of a wrapped sentence
# ("Sicherheitsdatenblattes") is none.
_TITLE_WORD = "sicherheitsdatenblatt"
_TITLE_CANDIDATE = re.compile(
    r"(?im)^[^\S\n]*[\W\d]{0,4}([^\W\d_]{17,21})\b"
    r"(?![^\S\n]*(?:\.|auf\s+Anfrage))"
)
# A sentence that wraps before the word is no title (SDB-59): the word goes on
# in lower case and the line before ends in a lower-case word ("… die in
# diesem" / "Sicherheitsdatenblatt enthaltenen Daten"). What a title goes on
# with says by what or for what the sheet is made; such a line stays a title
# also under a product name in lower case.
_LOWER_CASE_AHEAD = re.compile(r"[^\S\n]+[a-zäöüß]")
_TITLE_GOES_ON = re.compile(
    r"[^\S\n]+(?:gemäß|gemäss|nach|in[^\S\n]+Anlehnung[^\S\n]+an|für|zum|vom)\b",
    re.IGNORECASE,
)
_ENDS_IN_LOWER_CASE = re.compile(r"(?:^|\s)[a-zäöüß]+$")
# A leaflet on handling an article that calls itself a safety data sheet
# (SDB-59): "Sicherheitsdatenblatt" / "zum sicheren Umgang mit Bleibatterien".
_LEAFLET_GOES_ON = re.compile(
    r"zum[^\S\n]+sicheren[^\S\n]+Umgang[^\S\n]+mit\b", re.IGNORECASE
)
_REACH_NUMBER = re.compile(r"1907\s*/\s*2006")
# How many of the sixteen sections make the layout of a safety data sheet
# (SDB-66). Among the files the check refuses, 1,451 hold four at most and 589
# twelve or more, none between.
SECTIONS_OF_A_SHEET = 12
# Headings a sheet in English carries, which the parser reads too: sections
# found under them are no German layout.
_ENGLISH_HEADING = re.compile(
    r"(?im)^\W{0,6}(?:\d{1,2}\W{1,3})?section[^\S\n]+0?(\d{1,2})\b"
)
# The numbering Annex II prescribes in every language (SDB-68): a subsection
# "n.1" at a line's start for sections 1 to 15.
_FIRST_SUBSECTION = re.compile(
    r"(?m)^[^\S\n]*[-·•*]?[^\S\n]*(\d{1,2})\s?\.\s?1\b(?!\s?\.\s?\d)"
)
NUMBERED_SECTIONS_OF_A_SHEET = 10
# A document that prints statement codes says something about the product,
# whatever it is (SDB-68). Three different ones, because one or two are mostly
# chance: "BM P150 L".
_STATEMENT_CODE = re.compile(r"\b(?:H[2-4]\d{2}|P[1-5]\d{2}|EUH\s?\d{3})\b")
STATEMENT_CODES_OF_A_LABEL = 3


class DocumentKind(StrEnum):
    """What a file filed as a safety data sheet is (SDB-66, SDB-68)."""

    # Carries the German title: the only kind the parser reads.
    SAFETY_DATA_SHEET = "safety-data-sheet"
    # Laid out like one, without calling itself one: a voluntary document for
    # a product that needs none.
    SAFETY_INFORMATION = "safety-information"
    # A safety data sheet in another language, told by its layout.
    FOREIGN_SAFETY_DATA_SHEET = "safety-data-sheet-other-language"
    DOCUMENT = "document"


REGULATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"verordnung\s*\(eg\)\s*nr\.?\s*1907/2006", re.IGNORECASE),
    re.compile(r"regulation\s*\(ec\)\s*no\s*1907/2006", re.IGNORECASE),
)

HAZARD_CODE_PATTERN = re.compile(r"\bH\d{3}\b")


@dataclass(slots=True)
class Verification:
    """What kind of document a text is, and why.

    ``kind`` is the verdict; only a ``SAFETY_DATA_SHEET`` is parsed. ``errors``
    say why a file is none, ``warnings`` what else stood out.
    """

    errors: list[Message]
    warnings: list[Message]
    kind: DocumentKind = DocumentKind.DOCUMENT
    # Whether the text prints three or more different statement codes. Judged
    # for every file that is neither a German sheet nor a safety information;
    # None for those two (SDB-68).
    prints_statement_codes: bool | None = None


class SDSVerifier:
    """Detect whether a PDF is a genuine Sicherheitsdatenblatt."""

    def verify(self, extraction: ExtractionResult) -> Verification:
        """Judge an already-extracted document.

        Takes the text rather than the file. It never needed the file -- all
        it looks at is ``extraction.text`` -- but it used to
        open the PDF itself and read the first four pages, so every document was
        read twice: once cheaply to decide whether it was a safety data sheet,
        then again in full to parse it.

        The idea was that a document which turns out not to be one should never
        cost a full extraction. Measured over the corpus that saves nothing:
        of 2804 current sheets and 884 retired ones, not one was refused. The
        gate cost 37% more reading time on every document to guard against a
        case that does not arise.
        """

        errors: list[Message] = []
        warnings: list[Message] = list(extraction.warnings)

        lower_text = extraction.text.lower()

        header_hits = _find_keywords(lower_text, HEADER_KEYWORDS)
        if not header_hits:
            warnings.append(Message("no-title-keywords"))
        title_line = has_german_title(extraction.text)
        leaflet = not title_line and _has_leaflet_title(extraction.text)

        section_hits = sum(
            1 for pattern in SECTION_MARKER_PATTERNS if pattern.search(lower_text)
        )
        if section_hits == 0:
            warnings.append(Message("no-section-marker"))

        regulation_hits = sum(
            1 for pattern in REGULATION_PATTERNS if pattern.search(lower_text)
        )
        if regulation_hits == 0:
            warnings.append(Message("no-regulation-reference"))

        hazard_code_count = len(HAZARD_CODE_PATTERN.findall(extraction.text))
        if hazard_code_count == 0:
            warnings.append(Message("no-hazard-codes-in-text"))

        document_length = len(extraction.text)
        if document_length < 800:
            warnings.append(Message("short-sample"))

        sections_found = _sections_found(extraction.text)
        kind = _kind(extraction.text, title_line=title_line, sections=sections_found)
        prints_statement_codes: bool | None = None
        if kind is DocumentKind.SAFETY_INFORMATION:
            errors.append(
                Message("leaflet-title")
                if leaflet
                else Message("safety-information", {"sections": sections_found})
            )
        elif kind is not DocumentKind.SAFETY_DATA_SHEET:
            prints_statement_codes = (
                len(
                    {
                        "".join(c.split())
                        for c in _STATEMENT_CODE.findall(extraction.text)
                    }
                )
                >= STATEMENT_CODES_OF_A_LABEL
            )
            if kind is DocumentKind.FOREIGN_SAFETY_DATA_SHEET:
                errors.append(Message("other-language"))
            elif leaflet:
                errors.append(Message("leaflet-title"))
            elif title_line:
                errors.append(Message("cover-only"))
            elif header_hits:
                errors.append(Message("title-in-running-text"))
            else:
                errors.append(Message("no-safety-data-sheet"))

        return Verification(
            errors=errors,
            warnings=warnings,
            kind=kind,
            prints_statement_codes=prints_statement_codes,
        )

    def refuse_unreadable(self, errors: Sequence[Message]) -> Verification:
        """The verdict for a document that could not be read at all."""
        return Verification(errors=list(errors), warnings=[])


def has_german_title(text: str) -> bool:
    """Whether a line carries "Sicherheitsdatenblatt" as a title, misspelled or not.

    A sentence that wraps before the word is none (SDB-59), nor is the title
    of a leaflet on handling an article (SDB-59).
    """
    names_reach = bool(_REACH_NUMBER.search(text))
    return any(
        not _wraps_before(text, end)
        and (names_reach or not _goes_on_as_leaflet(text, end))
        for end in _title_ends(text)
    )


def _has_leaflet_title(text: str) -> bool:
    """Whether a title line is a leaflet's, in a text that does not name REACH."""
    return not _REACH_NUMBER.search(text) and any(
        _goes_on_as_leaflet(text, end) for end in _title_ends(text)
    )


def _title_ends(text: str) -> Iterator[int]:
    """Where the word ends in each line that carries it the way a title does."""
    for match in GERMAN_TITLE_PATTERN.finditer(text):
        yield match.end()
    for match in _TITLE_CANDIDATE.finditer(text):
        if _edits(match.group(1).lower(), _TITLE_WORD) <= 2:
            yield match.end(1)


def _wraps_before(text: str, end: int) -> bool:
    """Whether the line is the rest of a sentence that broke before the word."""
    if not _LOWER_CASE_AHEAD.match(text, end) or _TITLE_GOES_ON.match(text, end):
        return False
    start = text.rfind("\n", 0, end)
    before = text[: max(start, 0)].rstrip()
    return bool(_ENDS_IN_LOWER_CASE.search(before[before.rfind("\n") + 1 :]))


def _goes_on_as_leaflet(text: str, end: int) -> bool:
    """Whether the word is followed, on its line or the next with text, by the leaflet's words."""
    stop = text.find("\n", end)
    rest = text[end:] if stop < 0 else text[end:stop]
    if not rest.strip():
        rest = text[stop:].lstrip().split("\n", 1)[0] if stop >= 0 else ""
    return bool(_LEAFLET_GOES_ON.match(rest.lstrip()))


def _edits(word: str, target: str) -> int:
    """How many single-letter changes turn *word* into *target*."""
    previous = list(range(len(target) + 1))
    for i, a in enumerate(word, start=1):
        current = [i]
        for j, b in enumerate(target, start=1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a != b))
            )
        previous = current
    return previous[-1]


def _sections_found(text: str) -> int:
    """How many of the sixteen sections the parser finds in *text*."""
    return sum(
        1
        for section, body in split_sections(text).items()
        if isinstance(section, Section) and body.strip()
    )


def _kind(text: str, *, title_line: bool, sections: int) -> DocumentKind:
    # The title over none of the sixteen sections is a cover (SDB-66).
    if title_line and sections:
        return DocumentKind.SAFETY_DATA_SHEET
    laid_out = sections >= SECTIONS_OF_A_SHEET
    english = (
        len({int(n) for n in _ENGLISH_HEADING.findall(text)}) >= SECTIONS_OF_A_SHEET
    )
    if laid_out and not english:
        return DocumentKind.SAFETY_INFORMATION
    numbered = {int(n) for n in _FIRST_SUBSECTION.findall(text) if 1 <= int(n) <= 15}
    if laid_out or len(numbered) >= NUMBERED_SECTIONS_OF_A_SHEET:
        return DocumentKind.FOREIGN_SAFETY_DATA_SHEET
    return DocumentKind.DOCUMENT


def _find_keywords(text: str, keywords: Iterable[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]
