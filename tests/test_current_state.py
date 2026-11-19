"""Which of several sheets is the current one (specs/bibliothek.md)."""

from __future__ import annotations

from datetime import date

import pytest

from sdb_reader import Choice, ChoiceReason, SheetState, current_state


def _state(
    revised: str | None,
    *,
    version: str | None = None,
    countries: tuple[str, ...] = (),
    issued: str | None = None,
) -> SheetState:
    return SheetState(
        revision_date=date.fromisoformat(revised) if revised else None,
        issue_date=date.fromisoformat(issued) if issued else None,
        version=version,
        countries=countries,
    )


@pytest.mark.spec("BIB-6")
def test_the_choice_names_a_position_among_plain_data() -> None:
    states = [_state("2021-01-01"), _state("2024-01-01"), _state("2023-01-01")]

    assert current_state(states) == Choice(1, ChoiceReason.NEWEST)


@pytest.mark.spec("BIB-6")
def test_nothing_to_choose_from_is_an_error() -> None:
    with pytest.raises(ValueError, match="no states"):
        current_state([])


@pytest.mark.spec("BIB-7")
def test_the_revision_date_leads_over_the_version() -> None:
    """A supplier that starts counting anew: 6.00 is the older sheet."""
    states = [
        _state("2019-07-26", version="6.00"),
        _state("2025-01-15", version="1.05"),
    ]

    assert current_state(states).index == 1


@pytest.mark.spec("BIB-7")
@pytest.mark.parametrize(
    ("states", "expected"),
    [
        # One date: the sheet for the wanted country first.
        (
            [
                _state("2023-03-28", version="3", countries=("CH",)),
                _state("2023-03-28", version="1", countries=("DE",)),
                _state("2023-03-28", version="2", countries=("AT",)),
            ],
            1,
        ),
        # Then the higher version, read as numbers: 2.10 is above 2.9.
        (
            [_state("2023-03-28", version="2.10"), _state("2023-03-28", version="2.9")],
            0,
        ),
        # Then the newer issue date.
        (
            [
                _state("2023-03-28", issued="2023-04-02"),
                _state("2023-03-28", issued="2023-04-01"),
            ],
            0,
        ),
        # Last the later one given.
        ([_state("2023-03-28"), _state("2023-03-28")], 1),
        # No date is the oldest, no readable version the lowest.
        ([_state("2015-01-01"), _state(None, version="9")], 0),
        ([_state("2023-03-28", version="1"), _state("2023-03-28", version="B")], 0),
    ],
)
def test_what_decides_among_sheets_of_one_date(
    states: list[SheetState], expected: int
) -> None:
    assert current_state(states).index == expected


@pytest.mark.spec("BIB-8")
@pytest.mark.parametrize(
    ("own", "ahead", "stands_in"),
    [
        ("2", "2", True),
        ("3", "2", True),
        ("1", "2", False),
        (None, "2", False),
        ("2", None, False),
        (None, None, False),
    ],
)
def test_a_sheet_for_the_country_stands_in_for_a_newer_foreign_one(
    own: str | None, ahead: str | None, stands_in: bool
) -> None:
    """Each country has its own line of sheets: one version, a year apart.
    A lower or missing version leaves the foreign sheet current."""
    states = [
        _state("2022-07-20", version=own, countries=("DE",)),
        _state("2023-07-10", version=ahead, countries=("CH",)),
    ]

    expected = (
        Choice(0, ChoiceReason.STANDS_IN, instead_of=1)
        if stands_in
        else Choice(1, ChoiceReason.OTHER_COUNTRY)
    )
    assert current_state(states) == expected


@pytest.mark.spec("BIB-8")
def test_the_first_sheet_for_the_country_is_the_one_that_stands_in() -> None:
    states = [
        _state("2021-04-08", version="1", countries=("DE",)),
        _state("2022-07-20", version="2", countries=("AT",)),
        _state("2022-07-20", version="2", countries=("DE",)),
        _state("2023-07-10", version="2", countries=("CH",)),
    ]

    assert current_state(states) == Choice(2, ChoiceReason.STANDS_IN, instead_of=3)


@pytest.mark.spec("BIB-8")
def test_a_sheet_that_names_no_country_counts_for_the_wanted_one() -> None:
    states = [
        _state("2022-07-20", version="2", countries=("DE",)),
        _state("2023-07-10", version="2"),
    ]

    assert current_state(states) == Choice(1, ChoiceReason.NEWEST)


@pytest.mark.spec("BIB-8")
def test_a_foreign_sheet_alone_is_reported_as_such() -> None:
    assert current_state([_state("2023-07-10", countries=("AT", "CH"))]) == Choice(
        0, ChoiceReason.OTHER_COUNTRY
    )


@pytest.mark.spec("BIB-9")
def test_the_wanted_country_is_the_callers() -> None:
    states = [
        _state("2022-07-20", version="2", countries=("DE",)),
        _state("2023-07-10", version="2", countries=("CH",)),
    ]

    assert current_state(states, country="CH") == Choice(1, ChoiceReason.NEWEST)
    assert current_state(states, country="AT") == Choice(1, ChoiceReason.OTHER_COUNTRY)


@pytest.mark.spec("BIB-9")
def test_without_a_wanted_country_countries_play_no_part() -> None:
    states = [
        _state("2023-07-10", version="2", countries=("DE",)),
        _state("2023-07-10", version="3", countries=("CH",)),
    ]

    assert current_state(states, country=None) == Choice(1, ChoiceReason.NEWEST)


@pytest.mark.spec("BIB-19")
def test_a_date_after_the_given_day_does_not_make_a_sheet_the_newest() -> None:
    states = [_state("2024-03-01", version="3"), _state("2028-11-28", version="4")]

    assert current_state(states) == Choice(1, ChoiceReason.NEWEST)
    assert current_state(states, today=date(2026, 11, 18)) == Choice(
        0, ChoiceReason.NEWEST
    )


@pytest.mark.spec("BIB-19")
def test_a_sheet_with_an_impossible_date_ranks_as_one_without_a_date() -> None:
    today = date(2026, 11, 18)
    # No other sheet is dated: the version decides, as among undated sheets.
    undated = [_state(None, version="3"), _state("2028-11-28", version="4")]
    assert current_state(undated, today=today) == Choice(1, ChoiceReason.NEWEST)
    # The issue date is looked at on its own.
    issued = [
        _state("2024-03-01", issued="2027-01-01"),
        _state("2024-03-01", issued="2020-01-01"),
    ]
    assert current_state(issued, today=today) == Choice(1, ChoiceReason.NEWEST)


@pytest.mark.spec("BIB-19")
def test_the_day_itself_is_not_the_future() -> None:
    states = [_state("2024-03-01"), _state("2026-11-18")]

    assert current_state(states, today=date(2026, 11, 18)).index == 1
