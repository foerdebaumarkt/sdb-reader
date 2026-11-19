"""A word or a name that a line's end breaks in two (SDB-32, SDB-54)."""

from __future__ import annotations

import re

# A hyphen at a line's end with the word going on below. Not before "und" or
# "oder": there the hyphen stands for the shared part of a word ("Haut-" /
# "und Augenschutz"), and the line break is a space.
_BROKEN_AT_HYPHEN = re.compile(r"([^\W_]|[)\]/])-\n(?!(?:und|oder)\b)([^\W_]|[(\[])")
# A name broken before the bracket of an indicated hydrogen, which a hyphen
# ties to what follows: "2-Methyl-1,2-benzothiazol-3" / "(2H)-on". Not any
# bracket: "(R)-p-Mentha-1,8-dien" begins a name of its own.
_BROKEN_BEFORE_BRACKET = re.compile(r"(\d)\n(\(\d+H\)-[^\W_])")


def _in_a_word(letter: str) -> bool:
    """Whether *letter* is a lower-case letter of a word, not a Greek locant."""
    return letter.islower() and not "Ͱ" <= letter <= "Ͽ"


def join_broken_words(text: str) -> str:
    """*text* with the words its line ends break joined back.

    The hyphen goes only between two lower-case letters: "Reakti-" / "onen"
    is "Reaktionen". Beside a digit, a capital, a bracket, a slash or a Greek
    letter it is the name's own, and so is a break before the bracket of an
    indicated hydrogen: "5-Chlor-2-methyl-2H-" / "isothiazol-3-on",
    "tert-butyl-" / "4-hydroxyphenyl", "…-5-" / "(1,1-dimethylethyl)",
    "propionyl-ω-" / "hydroxypoly…", "Augenschädigung/-" / "reizung". A line
    break that breaks nothing stays.
    """

    def joined(match: re.Match[str]) -> str:
        before, after = match.groups()
        if _in_a_word(before) and _in_a_word(after):
            return before + after
        return f"{before}-{after}"

    return _BROKEN_BEFORE_BRACKET.sub(r"\1\2", _BROKEN_AT_HYPHEN.sub(joined, text))
