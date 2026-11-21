"""What one safety data sheet says about itself as a document.

Not about our reading of it: whether a sheet can meet the Annex II in force,
whether it states a classification at all, and what it prints outside its
label are the supplier's to put right, and no parser work changes them. They
are judged from what the parser read; reporting them is the caller's.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import asdict
from datetime import date
from enum import StrEnum

from .messages import Message
from .parser import (
    CLASSIFIED_BEFORE_CLP,
    EUH_WORDING_OUTSIDE_LABEL,
    LABEL_BEFORE_CLP,
    LABEL_HEADING_PATTERN,
    LABEL_UNDETERMINED,
    NO_LABEL_SECTION,
    SheetPart,
    classification_hazard_codes,
)
from .schema import HazardStatements, SafetyDataSheet, Section, StatedClassification
from .statements import (
    SHEET_ON_REQUEST,
    _catalogue,
    _comparable,
    base_code,
    deviates_from_regulation,
    label_statements,
)

# Annex II of REACH in the version of Regulation (EU) 2020/878 applies from
# 1 January 2021; sheets not conforming to it could be supplied until
# 31 December 2022. A sheet last revised before this date therefore cannot
# comply -- not as a matter of judgement but of structure, because it lacks
# fields the 2020 amendment introduced: the UFI, nanoform particle
# characteristics, endocrine-disrupting properties in 2.3, 11.2 and 12.6, and
# ATE and M-factors in section 3.
ANNEX_II_2020_878 = date(2021, 1, 1)


# Mixtures are classified and labelled under CLP from 1 June 2015 (Regulation
# (EC) No 1272/2008, Art. 61). A sheet last revised before that cannot be the
# valid sheet of a product that needs one.
CLP_FOR_MIXTURES = date(2015, 6, 1)


def predates_clp(revised: date) -> bool:
    """Whether a sheet last revised on *revised* predates CLP for mixtures.

    >>> from datetime import date
    >>> predates_clp(date(2015, 5, 31)), predates_clp(date(2015, 6, 1))
    (True, False)
    """
    return revised < CLP_FOR_MIXTURES


def predates_annex_ii(revised: date) -> bool:
    """Whether a sheet last revised on *revised* cannot meet Annex II as amended
    by Regulation (EU) 2020/878.

    >>> from datetime import date
    >>> predates_annex_ii(date(2020, 12, 31)), predates_annex_ii(date(2021, 1, 1))
    (True, False)
    """
    return revised < ANNEX_II_2020_878


# What a sheet in the 2020 version of Annex II prints and an older one cannot:
# the endocrine-disrupting properties (2.3, 11.2.1, 12.6) and the subsections
# the amendment added, 11.2 and 12.7. A date alone does not show the format:
# sheets in the older one could be issued until 31 December 2022, and some
# carry a later date all the same. Measured over 12,600 sheets, 97 % of
# those revised in 2023 or later print all three; one is enough here, because
# what is missing may also be what the reader did not get.
_ENDOCRINE = re.compile(r"endokrin", re.IGNORECASE)
_SUBSECTION_11_2 = re.compile(
    r"(?m)^[^\S\n]*[-·•*]?[^\S\n]*11\s?\.\s?2\b(?!\s?\.?\s?\d)"
)
_SUBSECTION_12_7 = re.compile(r"(?m)^[^\S\n]*[-·•*]?[^\S\n]*12\s?\.\s?7\b")


def lacks_annex_ii_2020(section_text: Mapping[Section, str]) -> bool:
    """Whether a sheet prints none of what the 2020 version of Annex II added.

    Judged only where sections 11 and 12 were read: without them their
    subsections cannot be missed.

    >>> lacks_annex_ii_2020(
    ...     {Section.TOXICOLOGY: "11.1 Angaben", Section.ECOLOGY: "12.1 Toxizität"}
    ... )
    True
    >>> lacks_annex_ii_2020(
    ...     {
    ...         Section.TOXICOLOGY: "11.2 Angaben über sonstige Gefahren",
    ...         Section.ECOLOGY: "12.7 Andere schädliche Wirkungen",
    ...     }
    ... )
    False
    """
    toxicology = section_text.get(Section.TOXICOLOGY) or ""
    ecology = section_text.get(Section.ECOLOGY) or ""
    if not toxicology.strip() or not ecology.strip():
        return False
    if _SUBSECTION_11_2.search(toxicology) or _SUBSECTION_12_7.search(ecology):
        return False
    return not any(_ENDOCRINE.search(text or "") for text in section_text.values())


def requires_sheet(sheet: SafetyDataSheet) -> bool:
    """Whether a sheet is issued for a product that needs one.

    SDB-76, SDB-142, SDB-154.

    REACH Article 31(1) requires a safety data sheet for a classified product
    and Article 31(3) one on request where the label carries EUH210. So a
    sheet is required where section 2 classifies the product
    (``stated_classification``, as SDB-75 reads it), or where the label carries what only a classified
    product's label does -- an H statement, a signal word, a pictogram -- or
    an EUH statement, or the sentence that a safety data sheet is to be had
    on request, under whichever law the label stands. P statements alone are
    advice a supplier may print on anything. A sheet without any of it is
    issued voluntarily.

    A sheet that says of itself that it is issued voluntarily or that none is
    prescribed for its product (``stated_voluntary``, as SDB-142 reads it) is
    taken at its word where the duty allows it. For an article
    (``stated_article``: the sheet
    calls the product one, beside that sentence or by saying that as an
    article it is not subject to labelling, SDB-154) Article 31 knows no
    duty, whatever the label prints and whether or not the sheet calls
    itself voluntary. For a mixture it is so while the mixture is
    not classified: not where section 2 classifies it or the label carries an
    H statement, since Article 31(4) spares the supplier the sheet of a
    hazardous mixture only towards the general public and leaves it due to a
    downstream user or distributor who asks. In either case a label that
    carries EUH210 or the sentence that a sheet is to be had on request goes
    first: there the supplier says at the label that one is due.

    A sheet kept as a record is read back with ``sheet_from_dict``.

    >>> from sdb_reader import HazardStatements
    >>> def sheet(label=None, **stated):
    ...     return SafetyDataSheet(
    ...         None, None, None, None, "de",
    ...         hazard_statements=label or HazardStatements(), **stated
    ...     )
    >>> requires_sheet(sheet(HazardStatements(hazard_codes=["H315"])))
    True
    >>> requires_sheet(sheet(HazardStatements(supplemental_codes=["EUH210"])))
    True
    >>> requires_sheet(sheet(HazardStatements(precautionary_codes=["P102"])))
    False
    >>> requires_sheet(
    ...     sheet(
    ...         HazardStatements(
    ...             supplemental_text="Sicherheitsdatenblatt auf Anfrage für "
    ...             "berufsmäßige Verwender erhältlich."
    ...         )
    ...     )
    ... )
    True
    >>> requires_sheet(sheet(stated_classification=StatedClassification.CLASSIFIED))
    True
    >>> requires_sheet(
    ...     sheet(
    ...         HazardStatements(hazard_codes=["H314"]),
    ...         stated_voluntary=True,
    ...         stated_article=True,
    ...     )
    ... )
    False
    >>> requires_sheet(
    ...     sheet(
    ...         stated_classification=StatedClassification.CLASSIFIED,
    ...         stated_article=True,
    ...     )
    ... )
    False
    >>> requires_sheet(
    ...     sheet(HazardStatements(supplemental_codes=["EUH210"]), stated_article=True)
    ... )
    True
    >>> requires_sheet(
    ...     sheet(HazardStatements(hazard_codes=["H314"]), stated_voluntary=True)
    ... )
    True
    >>> requires_sheet(
    ...     sheet(HazardStatements(supplemental_codes=["EUH208"]), stated_voluntary=True)
    ... )
    False
    >>> requires_sheet(
    ...     sheet(HazardStatements(supplemental_codes=["EUH210"]), stated_voluntary=True)
    ... )
    True
    """
    return _label_requires_sheet(
        sheet.hazard_statements,
        sheet.stated_classification,
        voluntary=sheet.stated_voluntary,
        article=sheet.stated_article,
    )


def _label_requires_sheet(
    hazards: HazardStatements,
    stated: StatedClassification = StatedClassification.NOT_STATED,
    *,
    voluntary: bool = False,
    article: bool = False,
) -> bool:
    """``requires_sheet`` for a label and what the sheet states beside it."""
    # In the words of the directive before CLP the sentence stands under no
    # code (SDB-123): it is what asks for the sheet.
    on_request = (
        hazards.supplemental_text is not None
        and SHEET_ON_REQUEST.search(hazards.supplemental_text) is not None
    )
    classified = stated in (
        StatedClassification.CLASSIFIED,
        StatedClassification.OLD_SYSTEM,
    )
    hazardous = classified or bool(hazards.hazard_codes)
    if article or (voluntary and not hazardous):
        return on_request or "EUH210" in hazards.supplemental_codes
    if classified:
        return True
    if (
        hazards.hazard_codes
        or hazards.supplemental_codes
        or hazards.signal_word
        or hazards.pictograms
    ):
        return True
    return on_request


def contradicts_label(sheet: SafetyDataSheet) -> bool:
    """Whether section 2 says "not classified" while the label carries what only
    a classified product's label does (SDB-79): an H statement, a signal word or
    a pictogram. An EUH statement is no contradiction; an unclassified mixture
    may have to carry one.

    >>> from sdb_reader import HazardStatements
    >>> def sheet(label):
    ...     return SafetyDataSheet(
    ...         None, None, None, None, "de", hazard_statements=label,
    ...         stated_classification=StatedClassification.NOT_CLASSIFIED,
    ...     )
    >>> contradicts_label(sheet(HazardStatements(signal_word="Achtung")))
    True
    >>> contradicts_label(sheet(HazardStatements(supplemental_codes=["EUH210"])))
    False
    """
    label = sheet.hazard_statements
    return sheet.stated_classification is StatedClassification.NOT_CLASSIFIED and bool(
        label.hazard_codes or label.signal_word or label.pictograms
    )


def label_not_found(
    sheet: SafetyDataSheet, parser_warnings: Iterable[Message]
) -> list[Message]:
    """What the label of a product section 2 classifies should carry and the
    parser did not find in it (SDB-169 to SDB-172).

    The reading stays as it is: these are findings beside it, and each says
    "not found", which is true whether the sheet lacks it or the parser missed
    it. Only for a product classified under CLP (SDB-75); not under the old
    law (SDB-73), not for a label under the old directives on a sheet dated
    before 1 June 2015, and not for an article, which is not labelled under
    CLP (SDB-142, SDB-154). A label counts as found where the parser found its
    block (SDB-4), or, without one, read any element of a label in section 2.

    >>> from sdb_reader import HazardStatements
    >>> def sheet(label, stated=StatedClassification.CLASSIFIED):
    ...     return SafetyDataSheet(
    ...         None, None, None, None, "de", hazard_statements=label,
    ...         stated_classification=stated,
    ...     )
    >>> [m.code for m in label_not_found(sheet(HazardStatements()),
    ...                                  [Message(NO_LABEL_SECTION)])]
    ['label-not-found']
    >>> [m.code for m in label_not_found(
    ...     sheet(HazardStatements(signal_word="Achtung", precautionary_codes=["P210"])),
    ...     [])]
    ['label-without-hazard-statement']
    >>> label_not_found(sheet(HazardStatements(), StatedClassification.NOT_STATED), [])
    []
    """
    noted = {warning.code for warning in parser_warnings}
    if not _label_is_judged(sheet, noted):
        return []
    label = sheet.hazard_statements
    read_any = bool(
        label.hazard_codes
        or label.precautionary_codes
        or label.supplemental_codes
        or label.signal_word
        or label.pictograms
    )
    if NO_LABEL_SECTION in noted and not read_any:
        return [Message("label-not-found")]
    findings: list[Message] = []
    if not label.hazard_codes:
        findings.append(Message("label-without-hazard-statement"))
    if not label.precautionary_codes:
        findings.append(Message("label-without-precautionary-statement"))
    return findings


def _label_is_judged(sheet: SafetyDataSheet, noted: Collection[str]) -> bool:
    """Whether the label findings apply to *sheet* (SDB-170): a product
    classified under CLP, no article, no classification under the old law, and
    no label under the old directives on a sheet dated before 1 June 2015.
    *noted* are the codes of the parser's warnings."""
    if sheet.stated_classification is not StatedClassification.CLASSIFIED:
        return False
    return not _label_is_exempt(sheet, noted)


def _label_is_exempt(sheet: SafetyDataSheet, noted: Collection[str]) -> bool:
    """Whether *sheet* is not labelled under CLP (SDB-170): an article, a
    classification under the old law, or a label under the old directives on a
    sheet dated before 1 June 2015."""
    if sheet.stated_article or CLASSIFIED_BEFORE_CLP in noted:
        return True
    # A mixture could be labelled under the old directives until 1 June 2015.
    dated = sheet.revision_date or sheet.issue_date
    return LABEL_BEFORE_CLP in noted and dated is not None and dated < CLP_FOR_MIXTURES


def signal_word_not_found(
    sheet: SafetyDataSheet, parser_warnings: Iterable[Message]
) -> list[Message]:
    """The signal word the label's codes call for and the parser did not find
    printed (SDB-178), with the word under ``expected``.

    The reading keeps the printed signal word only (SDB-176); the one the codes
    call for stands in ``expected_signal_word``. Not for an article, a
    classification under the old law, or a label under the old directives on a
    sheet dated before 1 June 2015 (SDB-170).

    >>> from sdb_reader import HazardStatements
    >>> label = HazardStatements(hazard_codes=["H225"], expected_signal_word="Gefahr")
    >>> [m.params for m in signal_word_not_found(
    ...     SafetyDataSheet(None, None, None, None, "de", hazard_statements=label), [])]
    [{'expected': 'Gefahr'}]
    """
    expected = sheet.hazard_statements.expected_signal_word
    if expected is None or sheet.hazard_statements.signal_word is not None:
        return []
    if _label_is_exempt(sheet, {warning.code for warning in parser_warnings}):
        return []
    return [Message("signal-word-not-found", {"expected": expected})]


# The order of precedence Annex III Part 1 sets under Article 27 (consolidated
# version of 1 July 2026): a statement the label may leave out beside another.
_LEFT_OUT_BESIDE = {"H400": "H410", "H318": "H314"}
# An aerosol: its class in 2.1 or one of its statements (Annex I 2.3).
_AEROSOL_CLASS = re.compile(r"\bAerosol\s?[123]\b")
_AEROSOL_STATEMENTS = frozenset({"H222", "H223", "H229"})


def _not_required(
    code: str, on_label: set[str], classified: set[str], hazards: str
) -> bool:
    """Whether the label may go without *code* although 2.1 names it (SDB-173).

    Beside H410 or H314 the label may leave out H400 or H318 (CLP Annex III
    Part 1 under Article 27). A product placed on the market as an aerosol need
    not be labelled for the aspiration hazard, H304 (Annex I 1.3.3).
    """
    if _LEFT_OUT_BESIDE.get(code) in on_label:
        return True
    return code == "H304" and bool(
        _AEROSOL_CLASS.search(hazards) or (classified | on_label) & _AEROSOL_STATEMENTS
    )


def hazard_statements_not_in_label(
    sheet: SafetyDataSheet, parser_warnings: Iterable[Message]
) -> list[Message]:
    r"""Each H statement of the classification in 2.1 that the label does not
    carry (SDB-173), with its code as ``statement``.

    Only where the label carries at least one H statement -- without any,
    ``label-without-hazard-statement`` says so (SDB-171) -- and with the
    exceptions of SDB-170. A code counts as carried where the label carries the
    same statement, H360 and H361 whatever their letters, and H400 and H318 also
    where the label carries H410 or H314 (CLP Article 27 with Annex III Part 1).

    >>> from sdb_reader import HazardStatements
    >>> section = (
    ...     "2.1 Einstufung des Stoffs oder Gemischs\n"
    ...     "Aerosol 3, H229\nAquatic Acute 1, H400\nAquatic Chronic 1, H410\n"
    ...     "2.2 Kennzeichnungselemente\n"
    ... )
    >>> sheet = SafetyDataSheet(
    ...     None, None, None, None, "de",
    ...     hazard_statements=HazardStatements(hazard_codes=["H410"]),
    ...     stated_classification=StatedClassification.CLASSIFIED,
    ...     section_text={Section.HAZARDS: section},
    ... )
    >>> [m.params["statement"] for m in hazard_statements_not_in_label(sheet, [])]
    ['H229']
    """
    noted = {warning.code for warning in parser_warnings}
    label = sheet.hazard_statements
    if not label.hazard_codes or not _label_is_judged(sheet, noted):
        return []
    hazards = sheet.section_text.get(Section.HAZARDS, "")
    heading = LABEL_HEADING_PATTERN.search(hazards)
    label_text = _comparable(hazards[heading.start() :]) if heading else ""
    on_label = {base_code(code) for code in label.hazard_codes}
    # Without the wordings of its own statements: "Giftig für Wasserorganismen,
    # mit langfristiger Wirkung" (H411) stands inside H410's.
    wordings = _catalogue()
    for code in on_label:
        if own := wordings.get(code):
            label_text = label_text.replace(_comparable(own), " ")
    classified = {base_code(code) for code in classification_hazard_codes(hazards)}
    missing: list[Message] = []
    for code in sorted(classification_hazard_codes(hazards)):
        base = base_code(code)
        if base in on_label or _not_required(base, on_label, classified, hazards):
            continue
        # The label prints the statement's wording without its code.
        wording = wordings.get(base)
        if wording and _comparable(wording) in label_text:
            continue
        missing.append(Message("hazard-statement-not-in-label", {"statement": code}))
    return missing


class Classification(StrEnum):
    """What a sheet's label states about the product's classification."""

    # The label says the classification was not determined: neither classified
    # nor established as not classified, a sheet without an answer.
    UNDETERMINED = "undetermined"
    # The label carries an H-code or a signal word.
    CLASSIFIED = "classified"
    # Section 2 classifies by the rules before CLP, with R phrases and hazard
    # symbols (SDB-73): the product is classified, and the sheet has no label
    # the regulation in force knows.
    OLD_SYSTEM = "classified-old-system"
    NOT_CLASSIFIED = "not-classified"


def classification(
    hazard_codes: Collection[str],
    signal_word: str | None,
    parser_warnings: Iterable[Message],
) -> Classification:
    """What the label states, from the parser's codes, signal word and warnings.

    A label that says nobody determined the classification counts as that even
    where the parser found codes elsewhere in section 2.

    >>> classification(["H315"], "Achtung", []).value
    'classified'
    >>> classification([], None, []).value
    'not-classified'
    """
    noted = {warning.code for warning in parser_warnings}
    if LABEL_UNDETERMINED in noted:
        return Classification.UNDETERMINED
    if CLASSIFIED_BEFORE_CLP in noted:
        return Classification.OLD_SYSTEM
    if hazard_codes:
        return Classification.CLASSIFIED
    if signal_word is not None and signal_word.strip().lower() in {
        "gefahr",
        "achtung",
    }:
        return Classification.CLASSIFIED
    return Classification.NOT_CLASSIFIED


def euh_outside_label(parser_warnings: Iterable[Message]) -> list[Message]:
    """The EUH statements the sheet prints only outside its label (SDB-28).

    The parser's messages about them, each with the statement's code and the
    sentence as printed.
    """
    return [
        warning
        for warning in parser_warnings
        if warning.code == EUH_WORDING_OUTSIDE_LABEL
    ]


# How a sheet names the part of a product it is for: "Komponente A", "Komp.
# B", "Comp. A", "Part C", "Teil B", "PTA", "erste Komponente".
_COMPONENT = re.compile(
    r"\b(?:(?:komponente|komp\.?|component|comp\.?|part|teil)\s*([a-d])[a-z]?"
    r"|pt([a-d])|(?:erste|zweite|dritte)\s+komponente)\b",
    re.IGNORECASE,
)
# What a part of a product is called beside its letter, or instead of it.
_COMPONENT_ROLE = re.compile(
    r"\b(?:harz|härter|haerter|mörtel|moertel|basis)\b", re.IGNORECASE
)
# An addition in brackets or a number at the end of a name: "(Finish)", "-019".
# The separators start only where a run of them starts: the same tail, and a
# long run of them is read once.
_NAME_TAIL = re.compile(r"(?:\([^()]*\)|(?<![\s,;:–-])[\s,;:–-]+\d{2,4})\s*$")
_NOT_A_NAME_S = re.compile(r"[^\w]+")


def _folded_name(name: str) -> str:
    return _NOT_A_NAME_S.sub(" ", name.casefold()).strip()


def _product(name: str) -> str:
    """*name* without what tells one part of a product from another (SDB-139)."""
    name = _COMPONENT.sub(" ", name)
    name = _COMPONENT_ROLE.sub(" ", name)
    stripped = _NAME_TAIL.sub("", name.strip())
    while stripped != name.strip():
        name, stripped = stripped, _NAME_TAIL.sub("", stripped.strip())
    return _folded_name(stripped)


def same_product(names: Sequence[str]) -> bool:
    """Whether sheets named *names* are for one product (SDB-139).

    They are where the names are the same once a component's designation, a
    component's role, an addition in brackets at the end and a number at the
    end are left out; and where every name carries a component's letter and
    the letters are not all the same ("… PTA" beside "… PART B").

    >>> same_product(["Musterkleber Komponente A", "Musterkleber Komponente B"])
    True
    >>> same_product(["Musterfarbe (Harz)", "Musterfarbe (Härter)"])
    True
    >>> same_product(["Musterfarbe", "Musterlack"])
    False
    """
    if len({_product(name) for name in names}) <= 1:
        return True
    letters = [
        {(match.group(1) or match.group(2) or "").casefold() for match in found} - {""}
        for found in (list(_COMPONENT.finditer(name)) for name in names)
    ]
    return all(letters) and len(set().union(*letters)) > 1


# What sheets of one product for different countries are compared in.
_EDITION_FIELDS = (
    "hazard_codes",
    "precautionary_codes",
    "supplemental_codes",
    "signal_word",
    "pictograms",
)


def several_sheets_findings(parts: Sequence[SheetPart]) -> list[Message]:
    """What the sheets of one file say about each other (SDB-139, SDB-140).

    *parts* are the sheets of a file that holds several, each read on its
    own (``ParsedSheet.parts``). That they are for different products
    is said where every sheet's product name is read and the names are not
    one product's (``same_product``); where a name is not read, nothing is
    said, because it cannot be told. Sheets with the same name that are for
    different countries are compared, and the fields they differ in are
    named.
    """
    findings: list[Message] = []
    names = [part.sheet.product_identifier or "" for part in parts]
    if len(parts) > 1 and all(names) and not same_product(names):
        findings.append(
            Message("different-products", {"products": list(dict.fromkeys(names))})
        )
    differing: list[str] = []
    for index, one in enumerate(parts):
        for other in parts[index + 1 :]:
            if not _are_editions(one.sheet, other.sheet):
                continue
            differing.extend(
                name
                for name in _edition_differences(one.sheet, other.sheet)
                if name not in differing
            )
    if differing:
        findings.append(Message("country-editions-differ", {"fields": differing}))
    return findings


def _are_editions(one: SafetyDataSheet, other: SafetyDataSheet) -> bool:
    """Whether two sheets are the same product's for different countries."""
    return bool(
        one.product_identifier
        and other.product_identifier
        and _folded_name(one.product_identifier)
        == _folded_name(other.product_identifier)
        and one.countries
        and other.countries
        and set(one.countries) != set(other.countries)
    )


def _edition_differences(one: SafetyDataSheet, other: SafetyDataSheet) -> list[str]:
    a, b = asdict(one.hazard_statements), asdict(other.hazard_statements)
    names = [
        name
        for name in _EDITION_FIELDS
        if (set(a[name] or ()) if isinstance(a[name], list) else a[name])
        != (set(b[name] or ()) if isinstance(b[name], list) else b[name])
    ]
    if one.stated_classification is not other.stated_classification:
        names.append("stated_classification")
    return names


def counted_date(sheet: SafetyDataSheet, today: date | None = None) -> date | None:
    """The date a sheet's age is judged by (SDW-7, SDW-34).

    Its revision date, else its issue date; with *today*, neither of them
    when it lies after that day (SDB-137).
    """
    return next(
        (
            day
            for day in (sheet.revision_date, sheet.issue_date)
            if day is not None and (today is None or day <= today)
        ),
        None,
    )


def _dated(sheet: SafetyDataSheet, today: date | None) -> list[Message]:
    """A date in the future, and the sheet's age: undated or before 2021."""
    findings: list[Message] = []
    stated = sheet.revision_date or sheet.issue_date
    if today is not None and stated is not None and stated > today:
        findings.append(
            Message(
                "revised-in-future",
                {"revised": stated.isoformat(), "today": today.isoformat()},
            )
        )
    revised = counted_date(sheet, today)
    if revised is None:
        findings.append(Message("undated"))
    elif predates_annex_ii(revised):
        findings.append(Message("predates-annex-ii", {"revised": revised.isoformat()}))
    return findings


def _old_format(sheet: SafetyDataSheet, revised: date | None) -> list[Message]:
    """A sheet revised from 2021 on that follows the layout before (SDW-9)."""
    if (
        revised is not None
        and not predates_annex_ii(revised)
        and requires_sheet(sheet)
        and lacks_annex_ii_2020(sheet.section_text)
    ):
        return [Message("old-format", {"revised": revised.isoformat()})]
    return []


def age_findings(sheet: SafetyDataSheet, today: date | None = None) -> list[Message]:
    """The findings on one sheet's age, judged on its own dates (SDW-46).

    The same as for a file that is this sheet: a date in the future,
    undated, revised before 2021, or the layout before 2020/878.
    """
    return [*_dated(sheet, today), *_old_format(sheet, counted_date(sheet, today))]


def oldest_sheet(
    parts: Sequence[SheetPart], today: date | None = None
) -> tuple[int, date, str] | None:
    """The sheet of a file of several with the oldest date (SDW-45).

    Its number in the file's order (from 1), its date and whether that is
    its revision or its issue date; the first where several share the
    oldest; None where no sheet carries a date that counts.
    """
    best: tuple[int, date, str] | None = None
    for number, part in enumerate(parts, start=1):
        day = counted_date(part.sheet, today)
        if day is None:
            continue
        dated_by = "revision" if day == part.sheet.revision_date else "issue"
        if best is None or day < best[1]:
            best = (number, day, dated_by)
    return best


def sheet_findings(
    sheet: SafetyDataSheet,
    parser_warnings: Sequence[Message],
    *,
    today: date | None = None,
    parts: Sequence[SheetPart] = (),
) -> list[Message]:
    """What is wrong with *sheet* as a document (SDW-6, SDW-7, SDW-9).

    *parts* are the sheets of a file that holds several
    (``ParsedSheet.parts``); with them, what they say about each other
    is among the findings (``several_sheets_findings``).

    *today* is the day the caller takes as the present; the library has no
    clock of its own. With it, a revision date (or, where the sheet names
    none, an issue date) after that day is reported and does not count for
    the sheet's age: the sheet is judged by its issue date where that is no
    later than *today*, else like a sheet without a date (SDB-137). Without
    *today* no date is questioned.

    *parser_warnings* are the warnings of the parser's result for the sheet.
    Each finding is a message; where it concerns one statement, its values
    name it as ``statement``.

    >>> from sdb_reader import extraction_from_dict, read_extraction
    >>> text = (
    ...     "Sicherheitsdatenblatt\\n"
    ...     "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs\\n"
    ...     "Produktname: Musterfarbe\\n"
    ...     "ABSCHNITT 2: Mögliche Gefahren\\n"
    ...     "Verordnung (EG) Nr. 1907/2006\\n"
    ...     "Signalwort: Achtung\\n"
    ...     "H315: Verursacht Hautreizungen.\\n"
    ...     "P280: Schutzhandschuhe tragen.\\n"
    ... )
    >>> result = read_extraction(
    ...     extraction_from_dict(
    ...         {"text": text, "extractor": "pymupdf", "pages_sampled": 1, "warnings": []}
    ...     )
    ... ).parser_result
    >>> [finding.code for finding in sheet_findings(result.sheet, result.warnings)]
    ['undated']
    """
    findings: list[Message] = []
    for statement in label_statements(sheet.hazard_statements):
        if (
            statement.sheet is not None
            and statement.regulation is not None
            and deviates_from_regulation(statement.code, statement.sheet)
        ):
            findings.append(
                Message(
                    "wording-deviates",
                    {
                        "statement": statement.code,
                        "sheet": statement.sheet,
                        "regulation": statement.regulation,
                    },
                )
            )

    findings.extend(_dated(sheet, today))
    revised = counted_date(sheet, today)

    hazards = sheet.hazard_statements
    state = classification(hazards.hazard_codes, hazards.signal_word, parser_warnings)
    if state is Classification.UNDETERMINED:
        findings.append(Message("classification-undetermined"))
    if state is Classification.OLD_SYSTEM:
        findings.append(Message("old-classification"))
    findings.extend(_old_format(sheet, revised))

    if (
        state is Classification.NOT_CLASSIFIED
        and sheet.stated_classification is StatedClassification.NOT_STATED
        and not _label_requires_sheet(hazards)
    ):
        findings.append(Message("classification-not-stated"))

    if contradicts_label(sheet):
        findings.append(Message("classification-contradicts-label"))

    findings.extend(label_not_found(sheet, parser_warnings))
    findings.extend(hazard_statements_not_in_label(sheet, parser_warnings))
    findings.extend(signal_word_not_found(sheet, parser_warnings))

    findings.extend(
        Message("euh-outside-label", dict(outside.params))
        for outside in euh_outside_label(parser_warnings)
    )
    findings.extend(several_sheets_findings(parts))
    return findings
