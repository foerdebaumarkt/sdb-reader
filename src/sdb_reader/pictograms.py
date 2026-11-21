"""CLP-based GHS pictogram and signal word derivation from H-codes.

Based on CLP Regulation (EC) No 1272/2008 (Annex I).

Precedence rules (CLP Art. 26):
- GHS06 (skull) suppresses GHS07 (exclamation mark) for acute toxicity
- GHS05 (corrosion) suppresses GHS07 for skin/eye irritation
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# H-code → GHS pictogram(s)
# ---------------------------------------------------------------------------

H_TO_PICTOGRAM: dict[str, set[str]] = {
    # Physical hazards (H200 series)
    "H200": {"GHS01"},
    "H201": {"GHS01"},
    "H202": {"GHS01"},
    "H203": {"GHS01"},
    "H204": {"GHS01"},
    "H205": {"GHS01"},
    "H206": {"GHS01", "GHS02"},
    "H207": {"GHS01", "GHS02"},
    "H208": {"GHS02"},
    "H220": {"GHS02"},
    "H221": {"GHS02"},
    "H222": {"GHS02"},
    "H223": {"GHS02"},
    "H224": {"GHS02"},
    "H225": {"GHS02"},
    "H226": {"GHS02"},
    "H228": {"GHS02"},
    "H229": set(),
    # Anhang I, Tabelle 2.2.3: chemically unstable and pyrophoric gases are
    # flammable gases of category 1A and carry its flame.
    "H230": {"GHS02"},
    "H231": {"GHS02"},
    "H232": {"GHS02"},
    "H240": {"GHS01"},
    "H241": {"GHS01", "GHS02"},
    "H242": {"GHS02"},
    "H250": {"GHS02"},
    "H251": {"GHS02"},
    "H252": {"GHS02"},
    "H260": {"GHS02"},
    "H261": {"GHS02"},
    "H270": {"GHS03"},
    "H271": {"GHS03"},
    "H272": {"GHS03"},
    "H280": {"GHS04"},
    "H281": {"GHS04"},
    "H290": {"GHS05"},
    # Health hazards (H300 series)
    "H300": {"GHS06"},
    "H301": {"GHS06"},
    "H302": {"GHS07"},
    "H304": {"GHS08"},
    "H310": {"GHS06"},
    "H311": {"GHS06"},
    "H312": {"GHS07"},
    "H314": {"GHS05"},
    "H315": {"GHS07"},
    "H317": {"GHS07"},
    "H318": {"GHS05"},
    "H319": {"GHS07"},
    "H330": {"GHS06"},
    "H331": {"GHS06"},
    "H332": {"GHS07"},
    "H334": {"GHS08"},
    "H335": {"GHS07"},
    "H336": {"GHS07"},
    "H340": {"GHS08"},
    "H341": {"GHS08"},
    "H350": {"GHS08"},
    "H351": {"GHS08"},
    "H360": {"GHS08"},
    "H361": {"GHS08"},
    "H362": set(),
    "H370": {"GHS08"},
    "H371": {"GHS08"},
    "H372": {"GHS08"},
    "H373": {"GHS08"},
    # Environmental hazards (H400 series)
    "H400": {"GHS09"},
    "H410": {"GHS09"},
    "H411": {"GHS09"},
    "H412": set(),
    "H413": set(),
    "H420": {"GHS07"},
}

# Combined H-codes as printed in many SDS documents
COMBINED_H_CODES: dict[str, list[str]] = {
    "H300+H310": ["H300", "H310"],
    "H300+H330": ["H300", "H330"],
    "H310+H330": ["H310", "H330"],
    "H300+H310+H330": ["H300", "H310", "H330"],
    "H301+H311": ["H301", "H311"],
    "H301+H331": ["H301", "H331"],
    "H311+H331": ["H311", "H331"],
    "H301+H311+H331": ["H301", "H311", "H331"],
    "H302+H312": ["H302", "H312"],
    "H302+H332": ["H302", "H332"],
    "H312+H332": ["H312", "H332"],
    "H302+H312+H332": ["H302", "H312", "H332"],
}

# CLP Art. 26 precedence: if key pictogram is present, suppress value pictograms
# CLP Art. 26 precedence. Only rule (b) is unconditional; (c) and (d) depend on
# *why* GHS07 applies, so they cannot be expressed as a plain pictogram-to-
# pictogram table. Suppressing GHS07 whenever GHS05 is present drops the
# exclamation mark from, say, H302 + H318 -- acute oral toxicity, which Art. 26
# does not suppress at all.
GHS07_IRRITATION_CODES: frozenset[str] = frozenset({"H315", "H319"})
GHS07_SKIN_SENSITISATION_CODES: frozenset[str] = frozenset({"H317"})
GHS08_RESPIRATORY_SENSITISATION_CODES: frozenset[str] = frozenset({"H334"})

# ---------------------------------------------------------------------------
# H-code → signal word
# ---------------------------------------------------------------------------

_GEFAHR_CODES: frozenset[str] = frozenset(
    {
        # Anhang I, Tabelle 2.6.2: Flam. Liq. 2 carries "Gefahr". This said
        # "Achtung" until the tables were checked against the regulation.
        "H225",
        # Anhang I, Tabelle 2.11.1: Self-heat. 1 carries "Gefahr".
        "H251",
        "H200",
        "H201",
        "H202",
        "H203",
        "H205",
        "H206",
        "H207",
        "H220",
        "H222",
        "H224",
        "H240",
        "H241",
        "H250",
        "H260",
        "H270",
        "H271",
        "H300",
        "H301",
        "H310",
        "H311",
        "H314",
        "H318",
        "H330",
        "H331",
        "H334",
        "H340",
        "H350",
        "H360",
        "H370",
        "H372",
        "H304",
        # Anhang I, Tabelle 2.2.3: chemically unstable gases A and B, and
        # pyrophoric gases, all within Flam. Gas 1A.
        "H230",
        "H231",
        "H232",
        # The hazard classes added in 2023 number their hazard statements as
        # EUH and carry a signal word, but no pictogram. Category 1 of the
        # endocrine disruptors (Tabellen 3.11.3 and 4.2.3), PBT and vPvB
        # (4.3.1), PMT and vPvM (4.4.1).
        "EUH380",
        "EUH430",
        "EUH440",
        "EUH441",
        "EUH450",
        "EUH451",
    }
)

_ACHTUNG_CODES: frozenset[str] = frozenset(
    {
        # H410 is Aquatic Chronic 1 and carries "Achtung"; H411, H412 and
        # H413 are categories 2 to 4 and carry none. Anhang I, the table
        # headed LANGFRISTIG (CHRONISCH) GEWÄSSERGEFÄHRDEND. H411 sat here
        # until the verifier learned to read that table -- it is headed
        # differently from the rest and was being skipped.
        "H410",
        # Endocrine disruptors of category 2 (Tabellen 3.11.3 and 4.2.3).
        "EUH381",
        "EUH431",
        # Anhang I, Tabelle 2.1.2: explosives of division 1.4 carry "Achtung",
        # the only division that does. This said "Gefahr" with the others.
        "H204",
        # Anhang I, Tabelle 2.5.2: gases under pressure carry "Achtung" in all
        # four groups. Both said "Gefahr" until the verifier read the table: its
        # row label breaks across a line and was not found.
        "H280",
        "H281",
        # Anhang I, Tabelle 2.16.1: Met. Corr. 1 carries "Achtung". Corrosion
        # towards metals, not towards skin -- this said "Gefahr".
        "H290",
        "H208",
        "H221",
        "H223",
        "H226",
        "H228",
        # Anhang I, Tabelle 2.3.1: an aerosol of category 3 carries H229 alone
        # and "Achtung". Beside H222 (category 1) the product's word is
        # "Gefahr" through H222, beside H223 (category 2) "Achtung": the
        # stronger word wins, so one entry holds for all three categories.
        "H229",
        "H242",
        "H252",
        "H261",
        "H272",
        "H302",
        "H312",
        "H315",
        "H317",
        "H319",
        "H332",
        "H335",
        "H336",
        "H341",
        "H351",
        "H361",
        "H371",
        "H373",
        "H400",
        "H420",
    }
)

# Six statements carry different signal words depending on the category they
# were assigned, which a table keyed on the statement alone cannot express:
#
#   H207  Gefahr in Kategorie 2, Achtung in Kategorie 3
#         (Anhang I, Tabelle 2.17.2 -- desensitised explosives)
#   H221  Gefahr in Kategorie 1B, Achtung in Kategorie 2
#         (Anhang I, Tabelle 2.2.3 -- flammable gases)
#   H228  Gefahr in Kategorie 1, Achtung in Kategorie 2
#         (Anhang I, Tabelle 2.7.2 -- flammable solids)
#   H242  Gefahr in Typen C & D, Achtung in Typen E & F
#         (Anhang I, Tabelle 2.8.1 and 2.15.1 -- self-reactive substances and
#         organic peroxides, two hazard classes sharing the statement)
#   H261  Gefahr in Kategorie 2, Achtung in Kategorie 3
#         (Anhang I, Tabelle 2.12.2 -- substances emitting flammable gases
#         in contact with water)
#   H272  Gefahr in Kategorie 2, Achtung in Kategorie 3
#         (Anhang I, Tabelle 2.13.2 and 2.14.2 -- oxidising liquids and solids)
#
# Each is entered with one of the two answers. H229 looked like a fifth and is
# none: its table gives it two words too, but category 1 prints H222 beside it
# and the word comes from there, so "Achtung" for H229 is right in every
# category. tools/clp/verify_tables.py compares column by column for that
# reason: what counts is the word of the statements a category prints together.
#
# It costs little: a sheet that carries one of these nearly always prints its
# signal word, which is then read rather than derived. Resolving it properly
# needs the classification code -- "Flam. Sol. 1", "Org. Perox. CD" -- from
# section 2.1, which the parser does not read.
H_TO_SIGNAL_WORD: dict[str, str] = {c: "Gefahr" for c in _GEFAHR_CODES}
H_TO_SIGNAL_WORD.update({c: "Achtung" for c in _ACHTUNG_CODES})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _resolve(code: str) -> list[str]:
    """Expand combined codes (e.g. 'H300+H310') to individual codes."""
    upper = code.strip().upper()
    # The letters of an effect behind H360 and H361 (SDB-155) change neither
    # pictogram nor signal word: "H360FD" counts as H360.
    upper = re.sub(r"^(H36[01])[A-Z]{1,2}$", r"\1", upper)
    return COMBINED_H_CODES.get(upper, [upper])


def pictograms_for(h_codes: set[str], *, apply_precedence: bool = True) -> set[str]:
    """Derive GHS pictogram codes from a set of H-codes.

    *h_codes* are H-statement codes, combined ones included
    (``{"H225", "H302", "H300+H310"}``); a code the table does not know adds
    nothing. With *apply_precedence*, the default, a pictogram that Article 26
    of the CLP Regulation lets another one replace is left out.

    >>> sorted(pictograms_for({"H225", "H302"}))
    ['GHS02', 'GHS07']
    >>> sorted(pictograms_for({"H300", "H302"}))
    ['GHS06']
    """
    resolved: set[str] = set()
    for raw in h_codes:
        resolved.update(_resolve(raw))

    pictograms: set[str] = set()
    for code in resolved:
        pictograms.update(H_TO_PICTOGRAM.get(code, set()))

    if apply_precedence and pictograms:
        pictograms = suppress_pictograms(pictograms, resolved)

    return pictograms


def suppress_pictograms(pictograms: set[str], h_codes: set[str]) -> set[str]:
    """Apply the CLP Art. 26 precedence rules to *pictograms*.

    *h_codes* must be the already-resolved H-codes behind them, because two of
    the three rules turn on which hazard triggered GHS07:

    (b) GHS06 present -> GHS07 is dropped outright.
    (c) GHS05 present -> GHS07 is dropped only where it stands for skin or eye
        irritation. Acute toxicity (H302, H312, H332) and the narcotic and
        respiratory-irritation statements (H335, H336) keep it.
    (d) GHS08 present *for respiratory sensitisation* (H334) -> GHS07 is dropped
        where it stands for skin sensitisation or for irritation.
    """

    result = set(pictograms)
    if "GHS07" not in result:
        return result

    resolved: set[str] = set()
    for raw in h_codes:
        resolved.update(_resolve(raw))
    ghs07_triggers = {
        code for code in resolved if "GHS07" in H_TO_PICTOGRAM.get(code, set())
    }

    if "GHS06" in result:
        result.discard("GHS07")
        return result

    if "GHS05" in result and ghs07_triggers <= GHS07_IRRITATION_CODES:
        result.discard("GHS07")
        return result

    if (
        "GHS08" in result
        and resolved & GHS08_RESPIRATORY_SENSITISATION_CODES
        and ghs07_triggers <= (GHS07_IRRITATION_CODES | GHS07_SKIN_SENSITISATION_CODES)
    ):
        result.discard("GHS07")

    return result


def get_signal_word(h_codes: set[str]) -> str | None:
    """Derive the signal word from a set of H-codes.

    The EUH codes of the hazard classes added in 2023 count like H-codes:
    the regulation gives them a signal word (SDB-177).

    'Gefahr' takes precedence over 'Achtung' per CLP Art. 19(4).

    Args:
        h_codes: H-statement codes, e.g. ``{"H225", "H302"}``.

    Returns:
        ``"Gefahr"``, ``"Achtung"``, or ``None`` (not classified / no match).
    """
    has_gefahr = False
    has_achtung = False
    for raw in h_codes:
        for code in _resolve(raw):
            sw = H_TO_SIGNAL_WORD.get(code)
            if sw == "Gefahr":
                has_gefahr = True
            elif sw == "Achtung":
                has_achtung = True
    if has_gefahr:
        return "Gefahr"
    if has_achtung:
        return "Achtung"
    return None
