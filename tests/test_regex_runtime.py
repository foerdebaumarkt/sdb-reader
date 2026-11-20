"""Patterns whose old form searched long runs in polynomial time.

The blank and dash runs are the inputs `regexploit` reported for the old
forms, made longer. The long words and the chain of capitalised words were
found by feeding every pattern long runs: the old forms tried such a run
once from every character or word in it, quadratic in its length. The new
forms read each run once and finish at once.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

import pytest

from sdb_reader import compliance, parser, statements

RUN = 20_000
# A quadratic search of 20,000 characters can stay under a second on a fast
# machine; this many takes the old forms many seconds anywhere.
LONG = 60_000


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


@pytest.mark.parametrize(
    ("pattern", "text"),
    [
        (parser._EMAIL, "a" * LONG),
        (parser._DISPLAY_TERM, "a" * LONG),
        (parser._ARTICLE_NUMBER_FIRST, "Art.-Nr. " + "1" * LONG),
        (compliance._NAME_TAIL, "," * LONG + "1"),
        (parser.CLASSIFICATION_ENTRY, "Abc " * (LONG // 4)),
        (parser._SIGNAL_OR_PICTOGRAM_WORDS, "-" * LONG),
        (parser._SIGNAL_OR_PICTOGRAM_WORDS, "- " * (LONG // 2)),
    ],
    ids=[
        "email",
        "display-term",
        "article-number-first",
        "name-tail",
        "classification-entry",
        "signal-word-dashes",
        "signal-word-dash-blank",
    ],
)
def test_a_long_word_or_chain_is_searched_at_once(
    pattern: re.Pattern[str], text: str
) -> None:
    assert _searched_quickly(pattern, text)


def _read_quickly(read: Callable[[str], object], text: str) -> bool:
    start = time.perf_counter()
    read(text)
    return time.perf_counter() - start < 1.0


def _section_ends(text: str) -> list[re.Match[str]]:
    return list(parser._label_section_ends(text))


@pytest.mark.parametrize(
    ("read", "text"),
    [
        (parser._NOTHING_TO_LABEL.match, "," * LONG + "x"),
        (parser._NOTHING_TO_LABEL.match, "(" * LONG + "x"),
        (parser._NOTHING_TO_LABEL.match, "-" * LONG + "x" * 50),
        (parser._NOTHING_TO_LABEL.match, "keine" + "," * LONG + "x" * 50),
        (parser._ARTICLE_LABEL_LAST.match, "ä" * LONG),
        (parser._ARTICLE_LABEL_LAST.match, "a" * LONG + " Handelsname"),
        (parser._NOT_CLASSIFIED.search, ": " * (LONG // 2)),
        (parser._NOT_CLASSIFIED.search, ":" * LONG),
        (statements._CODE_FIRST.search, "-" * LONG),
        (_section_ends, "-\n" * (LONG // 2)),
        (parser._ENDS_IN_ABBREVIATION.search, "a." * (LONG // 2) + "ab."),
    ],
    ids=[
        "nothing-to-label-commas",
        "nothing-to-label-brackets",
        "nothing-to-label-dashes",
        "nothing-to-label-none-commas",
        "article-label-last-umlauts",
        "article-label-last-word",
        "not-classified-colon-blank",
        "not-classified-colons",
        "code-first-dashes",
        "label-section-end-dash-lines",
        "ends-in-abbreviation",
    ],
)
def test_a_run_of_marks_or_letters_is_read_once(
    read: Callable[[str], object], text: str
) -> None:
    assert _read_quickly(read, text)


def test_the_new_forms_still_find_what_they_found() -> None:
    assert parser.VERSION_CREATED_PATTERN.search(
        "Aktuelle Version: 2.0.1, erstellt am: 20.03.2020"
    )
    assert parser.VERSION_CREATED_PATTERN.search("Version 3.1\nErstellt am 30.03.2023")
    assert parser._NOT_CLASSIFIED.search("Einstufung:\n  –  \n")
    assert not parser._NOT_CLASSIFIED.search("Einstufung:\n– –\n")
    assert parser.NO_SIGNAL_WORD_PATTERN.search("Signalwort (CLP) : -")
    assert parser.NO_SIGNAL_WORD_PATTERN.search("Signalwort\nkeine\n")
    found = parser._SUBSTANCES_BEFORE_CODE.search(
        "Enthält: Musterol.   \n  EUH208 Kann …"
    )
    assert found is not None
    assert found.group(1) == "Enthält: Musterol."
    found = parser._EMAIL.search("E-Mail: sdb.team@beispiel-firma.de")
    assert found is not None
    assert found.group() == "sdb.team@beispiel-firma.de"
    found = parser._DISPLAY_TERM.search("Inhalt: 1 Mix-Display mit 24 Dosen")
    assert found is not None
    assert found.group() == "Mix-Display"
    assert (
        parser._ARTICLE_NUMBER_FIRST.sub("", "Art.-Nr. 12.345 Musterdünger")
        == "Musterdünger"
    )
    assert compliance._NAME_TAIL.sub("", "Musterlack - 019") == "Musterlack"
    assert parser.CLASSIFICATION_ENTRY.sub(" ", "Skin Corr. 1A, H314").split() == [
        "Skin"
    ]
    assert parser._SIGNAL_OR_PICTOGRAM_WORDS.match("- Signalwort (CLP): Gefahr")
    assert parser._SIGNAL_OR_PICTOGRAM_WORDS.match("• Flamme, Ausrufezeichen")
    assert not parser._SIGNAL_OR_PICTOGRAM_WORDS.match("- Signalwort: siehe oben")
    assert parser._NOTHING_TO_LABEL.match("(EU)")
    assert parser._NOTHING_TO_LABEL.match("- / nicht weiter")
    assert parser._NOTHING_TO_LABEL.match("Prävention: Reaktion:")
    assert not parser._NOTHING_TO_LABEL.match("Schutzhandschuhe tragen und lüften.")
    found = parser._ARTICLE_LABEL_LAST.match("Musterspray 200 ml Art.Nr.")
    assert found is not None
    assert found.group(1) == "Musterspray 200 ml"
    assert parser._NOT_CLASSIFIED.search("Einstufung: : keine")
    assert parser._NOT_CLASSIFIED.search("Gefahrenhinweise: N/A")
    assert statements._CODE_FIRST.match("• h315 verursacht hautreizungen.")
    assert not statements._CODE_FIRST.match("verursacht h315")
    assert [end.start() for end in _section_ends("x\n-\n- -\nSonstige Gefahren\n")] == [
        2
    ]
    assert parser._ENDS_IN_ABBREVIATION.search("Musterwerk B.V.")
    assert not parser._ENDS_IN_ABBREVIATION.search("Musterwerk AB.")
