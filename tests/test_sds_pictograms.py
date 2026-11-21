"""Unit tests for CLP-based pictogram and signal word derivation."""

from __future__ import annotations

import json
from importlib import resources

import pytest

from sdb_reader.pictograms import (
    H_TO_SIGNAL_WORD,
    get_signal_word,
    pictograms_for,
    suppress_pictograms,
)

# ---------------------------------------------------------------------------
# pictograms_for
# ---------------------------------------------------------------------------


def test_single_code_no_precedence_reduction() -> None:
    assert pictograms_for({"H225"}) == {"GHS02"}


def test_skull_suppresses_exclamation_mark() -> None:
    # H300 → GHS06, H302 → GHS07; GHS06 suppresses GHS07
    assert pictograms_for({"H300", "H302"}) == {"GHS06"}


def test_corrosion_suppresses_exclamation_mark() -> None:
    # H314 → GHS05, H315 → GHS07; GHS05 suppresses GHS07
    assert pictograms_for({"H314", "H315"}) == {"GHS05"}


def test_combined_code_expanded() -> None:
    # "H300+H310" → H300 (GHS06) + H310 (GHS06) → {GHS06}
    assert pictograms_for({"H300+H310"}) == {"GHS06"}


def test_unknown_code_returns_empty_set() -> None:
    assert pictograms_for({"HXXX"}) == set()


def test_unknown_code_mixed_with_known() -> None:
    assert pictograms_for({"HXXX", "H225"}) == {"GHS02"}


def test_apply_precedence_false_keeps_suppressed() -> None:
    # Without precedence enforcement GHS07 must remain alongside GHS06
    result = pictograms_for({"H300", "H302"}, apply_precedence=False)
    assert result == {"GHS06", "GHS07"}


def test_environmental_code() -> None:
    assert pictograms_for({"H400"}) == {"GHS09"}


def test_code_with_empty_pictogram_set() -> None:
    # H412 has no pictogram; should return empty set, not raise
    assert pictograms_for({"H412"}) == set()


def test_multiple_codes_merge_pictograms() -> None:
    # H225 → GHS02, H400 → GHS09 — no precedence interaction
    assert pictograms_for({"H225", "H400"}) == {"GHS02", "GHS09"}


def test_empty_input() -> None:
    assert pictograms_for(set()) == set()


# ---------------------------------------------------------------------------
# get_signal_word
# ---------------------------------------------------------------------------


def test_achtung_code() -> None:
    assert get_signal_word({"H226"}) == "Achtung"


def test_gefahr_code() -> None:
    assert get_signal_word({"H300"}) == "Gefahr"


def test_gefahr_wins_over_achtung() -> None:
    # Mix: H300 (Gefahr) + H302 (Achtung) → "Gefahr" wins
    assert get_signal_word({"H300", "H302"}) == "Gefahr"


def test_no_signal_word_for_environmental_only() -> None:
    # H412 has no signal word
    assert get_signal_word({"H412"}) is None


def test_empty_input_returns_none() -> None:
    assert get_signal_word(set()) is None


def test_combined_code_signal_word() -> None:
    # H300+H310 → both Gefahr → "Gefahr"
    assert get_signal_word({"H300+H310"}) == "Gefahr"


def test_unknown_code_returns_none() -> None:
    assert get_signal_word({"HXXX"}) is None


@pytest.mark.spec("BIB-25")
def test_an_aerosol_s_h229_gives_achtung_unless_h222_stands_beside_it() -> None:
    # Anhang I, Tabelle 2.3.1: category 3 prints H229 alone, category 2 H223
    # beside it, category 1 H222.
    assert get_signal_word({"H229"}) == "Achtung"
    assert get_signal_word({"H223", "H229"}) == "Achtung"
    assert get_signal_word({"H222", "H229"}) == "Gefahr"


@pytest.mark.spec("BIB-25")
@pytest.mark.parametrize("code", ["H204", "H280", "H281"])
def test_division_1_4_and_gases_under_pressure_give_achtung(code: str) -> None:
    # Anhang I, Tabellen 2.1.2 and 2.5.2.
    assert get_signal_word({code}) == "Achtung"


@pytest.mark.spec("BIB-25")
def test_every_h_statement_of_the_regulation_has_its_signal_word_or_none() -> None:
    # The four the regulation gives no signal word: effects on or via
    # lactation, and the aquatic categories chronic 2 to 4.
    without = {"H362", "H411", "H412", "H413"}
    catalogue = json.loads(
        (resources.files("sdb_reader") / "clp_statements_de.json").read_text(
            encoding="utf-8"
        )
    )["statements"]
    codes = {code for code in catalogue if code.startswith("H") and "+" not in code}

    assert codes - set(H_TO_SIGNAL_WORD) == without
    assert not without & set(H_TO_SIGNAL_WORD)


# ---------------------------------------------------------------------------
# CLP Art. 26 precedence is conditional, not a flat pictogram table
# ---------------------------------------------------------------------------


def test_corrosion_keeps_exclamation_mark_for_acute_toxicity() -> None:
    # H318 -> GHS05, H302 -> GHS07 for acute oral toxicity. Art. 26(1)(c)
    # suppresses GHS07 only where it stands for skin or eye irritation, so the
    # exclamation mark stays.
    assert pictograms_for({"H302", "H318"}) == {"GHS05", "GHS07"}


def test_corrosion_keeps_exclamation_mark_for_narcotic_effects() -> None:
    # H336 (drowsiness) is not an irritation statement.
    assert pictograms_for({"H314", "H336"}) == {"GHS05", "GHS07"}


def test_corrosion_drops_exclamation_mark_when_only_irritation() -> None:
    assert pictograms_for({"H318", "H315", "H319"}) == {"GHS05"}


def test_skull_suppresses_exclamation_mark_unconditionally() -> None:
    # Art. 26(1)(b) has no exception: even acute-toxicity GHS07 goes.
    assert pictograms_for({"H300", "H302"}) == {"GHS06"}


def test_respiratory_sensitisation_suppresses_skin_sensitisation() -> None:
    # H334 -> GHS08 for respiratory sensitisation; H317 -> GHS07 for skin
    # sensitisation, which Art. 26(1)(d) suppresses.
    assert pictograms_for({"H334", "H317"}) == {"GHS08"}


def test_respiratory_sensitisation_keeps_unrelated_exclamation_mark() -> None:
    # H302 is acute toxicity and outside the reach of Art. 26(1)(d).
    assert pictograms_for({"H334", "H317", "H302"}) == {"GHS07", "GHS08"}


def test_health_hazard_without_respiratory_sensitisation_keeps_ghs07() -> None:
    # H351 -> GHS08, but not for respiratory sensitisation, so no suppression.
    assert pictograms_for({"H351", "H317"}) == {"GHS07", "GHS08"}


def test_suppress_pictograms_leaves_sets_without_ghs07_alone() -> None:
    assert suppress_pictograms({"GHS05", "GHS09"}, {"H318", "H410"}) == {
        "GHS05",
        "GHS09",
    }


# ---------------------------------------------------------------------------
# Signal words checked against Annex I, not against recollection
# ---------------------------------------------------------------------------


def test_flammable_liquid_category_2_is_danger() -> None:
    """Anhang I, Tabelle 2.6.2. Category 1 and 2 are Gefahr, only 3 is Achtung."""
    assert get_signal_word({"H224"}) == "Gefahr"
    assert get_signal_word({"H225"}) == "Gefahr"
    assert get_signal_word({"H226"}) == "Achtung"


def test_self_heating_category_1_is_danger() -> None:
    """Anhang I, Tabelle 2.11.1."""
    assert get_signal_word({"H251"}) == "Gefahr"
    assert get_signal_word({"H252"}) == "Achtung"


def test_corrosive_to_metals_is_warning() -> None:
    """Anhang I, Tabelle 2.16.1 -- corrosion towards metals, not towards skin."""
    assert get_signal_word({"H290"}) == "Achtung"
    assert get_signal_word({"H314"}) == "Gefahr"


def test_danger_still_wins_over_warning() -> None:
    """The corrections must not disturb the Art. 26 precedence."""
    assert get_signal_word({"H225", "H290"}) == "Gefahr"


def test_chronic_aquatic_categories_two_to_four_have_no_signal_word() -> None:
    """Anhang I, the LANGFRISTIG (CHRONISCH) GEWÄSSERGEFÄHRDEND table.

    Only category 1 carries one. H411 sat in the Achtung set until the
    verifier learned to read that table, which is headed differently from the
    others and was being skipped.
    """
    assert get_signal_word({"H410"}) == "Achtung"
    assert get_signal_word({"H411"}) is None
    assert get_signal_word({"H412"}) is None
    assert get_signal_word({"H413"}) is None


def test_table_carries_no_statements_the_eu_did_not_adopt() -> None:
    """H303, H305, H313, H333, H401 and H402 are UN GHS, not CLP.

    They appear on labels outside Europe and in no sheet in the corpus.
    Carrying them was a sign the table came from a GHS list rather than from
    Annex I.
    """
    from sdb_reader.pictograms import H_TO_PICTOGRAM

    for code in ("H303", "H305", "H313", "H333", "H401", "H402"):
        assert code not in H_TO_SIGNAL_WORD, code
        assert code not in H_TO_PICTOGRAM, code


def test_category_dependent_codes_are_recorded_as_such() -> None:
    """The six statements a code-keyed table cannot express correctly.

    It guards the note above H_TO_SIGNAL_WORD: each carries one of its two
    signal words, and the answers named there are the ones in force.
    """
    assert get_signal_word({"H207"}) == "Gefahr"
    for code in ("H221", "H228", "H242", "H261", "H272"):
        assert get_signal_word({code}) == "Achtung"


def test_unstable_and_pyrophoric_gases_are_flammable_gases_of_category_1a() -> None:
    """Anhang I, Tabelle 2.2.3: H230, H231 and H232 stand beside H220."""
    for code in ("H230", "H231", "H232"):
        assert get_signal_word({code}) == "Gefahr"
        assert pictograms_for({code}) == {"GHS02"}


def test_the_hazard_classes_of_2023_carry_a_signal_word_and_no_pictogram() -> None:
    """Their hazard statements are numbered EUH (Tabellen 3.11.3, 4.2.3,
    4.3.1 and 4.4.1 of Anhang I)."""
    for code in ("EUH380", "EUH430", "EUH440", "EUH441", "EUH450", "EUH451"):
        assert get_signal_word({code}) == "Gefahr"
    for code in ("EUH381", "EUH431"):
        assert get_signal_word({code}) == "Achtung"
    assert get_signal_word({"EUH208"}) is None
    assert pictograms_for({"EUH380", "EUH440"}) == set()
