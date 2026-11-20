"""Patterns whose old form searched long blank or dash runs in polynomial time.

Each input is the one `regexploit` reported for the old form, made longer.
The new forms read each character one way and finish at once.
"""

from __future__ import annotations

import re
import time

import pytest

from sdb_reader import parser

RUN = 20_000


def _searched_quickly(pattern: re.Pattern[str], text: str) -> bool:
    start = time.perf_counter()
    list(pattern.finditer(text))
    return time.perf_counter() - start < 1.0


@pytest.mark.parametrize(
    ("pattern", "text"),
    [
        (parser.REVISION_DATE_PATTERN, "version" + " " * RUN),
        (parser.VERSION_CREATED_PATTERN, "Version0" + " " * RUN),
        (parser.VERSION_CREATED_PATTERN, "Aktuelle Version0" + " " * RUN),
        (parser._NOT_CLASSIFIED, "–" * RUN + "0"),
        (parser.NO_SIGNAL_WORD_PATTERN, "Signalwort" + " " * RUN),
        (parser._SUBSTANCES_BEFORE_CODE, "Enthält" + " " * RUN),
    ],
    ids=[
        "revision-date",
        "version-created",
        "current-version-created",
        "not-classified-dash",
        "no-signal-word",
        "substances-before-code",
    ],
)
def test_a_long_run_is_searched_at_once(pattern: re.Pattern[str], text: str) -> None:
    assert _searched_quickly(pattern, text)


def test_the_new_forms_still_find_what_they_found() -> None:
    assert parser.VERSION_CREATED_PATTERN.search(
        "Aktuelle Version: 2.0.1, erstellt am: 20.03.2020"
    )
    assert parser.VERSION_CREATED_PATTERN.search("Version 3.1\nErstellt am 30.03.2023")
    assert parser._NOT_CLASSIFIED.search("Einstufung:\n  –  \n")
    assert not parser._NOT_CLASSIFIED.search("Einstufung:\n– –\n")
    assert parser.NO_SIGNAL_WORD_PATTERN.search("Signalwort (CLP) : -")
    assert parser.NO_SIGNAL_WORD_PATTERN.search("Signalwort\nkeine\n")
    found = parser._SUBSTANCES_BEFORE_CODE.search("Enthält: Musterol.   \n  EUH208 Kann …")
    assert found is not None
    assert found.group(1) == "Enthält: Musterol."
