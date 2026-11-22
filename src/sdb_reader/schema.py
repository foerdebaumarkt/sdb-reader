"""Structured representation of Sicherheitsdatenblatt content."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum, StrEnum


class Section(Enum):
    """The sixteen sections of a safety data sheet, as keys of its section texts."""

    IDENTIFICATION = "section_1"
    HAZARDS = "section_2"
    COMPOSITION = "section_3"
    FIRST_AID = "section_4"
    FIRE_FIGHTING = "section_5"
    ACCIDENTAL_RELEASE = "section_6"
    HANDLING_STORAGE = "section_7"
    EXPOSURE_PPE = "section_8"
    PHYSICAL_CHEMICAL = "section_9"
    STABILITY_REACTIVITY = "section_10"
    TOXICOLOGY = "section_11"
    ECOLOGY = "section_12"
    DISPOSAL = "section_13"
    TRANSPORT = "section_14"
    REGULATORY = "section_15"
    OTHER = "section_16"


class LabelKind(StrEnum):
    """What a further label block in 2.2 is (SDB-188 to SDB-190)."""

    # The label of a package of at most 125 ml (CLP Annex I 1.5.2.1).
    SMALL_PACKAGE = "small-package"
    # A block under the Biocidal Products Regulation (EU) No 528/2012.
    BIOCIDES = "biocides"
    # A block under the Detergents Regulation (EC) No 648/2004.
    DETERGENTS = "detergents"


class LabelCondition(StrEnum):
    """Whom a label or a statement applies to, as the sheet prints it
    (SDB-191, SDB-192)."""

    # Supplied to private consumers.
    CONSUMERS = "consumers"
    # Supplied to others than the general public.
    NOT_GENERAL_PUBLIC = "not-general-public"


@dataclass(slots=True)
class HazardStatements:
    """The label of a sheet (section 2.2): codes, their texts as printed, the
    signal word and the pictograms."""

    hazard_codes: list[str] = field(default_factory=list)
    precautionary_codes: list[str] = field(default_factory=list)
    supplemental_codes: list[str] = field(default_factory=list)
    # The signal word the label prints (SDB-176); None where it prints none.
    signal_word: str | None = None
    # The pictograms the label names in its text or shows as pictures
    # (SDB-179), as printed.
    pictograms: list[str] = field(default_factory=list)
    hazard_text: str | None = None
    precautionary_text: str | None = None
    supplemental_text: str | None = None
    # The codes the label does not print and the parser assigned to the
    # sentences it prints (SDB-174); every one of them also stands in its list.
    codes_from_wording: list[str] = field(default_factory=list)
    # Whether the label was looked at as drawn and every red diamond in it was
    # named (SDB-179): only then can a pictogram be said not to be printed.
    drawing_read: bool = False
    # Whether the label states that it has no signal word (SDB-176) or no
    # pictogram (SDB-180): "Signalwort entfällt", "Piktogramme: keine".
    states_no_signal_word: bool = False
    states_no_pictograms: bool = False
    # Whom the label applies to, where it says so, and the sentence that says
    # it (SDB-191).
    condition: LabelCondition | None = None
    condition_text: str | None = None
    # Single statements printed with a condition, by code (SDB-192); they
    # stand in the lists above as well.
    statement_conditions: dict[str, LabelCondition] = field(default_factory=dict)
    # The blocks of 2.2 beside the label, in the sheet's order (SDB-188 to
    # SDB-190); none of their elements stands above.
    further_labels: list[FurtherLabel] = field(default_factory=list)


@dataclass(slots=True)
class FurtherLabel:
    """A block of 2.2 beside the label (SDB-188 to SDB-190): the label of a
    small package, or a block under another regulation, as printed."""

    kind: LabelKind
    # Its heading, or for a sentence naming what a small package leaves out,
    # that sentence (SDB-189).
    heading: str
    # The block's lines as printed, without the heading.
    text: str | None = None
    # The codes such a sentence says a small package leaves out (SDB-189).
    omitted_codes: list[str] = field(default_factory=list)
    # What the block labels with, read like a label (SDB-188); empty for a
    # block under another regulation and for a sentence of SDB-189.
    label: HazardStatements = field(default_factory=HazardStatements)


@dataclass(slots=True)
class ContactInfo:
    """The supplier named in section 1.3, and the emergency telephone of 1.4."""

    supplier_name: str | None = None
    supplier_address: str | None = None
    supplier_phone: str | None = None
    emergency_phone: str | None = None
    supplier_email: str | None = None
    supplier_website: str | None = None
    # The address the sheet names for whoever answers for it (SDB-136): the
    # competent person's, else an information office's. It may equal `supplier_email`,
    # and it may be the address of a firm that wrote the sheet.
    information_email: str | None = None


class StatedClassification(StrEnum):
    """What section 2 of a sheet says about the product's classification (SDB-75)."""

    # It names a hazard class under CLP: "Eye Irrit. 2, H319".
    CLASSIFIED = "classified"
    # It classifies under the directives before CLP (SDB-73).
    OLD_SYSTEM = "classified-old-system"
    # It says the product is not classified, in one of the known wordings.
    NOT_CLASSIFIED = "not-classified"
    # Neither: no classification part, or a wording the parser does not know.
    NOT_STATED = "not-stated"


@dataclass(slots=True)
class SafetyDataSheet:
    """What the parser read from one German safety data sheet."""

    product_identifier: str | None
    issue_date: date | None
    revision_date: date | None
    version: str | None
    language: str
    hazard_statements: HazardStatements = field(default_factory=HazardStatements)
    contact_info: ContactInfo = field(default_factory=ContactInfo)
    section_text: dict[Section, str] = field(default_factory=dict)
    # The countries the sheet is issued for, of DE, AT and CH (SDB-69).
    countries: list[str] = field(default_factory=list)
    # What section 2 says about the classification (SDB-75).
    stated_classification: StatedClassification = StatedClassification.NOT_STATED
    # Whether the sheet says of itself that it is issued voluntarily or that
    # none is prescribed for its product (SDB-142).
    stated_voluntary: bool = False
    # Whether it calls the product an article: beside that sentence (SDB-142)
    # or by saying that as an article it needs no labelling (SDB-154).
    stated_article: bool = False
