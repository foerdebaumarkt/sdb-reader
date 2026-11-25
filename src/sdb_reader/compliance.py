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

from .expected import clp_expected
from .messages import Message
from .parser import (
    CLASSIFIED_BEFORE_CLP,
    EUH_WORDING_OUTSIDE_LABEL,
    LABEL_HEADING_PATTERN,
    LABEL_UNDETERMINED,
    NO_LABEL_SECTION,
    SheetPart,
    classification_codes_complete,
    classification_hazard_codes,
    without_lines,
)
from .pictograms import get_signal_word
from .schema import (
    FurtherLabel,
    HazardStatements,
    LabelKind,
    SafetyDataSheet,
    Section,
    StatedClassification,
)
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


class SheetDuty(StrEnum):
    """Whether a product needs a safety data sheet, by its sheet (SDB-76, SDB-218)."""

    # REACH Article 31 asks for one.
    REQUIRED = "required"
    # Not by what the sheet says: it is issued voluntarily.
    NOT_REQUIRED = "not-required"
    # The reading holds no label (SDB-216, SDB-217), and section 2 alone does
    # not say that a sheet is due: not checked under the rules in force.
    NOT_CHECKED = "not-checked"


def sheet_duty(sheet: SafetyDataSheet) -> SheetDuty:
    """Whether a sheet is issued for a product that needs one.

    SDB-76, SDB-142, SDB-154, SDB-218, SDB-220.

    REACH Article 31(1) requires a safety data sheet for a classified product
    and Article 31(3) one on request where the label carries EUH210. So a
    sheet is required where section 2 classifies the product
    (``stated_classification``, as SDB-75 reads it), or where the label carries what only a classified
    product's label does -- an H statement, a signal word, a pictogram -- or
    an EUH statement that owes a sheet (EUH210, and EUH208, EUH204 and
    EUH205 for a sensitising substance, SDB-220), or the sentence that a
    safety data sheet is to be had on request, under whichever law the label
    stands. P statements alone are
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
    first: there the supplier says at the label that one is due. For a
    mixture the statements of a sensitising substance go first as well.

    A sheet kept as a record is read back with ``sheet_from_dict``.

    >>> from sdb_reader import HazardStatements
    >>> def sheet(label=None, **stated):
    ...     return SafetyDataSheet(
    ...         None, None, None, None, "de",
    ...         hazard_statements=label or HazardStatements(), **stated
    ...     )
    >>> sheet_duty(sheet(HazardStatements(hazard_codes=["H315"])))
    <SheetDuty.REQUIRED: 'required'>
    >>> sheet_duty(sheet(HazardStatements(supplemental_codes=["EUH210"])))
    <SheetDuty.REQUIRED: 'required'>
    >>> sheet_duty(sheet(HazardStatements(precautionary_codes=["P102"])))
    <SheetDuty.NOT_REQUIRED: 'not-required'>
    >>> sheet_duty(
    ...     sheet(
    ...         HazardStatements(
    ...             supplemental_text="Sicherheitsdatenblatt auf Anfrage für "
    ...             "berufsmäßige Verwender erhältlich."
    ...         )
    ...     )
    ... )
    <SheetDuty.REQUIRED: 'required'>
    >>> sheet_duty(sheet(stated_classification=StatedClassification.CLASSIFIED))
    <SheetDuty.REQUIRED: 'required'>
    >>> sheet_duty(
    ...     sheet(
    ...         HazardStatements(hazard_codes=["H314"]),
    ...         stated_voluntary=True,
    ...         stated_article=True,
    ...     )
    ... )
    <SheetDuty.NOT_REQUIRED: 'not-required'>
    >>> sheet_duty(
    ...     sheet(
    ...         stated_classification=StatedClassification.CLASSIFIED,
    ...         stated_article=True,
    ...     )
    ... )
    <SheetDuty.NOT_REQUIRED: 'not-required'>
    >>> sheet_duty(
    ...     sheet(HazardStatements(supplemental_codes=["EUH210"]), stated_article=True)
    ... )
    <SheetDuty.REQUIRED: 'required'>
    >>> sheet_duty(
    ...     sheet(HazardStatements(hazard_codes=["H314"]), stated_voluntary=True)
    ... )
    <SheetDuty.REQUIRED: 'required'>
    >>> sheet_duty(
    ...     sheet(HazardStatements(supplemental_codes=["EUH208"]), stated_voluntary=True)
    ... )
    <SheetDuty.REQUIRED: 'required'>
    >>> sheet_duty(sheet(HazardStatements(supplemental_codes=["EUH066", "EUH401"])))
    <SheetDuty.NOT_REQUIRED: 'not-required'>
    >>> sheet_duty(
    ...     sheet(HazardStatements(supplemental_codes=["EUH210"]), stated_voluntary=True)
    ... )
    <SheetDuty.REQUIRED: 'required'>
    >>> sheet_duty(sheet(label_withheld="before-2017-06"))
    <SheetDuty.NOT_CHECKED: 'not-checked'>
    >>> sheet_duty(
    ...     sheet(
    ...         stated_classification=StatedClassification.CLASSIFIED,
    ...         label_withheld="incomplete",
    ...     )
    ... )
    <SheetDuty.REQUIRED: 'required'>
    >>> sheet_duty(sheet(label_withheld="incomplete"))
    <SheetDuty.NOT_CHECKED: 'not-checked'>
    """
    if sheet.label_withheld == "before-2017-06":
        return SheetDuty.NOT_CHECKED
    if sheet.label_withheld is not None:
        classified = _label_requires_sheet(
            HazardStatements(),
            sheet.stated_classification,
            voluntary=sheet.stated_voluntary,
            article=sheet.stated_article,
        )
        return SheetDuty.REQUIRED if classified else SheetDuty.NOT_CHECKED
    # What a small package's label carries speaks of the same product: its
    # contents do not change with the package (SDB-76, SDB-188).
    labels = [
        sheet.hazard_statements,
        *(
            further.label
            for further in sheet.hazard_statements.further_labels
            if further.kind is LabelKind.SMALL_PACKAGE
        ),
    ]
    required = any(
        _label_requires_sheet(
            label,
            sheet.stated_classification,
            voluntary=sheet.stated_voluntary,
            article=sheet.stated_article,
        )
        for label in labels
    )
    return SheetDuty.REQUIRED if required else SheetDuty.NOT_REQUIRED


def _label_requires_sheet(
    hazards: HazardStatements,
    stated: StatedClassification = StatedClassification.NOT_STATED,
    *,
    voluntary: bool = False,
    article: bool = False,
) -> bool:
    """``sheet_duty`` for a label and what the sheet states beside it."""
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
    owed = not DUTY_STATEMENTS.isdisjoint(hazards.supplemental_codes)
    if article:
        return on_request or "EUH210" in hazards.supplemental_codes
    if voluntary and not hazardous:
        return on_request or owed
    if classified:
        return True
    if hazards.hazard_codes or hazards.signal_word or hazards.pictograms or owed:
        return True
    return on_request


# The EUH statements by which a label says that a sheet is owed (SDB-220):
# EUH210 itself, and those that name a sensitising substance, which REACH
# Article 31(3)(b) owes a sheet for on request. The others (EUH066, EUH401,
# EUH211, EUH212, EUH202 …) rest on something else and owe none.
DUTY_STATEMENTS = frozenset({"EUH210", "EUH208", "EUH204", "EUH205"})


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
    law (SDB-73), and not for an article, which is not labelled under
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
    # Where the label may be a small package's, a label without what such a
    # package may leave out is no finding (SDB-194).
    hazards = sheet.section_text.get(Section.HAZARDS, "")
    classified = {base_code(c) for c in classification_hazard_codes(hazards)}
    small_may_be = not prints_small_package_label(label)
    if not label.hazard_codes and not (
        small_may_be and classified and all(map(small_package_may_omit, classified))
    ):
        findings.append(Message("label-without-hazard-statement"))
    product = classified | {base_code(c) for c in label.hazard_codes}
    if not label.precautionary_codes and not (
        small_may_be
        and product
        and all(
            small_package_may_omit(code) or code in _SMALL_PACKAGE_OMITS_PRECAUTIONS
            for code in product
        )
    ):
        findings.append(Message("label-without-precautionary-statement"))
    return findings


# The hazard statements CLP Annex I 1.5.2.1.1 lets a package of at most 125 ml
# leave out (consolidated version of 1 July 2026), each standing for categories
# of the list only: oxidising gas 1 (H270), gases under pressure (H280, H281),
# flammable liquid 2 and 3 (H225, H226), flammable solid 1 and 2 (H228),
# self-reactive and organic peroxide types C to F (H242), self-heating 2
# (H252), water-reactive 1 to 3 (H260, H261), oxidising liquid and solid 2
# and 3 (H272), skin irritation 2 (H315), eye irritation 2 (H319), aquatic
# acute 1 (H400), aquatic chronic 1 and 2 (H410, H411); and 1.5.2.1.3 metal
# corrosion (H290). SDB-194.
_SMALL_PACKAGE_OMITS = frozenset(
    {
        "H225", "H226", "H228", "H242", "H252", "H260", "H261", "H270", "H272",
        "H280", "H281", "H290", "H315", "H319", "H400", "H410", "H411",
    }
)  # fmt: skip
# Those 1.5.2.1.1 lets it leave out only where the product is not supplied to
# the general public: acute toxicity 4, STOT SE 2 and 3, STOT RE 2. Who buys
# the product the sheet does not say (SDB-183).
_SMALL_PACKAGE_OMITS_NOT_PUBLIC = frozenset(
    {"H302", "H312", "H332", "H335", "H336", "H371", "H373"}
)
# The categories whose precautionary statements alone 1.5.2.1.2 lets it leave
# out: effects on or via lactation, aquatic chronic 3 and 4. H221 stands for
# flammable gas 1B as well, which the list does not name.
_SMALL_PACKAGE_OMITS_PRECAUTIONS = frozenset({"H362", "H412", "H413"})


def small_package_may_omit(code: str) -> bool:
    """Whether a package of at most 125 ml may go without the hazard statement
    *code* (CLP Annex I 1.5.2.1.1 and 1.5.2.1.3; SDB-194). Not an aerosol's
    own statements: Directive 75/324/EEC, to which 1.5.2.1.1 refers, requires
    them on every aerosol dispenser (Art. 8(1), Annex 2.2; SDB-198)."""
    return code in _SMALL_PACKAGE_OMITS or code in _SMALL_PACKAGE_OMITS_NOT_PUBLIC


def prints_small_package_label(label: HazardStatements) -> bool:
    """Whether the sheet prints a small package's label beside *label*, by a
    heading or a sentence naming what it leaves out (SDB-188, SDB-189): the
    label is then that of a larger package."""
    return any(f.kind is LabelKind.SMALL_PACKAGE for f in label.further_labels)


def _label_is_judged(sheet: SafetyDataSheet, noted: Collection[str]) -> bool:
    """Whether the label findings apply to *sheet* (SDB-170): a product
    classified under CLP, no article and no classification under the old law.
    *noted* are the codes of the parser's warnings."""
    if sheet.stated_classification is not StatedClassification.CLASSIFIED:
        return False
    return not _label_is_exempt(sheet, noted)


def _label_is_exempt(sheet: SafetyDataSheet, noted: Collection[str]) -> bool:
    """Whether *sheet* is not labelled under CLP (SDB-170): an article or a
    classification under the old law. A label under the old directives stands
    on sheets before 2021, which get no label findings (SDW-49)."""
    return sheet.stated_article or CLASSIFIED_BEFORE_CLP in noted


# The pictogram that makes Article 26 leave out GHS07, in the order
# suppress_pictograms tries them.
_GHS07_GIVES_WAY_TO = ("GHS06", "GHS05", "GHS08")


def pictogram_findings(
    sheet: SafetyDataSheet, parser_warnings: Iterable[Message]
) -> list[Message]:
    """What the label's pictograms say against its H codes (SDB-181), from
    ``clp_expected`` (BIB-25).

    ``pictogram-not-found`` for each pictogram the codes call for that the
    label neither names nor shows, only where the label was looked at as
    drawn and every red diamond in it was named (``drawing_read``), not where
    the label states it has none;
    ``pictogram-not-expected`` for each pictogram the label names or shows
    that none of its H codes calls for, not GHS08 on an aerosol, where it may
    stand for the aspiration hazard; ``pictogram-precedence`` for a
    pictogram the label shows although Article 26 CLP leaves it out beside
    another. Not for an article or a classification under the old law
    (SDB-170), and nothing where the label carries no H code.

    >>> from sdb_reader import HazardStatements
    >>> label = HazardStatements(
    ...     hazard_codes=["H225", "H319"],
    ...     pictograms=["GHS02", "GHS09"],
    ...     drawing_read=True,
    ... )
    >>> sheet = SafetyDataSheet(None, None, None, None, "de", hazard_statements=label)
    >>> [(m.code, m.params["pictogram"]) for m in pictogram_findings(sheet, [])]
    [('pictogram-not-found', 'GHS07'), ('pictogram-not-expected', 'GHS09')]
    """
    label = sheet.hazard_statements
    noted = {warning.code for warning in parser_warnings}
    if not label.hazard_codes or _label_is_exempt(sheet, noted):
        return []
    expected = clp_expected(label)
    findings: list[Message] = []
    if label.drawing_read and not label.states_no_pictograms:
        findings.extend(
            Message("pictogram-not-found", {"pictogram": code})
            for code in expected.pictograms_missing
        )
    # GHS08 on an aerosol may stand for the aspiration hazard, which Annex I
    # 1.3.3 lets the label leave out with H304: no finding where it may be
    # right (SDB-181, SDB-183).
    hazards = sheet.section_text.get(Section.HAZARDS, "")
    findings.extend(
        Message("pictogram-not-expected", {"pictogram": code})
        for code in expected.pictograms_not_expected
        if code != "GHS08"
        or not _is_aerosol(
            hazards, {*label.hazard_codes, *classification_hazard_codes(hazards)}
        )
    )
    printed = set(label.pictograms)
    findings.extend(
        Message(
            "pictogram-precedence",
            {
                "pictogram": code,
                "beside": next(c for c in _GHS07_GIVES_WAY_TO if c in printed),
            },
        )
        for code in expected.pictograms_left_out
    )
    return findings


def signal_word_not_found(
    sheet: SafetyDataSheet, parser_warnings: Iterable[Message]
) -> list[Message]:
    """The signal word the label's codes call for and the parser did not find
    printed (SDB-178), with the word under ``expected``, from ``clp_expected``
    (BIB-25).

    Not where the label states it has none (SDB-176), and not for an article
    or a classification under the old law (SDB-170).

    >>> from sdb_reader import HazardStatements
    >>> label = HazardStatements(hazard_codes=["H225"])
    >>> [m.params for m in signal_word_not_found(
    ...     SafetyDataSheet(None, None, None, None, "de", hazard_statements=label), [])]
    [{'expected': 'Gefahr'}]
    """
    label = sheet.hazard_statements
    expected = clp_expected(label)
    if not expected.signal_word_missing or label.states_no_signal_word:
        return []
    if _label_is_exempt(sheet, {warning.code for warning in parser_warnings}):
        return []
    return [Message("signal-word-not-found", {"expected": expected.signal_word})]


# The order of precedence Annex III Part 1 sets under Article 27 (consolidated
# version of 1 July 2026): a statement the label may leave out beside another.
_LEFT_OUT_BESIDE = {"H400": "H410", "H318": "H314"}
# An aerosol: its class in 2.1 or one of its statements (Annex I 2.3).
_AEROSOL_CLASS = re.compile(r"\bAerosol\s?[123]\b")
_AEROSOL_STATEMENTS = frozenset({"H222", "H223", "H229"})


def _not_required(
    code: str, on_label: set[str], classified: set[str], sheet: SafetyDataSheet
) -> bool:
    """Whether the label may go without *code* although 2.1 names it (SDB-173).

    Beside H410 or H314 the label may leave out H400 or H318 (CLP Annex III
    Part 1 under Article 27). A product placed on the market as an aerosol, or
    in a container with a sealed spray attachment the sheet names, need not be
    labelled for the aspiration hazard, H304 (Annex I 1.3.3; SDB-195).
    """
    if _LEFT_OUT_BESIDE.get(code) in on_label:
        return True
    hazards = sheet.section_text.get(Section.HAZARDS, "")
    return code == "H304" and (
        _is_aerosol(hazards, classified | on_label) or _names_sealed_spray(sheet)
    )


# A sealed spray attachment, or Annex I 1.3.3 named as the reason to leave the
# aspiration hazard out (SDB-195): "Behälter mit versiegelter
# Sprühvorrichtung", "… Anhang 1 Abs. 1.3.3.".
_SEALED_SPRAY = re.compile(
    r"versiegelte\w*\s+Spr(?:ü|ue)hvorrichtung|\bAnhang\b[^\n]{0,60}?\b1\.3\.3\b",
    re.IGNORECASE,
)


def _names_sealed_spray(sheet: SafetyDataSheet) -> bool:
    """Whether section 2 or 3 names a sealed spray attachment or Annex I 1.3.3
    (SDB-195)."""
    return any(
        _SEALED_SPRAY.search(sheet.section_text.get(section, ""))
        for section in (Section.HAZARDS, Section.COMPOSITION)
    )


def _is_aerosol(hazards: str, codes: Collection[str]) -> bool:
    """Whether the product is placed on the market as an aerosol (SDB-173):
    section 2, its text *hazards*, classes it as one, or its classification
    or label names one of the aerosol's statements among *codes*."""
    return bool(_AEROSOL_CLASS.search(hazards)) or not _AEROSOL_STATEMENTS.isdisjoint(
        codes
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
    Where the sheet prints no small package's label beside it, the label may be
    one, and a statement such a package may leave out gives no finding (CLP
    Annex I 1.5.2.1; SDB-194); an aerosol's own statements are none of them
    (SDB-198).

    >>> from sdb_reader import HazardStatements
    >>> section = (
    ...     "2.1 Einstufung des Stoffs oder Gemischs\n"
    ...     "Aerosol 3, H229\nAquatic Acute 1, H400\nAquatic Chronic 1, H410\n"
    ...     "Skin Sens. 1, H317\n"
    ...     "2.2 Kennzeichnungselemente\n"
    ... )
    >>> sheet = SafetyDataSheet(
    ...     None, None, None, None, "de",
    ...     hazard_statements=HazardStatements(hazard_codes=["H410"]),
    ...     stated_classification=StatedClassification.CLASSIFIED,
    ...     section_text={Section.HAZARDS: section},
    ... )
    >>> [m.params["statement"] for m in hazard_statements_not_in_label(sheet, [])]
    ['H229', 'H317']
    """
    noted = {warning.code for warning in parser_warnings}
    label = sheet.hazard_statements
    if not label.hazard_codes or not _label_is_judged(sheet, noted):
        return []
    hazards = sheet.section_text.get(Section.HAZARDS, "")
    heading = LABEL_HEADING_PATTERN.search(hazards)
    # Without the blocks beside the label (SDB-188 to SDB-190).
    printed = hazards[heading.start() :] if heading else ""
    for further in label.further_labels:
        printed = without_lines(
            printed, [further.heading, *(further.text or "").split("\n")]
        )
    # Where the label may be a small package's, what such a package may
    # leave out is no finding (SDB-194).
    small_may_be = not prints_small_package_label(label)
    return [
        Message("hazard-statement-not-in-label", {"statement": code})
        for code in _not_carried(sheet, label, printed, small_package=small_may_be)
    ]


def _not_carried(
    sheet: SafetyDataSheet,
    label: HazardStatements,
    printed: str,
    *,
    small_package: bool,
) -> list[str]:
    """The H codes of the classification in 2.1 that *label*, printed as
    *printed*, does not carry and has to (SDB-173); with *small_package*
    not those a package of at most 125 ml may leave out (SDB-194)."""
    hazards = sheet.section_text.get(Section.HAZARDS, "")
    label_text = _comparable(printed)
    on_label = {base_code(code) for code in label.hazard_codes}
    # Without the wordings of its own statements: "Giftig für Wasserorganismen,
    # mit langfristiger Wirkung" (H411) stands inside H410's.
    wordings = _catalogue()
    for code in on_label:
        if own := wordings.get(code):
            label_text = label_text.replace(_comparable(own), " ")
    classified = {base_code(code) for code in classification_hazard_codes(hazards)}
    missing: list[str] = []
    for code in sorted(classification_hazard_codes(hazards)):
        base = base_code(code)
        if base in on_label or _not_required(base, on_label, classified, sheet):
            continue
        if small_package and small_package_may_omit(base):
            continue
        # The label prints the statement's wording without its code.
        wording = wordings.get(base)
        if wording and _comparable(wording) in label_text:
            continue
        missing.append(code)
    return missing


# The statements Annex III Part 1 lets a label leave out beside another
# (_LEFT_OUT_BESIDE): a classification that names H410 or H314 may leave out
# H400 or H318 in the same way, and a label that prints them prints what it
# calls for. Not the other way round: H410 does not follow from H400.
_AEROSOL_CATEGORY = re.compile(r"\bAerosol\s?([123])\b")
_AEROSOL_CALLS_FOR = {
    "1": {"H222", "H229"},
    "2": {"H223", "H229"},
    "3": {"H229"},
}


def hazard_statements_not_classified(
    sheet: SafetyDataSheet, parser_warnings: Iterable[Message]
) -> list[Message]:
    r"""Each H statement the label prints that the classification in 2.1 does
    not call for (SDB-197), with its code as ``statement`` and the codes 2.1
    names as ``classified``.

    Either side may be the wrong one, and the finding does not say which.
    Only where 2.1 names H codes and the label prints one; not for H360 or
    H361 that 2.1 names with other letters, nor for H400 or H318 where 2.1
    names H410 or H314 (Annex III Part 1).
    The size of the package does not matter: a statement printed instead of
    another is no statement left out.

    >>> from sdb_reader import HazardStatements
    >>> section = (
    ...     "2.1 Einstufung des Stoffs oder Gemischs\n"
    ...     "Aquatic Acute 1, H400\nAquatic Chronic 2, H411\n"
    ...     "2.2 Kennzeichnungselemente\n"
    ... )
    >>> sheet = SafetyDataSheet(
    ...     None, None, None, None, "de",
    ...     hazard_statements=HazardStatements(hazard_codes=["H410"]),
    ...     stated_classification=StatedClassification.CLASSIFIED,
    ...     section_text={Section.HAZARDS: section},
    ... )
    >>> [m.params for m in hazard_statements_not_classified(sheet, [])]
    [{'statement': 'H410', 'classified': 'H400, H411'}]
    """
    label = sheet.hazard_statements
    if not label.hazard_codes or not _label_is_judged(
        sheet, {warning.code for warning in parser_warnings}
    ):
        return []
    hazards = sheet.section_text.get(Section.HAZARDS, "")
    named = sorted(classification_hazard_codes(hazards))
    classified = {base_code(code) for code in named}
    if not classified or not classification_codes_complete(hazards):
        return []
    # An aerosol's category calls for its statements, also where 2.1 names
    # only one of them ("Aerosol 1, H222"): Annex I Table 2.3.1.
    for category in _AEROSOL_CATEGORY.findall(hazards):
        classified |= _AEROSOL_CALLS_FOR[category]
    for code, category in (("H222", "1"), ("H223", "2")):
        if code in classified:
            classified |= _AEROSOL_CALLS_FOR[category]
    return [
        Message(
            "hazard-statement-not-classified",
            {"statement": code, "classified": ", ".join(named)},
        )
        for code in label.hazard_codes
        if base_code(code) not in classified
        and _LEFT_OUT_BESIDE.get(base_code(code)) not in classified
    ]


# The H codes whose signal word depends on the category, which the code does
# not tell (Annex I Tables 2.1.2, 2.2.2, 2.7.2, 2.8.2, 2.12.2, 2.13.2/2.14.2,
# 2.15.2): H207, H221, H228, H242, H261, H272 (SDB-199).
_SIGNAL_WORD_BY_CATEGORY = frozenset({"H207", "H221", "H228", "H242", "H261", "H272"})


def signal_word_conflict(printed: str | None, codes: Collection[str]) -> str | None:
    """What *codes* call for where the printed signal word surely conflicts
    with them (SDB-199), else None: "Gefahr" where "Achtung" is printed and a
    code calls for "Gefahr" whatever its category (Art. 20(1), (3)); "Achtung"
    or "none" where "Gefahr" is printed and no code can call for it.

    >>> signal_word_conflict("Achtung", {"H270", "H280"})
    'Gefahr'
    >>> signal_word_conflict("Achtung", {"H228"}) is None
    True
    >>> signal_word_conflict("Gefahr", {"H315"})
    'Achtung'
    >>> signal_word_conflict("Gefahr", {"H412"})
    'none'
    """
    words = {code: get_signal_word({code}) for code in codes}
    if printed == "Achtung" and any(
        word == "Gefahr" and base_code(code) not in _SIGNAL_WORD_BY_CATEGORY
        for code, word in words.items()
    ):
        return "Gefahr"
    if printed == "Gefahr" and not any(
        word == "Gefahr" or base_code(code) in _SIGNAL_WORD_BY_CATEGORY
        for code, word in words.items()
    ):
        return get_signal_word(set(codes)) or "none"
    return None


def _product_codes(sheet: SafetyDataSheet, *labels: HazardStatements) -> set[str]:
    """The codes of the product (SDB-193): those of the classification in
    2.1 and of *labels*, H and EUH; without H304 on an aerosol or where the
    sheet names a sealed spray attachment (Annex I 1.3.3)."""
    hazards = sheet.section_text.get(Section.HAZARDS, "")
    codes = set(classification_hazard_codes(hazards))
    for label in labels:
        codes |= {*label.hazard_codes, *label.supplemental_codes}
    if _is_aerosol(hazards, codes) or _names_sealed_spray(sheet):
        codes.discard("H304")
    return codes


def signal_word_conflicts(
    sheet: SafetyDataSheet, parser_warnings: Iterable[Message]
) -> list[Message]:
    r"""Where the signal word a label prints conflicts with what the product's
    codes call for (SDB-199): ``signal-word-conflicts`` for the label,
    ``small-package-signal-word-conflicts`` for a small package's label, with
    the word ``printed`` and the one ``expected`` ("none" for none). Either
    side may be the wrong one.

    "Gefahr" where none can be called for only where 2.1 names a code for
    every class it names (SDB-197): a code it leaves out might call for it.
    Not where the label states it has no signal word; with the exceptions of
    SDB-170.

    >>> from sdb_reader import HazardStatements
    >>> section = "2.1 Einstufung\nOx. Gas 1, H270\nPress. Gas, H280\n2.2 Kennzeichnungselemente\n"
    >>> sheet = SafetyDataSheet(
    ...     None, None, None, None, "de",
    ...     hazard_statements=HazardStatements(
    ...         hazard_codes=["H270", "H280"], signal_word="Achtung"),
    ...     stated_classification=StatedClassification.CLASSIFIED,
    ...     section_text={Section.HAZARDS: section},
    ... )
    >>> [(m.code, m.params) for m in signal_word_conflicts(sheet, [])]
    [('signal-word-conflicts', {'printed': 'Achtung', 'expected': 'Gefahr'})]
    """
    if not _label_is_judged(sheet, {w.code for w in parser_warnings}):
        return []
    hazards = sheet.section_text.get(Section.HAZARDS, "")
    complete = classification_codes_complete(hazards)
    label = sheet.hazard_statements

    # The labels of a sheet speak of one product (SDB-76): any of them may
    # hold the code that can call for "Gefahr". That a code calls for it is
    # sure only of 2.1 and the label judged, beside a small package's the
    # product's label; another label of an inconsistent sheet is not (SDB-199).
    small = [
        further.label
        for further in label.further_labels
        if further.kind is LabelKind.SMALL_PACKAGE
    ]
    every = _product_codes(sheet, label, *small)

    def conflict(
        printing: HazardStatements, *callers: HazardStatements
    ) -> dict[str, str] | None:
        if printing.signal_word is None:
            return None
        expected = signal_word_conflict(printing.signal_word, every)
        if expected == "Gefahr" and (
            signal_word_conflict(printing.signal_word, _product_codes(sheet, *callers))
            != "Gefahr"
        ):
            return None
        if expected is None or (expected != "Gefahr" and not complete):
            return None
        return {"printed": printing.signal_word, "expected": expected}

    findings: list[Message] = []
    if (found := conflict(label, label)) is not None:
        findings.append(Message("signal-word-conflicts", found))
    for further in label.further_labels:
        if _judged_small_package(further) and (
            found := conflict(further.label, label, further.label)
        ):
            findings.append(Message("small-package-signal-word-conflicts", found))
    return findings


def small_package_findings(
    sheet: SafetyDataSheet, parser_warnings: Iterable[Message]
) -> list[Message]:
    """What each small package's label the sheet prints beside its label
    lacks that CLP Annex I 1.5.2.1 requires on such a package too (SDB-193).

    Only for a small package's label that prints an element or states it has
    none; with the exceptions of SDB-170. A hazard statement of 2.1 it does
    not carry, unless such a package may leave it out (SDB-194); the signal
    word and the pictograms the product's codes call for -- those of the
    classification in 2.1, of the label and of the small package's label,
    since 1.5.2.1.1 leaves out statements and never a pictogram or the
    signal word -- without H290 (1.5.2.1.3) and, on an aerosol, the
    aerosol's statements (``clp_expected`` with ``small_package``). A
    pictogram only where its drawing was read.
    """
    if not _label_is_judged(sheet, {w.code for w in parser_warnings}):
        return []
    hazards = sheet.section_text.get(Section.HAZARDS, "")
    product = {
        *classification_hazard_codes(hazards),
        *sheet.hazard_statements.hazard_codes,
    }
    # An aerosol, or a sealed spray attachment the sheet names, is not
    # labelled for the aspiration hazard (Annex I 1.3.3; SDB-173, SDB-195).
    if _is_aerosol(hazards, product) or _names_sealed_spray(sheet):
        product.discard("H304")
    findings: list[Message] = []
    for further in sheet.hazard_statements.further_labels:
        if not _judged_small_package(further):
            continue
        small = further.label
        text = further.text or ""
        printed = "\n".join(
            filter(
                None,
                [small.hazard_text, small.precautionary_text, small.supplemental_text],
            )
        )
        if small.hazard_codes or _NAMES_HAZARD_STATEMENTS.search(text):
            findings.extend(
                Message(
                    "small-package-hazard-statement-not-in-label", {"statement": code}
                )
                for code in _not_carried(sheet, small, printed, small_package=True)
            )
        # As the small package's label prints its signal word and pictograms,
        # against what the product's codes call for (SDB-193).
        expected = clp_expected(
            HazardStatements(
                hazard_codes=sorted(product | set(small.hazard_codes)),
                supplemental_codes=small.supplemental_codes,
                signal_word=small.signal_word,
                pictograms=small.pictograms,
            ),
            small_package=True,
        )
        if (
            expected.signal_word_missing
            and not small.states_no_signal_word
            and _NAMES_SIGNAL_WORD.search(text)
        ):
            findings.append(
                Message(
                    "small-package-signal-word-not-found",
                    {"expected": expected.signal_word},
                )
            )
        if (
            small.drawing_read
            and not small.states_no_pictograms
            and (small.pictograms or _NAMES_PICTOGRAMS.search(text))
        ):
            findings.extend(
                Message("small-package-pictogram-not-found", {"pictogram": code})
                for code in expected.pictograms_missing
            )
    return findings


# Where a small package's label speaks of an element (SDB-193): the name of
# its field, "Signalwort", "Piktogramme", "Gefahrenhinweise", "H-Sätze".
_NAMES_SIGNAL_WORD = re.compile(r"^\W*Signalw(?:o|ö)rt", re.IGNORECASE | re.MULTILINE)
_NAMES_PICTOGRAMS = re.compile(r"Piktogramm|Gefahrensymbol", re.IGNORECASE)
_NAMES_HAZARD_STATEMENTS = re.compile(
    r"Gefahrenhinweis|\bH\s*-\s*(?:und\s+P\s*-\s*)?S(?:ä|ae)tze", re.IGNORECASE
)


def _judged_small_package(further: FurtherLabel) -> bool:
    """Whether *further* is a small package's label that prints an element of
    a label or states it has none (SDB-193)."""
    label = further.label
    return further.kind is LabelKind.SMALL_PACKAGE and bool(
        label.hazard_codes
        or label.precautionary_codes
        or label.supplemental_codes
        or label.signal_word
        or label.pictograms
        or label.states_no_signal_word
        or label.states_no_pictograms
    )


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


def usable_dates(
    sheet: SafetyDataSheet,
    today: date | None = None,
    parts: Sequence[SheetPart] = (),
) -> tuple[date | None, date | None]:
    """The revision and the issue date that can be right (SDB-137, SDB-182).

    Without *today* the dates as read. With it, a date after that day is
    no date; for a file of several sheets (*parts*), each is the newest that
    the file or one of its sheets names and that is not after that day.
    """
    if today is None:
        return sheet.revision_date, sheet.issue_date
    sheets = [sheet, *(part.sheet for part in parts)]

    def newest(days: list[date | None]) -> date | None:
        possible = [day for day in days if day is not None and day <= today]
        return max(possible) if possible else None

    return (
        newest([one.revision_date for one in sheets]),
        newest([one.issue_date for one in sheets]),
    )


def counted_date(
    sheet: SafetyDataSheet,
    today: date | None = None,
    parts: Sequence[SheetPart] = (),
) -> date | None:
    """The date a sheet's age is judged by (SDW-7, SDW-34).

    Its revision date, else its issue date, of those that can be right
    (``usable_dates``).
    """
    revision, issue = usable_dates(sheet, today, parts)
    return revision or issue


def _dated(
    sheet: SafetyDataSheet, today: date | None, revised: date | None
) -> list[Message]:
    """A date in the future, and the age by *revised*: undated or before 2021."""
    findings: list[Message] = []
    if today is not None:
        printed_revision, printed_issue = sheet.revision_date, sheet.issue_date
        if printed_revision is not None and printed_revision > today:
            findings.append(
                Message(
                    "revised-in-future",
                    {
                        "revised": printed_revision.isoformat(),
                        "today": today.isoformat(),
                    },
                )
            )
        if printed_issue is not None and printed_issue > today:
            findings.append(
                Message(
                    "issued-in-future",
                    {"issued": printed_issue.isoformat(), "today": today.isoformat()},
                )
            )
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
        and sheet_duty(sheet) is SheetDuty.REQUIRED
        and lacks_annex_ii_2020(sheet.section_text)
    ):
        return [Message("old-format", {"revised": revised.isoformat()})]
    return []


def age_findings(sheet: SafetyDataSheet, today: date | None = None) -> list[Message]:
    """The findings on one sheet's age, judged on its own dates (SDW-46).

    The same as for a file that is this sheet: a date in the future,
    undated, revised before 2021, or the layout before 2020/878.
    """
    revised = counted_date(sheet, today)
    return [*_dated(sheet, today, revised), *_old_format(sheet, revised)]


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
    """What is wrong with *sheet* as a document (SDW-7, SDW-9, SDW-50).

    A sheet whose label the reading withholds (``label_withheld``: a sheet of
    the rules before June 2017, SDB-216, or an incomplete label, SDB-217)
    gets only the findings on its age and those on a file of several sheets
    (SDW-49).

    *parts* are the sheets of a file that holds several
    (``ParsedSheet.parts``); with them, what they say about each other
    is among the findings (``several_sheets_findings``).

    *today* is the day the caller takes as the present; the library has no
    clock of its own. With it, a revision date (or, where the sheet names
    none, an issue date) after that day is reported and does not count for
    the sheet's age: the sheet is judged by its issue date where that is no
    later than *today*, else like a sheet without a date (SDB-137). A file
    of several sheets is judged by the newest date one of them names that
    is not after *today* (SDB-182). Without *today* no date is questioned.

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
    revised = counted_date(sheet, today, parts)
    age = [*_dated(sheet, today, revised), *_old_format(sheet, revised)]
    if sheet.label_withheld is not None:
        # A sheet whose label is not given gets only the findings on its age:
        # one of the rules before June 2017 is to be renewed and its label is
        # not read (SDW-49, SDB-216); for an incomplete one the error names
        # what the label lacks (SDB-217).
        return [*age, *several_sheets_findings(parts)]

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

    findings.extend(age)

    hazards = sheet.hazard_statements
    state = classification(hazards.hazard_codes, hazards.signal_word, parser_warnings)
    if state is Classification.UNDETERMINED:
        findings.append(Message("classification-undetermined"))
    if state is Classification.OLD_SYSTEM:
        findings.append(Message("old-classification"))

    if (
        state is Classification.NOT_CLASSIFIED
        and sheet.stated_classification is StatedClassification.NOT_STATED
        and not _label_requires_sheet(hazards)
    ):
        findings.append(Message("classification-not-stated"))

    if contradicts_label(sheet):
        findings.append(Message("classification-contradicts-label"))
    findings.extend(pictogram_findings(sheet, parser_warnings))

    findings.extend(label_not_found(sheet, parser_warnings))
    findings.extend(hazard_statements_not_in_label(sheet, parser_warnings))
    findings.extend(signal_word_not_found(sheet, parser_warnings))
    # Sheet by sheet in a file of several: each label against its own 2.1.
    if parts:
        not_classified: list[Message] = []
        for part in parts:
            for found in hazard_statements_not_classified(part.sheet, part.warnings):
                if found not in not_classified:
                    not_classified.append(found)
        findings.extend(not_classified)
    else:
        findings.extend(hazard_statements_not_classified(sheet, parser_warnings))
    findings.extend(small_package_findings(sheet, parser_warnings))
    if parts:
        conflicts: list[Message] = []
        for part in parts:
            for found in signal_word_conflicts(part.sheet, part.warnings):
                if found not in conflicts:
                    conflicts.append(found)
        findings.extend(conflicts)
    else:
        findings.extend(signal_word_conflicts(sheet, parser_warnings))

    findings.extend(
        Message("euh-outside-label", dict(outside.params))
        for outside in euh_outside_label(parser_warnings)
    )
    findings.extend(several_sheets_findings(parts))
    return findings
