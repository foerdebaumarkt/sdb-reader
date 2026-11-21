"""What the CLP Regulation expects of a label's signal word and pictograms.

The reading holds only what the label prints (SDB-169). ``clp_expected`` puts
beside it what the label's codes call for and where the two differ, as data:
a caller fills a gap or checks a label with it, and decides itself what a
difference means for its use (BIB-25).
"""

from __future__ import annotations

from dataclasses import dataclass

from .parser import with_effects_joined
from .pictograms import get_signal_word, pictograms_for, suppress_pictograms
from .schema import HazardStatements


@dataclass(frozen=True, slots=True)
class ClpExpected:
    """What the CLP Regulation expects of a label, and where the reading
    differs from it (BIB-25).

    ``signal_word`` is the word Annex I gives the label's H and EUH codes,
    ``pictograms`` the pictograms its H codes call for, with the precedence of
    Article 26. The other fields compare the reading with them, and nothing
    else: whether the label states it has none (``states_no_signal_word``,
    ``states_no_pictograms``) or was looked at as drawn (``drawing_read``)
    stands in the reading for the caller to weigh.
    """

    signal_word: str | None
    pictograms: list[str]
    # The codes call for a signal word, and the reading has none.
    signal_word_missing: bool
    # The reading has a signal word other than the one the codes call for,
    # or one where they call for none.
    signal_word_differs: bool
    # Pictograms the codes call for that the reading does not have.
    pictograms_missing: list[str]
    # Pictograms the reading has that none of the H codes calls for.
    pictograms_not_expected: list[str]
    # Pictograms the reading has that a code calls for and Article 26 leaves
    # out beside another pictogram the reading has.
    pictograms_left_out: list[str]


def clp_expected(label: HazardStatements) -> ClpExpected:
    """What the CLP Regulation expects of *label*, from its codes (BIB-25).

    The signal word follows from the H and EUH codes, never from the
    pictograms; the pictograms from the H codes. A label without codes
    expects neither.

    >>> from sdb_reader import HazardStatements
    >>> expected = clp_expected(HazardStatements(
    ...     hazard_codes=["H302", "H318"], pictograms=["GHS05", "GHS07"]))
    >>> expected.signal_word, expected.pictograms, expected.signal_word_missing
    ('Gefahr', ['GHS05', 'GHS07'], True)
    >>> expected.pictograms_left_out
    []
    >>> clp_expected(HazardStatements(
    ...     hazard_codes=["H315", "H318"], pictograms=["GHS05", "GHS07"])
    ... ).pictograms_left_out
    ['GHS07']
    """
    hazard_codes = with_effects_joined(set(label.hazard_codes))
    codes = hazard_codes | set(label.supplemental_codes)
    signal_word = get_signal_word(codes) if codes else None
    expected = pictograms_for(hazard_codes) if hazard_codes else set()
    allowed = (
        pictograms_for(hazard_codes, apply_precedence=False) if hazard_codes else set()
    )
    printed = set(label.pictograms)
    return ClpExpected(
        signal_word=signal_word,
        pictograms=sorted(expected),
        signal_word_missing=signal_word is not None and label.signal_word is None,
        signal_word_differs=label.signal_word is not None
        and label.signal_word != signal_word,
        pictograms_missing=sorted(expected - printed),
        pictograms_not_expected=sorted(printed - allowed),
        pictograms_left_out=sorted(
            (printed & allowed) - suppress_pictograms(printed, hazard_codes)
        ),
    )
