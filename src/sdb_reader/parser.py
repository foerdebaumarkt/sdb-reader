"""Parse normalized SDS text into structured data."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from itertools import pairwise

import structlog

from .extraction import ExtractionResult
from .label_blocks import SMALL_PACKAGE_HEADING
from .line_breaks import join_broken_words
from .messages import Message
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
from .statements import (
    OLD_REQUEST_SENTENCE,
    STATEMENT_LINE,
    base_code,
    canonical_text,
    codes_from_wording,
    codes_without_wording,
    euh_statements_by_wording,
    first_word_of,
    holds_a_wording_of,
    holds_official_form,
    interleaves_wording,
    lettered_code,
    open_end,
    precautionary_by_variants,
    statement_code,
    statement_codes,
    variant_wordings_in_print_order,
    with_effects_joined,
    worded_codes,
    wording_bounds,
    wordings_apart,
    wordings_in_print_order,
)

logger = structlog.stdlib.get_logger(__name__)

# Three of the parser's messages are what compliance.py judges by: a label
# stating that nobody determined the classification, an EUH wording standing
# outside the label (SDB-28), and a section 2 that classifies by the rules
# before CLP (SDB-73).
LABEL_UNDETERMINED = "label-undetermined"
LABEL_LINE_UNASSIGNED = "label-line-unassigned"
EUH_WORDING_OUTSIDE_LABEL = "euh-wording-outside-label"
CLASSIFIED_BEFORE_CLP = "classified-before-clp"
# No block "2.2 Kennzeichnungselemente" was found in section 2 (SDB-4).
NO_LABEL_SECTION = "no-label-section"
# The label block follows the directives before CLP (SDB-170).
LABEL_BEFORE_CLP = "label-before-clp"
STATEMENT_TOO_LONG = "statement-too-long"
# How many lines a statement of the hint texts spans at most (SDB-168): the
# longest a sheet of the measured collection prints has 37.
MAX_STATEMENT_LINES = 100

SECTION_BY_NUMBER: dict[int, Section] = {
    1: Section.IDENTIFICATION,
    2: Section.HAZARDS,
    3: Section.COMPOSITION,
    4: Section.FIRST_AID,
    5: Section.FIRE_FIGHTING,
    6: Section.ACCIDENTAL_RELEASE,
    7: Section.HANDLING_STORAGE,
    8: Section.EXPOSURE_PPE,
    9: Section.PHYSICAL_CHEMICAL,
    10: Section.STABILITY_REACTIVITY,
    11: Section.TOXICOLOGY,
    12: Section.ECOLOGY,
    13: Section.DISPOSAL,
    14: Section.TRANSPORT,
    15: Section.REGULATORY,
    16: Section.OTHER,
}

# Pattern handles OCR spacing issues within "ABSCHNITT" (e.g., "ABSC HNITT 1")
#
# "SECTION" is accepted beside it because sheets are not reliably monolingual.
# Four sheets in the corpus head every section "ABSCHNITT n" and section 2
# alone "SECTION 2: Hazards identification" -- a translation memory that lost
# one string. LABEL_SECTION_END_PATTERN already reads "SECTION 3" as a boundary,
# so the two spellings were half-equivalent here already.
#
# The leading zero is the same kind of variation: "02 MÖGLICHE GEFAHREN".
#
# Anchored at the start of the line, which is what separates a heading from a
# cross-reference. "Der Wortlaut der angeführten Gefahrenhinweise ist dem
# Abschnitt 16 zu entnehmen." sits in the middle of section 2 on 152 sheets and
# used to open section 16 right there, taking the rest of section 2 with it --
# including 2.2 Kennzeichnungselemente, which is where the label is.
#
# What may precede the word is any short run of non-word characters. Counted
# over the corpus, a heading is preceded by nothing (13629), "!" (161), "("
# (39) or "* " (20); a cross-reference is preceded by a word -- "Siehe " (660),
# "siehe " (42), "in ", "unter ". So the rule is punctuation yes, letters no.
# Enumerating the punctuation instead was tried and cost 96 sheets their
# section 1, all of them headed "!ABSCHNITT 1:" -- invisible in a label
# measurement, because find_label_section reads the raw text.
#
# A sheet that marks its changed sections prints the mark and the number in
# front of the word: "* 1 Abschnitt 1: Bezeichnung des Stoffs …".
SECTION_HEADER_PATTERN = re.compile(
    r"^\W{0,6}(?:\d{1,2}\W{1,3})?"
    r"(?:a\s*b\s*s\s*c\s*h\s*n\s*i\s*t\s*t|s\s*e\s*c\s*t\s*i\s*o\s*n)"
    r"\s+0?(\d{1,2})\b",
    re.IGNORECASE,
)

# The sixteen section titles are fixed by REACH Annex II, but the way suppliers
# write the heading is not. Most use "ABSCHNITT 2: Mögliche Gefahren", which
# SECTION_HEADER_PATTERN reads. A sizeable minority number the sections plainly
# instead -- "2. Mögliche Gefahren", or "2 Mögliche Gefahren" without the dot --
# and those sheets have no heading this parser could see at all.
#
# The consequence was not merely a missing section. With no heading recognised,
# the first thing that did match was whatever cross-reference in the body prose
# mentioned an "Abschnitt" ("Persönliche Schutzausrüstung siehe unter Abschnitt
# 8."), so the rest of the document was filed under that number. Section 2 stayed
# empty on 81 sheets in the corpus.
#
# The number alone cannot identify a heading: numbered lists inside sections 1, 8
# and 16 are written exactly the same way, and keying on the number alone moved
# content out of 43 sections that were previously correct. The title has to agree
# with the number. One distinctive word per section is enough -- suppliers vary
# the wording around it ("Mögliche Gefahren", "MÖGLICHE GEFAHREN", "Gefahren und
# Einstufung") but not the word itself.
#
# Case is deliberately not a criterion. All-caps headings are as valid as any
# other, here and in every other heading pattern in this module.
SECTION_TITLE_PATTERNS: dict[int, re.Pattern[str]] = {
    number: re.compile(keyword, re.IGNORECASE)
    for number, keyword in {
        1: r"bezeichnung|stoff|gemisch",
        2: r"gefahren",
        3: r"zusammensetzung|bestandteil",
        4: r"erste[-\s]?hilfe",
        5: r"brandbek",
        6: r"unbeabsichtigt|freisetzung",
        7: r"handhabung|lagerung",
        8: r"begrenzung|exposition|schutzaus",
        9: r"physikalisch|chemische",
        10: r"stabilit|reaktivit",
        11: r"toxikolog",
        12: r"umweltbezogen|ökolog",
        13: r"entsorgung",
        14: r"transport",
        15: r"rechtsvorschrift|vorschrift",
        16: r"sonstige|weitere",
    }.items()
}
# A heading whose number and title landed on separate lines. Two sheets here
# read "2\nMögliche Gefahren", which no single-line pattern can see. Merging the
# pair is safe only because the title still has to agree with the number
# afterwards -- a bare "2" is otherwise one of the commonest lines in a data
# sheet, sitting in every table.
BARE_SECTION_NUMBER_PATTERN = re.compile(r"^0?(1[0-6]|[1-9])\s*\.?\s*$")
# A sheet whose section 2 heading is missing while its subsections are all
# there: "2.1 Einstufung", "2.2 Kennzeichnungselemente", "2.3 Sonstige
# Gefahren". Without this the label sits in whatever section preceded it.
# Only consulted while section 2 has not been seen, so a later cross-reference
# cannot pull the rest of a document into it.
#
# The same holds for sections 1 and 3, whose headings a sheet read by OCR
# often loses (one supplier prints them white on a dark bar): "1.1
# Produktidentifikator" opens section 1 and "3.2 Gemische" section 3, which
# is where section 2 ends.
SUBSECTION_PATTERN = re.compile(
    r"^[-·•\s]*([123])\s*\.\s*([1-4])\b\.?\s*(.{3,79}?)\s*$"
)
SUBSECTION_TITLES: dict[int, re.Pattern[str]] = {
    1: re.compile(
        r"produktidentifikator|identifizierte\s+verwendung|einzelheiten\s+zum\s+lieferanten",
        re.IGNORECASE,
    ),
    2: re.compile(r"einstufung|kennzeichnung|sonstige\s+gefahren", re.IGNORECASE),
    3: re.compile(r"^(?:stoffe|gemische)\b", re.IGNORECASE),
}
# The dot after the number is optional: "3 Zusammensetzung" is as common as
# "3. Zusammensetzung", and both are headings. Section numbers stop at 16.
# A mark for a changed section may stand in front (SDB-1): "* 1 Bezeichnung
# des …", "! 2. Mögliche Gefahren". A colon may stand for the dot (SDB-1):
# "3: Zusammensetzung / Angaben zu den Bestandteilen".
NUMBERED_SECTION_PATTERN = re.compile(
    r"^(?:[*!]\s*)?0?(1[0-6]|[1-9])\s*[.:]?\s+(\S.{3,79}?)\s*$"
)
# Suppliers state the document's own version several ways: "Version 8.2",
# "Version: 1.1", "Versionsnummer 1", "Nummer der Fassung: 1.0" and
# "Ausgabenr. : 15.01" all appear in the corpus, so the label is matched
# loosely and the separator may be a colon. Digits must follow immediately:
# that is what keeps "Fassung: GHS 1.0" (the GHS revision, not this document's
# version) and bare prose like "Fassung." out.
# A leading "V" and dash separators are accepted too, for "Versionsnummer:
# V01-02" -- the same supplier writes "2.01" elsewhere, so V01-02 is 01.02.
VERSION_PATTERN = re.compile(
    r"\b(?:Version(?:snummer)?|Nummer\s+der\s+Fassung|Fassung|Ausgabenr\.?)"
    r"\s*:?\s*V?(\d+(?:[-.,]\d+)*)",
    re.IGNORECASE | re.MULTILINE,
)
# Sheets name the version they supersede right next to their own, as in
# "Versionsnummer: 2.01 (ersetzt Version 1.03)". Both then repeat once per page,
# so counting occurrences alone cannot separate them.
# Word boundaries matter here: without the leading \b, the "alte" branch fires
# inside "enthalten" and discards a perfectly good version.
SUPERSEDED_MARKER = re.compile(
    r"\b(?:ersetzt|ersetzen|vorherig\w*|vorgänger\w*|alte)\b\s*(?:\w+\s+)?$",
    re.IGNORECASE,
)
_DATE_AS_VERSION = re.compile(r"\d{1,2}[-.,]\d{1,2}[-.,](?:19|20)\d{2}")
# "Überarbeitet am / Version: 31.05.2012 / 0007": one label for two values,
# the day and behind it the number. The line below it, "Ersetzt Fassung vom /
# Version: 19.01.2011 / 0006", is built alike and names the version before.
VERSION_BEHIND_DATE_PATTERN = re.compile(
    r"^[^\S\n]*Überarbeitet[^\S\n]+am[^\S\n]*/[^\S\n]*Version[^\S\n]*:[^\S\n]*"
    r"\d{1,2}\.\d{1,2}\.\d{4}[^\S\n]*/[^\S\n]*V?(\d+(?:[-.,]\d+)*)",
    re.IGNORECASE | re.MULTILINE,
)
# Fallback used only when no version label is present: some sheets number their
# revisions instead, as "Revisionsnummer 1", "Revisions-Nr.: 1,2", "Rev. Nr. 4"
# or plain "REV. 1". The "Nr." branch is tried before the bare one so
# "Rev. Nr. 4" yields 4 rather than failing on the "Nr".
REVISION_NUMBER_PATTERN = re.compile(
    r"\b(?:Revisions?nummer|Rev(?:isions?)?\s*[-.]?\s*Nr\.?|Revision(?=[^\S\n]*:)|Rev\.?)"
    r"\s*:?\s*V?(\d+(?:[-.,]\d+)*)",
    re.IGNORECASE | re.MULTILINE,
)

# "23-Nov-2023" is day-first like "23.11.2023", just written with dashes and a
# month name -- not a month-first US date, so both forms parse the same way.
# Keyed by the first three letters, so both the abbreviation and the spelled-out
# month resolve: "Nov"/"November", "März"/"Mrz", "Juli"/"Jul".
_MONTH_NAMES: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "mär": 3,
    "mae": 3,
    "mrz": 3,
    "apr": 4,
    "mai": 5,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "okt": 10,
    "oct": 10,
    "nov": 11,
    "dez": 12,
    "dec": 12,
}
# The separators may stand between spaces: "15 / 6 / 2010" (SDB-57).
_DATE_SEPARATOR = r"(?:[^\S\n]?[.\-/]\s*|\s)"
_DATE_FRAGMENT = (
    rf"(\d{{1,2}}){_DATE_SEPARATOR}([A-Za-zÄÖÜäöüß]{{3,9}}|\d{{1,2}})"
    rf"{_DATE_SEPARATOR}(\d{{4}})"
)
# "Überarbeitet am: 2024-08-26": the same date, year first. Only behind a label,
# and only with its dashes: a CAS number or an article number is built alike.
# A weekday may stand in front: "Mittwoch, 13. Mai 2015" (SDB-57).
_WEEKDAY = r"(?:(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag),?\s+)?"
_DATED = rf"(?:{_WEEKDAY}{_DATE_FRAGMENT}|(?<!\d)(\d{{4}})-(\d{{2}})-(\d{{2}})(?!\d))"
# A page marker may sit between a date's label and its value. Suppliers put both
# in the page footer, and flattening the layout interleaves them:
#
#     Ausgabedatum/
#     Überarbeitungsdatum
#     :
#     Seite: 1/13
#     10-2-2021
#
# Only a page marker is tolerated, nothing else. Allowing any 45 characters of
# filler instead was measured on the corpus: it bound labels to unrelated
# dates and moved five sheets from 2013 to 2015.
_PAGE_MARKER = r"(?:\s*Seite\s*:?\s*\d{1,3}\s*(?:/|von)\s*\d{1,3})?"

# Revision date: "Überarbeitet am: 16.11.2020", "Revisionsdatum 02.03.2021",
# "Änderungsdatum: 11.11.2020", "Version vom: 04-Jan-2024", "REV. 1 vom
# 14.11.2019". A bare "vom" is too common to anchor on, so it only counts when
# a revision or version number precedes it.
#
# "Bearbeitungsdatum", "Fassung vom" and "Stand:" are the same statement in
# other suppliers' words, and together they carry 75 of the sheets this parser
# used to leave undated. "Stand" needs its colon: on its own the word is far too
# common in German prose to anchor a date on.
#
# "Druckdatum" is deliberately absent. It records when the PDF was rendered, not
# when the document was revised, and the two can be years apart -- one sheet here
# reads "überarbeitet am: 30.04.2012 ... Druckdatum: 13.07.2018".
# The optional second word absorbs a break inside the label itself: one sheet
# here reads "Überarbeitungsd\natum:\n01.10.2021", and the layout reader joins
# the two lines of the label to "Überarbeitungsd atum: 01.10.2021". It matches
# letters only -- an earlier draft wrote \w, which also matches digits, so it ate
# the first digit of the day and turned 25.08.2020 into 05.08.2020 on 37 sheets.
# Lower-case letters only, and only before the label's colon: a word that
# merely follows ("Überarbeitet Druckdatum: 13.07.2018", "Überarbeitungsdatum
# ersetzt 12.03.2019") is another label's, not the rest of this one.
#
# A version carries its date behind it, in brackets or behind a dash: "Nummer
# der Fassung: GHS 8.0 (10.06.2024)", "Version 2.2 (18/07/2017)", "Revision :
# Nr. 2 (22/11/2019)", "Rev. 14 – 19/12/2024". The version a sheet replaces
# does too ("Ersetzt Fassung: GHS 7 (29.01.2024)"), and that date is not this
# sheet's.
# Optional parts carry their own blanks behind them ("(?::\s*)?"), so that a
# run of blanks can be read only one way (no slow search on long blank runs).
REVISION_DATE_PATTERN = re.compile(
    # "Überarbei tung": the word broken at the line's end (SDB-57).
    r"(?:überarbei[^\S\n]?t[a-zäöüß]*(?:\s+(?-i:[a-zäöüß]{2,})(?=\s*:))?(?:\s+am)?"
    r"|revisions?datum|änderungsdatum|bearbeitungsdatum|überprüfung"
    r"|(?<!ersetzt )fassung\s+vom|stand\s*:|sicherheitsdatenblatt\s+vom"
    r"|(?:version|rev\.?)\s*(?:nr\.?\s*)?(?::\s*)?\d+(?:[.,]\d+)*\s*vom"
    r"|(?<!ersetzt )(?:version|fassung|revision|rev\.?)\s*(?::\s*)?(?:nr\.?\s*)?(?:GHS\s*)?"
    r"\d+(?:[.,]\d+)*\.?\s*[(–—-]"
    # "Durchsicht Nr. 3" / "vom 11/10/2023" (SDB-57).
    r"|durchsicht\s+nr\.?\s*\d+\s+vom"
    r"|version\s+vom)"
    rf"\s*:?{_PAGE_MARKER}\s*{_DATED}",
    re.IGNORECASE | re.MULTILINE,
)
# "20/09/2021 (Version: 9.4)": the date first, its version behind it. Also
# behind a comma, "20/11/2012, version 2." (SDB-57).
REVISION_DATE_BEFORE_VERSION_PATTERN = re.compile(
    rf"{_DATED}(?:\s*\(Version\s*:|,[^\S\n]*Version[^\S\n]+\d)", re.IGNORECASE
)
# "23.04.2024 (Überarbeitungsdatum)": the date first, its label behind it in
# brackets, in the footer of every page (SDB-57).
REVISION_DATE_BEFORE_LABEL_PATTERN = re.compile(
    rf"{_DATED}[^\S\n]*\((?:Überarbeitungsdatum|Revisionsdatum|überarbeitet\s+am)\)",
    re.IGNORECASE,
)
# A version's date is this sheet's only where the version is: "ersetzt Version
# 003 vom 12.03.2019", "(ungültig wird Version 1.3 vom 04.03.2022)", "Geänderte
# Daten in der Version 11 gegenüber der Version 10 vom 06.03.2023", "Ersetzt die
# vorherige Version vom 27.01.2017" and "Vorversion vom 31.05.2019" name the
# version before it (SDB-57). Mostly that cost nothing, the sheet's own date
# being the newer one; it decided where the sheet's own date was not read (a
# two-digit year, a date of issue only) or was the older of the two.
_OTHER_VERSION_BEFORE = re.compile(
    r"(?:\b(?:ersetz\w*|ersatz[^\S\n]+für|ungültig[^\S\n]+wird|gegenüber)"
    r"\s*:?\s*(?:(?:die|der|das|den)\s+)?(?:\w+e[nrs]?\s+)?|\bvor)$",
    re.IGNORECASE,
)
_VERSION_LABEL_START = re.compile(r"version|fassung|revision|rev\b", re.IGNORECASE)
# The day the version in hand was made is the day of its revision (SDB-57):
# "Aktuelle Version: 2.0.1, erstellt am: 20.03.2020", or the version on one
# line and "Erstellt am 30.03.2023" on the next. The line begins with the
# version, so "Ersetzte Version: 2.0.0, erstellt am: 04.06.2019" below it is
# not one.
VERSION_CREATED_PATTERN = re.compile(
    r"^[^\S\n]*(?:Aktuelle[^\S\n]+)?Version[^\S\n]*(?::[^\S\n]*)?V?\d"
    # The rest of the version's line up to a blank or a comma before
    # "erstellt", or the whole line and then the next: one way to read each
    # character, so that a long line cannot make the search slow.
    r"(?:[^\n]*?(?<=[^\S\n]|,)|[^\n]*\n[^\S\n]*)"
    rf"erstellt[^\S\n]+am[^\S\n]*:?[^\S\n]*{_DATED}",
    re.IGNORECASE | re.MULTILINE,
)
# The same with the day above its version: "Erstellt am 24.07.2013" /
# "Version 1.2".
VERSION_CREATED_ABOVE_PATTERN = re.compile(
    rf"^[^\S\n]*erstellt[^\S\n]+am[^\S\n]*:?[^\S\n]*{_DATED}[^\S\n]*\n"
    r"[^\S\n]*Version[^\S\n]*:?[^\S\n]*V?\d",
    re.IGNORECASE | re.MULTILINE,
)
# "überarbeitet am: 30.04.2012 + 10.06.2016": revised twice, both days behind
# the one label (SDB-57).
_FURTHER_DATE = re.compile(rf"[^\S\n]*(?:\+|und)[^\S\n]*{_DATED}", re.IGNORECASE)
# SAP prints an older header as a grid of labels over a row of values, and the
# reader gives the labels on one line: "Überarbeitet am: Druckdatum Datum der
# letzten Ausgabe: 13.06.2017", then "3.4", "27.02.2018", "28.11.2018". The
# first date below is the revision's, the second the day it was printed.
REVISION_DATE_GRID_PATTERN = re.compile(
    r"überarbeitet\s+am:[^\S\n]*Druckdatum[^\n]*\n"
    rf"(?:\s*\d+(?:[.,]\d+)*[^\S\n]*\n)?\s*{_DATED}",
    re.IGNORECASE,
)
# Issue date: "Ausstellungsdatum: 11.07.2013", "Ausgabedatum: 17.08.2021",
# "Datum der Erstellung: 29.05.2020".
# "Ausgabe:" counts only at the start of its line: "Datum der letzten Ausgabe:"
# names the sheet before this one.
ISSUE_DATE_PATTERN = re.compile(
    # "Ausgabedatum/: 08/31/2020" with "Überarbeitungsdatum" a line lower: the
    # label split around its value by the layout (SDB-201).
    r"(?:ausstellungsdatum|ausgabedatum/?|erstellungsdatum|erstelldatum"
    r"|erstellt(?:\s+am|\s*:)"
    # "Erste Fassung: 15.12.2025" (SDB-57).
    r"|erste\s+fassung|erstfassung"
    r"|datum\s+der\s+erstellung|datum\s+ausgestellt|(?<![a-zäöüß])erstellung"
    # "Datum der Ausstellung: 5/05/2022", "Ausgestellt am" (SDB-57).
    r"|datum\s+der\s+ausstellung|ausgestellt\s+am"
    # "Datum der Ausgabe: 06.01.2021" (SDB-57); not "Datum der letzten Ausgabe".
    r"|datum\s+der\s+ausgabe"
    r"|^[^\S\n]*ausgabe)"
    rf"\s*:?{_PAGE_MARKER}\s*{_DATED}",
    re.IGNORECASE | re.MULTILINE,
)
# "Tritt in Kraft ab: 23.05.2022", "gültig ab: 18.07.2022". Neither is a
# revision date -- a sheet is revised on one day and takes effect on another,
# and one document here says 30/09/2021 and 01/10/2021 in that order. Ranking
# revisions on the wrong one of those would pick the wrong sheet.
#
# So this is consulted last, only for a document that states neither when it was
# revised nor when it was issued. For those 35 sheets it is the difference
# between a known date and none at all, and "in force since" is a sound floor
# for how old the document is.
EFFECTIVE_DATE_PATTERN = re.compile(
    r"(?:tritt\s+in\s+kraft(?:\s+ab)?|gültig\s+ab)"
    rf"\s*:?{_PAGE_MARKER}\s*{_DATED}",
    re.IGNORECASE | re.MULTILINE,
)
# "Datum: 16.05.2024" in a page's footer, "Stand 13.12.2014" under the title.
# Neither says what the date is of, so it stands last, behind every date that
# does, and only at the start of its line: "TRGS 900, Stand 29.01.2018" dates
# a list of limit values.
PLAIN_DATE_PATTERN = re.compile(
    rf"^[^\S\n]*(?:datum[^\S\n]*:|stand)[^\S\n]*{_DATED}",
    re.IGNORECASE | re.MULTILINE,
)
# "Überarbeitung 29.06.11". A two-digit year is ambiguous by construction, and
# widening _DATE_FRAGMENT to accept one everywhere would let version numbers and
# article numbers read as dates across the whole catalogue.
#
# So it gets its own pattern and the same standing as the effective date: last,
# and only for a document that has yielded nothing else. A guess that cannot
# displace a certainty costs nothing to try.
#
# (?!\d) is what keeps it off the front of a four-digit year -- without it,
# "29.06.2011" reads as the 29th of June 20.
#
# The century boundary is fixed at 90 rather than pegged to the current year, so
# the same document reads the same way next year: 90-99 is the 1990s, everything
# below is the 2000s. The oldest sheet in the corpus is from 1994.
_SHORT_YEAR_FRAGMENT = r"(\d{1,2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{2})(?!\d)"
SHORT_YEAR_DATE_PATTERN = re.compile(
    r"(?:überarbeit[a-zäöüß]*(?:\s+(?-i:[a-zäöüß]{2,})(?=\s*:))?(?:\s+am)?"
    r"|revisions?datum|änderungsdatum|bearbeitungsdatum|fassung\s+vom|stand\s*:"
    r"|ausstellungsdatum|ausgabedatum|erstellungsdatum|erstellt\s+am"
    r"|ausgestellt\s+am)"
    rf"\s*:?{_PAGE_MARKER}\s*{_SHORT_YEAR_FRAGMENT}",
    re.IGNORECASE | re.MULTILINE,
)
# Section 2.2 of an SDS carries the label: exactly the statements that appear on
# the product. Section 2.1 above it carries the classification, which lists more
# -- typically H400 next to H410, where only H410 is labelled. Reading the whole
# hazards section conflates the two, so the block is located on its own.
LABEL_SECTION_START_PATTERN = re.compile(
    r"2\s*\.\s*2\s*\.?\s*(?:Kennzeichnungselemente|Label\s+elements)"
    # A heading numbered 2.2 that begins with "Kennzeichnung" or "Etikett":
    # "2.2 Kennzeichnung nach GHS:", "2.2. Etiketteninhalt" (SDB-209); not the
    # "2.2. Verwendungsbedingungen …" of an exposure scenario in an annex.
    r"|^[ \t]*(?:[·•∙*][ \t]*)?(?<!\d)2[ \t]*\.[ \t]*2\.?[ \t]+(?:Kennzeichnung|Etikett)\w*",
    re.IGNORECASE | re.MULTILINE,
)
# The same heading without its number, for sheets written before the REACH
# restructuring: they number their sections 1 to 17 and put the label at
# "4. Kennzeichnungselemente".
#
# Dropping the number is safe on its own -- the heading is the first occurrence
# of the word, measured over 400 sheets, including the 49 that mention it twice
# (the second is a back-reference and comes later). It is only used where a real
# boundary follows; see find_label_section for why.
LABEL_HEADING_PATTERN = re.compile(
    # "GHS-Kennzeichnung" heads the label of sheets without a 2.2 (SDB-202).
    r"\b(?:Kennzeichnungselemente|Label\s+elements)\b|^[ \t]*GHS-Kennzeichnung\b",
    re.IGNORECASE | re.MULTILINE,
)
# Only a heading ends it. An unanchored "3.1" also matches inside a date such as
# "13.10.2024", which truncates the block before the codes it should contain.
#
# The last alternative ends the old layout, where the label is section 4 and
# section 5 follows. It wants a top-level number and a capitalised word, so
# "2.3." does not match it -- after "2." comes a digit, not a letter.
# The leading zero is not decoration. 248 sheets in the corpus number their
# sections "ABSCHNITT 01" through "ABSCHNITT 16", and without the optional zero
# the boundary is simply not found: the block then runs to LABEL_SECTION_MAX_CHARS
# and takes the ingredient table with it. Measured, that put thirteen sheets'
# raw-material classifications on the label -- one of them reporting H301, H310,
# H314, H330 and nine more from a sheet whose label says "Gefahrenpiktogramme
# entfällt, Signalwort entfällt".
#
# split_sections already reads "03" correctly, because it captures \d{1,2} and
# converts. Only this pattern spells the number out, and only here did it matter.
# Section 2.3 by its name, for sheets that number nothing. Some suppliers write
# the whole document as a bulleted list -- "· Kennzeichnungselemente",
# "· Sonstige Gefahren" -- and follow it with "3 Zusammensetzung" without a dot,
# so neither the numeric boundary nor the "ABSCHNITT 3" one matches. The label
# heading is then found and the block discarded for want of an end, which costs
# the whole label: three sheets here carry GHS05, GHS07, "Signalwort Gefahr" and
# H315, H318, H335 in a block nothing could close.
LABEL_SECTION_END_PATTERN = re.compile(
    r"(?m)^[ \t]*(?:[·•∙][ \t]*)?(?:2\s*\.\s*3\s*\.?\s|ABSCHNITT\s*0?3\b|SECTION\s*0?3\b"
    r"|[·•\-\s]*(?:Sonstige\s+Gefahren|Other\s+hazards)\b"
    r"|\d{1,2}\s*\.\s*[A-ZÄÖÜ][a-zäöüß])",
    re.IGNORECASE,
)
# The same boundaries with "Sonstige Gefahren" behind marks of its own line
# only; _label_section_ends adds the lines of marks above it that the pattern
# above takes in. Searched with the pattern above, every line of a long run of
# such lines was read again to the run's end.
_LABEL_SECTION_END_IN_LINE = re.compile(
    r"(?m)^[ \t]*(?:[·•∙][ \t]*)?(?:2\s*\.\s*3\s*\.?\s|ABSCHNITT\s*0?3\b|SECTION\s*0?3\b"
    r"|(?:[·•\-]|[^\S\n])*(?:Sonstige\s+Gefahren|Other\s+hazards)\b"
    r"|\d{1,2}\s*\.\s*[A-ZÄÖÜ][a-zäöüß])",
    re.IGNORECASE,
)
# A line of nothing but those marks, and the first such line, which may open
# with a bullet of its own.
_MARKS_LINE = re.compile(r"(?:[·•\-]|[^\S\n])*")
_BULLET_MARKS_LINE = re.compile(r"[ \t]*∙(?:[·•\-]|[^\S\n])*")
# The line a version number follows. Some sheets print "Version" in their
# running header with the number alone on the next line, and where that number
# is 2.3 it is the heading of section 2.3 to the pattern above. The header lands
# between two pages in the text, so a label running across a page break ended
# there -- before its pictograms, signal word and statements. Nine sheets in
# the corpus are cut there; see below for what they get back.
VERSION_KEY_PATTERN = re.compile(r"(?:Version|Versionsnummer)\s*:?", re.IGNORECASE)
# Cap for documents whose section 2.3 heading never matches, so a failed
# boundary yields the label block rather than the rest of the sheet.
LABEL_SECTION_MAX_CHARS = 3500

# A classification entry, not a label element: "Skin Corr. 1, H314",
# "Aquatic Chronic 1, H410", "Carc. 2 - H351". Class, category, code.
#
# These belong to section 2.1 and are not what the label says. They reached the
# label block in the file's order, which flattens a two-column layout into one
# stream: 69 sheets here. Read in print order (SDB-42) two still have one there,
# and OCR text keeps its own order (SDB-46). Article 26 is why it matters:
# a label carrying H410 may omit H400, and one carrying H314 may omit H318, so
# reading the classification puts statements on a product that its label
# deliberately leaves off.
#
# Only the class's last word is matched ("Corr. 1, H314" of "Skin Corr. 1,
# H314"): the words before it hold no code, so dropping them changed nothing
# the label's codes are read from, and taking them made a long run of
# capitalised words cost a search from every word in it.
CLASSIFICATION_ENTRY = re.compile(
    r"\b[A-Z][A-Za-z]*\.?\s+\d[A-F]?\s*[,\-–]\s*H\d{3}(?!\d)"
)

HAZARD_CODE_PATTERN = re.compile(r"\bH\d{3}(?!\d)")
# A label's H-codes as printed, with the letters of an effect behind H360 and
# H361 ("H360FD", "H361d"), which belong to the code (SDB-155).
LABEL_HAZARD_CODE = re.compile(r"\bH(?:36[01][A-Za-z]{1,2}(?![^\W\d_])|\d{3})(?!\d)")
PRECAUTION_CODE_PATTERN = re.compile(r"\bP\d{3}(?!\d)")
SUPPLEMENTAL_CODE_PATTERN = re.compile(r"\bEUH\d{3}\b", re.IGNORECASE)
# A pictogram's code, also as text recognition misreads it with more zeros or
# a space ("GHS007", "GHS 07"): there are only GHS01 to GHS09 (SDB-203). Not
# the revision of the GHS in "GHS 8.0".
PICTOGRAM_PATTERN = re.compile(r"\bGHS(?:[ \t]?0+)?([1-9])(?![\d.,]?\d)", re.IGNORECASE)
# Two bugs kept this from ever matching German text: no IGNORECASE against a
# lowercase "signal", and a capture that took whatever word came next. Every
# signal word of the stored readings therefore came from the H-code derivation, not from
# the sheet -- including the two the derivation had wrong.
#
# The trailing \b is what stops "Gefahr" from matching inside
# "Gefahrenhinweise", which is the row label sitting directly above the value in
# the two-column layouts these sheets use.
# Case-insensitive because 140 sheets in the corpus set the value in caps --
# 97 "GEFAHR", 43 "ACHTUNG" -- and a case-sensitive read sent every one of them
# to the derivation instead. The \b anchors keep that safe: "Gefahrenhinweise"
# still fails the trailing boundary whatever its case.
# The lookahead is what keeps EUH211 and EUH212 out. Both phrases are fixed by
# the regulation and both open with the word itself -- "Achtung! Beim Spruehen
# koennen gefaehrliche lungengaengige Troepfchen entstehen." -- so a bare word
# search read 53 sheets' supplemental phrase as their signal word. CLP prints
# the signal word without punctuation, which makes the "!" diagnostic: it never
# belongs to the label element, only to the sentence that quotes it.
SIGNAL_WORD_PATTERN = re.compile(r"\b(Gefahr|Achtung)\b(?!\s*!)", re.IGNORECASE)
# The word behind its own label: "Signalwort: Achtung" (SDB-176). Behind its
# label the word may carry an exclamation mark that ends its line ("Signalwort:
# Achtung!", SDB-176): EUH211 and EUH212 go on after theirs on the same line.
_SIGNAL_WORD_NAMED = re.compile(
    r"\bSignalwort[^\S\n]*[:\-–]?\s*(Gefahr|Achtung)\b(?![^\S\n]*![^\S\n]*\S)",
    re.IGNORECASE,
)

# How a sheet classifies under Directive 67/548/EEC or 1999/45/EC, the rules
# before CLP (SDB-73): an R phrase with its number, or a hazard symbol with its
# designation. A sheet that only names the directives, or prints "R-Sätze:
# keine", states no hazard and is not meant.
#
# A combination is unmistakable: "R20/21/22", "R 36/38".
_R_COMBINATION = re.compile(r"(?<![\w/])R[^\S\n]?\d{1,2}(?:/\d{1,2})+(?![\w/])")
# A single number is not -- "ABCDE R 1" is a product, "R134a" a refrigerant --
# so it counts only with two digits and where section 2 names the old rules.
_R_SINGLE = re.compile(r"(?<![\w/])R[^\S\n]?\d{2}(?![\w/.,])")
_OLD_RULES_NAMED = re.compile(
    r"67/548|(?:19)?99/45|\bR[^\S\n]?-?[^\S\n]?S[äa]tze", re.IGNORECASE
)
# Or each on a line of its own, its sentence below: "R11" / "Leichtentzündlich" /
# "R19" / "Kann explosionsfähige Peroxide bilden". One such line may be part of
# a product's name, two are not.
_R_ALONE = re.compile(r"(?m)^[^\S\n]*R[^\S\n]?\d{2}[^\S\n]*$")
# Under the heading the numbers stand alone: "R-Sätze:" / "11" / "Leichtentzündlich."
_R_PHRASES_LISTED = re.compile(
    r"\bR[^\S\n]?-?[^\S\n]?S[äa]tze[^\S\n]*:*\s*\d{1,2}(?:/\d{1,2})*(?![\w.,])",
    re.IGNORECASE,
)
# "Xn; Gesundheitsschädlich", "Xi - Reizend", "F Leichtentzündlich".
_HAZARD_SYMBOL = re.compile(
    r"(?<![\w/])(?:Xn|Xi|T\+?|F\+?|C|N|O|E)[^\S\n]*[;,:\u2013\u2014-]?[^\S\n]*"
    r"(?:Gesundheitsschädlich|Reizend|Sensibilisierend|Sehr[^\S\n]+giftig|Giftig"
    r"|Leichtentzündlich|Hochentzündlich|Ätzend|Umweltgefährlich|Brandfördernd"
    r"|Explosionsgefährlich)\b"
)
# Or the designation alone, as a sentence of its own: "Hochentzündlich. Reizend.",
# "Für die Umwelt :" / "Umweltgefährlich" (SDB-120).
_HAZARD_DESIGNATION = re.compile(
    r"(?m)(?:^|[.:;][^\S\n]+)(?:Hochentzündlich|Leichtentzündlich|Umweltgefährlich"
    r"|Gesundheitsschädlich|Reizend|Ätzend|Brandfördernd|Sehr[^\S\n]+giftig|Giftig)"
    r"[^\S\n]*(?:\.|$)"
)
# A sheet of the years between the two systems prints both; with a CLP code in
# section 2 it has a label to read: "R 10 Entzündlich." beside "H 226 …".
_CLP_CODE_PRINTED = re.compile(r"\b(?:[HP][^\S\n]?\d{3}|EUH[^\S\n]?\d{3})\b")


# A label under the directives before CLP names them as its basis: "Kennzeichnung
# nach EWG-Richtlinien", "nach EG-Richtlinien/GefStoffV nicht
# kennzeichnungspflichtig", "gemäß 1999/45/EG".
_OLD_RULES_LABEL = re.compile(
    r"\b(?:EWG|EG)-Richtlinien\b|67/548|(?:19)?99/45|\bGefStoffV\b", re.IGNORECASE
)


def label_before_clp(label: str) -> bool:
    """Whether a label block follows the directives before CLP (SDB-170).

    It prints no H, P or EUH code, and either names the old directives as its
    basis or labels with R phrases or a hazard symbol as SDB-73 reads them.

    >>> label_before_clp("Kennzeichnung nach EWG-Richtlinien:\\nnicht kennzeichnungspflichtig.")
    True
    >>> label_before_clp("Kennzeichnung nach EWG-Richtlinien\\nH315 Verursacht Hautreizungen.")
    False
    >>> label_before_clp("Signalwort: Achtung")
    False
    """
    if _CLP_CODE_PRINTED.search(label):
        return False
    return bool(_OLD_RULES_LABEL.search(label)) or old_classification(label) is not None


def old_classification(hazards_section: str) -> str | None:
    """What section 2 classifies with under the rules before CLP, else None (SDB-73)."""
    if _CLP_CODE_PRINTED.search(hazards_section):
        return None
    patterns = [_R_COMBINATION, _R_PHRASES_LISTED, _HAZARD_SYMBOL]
    if _OLD_RULES_NAMED.search(hazards_section):
        patterns.append(_R_SINGLE)
    for pattern in patterns:
        match = pattern.search(hazards_section)
        if match:
            return " ".join(match.group(0).split())
    alone = _R_ALONE.findall(hazards_section)
    if len({" ".join(code.split()) for code in alone}) >= 2:
        return " ".join(alone[0].split())
    designation = _HAZARD_DESIGNATION.search(hazards_section)
    if designation:
        return designation.group(0).strip(" .:;\n")
    return None


# What section 2 says about the classification (SDB-75). REACH Article 31(1)
# asks whether the product meets the criteria for classification, and this is
# where a sheet answers it; the label only follows from it. The part read runs
# from the heading "Einstufung des Stoffs oder Gemischs" -- not from its number,
# which sheets leave out or write "2,1" -- to the label's heading.
_CLASSIFICATION_HEADING = re.compile(
    r"Einstufung\s+des\s+Stoff(?:e?s)?\s+oder\s+(?:des\s+)?Gemische?s?"
    r"|Classification\s+of\s+the\s+substance\s+or\s+mixture",
    re.IGNORECASE,
)
# A hazard class is told by its H code or by the abbreviation CLP gives it with
# its category ("Skin Corr. 1B", "Aquatic Chronic 3"), which some sheets print
# without the code -- also in German ("Entz. Fl. 2", "Augenreiz. 2").
_HAZARD_CLASS_CODE = re.compile(r"\bH[2-4]\d{2}[A-Za-z]{0,2}\b")
_HAZARD_CLASS_NAME = re.compile(
    r"\b(?:Expl\.|Flam\.\s?(?:Gas|Liq\.|Sol\.)|Aerosol|Ox\.\s?(?:Gas|Liq\.|Sol\.)"
    r"|Press\.\s?Gas|Self-react\.|Pyr\.\s?(?:Liq\.|Sol\.)|Self-heat\.|Water-react\."
    r"|Org\.\s?Perox\.|Met\.\s?Corr\.|Acute\s?Tox\.|Skin\s?Corr\.|Skin\s?Irrit\."
    r"|Eye\s?Dam\.|Eye\s?Irrit\.|Resp\.\s?Sens\.|Skin\s?Sens\.|Muta\.|Carc\.|Repr\."
    r"|STOT\s?[SR]E|Asp\.\s?Tox\.|Aquatic\s?(?:Acute|Chronic)"
    r"|Entz\.\s?Fl\.|Augenreiz\.|Augenschäd\.|Hautreiz\.|Hautätz\.|Akut\s?Tox\.)"
    # "Eye Irrit. 2", and "Eye Irrit. Gefahrenkategorie 2" (SDB-81).
    r"\s?(?:(?:Gefahren)?[Kk]ategorie\s)?[1-4][A-C]?\b"
)
# Or the class is written out, as an entry of its own with its category (SDB-80):
# "Reizwirkung auf die Haut, Kategorie 2", "Korrosiv gegenüber Metallen
# (Kategorie 1)". The names differ from one supplier's software to the next, the
# shape does not. The bare word "Kategorie" is not enough: sheets use it of
# their ingredients too ("enthält Stoffe, die als Akut Toxisch
# (Gefahrenkategorie 4) eingestuft sind"), which the sentence around it tells.
_HAZARD_CLASS_IN_WORDS = re.compile(
    r"(?m)(?:^|[:.]\s)[^\S\n]*[A-ZÄÖÜ][^.:\n]{3,70}?[^\S\n]*[,(][^\S\n]*"
    r"(?:Gefahren)?[Kk]ategorie[^\S\n]+[1-4][A-C]?\b"
    # A table sets the category in a cell of its own (SDB-81): "Aerosol" /
    # "Kategorie 1", "Schwere Augenschädigung/-reizung," / "Kategorie 1", and
    # "… auf die Haut, Kategorie" / "2".
    r"|^[^\S\n]*(?:Gefahren)?Kategorie[^\S\n]+[1-4][A-C]?[^\S\n]*$"
    r"|\b(?:Gefahren)?Kategorie[^\S\n]*\n[^\S\n]*[1-4][A-C]?[^\S\n]*$"
    # Or the table drops the word (SDB-80): a line that is the name, a comma
    # and the category, "Ätz-/Reizwirkung auf die Haut, 2".
    r"|^[^\S\n]*[A-ZÄÖÜ][^.:\n]{3,70}?,[^\S\n]*[1-4][A-C]?[^\S\n]*$"
    # A list under "Gefahrenkategorien:" names each class with an abbreviation
    # of the supplier's software: "Entzündbare Feststoffe: Entz. Festst. 1".
    r"|^[^\S\n]*Gefahrenkategorien:[^\S\n]*\n[^\n:]{3,80}:[^\S\n]*[^\n]{2,30}?"
    r"[^\S\n][1-4][A-C]?[^\S\n]*$"
)
# Or the sheet says so in a sentence: "Das Gemisch ist als gefährlich eingestuft
# im Sinne der Verordnung (EG) Nr. 1272/2008" -- not "nicht als gefährlich".
_CLASSIFIED_AS_HAZARDOUS = re.compile(
    r"(nicht\s+)?als\s+gefährlich\s+eingestuft", re.IGNORECASE
)
_ABOUT_INGREDIENTS = re.compile(r"enthält|Inhaltsstoff|Bestandteil", re.IGNORECASE)


def _names_a_hazard_class(part: str) -> bool:
    """Whether a classification part names a hazard class of the product."""
    if _HAZARD_CLASS_CODE.search(part) or _HAZARD_CLASS_NAME.search(part):
        return True
    for entry in _HAZARD_CLASS_IN_WORDS.finditer(part):
        start = part.rfind(".", 0, entry.start()) + 1
        end = part.find(".", entry.end())
        sentence = part[start : end if end != -1 else len(part)]
        if not _ABOUT_INGREDIENTS.search(sentence):
            return True
    return False


def _says_classified(part: str) -> bool:
    """Whether a part says in a sentence that the product is classified as
    hazardous; not in a clause of a condition ("… selbst wenn sie … als
    gefährlich eingestuft wurden", SDB-75)."""
    for match in _CLASSIFIED_AS_HAZARDOUS.finditer(part):
        if match.group(1) is not None:
            continue
        sentence = part[
            max(part.rfind(".", 0, match.start()), part.rfind(";", 0, match.start()))
            + 1 : match.start()
        ]
        if not _CONDITION.search(sentence):
            return True
    return False


# A clause of a condition: what follows it says what would be, not what is.
_CONDITION = re.compile(
    r"\b(?:selbst\s+wenn|auch\s+wenn|wenn|falls|sofern)\b", re.IGNORECASE
)


# How sheets say that the product is not classified.
_NOT_CLASSIFIED = re.compile(
    r"nicht\s+(?:als\s+gefährlich\s+)?eingestuft"
    r"|nicht\s+als\s+(?:gesundheits-\s+oder\s+umwelt)?gefährlich"
    r"|nicht\s+(?:den|die)\s+Kriterien|keinem\s+Kriterium\s+für\s+die\s+Einstufung"
    r"|kriterien\s+(?:sind\s+)?nicht\s+erfüllt"
    r"|keiner\s+Gefahren(?:kategorie|klasse)"
    r"|nicht\s+einstufungspflichtig|keine\s+(?:Gefahren)?einstufung"
    # "… ist eine Einstufung gemäß der Verordnung … nicht nötig." (SDB-75).
    r"|\bEinstufung\b(?:Nr\.|[^.]){0,120}?\bnicht\s+(?:nötig|notwendig|erforderlich)\b"
    # "Keine Klassifizierung für physikalische Gefahren." (SDB-81).
    r"|keine\s+Klassifizierung"
    # "… als Fertigprodukt unterliegen nicht der Einstufung gemäß …" (SDB-81).
    r"|unterlieg\w*\s+nicht\s+der\s+Einstufung"
    r"|nicht\s+gefährlich|\bungefährlich|nicht\s+klassifiziert"
    r"|nicht\s+kennzeichnungspflichtig|von\s+der\s+Etikettierung\s+befreit"
    r"|keine?\s+gefährliche[nrs]?\s+"
    r"(?:Substanz|Stoffe?|Mischung|Gemische?|Produkt|Zubereitung)"
    r"|keine\s+relevanten\s+Anteile\s+an\s+gefährlichen"
    r"|keine\s+gesundheitsschädlichen?\s+Wirkung"
    r"|keine\s+besonder(?:en|s)\s+(?:zu\s+erwähnenden\s+)?Gefahren"
    r"|Gefahrenbezeichnung:\s*keine"
    # A cosmetic product is exempt from CLP (Article 1(5)(c)).
    r"|kosmetisches\s+Mittel"
    r"|keine\s+Gefährdung\s+für\s+die\s+Gesundheit|keine\s+weiteren\s+Risiken"
    # An article is not classified at all: CLP covers substances and mixtures.
    r"|\bErzeugnis\b"
    r"|\bentfällt\b|nicht\s+(?:relevant|anwendbar|zutreffend)"
    # From the last colon before the word, so that a run of colons and blanks
    # is not read again from each of them.
    r"|(?m:(?:^|:)[^\w\n:]*keine?\.?[^\w\n]*$)"
    # "GHS Einstufung:" / "N/A" -- not applicable (SDB-81).
    r"|(?m:(?:^|:)[^\w\n:]*N\s?/\s?A\b[^\w\n]*$)"
    # A dash where the classification would stand.
    # Each character of the line one way: dashes, then blanks to its end.
    r"|(?m:^[^\S\n]*[-\u2013\u2014](?:[-\u2013\u2014]|[^\S\n](?=[^\S\n]|$))*$)",
    re.IGNORECASE,
)


# A classification that only says nothing is at hand (SDB-75, step 5): a classified
# product has to name its classification there, so this names none.
_NO_ANSWER = re.compile(
    r"Es\s+liegen\s+keine\s+Informationen\s+vor"
    r"|Keine\s+Daten\s+verfügbar"
    r"|\bn\.\s?a\.",
    re.IGNORECASE,
)
# An EUH statement is supplemental labelling, not a hazard class (SDB-75, step 7).
_EUH_CODE = re.compile(r"\bEUH\s?\d{3}[A-Z]?\b")


def _classification_parts(hazards_section: str) -> list[str]:
    """The text under each classification heading, up to the label's heading.

    A document that holds several sheets -- the two components of an adhesive
    -- has one part per sheet. Without the heading the section itself is the
    part, as far as the label's heading.
    """
    starts = [m.end() for m in _CLASSIFICATION_HEADING.finditer(hazards_section)]
    ends = [*starts[1:], len(hazards_section)]
    parts = [
        hazards_section[start:end] for start, end in zip(starts, ends, strict=False)
    ] or [hazards_section]
    return [
        part[: label.start()] if (label := LABEL_HEADING_PATTERN.search(part)) else part
        for part in parts
    ]


# What the label part says when the section has no classification heading
# (SDB-107): that the product is not classified, or that it needs no label.
_LABEL_SAYS_UNCLASSIFIED = re.compile(
    r"nicht\s+(?:als\s+gefährlich\s+)?eingestuft|als\s+nicht\s+gefährlich\s+eingestuft"
    r"|nicht\s+kennzeichnungspflichtig|keine\s+Kennzeichnung\s+erforderlich",
    re.IGNORECASE,
)
_OTHER_HAZARDS_HEADING = re.compile(r"Sonstige\s+Gefahren", re.IGNORECASE)


def _label_says_unclassified(hazards_section: str) -> bool:
    """Whether the label part, up to the other hazards, says so and prints no
    hazard code."""
    heading = LABEL_HEADING_PATTERN.search(hazards_section)
    if heading is None:
        return False
    label = hazards_section[heading.end() :]
    other = _OTHER_HAZARDS_HEADING.search(label)
    label = label[: other.start()] if other else label
    return (
        _LABEL_SAYS_UNCLASSIFIED.search(label) is not None
        and _HAZARD_CLASS_CODE.search(label) is None
    )


def _gives_no_answer(part: str) -> bool:
    """Nothing under the classification but "no information" (SDB-75, step 5)."""
    rest, found = _NO_ANSWER.subn("", part)
    return found > 0 and not re.search(r"[^\W\d]", rest)


# A hazard statement's code as section 2.1 names it with a hazard class: H200
# to H499, H360 and H361 with the letters of their effect (SDB-173).
_CLASSIFICATION_HAZARD_CODE = re.compile(
    r"\bH(?:36[01][A-Za-z]{1,2}(?![^\W\d_])|[2-4]\d{2})(?!\d)"
)


def classification_hazard_codes(hazards_section: str) -> set[str]:
    r"""The H codes section 2.1 names for the product's classification (SDB-173).

    Read from the text under each classification heading up to the label's
    (SDB-75); never codes of the sheet. A code on a line that speaks of
    ingredients ("enthält", "Inhaltsstoff", "Bestandteil", as in SDB-80), or on
    the line after one that it continues, is an ingredient's, not the product's.

    >>> classification_hazard_codes(
    ...     "2.1 Einstufung des Stoffs oder Gemischs\n"
    ...     "Flam. Liq. 3, H226\nRepr. 1B, H360D\n"
    ...     "Das Gemisch enthält Stoffe, die als Acute Tox. 4\n(H302) eingestuft sind.\n"
    ...     "2.2 Kennzeichnungselemente\nH226 Flüssigkeit und Dampf entzündbar.\n"
    ... ) == {"H226", "H360D"}
    True
    """
    codes: set[str] = set()
    for part in _classification_parts(hazards_section):
        lines = part.split("\n")
        for index, line in enumerate(lines):
            found = _CLASSIFICATION_HAZARD_CODE.findall(line)
            if not found or _ABOUT_INGREDIENTS.search(line):
                continue
            continues = line.lstrip()[:1].islower() or line.lstrip().startswith("(")
            if continues and index and _ABOUT_INGREDIENTS.search(lines[index - 1]):
                continue
            codes.update(lettered_code(code) for code in found)
    return codes


def classification_codes_complete(hazards_section: str) -> bool:
    r"""Whether 2.1 names a code for each hazard class it names (SDB-197):
    in every classification part at least as many H codes as classes, by
    their abbreviation ("Skin Irrit. 2") or in words ("Reizwirkung auf die
    Haut, Kategorie 2"). A part that names classes in words only is not
    read to its codes.

    >>> classification_codes_complete("Skin Irrit. 2, H315\nEye Irrit. 2")
    False
    >>> classification_codes_complete(
    ...     "Akut gewässergefährdend, Kategorie 1 (Aquatic Acute 1, H400)."
    ... )
    True
    """
    for part in _classification_parts(hazards_section):
        # A class may stand in both forms ("Akut gewässergefährdend, Kategorie
        # 1 (Aquatic Acute 1, H400)"): the larger count is that of the classes.
        classes = max(
            len(_HAZARD_CLASS_NAME.findall(part)),
            sum(
                1
                for entry in _HAZARD_CLASS_IN_WORDS.finditer(part)
                if not _ABOUT_INGREDIENTS.search(entry.group(0))
            ),
        )
        if len(set(_CLASSIFICATION_HAZARD_CODE.findall(part))) < classes:
            return False
    return True


def stated_classification(hazards_section: str) -> StatedClassification:
    """What section 2 says about the product's classification (SDB-75).

    Of several sheets in one document the product is classified if one is.
    """
    parts = _classification_parts(hazards_section)
    if any(_names_a_hazard_class(part) for part in parts):
        return StatedClassification.CLASSIFIED
    if any(old_classification(part) is not None for part in parts):
        return StatedClassification.OLD_SYSTEM
    if any(_says_classified(part) for part in parts):
        return StatedClassification.CLASSIFIED
    if any(_NOT_CLASSIFIED.search(part) for part in parts):
        return StatedClassification.NOT_CLASSIFIED
    if any(_gives_no_answer(part) for part in parts):
        return StatedClassification.NOT_CLASSIFIED
    # Only under the classification's own heading: without it the part is the
    # whole section, where an EUH statement may stand beside a hazard in words.
    headed = _CLASSIFICATION_HEADING.search(hazards_section) is not None
    # The regulation's wording of a hazard statement without its code
    # (SDB-75, step 6): "Schädlich für Wasserorganismen, mit langfristiger Wirkung."
    if headed and any(
        _HAZARD_CLASS_CODE.fullmatch(code)
        for part in parts
        for code in codes_from_wording(part)
    ):
        return StatedClassification.CLASSIFIED
    if headed and any(_EUH_CODE.search(part) for part in parts):
        return StatedClassification.NOT_CLASSIFIED
    if not headed and _label_says_unclassified(hazards_section):
        return StatedClassification.NOT_CLASSIFIED
    return StatedClassification.NOT_STATED


# A sheet that says of itself that it is issued voluntarily or that none is
# prescribed for its product (SDB-142). The sentence speaks of the safety data
# sheet itself; within it a full stop only ends an abbreviation or stands
# before a number ("gem. Artikel 31", "Art. 31", "Nr. 1907/2006").
_SHEET_WORD = r"(?:Produkt)?[Ss]icherheitsdatenbl[aä]tt(?:es|s|er|ern)?|SDB|SDS"
_SHEET = rf"\b(?:{_SHEET_WORD})\b(?:\s*\((?:SDB|SDS)\))?"
_IN_SENTENCE = (
    r"(?:\b(?:gem|Nr|Art|Abs|bzw|ggf|lt|vgl)\.|[^.!?;:]|\.(?=\s*[\da-zäöü(]))"
)
_NOT_DUE = (
    r"(?:verpflichtend|vorgeschrieben|erforderlich|notwendig|nötig|verlangt"
    r"|gefordert|zu\s+erstellen)"
)
_VOLUNTARILY = r"(?:freiwillig|auf\s+freiwilliger\s+(?:Basis|Grundlage))"
_SAYS_VOLUNTARY = re.compile(
    "|".join(
        (
            # "… ist gemäß Artikel 31 … kein Sicherheitsdatenblatt erforderlich."
            rf"\b[Kk]ein\s+{_SHEET}{_IN_SENTENCE}{{0,140}}?\b{_NOT_DUE}\b",
            # "Das SDB ist für dieses Produkt rechtlich nicht vorgeschrieben."
            rf"{_SHEET}\s+(?:ist|sind)\s{_IN_SENTENCE}{{0,140}}?"
            rf"\b(?:nicht|keine?)\s+(?:\w+\s+){{0,2}}{_NOT_DUE}\b",
            # "… eines Sicherheitsdatenblattes (SDS) gesetzlich nicht verpflichtend."
            rf"{_SHEET}\s+(?:(?:gesetzlich|rechtlich)\s+)?nicht\s+{_NOT_DUE}\b",
            # "… sind wir nicht verpflichtet ein Sicherheitsdatenblatt zu erstellen."
            rf"\bnicht\s+verpflichtet,?\s+eine?\s+{_SHEET}",
            # "Dieses Sicherheitsdatenblatt wurde freiwillig erstellt"
            rf"{_SHEET}\s+(?:wurde|wird|ist|erfolgt)\s+(?:\w+\s+){{0,4}}?{_VOLUNTARILY}\b",
            # "… dieses Sicherheitsdatenblatts auf freiwilliger Basis."
            rf"{_SHEET}\s+auf\s+freiwilliger\s+(?:Basis|Grundlage)\b",
            # "Dieses auf freiwilliger Basis erstellte SDS", "die von uns
            # freiwillig zur Verfügung gestellten Sicherheitsdatenblätter"
            rf"\b{_VOLUNTARILY}\s+(?:erstellte|bereitgestellte"
            rf"|zur\s+Verfügung\s+gestellte)[nrs]?\s+{_SHEET}",
            # "Freiwillige Produktinformation in Anlehnung an das
            # Sicherheitsdatenblatt-Format"
            r"\b[Ff]reiwillige[ns]?\s+(?:Produkt|Sicherheits)?[Ii]nformation(?:en)?"
            r"\s+in\s+Anlehnung\s+an\s+(?:das|ein)\s+Sicherheitsdatenbl[aä]tt",
            # "… ist eine freiwillige Information und kein Sicherheitsdatenblatt"
            r"\bfreiwillige\s+Information\s+und\s+kein\s+Sicherheitsdatenbl[aä]tt",
        )
    )
)


# The sheet calls its product an article beside that sentence (SDB-142): the
# word within this many characters of it, and not in the regulation's row
# "Stoffe, Gemische und Erzeugnisse", which stands in every sheet.
_ARTICLE_REACH = 400
_ARTICLE = re.compile(r"\bErzeugnis(?:se[sn]?|s)?\b")
_ARTICLE_IN_A_ROW = re.compile(
    r"\b(?:Stoffe|Gemische|Mischungen|Zubereitungen)\b[^.]{0,60}?\bund\s+Erzeugnisse\b"
)


# The sheet says its product is an article and therefore not subject to
# labelling (SDB-154): that it is one, and within this many characters behind
# it that no labelling is due. The bare word says nothing of the product
# ("Das Erzeugnis ist ... nicht kennzeichnungspflichtig"), and "kein
# Erzeugnis" denies it.
_ARTICLE_EXEMPT_REACH = 250
_IS_ARTICLE = re.compile(
    r"\b(?:ist|sind)\s+ein\s+Erzeugnis\b"
    r"|\bstell(?:t|en)\s[^.]{0,80}?\bein\s+Erzeugnis\s+dar\b"
    r"|\bgilt\s[^.]{0,120}?\bals\s+Erzeugnis\b"
    r"|\bhandelt\s+(?:es\s+)?sich\s+um\s+ein\s+Erzeugnis\b"
    r"|\bunterliegt\s+als\s+Erzeugnis\s+nicht\b"
)
_NOT_LABELLED = re.compile(
    r"\bnicht\s+kennzeichnungspflichtig\b"
    r"|\bnicht\s+der\s+(?:\w+\s+){0,2}Kennzeichnungspflicht\b"
)


def says_article(text: str) -> bool:
    """Whether a sheet calls its product an article (SDB-142, SDB-154).

    Beside the sentence that makes the sheet voluntary: "Dieses Produkt ist
    ein Erzeugnis und daher ist die Erstellung eines Sicherheitsdatenblattes
    nicht verpflichtend." Or with the sentence that an article needs no
    labelling: "Dieses Produkt ist ein Erzeugnis, deshalb ist es nicht
    kennzeichnungspflichtig."

    >>> says_article(
    ...     "Dieses Produkt ist ein Erzeugnis und daher ist die Erstellung eines "
    ...     "Sicherheitsdatenblattes gesetzlich nicht verpflichtend."
    ... )
    True
    >>> says_article(
    ...     "Dieses Produkt ist ein Erzeugnis, deshalb ist es nach "
    ...     "EG-Richtlinien nicht kennzeichnungspflichtig."
    ... )
    True
    >>> says_article("Das Erzeugnis ist nicht kennzeichnungspflichtig.")
    False
    >>> says_article("Dieses Sicherheitsdatenblatt wurde freiwillig erstellt.")
    False
    """
    flat = _ARTICLE_IN_A_ROW.sub(" ", re.sub(r"\s+", " ", text))
    if any(
        _NOT_LABELLED.search(flat, said.end(), said.end() + _ARTICLE_EXEMPT_REACH)
        for said in _IS_ARTICLE.finditer(flat)
    ):
        return True
    return any(
        _ARTICLE.search(
            flat, max(0, said.start() - _ARTICLE_REACH), said.end() + _ARTICLE_REACH
        )
        for said in _SAYS_VOLUNTARY.finditer(flat)
    )


def says_voluntary(text: str) -> bool:
    """Whether a sheet says it is issued voluntarily or none is prescribed (SDB-142).

    Anywhere in its text: sheets print the sentence under the title, in
    section 1, 2, 3, 15 or 16, or in the page header.

    >>> says_voluntary(
    ...     "Für dieses Produkt ist gemäß Artikel 31 der REACH-Verordnung "
    ...     "kein Sicherheitsdatenblatt erforderlich."
    ... )
    True
    >>> says_voluntary("Signalwort: nicht erforderlich. UFI: nicht notwendig.")
    False
    """
    return _SAYS_VOLUNTARY.search(re.sub(r"\s+", " ", text)) is not None


# Which countries a German-language sheet is issued for (SDB-69). Annex II
# asks for the limit values and regulations of the country of sale and for its
# advisory body, so suppliers issue the same sheet per country. A code printed
# beside the version says it outright ("Version: 3 / CH"); it comes first,
# because a template carries some national names into every version
# ("Lagerklasse nach TRGS 510" stands in one supplier's Austrian and Swiss sheets).
_COUNTRY_CODE = re.compile(
    r"(?m)Version[^\S\n]*:?[^\n/]{0,12}/[^\S\n]*(DE|AT|CH)[^\S\n]*$"
)
_NATIONAL_RULES: dict[str, re.Pattern[str]] = {
    "DE": re.compile(
        r"\bTRGS\s?\d{3}|Wassergef[äa]hrdungsklasse|\bWGK\b|\bAwSV\b|\bVwVwS\b|\bAGW\b"
    ),
    "AT": re.compile(r"\bGKV\b|Grenzwerteverordnung|\bVbF\b"),
    "CH": re.compile(r"\bSUVA\b|\bChemRRV\b"),
}
# An advisory body by its name or number, looked for in section 1 only:
# "GIFTINFORMATIONSZENTRUM" alone is the wording of P statements.
_ADVISORY_BODIES: dict[str, re.Pattern[str]] = {
    "DE": re.compile(
        r"19\s?2\s?40\b|GIZ-Nord|Vergiftungs-Informations-Zentrale"
        r"|Giftnotruf\s+(?:Berlin|München|Mainz|Bonn|Erfurt|Freiburg|Göttingen|Homburg"
        r"|Nürnberg|der\s+Charité)"
        r"|Giftinformationszentrum(?:-Nord|\s+der\s+Länder|\s+Erfurt|\s+Mainz|\s+Nord)"
        r"|\+\s?49[^\n]{0,30}(?:Gift|Notruf)|(?:Gift|Notruf)[^\n]{0,40}\+\s?49"
    ),
    "AT": re.compile(
        r"406\s?43\s?43|1\s?406\s?43|14064343|Vergiftungsinformationszentrale"
    ),
    "CH": re.compile(
        r"Tox\s?Info\s?Suisse|Toxikologisches\s+Informationszentrum|\bSTIZ\b"
        r"|(?:Tel\.?|Notruf\w*:?)\s*145\b"
    ),
}


def sheet_countries(text: str, identification: str) -> list[str]:
    """The countries a sheet is issued for, of DE, AT and CH (SDB-69)."""
    printed = {match.group(1) for match in _COUNTRY_CODE.finditer(text)}
    if printed:
        return sorted(printed)
    named = {country for country, rule in _NATIONAL_RULES.items() if rule.search(text)}
    named |= {
        country
        for country, body in _ADVISORY_BODIES.items()
        if body.search(identification)
    }
    return sorted(named)


# "Kein Signalwort" is an answer, not a missing one: the sheet states that this
# classification carries none. Distinguishing it from "not found" is what lets
# the caller decide whether to fall back to the derivation.
#
# On one line: "Gefahrenpiktogramme" / "keine" / "Signalwort" / "ACHTUNG" is a
# label without a pictogram, not one without a signal word.
# A sentence that says a label is not applied (SDB-78): "Eine Kennzeichnung des
# Silikons mit GHS 07 / Achtung / H317 erfolgt daher nicht." Read as a label it
# gave 19 sealants the very statement the sheet explains away.
# Or that one is not required: "Die Kennzeichnung einer Aspirationsgefahr (Asp.
# Tox. 1 H304) ist für Aerosolpackungen … nicht vorgeschrieben". The class's
# abbreviation carries full stops, so the sentence is not held to them.
_LABEL_DECLINED = re.compile(
    r"Eine\s+Kennzeichnung\b[^.]{0,200}?\berfolgt\s+(?:daher\s+)?nicht\."
    r"|(?:Eine|Die)\s+(?:Einstufung\s+und\s+)?Kennzeichnung\b[^\n]{0,80}?"
    r"\bH\d{3}\b[\s\S]{0,160}?\bnicht\s+(?:vorgeschrieben|erforderlich|notwendig)\b"
)
NO_SIGNAL_WORD_PATTERN = re.compile(
    r"\bkein(?:e[ns]?)?[^\S\n]+Signalwort\b"
    # Suppliers write the absence four ways. All of them are anchored to the
    # label, because a bare dash or "entfällt" says nothing on its own:
    #   Signalwort entfällt
    #   Signalwort (CLP) : -
    #   Signalwort nicht erforderlich
    r"|\bSignalwort\b\s*(?:\([^)]{0,12}\)\s*)?(?::\s*)?"
    r"(?:entfällt|nicht\s+erforderlich|nicht\s+anwendbar|[-\u2013\u2014](?!\w))"
    # The value in a form, behind the label or on the line below it, and
    # nothing after it on its line:
    #   Signalwort
    #   keine
    r"|\bSignalwort\b[^\S\n]*(?:\([^)]{0,12}\)[^\S\n]*)?(?::[^\S\n]*)?(?:\n[^\S\n]*)?"
    r"(?:kein(?:e[ns]?)?|ohne)[^\S\n]*(?=\n|$)",
    re.IGNORECASE,
)
# A label that states it carries no pictogram (SDB-180), the word anchored to
# the label as for the signal word above:
#   Gefahrenpiktogramme entfällt
#   Piktogramme: nicht erforderlich
#   Gefahrenpiktogramme
#   -
#   Kein Piktogramm, kein Signalwort, keine Gefahrenhinweise
# The dash ends its line: "Symbol R - Sätze" is a heading of the old law.
NO_PICTOGRAM_PATTERN = re.compile(
    r"\bkein(?:e[ns]?)?[^\S\n]+(?:Gefahren)?piktogramm"
    r"|\b(?:Gefahren)?(?:piktogramm(?:e|en|\(e\)|/e)?|symbole)\b[^\S\n]*"
    r"(?:code[^\S\n]*)?(?::[^\S\n]*)?(?:\n[^\S\n]*)?"
    r"(?:entfällt|nicht\s+(?:erforderlich|anwendbar|zutreffend|kennzeichnungspflichtig)"
    r"|kein(?:e[nrs]?)?\b|[-\u2013\u2014]+[^\S\n]*(?=\n|$))",
    re.IGNORECASE,
)


def states_no_pictograms(label_text: str) -> bool:
    r"""Whether the label states that it carries no pictogram (SDB-180), of the
    pictograms or of the whole label (UNLABELLED_PATTERN, as for the signal
    word).

    >>> states_no_pictograms("Gefahrenpiktogramme entfällt\nSignalwort entfällt")
    True
    >>> states_no_pictograms("Gefahrenpiktogramme\nGHS07\nSignalwort Achtung")
    False
    """
    return bool(
        NO_PICTOGRAM_PATTERN.search(label_text) or UNLABELLED_PATTERN.search(label_text)
    )


# A product that carries no label at all carries no signal word either. These
# sheets never print a Signalwort row, because there is no label to print it on
# -- they say so in section 2.2 instead:
#
#   Keine Kennzeichnung erforderlich
#   Der Stoff oder das Gemisch ist nicht gefährlich gemäß Verordnung (EG)
#     Nr. 1272/2008 (CLP)
#   NC Nicht Eingestuft
#
# That is a determination, not silence, and it matters: 97 sheets in this
# catalogue state it, and the model gave 19 of them "Gefahr" -- read off the
# ingredient classifications in section 3, which belong to the raw materials
# and not to the product.
#
# Searched only within section 2.2, which is what keeps it safe: "nicht
# eingestuft" is commonplace in 2.1 beside a hazard class the product does not
# meet, and would say nothing about the label there. Measured over the
# catalogue, all 147 sheets this matches carry no hazard code and no printed
# signal word in their label block.
UNLABELLED_PATTERN = re.compile(
    r"kein[a-zäöü]*\s+Kennzeichnung\b[^.\n]{0,40}\berforderlich"
    r"|nicht\s+gefährlich\s+(?:gemäß|nach|im\s+Sinne)"
    r"|\bnicht\s+eingestuft\b",
    re.IGNORECASE,
)

# "Nicht bestimmt" under the 2.2 heading is a third state, and conflating it
# with either of the other two gets the product wrong.
#
# It is not UNLABELLED_PATTERN. That one reads a *determination* -- the supplier
# has established that this product carries no label -- and settling the signal
# word on it is sound. "Nicht bestimmt" establishes nothing: the supplier has
# not worked the labelling out. Reading it as "no hazard" would put an absence
# on the product that the sheet never states.
#
# What it does settle is that no classification was declared, and that is enough
# to keep an undeclared one off the label. On the sheet this was measured from,
# a 2012 motor oil, the model returned H304 -- read from "Asp. Tox. 1, H304" in
# the section 3 ingredient table and from the section 16 glossary. The mixture
# may well merit it; 10-20% of an Asp. Tox. 1 substance would. But that is our
# inference from a component, not the supplier's declaration, and section 2.2 is
# the authority on what the product is labelled with.
#
# Bounded to the top of the block on purpose. "Nicht bestimmt" is commonplace in
# section 9 next to a physical property nobody measured, and a label block whose
# boundary failed runs on for LABEL_SECTION_MAX_CHARS.
_UNDETERMINED_WINDOW = 300
UNDETERMINED_LABELLING_PATTERN = re.compile(
    r"\bnicht\s+bestimmt\b|\bnicht\s+festgelegt\b", re.IGNORECASE
)


def states_undetermined_labelling(label_text: str) -> bool:
    """Whether the label block says the labelling was never determined."""
    return bool(
        UNDETERMINED_LABELLING_PATTERN.search(label_text[:_UNDETERMINED_WINDOW])
    )


STATEMENT_CODE_PREFIX = re.compile(r"^(H|P|EUH)\d{2,3}\b", re.IGNORECASE)

# Where a statement of the parser's text ends, and what it reads past (SDB-27).
# Measured over the 1997 current sheets, a statement that ran on to the next code
# carried a page header or a foreign heading 4454 times; 118 are left.
_ANY_STATEMENT_CODE = re.compile(r"\b(?:EUH\d{3}|[HP]\d{3})(?!\d)")
# "2.3 Sonstige Gefahren", and "2.3" on its own line with its title below; not
# "2.5 kg".
_NUMBERED_SUBHEADING = re.compile(r"^\d{1,2}\.\d{1,2}\.?(?:\s+[A-ZÄÖÜ].*)?$")
# The label's own headings and the rows of its 2.2 table, capitalised as headings
# are: a line that continues a sentence in lower case is not one.
_LABEL_HEADING = re.compile(
    r"^(?=(?-i:[A-ZÄÖÜ]))(?:Gefahrenhinweis\w*|Sicherheitshinweis\w*|[HP]-Sätze|EUH[- ]?Sätze"
    r"|Ergänzende|Zusätzliche|Besondere\s+(?:Vorschriften|Kennzeichnung|Gefahrenhinweise)"
    r"|Andere\s+Kennzeichnung|Kindersicherung|Ta[ks]t\w+\s+Warn(?:zeichen|hinweis)"
    r"|Ergebnisse\s+der\s+PBT-\s+und\s+vPvB-Beurteilung"
    r"|Endokrinschädliche\s+Eigenschaften"
    r"|Mögliche\s+Gefahren|Hinweise?\s+zur\s+Kennzeichnung|Signalwort"
    r"|Gefahrenpiktogramm\w*|Piktogramm\w*|Gefahr(?:en)?bestimmende"
    r"|Gefährliche\s+Inhaltsstoffe|[RS]-Sätze"
    r"|Kennzeichnung|Kennzeichnungselemente|Sonstige\s+Gefahren"
    r"|Wortlaut\s+der|Volltext\s+der|Mit\s+kindergesicherten"
    r"|Kindergesicherte[rn]?|Tastbare[rn]?|Spezielle\s+Verpackungs\w*"
    r"|Anhang\s+XVII|Nicht\s+anwendbar\.?$"
    r"|(?:Prävention|Reaktion|Lagerung|Entsorgung|Allgemein(?:es)?)\s*:)(?![\w-])",
    re.IGNORECASE,
)
# A hazard class with its category, the way 2.1 lists them: "Eye Irrit. 2",
# "STOT SE 3", "Langfristig (chronisch) gewässergefährdend, Kategorie 3". The
# classes are CLP's own abbreviations (Annex VI, table 1.1), so a page header's
# "Version 3" is not one of them.
_CLASSIFICATION_LINE = re.compile(
    r"^(?:Unst\.\s*Expl|Expl|Flam\.\s*(?:Gas|Liq|Sol)|Chem\.\s*Unst\.\s*Gas|Aerosol"
    r"|Ox\.\s*(?:Gas|Liq|Sol)|Press\.\s*Gas|Self-react|Pyr\.\s*(?:Liq|Sol)"
    r"|Self-heat|Water-react|Org\.\s*Perox|Met\.\s*Corr|Acute\s*Tox|Skin\s*Corr"
    r"|Skin\s*Irrit|Eye\s*Dam|Eye\s*Irrit|Resp\.\s*Sens|Skin\s*Sens|Muta|Carc"
    r"|Repr|Lact|STOT\s*(?:SE|RE)|Asp\.\s*Tox|Aquatic\s*(?:Acute|Chronic)"
    r"|Ozone|Desen\.\s*Expl|ED\s*(?:HH|ENV)|PBT|vPvB|PMT|vPvM)\b\.?\s*\d?[A-F]?$"
    r"|\bKategorie\s+\d"
)
# A pictogram's code at a statement's end (SDB-27).
_TRAILING_PICTOGRAM = re.compile(
    r"(?m)(?<=[.!])[^\S\n]+GHS\d{2}(?:[\s,]+GHS\d{2})*[^\S\n]*$"
)
_PAGE_NUMBER = re.compile(
    # "Page n. 1 von 9" (SDB-27).
    r"^(?:Page\s+(?:n\.|no\.|nr\.)?\s*)?\d{1,3}\s*(?:/|von|of)\s*\d{1,3}$"
    r"|^(?:Seite\s*:?\s*)?\d{1,3}\s*(?:/|von)\s*\d{1,3}$"
    r"|^Seite\s*:?\s*\d{1,3}(?:\s*(?:/|von)\s*\d{1,3}|\s*\(\d{1,3}\))?$",
    re.IGNORECASE,
)
_CONTINUED = re.compile(r"\(?Fortsetzung\s+(?:auf|von)\s+Seite\s*\d+\)?", re.IGNORECASE)
# A statement's own heading, repeated at the top of the next page: read as a
# heading, it cut P210 of one sheet off before "fernhalten. Nicht rauchen."
_OWN_HEADING = {
    HAZARD_CODE_PATTERN: re.compile(
        r"^Gefahrenhinweis\w*(?:\s*\(Fortsetzung\))?\s*:?$", re.IGNORECASE
    ),
    PRECAUTION_CODE_PATTERN: re.compile(
        r"^Sicherheitshinweis\w*(?:\s*\(Fortsetzung\))?\s*:?$", re.IGNORECASE
    ),
    SUPPLEMENTAL_CODE_PATTERN: re.compile(
        r"^(?:Ergänzende\s+Gefahrenhinweise|EUH[- ]?Sätze)(?:\s*\(Fortsetzung\))?\s*:?$",
        re.IGNORECASE,
    ),
}


def _page_furniture(text: str, pages: int) -> frozenset[str]:
    """The lines that repeat like a page header: on half the pages, three times at least.

    The pages themselves are not kept with the record, so this counts the
    joined text. A sentence a sheet prints in 2.2 and again in section 16 can
    repeat as often on a short sheet, which is why _extract_statement_text
    passes over these lines only once a statement has its wording.
    """
    counts = Counter(line.strip() for line in text.split("\n") if line.strip())
    threshold = max(3, (pages + 1) // 2)
    return frozenset(line for line, n in counts.items() if n >= threshold)


@dataclass(slots=True)
class ParsedSheet:
    """A parsed sheet, and what the parser noticed while reading it."""

    sheet: SafetyDataSheet
    warnings: list[Message]
    # Each sheet of a file that holds several, read on its own, in the file's
    # order (SDB-118); empty for a file that is one sheet.
    parts: list[SheetPart] = field(default_factory=list)
    # Whether a cover page stands in front of the file's sheets, and the word
    # on it that names a display, as printed (SDB-138); it is read for nothing
    # else and is no sheet.
    cover_page: bool = False
    display_term: str | None = None


@dataclass(slots=True)
class SheetPart:
    """One sheet of a file that holds several, read on its own (SDB-118)."""

    sheet: SafetyDataSheet
    warnings: list[Message]
    # The sheet's text, as split_into_sheets cuts it from the file's.
    text: str


class SDSParser:
    """Convert extracted SDS text into structured fields."""

    def __init__(self, *, language: str = "de") -> None:
        self.language = language

    def parse(self, extraction: ExtractionResult) -> ParsedSheet:
        """The file's reading, and each sheet's where it holds several.

        The file's reading unites its sheets (SDB-3, SDB-9). Beside it each
        sheet is read from its own text, as a file holding only that sheet
        would be (SDB-118). A cover page in front of the sheets is left out
        of both (SDB-138).
        """
        whole = max(len(extraction.text), 1)

        def share(text: str) -> int:
            # The pages are not kept with the text: a part of it has its share
            # of them, which is what repeating page headers are counted by.
            return max(1, round(extraction.pages_sampled * len(text) / whole))

        cover, body = split_cover_page(extraction.text)
        if cover:
            # The cover page is read for nothing (SDB-138): the file's reading
            # is that of the sheets behind it.
            extraction = replace(extraction, text=body, pages_sampled=share(body))
        result = self._parse_text(extraction)
        result.cover_page = bool(cover)
        result.display_term = _display_term(cover)
        texts = split_into_sheets(body)
        if len(texts) > 1:
            for text in texts:
                read = self._parse_text(
                    replace(
                        extraction,
                        text=text,
                        raw_text=text,
                        pages_sampled=share(text),
                        warnings=[],
                        metadata={},
                    )
                )
                result.parts.append(SheetPart(read.sheet, read.warnings, text))
            # A file calls itself voluntary where each of its sheets does
            # (SDB-142): one sheet's word does not speak for the others.
            result.sheet.stated_voluntary = all(
                part.sheet.stated_voluntary for part in result.parts
            )
            result.sheet.stated_article = all(
                part.sheet.stated_article for part in result.parts
            )
        return result

    def _parse_text(self, extraction: ExtractionResult) -> ParsedSheet:
        sections = split_sections(extraction.text)

        hazards, hazard_warnings = _parse_hazard_statements(
            sections, extraction.text, pages=extraction.pages_sampled
        )
        stated = stated_classification(sections.get(Section.HAZARDS, ""))
        if (
            stated is StatedClassification.NOT_CLASSIFIED
            and hazards.signal_word
            and not hazards.hazard_codes
        ):
            # A signal word comes with a hazard statement. On a sheet that says
            # "not classified" and prints none, "Gefahr" is a word of its text
            # (SDB-77): "Es besteht keine Gefahr, wenn …", "Gefahr bestimmende
            # Komponente zur Etikettierung".
            hazard_warnings.append(
                Message("signal-word-not-taken", {"signal_word": hazards.signal_word})
            )
            hazards.signal_word = None
        contact_info, contact_warnings = _parse_contact_info(
            sections.get(Section.IDENTIFICATION, ""),
            _page_furniture(extraction.text, extraction.pages_sampled),
        )
        product_identifier = (
            _value_before_label(extraction.text)
            or _extract_product_identifier(sections.get(Section.IDENTIFICATION, ""))
            or _name_in_header(
                sections.get(Section.IDENTIFICATION, ""),
                _lines_above_section_1(extraction.text),
            )
        )

        # Version and the dates are document-level facts carried in the page
        # header/footer, not Section 2 content -- reading only the hazard
        # section missed every sheet whose pagination put the footer elsewhere.
        version = _extract_version(extraction.text)
        revision_date = _extract_revision_date(extraction.text)
        issue_date = _extract_issue_date(extraction.text)
        if revision_date is None and issue_date is None:
            # An undated sheet cannot be ranked against its own revisions, and
            # cannot be checked against the statutory cut-offs that decide
            # whether it is still a valid document. See EFFECTIVE_DATE_PATTERN.
            revision_date = (
                _extract_date_from_columns(extraction.text)
                or _extract_date_below_label(extraction.text)
                or _extract_effective_date(extraction.text)
                or _extract_short_year_date(extraction.text)
                or _latest_dated_match(extraction.text, PLAIN_DATE_PATTERN)
                or _extract_month_year_date(extraction.text)
            )

        warnings: list[Message] = [
            *extraction.warnings,
            *hazard_warnings,
            *contact_warnings,
        ]

        sheet = SafetyDataSheet(
            product_identifier=product_identifier,
            issue_date=issue_date,
            revision_date=revision_date,
            version=version,
            language=self.language,
            hazard_statements=hazards,
            contact_info=contact_info,
            section_text=sections,
            countries=sheet_countries(
                extraction.text, sections.get(Section.IDENTIFICATION, "")
            ),
            stated_classification=stated,
            stated_voluntary=says_voluntary(extraction.text),
            stated_article=says_article(extraction.text),
        )

        return ParsedSheet(sheet=sheet, warnings=warnings)


def read_numbered_section_heading(line: str) -> int | None:
    """Return the section number of a plainly numbered heading, else None.

    Recognises "2. Mögliche Gefahren", "2: Mögliche Gefahren" and "2 Mögliche
    Gefahren", the forms that carry no "Abschnitt" for SECTION_HEADER_PATTERN
    to find. The title must
    agree with the number: see SECTION_TITLE_PATTERNS for why the number alone
    is not enough.
    """
    match = NUMBERED_SECTION_PATTERN.match(line)
    if match is None:
        return None
    number = int(match.group(1))
    title_pattern = SECTION_TITLE_PATTERNS.get(number)
    if title_pattern is not None and title_pattern.search(match.group(2)):
        return number
    # The order before REACH (SDB-1): the composition was section 2 and the
    # hazards section 3. The title says which section it is.
    swapped = _ORDER_BEFORE_REACH.get(number)
    if swapped is not None and SECTION_TITLE_PATTERNS[swapped].search(match.group(2)):
        return swapped
    return None


_ORDER_BEFORE_REACH = {2: 3, 3: 2}


def _merge_split_headings(lines: list[str]) -> list[str]:
    """Join a heading whose number and title landed on separate lines.

    Only when the join reads as a heading afterwards -- the title still has to
    agree with the number, exactly as it does on one line. A bare "2" followed
    by a table value stays two lines, which is what keeps this from eating the
    commonest line in a data sheet.
    """
    merged: list[str] = []
    i = 0
    while i < len(lines):
        current = lines[i].strip()
        if BARE_SECTION_NUMBER_PATTERN.match(current):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                candidate = f"{current.rstrip('.').strip()} {lines[j].strip()}"
                if read_numbered_section_heading(candidate) is not None:
                    merged.append(candidate)
                    i = j + 1
                    continue
        merged.append(lines[i])
        i += 1
    return merged


def _read_section_heading(line: str) -> tuple[int, str | None, bool] | None:
    """The section number a heading line opens, the text after it on the same
    line, and whether the line carries its section's title.

    A plainly numbered heading always does: read_numbered_section_heading
    accepts it only with the title.
    """
    number = read_numbered_section_heading(line)
    if number is not None:
        return number, None, True
    match = SECTION_HEADER_PATTERN.search(line)
    if match is None:
        return None
    number = int(match.group(1))
    remainder = SECTION_HEADER_PATTERN.sub("", line, count=1).strip(" :")
    title_pattern = SECTION_TITLE_PATTERNS.get(number)
    titled = bool(title_pattern and title_pattern.search(remainder))
    if not titled and remainder[:1].islower():
        # A sentence that wraps before the word: "… ist der volle Wortlaut in"
        # / "Abschnitt 16 zu finden." is a reference, whatever its number.
        return None
    if not titled and re.match(r"[.,]\s?\d", remainder):
        # A subsection's number with no title: "Abschnitt 7.3 angegeben",
        # the end of a sentence that refers to it (SDB-21).
        return None
    return number, remainder, titled


def split_sections(text: str) -> dict[Section, str]:
    """Split normalised SDS text into section buckets.

    A heading numbered below a section already begun in the same sheet, and
    without its own section's title, is a line of the section it stands in
    (SDB-21). One supplier's sheets close with a change list whose every line opens
    "ABSCHNITT 2 gelöscht: P405 …"; read as headings, they put the deleted
    statements back into section 2 -- into the parser's statement text and into
    what the model is shown.

    The title is what keeps the rule from going further. Sections do not
    reliably come in order: a line opening "Abschnitt 8 zu geeigneten
    Materialien …" in section 6 is a reference, not a heading, and two-column
    layouts reach the text layer as "6, 8, 7, 9". Ignoring every heading below
    the highest so far emptied 519 sections of 603 sheets. Section 1
    begins the next sheet, as in _split_sheets, whose section 2 is a section 2
    again.
    """

    sections: dict[Section, list[str]] = {}
    current_section: Section | None = None
    highest = 0

    lines = text.split("\n")
    merged_lines = _merge_split_headings(_merge_broken_pairs(lines))
    seen: set[int] = set()
    before = ""

    for index, line in enumerate(merged_lines):
        stripped = line.strip()
        if not stripped:
            if current_section is not None:
                sections.setdefault(current_section, []).append("")
            continue

        heading = _read_section_heading(stripped)
        if heading is not None and _ends_a_reference(
            heading, before, merged_lines[index + 1 :]
        ):
            heading = None
        before = stripped
        if heading is not None:
            section_number, remainder, titled = heading
            if section_number == 1 and highest >= 2:
                highest = 0
            if section_number >= highest or titled:
                highest = max(highest, section_number)
                current_section = SECTION_BY_NUMBER.get(section_number, Section.OTHER)
                seen.add(section_number)
                if remainder:
                    sections.setdefault(current_section, []).append(remainder)
                continue

        subsection = SUBSECTION_PATTERN.match(stripped)
        if subsection:
            section_number = int(subsection.group(1))
            if (
                section_number not in seen
                and highest <= section_number
                and SUBSECTION_TITLES[section_number].search(subsection.group(3))
            ):
                current_section = SECTION_BY_NUMBER[section_number]
                seen.add(section_number)
                highest = section_number
                sections.setdefault(current_section, []).append(stripped)
                continue

        if current_section is None:
            # skip preamble until the first recognised section appears
            continue

        sections.setdefault(current_section, []).append(stripped)

    return {
        section: "\n".join(filter(None, lines)).strip()
        for section, lines in sections.items()
        if lines
    }


def _ends_a_reference(
    heading: tuple[int, str | None, bool], before: str, after: list[str]
) -> bool:
    """Whether a heading line without its title ends the sentence above it
    (SDB-21): "… finden sich unter" / "Abschnitt 16." / "2.2 Kennzeichnungs-
    elemente".

    Only "Abschnitt n" with a full stop or nothing behind it, under a line that
    breaks off after a lower-case word, and not over its section's title or one
    of its subsections: "Abschnitt 16." / "Sonstige Angaben" is a heading.
    """
    number, remainder, titled = heading
    if titled or remainder not in ("", ".") or not _OPEN_SENTENCE.search(before):
        return False
    below = next((line.strip() for line in after if line.strip()), "")
    title = SECTION_TITLE_PATTERNS.get(number)
    return not (
        (title is not None and title.search(below))
        or re.match(rf"0?{number}\.\d", below)
    )


# A line that breaks off in the middle of a sentence: after a lower-case word.
_OPEN_SENTENCE = re.compile(r"\b[a-zäöüß]+$")


def find_label_section(text: str) -> str | None:
    """Return the text of section 2.2 (Kennzeichnungselemente), if present.

    Returns None when the heading is absent, which leaves the caller on its
    previous source rather than guessing at a block.
    """

    start = LABEL_SECTION_START_PATTERN.search(text)
    if start:
        rest = text[start.end() :]
        end = _label_section_end(rest)
        block = rest[: end.start()] if end else rest[:LABEL_SECTION_MAX_CHARS]
        return block or None

    # No "2.2". The heading may still be there under another number, which is
    # how sheets from before the REACH restructuring are written. Those are
    # taken only when a section boundary actually follows.
    #
    # The cap is not good enough here. Sheets in that shape often have no
    # recognisable heading after the label at all, and the block then runs 3500
    # characters into the ingredient table -- where H-statements belong to the
    # raw materials, not to the product. Measured, four sheets would have
    # reported H304 as their label while their label says "Kennzeichnung
    # entfällt". A block with no boundary is worth less than no block.
    heading = LABEL_HEADING_PATTERN.search(text)
    if not heading:
        return None
    rest = text[heading.end() :]
    end = _label_section_end(rest)
    if not end:
        return None
    return rest[: end.start()] or None


def _label_section_ends(rest: str) -> Iterator[re.Match[str]]:
    """What LABEL_SECTION_END_PATTERN.finditer(*rest*) gives, each line read once.

    A boundary by "Sonstige Gefahren" behind marks begins, in the pattern, at
    the first of the lines of nothing but marks above it that follow the
    previous boundary. Those lines are found here going up from the boundary's
    own line, and the pattern then matches from the first of them.
    """
    done = 0
    for found in _LABEL_SECTION_END_IN_LINE.finditer(rest):
        first = found.start()
        while first > done:
            above = rest.rfind("\n", 0, first - 1) + 1
            if above < done or not _MARKS_LINE.fullmatch(rest, above, first - 1):
                break
            first = above
        if first > done:
            above = rest.rfind("\n", 0, first - 1) + 1
            if above >= done and _BULLET_MARKS_LINE.fullmatch(rest, above, first - 1):
                first = above
        if first < found.start():
            across = LABEL_SECTION_END_PATTERN.match(rest, first)
            if across is not None:
                found = across
        yield found
        done = found.end()


def _label_section_end(rest: str) -> re.Match[str] | None:
    """The first boundary in *rest* that is a heading, not a version number.

    See VERSION_KEY_PATTERN. A boundary always begins a line, so the line before
    it is whatever *rest* holds up to it, read back to the last line break.
    """
    for end in _label_section_ends(rest):
        preceding = rest[: end.start()].rstrip().rpartition("\n")[2]
        if VERSION_KEY_PATTERN.fullmatch(preceding.strip()):
            continue
        if _BARE_2_3.match(end.group(0)) and _LABEL_ELEMENT_TITLE.match(
            rest[end.end() :].lstrip()
        ):
            continue
        return end
    return None


# "2.3" as the number of a label element, not of "Sonstige Gefahren" (SDB-4):
# a sheet numbers its label's parts on, "2.2 Kennzeichnungselemente", "2.3
# Gefahrbestimmende Komponenten …", "2.4 Gefahrenhinweise", "2.5
# Sicherheitshinweise", and the label ended before its statements.
_BARE_2_3 = re.compile(r"[ \t]*(?:[·•∙][ \t]*)?2\s*\.\s*3\b")
_LABEL_ELEMENT_TITLE = re.compile(
    r"(?:Gefahrbestimmende\s+Komponente|Gefahrenhinweis|Sicherheitshinweis"
    r"|Signalwort|Gefahrenpiktogramm|Piktogramm|Ergänzende|Besondere\s+Kennzeichnung)",
    re.IGNORECASE,
)


def _parts_with_labels(text: str) -> list[tuple[str, str | None]]:
    """Every part _split_sheets cuts *text* into, with its label if it has one.

    The one place that decides how many sheets a file holds (SDB-2): the
    parts that carry a label of their own and are a sheet (_is_no_sheet); a
    part that is none comes back without its label.

    One PDF can hold several complete sheets, one after another. Suppliers ship them
    for products that contain more than one chemical: a combination pack of two
    plant protection products, a two-component adhesive, a mortar with its
    hardener. 18 files in the corpus are built that way, for 13 products. Reading
    only the first label put half a product's hazards on it: a combination
    pack showed the insecticide's H411 and lost the fungicide's H410.

    Every sheet is searched on its own, so a sheet's label ends where that
    sheet's section 2.3 does. A document holding one sheet gives exactly the
    block find_label_section returns for it -- measured over all 3232
    documents, the first block is unchanged on every one of them.
    """
    pairs = [(part, find_label_section(part)) for part in _split_sheets(text)]
    sheets = [
        label is not None and not _is_no_sheet(part, label) for part, label in pairs
    ]
    if not any(sheets):
        # Nothing here is a sheet by these signs: the labels stand as found.
        return pairs
    return [
        (part, label if sheet else None)
        for (part, label), sheet in zip(pairs, sheets, strict=True)
    ]


def _section_number(line: str) -> int | None:
    """The number of the section *line* heads, in either way of writing it."""
    stripped = line.strip()
    number = read_numbered_section_heading(stripped)
    if number is not None:
        return number
    match = SECTION_HEADER_PATTERN.search(stripped)
    return int(match.group(1)) if match else None


# A heading of section 1 in another language: "SECTION 1: Identification of
# the substance/mixture …". "Section" with the German title is a German
# heading.
_FOREIGN_SECTION_1 = re.compile(
    r"^\W{0,6}(?:\d{1,2}\W{1,3})?s\s*e\s*c\s*t\s*i\s*o\s*n\s+0?1\b(.*)$",
    re.IGNORECASE,
)
# How many headings in a row make a list of sections.
SECTION_LIST_LINES = 3


def _is_no_sheet(part: str, label: str) -> bool:
    """Whether a part with a label's heading is still no sheet (SDB-2).

    Two kinds in the corpus. A list of changes at the end of section 16
    names the sections it changed one below the other -- "Abschnitt 1: UFI /
    Abschnitt 2: Einstufung/Kennzeichnungselemente / Abschnitt 3: …": that
    names the label's heading and holds no label. And the same sheet once
    more in another language, opened by "SECTION 1: Identification …": the
    reader reads German sheets.
    """
    lines = [line.strip() for line in part.split("\n") if line.strip()]
    for line in lines:
        if _section_number(line) != 1:
            continue
        foreign = _FOREIGN_SECTION_1.match(line)
        if foreign and not SECTION_TITLE_PATTERNS[1].search(foreign.group(1)):
            return True
        break
    if label.strip():
        return False
    run = 0
    for line in lines:
        run = run + 1 if _section_number(line) is not None else 0
        if run >= SECTION_LIST_LINES:
            return True
    return False


# What a cover page in front of a file's sheets is titled, at a line's start
# (SDB-138): "Deckblatt", "Deckblatt zum Sicherheitsdatenblatt", "Kit
# Sicherheitsinformationsblatt", "Sicherheitsdatenblätter für Kombi-Produkte",
# "Set aus Sicherheitsdatenblättern bestehend aus:", "Setbestandteile".
_COVER_TITLE = re.compile(
    r"^\W*(?:Deckblatt\b|Kit[- ]?Sicherheits(?:informations|daten)blatt\b"
    r"|Sicherheitsdatenbl(?:ä|ae)tter\b"
    r"|Set\s+(?:aus|von)\s+Sicherheitsdatenbl(?:ä|ae)ttern\b|Setbestandteile\b)",
    re.IGNORECASE,
)
# A word that names a display, the unit a supplier ships to be set up in a
# shop: "Mix-Display", "Mixdisplay". Starting only where a word starts finds
# the same word and reads a long one once (see _EMAIL).
_DISPLAY_TERM = re.compile(r"(?<![\w-])[\w-]*display[\w-]*", re.IGNORECASE)


def split_cover_page(text: str) -> tuple[str, str]:
    """The cover page in front of *text*'s sheets, and the text behind it (SDB-138).

    A cover page is titled as one (_COVER_TITLE) among the first
    SHEET_TOP_LINES lines with text, and ends where the first sheet begins:
    at the top (_sheet_top) of the first heading of section 1 that is not
    the cover page's own. A cover page may head a section 1 itself, "Kit
    Identifizierung" or a country's additions: that heading is its own where
    the cover's title is the nearest title above it. Without such a title,
    or without a sheet behind it, there is no cover page and *text* comes
    back whole. The two joined by a line break are *text* again.
    """
    lines = text.split("\n")
    titled = None
    seen = 0
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        seen += 1
        if seen > SHEET_TOP_LINES:
            break
        if _COVER_TITLE.match(line):
            titled = index
            break
    if titled is None:
        return "", text
    for index in range(titled + 1, len(lines)):
        if _section_number(lines[index]) != 1:
            continue
        top = _sheet_top(lines, index, titled)
        if _nearest_title_is_the_cover_s(lines, index, top):
            continue
        return "\n".join(lines[:top]), "\n".join(lines[top:])
    return "", text


def _nearest_title_is_the_cover_s(lines: Sequence[str], heading: int, top: int) -> bool:
    """Whether the heading in line *heading* is a cover page's own.

    *top* is where _sheet_top puts the heading's sheet: the heading itself
    where no sheet's title stands above it. Then the cover's title among
    the lines right above makes it the cover's.
    """
    if top != heading:
        return False
    seen = 0
    for index in range(heading - 1, -1, -1):
        if not lines[index].strip():
            continue
        seen += 1
        if seen > SHEET_TOP_LINES:
            return False
        if _COVER_TITLE.match(lines[index]):
            return True
    return False


def _display_term(cover: str) -> str | None:
    """The first word on the cover page that names a display, as printed."""
    found = _DISPLAY_TERM.search(cover)
    return found.group(0).strip("-_") if found else None


def split_into_sheets(text: str) -> list[str]:
    """The text of every safety data sheet *text* holds, in its order (SDB-2).

    A cover page in front of the sheets is none of them and is left out
    (SDB-138). As many as _parts_with_labels finds labels, and at least one:
    a file with fewer than two labelled parts is one sheet and comes back
    whole. A part without a label is no sheet of its own -- a list of
    revisions that names "Abschnitt 1" at the end of section 16 -- and stays
    with the sheet before it, or with the first sheet where it stands before
    that. The sheets joined by line breaks are *text* again, without its
    cover page.
    """
    text = split_cover_page(text)[1]
    parts = _parts_with_labels(text)
    if sum(label is not None for _, label in parts) < 2:
        return [text]
    sheets: list[list[str]] = []
    labelled = False
    for part, label in parts:
        if sheets and not (labelled and label is not None):
            sheets[-1].append(part)
            labelled = labelled or label is not None
        else:
            sheets.append([part])
            labelled = label is not None
    return ["\n".join(sheet) for sheet in sheets]


def _split_sheets(text: str) -> list[str]:
    """Cut *text* where a further safety data sheet begins.

    A sheet begins where section 1 is headed after a later section has been,
    at the top of that heading's page as far as the text shows it (_sheet_top).
    Section 1 coming round again is not enough on its own: four single sheets
    in the corpus list their revisions at the end of section 16 --
    "Änderungen mit Version 1.2: / Abschnitt 1: Handelsname" -- which is why the
    caller counts only the parts that carry a label of their own. The cut is
    made between lines, so the parts join back into *text* exactly.
    """
    lines = text.split("\n")
    starts = [0]
    highest = 0
    for index, line in enumerate(lines):
        number = _section_number(line)
        if number is None:
            continue
        if number == 1 and highest >= 2:
            starts.append(_sheet_top(lines, index, starts[-1]))
            highest = 0
        highest = max(highest, number)
    bounds = [*starts, len(lines)]
    return ["\n".join(lines[start:end]) for start, end in pairwise(bounds)]


# The title a sheet prints at the top of its first page, at a line's start.
_SHEET_TITLE = re.compile(r"^\W*(?:E[GU]-)?Sicherheitsdatenblatt", re.IGNORECASE)
# How many lines with text above a heading of section 1 can be its page's top.
SHEET_TOP_LINES = 12


def _sheet_top(lines: Sequence[str], heading: int, floor: int) -> int:
    """Where the sheet begins whose section 1 is headed in line *heading* (SDB-2).

    A sheet prints its title, its product and its dates above section 1, at
    the top of its first page. The text holds no page boundaries, so the top
    is the nearest line above the heading that begins with the title, among
    the SHEET_TOP_LINES lines with text right above it and not before
    *floor*; else the heading itself.
    """
    seen = 0
    for index in range(heading - 1, floor, -1):
        if not lines[index].strip():
            continue
        seen += 1
        if seen > SHEET_TOP_LINES:
            break
        if _SHEET_TITLE.match(lines[index]):
            return index
    return heading


def read_signal_word(label_text: str) -> tuple[str | None, bool]:
    """Read the signal word out of a label section.

    Returns the word and whether the label said anything about it at all. Three
    answers, and only the last of them is silence:

    * ``("Gefahr", True)``  -- the label prints it
    * ``(None, True)``      -- the label states that it has none, either of the
      signal word specifically or of the whole label
    * ``(None, False)``     -- the label is silent, and the caller may fall back

    The negations are tested first, because a sheet that states an absence can
    still carry the word elsewhere in the block: one sheet prints "Signalwort
    entfällt" and then "Achtung" 570 characters later in an unrelated sentence.
    The statement anchored to the label wins.

    Shared with the service layer so that "the label has settled this" means one
    thing in both places rather than two regexes drifting apart.
    """
    negations = [
        found.start()
        for pattern in (NO_SIGNAL_WORD_PATTERN, UNLABELLED_PATTERN)
        if (found := pattern.search(label_text))
    ]
    # A word set behind its own label before any negation is the label's
    # (SDB-176): "Signalwort: Achtung" for the product as sold, and further
    # down "kein Signalwort … erforderlich" for it diluted for use.
    named = _SIGNAL_WORD_NAMED.search(label_text)
    if named and (not negations or named.start() < min(negations)):
        return named.group(1).capitalize(), True
    if negations:
        return None, True

    match = SIGNAL_WORD_PATTERN.search(label_text)
    if match:
        # Normalise "GEFAHR" to "Gefahr": the value is displayed, and the
        # sheet's typography is not part of the classification.
        raw = _clean_value(match.group(1))
        return (raw.capitalize() if raw else raw), True

    return None, False


# A joined code whose cell is too narrow for it (SDB-121): the code breaks
# inside its last number, the rest of the number alone on the next line.
#   P305+P351+P33 BEI KONTAKT MIT DEN AUGEN: … Eventuell vorhandene
#   8
#   Kontaktlinsen nach Möglichkeit entfernen. Weiter spülen.
_BROKEN_CODE = re.compile(
    r"(?m)^([^\S\n]*(?:[HP]\d{3}[^\S\n]*\+[^\S\n]*)+[HP])(\d{1,2})(?!\d)([^\n]*)\n"
    r"[^\S\n]*(\d{1,2})[^\S\n]*$"
)


# "EUH 208" for EUH208 (SDB-121).
_SPACED_EUH_CODE = re.compile(r"\bEUH[^\S\n](?=\d{3}\b)")

# "H 315", "P 305 + P 351", "H 360 D" for the codes (SDB-164), where they can
# be nothing else. A product's "P 750", a height "H 330 mm" and a table's
# "NOAEL P 250 mg/kg" are not: the number is no statement of the regulation,
# or a word stands before the letter, or neither a separator nor the
# statement's first word follows it.
_SPACED_HP_CODE = re.compile(
    r"(?m)(^[^\S\n]*(?:[•·*\-–][^\S\n]*)?|[+:;,][^\S\n]*)"
    r"([HP])[^\S\n]+(\d{3})(?:[^\S\n]?([FfDd]{1,2}))?(?!\w)"
)
_AFTER_SPACED_CODE = re.compile(r"[^\S\n]*(?:$|[:+,;\-–])", re.MULTILINE)
_FIRST_WORD = re.compile(r"[^\S\n]*([^\W\d_]+)")
# A sentence as the sheet words it, behind a code that opens its line: a
# capital and at least two more letters ("H 226 Entzündliche Flüssigkeit …"),
# not a unit or a dimension ("mm", "x 113").
_SHEETS_SENTENCE = re.compile(r"[^\S\n]+[^\W\d_a-zäöüß][^\W\d_]{2,}")


def _join_spaced_codes(text: str) -> str:
    """*text* with H and P codes printed with a space written as codes (SDB-164)."""
    known = statement_codes()

    def joined(match: re.Match[str]) -> str:
        before, letter, number, effect = match.groups()
        code = letter + number
        if code not in known:
            return match.group(0)
        if effect and code not in ("H360", "H361"):
            return match.group(0)
        in_combination = before.strip() == "+"
        opens_line = not before.strip(" \t•·*-–")
        if not in_combination and not _AFTER_SPACED_CODE.match(text, match.end()):
            word = _FIRST_WORD.match(text, match.end())
            own_wording = word is not None and word.group(1).lower() == first_word_of(
                code
            )
            if not own_wording and not (
                opens_line and _SHEETS_SENTENCE.match(text, match.end())
            ):
                return match.group(0)
        return f"{before}{code}{effect or ''}"

    return _SPACED_HP_CODE.sub(joined, text)


def _mend_codes(text: str) -> str:
    """*text* with its statement codes as the regulation writes them (SDB-121,
    SDB-164): a code whole that broke inside its last number, EUH, H and P
    joined to their numbers."""

    def whole(match: re.Match[str]) -> str:
        head, begun, rest, end = match.groups()
        if len(begun) + len(end) != 3:
            return match.group(0)
        return f"{head}{begun}{end}{rest}"

    return _join_spaced_codes(
        _SPACED_EUH_CODE.sub("EUH", _BROKEN_CODE.sub(whole, text))
    )


def _without_the_old_directives_phrase(text: str) -> tuple[str, list[str]]:
    """*text* without the Preparations Directive's sentence that a safety data
    sheet is to be had on request, and the sentences taken out (SDB-123): it
    is no statement of CLP and gets no code; the caller keeps it as printed.
    """
    taken = [" ".join(found.split()) for found in OLD_REQUEST_SENTENCE.findall(text)]
    return OLD_REQUEST_SENTENCE.sub("", text), taken


# The blocks of 2.2 beside the label (SDB-188 to SDB-190). The heading of a
# small package's label is label_blocks.py's, which the drawing shares.
#
# A sentence that says what a small package leaves out (SDB-189):
# "Reduzierte Kennzeichnung <= 125 ml: H225 und H319 entfallen. …", "Nach
# 1272/2008/EG I, 1.5.2 keine Kennzeichnung bei Gebinden < 125ml mit: H225, …".
_SMALL_PACKAGE_OMITS = re.compile(
    r"Reduzierte\s+Kennzeichnung\s*(?:<=|≤|<)\s*125\s*ml\s*:"
    r"|keine\s+Kennzeichnung\s+bei\s+Gebinden\s*(?:<=|≤|<)\s*125\s*ml\b",
    re.IGNORECASE,
)
# A code list's shorthand combination: "P303+361+353" is P303, P361 and P353.
_SHORTHAND_COMBINATION = re.compile(r"\b(EUH|[HP])(\d{3})((?:\s*\+\s*\d{3}(?!\d))+)")
# What a small package's label shares with the product's (SDB-188).
_FOR_ALL_SIZES = re.compile(
    r"\(\s*f(?:ü|ue)r\s+alle\s+Verpackungsgr(?:ö|oe)(?:ß|ss)en\s*\)", re.I
)
# The heading of a block under another regulation (SDB-190), on a line of its
# own after any bullets, and what its block says it is.
_LINE_MARKS = re.compile(r"^[ \t·•∙*\-]*")
_OTHER_REGULATION_HEADINGS = (
    (
        LabelKind.BIOCIDES,
        re.compile(
            r"(?:Biozid-?\s*Kennzeichnung"
            r"|Kennzeichnung\s+gem(?:\.|äß|aess)\s+Verordnung\s+\((?:EU|EG)\)\s+Nr\.\s*528/2012"
            r"|Verordnung\s+\((?:EU|EG)\)\s+Nr\.\s*528/2012\s+über\s+Biozidprodukte)"
            r"[\s:*]*",
            re.IGNORECASE,
        ),
    ),
    (
        LabelKind.DETERGENTS,
        re.compile(
            r"(?:Etikettierung\s+von\s+Wasch-?\s*(?:und|u\.)\s*Reinigungsmitteln"
            r"|Inhaltsstoffe\s+nach\s+Detergenzienverordnung\s+(?:\(?EG\)?\s+)?(?:Nr\.\s*)?648/2004"
            r"|Kennzeichnung\s+der\s+Inhaltsstoffe\s+gem(?:äß|aess)\s+Verordnung\s+\(EG\)"
            r"\s+Nr\.\s*648/2004(?:\s*,\s*Anhang\s+VII)?"
            r"|Zus(?:ä|ae)tzliche\s+Angaben\s+gem(?:äß|aess)\s+Verordnung\s+\(EG\)\s+Nr\.\s*"
            r"648/2004(?:\s*\([^()\n]*\))?)"
            r"[\s:*]*",
            re.IGNORECASE,
        ),
    ),
)
# What ends such a block (SDB-190): a line beginning with a code, and the name
# of an element of the label.
_STARTS_WITH_CODE = re.compile(r"^\W*(?:EUH|[HP])\s?\d{3}(?!\d)", re.IGNORECASE)
_LABEL_ELEMENT_LINE = re.compile(
    r"^[ \t·•∙*\-]*(?:"
    r"(?:Zus(?:ä|ae)tzliche|Erg(?:ä|ae)nzende)[\s:]*$"
    r"|(?:(?:Zus(?:ä|ae)tzliche|Erg(?:ä|ae)nzende)\s+)?(?:Signalw|Gefahren-?\s*piktogramm"
    r"|Piktogramm|Gefahrenhinweis|Sicherheitshinweis|[HP]\s*-\s*S(?:ä|ae)tze"
    r"|EUH\s*-\s*S(?:ä|ae)tze))",
    re.IGNORECASE,
)


@dataclass(slots=True)
class _Block:
    """A block of 2.2 beside the label, as the parser cut it (SDB-188 to SDB-190)."""

    kind: LabelKind
    heading: str
    # Its lines as printed, without the heading.
    lines: list[str] = field(default_factory=list)
    # The lines that are its own: not shared with the label (SDB-188), with
    # the heading. These leave section 2 when the label's texts are cut.
    own: list[str] = field(default_factory=list)
    # A sentence of SDB-189: the codes it says a small package leaves out.
    omitted: list[str] | None = None


def _other_regulation_heading(
    lines: Sequence[str], index: int
) -> tuple[LabelKind, str, int] | None:
    """The kind and heading of a block under another regulation that begins at
    *lines[index]*, and how many lines its heading takes (SDB-190)."""
    first = _LINE_MARKS.sub("", lines[index]).strip()
    candidates = [(first, 1)]
    if index + 1 < len(lines) and lines[index + 1].strip():
        candidates.append((f"{first} {lines[index + 1].strip()}", 2))
    for text, taken in candidates:
        for kind, pattern in _OTHER_REGULATION_HEADINGS:
            if pattern.fullmatch(text):
                return kind, text.rstrip(" :*").strip(), taken
    return None


def omitted_codes(sentence: str) -> list[str]:
    """The codes a sentence of SDB-189 names, one by one, a shorthand
    combination ("P303+361+353") as its parts.

    >>> omitted_codes("H225, H319, P210, P303+361+353, P305+351+338")
    ['H225', 'H319', 'P210', 'P303', 'P305', 'P338', 'P351', 'P353', 'P361']
    """
    codes = set(_ANY_STATEMENT_CODE.findall(sentence))
    for letters, first, rest in _SHORTHAND_COMBINATION.findall(sentence):
        codes.add(f"{letters}{first}")
        codes.update(f"{letters}{number}" for number in re.findall(r"\d{3}", rest))
    return sorted(code.upper() for code in codes)


def _page_furniture_line(line: str, furniture: frozenset[str]) -> bool:
    """Whether *line* is the page's, not the label's: a running head, a page
    number, a line repeated on the pages."""
    text = line.strip()
    return bool(text) and (
        text in furniture
        or bool(_PAGE_NUMBER.match(text))
        or bool(_CONTINUED.fullmatch(text))
        or bool(_RUNNING_HEAD.search(text))
    )


def split_label_blocks(
    label: str, furniture: frozenset[str] = frozenset()
) -> tuple[str, list[_Block]]:
    """*label* without the blocks beside it, and those blocks in its order
    (SDB-188 to SDB-190).

    A small package's label runs to the next such heading or the label's end;
    a block under another regulation interrupts it, and what follows "(für
    alle Verpackungsgrößen)" belongs to the label as well. A block under
    another regulation ends before an empty line, a line beginning with a
    code, the name of a label element or another heading; a page break, the
    lines of *furniture* and the empty lines among them, ends none. A
    sentence naming what a small package leaves out is a block of its own.
    """
    lines = label.split("\n")
    main: list[str] = []
    blocks: list[_Block] = []
    small: _Block | None = None
    other: _Block | None = None
    shared = False
    page_break = False
    index = 0
    while index < len(lines):
        line = lines[index]
        heading_other = _other_regulation_heading(lines, index)
        if other is not None and (
            _page_furniture_line(line, furniture) or (page_break and not line.strip())
        ):
            page_break = True
            other.own.append(line)
            index += 1
            continue
        page_break = False
        if other is not None:
            if (
                not line.strip()
                or _STARTS_WITH_CODE.match(line)
                or _LABEL_ELEMENT_LINE.match(line)
                or SMALL_PACKAGE_HEADING.match(line)
                or heading_other is not None
            ):
                other = None
            else:
                other.lines.append(line)
                other.own.append(line)
                index += 1
                continue
        if SMALL_PACKAGE_HEADING.match(line):
            heading = [_LINE_MARKS.sub("", line).strip()]
            # A heading that runs on: "… 125 ml und es technisch unmöglich
            # ist um alle Sätze" / "aufzulisten:".
            while index + 1 < len(lines) and re.match(
                r"\s*[a-zäöüß]", lines[index + 1]
            ):
                index += 1
                heading.append(lines[index].strip())
            small = _Block(LabelKind.SMALL_PACKAGE, " ".join(heading), own=[line])
            blocks.append(small)
            shared = False
            index += 1
            continue
        if heading_other is not None:
            kind, title, taken = heading_other
            other = _Block(kind, title, own=lines[index : index + taken])
            blocks.append(other)
            index += taken
            continue
        if _SMALL_PACKAGE_OMITS.search(line):
            sentence = [line]
            while sentence[-1].rstrip().endswith(",") and index + 1 < len(lines):
                index += 1
                sentence.append(lines[index])
            text = " ".join(part.strip() for part in sentence)
            blocks.append(
                _Block(
                    LabelKind.SMALL_PACKAGE,
                    _LINE_MARKS.sub("", text).strip(),
                    own=sentence,
                    omitted=omitted_codes(text),
                )
            )
            index += 1
            continue
        if small is not None and _FOR_ALL_SIZES.search(line):
            shared = True
        if small is None or shared:
            main.append(line)
        if small is not None:
            small.lines.append(line)
            if not shared:
                small.own.append(line)
        index += 1
    return "\n".join(main), blocks


# The label's own condition (SDB-191): "Obige Kennzeichnung gilt bei Abgabe
# an privaten Endverbraucher."
_LABEL_FOR_CONSUMERS = re.compile(
    r"Obige\s+Kennzeichnung\s+gilt\s+bei\s+Abgabe\s+an\s+private[n]?\s+Endverbraucher\.?",
    re.IGNORECASE,
)
# What begins statements for consumers only (SDB-192), and the end of the
# passage the first one opens: "***Nur für private Endverbraucher: P101 …
# P501 …***".
_FOR_CONSUMERS = re.compile(
    r"Nur\s+f(?:ü|ue)r\s+private\s+Endverbraucher\s*:"
    r"|F(?:ü|ue)r\s+den\s+privaten\s+Endabnehmer\s+steht\s+zus(?:ä|ae)tzlich\s+auf\s+dem"
    r"\s+Etikett\W*:"
    r"|Zus(?:ä|ae)tzliche\s+Angaben\s+auf\s+dem\s+Etikett\s+f(?:ü|ue)r\s+den\s+privaten"
    r"\s+Endabnehmer\s*:",
    re.IGNORECASE,
)
_PASSAGE_CLOSED = re.compile(r"\*{3}\s*$")
# A line that names something, not a sentence going on: "Zusätzliche Angaben
# gemäß Verordnung (EG) Nr. 648/2004 (Detergenzienverodnung):".
_NAMES_A_FIELD = re.compile(r"^[^\S\n]*[A-ZÄÖÜ][^:\n]{2,90}:[^\S\n]*$")
# EUH210 for others than the general public (SDB-192).
_EUH210_NOT_PUBLIC = re.compile(
    r"EUH\s?210\b[^.]{0,200}?\bnicht\s+f(?:ü|ue)r\s+die\s+breite\s+(?:Ö|Oe)ffentlichkeit"
    r"\s+bestimmt"
    r"|EUH\s?210\b[^.]{0,80}?\bdarf\s+entfallen\b[^.]{0,120}?\bbreite\s+(?:Ö|Oe)ffentlichkeit"
    r"|Nicht\s+f(?:ü|ue)r\s+die\s+private\s+Abnahme\s+bestimmte\s+Zubereitungen",
    re.IGNORECASE,
)


def label_condition(label: str) -> tuple[LabelCondition, str] | None:
    """Whom *label* says it applies to, and the sentence that says so (SDB-191)."""
    found = _LABEL_FOR_CONSUMERS.search(label)
    if found is None:
        return None
    return LabelCondition.CONSUMERS, " ".join(found.group(0).split())


def statement_conditions(
    label: str, on_label: Iterable[str]
) -> dict[str, LabelCondition]:
    """The statements of *label* printed with a condition, by code (SDB-192);
    only codes in *on_label*, the codes the label carries."""
    carried = set(on_label)
    found: dict[str, LabelCondition] = {}
    lines = label.split("\n")
    for index, line in enumerate(lines):
        start = _FOR_CONSUMERS.search(line)
        if start is None:
            continue
        passage = [line[start.end() :]]
        closes = "***" in line[: start.start()] or line.lstrip().startswith("*")
        for after in lines[index + 1 :]:
            if closes and _PASSAGE_CLOSED.search(passage[-1]):
                break
            if not after.strip() or _FOR_CONSUMERS.search(after):
                break
            if not closes and (
                _NAMES_A_FIELD.match(after)
                or not (
                    _STARTS_WITH_CODE.match(after)
                    or not _SENTENCE_END.search(passage[-1].rstrip())
                )
            ):
                break
            passage.append(after)
        for code in _ANY_STATEMENT_CODE.findall("\n".join(passage)):
            if code in carried:
                found.setdefault(code, LabelCondition.CONSUMERS)
    if "EUH210" in carried and _EUH210_NOT_PUBLIC.search(re.sub(r"\s+", " ", label)):
        found["EUH210"] = LabelCondition.NOT_GENERAL_PUBLIC
    return dict(sorted(found.items()))


def without_lines(text: str, lines: Sequence[str]) -> str:
    """*text* without the first run of *lines* in it, empty lines aside.

    The label is cut from the file's text, section 2 from its sections, and
    the two do not keep the same empty lines (SDB-196).
    """
    wanted = "\n".join(line.strip() for line in lines if line.strip())
    if not wanted:
        return text
    rows = text.split("\n")
    filled = [i for i, row in enumerate(rows) if row.strip()]
    joined = "\n" + "\n".join(rows[i].strip() for i in filled) + "\n"
    at = joined.find("\n" + wanted + "\n")
    if at == -1:
        return text
    first = joined.count("\n", 0, at)
    gone = set(filled[first : first + wanted.count("\n") + 1])
    return "\n".join(row for i, row in enumerate(rows) if i not in gone)


def _parse_hazard_statements(
    sections: dict[Section, str],
    full_text: str,
    *,
    pages: int,
) -> tuple[HazardStatements, list[Message]]:
    warnings: list[Message] = []
    full_text, _ = _without_the_old_directives_phrase(_mend_codes(full_text))
    old_phrases: list[str] = []
    if Section.HAZARDS in sections:
        hazards_text, old_phrases = _without_the_old_directives_phrase(
            _mend_codes(sections[Section.HAZARDS])
        )
        sections = {**sections, Section.HAZARDS: hazards_text}

    # Prefer the label block. Section splitting mis-assigns the hazards section
    # often enough to matter -- in one sheet it captured section 11 text, so no
    # code was found although every one of them sat in the document -- and even
    # when it lands correctly it spans 2.1 as well, mixing classification
    # statements into the label.
    labelled = [
        (part, label)
        for part, label in (_parts_with_labels(full_text) if full_text else [])
        if label is not None
    ]
    if not labelled and full_text:
        warnings.append(Message(NO_LABEL_SECTION))
    # The blocks beside the label are read apart from it (SDB-188 to SDB-190):
    # the label is what stays, and section 2 loses their lines before the
    # label's texts are cut from it.
    furniture = _page_furniture(full_text, pages)
    blocks: list[_Block] = []
    without_blocks: list[tuple[str, str]] = []
    for part, label in labelled:
        main, found = split_label_blocks(label, furniture)
        without_blocks.append((part, main))
        blocks.extend(found)
    if blocks and Section.HAZARDS in sections:
        hazards_text = sections[Section.HAZARDS]
        for block in blocks:
            hazards_text = without_lines(hazards_text, block.own)
        sections = {**sections, Section.HAZARDS: hazards_text}
    hazard_statements, label_warnings = _read_labels(
        without_blocks, sections, furniture, old_phrases
    )
    if any(w.code == CLASSIFIED_BEFORE_CLP for w in label_warnings):
        # A sheet from before CLP carries no CLP label (_read_labels).
        return hazard_statements, label_warnings
    warnings.extend(label_warnings)
    if labelled:
        # The blocks beside the label have left section 2 (SDB-196).
        warnings.extend(
            _euh_wordings_outside(
                sections.get(Section.HAZARDS, ""),
                [
                    *(main for _, main in without_blocks),
                    *_supplemental_passages(sections.get(Section.HAZARDS, "")),
                ],
                set(hazard_statements.supplemental_codes),
            )
        )
    for _, main in without_blocks:
        condition = label_condition(main)
        if condition is not None and hazard_statements.condition is None:
            hazard_statements.condition, hazard_statements.condition_text = condition
        on_label = {
            *hazard_statements.hazard_codes,
            *hazard_statements.precautionary_codes,
            *hazard_statements.supplemental_codes,
        }
        for code, said in statement_conditions(main, on_label).items():
            hazard_statements.statement_conditions.setdefault(code, said)
    hazard_statements.statement_conditions = dict(
        sorted(hazard_statements.statement_conditions.items())
    )
    for block in blocks:
        further, block_warnings = _further_label(block, furniture)
        _sentences_from_the_label(further.label, hazard_statements)
        hazard_statements.further_labels.append(further)
        warnings.extend(block_warnings)
    return hazard_statements, warnings


# What a small package's label reports of the label's own warnings: the lines
# it does not account for and the statements cut off (SDB-165, SDB-168).
_FURTHER_LABEL_WARNINGS = frozenset({LABEL_LINE_UNASSIGNED, STATEMENT_TOO_LONG})


def _further_label(
    block: _Block, furniture: frozenset[str]
) -> tuple[FurtherLabel, list[Message]]:
    """The reading of a block beside the label (SDB-188 to SDB-190): a small
    package's label is read like a label, from its own lines alone; a block
    under another regulation and a sentence of SDB-189 only as printed."""
    text = (
        "\n".join(
            line for line in block.lines if not _page_furniture_line(line, furniture)
        ).strip("\n")
        or None
    )
    if block.omitted is not None:
        return FurtherLabel(block.kind, block.heading, omitted_codes=block.omitted), []
    further = FurtherLabel(block.kind, block.heading, text=text)
    if block.kind is not LabelKind.SMALL_PACKAGE or text is None:
        return further, []
    label, notes = _read_labels([(text, text)], {Section.HAZARDS: text}, furniture, [])
    on_label = {
        *label.hazard_codes,
        *label.precautionary_codes,
        *label.supplemental_codes,
    }
    label.statement_conditions = statement_conditions(text, on_label)
    further.label = label
    # What it shares with the label is the label's to account for (SDB-188).
    own = {" ".join(line.split()) for line in block.own}
    return further, [
        found
        for found in notes
        if found.code in _FURTHER_LABEL_WARNINGS
        and (found.code != LABEL_LINE_UNASSIGNED or found.params["line"] in own)
    ]


_STATEMENT_TEXTS = ("hazard_text", "precautionary_text", "supplemental_text")


def _worded(texts: Iterable[str | None]) -> dict[str, str]:
    """Each code of *texts* printed with a sentence, and its first such line;
    a combination is one code."""
    worded: dict[str, str] = {}
    for text in texts:
        for line in (text or "").split("\n"):
            statement = STATEMENT_LINE.match(line)
            if (
                statement is not None
                and statement.group(4).strip()
                and not _ONLY_CODES.match(line.strip())
            ):
                code = re.sub(r"\s*\+\s*", "+", statement.group(2)).upper()
                worded.setdefault(code, line.strip())
    return worded


def _sentences_from_the_label(
    further: HazardStatements, label: HazardStatements
) -> None:
    """*further*'s codes printed without a sentence, each with the line the
    label of the same sheet prints for it (SDB-188).

    A row of codes is split at its dashes, commas and semicolons, a
    combination staying one, and each code given once. A code *further*
    prints a sentence for elsewhere keeps that one; a code the label prints no
    sentence for stands alone.
    """
    printed = _worded(getattr(label, name) for name in _STATEMENT_TEXTS)
    own = _worded(getattr(further, name) for name in _STATEMENT_TEXTS)
    for name in _STATEMENT_TEXTS:
        text = getattr(further, name)
        if not text:
            continue
        lines: list[str] = []
        listed: set[str] = set()
        for line in text.split("\n"):
            if not _ONLY_CODES.match(line.strip()):
                lines.append(line)
                continue
            for code in _codes_of(line):
                if code.upper() not in own and code.upper() not in listed:
                    listed.add(code.upper())
                    lines.append(printed.get(code.upper(), code))
        setattr(further, name, "\n".join(lines) or None)


def _read_labels(
    labelled: Sequence[tuple[str, str]],
    sections: dict[Section, str],
    furniture: frozenset[str],
    old_phrases: list[str],
) -> tuple[HazardStatements, list[Message]]:
    """What the labels of *labelled*, each with the text of its sheet, carry
    together (SDB-9); *sections* gives section 2, whose texts the statements
    are cut from."""
    warnings: list[Message] = []
    labels = [label for _, label in labelled]
    if len(labels) > 1:
        warnings.append(Message("several-sheets", {"count": len(labels)}))
    if labels and all(label_before_clp(label) for label in labels):
        warnings.append(Message(LABEL_BEFORE_CLP))

    # Each sheet's label is read as if it stood alone, then the product carries
    # all of them. A combination pack holds both products, so it carries both
    # hazards: such a pack is H410 and H411, not whichever sheet came
    # first. Combining after reading, not before, is what keeps one sheet's
    # "Kein Signalwort" from silencing the other sheet's "Achtung".
    readings = [
        _read_label(label, _classification_referred_to(part, label))
        for part, label in labelled
    ] or [_read_label(sections.get(Section.HAZARDS, ""))]
    for reading in readings:
        warnings.extend(reading.warnings)

    hazard_codes = sorted(set().union(*(r.hazard_codes for r in readings)))
    precautionary_codes = sorted(
        set().union(*(r.precautionary_codes for r in readings))
    )

    if not hazard_codes:
        # A sheet from before CLP states its hazards as R phrases and hazard
        # symbols. Read as a CLP label it yields what it does not say: "R33:
        # Gefahr kumulativer Wirkungen." gave the signal word "Gefahr", and the
        # S phrase "Bei Berührung mit der Haut sofort abwaschen …" the code P302
        # by its wording (SDB-52). Such a sheet carries no CLP label at all.
        old = old_classification(
            "\n".join([sections.get(Section.HAZARDS, ""), *labels])
        )
        if old is not None:
            return HazardStatements(), [Message(CLASSIFIED_BEFORE_CLP, {"basis": old})]
        warnings.append(Message("no-hazard-codes"))
        # Two very different documents reach this line, and reporting has to be
        # able to tell them apart. One states that the product carries no label;
        # the other states that nobody worked out what its label should be. The
        # second is not a product without hazards, it is a sheet without an
        # answer -- and a product resting on one belongs on the list of sheets
        # the supplier owes a replacement for, not in the untroubled majority.
        if any(states_undetermined_labelling(label) for label in labels):
            warnings.append(Message(LABEL_UNDETERMINED))
    if not precautionary_codes:
        warnings.append(Message("no-precautionary-codes"))

    # The label's own block of supplemental elements can stand outside the block
    # read as the label: set in two columns, "Ergänzende Kennzeichnungselemente:
    # Enthält … Kann allergische Reaktionen hervorrufen." reached the text after
    # 2.3 in the file's order on the sheets of four paint brands.
    # In print order (SDB-42) it stands in the label block, and these
    # passages change nothing else (215 sheets before, 0 after);
    # SDB-28 keeps them until the clause is withdrawn.
    supplemental = set().union(*(r.supplemental for r in readings))
    worded_supplemental = [w for r in readings for w in r.worded_supplemental]
    passages = _supplemental_passages(sections.get(Section.HAZARDS, ""))
    if labels and passages:
        beside = euh_statements_by_wording("\n".join(passages), skip=supplemental)
        worded_supplemental.extend(beside)
        supplemental |= {code for code, _ in beside}

    hazard_statements = HazardStatements(
        hazard_codes=hazard_codes,
        precautionary_codes=precautionary_codes,
        supplemental_codes=sorted(supplemental),
        signal_word=_strongest_signal_word(r.signal_word for r in readings),
        pictograms=sorted(set().union(*(r.pictograms for r in readings))),
    )
    # Named in the text; the drawing adds its pictures (reading.py, SDB-211).
    hazard_statements.pictogram_forms = {
        code: ["code"] for code in hazard_statements.pictograms
    }
    # The file's label states none only where every sheet's label does
    # (SDB-176, SDB-180).
    hazard_statements.states_no_signal_word = (
        hazard_statements.signal_word is None
        and all(r.states_no_signal_word for r in readings)
    )
    hazard_statements.states_no_pictograms = all(
        r.states_no_pictograms for r in readings
    )
    # A code one sheet's label prints is printed, even where another sheet of
    # the file only prints its sentence (SDB-174).
    printed_somewhere = set().union(
        *(
            (r.hazard_codes | r.precautionary_codes | r.supplemental) - r.from_wording
            for r in readings
        )
    )
    from_wording = (
        set().union(*(r.from_wording for r in readings))
        | {code for code, _ in worded_supplemental}
    ) - printed_somewhere
    # The text has to say what the codes say. The codes are read off the label;
    # the text is cut from the whole hazards section, which also holds 2.1's
    # classification and, where a heading goes unread, the section 3 ingredient
    # table or the section 16 change log ("gelöscht: Asp. Tox. 1"). Measured over the
    # 1997 current sheets, 102 carried a statement their label does not. On 16
    # the label carries no code at all and the model found none either, so the
    # text went into the output as it was: a filler, "Nicht eingestuft"
    # in 2.1, displayed H330 "Lebensgefahr bei Einatmen" from a preservative
    # below 0.001%. On the other 86 the model's answer covered it.
    #
    # Dropping a hazard statement is the dangerous direction, so the label had
    # to prove itself first: on all 102 every block was found, and the model
    # confirmed a dropped code on two, both H318 beside H314 -- the pair Article
    # 27 lets the label print as H314 alone.
    # The statements cut off at their limit (SDB-168), by the codes they begin with.
    too_long: list[str] = []
    hazard_statements.hazard_text = _statements_within(
        _extract_statements_from_sections(
            sections,
            allowed_sections={Section.HAZARDS},
            pattern=HAZARD_CODE_PATTERN,
            furniture=furniture,
            too_long=too_long,
        ),
        set(hazard_codes),
    )
    # Precautionary text is deliberately not held to the label's codes: P101 and
    # P102 stood behind 2.3 on whole supplier templates, and they are wanted. In
    # print order (SDB-42) the label carries every code of the P text on all
    # 1,991 local sheets, 251 before; SDB-10 keeps the exception until it is
    # withdrawn.
    hazard_statements.precautionary_text = _extract_statements_from_sections(
        sections,
        allowed_sections={Section.HAZARDS},
        pattern=PRECAUTION_CODE_PATTERN,
        furniture=furniture,
        too_long=too_long,
    )
    # A label that prints its statements without their codes (SDB-6) leaves
    # no text to cut; the codes take the sentences they were read from. A
    # line under a code the label only words is 2.1's, not the label's: "H411
    # Aqu. chron. Kat. 2 – …" above "Giftig für Wasserorganismen …".
    codeless = _passages(sections.get(Section.HAZARDS, "").split("\n"), furniture)
    hazard_statements.hazard_text = _with_the_labels_sentences(
        hazard_statements.hazard_text,
        {code for code in hazard_codes if code in from_wording},
        codeless,
    )
    if hazard_statements.hazard_text is None and hazard_codes:
        hazard_statements.hazard_text = _in_print_order(hazard_codes, codeless)
    hazard_statements.precautionary_text = _precautionary_text(
        hazard_statements.precautionary_text,
        precautionary_codes,
        codeless,
        next((r.disposal for r in readings if r.disposal), None),
    )
    supplemental_text = _extract_statements_from_sections(
        sections,
        allowed_sections={Section.HAZARDS},
        pattern=SUPPLEMENTAL_CODE_PATTERN,
        furniture=furniture,
        too_long=too_long,
    )
    # The text is cut from all of section 2, the codes from the label: a
    # statement the text holds under a code the label does not carry is the
    # label's if it is that code's wording, and else no statement (SDB-10).
    if supplemental_text:
        kept: list[str] = []
        for line in supplemental_text.split("\n"):
            code = SUPPLEMENTAL_CODE_PATTERN.match(line)
            if code is None or code.group(0).upper() in supplemental:
                kept.append(line)
            elif any(
                found == code.group(0).upper()
                for found, _ in euh_statements_by_wording(line)
            ):
                kept.append(line)
                supplemental.add(code.group(0).upper())
        supplemental_text = "\n".join(kept) or None
        hazard_statements.supplemental_codes = sorted(supplemental)
        # A code kept by its wording here is printed in the text (SDB-10).
        from_wording -= {
            code.group(0).upper()
            for line in kept
            if (code := SUPPLEMENTAL_CODE_PATTERN.match(line)) is not None
        }
    if supplemental_text:
        supplemental_text = _with_substances_before_the_code(
            supplemental_text, sections.get(Section.HAZARDS, "")
        )
    # On one line with the statement before, the worded one is part of it
    # (SDB-27 stops at a code, and SDB-51 keeps what a wording's own line
    # holds): "EUH210 … auf Anfrage erhältlich. Enthält Linalool. Kann
    # allergische …". The sentence leaves that statement and stands on its own
    # line, with its code.
    for _, sentence in worded_supplemental:
        if supplemental_text:
            supplemental_text = _without_sentence(supplemental_text, sentence)
    worded = [f"{code}: {sentence}" for code, sentence in worded_supplemental]
    # The old directive's request sentence: as printed, under no code (SDB-123).
    hazard_statements.supplemental_text = (
        "\n".join(
            dict.fromkeys([*filter(None, [supplemental_text]), *worded, *old_phrases])
        )
        or None
    )
    on_label = {
        *hazard_statements.hazard_codes,
        *hazard_statements.precautionary_codes,
        *hazard_statements.supplemental_codes,
    }
    hazard_statements.codes_from_wording = sorted(from_wording & on_label)
    _without_trailing_pictograms(hazard_statements)
    hazard_statements.section_16_wordings = _section_16_wordings(
        hazard_statements, sections.get(Section.OTHER, ""), furniture
    )
    warnings.extend(Message(STATEMENT_TOO_LONG, {"codes": codes}) for codes in too_long)
    # What the label holds that nothing above read (SDB-165): a measure of
    # where rules are missing, never a reading.
    warnings.extend(
        Message(LABEL_LINE_UNASSIGNED, {"line": line})
        for line in unassigned_label_lines(labels, hazard_statements, furniture)
    )
    return hazard_statements, warnings


# What a label's line may be besides a statement (SDB-165). A field's own
# name, with nothing behind it that labels: "Gefahrenhinweise:", "Signalwort",
# "Kennzeichnung gemäß Verordnung (EG) Nr. 1272/2008", "Tastbarer Warnhinweis:
# Nicht anwendbar.".
_LABEL_FIELD = re.compile(
    r"^[^\w]*(?:\d(?:\.\d){1,2}\.?\s*)?"
    r"(?:Kennzeichnungselemente|Kennzeichnung|Etikettierung|Etikett"
    r"|Gefahren-?\s*[Pp]iktogramm\w*(?:\(e\))?(?:\s+und\s+Signalwort)?|Piktogramm\w*(?:\s+und\s+Signalwort)?"
    r"|Gefahrensymbol\w*|Symbol\w*|UFI|\(?\s*R\s*-\s*S\s*\)?"
    r"|Kennzeichnung\s+von\s+Verpackungen\b[^\n]*"
    r"|Signalw[oö]rt\w*|Gefahrenhinweis\w*|Gefahrenbezeichnung\w*|[HPR]\s*-\s*S[äa]tze"
    r"|Bestandteil\w*(?:\(e\))?"
    r"|Sicherheitshinweis\w*|P-S[äa]tze|EUH-S[äa]tze"
    r"|(?:Erg[äa]nzende|Zus[äa]tzliche|Besondere|Weitere|Sonstige)\s+\w+(?:\s+\w+){0,6}"
    r"|Gefahr(?:en)?bestimmende\s+Komponente\w*(?:\s+\w+){0,4}"
    r"|Komponente\w*\s+zur\s+Etikettierung"
    r"|Pr[äa]vention|Reaktion|Aufbewahrung|Lagerung|Entsorgung|Allgemein\w*"
    r"|Spezielle\s+Verpackungsanforderungen|Verpackungen?"
    r"|(?:Mit\s+)?kindergesicherte\w*(?:\s+\w+){0,3}|Tastbare\w*\s+Warnhinweis\w*"
    r"|Verschl[üu]ss\w*(?:\s+\w+){0,3}|Beh[äa]lter\s*:?"
    r"|Enth[äa]lt|Gefahrenkategorie\w*|Gefahrenklasse\w*|Einstufung\w*"
    r"|Abschnitt\s*\d{1,2}(?:\.\d)?\s*:?(?:\s*Mögliche\s+Gefahren)?|Mögliche\s+Gefahren"
    r"|Hinweis\w*\s+zur\s+Kennzeichnung|Bemerkung\w*)"
    r"\b(?P<rest>[^\n]*)$",
    re.IGNORECASE,
)
# What may stand behind such a name without labelling anything. Each run of
# marks is read one way. The marks in front are taken whole, and a part that
# could begin with one of them begins behind them instead ("(EU)" by the
# bracket before it); a dash among them is the last one, followed as far as
# such marks go. "(?=(...))\1" takes what the lookahead found and gives none
# of it back. Read otherwise, a long run of commas took seconds, and a run of
# dashes before some words minutes.
_NOTHING_TO_LABEL = re.compile(
    r"^(?:(?=([\s:;,.()\-–/]*-[\s.:;,()-]*))\1[^\n]{0,40}[\s.:;,()\-–]*$"
    r"|(?=([\s:;,.()\-–/]*))\2(?:"
    r"(?:Pr[äa]vention|Reaktion|Aufbewahrung|Lagerung|Entsorgung|Allgemein\w*"
    r"|(?<=\()(?:EU|CLP|GHS)\))"
    r"(?:[\s:;,]+(?:Pr[äa]vention|Reaktion|Aufbewahrung|Lagerung|Entsorgung"
    r"|Allgemein\w*|\((?:EU|CLP|GHS)\)))*"
    r"|[^\n]{0,40}(?:1272/2008|CLP|GHS|Verordnung|Richtlinie)[^\n]{0,60}"
    r"|\*+|gem[äa](?:ß|ss)|nach|UFI"
    r"|(?:nach|gem[äa](?:ß|ss)|entsprechend|laut|according\s+to)\b[^\n]*"
    r"(?:1272/2008|CLP|GHS|Verordnung|Richtlinie)[^\n]*"
    r"|(?:nicht\s+(?:anwendbar|erforderlich|zutreffend|relevant|vorgeschrieben|"
    r"kennzeichnungspflichtig|bekannt|vorhanden)"
    r"|keine?\w*|entf[äa]llt|n\.\s*a)"
    r"(?=([\s.:;,()-]*))\3[^\n]{0,40}"
    r")?[\s.:;,()\-–]*$)",
    re.IGNORECASE,
)
# The signal word's own line, and what the pictograms are called in words.
# The marks before "Signalwort" stand inside its optional group: two classes
# of the same marks in a row would split a line of dashes every way there is.
_SIGNAL_OR_PICTOGRAM_WORDS = re.compile(
    r"^(?:[\s·•\-–]*Signalwort\w*(?:\s*\((?:CLP|GHS)\))?\s*:?)?[\s,;:/·•\-–]*"
    r"(?:(?:Gefahr|Achtung|kein(?:e|es)?|Danger|Warning|Flamme(?:\s+über\s+einem\s+Kreis)?"
    r"|Totenkopf(?:\s+mit\s+gekreuzten\s+Knochen)?|Ausrufezeichen|Ätzwirkung|Gasflasche"
    r"|Umwelt|Gesundheitsgefahr|explodierende\s+Bombe|GHS\s*\d{1,2}|Piktogramm\w*)"
    r"\b[\s,;:/·•\-–.!]*)+$",
    re.IGNORECASE,
)
# A substance's name in a list of the components that determine the label:
# no sentence, at most a short line, often a CAS or EC number.
_SUBSTANCE_LIST_HEAD = re.compile(
    r"Gefahr(?:en)?bestimmende|zur\s+Etikettierung|zur\s+Kennzeichnung|^[^\w]*Enth[äa]lt\b|"
    r"Gef[äa]hrliche\s+(?:Bestandteile|Inhaltsstoffe|Komponenten)|"
    r"Komponenten?\s+f[üu]r\s+die\s+Etikettierung",
    re.IGNORECASE,
)
# What a sheet says about its label instead of labelling (SDB-165): the
# classification stated in words, or a regulation cited on a line of its own.
_LABEL_DECLARATION = re.compile(
    r"\b(?:eingestuft|gekennzeichnet|kennzeichnungspflichtig|einstufungspflichtig"
    r"|Kennzeichnung\s+(?:ist\s+)?(?:nicht\s+)?erforderlich|keine\s+Kennzeichnung"
    r"|nicht\s+(?:gef[äa]hrlich|relevant|erforderlich|anwendbar|zutreffend)"
    r"|kein(?:e|en)?\s+gef[äa]hrlich\w*\s+(?:Stoff|Gemisch|Substanz|Mischung)"
    r"|keine\s+besonderen\b|keine\s+(?:Wirkungen|Gefahren)\s+bekannt"
    r"|keine\s+[HPR]-?S[äa]tze|nach\s+EG-Richtlinien|nationalen\s+Gesetzen"
    r"|kein\s+Gefahrenpiktogramm|entf[äa]llt|Etikettierung\s+gem[äa])",
    re.IGNORECASE,
)
_ONLY_A_REGULATION = re.compile(
    r"^[\s(\[]*(?:(?:EG|EU|EWG)\s*-?\s*)?(?:Verordnung|Richtlinie|VO)\b[^\n]{0,60}$"
    r"|^[\s(\[]*\d{3,4}/\d{4}[\s)\]:.]*$"
    r"|^[\s(\[]*(?:CLP|GHS|REACH)[\s)\]/:]*(?:CLP|GHS)?[\s)\]]*$",
    re.IGNORECASE,
)
# A page's running head that changes from page to page (its page number), and
# a line without a word: neither is the label's.
_RUNNING_HEAD = re.compile(
    r"Sicherheitsdatenblatt\b[^\n]*(?:Seite|Page|1907/2006)|^[\w.-]+\.(?:de|com|at|ch|eu)$",
    re.IGNORECASE,
)
_A_WORD = re.compile(r"[^\W\d_]{4,}")
_CAS_OR_EC = re.compile(r"\b\d{2,7}-\d{2}-\d\b|\b\d{3}-\d{3}-\d\b")


def _comparable_words(text: str) -> str:
    """*text* as lower-case words, for finding one text inside another."""
    return " ".join(re.findall(r"[^\W_]+", text.lower()))


def _read_already(line: str, read: str) -> bool:
    """Whether every sentence of *line* stands in the statements' text *read*."""
    pieces = [
        words
        for piece in re.split(r"[.!;:]\s+|[.!;:]$", line)
        if (words := _comparable_words(piece))
    ]
    return bool(pieces) and all(f" {piece} " in f" {read} " for piece in pieces)


def _holds_a_statement(line: str) -> bool:
    """Whether *line* carries a statement's wording, in any form the parser reads."""
    return bool(
        codes_from_wording(line)
        or euh_statements_by_wording(line)
        or precautionary_by_variants(line)[0]
    )


def _looks_like_substance(line: str) -> bool:
    """Whether *line* reads as a substance's name rather than a sentence."""
    if _CAS_OR_EC.search(line):
        return True
    words = line.split()
    return len(words) <= 8 and not line.rstrip().endswith((".", "!"))


def unassigned_label_lines(
    labels: Sequence[str], hazards: HazardStatements, furniture: frozenset[str]
) -> list[str]:
    """The lines of *labels* that nothing in *hazards* accounts for (SDB-165).

    A line is accounted for when it holds a code or a pictogram's code, is the
    signal word or a pictogram named in words, belongs to a statement the
    reading took (its words stand in that statement's text, or it holds a
    statement's wording), is a field's own name with nothing behind it that
    labels, a name in the list of components that determine the label, page
    furniture, or empty. What is left the parser did not read.
    """
    read = _comparable_words(
        "\n".join(
            filter(
                None,
                [
                    hazards.hazard_text,
                    hazards.precautionary_text,
                    hazards.supplemental_text,
                ],
            )
        )
    )
    left: list[str] = []
    for label in labels:
        in_substances = False
        for raw in join_broken_words(label).split("\n"):
            line = raw.strip()
            words = _comparable_words(line)
            if (
                not words
                or not _A_WORD.search(line)
                or _RUNNING_HEAD.search(line)
                or line in furniture
                or _PAGE_NUMBER.match(line)
                or _CONTINUED.fullmatch(line)
            ):
                continue
            if _SUBSTANCE_LIST_HEAD.search(line):
                in_substances = True
                continue
            if (
                LABEL_HAZARD_CODE.search(line)
                or PRECAUTION_CODE_PATTERN.search(line)
                or SUPPLEMENTAL_CODE_PATTERN.search(line)
                or PICTOGRAM_PATTERN.search(line)
                or _SIGNAL_OR_PICTOGRAM_WORDS.match(line)
            ):
                in_substances = False
                continue
            field_name = _LABEL_FIELD.match(line)
            content = field_name.group("rest") if field_name else line
            if (
                _read_already(content, read)
                or _holds_a_statement(content)
                or _LABEL_DECLARATION.search(line)
                or _ONLY_A_REGULATION.match(line)
                or (field_name and _NOTHING_TO_LABEL.match(content))
            ):
                in_substances = False
                continue
            if in_substances and _looks_like_substance(line):
                continue
            in_substances = False
            left.append(line)
    return left


# EUH208 printed with its code inside the sentence (SDB-125): "Enthält: A, B.
# EUH208 Kann allergische Reaktionen hervorrufen.", or the code on a line of
# its own between the two halves of the name.
_SUBSTANCES_BEFORE_CODE = re.compile(
    # The names end on a character that is not a blank: the blanks before the
    # code are the gap, never part of the names.
    r"(Enthält\b[^\n]*?(?<![^\S\n]))[^\S\n]*(?:\n[^\S\n]*)?EUH208\b",
    re.IGNORECASE,
)
_EUH208_WITHOUT_SUBSTANCES = re.compile(
    r"^EUH208\b(?![^\n]*\bEnth[äa]lt)[^\n]*\S[^\n]*$"
)


def _with_substances_before_the_code(text: str, hazards_text: str) -> str:
    """*text* with what EUH208 names where the sheet prints it before the code.

    The statement is cut from its code on (SDB-27), which leaves "EUH208 Kann
    allergische Reaktionen hervorrufen." without the substances the sentence
    began with. They stand right before the code, on its line or the one above.
    """
    before = _SUBSTANCES_BEFORE_CODE.search(hazards_text)
    if before is None or "hervorrufen" in before.group(1):
        return text
    substances = " ".join(before.group(1).split())
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if _EUH208_WITHOUT_SUBSTANCES.match(line) and line.strip() != "EUH208":
            rest = re.sub(r"^EUH208[^\S\n]*[-:–]?[^\S\n]*", "", line)
            lines[index] = f"EUH208 {substances} {rest}"
            break
    return "\n".join(lines)


# A heading of the label's supplemental elements, and the line that ends what
# follows it: the next numbered heading ("2.3 Sonstige Gefahren").
_SUPPLEMENTAL_HEADING = re.compile(
    r"Ergänzende\s+(?:Kennzeichnungselemente|Gefahrenmerkmale|Gefahrenhinweise|Angaben)"
    r"|Zusätzliche\s+Angaben",
    re.IGNORECASE,
)
_PASSAGE_END = re.compile(
    r"^\s*[·.]?\s*\d{1,2}\.\d{1,2}\.?(?:[^\S\n]+[A-ZÄÖÜ]|[^\S\n]*$)", re.MULTILINE
)
_PASSAGE_LIMIT = 800


def _without_trailing_pictograms(hazards: HazardStatements) -> None:
    """A pictogram's code behind a statement is the label's next element (SDB-27).

    Not the statement's wording: "H335: Kann die Atemwege reizen. GHS07".
    """
    hazards.hazard_text = _without_pictogram(hazards.hazard_text)
    hazards.precautionary_text = _without_pictogram(hazards.precautionary_text)
    hazards.supplemental_text = _without_pictogram(hazards.supplemental_text)


def _without_pictogram(text: str | None) -> str | None:
    return _TRAILING_PICTOGRAM.sub("", text) if text else text


def _precautionary_text(
    text: str | None, codes: list[str], codeless: list[str], disposal: str | None
) -> str | None:
    """The label's precautionary text: *text* as cut by code, else the codes'
    sentences in print order (SDB-6, SDB-163); P501 read off its *disposal*
    sentence (SDB-166) adds the sheet's own words, the other codes find
    theirs as before."""
    worded = [code for code in codes if disposal is None or code != "P501"]
    if text is None and worded:
        text = _in_print_order(worded, codeless) or _in_print_order(
            worded, codeless, variants=True
        )
    if disposal is not None and not re.search(r"\bP501\b", text or ""):
        text = "\n".join(filter(None, [text, f"P501 {disposal}"]))
    return text


def _with_the_labels_sentences(
    text: str | None, worded: set[str], passages: list[str]
) -> str | None:
    """*text* without the lines under codes the label prints only as sentences
    (SDB-6), and with the label's sentences for them instead.

    Such a line is not the label's: the code stands in 2.1 ("H411 Aqu. chron.
    Kat. 2 – …"), and the text cut from section 2 took it with whatever
    followed. Where nothing else is left, the caller takes the sentences in
    print order for every code.
    """
    if not text or not worded:
        return text
    bases = {base_code(code) for code in worded}
    kept = [
        line
        for line in text.split("\n")
        if not (codes := set(HAZARD_CODE_PATTERN.findall(line))) or not codes <= bases
    ]
    if not kept:
        return None
    left = {
        base_code(code) for line in kept for code in HAZARD_CODE_PATTERN.findall(line)
    }
    missing = sorted(code for code in worded if base_code(code) not in left)
    sentences = _in_print_order(missing, passages) if missing else None
    return "\n".join([*kept, *filter(None, [sentences])])


def _in_print_order(
    codes: list[str], passages: list[str], *, variants: bool = False
) -> str | None:
    read = variant_wordings_in_print_order if variants else wordings_in_print_order
    statements = read(codes, passages)
    return "\n".join(statements) if statements else None


# What a line keeps of a code the sheet misprints once its sentence is taken
# from it: "EU208 -" (SDB-186).
_ONLY_A_MARK = re.compile(r"^[\W_]*([A-Za-z]{1,3})\s?(\d{3})[\W_]*$")


def _without_sentence(text: str, sentence: str) -> str:
    """*text* without *sentence*, and without a line it leaves only a mark on
    that is no code of the regulation (SDB-186): "EU208 -" goes, "EUH204:"
    stays."""
    words = re.escape(sentence).split(r"\ ")
    lines = []
    for line in text.split("\n"):
        rest = re.sub(r"[^\S\n]*" + r"\s+".join(words), "", line).rstrip()
        mark = _ONLY_A_MARK.match(rest)
        if (
            rest != line.rstrip()
            and mark
            and f"{mark.group(1).upper()}{mark.group(2)}" not in statement_codes()
        ):
            continue
        lines.append(rest)
    return "\n".join(line for line in lines if line.strip())


def _before_next_subsection(text: str) -> str:
    end = _OTHER_HAZARDS.search(text)
    return text[: end.start()] if end else text


_OTHER_HAZARDS = re.compile(r"^\s*[·•∙.]?\s*2\.3\b", re.MULTILINE)


def _supplemental_passages(hazards_text: str) -> list[str]:
    """What section 2 prints under a heading of supplemental label elements.

    Up to the next numbered heading, at most _PASSAGE_LIMIT characters. One sheet
    prints "Besondere Vorschriften für ergänzende
    Kennzeichnungselemente", then "2.3 Sonstige Gefahren" and under it
    "Wiederholter Kontakt kann zu spröder oder rissiger Haut führen." as an
    effect, not as EUH066: the heading ends the passage before that.
    """
    passages: list[str] = []
    for heading in _SUPPLEMENTAL_HEADING.finditer(hazards_text):
        rest = hazards_text[heading.end() : heading.end() + _PASSAGE_LIMIT]
        end = _PASSAGE_END.search(rest)
        passages.append(rest[: end.start()] if end else rest)
    return passages


_TREATED_ARTICLE = re.compile(
    r"\bbehandelt\w*\s+(?:Ware|Erzeugnis\w*)\s*\.\s*"
    r"Kann\s+allergische\s+Reaktionen\s+hervorrufen\s*\.?",
    re.IGNORECASE,
)
# How far back the sentence about a treated article may begin.
_TREATED_ARTICLE_REACH = 400
_CONTAINS = re.compile(r"\bEnth(?:ä|ae)lt\b", re.IGNORECASE)


def _without_treated_articles(text: str) -> str:
    """*text* without its sentences about a treated article that do not say
    "Enthält" (SDB-196), from the end of the sentence before."""
    kept: list[str] = []
    done = 0
    for found in _TREATED_ARTICLE.finditer(text):
        reach = max(done, found.start() - _TREATED_ARTICLE_REACH)
        before = max(text.rfind(mark, reach, found.start()) for mark in ".!?")
        start = reach if before == -1 else before + 1
        if _CONTAINS.search(text, start, found.end()):
            continue
        kept.append(text[done:start])
        done = found.end()
    kept.append(text[done:])
    return " ".join(kept)


def _euh_wordings_outside(
    hazards_text: str, labels: Sequence[str], on_label: set[str]
) -> list[Message]:
    """An EUH wording section 2 prints only outside the label (SDB-28).

    It does not count -- under 2.3 it can describe an effect rather than label
    one ("Wiederholter Kontakt kann zu spröder oder
    rissiger Haut führen." under "Mögliche schädliche Wirkungen") -- but where
    it stands is the supplier's to put right, so it is reported: one
    sealant prints EUH208 under "2.4 Zusätzliche Hinweise". Not where it runs
    on from other words on its line (SDB-219): that is a description.
    """
    outside = hazards_text
    for label in labels:
        # Line by line: the label and section 2 do not keep the same empty
        # lines (SDB-196).
        outside = without_lines(outside.replace(label, " "), label.split("\n"))
    # A sentence about a treated article is no EUH208 without "Enthält"
    # (SDB-196): "Mit Konservierungsmittel … behandelte Ware. Kann allergische
    # Reaktionen hervorrufen." is Article 58 of Regulation (EU) No 528/2012.
    outside = _without_treated_articles(outside)
    return [
        Message(EUH_WORDING_OUTSIDE_LABEL, {"statement": code, "sentence": sentence})
        for code, sentence in euh_statements_by_wording(
            outside, skip=on_label, partial=True, standing=True
        )
    ]


@dataclass(slots=True)
class _LabelReading:
    """What one sheet's label carries."""

    hazard_codes: set[str]
    precautionary_codes: set[str]
    supplemental: set[str]
    # EUH statements the label prints without their code, as (code, sentence).
    worded_supplemental: list[tuple[str, str]]
    signal_word: str | None
    pictograms: set[str]
    warnings: list[Message]
    # Whether the label states it has no signal word (SDB-176) or no
    # pictogram (SDB-180).
    states_no_signal_word: bool = False
    states_no_pictograms: bool = False
    # The sheet's sentence read as P501 by SDB-166, where the label prints no
    # P501 code.
    disposal: str | None = None
    # The codes the parser assigned to sentences the label prints without
    # them (SDB-174): SDB-6, SDB-28, SDB-163, SDB-166.
    from_wording: set[str] = field(default_factory=set)


def _strongest_signal_word(words: Iterable[str | None]) -> str | None:
    """The stronger word: CLP Article 20(3) never prints Achtung beside Gefahr."""
    present = set(words)
    for word in ("Gefahr", "Achtung"):
        if word in present:
            return word
    return None


def printed_hazard_codes(label_text: str) -> set[str]:
    """The H-codes a label prints as its own, one code per element (SDB-5).

    Codes standing only inside a classification entry are not label elements.
    Measured over the corpus this affects five sheets, and on every one of
    them the removed code is exactly what Article 26 lets the label omit --
    H400 beside H410, H318 beside H314. A code that also appears outside such
    an entry is kept, so a label that really does carry it is unaffected.

    A combination is split into its codes: "H300+H310+H330" is H300, H310 and
    H330. Codes read off the wording (SDB-6) are not printed ones.
    """
    return {
        lettered_code(code)
        for code in LABEL_HAZARD_CODE.findall(CLASSIFICATION_ENTRY.sub(" ", label_text))
    }


# A label that prints R or S phrases (SDB-120): their heading, or a phrase's
# number in brackets behind its sentence ("… gelangen.(S2)").
_OLD_PHRASES_PRINTED = re.compile(
    r"\b[RS][^\S\n]?-[^\S\n]?S[äa]tze\b|\([RS][^\S\n]?\d{1,2}(?:[/-][A-Z\d]{1,3})*\)"
)

# A label that refers to the classification for its hazard statements
# (SDB-119): "Gefahrenhinweis/e: siehe Abschnitt 2.1".
_REFERS_TO_CLASSIFICATION = re.compile(
    r"Gefahrenhinweis(?:/e|e)?[^\S\n]*:?[^\S\n]*siehe[^\S\n]+"
    r"(?:(?:Unter)?[Aa]bschnitt|Punkt|Kapitel|Ziffer)?[^\S\n]*2\.1\b",
    re.IGNORECASE,
)


def _classification_referred_to(part: str, label: str) -> str | None:
    """The classification of the sheet *part*, if its *label* refers to it (SDB-119)."""
    if not _REFERS_TO_CLASSIFICATION.search(label):
        return None
    hazards = split_sections(part).get(Section.HAZARDS, "")
    return "\n".join(_classification_parts(hazards))


# The sentence that sends content and container to disposal (SDB-166):
# "Inhalt/Behälter gemäß lokalen/regionalen/nationalen/internationalen
# Vorschriften entsorgen." -- the supplier's detail, then "entsorgen" or the
# regulation's "zuführen", within one sentence.
_DISPOSAL = re.compile(
    r"\bInhalt\s*(?:/|\bund\b|\boder\b|\bbzw\.?)\s*(?:den\s+|die\s+)?Beh[äa]lter\b"
    r"[^.!?:]{0,160}?\b(?:zu\s+)?(?:entsorgen|zuf[üu]hren)\b\.?",
    re.IGNORECASE,
)


def _disposal_sentence(label_text: str) -> str | None:
    """The label's disposal sentence without its code, as printed (SDB-166).

    Not one behind a code the sheet prints on its line: that sentence is the
    code's, also where the regulation knows no such code ("P502 Inhalt/
    Behälter der Problemabfallentsorgung zuführen.", SDB-166).
    """
    text = join_broken_words(_before_next_subsection(label_text))
    for found in _DISPOSAL.finditer(text):
        line = text[text.rfind("\n", 0, found.start()) + 1 : found.start()]
        if not _ANY_STATEMENT_CODE.search(line):
            return " ".join(found.group(0).split())
    return None


def _read_label(
    hazard_section_text: str, classification: str | None = None
) -> _LabelReading:
    """What a label carries; *classification* is the text of 2.1 where the
    label names it as the place of its hazard statements (SDB-119)."""
    warnings: list[Message] = []
    # What a sheet says it does not label with is no label (SDB-78).
    hazard_section_text = _LABEL_DECLINED.sub("", hazard_section_text)

    hazard_codes = sorted(printed_hazard_codes(hazard_section_text))
    # Which list came from the sentences rather than printed codes (SDB-174).
    hazard_by_wording = False
    precautionary_by_wording: set[str] = set()
    if not hazard_codes and classification is not None:
        hazard_codes = sorted(
            {lettered_code(code) for code in LABEL_HAZARD_CODE.findall(classification)}
        )
    precautionary_codes = sorted(
        set(PRECAUTION_CODE_PATTERN.findall(hazard_section_text))
    )

    # A label that names no code at all is read by its sentences instead. Twenty
    # sheets here print the wording and nothing else -- "Gefahrenhinweise :
    # Giftig für Wasserorganismen mit langfristiger Wirkung." -- and the codes
    # are unambiguous from the regulation's own table.
    #
    # Only when nothing was found, never alongside. A label that names codes is
    # using codes, and the ones it names are the ones it means; adding to them
    # from a sentence somewhere in the block is how the ingredient table gets
    # onto a product. Measured over the corpus, every sheet this helps had an
    # empty list, so the narrower rule costs nothing and claims less.
    #
    # And never from the phrases of the rules before CLP (SDB-120): "S2 Darf
    # nicht in die Hände von Kindern gelangen." is worded like P102 and is not it.
    if (not hazard_codes or not precautionary_codes) and not (
        _OLD_PHRASES_PRINTED.search(hazard_section_text)
        or old_classification(hazard_section_text) is not None
    ):
        by_wording = codes_from_wording(hazard_section_text)
        if not hazard_codes:
            # "H", not "not EUH": EUH statements have their own field, and P
            # statements are somebody else's list entirely.
            hazard_codes = sorted(c for c in by_wording if c.startswith("H"))
            hazard_by_wording = bool(hazard_codes)
        if not precautionary_codes:
            by_variants: set[str] = set()
            # And in the forms Annex IV allows for its choices, details and
            # optional parts (SDB-163) -- on a label with a hazard statement
            # only: precautionary statements come with a hazard class, and
            # "Aerosol und Nebel nicht einatmen." on a label with EUH211 alone
            # is that statement's own sentence, not P260.
            if hazard_codes:
                by_variants, unclear = precautionary_by_variants(hazard_section_text)
                warnings.extend(
                    Message("precautionary-wording-unclear", {"codes": codes})
                    for codes in unclear
                )
            precautionary_codes = sorted(
                {c for c in by_wording if c.startswith("P")} | by_variants
            )
            precautionary_by_wording = set(precautionary_codes)
    # P501 by the words many suppliers use for it, also beside other P codes
    # (SDB-166); never on a label by the rules before CLP (SDB-120).
    disposal = None
    if (
        hazard_codes
        and "P501" not in precautionary_codes
        and not (
            _OLD_PHRASES_PRINTED.search(hazard_section_text)
            or old_classification(hazard_section_text) is not None
        )
    ):
        disposal = _disposal_sentence(hazard_section_text)
        if disposal is not None:
            precautionary_codes = sorted({*precautionary_codes, "P501"})
            precautionary_by_wording.add("P501")
    supplemental = sorted(
        set(
            code.upper()
            for code in SUPPLEMENTAL_CODE_PATTERN.findall(hazard_section_text)
        )
    )
    # EUH statements by their wording, whatever codes the label prints (SDB-28):
    # 165 current sheets print EUH208 as "Enthält … Kann allergische Reaktionen
    # hervorrufen." without its code, among other codes or none, and nothing
    # else read it. A code the label prints is read with its own wording.
    # Not past a 2.3 the label's end did not catch ("· 2.3 Sonstige Gefahren"):
    # "Produkt reagiert heftig mit Wasser" there describes, it does not label.
    worded_supplemental = euh_statements_by_wording(
        _before_next_subsection(hazard_section_text), skip=set(supplemental)
    )
    supplemental = sorted(set(supplemental) | {c for c, _ in worded_supplemental})

    signal_word, signal_word_stated = read_signal_word(hazard_section_text)

    pictograms = sorted(
        {f"GHS0{digit}" for digit in PICTOGRAM_PATTERN.findall(hazard_section_text)}
    )

    # Two sentences of one effect each are the Annex's joined code (SDB-155).
    h_code_set = with_effects_joined(set(hazard_codes))

    # The pictograms are the ones the label names (SDB-179); those it shows as
    # pictures are added after the parse (reading.py). Nothing is derived from
    # the codes, and a printed pictogram Article 26 would leave out stays, as
    # printed; what the codes call for is clp_expected's (BIB-25).

    return _LabelReading(
        hazard_codes=h_code_set,
        precautionary_codes=set(precautionary_codes),
        supplemental=set(supplemental),
        worded_supplemental=worded_supplemental,
        signal_word=signal_word,
        pictograms=set(pictograms),
        warnings=warnings,
        states_no_signal_word=signal_word is None and signal_word_stated,
        states_no_pictograms=states_no_pictograms(hazard_section_text),
        disposal=disposal,
        from_wording=(h_code_set if hazard_by_wording else set())
        | precautionary_by_wording
        | {code for code, _ in worded_supplemental},
    )


def _page_break_beside(lines: list[str], index: int, furniture: frozenset[str]) -> bool:
    """Whether a page number or the page header stands next to line *index*."""
    for neighbour in (index - 1, index + 1):
        if 0 <= neighbour < len(lines):
            line = lines[neighbour].strip()
            if line in furniture or _PAGE_NUMBER.match(line):
                return True
    return False


def _ends_statement(line: str) -> bool:
    """Whether *line* begins something other than the statement before it."""
    return bool(
        STATEMENT_CODE_PREFIX.match(line)
        or _ANY_STATEMENT_CODE.search(line)
        or _NUMBERED_SUBHEADING.match(line)
        or _LABEL_HEADING.match(line)
        or _CLASSIFICATION_LINE.search(line)
    )


def _is_classification_entry(line: str) -> bool:
    """Whether a hazard class stands before the first code of *line* (SDB-41).

    "Aquatic Chronic 3, H412" lists 2.1's classification, not a statement. The
    shape identifies it, not where it stands: in the file's order one supplier's
    two-column sheets put it, and the boilerplate after it ("Das Produkt ist als
    gefährlich eingestuft gemäß …"), sometimes before the 2.2 heading and
    sometimes after. In print order it stands in 2.1, which the statement texts
    are cut from as well (SDB-10).
    """
    code = _ANY_STATEMENT_CODE.search(line)
    if code is None:
        return False
    before = line[: code.start()].strip().rstrip(",;:(").strip()
    # "Reproduktionstoxizität: Repr. 1B (H360D)": the class behind its name.
    return any(
        part and _CLASSIFICATION_LINE.search(part)
        for part in (before, before.rpartition(":")[2].strip())
    )


# What a supplier adds where the regulation's wording ends in a hole (SDB-108):
# the organs and the route of exposure, named or in brackets.
_HOLE_NAME = re.compile(
    r"(?:Expositionsweg|Zielorgan|Betroffene\s+Organe)", re.IGNORECASE
)
_HOLE_FILLING = re.compile(
    r"(?:\(|Expositionsweg|Zielorgan|Betroffene\s+Organe)", re.IGNORECASE
)
# How many words an organ's name on a line of its own may have.
_ORGAN_WORDS = 2


@dataclass(slots=True)
class _StatementReader:
    """The statements of one kind, collected line by line."""

    pattern: re.Pattern[str]
    statements: list[str] = field(default_factory=list)
    current: list[str] = field(default_factory=list)
    capturing: bool = False
    # How many of *current*'s lines the statement held when its wording was
    # last complete; what stands behind is kept only if it completes again.
    complete: int = 0
    # And how many characters, joined.
    whole: int = 0
    # Whether whole sentences without a code behind a statement are kept
    # beside it (SDB-56), and the lines read behind the one that is over.
    keeps_sentences: bool = False
    behind: list[str] = field(default_factory=list)
    following: bool = False
    # How many lines the statement held at the first page break read past.
    page_break: int | None = None
    # The lines read into the statement, joined ones and those behind it
    # included (SDB-168), and the codes of each statement cut off at the limit.
    taken: int = 0
    too_long: list[str] = field(default_factory=list)

    def close(self) -> None:
        if self.current:
            kept = self.current[: self.complete] if self.complete else self.current
            self.statements.extend(_split_statements(" ".join(kept), self.pattern))
            if self.keeps_sentences and self.complete:
                # Lines that began the wording again and did not finish it;
                # behind a page break they are the next page's.
                end = self.page_break
                if end is not None and end < self.complete:
                    end = None
                left = [*self.current[self.complete : end], *self.behind]
                self.statements.extend(_whole_sentences(left))
            self.current.clear()
        self.behind.clear()
        self.complete = self.whole = self.taken = 0
        self.capturing = self.following = False
        self.page_break = None

    def _at_the_limit(self) -> bool:
        """Whether the statement has all the lines it may take (SDB-168); if
        so, it is closed, and nothing up to the next code belongs to it."""
        if self.taken < MAX_STATEMENT_LINES:
            self.taken += 1
            return False
        begun = (
            _LEADING_STATEMENT_CODES.match(self.current[0]) if self.current else None
        )
        self.too_long.append(begun.group(1) if begun else "")
        self.close()
        return True

    def pass_page_break(self) -> None:
        if self.page_break is None:
            self.page_break = len(self.current)

    def follow(self, value: str) -> None:
        """Take *value* as a line behind the statement, which is over."""
        if self._at_the_limit():
            return
        self.following = True
        self.behind.append(value)

    def begin(self, value: str) -> None:
        self.close()
        self.capturing = True
        self.add(_statement_start(value))

    def add(self, value: str, *, whole: bool = False) -> None:
        if self._at_the_limit():
            return
        # "Reakti-" before the page header, "onen hervorrufen." after it: one
        # word, joined as the reader joins it within a page (SDB-32).
        joined = (
            join_broken_words(f"{self.current[-1]}\n{value}") if self.current else ""
        )
        if joined and "\n" not in joined:
            self.current[-1] = joined
        else:
            self.current.append(value)
        statement = " ".join(self.current)
        if whole or _wording_complete(statement, value, self.whole):
            self.complete = len(self.current)
            self.whole = len(statement)

    def fills_its_hole(self, line: str, below: Sequence[str]) -> bool:
        """Whether *line* is what the supplier adds to a wording that ends in
        a hole (SDB-108): in brackets, or under the hole's name, or a word or
        two right above that name ("Blut" / "Expositionsweg: oral")."""
        if not self.complete or self.complete != len(self.current):
            return False
        if not _ends_in_a_hole(" ".join(self.current)):
            return False
        if _HOLE_FILLING.match(line):
            return True
        following = next((b.strip() for b in below if b.strip()), "")
        return (
            len(line.split()) <= _ORGAN_WORDS
            and not any(c.isdigit() for c in line)
            and _HOLE_NAME.match(following) is not None
        )

    def resumes_below(self, line: str, below: Sequence[str]) -> bool:
        """Whether *line* is a heading of the label set into the statement,
        which the next line finishes (SDB-27).

        The statement has its code and some words, has not reached its
        wording's end, and its last line ends without a sentence's end;
        *line* is a heading alone, without a code; and with the first line
        below, the statement reaches its wording's end.
        """
        if (
            not self.worded
            or self.complete
            or _SENTENCE_END.search(self.current[-1])
            or not _LABEL_HEADING.match(line)
            or _ANY_STATEMENT_CODE.search(line)
        ):
            return False
        following = next((b.strip() for b in below if b.strip()), "")
        if not following or _ends_statement(following):
            return False
        statement = " ".join([*self.current, following])
        return _wording_complete(statement, following, self.whole)

    def finishes_after_heading(self, line: str) -> str | None:
        """The rest of *line* behind a heading of the label, where it finishes
        the statement (SDB-27).

        As SDB-27, but the heading stands at the line's start with a colon
        and the statement's last words behind it: "… Verpackung oder" /
        "Sicherheitshinweise: Kennzeichnungsetikett bereithalten.".
        """
        head, colon, rest = line.partition(":")
        rest = rest.strip()
        if (
            not colon
            or not rest
            or not self.worded
            or self.complete
            or _SENTENCE_END.search(self.current[-1])
            or not _LABEL_HEADING.match(f"{head.strip()}:")
            or _ANY_STATEMENT_CODE.search(line)
        ):
            return None
        statement = " ".join([*self.current, rest])
        return rest if _wording_complete(statement, rest, self.whole) else None

    def is_over_before(self, line: str) -> bool:
        """Whether the statement is whole and *line* does not begin it again (SDB-51)."""
        if not self.complete or self.complete != len(self.current):
            return False
        return not _begins_again(" ".join(self.current), line)

    @property
    def worded(self) -> bool:
        return bool(self.pattern.sub("", " ".join(self.current)).strip(" :-–+"))

    def text(self, passages: Sequence[str]) -> str | None:
        """The statements, one per line; *passages* is the text without a code."""
        unique: dict[str, str] = {}
        for statement in _without_strays(
            _with_wordings_apart(self.statements, passages)
        ):
            if cleaned := _FOOTNOTE_MARK.sub("", statement.strip()):
                unique.setdefault(cleaned.casefold(), cleaned)
        return "\n".join(_without_shorter_readings(list(unique.values()))) or None


def _without_shorter_readings(statements: list[str]) -> list[str]:
    """Drop the shorter of two readings of a statement that ends in a hole (SDB-108).

    2.1 prints "H373: Kann die Organe schädigen bei längerer oder wiederholter
    Exposition." and the label the same sentence with what the supplier adds
    to it, "(Zielorgan(e): Nieren; …)" or "… Exposition durch Verschlucken.":
    one statement, read twice, and the one that fills the hole is the whole
    one. Only for such a wording: behind any other, what follows the sentence
    is as often a cell of the table beside it ("… Hautreizungen.
    Berechnungsmethode.").
    """

    def parts(statement: str) -> tuple[str, str]:
        codes = _LEADING_STATEMENT_CODES.match(statement)
        if codes is None or not _ends_in_a_hole(statement):
            return "", ""
        return (
            re.sub(r"\s+", "", codes.group(1)),
            statement[codes.end() :].lstrip(" :-–").rstrip(" ."),
        )

    def fills(shorter: str, longer: str) -> bool:
        if not shorter or not longer.startswith(shorter) or longer == shorter:
            return False
        rest = longer[len(shorter) :]
        added = rest.lstrip(" .")
        # In the same sentence, or what the hole asks for behind it.
        return bool(added) and (
            not rest.startswith(".") or _HOLE_FILLING.match(added) is not None
        )

    read = [parts(statement) for statement in statements]
    return [
        statement
        for statement, (codes, body) in zip(statements, read, strict=True)
        if not (
            codes
            and any(
                other_codes == codes and fills(body, other)
                for other_codes, other in read
            )
        )
    ]


# The line that names what the label must name ("Enthält: Zement, Portland,
# Klinker"): no part of an H or a P statement above it (SDB-27). An EUH
# statement can begin so.
_CONTENTS_LINE = re.compile(r"^Enthält[^\S\n]*:")
# A footnote's number set against a statement's last full stop (SDB-27):
# "… Kann allergische Reaktionen hervorrufen.6".
_FOOTNOTE_MARK = re.compile(r"(?<=[a-zäöüß][.!?])\d$")


def _extract_statement_text(
    text: str,
    pattern: re.Pattern[str],
    furniture: frozenset[str],
    too_long: list[str] | None = None,
) -> str | None:
    """The statements *pattern* finds in *text*, one per line (SDB-27, SDB-51).

    A statement starts at its code and takes the lines after it until a line
    that belongs to something else: another code, a heading, a row of the label
    table, a hazard class. Page numbers, the page header and the statement's
    own heading repeated on the next page are read past, so a statement broken
    by a page carries on behind them. Once the statement holds the end of its
    regulation wording and its line or sentence is over, the next line is no
    longer its own -- unless the wording begins again there.
    """
    lines = _joined_combinations(_merge_broken_pairs(text.split("\n")))
    own_heading = _OWN_HEADING[pattern]
    reader = _StatementReader(
        pattern, keeps_sentences=pattern is SUPPLEMENTAL_CODE_PATTERN
    )
    label_broken = False

    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        normalized = stripped.lstrip("-*•·!\t ")
        if not stripped or _is_classification_entry(normalized):
            # A classification entry begins no statement, and what follows it
            # up to the next code belongs to none (SDB-41); like an empty line
            # it ends the one before (SDB-27).
            reader.close()
            continue
        behind = _CODE_BEHIND_ITS_WORDING.match(normalized)
        if behind and _all_of(pattern, behind.group(2)):
            # "Zur Vermeidung von Risiken … einhalten. (EUH401)": the code in
            # brackets closes its sentence instead of opening it.
            reader.close()
            sentence = _sentence_before_its_code(
                lines, index, behind.group(1), behind.group(2)
            )
            if sentence:
                reader.statements.append(
                    f"{behind.group(2)} {_clean_value(' '.join(sentence))}"
                )
            continue
        match = pattern.search(normalized)
        if match:
            head = _clean_value(normalized[: match.start()])
            if _finishes_the_statement(head, reader):
                # "… auch nicht nach" / "Gebrauch. P261-Einatmen von …": the
                # statement above ends on this line, before the next code.
                reader.add(head)
            reader.begin(
                _clean_value(_before_other_codes(normalized[match.start() :], pattern))
            )
            label_broken = _BROKEN_LABEL.search(head) is not None
            continue
        if not reader.capturing or _ONLY_PICTOGRAM_WORDS.fullmatch(normalized):
            continue
        if label_broken and _LABEL_TAIL.fullmatch(normalized):
            # "Ergänzende Gefahrenhin-: EUH401 …" and, after the page break,
            # "weise": the rest of the label, not a word of the statement
            # (SDB-27).
            label_broken = False
            continue
        if reader.following:
            # Behind a statement that is over: up to what ends one, or to the
            # page's end (SDB-56).
            if (
                _ends_statement(normalized)
                or stripped in furniture
                or _PAGE_NUMBER.match(stripped)
                or _CONTINUED.fullmatch(stripped)
            ):
                reader.close()
            else:
                reader.follow(_clean_value(normalized))
            continue
        # The header counts once the statement has its wording: before that,
        # the line may be the wording, which a short sheet repeats as often.
        if (
            (reader.worded and stripped in furniture)
            or _PAGE_NUMBER.match(stripped)
            or _CONTINUED.fullmatch(stripped)
            or (
                own_heading.match(normalized)
                and _page_break_beside(lines, index, furniture)
            )
        ):
            reader.pass_page_break()
            continue
        if reader.resumes_below(normalized, lines[index + 1 :]):
            # "… die Gebrauchsanleitung" / "EUH Sätze" / "einhalten.": the
            # label's column heading set into the sentence (SDB-27).
            continue
        if (rest := reader.finishes_after_heading(normalized)) is not None:
            reader.add(_clean_value(rest))
            continue
        if _ends_statement(normalized) or (
            not reader.keeps_sentences and _CONTENTS_LINE.match(normalized)
        ):
            reader.close()
            continue
        if reader.fills_its_hole(normalized, lines[index + 1 :]):
            reader.add(_clean_value(normalized), whole=True)
            continue
        if reader.is_over_before(normalized):
            if reader.keeps_sentences:
                reader.follow(_clean_value(normalized))
            else:
                reader.close()
            continue
        reader.add(_clean_value(normalized))

    reader.close()
    if too_long is not None:
        too_long.extend(reader.too_long)
    return reader.text(_passages(lines, furniture))


_ONE_CODE = r"(?:EUH\d{3}|[HP]\d{3})"
# A combination left open at a line's end, "P305+P351+" over "P338 BEI …", or
# continued at the next one's start, "P305 + P351" over "+ P338".
_OPEN_COMBINATION = re.compile(rf"{_ONE_CODE}\s*\+\s*$")
_CODE_AT_END = re.compile(rf"{_ONE_CODE}\s*$")
_CONTINUED_COMBINATION = re.compile(rf"^\+\s*{_ONE_CODE}")
# The codes a statement begins with: one, a combination, or several joined by
# a comma, a semicolon, a dash, a slash or a space ("H222-H229 Extrem …").
_LEADING_STATEMENT_CODES = re.compile(
    rf"^({_ONE_CODE}(?:(?:\s*[-–+,;/]\s*|\s+){_ONE_CODE})*)"
)
# "… einhalten. (EUH401)": a sentence with its code in brackets behind it, a
# combination or several codes too ("… bersten. (H222, H229)", "… Weiter
# spülen. (P305+P351+P338)"), or the brackets alone on the line below the
# sentence ("… fernhalten. Nicht rauchen." / "(P210)").
_CODE_BEHIND_ITS_WORDING = re.compile(
    rf"^(?:(\S.*[.!])\s*)?\(({_ONE_CODE}(?:\s*[+,]\s*{_ONE_CODE})*)\)\.?$"
)
# A sentence's end at a line's end, brackets and quotation marks behind it.
_SENTENCE_END = re.compile(r"[.!?][)\]\"“”]*$")


# What suppliers hang on a code: the bracket of "(EUH208) Enthält …", the
# number of their own variant ("P264.1 Nach Gebrauch …"), and the letters CLP
# sets behind H360 and H361 for the effect ("H361d Kann vermutlich das Kind im
# Mutterleib schädigen."), which the wording says in full.
_CODE_MARK = re.compile(rf"^({_ONE_CODE})(?:\)|\.\d\b|[dDfF]{{1,2}}(?=[\s:\-–]|$))\s*")
# A line that begins with a label and its colon.
_LABELLED_LINE = re.compile(r"^[A-ZÄÖÜ][^:.!?]{2,60}:\s")
# A statement that is codes and nothing else: one, a row, a list.
_ONLY_CODES = re.compile(
    rf"^{_ONE_CODE}(?:\s*\+\s*{_ONE_CODE})*"
    rf"(?:\s*[-–,;]\s*{_ONE_CODE}(?:\s*\+\s*{_ONE_CODE})*)*\s*[,;:]?$"
)


# "Enthält Biozidprodukte: Pyridin-2-thiol-1-oxid, Natriumsalz, …": a list,
# which no sentence end closes.
_BIOCIDES = re.compile(r"^Enthält\s+Biozidprodukte?\b", re.IGNORECASE)
# How many words make a sentence in its own right (SDB-52, SDB-56).
_SENTENCE_WORDS = 4


def _whole_sentences(lines: Sequence[str]) -> list[str]:
    """The whole sentences among the *lines* behind an EUH statement (SDB-56).

    Label text without a code: "Ohne ausreichende Lüftung Bildung
    explosionsfähiger Gemische möglich.", the warning for grill lighters. A
    sentence runs to the line that ends one. What reaches no end is not a
    sentence and goes -- a substance's name, "UFI: …", a list of ingredients
    -- except the list of a treated article's biocides.
    """
    sentences: list[str] = []
    current: list[str] = []
    for index, line in enumerate(lines):
        if not current and _BIOCIDES.match(line):
            sentences.append(_joined(lines[index:]))
            break
        ends = _SENTENCE_END.search(line) is not None
        if not current and not ends and len(line.split()) == 1:
            # "Bemerkung" over the sentence it heads.
            continue
        current.append(line)
        if ends:
            sentence = _joined(current)
            current = []
            if sentence[0].isupper() and len(sentence.split()) >= _SENTENCE_WORDS:
                sentences.append(sentence)
    return sentences


def _joined(lines: Sequence[str]) -> str:
    """*lines* as one, a word broken at a line's end joined (SDB-32)."""
    return join_broken_words("\n".join(lines)).replace("\n", " ")


# A label broken at its line's end before the statement's code, and the rest
# of it on a later line (SDB-27).
_BROKEN_LABEL = re.compile(r"[a-zäöüß]-\s*:?\s*$")
_LABEL_TAIL = re.compile(r"[a-zäöüß]{2,15}:?")
# A code in a list behind a comma or a semicolon.
_LISTED_CODE = re.compile(rf"\s*[,;]\s*({_ONE_CODE})(?!\d)")


def _before_other_codes(text: str, pattern: re.Pattern[str]) -> str:
    """*text* up to the first listed code of another kind (SDB-27).

    "H373 (Blut), EUH210, EUH401" under "Gefahrenhinweise:" lists the label's
    codes of every kind; the hazard statement ends before the first EUH code.
    """
    for listed in _LISTED_CODE.finditer(text):
        if not pattern.fullmatch(listed.group(1)):
            return text[: listed.start()]
    return text


# What a pictogram of the protective equipment leaves in the text behind its
# statement's code (SDB-27): "P280 gloves" over "Schutzhandschuhe tragen."
_PICTOGRAM_WORD = r"(?:hands|eyes|gloves|face|clothing|mask)"
_PICTOGRAM_WORDS = re.compile(
    rf"^((?:{_ONE_CODE})(?:\s*\+\s*{_ONE_CODE})*)"
    rf"(?:[^\S\n]+{_PICTOGRAM_WORD})+(?=[^\S\n]|$)"
)
_ONLY_PICTOGRAM_WORDS = re.compile(rf"{_PICTOGRAM_WORD}(?:[^\S\n]+{_PICTOGRAM_WORD})*")


def _statement_start(text: str) -> str:
    """The first line of a statement, its code freed of what suppliers hang on it."""
    text = _PICTOGRAM_WORDS.sub(r"\1", text)
    mark = _CODE_MARK.match(text)
    if mark is None:
        return text
    rest = text[mark.end() :]
    return f"{mark.group(1)}{'' if rest[:1] in tuple('-–:') else ' '}{rest}".strip()


def _all_of(pattern: re.Pattern[str], codes: str) -> bool:
    """Whether every code of *codes* ("P305+P351+P338", "H222, H229") is one of *pattern*'s."""
    return all(pattern.fullmatch(code.strip()) for code in re.split(r"[+,]", codes))


def _finishes_the_statement(head: str, reader: _StatementReader) -> bool:
    """Whether *head*, the text of a line before its first code, is the end of
    the statement being read: a sentence's end behind a line that ended none."""
    return (
        bool(head)
        and reader.capturing
        and not reader.following
        and bool(reader.current)
        and _SENTENCE_END.search(head) is not None
        and not _SENTENCE_END.search(reader.current[-1])
        and not _LABELLED_LINE.match(head)
    )


def _sentence_before_its_code(
    lines: list[str], index: int, on_the_line: str | None, codes: str
) -> list[str]:
    """The lines of the sentence whose code stands in brackets at *index*.

    On the code's own line, or on the line above where the brackets stand
    alone; with the lines above that it began on.
    """
    code = re.split(r"[+,]", codes)[0].strip() if "," in codes else codes
    if on_the_line:
        return [*_sentence_begun_above(lines, index, code), on_the_line]
    last = next(
        (i for i in range(index - 1, max(-1, index - 3), -1) if lines[i].strip()),
        None,
    )
    if last is None:
        return []
    line = lines[last].strip().lstrip("-*•·!\t ")
    if not _SENTENCE_END.search(line) or _ends_statement(line):
        return []
    return [*_sentence_begun_above(lines, last, code), line]


def _sentence_begun_above(lines: list[str], index: int, code: str) -> list[str]:
    """The lines above *index* that the sentence of *code* began on, at most three.

    "Zur Vermeidung von Risiken für Mensch und Umwelt die" over
    "Gebrauchsanleitung einhalten. (EUH401)": a line that ends no sentence
    carries on into the next. Only from where the wording begins: the heading
    above it ends no sentence either.
    """
    bounds = wording_bounds(code)
    above: list[str] = []
    for raw_line in reversed(lines[max(0, index - 3) : index]):
        line = raw_line.strip().lstrip("-*•·!\t ")
        if not line or _SENTENCE_END.search(line) or _ends_statement(line):
            break
        above.insert(0, line)
    for first, line in enumerate(above):
        if bounds and bounds.opening.match(line):
            return above[first:]
    return []


def _codes_of(statement: str) -> list[str]:
    """The codes a statement of codes alone lists, a combination as one."""
    joined = re.sub(r"\s*\+\s*", "+", statement.strip().rstrip(",;:"))
    return [code for code in re.split(r"\s*[-–,;]\s*", joined) if code]


def _listed(codes: str) -> list[str]:
    """The codes a statement begins with, however it joins them."""
    return _codes_of(re.sub(r"\s*/\s*|(?<=\d)\s+(?=[EHP])", ",", codes))


def _begins_again(statement: str, line: str) -> bool:
    """Whether *line* begins the wording of *statement*, whole as it is, once more.

    A second "Enthält …" under EUH208 does; under a row of codes it is the
    wording of any of them, the sheet's sentence for the row (SDB-30).
    """
    if _ONLY_CODES.match(statement):
        return holds_a_wording_of(line, _codes_of(statement))
    wording = _wording_of(statement)
    return wording is not None and wording[2].match(line) is not None


def _passages(lines: list[str], furniture: frozenset[str]) -> list[str]:
    """The text of *lines* that carries no code, cut where a sentence cannot run on.

    That is at an empty line, at a line with a code, at a numbered heading and
    at a heading of the label, whose own line may begin the next passage:
    "Prävention: Freisetzung in die Umwelt vermeiden." (SDB-52). What stands
    under 2.3 is no passage.
    """
    passages: list[str] = []
    current: list[str] = []

    def cut() -> None:
        if current:
            passages.append(" ".join(current))
            current.clear()

    for raw_line in lines:
        line = raw_line.strip().lstrip("-*•·!\t ")
        if _OTHER_HAZARDS.match(line):
            # The label's sentences stand in the label, not under 2.3.
            break
        if line in furniture or _PAGE_NUMBER.match(line) or _CONTINUED.fullmatch(line):
            continue
        if _LABEL_HEADING.match(line) and not _ANY_STATEMENT_CODE.search(line):
            cut()
            _, colon, behind = line.partition(":")
            if colon and behind.strip():
                current.append(behind.strip())
        elif (
            not line
            or _ANY_STATEMENT_CODE.search(line)
            or _NUMBERED_SUBHEADING.match(line)
            or _CLASSIFICATION_LINE.search(line)
        ):
            cut()
        else:
            if _LABELLED_LINE.match(line) and (
                not current or _SENTENCE_END.search(current[-1])
            ):
                # "Gefährliche Inhaltsstoffe: Aceton" is no part of the
                # sentence before it, and "Bei anhaltender Augenreizung: …"
                # begins one of its own. Behind a line that ends no sentence
                # the colon is the wording's: "BEI KONTAKT MIT DEN" over
                # "AUGEN: Einige Minuten …".
                cut()
            current.append(line)
    cut()
    return passages


def _with_wordings_apart(statements: list[str], passages: Sequence[str]) -> list[str]:
    """*statements*, a row of codes replaced by what it stands for (SDB-52).

    A sheet may print the codes apart from their sentences: a column of codes
    over the paragraph of their wordings, or the wordings under
    "Allgemein:", "Prävention:" … and the codes as a list below. Such a run of
    codes gives way to the statements already read with a wording where each
    of its codes has one, and otherwise takes the sheet's sentences from
    *passages*, all of them or none.
    """
    worded = _codes_with_a_sentence(statements)
    result: list[str] = []
    index = 0
    while index < len(statements):
        end = index
        while end < len(statements) and _ONLY_CODES.match(statements[end]):
            end += 1
        codes = [code for row in statements[index:end] for code in _codes_of(row)]
        if not codes:
            result.append(statements[index])
            index += 1
            continue
        # The paragraph under a column of codes was read as the wording of
        # the last one: it is the column's where it begins with the first's.
        last = statements[end] if end < len(statements) else ""
        first = wording_bounds(codes[0])
        last_codes = _LEADING_STATEMENT_CODES.match(last)
        if (
            first
            and last_codes
            and last_codes.group(1) not in codes
            and first.opening.match(last[last_codes.end() :].lstrip(" :-–"))
        ):
            apart = wordings_apart([*codes, last_codes.group(1)], passages)
            if apart is not None:
                result.extend(apart)
                index = end + 1
                continue
        if len(codes) > 1 and all(code in worded for code in codes):
            index = end
            continue
        apart = wordings_apart(codes, passages) if len(codes) > 1 else None
        result.extend(apart if apart is not None else statements[index:end])
        index = end
    return result


def _has_a_sentence_of_its_own(statement: str) -> bool:
    """Whether *statement* is a code with a sentence, not with what a table left.

    The sentence begins as the regulation words the code, or it is one in its
    own right, four words or more and brought to an end: "P103: Lesen Sie
    sämtliche Anweisungen aufmerksam und befolgen Sie diese." is the newer
    wording, "H319 Berechnungsverfahren." a cell of 2.1's table.
    """
    codes = _LEADING_STATEMENT_CODES.match(statement)
    if codes is None or _ONLY_CODES.match(statement):
        return False
    wording = statement[codes.end() :].lstrip(" :-–")
    bounds = wording_bounds(_listed(codes.group(1))[-1])
    if bounds is None or bounds.opening.match(wording):
        return bool(wording)
    return (
        len(wording.split()) >= _SENTENCE_WORDS
        and _SENTENCE_END.search(wording) is not None
    )


def _without_strays(statements: list[str]) -> list[str]:
    """*statements* without what a table left under a code that has its sentence.

    "H410" over "Berechnungsverfahren." in 2.1's table of classifications
    reads as a statement, and so does the first half of one cut by a column:
    "H410 Sehr giftig für Wasserorganismen, mit lang-". Where the same code
    has a statement that begins as the regulation words it, one that does not
    goes, and so does one without its end that another of the code begins
    with (SDB-53). Where it has one that holds an official form, one that
    holds the regulation's words with a table's cell between them goes too
    (SDB-185).
    """
    proper: dict[str, list[str]] = {}
    parsed: list[tuple[str, str | None, str, bool]] = []
    for statement in statements:
        codes = _LEADING_STATEMENT_CODES.match(statement)
        code = codes.group(1) if codes else None
        wording = statement[codes.end() :].lstrip(" :-–") if codes else ""
        bounds = wording_bounds(code) if code else None
        begins = bool(bounds and bounds.opening.match(wording))
        if code and begins:
            proper.setdefault(code, []).append(wording.casefold())
        parsed.append((statement, code, wording, begins))
    # Codes with a statement that holds an official form (SDB-185).
    whole = {
        code
        for _, code, wording, begins in parsed
        if code and begins and holds_official_form(code, wording)
    }
    kept: list[str] = []
    for statement, code, wording, begins in parsed:
        others = proper.get(code or "", [])
        folded = wording.casefold().rstrip("-")
        if code in whole and interleaves_wording(code or "", wording):
            continue
        if wording and others:
            if not begins and wording_bounds(code or "") is not None:
                continue
            if not _SENTENCE_END.search(wording) and any(
                other != wording.casefold() and other.startswith(folded)
                for other in others
            ):
                continue
        kept.append(statement)
    return kept


def _joined_combinations(lines: list[str]) -> list[str]:
    """Lines with a combination left open joined to the line that closes it (SDB-51)."""
    joined: list[str] = []
    for line in lines:
        stripped = line.strip()
        if (
            joined
            and stripped
            and (
                _OPEN_COMBINATION.search(joined[-1])
                or (
                    _CODE_AT_END.search(joined[-1])
                    and _CONTINUED_COMBINATION.match(stripped)
                )
            )
        ):
            joined[-1] = joined[-1].rstrip() + stripped
            continue
        joined.append(line)
    return joined


def _wording_of(statement: str) -> tuple[int, re.Pattern[str], re.Pattern[str]] | None:
    """Where a statement's codes end, and how its wording ends and begins.

    The wording is the last code's where a line lists several ("H222, H229:
    Extrem entzündbares Aerosol. Behälter steht unter Druck: …"). None for a
    statement whose code the regulation does not word, or words without an end.
    """
    codes = _LEADING_STATEMENT_CODES.match(statement)
    if codes is None:
        return None
    last = _listed(codes.group(1))[-1]
    bounds = wording_bounds(last)
    closing = bounds.closing or open_end(last) if bounds else None
    if bounds is None or closing is None:
        return None
    return codes.end(), closing, bounds.opening


def _ends_in_a_hole(statement: str) -> bool:
    """Whether the regulation leaves the end of *statement*'s wording open."""
    codes = _LEADING_STATEMENT_CODES.match(statement)
    return codes is not None and open_end(_listed(codes.group(1))[-1]) is not None


def _wording_complete(statement: str, last_line: str, whole_before: int) -> bool:
    """Whether *statement* holds its wording's end and stops there (SDB-51).

    It stops where its last line ends on the wording's last words or on a
    sentence's end: "… zuführen! Größere Produktreste zur Problemstoff-
    sammelstelle" goes on to "bringen.", and "Schutzhandschuhe tragen.
    Augenschutz oder Gesichtsschutz tragen." is whole with its line. A
    statement that was whole *whole_before* characters in has to reach the
    wording's end once more behind them: a second "Enthält Citral. Kann
    allergische Reaktionen hervorrufen." does, "Enthält 6,8 Massenprozent
    entzündbare Bestandteile." does not.
    """
    if _ONLY_CODES.match(statement):
        # A row or a list of codes is whole on its line (SDB-30): what follows
        # is theirs only where it begins a wording of one of them.
        return len(_codes_of(statement)) > 1
    wording = _wording_of(statement)
    if wording is None:
        return False
    position, closing, _ = wording
    found = list(closing.finditer(statement, max(position, whole_before)))
    if not found:
        return False
    last = found[-1]
    return not statement[last.end() :].strip() or bool(
        _SENTENCE_END.search(last_line.rstrip())
    )


def _split_statements(statement: str, pattern: re.Pattern[str]) -> list[str]:
    """*statement*, and the next one where a line holds two (SDB-51).

    "P101: … bereithalten. P102: Darf nicht …" on one line: a code *pattern*
    finds behind the end of the first wording begins the second statement.
    """
    wording = _wording_of(statement)
    if wording is None:
        return [statement]
    position, closing, _ = wording
    found = closing.search(statement, position)
    if found is None:
        return [statement]
    following = pattern.search(statement, found.end())
    if following is None:
        return [statement]
    return [
        statement[: following.start()].rstrip(),
        *_split_statements(_statement_start(statement[following.start() :]), pattern),
    ]


def _section_16_wordings(
    label: HazardStatements, section_16: str, furniture: frozenset[str]
) -> dict[str, str]:
    """The sentence section 16 prints for each code the label's texts name
    without one (SDB-222).

    Section 16 is read as the label's texts are (SDB-27, SDB-51); the first
    statement under exactly the code, a combination under exactly the
    combination, counts if it is a sentence of its own (SDB-52). Reading
    section 16 drops the letters of an effect behind H360 and H361 (SDB-53),
    so for "H361d" only a statement whose sentence is the regulation's for
    H361d counts, not that of H361f.
    """
    wanted = {
        code
        for text in (
            label.hazard_text,
            label.precautionary_text,
            label.supplemental_text,
        )
        for code in codes_without_wording(text)
    }
    if not wanted or not section_16.strip():
        return {}
    printed: dict[str, str] = {}
    for pattern in (
        HAZARD_CODE_PATTERN,
        PRECAUTION_CODE_PATTERN,
        SUPPLEMENTAL_CODE_PATTERN,
    ):
        text = _extract_statement_text(section_16, pattern, furniture)
        for line in (text or "").split("\n"):
            statement = STATEMENT_LINE.match(line)
            if statement is None:
                continue
            code = statement_code(statement)
            wording = statement.group(4).strip()
            if not wording or not _has_a_sentence_of_its_own(f"{code} {wording}"):
                continue
            for target in wanted - printed.keys():
                if target == code or (
                    target != base_code(target)
                    and base_code(target) == base_code(code)
                    and _is_the_regulations(target, wording)
                ):
                    printed[target] = wording
    return {code: printed[code] for code in sorted(printed)}


def _is_the_regulations(code: str, wording: str) -> bool:
    """Whether *wording* is the regulation's for *code*, case and
    punctuation aside."""
    official = canonical_text(code)
    return official is not None and _letters_only(official) == _letters_only(wording)


def _letters_only(text: str) -> str:
    return re.sub(r"[^\w]|_|\d", "", text.lower())


def _statements_within(text: str | None, codes: set[str]) -> str | None:
    """Keep the statements of *text* whose every H-code is one of *codes*.

    Every one, not any: "H300+H310+H330" is a single statement, and a line that
    runs on into a code the label does not carry is not the label's line.
    """
    if text is None:
        return None
    kept = [
        statement
        for statement in text.split("\n")
        if set(HAZARD_CODE_PATTERN.findall(statement)) <= {base_code(c) for c in codes}
    ]
    return "\n".join(_without_worded_rows(kept)) or None


def _without_worded_rows(statements: list[str]) -> list[str]:
    """*statements* without the lines of codes alone each of which has its
    sentence (SDB-52).

    Once the codes the label does not carry are gone, what is left of a row
    from 2.1's table ("H302" / "H314" / "H318" … over the label) may hold only
    codes that have their sentence, "H302" in "H302+H332 - Gesundheitsschädlich
    …", down to a single one. A code with text behind it has its own as
    section 16 is looked up (SDB-222): "H373" goes beside "H373 (Blut)".
    """
    worded = _codes_with_a_sentence(statements) | worded_codes("\n".join(statements))
    return [
        statement
        for statement in statements
        if not _ONLY_CODES.match(statement)
        or not all(code in worded for code in _codes_of(statement))
    ]


def _codes_with_a_sentence(statements: list[str]) -> set[str]:
    """The codes of *statements* that have a sentence of their own (SDB-52).

    A code has its sentence also as a part of a combination that has one:
    "H302" in a row from 2.1 beside "H302+H332 - Gesundheitsschädlich …".
    """
    return {
        code
        for statement in statements
        if _has_a_sentence_of_its_own(statement)
        and (leading := _LEADING_STATEMENT_CODES.match(statement))
        for listed in _listed(leading.group(1))
        for code in (listed, *listed.split("+"))
    }


def _extract_statements_from_sections(
    sections: dict[Section, str],
    *,
    allowed_sections: set[Section],
    pattern: re.Pattern[str],
    furniture: frozenset[str],
    too_long: list[str],
) -> str | None:
    relevant_chunks = [
        sections[section] for section in allowed_sections if sections.get(section)
    ]
    if not relevant_chunks:
        return None

    combined = "\n\n".join(relevant_chunks)
    return _extract_statement_text(combined, pattern, furniture, too_long)


def _parse_contact_info(
    section_text: str, furniture: frozenset[str]
) -> tuple[ContactInfo, list[Message]]:
    warnings: list[Message] = []

    if not section_text:
        warnings.append(Message("no-identification-section"))
        return ContactInfo(), warnings

    contact = _read_supplier_of(section_text, furniture)
    contact.emergency_phone = _emergency_phone(section_text)

    if not contact.supplier_name:
        warnings.append(Message("no-supplier-name"))
    if not contact.supplier_address:
        warnings.append(Message("no-supplier-address"))
    if not contact.supplier_phone:
        warnings.append(Message("no-supplier-phone"))
    if not contact.emergency_phone:
        warnings.append(Message("no-emergency-phone"))

    return contact, warnings


# The heading of subsection 1.4, numbered or not, behind a bullet or bare:
# "1.4 Notrufnummer", "1,4 Notrufnummer", "· Notfallauskunft:", "Emergency
# telephone number".
_EMERGENCY_HEADING = re.compile(
    r"^[\s·•*\-–]*(?:1\s*[.,]\s*4\.?\s*[:\-–]?\s*)?(?:Notruf|Notfall|Emergency)",
    re.IGNORECASE,
)
# Another subsection of section 1: where the file draws 1.4 before it, what
# follows is the supplier's block, and its numbers are the office's.
_OTHER_SUBSECTION = re.compile(
    r"^[\s·•*\-–]*1\s*[.,]\s*[1-3]\.?(?:\s|$)|Einzelheiten\s+zum\s+Lieferanten",
    re.IGNORECASE,
)
# How many lines below its heading the number may stand: a poison centre's
# name and address come first on some sheets.
_EMERGENCY_REACH = 12
_SHORT_EMERGENCY_NUMBER = re.compile(r"(?<![\d.,/])11[02](?![\d.,/])")
# Numbers of section 1 that are no telephone: a REACH registration
# ("01-2100000000-00-XXXX"), a CAS or EC number.
_NO_TELEPHONE = re.compile(r"^\d{2}-\d{10}-\d{2}|^\d{2,7}-\d{2}-\d$|^\d{3}-\d{3}-\d$")
# What stands behind the number on its line and is not it.
_FAX_BEHIND = re.compile(r"\s*[-–,;/|]?\s*(?:Tele)?Fax\b.*$", re.IGNORECASE)


def _emergency_number(text: str) -> re.Match[str] | None:
    """The first telephone number in *text* as an emergency line prints one.

    It begins with a plus, a zero or a bracket, as a number dialled in or to
    Germany does: "1907/2006" is the regulation, and a date is a date. "112"
    and "110" count as they stand.
    """
    for found in _PHONE_NUMBER.finditer(text):
        number = found.group(0).strip()
        digits = sum(c.isdigit() for c in number)
        if (
            digits >= 6
            and number[0] in "+0("
            and not _DATE_ONLY.match(number)
            and not _DATE_ONLY.match(number.strip("()"))
            and not _NO_TELEPHONE.match(number)
        ):
            return found
    return _SHORT_EMERGENCY_NUMBER.search(text)


def _emergency_phone(section_text: str) -> str | None:
    """The emergency number of subsection 1.4, as printed (SDB-117).

    Behind the heading on its line, or on the first line below it that
    carries a telephone number; never past another subsection's heading.
    What stands there without a number -- a company's name, "siehe 1.3" --
    is no emergency number.
    """
    lines = section_text.split("\n")
    headings = [i for i, line in enumerate(lines) if _EMERGENCY_HEADING.match(line)]
    # A number on the heading's own line first, wherever that heading stands:
    # where the file draws "1.4 Notrufnummer" above the supplier's block, the
    # lines below it are the office's, and the number follows its own label.
    for index in headings:
        if (value := _emergency_value(lines[index])) is not None:
            return value
    for index in headings:
        for below in lines[index + 1 : index + 1 + _EMERGENCY_REACH]:
            if _OTHER_SUBSECTION.search(below):
                break
            if (value := _emergency_value(below)) is not None:
                return value
    return None


def _emergency_value(line: str) -> str | None:
    """What *line* gives as the emergency number, or None without a number.

    The line as printed, without what only labels it: the heading in front
    ("Notrufnummer 1:"), a telephone label ("Tel.:") and a fax number behind.
    A poison centre's name stays: it says whose number it is.
    """
    text = line.strip().lstrip("|·•*").strip()
    if _EMERGENCY_HEADING.match(text):
        _, colon, behind = text.partition(":")
        if colon and _emergency_number(behind):
            text = behind.strip()
        elif found := _emergency_number(text):
            text = text[found.start() :]
        else:
            return None
    elif _emergency_number(text) is None:
        return None
    text = _FAX_BEHIND.sub("", _PHONE_LABEL.sub("", text, count=1))
    return _clean_value(text) if _emergency_number(text) else None


# The supplier block of section 1 (SDB-49, SDB-50): "1.3 Einzelheiten zum
# Lieferanten, der das Sicherheitsdatenblatt bereitstellt", numbered "1.3",
# "1.3." or "1,3" -- or titled so under another number, as a kit's sheet
# does ("1.2 Einzelheiten zum Lieferanten der das Kit-Sicherheitsdatenblatt
# bereitstellt").
_SUPPLIER_HEADING = re.compile(
    r"^1\s*[.,]\s*3\.?\s*[:\-–]?(?:\s*(?-i:[A-ZÄÖÜ])[a-zäöüß]{3,}|\s*$)"
    r"|Einzelheiten\s+zum\s+Lieferanten",
    re.IGNORECASE,
)
_BARE_SUPPLIER_NUMBER = re.compile(r"^1\s*[.,]\s*3\.?\s*[:\-–]?\s*$")
# What ends the block: the next numbered subsection, not one of 1.3's own.
_NUMBERED_SUBSECTION = re.compile(r"^\d{1,2}\s*[.,]\s*\d{1,2}\b")
_SUPPLIER_SUBSECTION = re.compile(r"^1\s*[.,]\s*\d\s*[.,]\s*\d{1,2}\.?\s*")
# What is left of the heading's title on the lines below the number.
# The end of the heading's title, broken by a hyphen and printed beside the
# block's second line: "… das Sicherheitsdatenblatt bereit-" / "F. Eichhof
# GmbH & Co. KG" / "stellt: Erlenweg 48".
_SUPPLIER_TITLE_TAIL = re.compile(r"^(?:bereit)?stellt\s*:\s*", re.IGNORECASE)
# A subsection's number before a supplier's label, where the sheet numbers
# its lines and has no "1.3 Einzelheiten zum Lieferanten": "1.2
# Inverkehrbringer: Birk Creations GmbH".
_NUMBER_BEFORE_SUPPLIER_LABEL = re.compile(
    r"^1\s*[.,]\s*\d\.?\s+(?=(?:Angaben\s+zu[mr]\s+)?(?:Hersteller|Lieferant|Firma"
    r"|Firmenname|Firmenbezeichnung|Inverkehrbringer)\w*\s*[:/])",
    re.IGNORECASE,
)
_SUPPLIER_TITLE = re.compile(
    r"^(?:Einzelheiten\b|der\s+das\b|das\s+Sicherheitsdatenblatt\b"
    r"|Sicherheitsdatenblatt(?:\s+bereitstellt|\s*$)|bereitstellt\b"
    r"|zum\s+Lieferanten\b|Lieferanten,\s+der\s+das\b"
    r"|Details\s+of\s+the\s+supplier\b)",
    re.IGNORECASE,
)
# The label a supplier's name stands under or beside. "Anschrift" and
# "Adresse" also head the poison centre's table under 1.4, so outside the
# block they count only where no other label does.
#
# "Angaben zum Hersteller:", "Angaben zum Lieferanten:" are the same labels
# in a sheet without numbered subsections.
_SUPPLIER_LABEL = re.compile(
    r"^(?:(?:Angaben|Informationen)\s+zu[mr]?\s+)?(?:Herstellers?|Herstellerin"
    r"|Lieferant(?:en)?|Firma|Firmenname"
    r"|Firmenbezeichnung|Firmenidentifikation|Unternehmen|Inverkehrbringer|Händler"
    r"|Fabrik|Bezeichnung\s+des\s+Unternehmens|Company|Firmendetails)\b",
    re.IGNORECASE,
)
# A label that heads the name's line and says nothing more: "Name" over the
# company in a table of the block.
_BARE_NAME_LABEL = re.compile(
    # "Name oder Handelsname" over the company (SDB-49).
    r"^Name(?:\s+oder\s+Handelsname)?\s*:?$",
    re.IGNORECASE,
)
# The same label with the company behind it (SDB-49): "Name: Musterchemie GmbH".
_NAME_LABEL_WITH_VALUE = re.compile(
    r"^Name(?:\s+(?:der\s+Firma|des\s+(?:Hersteller)?[Uu]nternehmens))?\s*:\s*(?=\S)",
    re.IGNORECASE,
)
# A label's value that points elsewhere (SDB-49): "Hersteller/Lieferant:
# siehe Kapitel 16 (Ansprechpartner)". Nobody's name.
_POINTS_ELSEWHERE = re.compile(r"^siehe\b", re.IGNORECASE)
# "1.3 Verwendung des Produkts": a sheet that numbers section 1 its own way
# has something else under 1.3 (SDB-49).
_OTHER_TITLE_UNDER_1_3 = re.compile(
    r"^1\s*[.,]\s*3\.?\s*[:\-–]?\s*(?:Verwendung|Relevante|Notruf|Produkt)",
    re.IGNORECASE,
)
_ADDRESS_HEADING = re.compile(r"^(?:Anschrift|Adresse)\b", re.IGNORECASE)
# The words of such a label, alone or joined by slashes: "Hersteller/Lieferant".
_LABEL_WORDS = re.compile(
    r"^(?:(?:Angaben|Informationen)\s+zu[mr]?\s+)?(?:Herstellers?|Herstellerin"
    r"|Lieferant(?:en)?|Firma|Firmenname"
    r"|Firmenbezeichnung|Unternehmen|Inverkehrbringer|Händler|Anschrift|Adresse)"
    r"(?:\s*/\s*(?:Hersteller|Lieferant|Firma|Importeur|Vertrieb|Händler))*\b",
    re.IGNORECASE,
)
# "T" and "F" stand for telephone and fax only before a number, with no word
# in lower case between: "T +49 8621 400", "T UK FREEPHONE 0800 006 1010",
# not "F. Eichhof GmbH & Co. KG" or "F.W.Kiefer".
_LETTER_LABEL = r"[TF]\b(?=(?-i:[^a-zäöüß\n]*)\d)"
# A line of contact details, not of the address.
_CONTACT_LINE = re.compile(
    rf"^(?:Tel(?:efon\w*)?\b\.?|Tlf\b\.?|Telefax\b|Fax\w*\b\.?|{_LETTER_LABEL}|Phone\b|Fon\b|E-?Mail|Mail\b"
    r"|Nicht-Notfall-Rufnummer"
    r"|Internet|Webseite|Website|Homepage|Web\b|URL\b|www\.|https?://|[\w.+-]+@)",
    re.IGNORECASE,
)
_PHONE_LABEL = re.compile(
    r"^(?:Tel(?:efon\w*)?\b\.?|Tlf\b\.?|T\b(?=(?-i:[^a-zäöüß\n]*)\d)|Phone\b|Fon\b"
    r"|Nicht-Notfall-Rufnummer\w*)"
    r"(?:[-\s]?Nr\.?)?\s*:?\s*",
    re.IGNORECASE,
)
# The same label behind other words of its line, with its colon. Not behind
# a slash: "Telefax:/Telefon: 0551 153467" does not say whose number it is.
_PHONE_LABEL_INSIDE = re.compile(
    r"(?<!/)\b(?:Tel(?:efon)?\.?|Tlf\.?|Fon)(?:[-\s]?Nr\.?)?\s*:\s*(?=[+(\d])",
    re.IGNORECASE,
)
_PICTOGRAM_LABELS = {
    "📞": "Telefon",
    "☎": "Telefon",
    "✆": "Telefon",
    "📠": "Telefax",
    "📧": "E-Mail",
    "✉": "E-Mail",
    "🌐": "Internet",
}
_CONTACT_PICTOGRAM = re.compile(
    "^([" + "".join(_PICTOGRAM_LABELS) + "])\ufe0f?\\s*:?\\s*"
)
# A telephone line that is not the supplier's office: a poison centre, an
# emergency line.
_NOT_THE_OFFICE = re.compile(r"Gift|Notruf|(?<!Nicht-)Notfall|Emergency", re.IGNORECASE)
# Numbers that cost the caller or lead to a service desk: 0180x, 0900, 0800,
# 0137. The office number is preferred where the block has one.
_SERVICE_NUMBER = re.compile(r"^(?:00)?(?:49)?0?(?:180\d|900|800|137)")
_DATE_ONLY = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}$")
# Any label of a telephone or fax number: without one in the block, a line
# that is only a number is the telephone.
_NUMBER_LABEL = re.compile(
    rf"^(?:(?:Tel(?:efon\w*)?|Tlf|Telefax|Fax\w*|Phone|Fon)\b|{_LETTER_LABEL})",
    re.IGNORECASE,
)
# A heading of section 1 where a name would stand: a table printed apart from
# its headings leaves it there.
_NOT_A_NAME = re.compile(
    r"^(?:Relevante\s+identifizierte|Verwendung(?:en)?\b|Notrufnummer|Produktidentifikator"
    r"|Bezeichnung\s+des|Einzelheiten\b)",
    re.IGNORECASE,
)
# A line that begins with a postcode and its town is an address line.
_POSTCODE_FIRST = re.compile(r"^(?:[A-Z]{1,2}\s?[-–]?\s?)?\d{4,5}\s+[A-ZÄÖÜ]")
# An address line in Germany (SDB-55): five digits first, "D-" or "DE-" before
# them or not, or the country's name.
_GERMAN_ADDRESS_LINE = re.compile(
    r"^(?:(?:D|DE)\s*[-–]?\s*)?\d{5}\b|\b(?:Deutschland|Germany|GERMANY)\b"
)
# How many lines may part the street from its town (see _read_supplier).
_LINES_BETWEEN = 2
# "(DE)" before one of several companies a block lists by country.
_COUNTRY_TAG = re.compile(r"^\([A-Z]{2}\)\s*")
# A legal form on the line below a name that ends "… GmbH & Co.".
_LEGAL_FORM_ALONE = re.compile(r"(?:KG|KGaA|OHG|GmbH|AG|mbH)\.?,?")
_NAME_LEFT_OPEN = re.compile(r"(?:&|\bCo\.?|\bund|\bu\.)$")
# "(+49) 231 1450-0": the country code may stand in brackets, plus included.
_PHONE_NUMBER = re.compile(r"\(?(?:\+\s?)?\(?\d[\d\s()/\-–.]{4,}\d")
# A line that is a telephone number and nothing else: contact, not address.
_PHONE_ONLY = re.compile(r"^\(?(?:\+\s?)?[\d\s()/\-–.]{6,}$")
# Where the company's own details end: a department, a person, a hotline.
_SUPPLIER_PART_END = re.compile(
    r"^(?:Auskunft|Auskunftgebender|Auskunftsgebender|Technische\s+Auskunft"
    r"|Ansprechpartner|Kontakt|Abteilung|Zuständig|Beratung|Notruf|Giftnotruf"
    r"|Giftinformation|GIZ|Notfall)",
    re.IGNORECASE,
)
# A poison centre or emergency line: its number is nobody's office phone.
_EMERGENCY_PART = re.compile(
    r"^(?:Notruf|Giftnotruf|Giftinformation|GIZ|Notfall)", re.IGNORECASE
)
# Labels of an address line, dropped from it: "Straße: Seeuferstraße 4".
_ADDRESS_LABEL = re.compile(
    r"^(?:(?:Straße|Strasse|Ort|PLZ|Postleitzahl|Postfach|Land|Stadt|Nat\.-Kenn\.)"
    r"(?:\s*/\s*(?:Straße|Strasse|Ort|PLZ|Postleitzahl|Postfach|Land|Stadt))*"
    r"|Anschrift|Adresse|Hauptsitz|Sitz)\s*:\s*",
    re.IGNORECASE,
)
# The same labels alone on their line, the value below: a table of the block.
_BARE_ADDRESS_LABEL = re.compile(
    r"^(?:Straße|Strasse|Ort|PLZ|Postleitzahl|Land|Stadt|Anschrift"
    r"|Adresse|Geschäftsadresse|Postadresse|Hauptsitz|Sitz)$",
    re.IGNORECASE,
)
# A company's register or tax number: behind the address, not part of it.
_REGISTER_LABEL = re.compile(r"^(?:Id-?Nr|USt-?Id-?Nr|Ust\.?-?Id)\b", re.IGNORECASE)
# The second half of a legal form at the start of the address line: "…
# GmbH" / "KG . Haselring 4 . 81602 Neufeld".
_LEGAL_FORM_BEFORE_ADDRESS = re.compile(r"^(KG|KGaA|OHG)\s*[.,]\s*(?=\S)")
# It starts only where a run of its characters starts: the same address as
# without the lookbehind (only search() reads it), but a long run without an
# "@" is read once instead of once from every character in it.
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_WEBSITE = re.compile(r"\b(?:https?://|www\.)[^\s,;]+", re.IGNORECASE)
# A company's legal form: a name without one may go on on the next line.
_LEGAL_FORM = re.compile(
    r"\b(?:GmbH|AG|KG|KGaA|mbH|SE|OHG|GbR|e\.\s?K|e\.\s?V|B\.\s?V|N\.\s?V|BV|NV|SA|S\.\s?A|S\.\s?p\.\s?A"
    r"|S\.\s?r\.\s?l|[Ss]rl|SRL|SAS|Ltd|Inc|LLC|plc|A/S|AB|Oy|Co)\b\.?",
)


def _read_supplier_of(section_text: str, furniture: frozenset[str]) -> ContactInfo:
    """The supplier of section 1 (SDB-49, SDB-50).

    Read from the block under 1.3; where that names nobody -- one supplier prints
    1.3's content as a table further down, after 1.4 -- from the first label
    of the supplier in section 1, and failing that from an address label.
    """
    lines = [
        part
        for line in _without_page_breaks(section_text.split("\n"), furniture)
        for part in _supplier_lines(line)
    ]
    starts: list[int] = []
    heading = next(
        (
            i
            for i, line in enumerate(lines)
            if _SUPPLIER_HEADING.search(line) and not _OTHER_TITLE_UNDER_1_3.match(line)
        ),
        None,
    )
    labels = [
        label
        for pattern in (_SUPPLIER_LABEL, _ADDRESS_HEADING)
        if (
            label := next(
                (i for i, line in enumerate(lines) if _is_label(line, pattern)), None
            )
        )
        is not None
    ]
    if heading is not None and _is_untitled(lines, heading):
        # "1.3" alone, no title below it: on a sheet from before REACH's
        # numbering that is "Zubereitung: …", and the supplier stands under
        # "1.4 Hersteller/Lieferant:".
        starts = [*labels[:1], heading + 1, *labels[1:]]
    else:
        starts = [*([heading + 1] if heading is not None else []), *labels]
    if heading is not None:
        # The company behind the heading's colon, the title running on below
        # (SDB-49): "1.3 Einzelheiten zum: Musterwerk GmbH" / "Lieferanten,
        # der das" / "Sicherheitsdatenblatt bereitstellt".
        _, colon, behind = lines[heading].partition(":")
        if colon and _LEGAL_FORM.search(behind):
            at = heading + 1
            while at < len(lines) and _SUPPLIER_TITLE.match(lines[at]):
                at += 1
            lines = [*lines[:at], behind.strip(), *lines[at:]]
    first: ContactInfo | None = None
    for start in starts:
        supplier = _german_supplier(_supplier_block(lines, start))
        if supplier.supplier_name:
            return supplier
        first = first or supplier
    return first or ContactInfo()


def _is_untitled(lines: list[str], heading: int) -> bool:
    """Whether the heading at *heading* is the bare number, its title not below."""
    if not _BARE_SUPPLIER_NUMBER.match(lines[heading]):
        return False
    below = lines[heading + 1] if heading + 1 < len(lines) else ""
    return not (_SUPPLIER_TITLE.match(below) or _SUPPLIER_HEADING.search(below))


def _german_supplier(block: list[str]) -> ContactInfo:
    """The supplier among the companies *block* names: the German one (SDB-55).

    The first company, unless its address lies abroad and a later one's in
    Germany: one sheet names its Danish maker, then "Nationaler Kontakt" over
    the German company. E-mail and website are that company's own
    where the block gives them from its name on, else the first company's.
    """
    first = _read_supplier(block)
    if not first.supplier_address or _in_germany(first.supplier_address):
        return first
    for index, line in enumerate(block[1:], start=1):
        if _EMERGENCY_PART.match(line):
            break
        if not _begins_a_company(line):
            continue
        company = _read_supplier(block[index:])
        if company.supplier_address and _in_germany(company.supplier_address):
            company.supplier_email = company.supplier_email or first.supplier_email
            company.information_email = (
                company.information_email or first.information_email
            )
            company.supplier_website = (
                company.supplier_website or first.supplier_website
            )
            return company
    return first


def _begins_a_company(line: str) -> bool:
    """Whether *line* names a company: a legal form, bare or behind a supplier's label."""
    labelled, value = _label_and_value(line)
    if labelled:
        return bool(_LEGAL_FORM.search(value))
    return ":" not in line and bool(_LEGAL_FORM.search(line))


def _in_germany(address: str) -> bool:
    """Whether a line of *address* begins with a German postcode or names the country."""
    return any(
        _GERMAN_ADDRESS_LINE.search(part.strip())
        for part in re.split(r", | \. | - ", address)
    )


def _without_page_breaks(lines: list[str], furniture: frozenset[str]) -> list[str]:
    """*lines* without a page number and the page header beside it.

    A page that ends inside the block puts its footer and the next page's
    header between the supplier's lines. The header alone does not tell: it
    often carries the supplier's name. Beside a page number it is the page's.
    """
    stripped = [line.strip() for line in lines]
    dropped: set[int] = set()
    for index, line in enumerate(stripped):
        if not _PAGE_NUMBER.match(line):
            continue
        dropped.add(index)
        for step in (-1, 1):
            neighbour = index + step
            while 0 <= neighbour < len(stripped) and stripped[neighbour] in furniture:
                dropped.add(neighbour)
                neighbour += step
    return [line for index, line in enumerate(lines) if index not in dropped]


def _supplier_lines(line: str) -> list[str]:
    """A line's parts, without bullet and without a number of 1.3's own ("1.3.1").

    A sheet that sets its lines side by side parts them with a bar:
    "GERMANY | Tel. +49 2054 4048-70, Fax. +49 2054 4048-790".
    """
    parts: list[str] = []
    # Or with stars: "Musterchemie KGaA * 12345 Musterstadt * Tel: …" (SDB-49).
    separator = " * " if line.count(" * ") >= 2 else " | "
    for part in line.split(separator):
        stripped = part.strip().lstrip("·•*-–. ").strip()
        stripped = _SUPPLIER_SUBSECTION.sub("", stripped).strip()
        stripped = _NUMBER_BEFORE_SUPPLIER_LABEL.sub("", stripped)
        pictogram = _CONTACT_PICTOGRAM.match(stripped)
        if pictogram:
            # A telephone, a letter and a globe for the labels.
            label = _PICTOGRAM_LABELS[pictogram.group(1)]
            stripped = f"{label}: {stripped[pictogram.end() :]}"
        if stripped:
            parts.append(stripped)
    return parts


def _is_label(line: str, pattern: re.Pattern[str]) -> bool:
    """Whether *line* is, or begins with, a label *pattern* names."""
    head = line.partition(":")[0]
    return (
        bool(pattern.match(head))
        and not any(c.isdigit() for c in head)
        and len(head) <= 120
    )


def _supplier_block(lines: list[str], start: int) -> list[str]:
    """The lines from *start* to the next numbered subsection, the title left out."""
    block: list[str] = []
    for line in lines[start:]:
        if _NUMBERED_SUBSECTION.match(line) and not _SUPPLIER_HEADING.search(line):
            break
        if (
            not block
            and _SUPPLIER_TITLE.match(line)
            and not any(c.isdigit() for c in line)
        ):
            continue
        if not block and line.startswith("(") and line.endswith(")"):
            # "(Hersteller/Importeur/Alleinvertreter/nachgeschalteter
            # Anwender/Händler)": the heading's remark, nobody's name.
            continue
        line = _SUPPLIER_TITLE_TAIL.sub("", line)
        if line and not _BARE_SUPPLIER_NUMBER.match(line):
            block.append(line)
    return block


def _label_and_value(line: str) -> tuple[bool, str]:
    """Whether *line* is a supplier's label, and the value it carries.

    Behind a colon, or behind the label itself where the value is a company:
    "Hersteller/Lieferant Haselwerk AG & Co. KGaA".
    """
    named = _NAME_LABEL_WITH_VALUE.match(line)
    if named:
        return True, line[named.end() :].strip()
    if not (_is_label(line, _SUPPLIER_LABEL) or _is_label(line, _ADDRESS_HEADING)):
        return False, ""
    _, colon, value = line.partition(":")
    if colon:
        # "Händler Tel.:: Ahornwerk GmbH": a second label's colon before it.
        return True, value.strip().lstrip(":").strip()
    behind = _LABEL_WORDS.sub("", line).strip()
    return True, behind if _LEGAL_FORM.search(behind) else ""


@dataclass(slots=True)
class _Phones:
    """The telephone numbers of a supplier block, by how they are marked."""

    labelled: list[str] = field(default_factory=list)
    bare: list[str] = field(default_factory=list)
    # Behind a label that does not begin its line.
    inside: list[str] = field(default_factory=list)
    pending: bool = False

    def read(self, line: str) -> None:
        if self.pending and not _CONTACT_LINE.match(line):
            self.pending = False
            self._keep(self.labelled, line)
        elif _PHONE_LABEL.match(line):
            number = _PHONE_NUMBER.search(line)
            if _NOT_THE_OFFICE.search(line[: number.start()] if number else line):
                return
            value = _PHONE_LABEL.sub("", line, count=1)
            self.pending = not self._keep(self.labelled, value)
        elif _PHONE_ONLY.match(line):
            self._keep(self.bare, line)
        elif (
            inside := _PHONE_LABEL_INSIDE.search(line)
        ) and not _NOT_THE_OFFICE.search(line[: inside.start()]):
            # "Deutschland Telefon: 0800 - 6536776, Fax: 0800 - 6367628"
            self._keep(self.inside, line[inside.end() :])

    @staticmethod
    def _keep(numbers: list[str], text: str) -> bool:
        number = _phone_number(text)
        if number is not None:
            numbers.append(number)
        return number is not None

    def chosen(self, block: list[str]) -> str | None:
        """The office number: labelled before bare, a service number last (SDB-50)."""
        numbers = list(self.labelled)
        if not numbers and not any(_NUMBER_LABEL.match(line) for line in block):
            numbers = self.bare[:1]
        numbers = numbers or self.inside
        office = [
            number
            for number in numbers
            if not _SERVICE_NUMBER.match("".join(c for c in number if c.isdigit()))
        ]
        return next(iter(office or numbers), None)


def _read_supplier(block: list[str]) -> ContactInfo:
    """Name, address, phone, e-mail and website from a supplier block."""
    contact = ContactInfo()
    name: list[str] = []
    address: list[str] = []
    phones = _Phones()
    stage = "name"
    behind_address = 0
    named_at = len(block)
    block = _without_label_remarks(block)
    for index, line in enumerate(block):
        if stage == "name":
            labelled, value = _label_and_value(line)
            if labelled:
                if not value or value.endswith(":") or _POINTS_ELSEWHERE.match(value):
                    # No value, another label where one would stand, or a
                    # pointer to another part of the sheet (SDB-49).
                    continue
                stage = "after name"
                line = value
            elif _CONTACT_LINE.match(line) or _SUPPLIER_PART_END.match(line):
                stage = "contacts"
            elif (
                ":" in line and not _LEGAL_FORM.search(line.partition(":")[0])
            ) or _NOT_A_NAME.match(line):
                # "Zubereitung: Organisch-mineralischer NPK-Dünger": another
                # label's value, not a name. "XYZ GmbH & Co. KG, Dieselstr.
                # 3, D-61417 Birkenhofen, Tel.: +49 7537 4180 0" is one.
                continue
            else:
                stage = "after name"
            if (
                stage == "after name"
                and _POSTCODE_FIRST.match(line)
                and not _LEGAL_FORM.search(line)
            ):
                # No name before the address: the block's table lost it. A
                # company's name may begin like a postcode: "2022 ES
                # Deutschland GmbH".
                stage = "address"
            elif stage == "after name":
                first, rest = _name_and_address(_COUNTRY_TAG.sub("", line))
                name = [_without_column_beside(_first_company(first))]
                named_at = index
                address.extend(_places_beside_a_name(rest, phones))
                continue
        if stage != "name" and _is_label(line, _SUPPLIER_LABEL):
            # A second "Lieferant": the next company, with a telephone of
            # its own (one supplier lists Germany, then Austria).
            break
        if stage == "after name":
            part, line = _name_part_of(name, address, line)
            name.extend(part)
            if not line:
                continue
            stage = "address"
        if stage == "address":
            head, colon, value = line.partition(":")
            number = value.partition(":")[0].strip()
            if colon and any(c.isdigit() for c in head) and _PHONE_ONLY.match(number):
                # A pictogram for a label: "D-49731 Talstadt (Unterland):
                # +49 (0) 5173 / 960 90 999", more pictograms' values behind.
                address.append(head.strip())
                line = number
                stage = "contacts"
            elif _ends_the_address(line):
                stage = "contacts"
            else:
                # "Anschrift:" or "Hauptsitz:" alone heads the lines below.
                value = _ADDRESS_LABEL.sub("", line).strip().rstrip(",;").strip()
                if value and not _BARE_ADDRESS_LABEL.match(value):
                    address.append(value)
                continue
        if stage == "contacts":
            if (
                _EMERGENCY_PART.match(line)
                or _COUNTRY_TAG.match(line)
                # "Gipswerk GmbH Schweiz, Seestrasse 4, 3011 Bergingen,
                # Schweiz Telefon: +41 …": the next company and its number.
                or _names_another_company(line)
            ):
                break
            behind_address += 1
            if (
                behind_address <= _LINES_BETWEEN + 1
                and _POSTCODE_FIRST.match(line)
                and not any(_POSTCODE_FIRST.match(part) for part in address)
            ):
                # The town, parted from the street by a line or two of the
                # column beside them: "Haselring 4" / "E-Mail
                # sachkundige Person:" / "sds@sdb-dienst.example" / "81602 Neufeld -
                # Germany".
                address.append(line)
                continue
            phones.read(line)
    contact.supplier_name = _without_marks(" ".join(name)) or None
    contact.supplier_address = ", ".join(line for line in address if line) or None
    contact.supplier_phone = phones.chosen(block)
    (
        contact.supplier_email,
        contact.supplier_website,
        contact.information_email,
    ) = _contact_addresses(block, named_at)
    return contact


def _without_label_remarks(block: list[str]) -> list[str]:
    """*block* without what only explains a label (SDB-133).

    "Name" alone over the name, and the rest of a remark in brackets that a
    supplier's label opens and a later line closes: "Lieferant
    (Hersteller/Importeur/Alleinvertreter/nachgeschalteter" /
    "Anwender/Händler)". The label's own line stays; it carries no name.
    """
    kept: list[str] = []
    remark_open = False
    for line in block:
        if remark_open:
            remark_open = ")" not in line
            continue
        if _BARE_NAME_LABEL.match(line):
            continue
        kept.append(line)
        remark_open = _label_and_value(line)[0] and line.count("(") > line.count(")")
    return kept


def _name_part_of(
    name: list[str], address: list[str], line: str
) -> tuple[list[str], str]:
    """What of *line* below the name still belongs to it, and the rest of it.

    The name's second line (SDB-49), or the second half of a legal form set
    before the address: "… GmbH" / "KG . Haselring 4 . 81602 Neufeld".
    """
    if len(name) != 1 or address:
        return [], line
    if _continues_name(name[0], line):
        return [line.rstrip(",")], ""
    form = _LEGAL_FORM_BEFORE_ADDRESS.match(line)
    if form and _LEGAL_FORM.search(name[0]):
        return [form.group(1)], line[form.end() :]
    return [], line


# A first name's full stop with a blank behind it, in front of the address:
# "E-Mail (fachkundige Person): Vorname. Nachname@firma.example".
_SPLIT_LOCAL_PART = re.compile(r"(?<=:\s)([A-Za-z]+\.)\s(?=[\w.+-]+@)")
# A web address printed against the e-mail address with nothing between.
_GLUED_WEBSITE = re.compile(r"(?<=[a-z])(?=www\.[\w-]+\.)")


# What a sheet calls whoever answers for it (SDB-136), on the address's line,
# on a line above, or heading the part of the block the address stands in:
# first the competent person Annex II asks for, then an office that gives
# information.
_INFORMATION_LABELS = (
    re.compile(
        r"sachkundig|fachkundig|zuständig|verantwortlich"
        r"|zum\s+(?:Sicherheitsdatenblatt|SDB)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"auskunft|auskünfte|ansprechpartner|kontaktperson|kontaktstelle"
        r"|technische[nr]?\s+information|regulatory|produktsicherheit",
        re.IGNORECASE,
    ),
)


def _contact_addresses(
    block: list[str], named_at: int
) -> tuple[str | None, str | None, str | None]:
    """The block's first e-mail address, its first website, and the address
    of whoever answers for the sheet (SDB-50, SDB-134, SDB-136).

    None of them from an emergency part below the name, at line *named_at*:
    what stands under "Notruf" or "Giftnotruf" there is the poison centre's.
    """
    end = next(
        (
            index
            for index, line in enumerate(block)
            if index > named_at and _EMERGENCY_PART.match(line)
        ),
        len(block),
    )
    own = [
        _GLUED_WEBSITE.sub(" ", _SPLIT_LOCAL_PART.sub(r"\1", line))
        if "@" in line
        else line
        for line in block[:end]
    ]
    text = "\n".join(own)
    email = _EMAIL.search(text)
    website = _WEBSITE.search(text)
    return (
        email.group(0) if email else None,
        website.group(0).rstrip(".") if website else None,
        _information_email(own),
    )


def _information_email(lines: list[str]) -> str | None:
    """The address under a label of whoever answers for the sheet, or None.

    An address belongs to the label last named at or before it. The
    competent person's goes before an information office's; an address under
    no such label is not one.
    """
    found: list[tuple[int, str]] = []
    rank = len(_INFORMATION_LABELS)
    for line in lines:
        email = _EMAIL.search(line)
        label = line[: email.start()] if email else line
        rank = next(
            (
                index
                for index, pattern in enumerate(_INFORMATION_LABELS)
                if pattern.search(label)
            ),
            rank,
        )
        if email and rank < len(_INFORMATION_LABELS):
            found.append((rank, email.group(0)))
    return min(found, key=lambda entry: entry[0])[1] if found else None


def _places_beside_a_name(parts: list[str], phones: _Phones) -> list[str]:
    """The address parts of a name's line; a telephone among them goes to *phones*."""
    places: list[str] = []
    for part in parts:
        # "D-91140 Nürnberg. Tel.: +49 (0)911 9410000 0"
        inside = _PHONE_LABEL_INSIDE.search(part)
        place = part[: inside.start()].rstrip(" .,;") if inside else part
        # "Tel.: …" alone; "54246 Lindendorf, D-Telefon: …" leaves "D-".
        if _CONTACT_LINE.match(part) or place in ("D-", "D"):
            place = ""
        if place:
            places.append(place)
        if place != part:
            phones.read(part)
    return places


def _ends_the_address(line: str) -> bool:
    """Whether *line* is the first behind the address: a contact, a department,
    a country's tag, or any label but an address line's own."""
    return bool(
        _CONTACT_LINE.match(line)
        or _PHONE_ONLY.match(line)
        or _SUPPLIER_PART_END.match(line)
        or _COUNTRY_TAG.match(line)
        or _REGISTER_LABEL.match(line)
        or (":" in line and not _ADDRESS_LABEL.match(line))
    )


def _names_another_company(line: str) -> bool:
    """Whether a line among the contact details opens a company of its own:
    a legal form before any colon, and an address behind a comma."""
    head = line.partition(":")[0]
    return (
        "," in head
        and _LEGAL_FORM.search(head.partition(",")[0]) is not None
        and not _CONTACT_LINE.match(line)
        and not _SUPPLIER_PART_END.match(line)
    )


def _continues_name(name: str, line: str) -> bool:
    """Whether *line* is the second line of the company's *name* (SDB-49)."""
    if _NAME_LEFT_OPEN.search(name) and _LEGAL_FORM_ALONE.fullmatch(line):
        return True
    # "Alfred Kirsch" over "Lackfabrik GmbH & Co. KG"; not "Custom Parts
    # Europe" over "The Old Mill", the first line of its address.
    return (
        not _LEGAL_FORM.search(name)
        and _LEGAL_FORM.search(line) is not None
        and not any(c.isdigit() for c in line)
        and not _CONTACT_LINE.match(line)
        and not _SUPPLIER_PART_END.match(line)
        and ":" not in line
    )


# A street with its number right behind a legal form (SDB-133).
_STREET_BEHIND_NAME = re.compile(
    r"\b(?:GmbH|AG|KG|KGaA|mbH|SE|OHG)(\s+)(?=[A-ZÄÖÜ][\wäöüß.-]*[\s-]?"
    r"(?i:str\.|straße|strasse|weg|platz|allee|ring|damm)\s*\d)",
)


def _name_and_address(line: str) -> tuple[str, list[str]]:
    """A name line that carries the address too, split into the two.

    "Ahornwerk Germany AG; Auenweg 22; 95044 Seestadt / Fluss" at its semicolons;
    "Buchfeld GmbH, Am Hafen 74, D- 29327 Feldstadt" at its commas, where
    the first part ends in a legal form and a number follows.
    """
    if ";" in line:
        head, *parts = (part.strip() for part in line.split(";"))
        return head, [part for part in parts if part]
    glued = _STREET_BEHIND_NAME.search(line)
    if glued:
        # "Mustermann GmbH Hafenstr. 40 12345 Musterstadt": the street behind
        # the legal form, no separator between (SDB-133).
        return line[: glued.start(1)].strip(), [line[glued.end(1) :].strip()]
    for separator in (" – ", ", ", " . ", " - "):
        head, found, tail = line.partition(separator)
        if found and _LEGAL_FORM.search(head) and any(c.isdigit() for c in tail):
            return head, [
                part.strip() for part in tail.split(separator) if part.strip()
            ]
    return line, []


# A company's legal form with what belongs to it: "GmbH & Co. KG".
_LEGAL_FORM_RUN = re.compile(
    rf"{_LEGAL_FORM.pattern}"
    rf"(?:\s*(?:&|\+|und|u\.)?\s*(?:Co\b\.?\s*)?{_LEGAL_FORM.pattern})*"
)
# An abbreviation's full stop at a name's end: "Co.", "B.V.", "a.s.". A run
# of letters with full stops is tried from its first letter only: where it
# fails, it fails from every later one too.
_ENDS_IN_ABBREVIATION = re.compile(
    r"(?:\b(?:Co|Inc|Ltd|Corp|Cie)"
    r"|(?<!\b[A-Za-z]\.)(?<!\b[A-Za-z]\.\s)\b(?:[A-Za-z]\.\s?)+[A-Za-z])\.$"
)


def _without_column_beside(name: str) -> str:
    """*name* up to its legal form where the next column runs on behind it (SDB-133).

    Two columns set side by side reach the text as one line: "Musterlack
    GmbH Notrufnummer (mit Bedienungszeiten)", "Musterlack GmbH Germany: +49
    …". What follows the legal form is no part of the name where it holds a
    colon, a digit or the emergency line's word.
    """
    form = _LEGAL_FORM_RUN.search(name)
    if form is None:
        return name
    behind = name[form.end() :]
    if re.search(r"[:\d]|Notruf|Emergency", behind):
        return name[: form.end()].strip()
    return name


def _first_company(name: str) -> str:
    """*name* up to its first company where the line carries two (SDB-133).

    A table with a column per country prints them side by side: "Birkenhof
    GmbH Birkenhof AG". The first ends with its legal form; what follows
    is another where it begins like the first and has a legal form of its own.
    """
    form = _LEGAL_FORM_RUN.search(name)
    if form is None:
        return name
    behind = name[form.end() :].split()
    if (
        not behind
        or behind[0].casefold() != name.split()[0].casefold()
        or not _LEGAL_FORM.search(" ".join(behind[1:]))
    ):
        return name
    return name[: form.end()]


def _without_marks(name: str) -> str:
    """*name* without a footnote's asterisk and stray punctuation at its end."""
    name = name.strip()
    while name:
        if not (
            name[-1] in "*,;:"
            or name.endswith((" .", "..", " -", " –"))
            or (name.endswith(".") and not _ENDS_IN_ABBREVIATION.search(name))
        ):
            break
        name = name[:-1].rstrip()
    return name


def _phone_number(text: str) -> str | None:
    """The first telephone number in *text*, nothing behind it ("Telefax …")."""
    match = _PHONE_NUMBER.search(text)
    if match is None:
        return None
    number = match.group(0).strip()
    if number.count("(") > number.count(")"):
        if number.rindex("(") == 0:
            # "(+49 231 1450-0)": the bracket holds the number, and closes
            # behind it.
            number = number[1:].strip()
        else:
            # "+49 (0) 1806/31-9000 (0,14 €/Min. …)": the bracket opens a remark.
            number = number[: number.rindex("(")].strip()
    if _DATE_ONLY.match(number):
        return None
    digits = "".join(c for c in number if c.isdigit())
    # 19240 is the number every German poison centre shares (0551 19240,
    # 030 19240 …): a sheet's emergency line, never the supplier's office.
    if len(digits) < 6 or digits.endswith("19240"):
        return None
    return number


# Where subsection 1.1 ends: the heading of 1.2 or 1.3, with or without number.
_AFTER_PRODUCT_IDENTIFIER = re.compile(
    r"^\W*(?:1\s*[.,]\s*[2-4]\b"
    r"|Relevante identifizierte Verwendungen"
    r"|Verwendung des Stoff"
    r"|Einzelheiten zum Lieferanten"
    r"|Angaben zum (?:Hersteller|Lieferanten))",
    re.IGNORECASE,
)
# A label that names the product by the name it is sold under (SDB-131):
# each of its parts, between slashes or "oder", is one of these.
_TRADE_NAME_PART = re.compile(
    r"^(?:handelsnamen?(?: des (?:produkte?s|gemischs?|stoffe?s))?"
    r"|handelsbezeichnung|produktnamen?|produktbezeichnung|markenname"
    r"|artikelbezeichnung|bezeichnung"
    r"|(?:die )?bezeichnung des (?:produkte?s|gemischs?|artikels)"
    r"|(?:ghs )?produkt-?(?:identi?fikator(?:en)?|indikator)(?: handelsnamen?)?)$"
)
# A label that names the product in other words: its trade name goes first.
_OTHER_NAME_PART = re.compile(
    r"^(?:(?:die )?(?:name|bezeichnung)"
    r"(?: de[sr] (?:produkte?s|gemisch(?:e?s)?|stoff(?:e?s)?|artikels|zubereitung))?"
    # The half behind "oder" (SDB-131): "Bezeichnung des Stoffes oder des
    # Gemisches".
    r"|de[sr] (?:gemisch(?:e?s)?|stoff(?:e?s)?|zubereitung)"
    r"|der zubereitung|produkt|stoffname|substanzname)$"
)
# What stands in front of a label: a bullet, the subsection's number.
_BEFORE_LABEL = re.compile(r"^[^\w(]*ꞏ?\s*(?:\d+\s*[.,]\s*)*\d*\s*\.?[^\w(]*")
# A bullet or dash in front of a value; a quote or bracket belongs to it.
_BULLET = re.compile(r"^(?:[^\w\"„“”»«‚‘'(\[<]|ꞏ)+")
# A trade name's label and the name on one line, with no colon between; one
# letter too many on the label is the sheet's slip (SDB-131).
_LABEL_THEN_NAME = re.compile(
    r"^(?:Handelsname[a-z]?(?:\s*/\s*Bezeichnung)?|Handelsbezeichnung"
    r"|Produktnamen?|Produktbezeichnung)\s+(?=\S)",
    re.IGNORECASE,
)
# A line that is a label of something else and carries no value: it ends in a
# colon, or it is one of the labels sheets print without one.
_OTHER_LABEL = re.compile(
    r"^(?:.*:"
    r"|UFI\b.*|.*(?:\b(?:Nr|Code|Codes)|nummern?)\.?"
    r"|Produkt(?:form|art|typ|gruppe|code|nummer)(?:\s*\([^()]*\))?"
    r"|Stoff-?\s*/\s*Produktidentifikation|Andere Bezeichnungen"
    r"|Weitere Handelsnamen.*|Geltungsbereich|Synonyme?"
    r"|Seite\s*:?\s*\d+.*"
    # A formula identifier, also with a character too many in a group, as
    # text recognition reads it (SDB-148).
    r"|[A-Z0-9]{4,5}(?:-[A-Z0-9]{4,}){3}"
    # Labels sheets print without a colon, the value elsewhere (SDB-148).
    r"|(?:REACH[-\s]?)?Registrier(?:ungs)?[-\s]?(?:nummer|nr\.?)\b.*"
    r"|Eindeutiger\s+Rezepturidentifikator.*"
    r"|Tele(?:fon|fax)|Fax|E-?Mail(?:-Adresse)?"
    # An article number's label, with its value or without (SDB-148):
    # "Artikelnr. (Hersteller/Lieferant): 12-345".
    r"|Art(?:ikel)?\.?\s?-?\s?(?:Nr|Nummer)\b.*"
    # The title of section 1 in another language, where its heading left it.
    r"|Identification\s+of\s+the\s+(?:substance|mixture|product)\b.*)$",
    re.IGNORECASE,
)
# "Produktform: Gemisch", "UFI: …": a label of something else with its value;
# a registration number's label may be longer, with the substance it belongs
# to ("REACH-Registrierungs-Nr. von n-Butylacetat: 01-…", SDB-148).
_LABELLED_VALUE = re.compile(
    r"^(?:[^:\d()]{2,40}|(?:REACH[-\s]?)?Registrier[^:]{2,80}):\s*\S", re.IGNORECASE
)
# An article number with its label in front of the name on the name's line
# (SDB-148): "Art.-Nr. 12.345 Musterdünger". The number is the whole run of
# its characters, with a digit in it: asked for ahead, so that a long run
# is not tried once for every digit in it.
_ARTICLE_NUMBER_FIRST = re.compile(
    r"^Art(?:ikel)?\.?\s?-?\s?(?:Nr|Nummer)\b\.?:?\s*(?=[\w./-]*\d)[\w./-]*\s+(?=\S)",
    re.IGNORECASE,
)
# Or its label behind the name, the number on the next line (SDB-148):
# "Musterspray 200 ml Art.Nr." Two words at least stand before it.
_ARTICLE_LABEL_LAST = re.compile(
    r"^((?=\S*?[^\W\d_])\S+\s+\S+(?:\s+\S+)*?)"
    r"\s+Art(?:ikel)?\.?\s?-?\s?(?:Nr|Nummer)\b\.?:?$",
    re.IGNORECASE,
)
# A supplier's label, alone or with its value: where 1.1 ends on a sheet
# that prints no heading for 1.2 or 1.3 (SDB-131).
_SUPPLIER_LABEL_LINE = re.compile(
    r"^(?:Hersteller|Lieferant|Firma|Firmenname|Firmenbezeichnung|Inverkehrbringer)"
    r"(?:\s*/\s*(?:Hersteller|Lieferant|Firma|Importeur|Vertrieb|Händler))*"
    r"\s*(?::.*)?$",
    re.IGNORECASE,
)
# The number of a subsection alone on its line.
_BARE_1_1 = re.compile(r"^1\s*[.,]\s*1\.?$")
_BARE_1_2 = re.compile(r"^1\s*[.,]\s*2\.?$")
# "Produkt: Musterreiniger" in a sheet's header (SDB-150).
_PRODUCT_LABEL = re.compile(r"^produkt$")
# A header line that is not the product's name (SDB-150): the sheet's title
# or what it was made by, its version, a date, a page.
_HEADER_LINE = re.compile(
    r"^(?:EU-|EG-)?Sicherheitsdatenbl[aä]tt|^gem(?:äß|äss|\.)\s"
    r"|^(?:nach|laut|entsprechend)\s+(?:der\s+)?(?:Verordnung|Richtlinie)"
    r"|^(?:Version|Revision|Fassung|Stand|Datum|Druck|Seite|Page|Ersetzt|Ersatz"
    r"|Überarbeit|Bearbeit|Erstell|Ausgabe|Ausstell|Gültig)"
    r"|\b\d{1,2}\s?[./]\s?\d{1,2}\s?[./]\s?(?:\d{4}|\d{2})\b"
    r"|\b(?:1907/2006|2020/878|453/2010|2015/830)\b",
    re.IGNORECASE,
)
# The heading of 1.2 behind a name, where the text lost the line break.
_HEADING_BEHIND_NAME = re.compile(r"\s*:?\s*1\s*\.\s*2\b\.?\s+Relevante\b.*$")


# A part in brackets. Only the text up to the last ")" can hold one; searched
# beyond it, a long run of "(" was read again to its end from each of them.
_BRACKETED = re.compile(r"\([^)]*\)")
# "UFI" in a label, with a comma and blanks before it. Without the comma it is
# tried from the first blank of a run only: a run of blanks, as the brackets
# above leave behind, was otherwise read again from each of them.
_UFI_IN_LABEL = re.compile(r",\s*ufi\b|(?<![\s,])\s*ufi\b")


def _label_parts(key: str) -> list[str]:
    key = _BEFORE_LABEL.sub("", key.casefold())
    closed = key.rfind(")") + 1
    key = _BRACKETED.sub(" ", key[:closed]) + key[closed:]
    key = _UFI_IN_LABEL.sub(" ", key)
    return [" ".join(part.split()) for part in re.split(r"/| oder ", key)]


def _is_trade_name_label(key: str) -> bool:
    return all(_TRADE_NAME_PART.match(part) for part in _label_parts(key))


def _is_name_label(key: str) -> bool:
    return all(
        _TRADE_NAME_PART.match(part) or _OTHER_NAME_PART.match(part)
        for part in _label_parts(key)
    )


def _name_value(value: str) -> str:
    """The name without the bullet or dash a sheet sets in front of it.

    Nor the article number a sheet prints in front of it with its label
    (SDB-148): "Art.-Nr. 12.345 Musterdünger".
    """
    name = _BULLET.sub("", _clean_value(value))
    name = _ARTICLE_NUMBER_FIRST.sub("", name)
    return _HEADING_BEHIND_NAME.sub("", name).strip()


# A reference to another place of the sheet where the name should stand
# (SDB-148): "Handelsname: siehe oben".
_REFERENCE = re.compile(r"^siehe\s+oben\.?$", re.IGNORECASE)


# What a product is, not what it is called (SDB-148): "Produktform" above
# "Gemisch".
_KIND_OF_PRODUCT = re.compile(
    r"^(?:Gemisch|Stoff|Mischung|Zubereitung|Erzeugnis|Mixture|Substance)\.?$",
    re.IGNORECASE,
)
# A label block's first value where an article number's label stands above
# the name's label (SDB-148): "Artikelnr." / "Handelsname" / "12345" /
# "Musterlack". One word with a digit is the number.
_ARTICLE_NUMBER_LABEL = re.compile(
    r"^Art(?:ikel)?\.?\s?-?\s?(?:Nr|Nummer)\b[^:]*$", re.IGNORECASE
)
_NUMBER_VALUE = re.compile(r"^\S*\d\S*$")


def _is_no_name(line: str) -> bool:
    """Whether *line* under a name's label is something other than the name."""
    return bool(
        _KIND_OF_PRODUCT.match(_BULLET.sub("", line).strip())
        or _REFERENCE.match(_BULLET.sub("", line).strip())
        or _OTHER_LABEL.match(_BULLET.sub("", line))
        or _LABELLED_VALUE.match(_BULLET.sub("", line))
        or _is_name_label(line.rstrip(": "))
        or not re.search(r"[^\W\d_]", line)
    )


def _extract_product_identifier(section_text: str) -> str | None:
    """The product's name as subsection 1.1 prints it (SDB-131).

    Behind a label that names the product, the trade name's first, on its
    line or on the next one that is no label; a heading "Produktidentifikator"
    is such a label. Further down in section 1 only behind a label with the
    name on its line.
    """
    if not section_text:
        return None

    lines = [
        _normalize_colon_spacing(line).strip()
        for line in _merge_broken_pairs(section_text.split("\n"))
    ]
    lines = [line for line in lines if line]
    end = _end_of_1_1(lines)
    first = lines[:end]
    for is_label in (_is_trade_name_label, _is_name_label):
        for line in first:
            key, _, value = line.partition(":")
            name = _name_value(value)
            if is_label(key) and _REFERENCE.match(name):
                # "Handelsname: siehe oben": the sheet names no product here,
                # and which line it means it does not say (SDB-148).
                return None
            if is_label(key) and name and not _is_name_label(name):
                return name
    for index, line in enumerate(first):
        if not _is_name_label(line.rstrip(": ")) and not _LABEL_THEN_NAME.match(
            _BULLET.sub("", line)
        ):
            continue
        number_first = False
        for later in first[index:]:
            bare = _BULLET.sub("", later)
            if _ARTICLE_NUMBER_LABEL.match(bare):
                number_first = True
            if number_first and _NUMBER_VALUE.match(bare):
                number_first = False
                continue
            joined = _LABEL_THEN_NAME.match(bare)
            if joined and not _is_name_label(bare.rstrip(": ")):
                # "Produktbezeichnung Musterreiniger": label and name, no colon.
                return _name_value(bare[joined.end() :])
            before_number = _ARTICLE_LABEL_LAST.match(bare)
            if before_number:
                # "Musterspray 200 ml Art.Nr.": the number stands below.
                return _name_value(before_number.group(1))
            if not _is_no_name(later):
                return _name_value(later)
    for line in lines[end:]:
        key, _, value = line.partition(":")
        if _is_trade_name_label(key) and _label_parts(key) != ["bezeichnung"]:
            name = _name_value(value)
            if name:
                return name
    return None


def _end_of_1_1(lines: list[str]) -> int:
    """Where subsection 1.1 ends among the lines of section 1 (SDB-131).

    At the heading of a later subsection, or at a supplier's label on a sheet
    that prints none. "1.2" alone under "1.1" alone is no heading: the sheet
    set both numbers in front of what follows.
    """
    for index, line in enumerate(lines):
        if not index:
            continue
        if _BARE_1_2.match(line) and _BARE_1_1.match(lines[index - 1]):
            continue
        if _AFTER_PRODUCT_IDENTIFIER.match(line) or _SUPPLIER_LABEL_LINE.match(
            _BULLET.sub("", line)
        ):
            return index
    return len(lines)


def _value_before_label(text: str) -> str | None:
    """The name a sheet prints above its label (SDB-149).

    ": Musterreiniger" / "Handelsname": the line with the colon and the value
    stands directly above the trade name's label, which is alone on its line
    and has no value below. Read from the sheet's text as it stands, up to
    the heading of 1.2: the sections' text has such a value joined to the
    label above it already.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for index, line in enumerate(lines):
        if index and _AFTER_PRODUCT_IDENTIFIER.match(line):
            break
        if not index or ":" in line or not _is_trade_name_label(line):
            continue
        above = lines[index - 1]
        below = lines[index + 1] if index + 1 < len(lines) else ""
        if above.startswith(":") and not below.startswith(":"):
            name = _name_value(above.lstrip(": "))
            if name and not _is_no_name(name):
                return name
    return None


def _lines_above_section_1(text: str) -> list[str]:
    """The lines of a sheet's header: what stands above its first section."""
    above: list[str] = []
    for line in _merge_split_headings(_merge_broken_pairs(text.split("\n"))):
        stripped = line.strip()
        if not stripped:
            continue
        if _read_section_heading(stripped) is not None:
            break
        subsection = SUBSECTION_PATTERN.match(stripped)
        if subsection and SUBSECTION_TITLES[int(subsection.group(1))].search(
            subsection.group(3)
        ):
            break
        above.append(stripped)
    return above


def _name_in_header(section_text: str, above: list[str]) -> str | None:
    """The product's name from the sheet's header, where 1.1 gives none (SDB-150).

    Behind a label of the trade name, or "Produkt", with the name on its line.
    Else, where 1.1 prints the trade name's label and leaves its field empty,
    the last line of the header, directly above section 1: the headline such
    a sheet sets its product's name in. Not a line that is the sheet's title,
    a date, a version, a page or another label's value.
    """
    for line in above:
        key, colon, value = _normalize_colon_spacing(line).partition(":")
        if not colon or not (
            _is_trade_name_label(key) or _PRODUCT_LABEL.match(key.strip().casefold())
        ):
            continue
        name = _name_value(value)
        if name and not _is_no_name(name):
            return name
    if not above or not _has_empty_name_field(section_text):
        return None
    last = above[-1]
    if _is_no_name(last) or _HEADER_LINE.search(last):
        return None
    return _name_value(last)


def _has_empty_name_field(section_text: str) -> bool:
    """Whether 1.1 prints the trade name's label with nothing behind it."""
    lines = [
        _normalize_colon_spacing(line).strip()
        for line in section_text.split("\n")
        if line.strip()
    ]
    return any(
        line.endswith(":") and _is_trade_name_label(line.rstrip(": "))
        for line in lines[: _end_of_1_1(lines)]
    )


def _extract_version(text: str) -> str | None:
    """
    Extract the document's own version from SDS text.

    REACH Annex II puts the revision indication on the first page, and in
    practice suppliers repeat it in a running header or footer on every page.
    Section 16 then lists the *superseded* versions once each. Searching the
    whole document therefore turns up several numbers, so the one repeated
    most often -- the running header -- is the document's own version, and a
    single mention is a reference to something else.

    Args:
        text: The full SDS text to search.

    Returns:
        The version string (e.g., "3.3") or None if not found.
    """
    for pattern in (
        VERSION_BEHIND_DATE_PATTERN,
        VERSION_PATTERN,
        REVISION_NUMBER_PATTERN,
    ):
        matches = [
            m.group(1).replace(",", ".").replace("-", ".")
            for m in pattern.finditer(text)
            # "(ersetzt Version 1.03)" sits in the same repeated footer line as
            # the current number, so it survives the frequency count. Reading
            # the words just before the label is what separates them.
            if not SUPERSEDED_MARKER.search(text[max(0, m.start() - 40) : m.start()])
            # "Letzte Version: 06.03.2023" names a day, not a number.
            and not _DATE_AS_VERSION.fullmatch(m.group(1))
        ]
        if not matches:
            continue
        counts = Counter(matches)
        top = max(counts.values())
        # Ties keep document order so the result stays deterministic.
        for value in matches:
            if counts[value] == top:
                return value
    return None


def _parse_date_parts(day: str, month: str, year: str) -> date | None:
    """Build a date from "23", "Nov", "2023" or "23", "11", "2023"."""
    if month.isdigit():
        month_number = int(month)
        if month_number > 12 and day.isdigit() and 1 <= int(day) <= 12:
            # "08/31/2020": month first, the only way the date can be read
            # (SDB-201).
            day, month_number = month, int(day)
    else:
        month_number = _MONTH_NAMES.get(month.casefold().rstrip(".")[:3], 0)
    try:
        return date(int(year), month_number, int(day))
    except ValueError:
        logger.warning("sds.date.invalid", value=f"{day}.{month}.{year}")
        return None


def _latest_dated_match(text: str, pattern: re.Pattern[str]) -> date | None:
    """Return the most recent date *pattern* finds, or None.

    Section 16 lists superseded revisions with their older dates, and a sheet
    can carry more than one dated label, so the newest is the one that
    describes the document in hand.
    """
    found = [
        parsed
        for match in pattern.finditer(text)
        if (parsed := _date_of(match)) is not None
    ]
    return max(found) if found else None


def _date_of(match: re.Match[str]) -> date | None:
    """The date a _DATED fragment matched, written day first or year first."""
    day, month, year, iso_year, iso_month, iso_day = match.groups()
    if day is None:
        return _parse_date_parts(iso_day, iso_month, iso_year)
    return _parse_date_parts(day, month, year)


def _extract_revision_date(text: str) -> date | None:
    """Extract the revision date ("Überarbeitet am: 16.11.2020") from SDS text."""
    found = [
        parsed
        for pattern in (
            REVISION_DATE_BEFORE_VERSION_PATTERN,
            REVISION_DATE_BEFORE_LABEL_PATTERN,
            REVISION_DATE_GRID_PATTERN,
            VERSION_CREATED_PATTERN,
            VERSION_CREATED_ABOVE_PATTERN,
        )
        if (parsed := _latest_dated_match(text, pattern)) is not None
    ]
    for match in REVISION_DATE_PATTERN.finditer(text):
        if _dates_another_version(text, match):
            continue
        dated: re.Match[str] | None = match
        while dated is not None:
            parsed = _date_of(dated)
            if parsed is not None:
                found.append(parsed)
            dated = _FURTHER_DATE.match(text, dated.end())
    return max(found) if found else None


def _dates_another_version(text: str, match: re.Match[str]) -> bool:
    """Whether *match* dates a version the sheet only names (SDB-57)."""
    if not _VERSION_LABEL_START.match(match.group(0)):
        return False
    before = text[max(0, match.start() - 60) : match.start()]
    return _OTHER_VERSION_BEFORE.search(before) is not None


def _extract_issue_date(text: str) -> date | None:
    """Extract the issue date ("Ausstellungsdatum: 11.07.2013") from SDS text."""
    return _latest_dated_match(text, ISSUE_DATE_PATTERN)


# A header table read column by column (SDB-90, step 1): the values first, each on a
# line of its own, then their labels in the same order.
#
#     02.01.2013          Erstfassung
#     08.04.2020          Überarbeitet am
_DATE_LABEL_LINE = re.compile(
    r"[^\S\n]*(?:(überarbeitet\s+am|überarbeitungsdatum|revisionsdatum)"
    r"|erstfassung|erstellt\s+am|erstellungsdatum|ausgabedatum|druckdatum)"
    r"[^\S\n]*:?[^\S\n]*",
    re.IGNORECASE,
)
_DATE_ONLY_LINE = re.compile(rf"[^\S\n]*{_DATE_FRAGMENT}[^\S\n]*")
# How far above its labels a column of values may stand.
_COLUMN_REACH = 15


def _extract_date_from_columns(text: str) -> date | None:
    """The revision date of a header table whose values precede their labels.

    Only where the count agrees: as many dates in a row as date labels in a
    row, so each date has its label.
    """
    lines = text.split("\n")
    found = []
    for index, line in enumerate(lines):
        label = _DATE_LABEL_LINE.fullmatch(line)
        if label is None or not label.group(1):
            continue
        first = index
        while first > 0 and _DATE_LABEL_LINE.fullmatch(lines[first - 1]):
            first -= 1
        last = index
        while last + 1 < len(lines) and _DATE_LABEL_LINE.fullmatch(lines[last + 1]):
            last += 1
        end = first
        while end > max(0, first - _COLUMN_REACH) and not _DATE_ONLY_LINE.fullmatch(
            lines[end - 1]
        ):
            end -= 1
        start = end
        while start > 0 and _DATE_ONLY_LINE.fullmatch(lines[start - 1]):
            start -= 1
        if end - start != last - first + 1 or end == start:
            continue
        match = _DATE_ONLY_LINE.fullmatch(lines[start + index - first])
        parsed = _parse_date_parts(*match.groups()) if match else None
        if parsed is not None:
            found.append(parsed)
    return max(found) if found else None


# How many lines below its label a revision date may stand (SDB-90, step 2).
_LABEL_REACH = 3


def _extract_date_below_label(text: str) -> date | None:
    """The revision date that stands a few lines below its label (SDB-90, step 2).

    A header whose cells reach the text one after another: "Überarbeitet am:",
    "Artikel-Nr.: 2297PR", "Seite 1 von 6", "17.07.2020". The lines between
    are complete in themselves; an empty line or another label without its
    value ends the search, because the date may be that label's.
    """
    lines = text.split("\n")
    found = []
    for index, line in enumerate(lines):
        label = _DATE_LABEL_LINE.fullmatch(line)
        if label is None or not label.group(1):
            continue
        for below in lines[index + 1 : index + 1 + _LABEL_REACH]:
            match = _DATE_ONLY_LINE.fullmatch(below)
            if match:
                parsed = _parse_date_parts(*match.groups())
                if parsed is not None:
                    found.append(parsed)
                break
            if not below.strip() or below.rstrip().endswith(":"):
                break
    return max(found) if found else None


# A month and a year (SDB-90): "STAND: 06/2022", "Stand: Februar 2003", or
# "03 / 2012" alone on a line. Last of all, and narrow: the number of a
# regulation looks the same ("Verordnung Nr. 8/1985", "NN 1/2021").
# Also behind the revision label: "Überarbeitet am: März 2013",
# "Überarbeitet am: April/2017".
_MONTH_YEAR_LABEL = (
    r"\b(?:Stand|Überarbeitet[^\S\n]+am|Überarbeitungsdatum|Revisionsdatum)"
    r"[^\S\n]*:[^\S\n]*"
)
MONTH_YEAR_PATTERN = re.compile(
    rf"{_MONTH_YEAR_LABEL}(0?[1-9]|1[0-2])[^\S\n]?/[^\S\n]?((?:19|20)\d{{2}})\b"
    rf"|{_MONTH_YEAR_LABEL}([A-Za-zä]{{3,9}})\.?(?:[^\S\n]+|[^\S\n]?/[^\S\n]?)"
    r"((?:19|20)\d{2})\b"
    r"|^[^\S\n]*(0[1-9]|1[0-2])[^\S\n]?/[^\S\n]?((?:19|20)\d{2})[^\S\n]*\.?[^\S\n]*$"
    # "Stand 10.2013" in a footer.
    r"|^[^\S\n]*Stand[^\S\n]*:?[^\S\n]*(0[1-9]|1[0-2])\.((?:19|20)\d{2})\b",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_month_year_date(text: str) -> date | None:
    """The newest month-and-year date of a sheet that states no other, as the
    first of its month, or None."""
    found = []
    for match in MONTH_YEAR_PATTERN.finditer(text):
        month, year = next(
            (match.group(i), match.group(i + 1)) for i in (1, 3, 5, 7) if match.group(i)
        )
        if not month.isdigit() and month.casefold()[:3] not in _MONTH_NAMES:
            continue
        parsed = _parse_date_parts("1", month, year)
        if parsed is not None:
            found.append(parsed)
    return max(found) if found else None


def _extract_short_year_date(text: str) -> date | None:
    """Read a date whose year is written with two digits, or None.

    See SHORT_YEAR_DATE_PATTERN: a last resort for a document that has yielded
    no date at all, never a substitute for one that has.
    """
    found = [
        parsed
        for match in SHORT_YEAR_DATE_PATTERN.finditer(text)
        if (
            parsed := _parse_date_parts(
                match.group(1), match.group(2), _expand_year(match.group(3))
            )
        )
        is not None
    ]
    return max(found) if found else None


def _expand_year(two_digits: str) -> str:
    """Expand a two-digit year, with the century boundary fixed at 90."""
    number = int(two_digits)
    return str(1900 + number if number >= 90 else 2000 + number)


def _extract_effective_date(text: str) -> date | None:
    """Extract the date a sheet states it takes effect, or None.

    See EFFECTIVE_DATE_PATTERN: this is a fallback for sheets that state no
    revision and no issue date, never a substitute for either.
    """
    return _latest_dated_match(text, EFFECTIVE_DATE_PATTERN)


def _merge_broken_pairs(lines: Iterable[str]) -> list[str]:
    merged: list[str] = []
    lines_list = list(lines)
    i = 0
    while i < len(lines_list):
        current = lines_list[i].rstrip()

        # Look ahead for colon, skipping blank lines
        j = i + 1
        while j < len(lines_list) and not lines_list[j].strip():
            j += 1

        next_line = lines_list[j].strip() if j < len(lines_list) else ""

        if next_line.startswith(":") and current.strip():
            value_text = next_line.lstrip(": ")

            # If colon line has no value, look for value on next line
            if not value_text:
                k = j + 1
                while k < len(lines_list) and not lines_list[k].strip():
                    k += 1
                if k < len(lines_list):
                    value_text = lines_list[k].strip()
                    # A key whose value the layout left empty, last in its
                    # section, is followed by the next section's heading -- and
                    # taking that as the value buries it mid-line, where no
                    # heading is read. "Das Produkt entspricht den Kriterien
                    # für PBT- oder vPvB-Stoffen ... 1907/2006 :" closes 2.3 on
                    # one supplier's sheets, and their section 3 opened a page
                    # late, at the running header, with the ingredient table
                    # filed under section 2.
                    if _is_section_heading(value_text):
                        merged.append(f"{current.strip()}:")
                        i = k
                        continue
                    merged.append(f"{current.strip()}: {value_text}")
                    i = k + 1
                    continue

            merged.append(f"{current.strip()}: {value_text}")
            i = j + 1
            continue

        merged.append(current)
        i += 1

    return merged


def _is_section_heading(line: str) -> bool:
    return (
        SECTION_HEADER_PATTERN.search(line) is not None
        or read_numbered_section_heading(line) is not None
    )


def _normalize_colon_spacing(line: str) -> str:
    return re.sub(r"\s*:\s*", ": ", line.strip())


def _clean_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
