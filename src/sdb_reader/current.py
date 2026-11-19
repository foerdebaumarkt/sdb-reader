"""Which of several sheets of one product is the current one (BIB-6 to BIB-9).

Pure data in, a position out: nothing here reads a file or knows where the
dates and versions came from. Which sheets belong together is the caller's
knowledge.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum


@dataclass(frozen=True, slots=True)
class SheetState:
    """What a sheet says about its own state: all the choice looks at."""

    revision_date: date | None = None
    issue_date: date | None = None
    # As printed, such as "2.01"; read as numbers between dots.
    version: str | None = None
    # The countries the sheet is issued for; empty where it names none.
    countries: Sequence[str] = ()


class ChoiceReason(Enum):
    """Why a state is the current one."""

    # First in the order of BIB-7, and not issued for other countries only.
    NEWEST = "newest"
    # A sheet for the wanted country, in place of a newer one for another
    # country that is not ahead of it in version (BIB-8).
    STANDS_IN = "stands-in"
    # Issued for other countries only, and no sheet for the wanted country
    # can take its place: that country's sheet of this state is missing.
    OTHER_COUNTRY = "other-country"


@dataclass(frozen=True, slots=True)
class Choice:
    """The current state among those given to ``current_state``."""

    # Position in the sequence given.
    index: int
    reason: ChoiceReason
    # With STANDS_IN: the position of the newer sheet for another country.
    instead_of: int | None = None


def current_state(
    states: Sequence[SheetState],
    *,
    country: str | None = "DE",
    today: date | None = None,
) -> Choice:
    """Choose the current one of *states*, the sheets of one product.

    The newest revision date leads; among sheets of one date the one for
    *country* comes first, then the higher version, then the newer issue date,
    then the later one given (BIB-7). Where the sheet so chosen is issued for
    other countries only, the first sheet for *country* takes its place if
    both carry a readable version and its own is not lower (BIB-8). With
    *country* None, countries play no part (BIB-9).

    *today* is the day the caller takes as the present. With it, a revision
    or issue date after that day counts as missing (BIB-19): a sheet that
    prints an impossible date is not the newest because of it, and ranks as
    a sheet without that date does. Without *today* every date counts as
    printed.

    Raises ValueError when *states* is empty.

    >>> from datetime import date
    >>> choice = current_state(
    ...     [
    ...         SheetState(date(2022, 7, 20), version="2", countries=("DE",)),
    ...         SheetState(date(2023, 7, 10), version="2", countries=("CH",)),
    ...     ]
    ... )
    >>> choice.index, choice.reason.value, choice.instead_of
    (0, 'stands-in', 1)
    """
    if not states:
        raise ValueError("no states to choose from")
    if today is not None:
        states = [
            replace(
                state,
                revision_date=_not_after(state.revision_date, today),
                issue_date=_not_after(state.issue_date, today),
            )
            for state in states
        ]

    def rank(index: int) -> tuple[date, bool, tuple[int, ...], date, int]:
        state = states[index]
        return (
            state.revision_date or date.min,
            country is not None and country in state.countries,
            _version(state),
            state.issue_date or date.min,
            index,
        )

    chosen = max(range(len(states)), key=rank)
    if country is None or not states[chosen].countries:
        return Choice(chosen, ChoiceReason.NEWEST)
    if country in states[chosen].countries:
        return Choice(chosen, ChoiceReason.NEWEST)

    wanted = [i for i in range(len(states)) if country in states[i].countries]
    if wanted:
        candidate = max(wanted, key=rank)
        ahead, own = _version(states[chosen]), _version(states[candidate])
        if ahead and own and own >= ahead:
            return Choice(candidate, ChoiceReason.STANDS_IN, instead_of=chosen)
    return Choice(chosen, ChoiceReason.OTHER_COUNTRY)


def _not_after(day: date | None, today: date) -> date | None:
    """*day*, or None where it lies after *today*."""
    return day if day is None or day <= today else None


def _version(state: SheetState) -> tuple[int, ...]:
    """The version as numbers; empty where there is none that can be read."""
    if not state.version:
        return ()
    try:
        return tuple(int(part) for part in state.version.strip().split("."))
    except ValueError:
        return ()
