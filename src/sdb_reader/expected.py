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
from .schema import HazardStatements, LabelKind


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


def clp_expected(
    label: HazardStatements, *, small_package: bool = False
) -> ClpExpected:
    """What the CLP Regulation expects of *label*, from its codes (BIB-25).

    The signal word follows from the H and EUH codes, never from the
    pictograms; the pictograms from the H codes. Where the regulation lets
    the package decide and the sheet does not show the package, nothing is
    claimed (SDB-183): GHS04 is never expected, because Article 33 CLP lets
    the transport label of a gas cylinder stand in for it; GHS05 is not
    expected where H290 is its only reason (no H314, no H318), because Annex
    I 1.3.6 CLP makes it optional on a package for consumers. A label that
    prints either is right as well; beside a printed GHS05, GHS07 for
    irritation gives way as Article 26 says. A label without codes expects
    neither.

    Where the label may be that of a package of at most 125 ml -- the sheet
    prints no small package's label beside it (SDB-194), or *small_package*
    says it is one -- H290 calls for no signal word, which Annex I 1.5.2.1.3
    lets such a package leave out. An aerosol's own elements stay: Directive
    75/324/EEC, to which 1.5.2.1.1 refers, requires them on every aerosol
    dispenser (SDB-193). A signal word the full codes call for does not
    differ.

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
    >>> clp_expected(HazardStatements(hazard_codes=["H290", "H319"])).pictograms
    ['GHS07']
    >>> clp_expected(HazardStatements(hazard_codes=["H290"])).signal_word is None
    True
    """
    hazard_codes = with_effects_joined(set(label.hazard_codes))
    codes = hazard_codes | set(label.supplemental_codes)
    full_word = get_signal_word(codes) if codes else None
    counted = set(hazard_codes)
    if small_package or not any(
        further.kind is LabelKind.SMALL_PACKAGE for further in label.further_labels
    ):
        counted -= {"H290"}
    called = counted | set(label.supplemental_codes)
    signal_word = get_signal_word(called) if called else None
    printed = set(label.pictograms)
    expected = _expected_pictograms(counted if small_package else hazard_codes)
    # A GHS05 the label prints for H290 alone applies all the same: GHS07 for
    # irritation then gives way to it (Article 26).
    called_for = suppress_pictograms(expected | (printed & {"GHS05"}), hazard_codes)
    allowed = (
        pictograms_for(hazard_codes, apply_precedence=False) if hazard_codes else set()
    )
    return ClpExpected(
        signal_word=signal_word,
        pictograms=sorted(expected),
        signal_word_missing=signal_word is not None and label.signal_word is None,
        signal_word_differs=label.signal_word is not None
        and label.signal_word not in {signal_word, full_word},
        pictograms_missing=sorted(called_for - printed),
        pictograms_not_expected=sorted(printed - allowed),
        pictograms_left_out=sorted(
            (printed & allowed) - suppress_pictograms(printed, hazard_codes)
        ),
    )


def _expected_pictograms(hazard_codes: set[str]) -> set[str]:
    """The pictograms *hazard_codes* call for, with Article 26; never GHS04
    (Article 33 CLP), and without GHS05 where H290 is its only reason
    (Annex I 1.3.6 CLP; BIB-25, SDB-183)."""
    if not hazard_codes:
        return set()
    without_h290 = hazard_codes - {"H290"}
    if "H290" in hazard_codes and "GHS05" not in pictograms_for(
        without_h290, apply_precedence=False
    ):
        expected = pictograms_for(without_h290) if without_h290 else set()
    else:
        expected = pictograms_for(hazard_codes)
    return expected - {"GHS04"}
