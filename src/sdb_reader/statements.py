"""The wording the CLP regulation prescribes for a hazard statement.

Suppliers type these sentences themselves, and they do not always type what the
regulation says: "H319 Verursacht schwere Augenreizungen" stands in the
corpus where Annex III has the singular. The wording is not the supplier's to
choose, so the regulation's is what a product shows.

Only statements with one wording are rendered. Three kinds are held back:

* **parameter** -- the sentence has a hole the supplier fills ("Inhalt/Behälter
  … zuführen"), and the filling is in the sheet, not here.
* **alternatives** -- the sentence is a menu ("Schutzhandschuhe/Schutzkleidung/
  Augenschutz/Gesichtsschutz tragen"), and a label carrying only "Augenschutz
  tragen" would gain three requirements it does not have.
* **disputed** -- the regulation states the sentence in two places and they do
  not agree. Annex I and Annex IV Part 1 say which statement a category
  carries and quote it; Annex III and Annex IV Part 2 hold the wording.
  Amendment M19 revised Part 1 alone, so Part 2 still has the 2008 sentence
  for P103 and the M4 one for P210. P338 carries a capital "Vorhandene"
  mid-sentence, H229 differs in the case of one word, and H410 drops a comma
  that its own annex uses when quoting it. Seven statements are affected.
  Which half governs is not ours to decide, and a superseded sentence on a
  product is worse than the supplier's own, so these are left alone.

That leaves 66.3% of the statement lines in the corpus, which is the part
that needs no knowledge of the label beyond the code itself.

The data comes from the regulation, not from a third party: see
tools/clp/extract_statements.py. A published dataset exists and was used to
check this one -- 152 of the shared entries matched, the rest were an extraction
artefact of ours since fixed, except one comma where the regulation we read is
the newer text.
"""

from __future__ import annotations

import itertools
import json
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from .line_breaks import join_broken_words
from .schema import HazardStatements

DATA_PATH = Path(__file__).with_name("clp_statements_de.json")
# The wordings earlier consolidations gave a statement (SDW-50).
EARLIER_PATH = Path(__file__).with_name("clp_earlier_wordings_de.json")

# "H315: Verursacht Hautreizungen." and the combination forms, with whatever
# separator the sheet used between code and sentence.
# What a sheet or a model writes right behind a code and before its separator
# (SDB-126): the letters of an effect ("H360FD", "H361d") or the number of a
# variant ("P501.9"). It belongs to the code's mark, not to the wording.
CODE_SUFFIX = r"(?:[A-Za-z]{1,2}(?![^\W\d_])|\.\d{1,2}(?!\d))"

STATEMENT_LINE = re.compile(
    r"^(\s*)((?:EUH\d{3}[A-Za-z]*|[HP]\d{3})(?:\s*\+\s*[HP]\d{3})*)"
    rf"({CODE_SUFFIX}?\s*[:\-–]?\s*)(.*)$"
)

# "P102, P101, P501:" -- a sheet's column of codes, set apart from the column
# of their wordings (SDB-30). Two or more codes, a combination counting as one.
_CODE_ITEM = r"(?:EUH\d{3}|[HP]\d{3})(?:\s*\+\s*[HP]\d{3})*"
CODE_LIST_LINE = re.compile(
    rf"^(\s*)({_CODE_ITEM}(?:\s*[,;]\s*{_CODE_ITEM})+)\s*[,;:]?(?:\s(.*))?$"
)


@lru_cache(maxsize=1)
def _fixed_statements() -> dict[str, str]:
    """Code to wording, for statements that have exactly one."""
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {
        code: entry["text"]
        for code, entry in raw.get("statements", {}).items()
        if entry.get("kind") == "fixed" and entry.get("text")
    }


def canonical_text(code: str) -> str | None:
    """The regulation's wording for *code*, or None where it prescribes no single one.

    >>> canonical_text("H315")
    'Verursacht Hautreizungen.'
    >>> canonical_text("P280") is None
    True
    """
    code = re.sub(r"\s*\+\s*", "+", code.strip())
    return LETTERED_WORDINGS.get(code) or _fixed_statements().get(code)


# Cache compiled regex patterns for statement normalization
_STATEMENT_REGEX_CACHE: dict[tuple[str, ...], re.Pattern[str] | None] = {}


def normalize_statements(text: str, prefixes: Sequence[str]) -> str:
    """One statement per line, a colon after each code (SDB-17).

    *prefixes* are the kinds of code the text holds ("H", "EUH", "P"). Codes
    joined by a plus or a dash stay on one line, as does a list of codes
    ("P102, P101, P501:"), which render_statements reads as one (SDB-30).

    >>> print(
    ...     normalize_statements(
    ...         "H315 Verursacht Hautreizungen. H319 Verursacht schwere Augenreizung.",
    ...         ("H", "EUH"),
    ...     )
    ... )
    H315: Verursacht Hautreizungen.
    H319: Verursacht schwere Augenreizung.
    """

    if not text:
        return text

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return normalized

    uppercase_prefixes = tuple(prefix.upper() for prefix in prefixes if prefix)

    # Insert missing colons: "P101 Text" → "P101: Text". Idempotent when colon present.
    #
    # The repetition is possessive on purpose. A greedy one can give back the
    # tail it just consumed to satisfy the lookahead, and on a combination that
    # already carries its colon it does exactly that: "P305 + P351 + P338:"
    # backtracks to "P305 + P351", where the next characters are " + P338" and
    # so not a colon, and a colon is inserted there. The three-part statement
    # then reads "P305 + P351: + P338: BEI KONTAKT ..." and the split below
    # turns it into two, the first holding nothing but a plus sign. Refusing to
    # give the tail back makes the match fail where it should, and the code is
    # left as the document wrote it.
    #
    # A dash where the colon should be is taken *over*, not added to. Models
    # differ on this and the prompt does not settle it: gpt-5-mini writes
    # "H220: Extrem entzündbares Gas", qwen3.8 writes "H220 - Extrem
    # entzündbares Gas". Inserting without absorbing turns the second into
    # "H220: - Extrem entzündbares Gas". Statements with one fixed wording
    # survive that, because the rendering overwrites the whole text -- but the
    # 61 held back as parameter, alternatives or disputed keep the stray dash,
    # on every sheet that carries one.
    #
    # A dash with no space on either side is a separator too, when a word
    # follows it: "H304-Kann bei Verschlucken …", as a sheet prints it and the
    # model copies it. Not taken for one, the line was never split, and the
    # rendering then gave the whole line the wording of its first code -- the
    # H412 behind it was gone. A code after the dash is the
    # sheet's way of joining two statements ("H335-H336 Kann …") and is left.
    if uppercase_prefixes:
        _code_pats = "|".join(
            f"{re.escape(p)}\\d{{2,3}}{CODE_SUFFIX}?" for p in uppercase_prefixes
        )
        _codes = rf"((?:{_code_pats})(?:\s*\+\s*(?:{_code_pats}))*+)"
        # And a dash right after the code with the space behind it, "P102-
        # Darf nicht …", as two suppliers print it (SDB-47): kept as
        # the separator, the line read "P102- Darf …" in the output, where the
        # model's answers read "P102: Darf …".
        _colon_inserter = re.compile(
            rf"{_codes}(?!\s*:)[^\S\n]+[-–—][^\S\n]*|"
            rf"{_codes}(?!\s*:)[^\S\n]+|"
            rf"{_codes}[-–—](?=[^\W\d_])(?!{_code_pats})|"
            rf"{_codes}[-–—][^\S\n]++(?!{_code_pats})",
            re.IGNORECASE,
        )
        normalized = _colon_inserter.sub(
            lambda m: f"{m.group(1) or m.group(2) or m.group(3) or m.group(4)}: ",
            normalized,
        )

    pattern: re.Pattern[str] | None = None
    if "\n" not in normalized and uppercase_prefixes:
        cached = _STATEMENT_REGEX_CACHE.get(uppercase_prefixes)
        if cached is None:
            code_pattern_parts = [
                f"{re.escape(prefix)}\\d{{2,3}}{CODE_SUFFIX}?"
                for prefix in uppercase_prefixes
            ]
            if code_pattern_parts:
                code_pattern = "|".join(code_pattern_parts)
                # A dash joins codes as a plus does ("H335-H336: Kann die
                # Atemwege reizen. Kann Schläfrigkeit …"): one line, so the
                # first code is not left behind on the line before. A list
                # ("P102, P101, P501:") stays whole too, for the rendering to
                # read as one (SDB-30).
                cached = re.compile(
                    rf"(?P<leading>\s*)(?P<code>(?:{code_pattern})(?:\s*[+\-–,;]\s*(?:{code_pattern}))*\s*:)",
                    re.IGNORECASE,
                )
            else:
                cached = None
            _STATEMENT_REGEX_CACHE[uppercase_prefixes] = cached
        pattern = cached

    if pattern is not None:
        pieces: list[str] = []
        last_index = 0
        for match in pattern.finditer(normalized):
            start, end = match.span()
            leading = match.group("leading") or ""
            code_segment = match.group("code")

            pieces.append(normalized[last_index:start])
            last_index = end

            preceding = pieces[-1] if pieces else ""
            needs_newline = bool(start > 0 and not preceding.endswith("\n"))

            if needs_newline:
                pieces[-1] = pieces[-1].rstrip()
                pieces.append("\n")
            else:
                pieces.append(leading)

            pieces.append(code_segment)

        pieces.append(normalized[last_index:])
        normalized = "".join(pieces)

    lines = [line.strip() for line in normalized.splitlines()]
    compact = [line for line in lines if line]
    if not compact:
        return normalized
    return "\n".join(compact)


def render_statements(text: str) -> tuple[str, int]:
    """Replace each line's wording with the regulation's, where there is one.

    Works line by line and keeps the sheet's order, so a paragraph that mixes
    rendered and untouched statements stays in the sequence the label used.
    Lines the pattern does not recognise are passed through untouched -- this
    corrects wording, it never removes a statement.

    A line that lists codes (SDB-30) becomes one line per code, with the
    regulation's wording where it has one and the code alone where it does not.
    What followed the list is dropped when it holds none of their wordings: on
    one line of paints it was the start of 2.3, "P501: Andere
    Gefahren, die zu keiner Einstufung führen …". When it does hold them, the
    line is the sheet's own statement and stays: One supplier prints "H222, H229:
    Extrem entzündbares Aerosol. Behälter steht unter Druck: …". EUH statements
    keep the sheet's wording (SDB-18); the regulation's is only taken for one
    that stands in a list.

    Returns the text and how many lines were replaced.

    >>> text, replaced = render_statements(
    ...     "H315: Reizt die Haut.\\nP280: Schutzhandschuhe tragen."
    ... )
    >>> print(text)
    H315: Verursacht Hautreizungen.
    P280: Schutzhandschuhe tragen.
    >>> replaced
    1
    """
    if not text:
        return text, 0

    replaced = 0
    lines: list[str] = []
    for line in text.split("\n"):
        listed = CODE_LIST_LINE.match(line)
        if listed:
            indent, codes, after = listed.groups()
            listed_codes = re.split(r"\s*[,;]\s*", codes)
            if after and holds_a_wording_of(after, listed_codes):
                lines.append(line)
                continue
            for code in listed_codes:
                canonical = canonical_text(code)
                if canonical is None:
                    lines.append(f"{indent}{code}")
                else:
                    replaced += 1
                    lines.append(f"{indent}{code}: {canonical}")
            continue
        match = STATEMENT_LINE.match(line)
        if not match:
            lines.append(line)
            continue
        indent, code, separator, wording = match.groups()
        canonical = canonical_text(code)
        if (
            canonical is None
            or code.startswith("EUH")
            or not wording.strip()
            or _holds_another(code, wording)
        ):
            lines.append(line)
            continue
        if canonical != wording.strip():
            replaced += 1
        lines.append(f"{indent}{code}{separator}{canonical}")
    return "\n".join(lines), replaced


def tidy_statements(text: str) -> str:
    """Each statement once, and no code without its wording (SDB-47).

    Runs after render_statements, on the statements from either source.
    A statement the field already holds with the same code and wording goes:
    the parser cuts its texts from the whole of section 2, and a sheet that
    prints the label's statements in 2.1 as well gave each of them twice once
    the regulation's wording made the two copies alike. A code standing alone
    goes too when the field gives the same code a wording -- "H220" beside
    "H220: Extrem entzündbares Gas." -- and otherwise takes the regulation's
    wording where it prescribes exactly one; a code it gives none keeps
    standing alone.

    >>> print(
    ...     tidy_statements(
    ...         "H315: Verursacht Hautreizungen.\\n"
    ...         "H315: Verursacht Hautreizungen.\\n"
    ...         "H319"
    ...     )
    ... )
    H315: Verursacht Hautreizungen.
    H319: Verursacht schwere Augenreizung.
    """
    if not text:
        return text
    parsed: list[tuple[str, str | None, str]] = []
    worded: set[str] = set()
    for line in text.split("\n"):
        match = STATEMENT_LINE.match(line)
        if match is None:
            parsed.append((line, None, ""))
            continue
        code = re.sub(r"\s*\+\s*", "+", match.group(2))
        wording = match.group(4).strip()
        if wording:
            worded.add(code)
        parsed.append((line, code, wording))
    lines: list[str] = []
    seen: set[str] = set()
    for line, statement, wording in parsed:
        if statement is not None and not wording:
            if statement in worded:
                continue
            canonical = canonical_text(statement)
            # "BEI VERSCHLUCKEN:" only opens a combination (P301+P310); on its
            # own it tells the reader nothing to do.
            if canonical is not None and not canonical.endswith(":"):
                line = f"{line.rstrip(' :-–')}: {canonical}"
        key = _comparable(line)
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _catalogue() -> dict[str, str]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {
        code: entry["text"]
        for code, entry in raw.get("statements", {}).items()
        if entry.get("text")
    }


@lru_cache(maxsize=1)
def statement_codes() -> frozenset[str]:
    """Every single H, P and EUH code of the regulation, a combination's parts
    counted on their own: what a number has to be to be read as a code
    printed with a space (SDB-164)."""
    return frozenset(part for code in _catalogue() for part in code.split("+"))


def first_word_of(code: str) -> str | None:
    """The first word of *code*'s wording in the regulation, lower case, or
    None where the regulation has none (SDB-164)."""
    wording = _catalogue().get(code)
    if not wording:
        return None
    match = re.search(r"[^\W\d_]+", wording)
    return match.group(0).lower() if match else None


# How many words of a wording identify it when it is not printed whole: a
# menu's first choice, the part before a hole.
_OPENING_WORDS = 3

# How many of a wording's last words mark where it ends (SDB-51): enough not
# to be met by chance, few enough to survive an older wording of the start.
_CLOSING_WORDS = 3
_OPTIONAL = re.compile(r"\[[^\]]*\]")


class WordingBounds(NamedTuple):
    """How a statement's regulation wording begins and ends."""

    opening: re.Pattern[str]
    # None where the wording ends in a hole: "Kann die Organe schädigen … bei
    # längerer oder wiederholter Exposition <Expositionsweg …>." ends with
    # whatever the supplier puts there.
    closing: re.Pattern[str] | None
    # The alternatives of a wording that begins with a choice, else none.
    choices: tuple[str, ...] = ()


def _opening(wording: str) -> str:
    """The first words of *wording*, as a pattern: up to its first hole or choice.

    A wording that begins with a choice begins with any of its alternatives:
    "Inhalt/Behälter … zuführen." is printed "Inhalt und Behälter in …" and
    "Behälter der Wertstoffsammlung …", P280's menu of protective gear
    "Augenschutz oder Gesichtsschutz tragen.".
    """
    tokens = _HOLE.split(_OPTIONAL.sub("", wording))[0].split()
    if not tokens:
        return ""
    if "/" in tokens[0]:
        return "(?:" + "|".join(map(re.escape, _WORD.findall(tokens[0]))) + ")"
    words: list[str] = []
    for token in tokens[:_OPENING_WORDS]:
        if "/" in token:
            break
        words.extend(_WORD.findall(token))
    return r"[\W_]+".join(map(re.escape, words))


def _closing(wording: str) -> str:
    """The last words of *wording* behind its last hole or choice, as a pattern.

    A part the regulation prints in brackets at the very end ("[oder
    duschen]") may follow them.
    """
    optional = _OPTIONAL.findall(wording)
    words = _HOLE.split(_OPTIONAL.sub("", wording))[-1].split()
    choice = max((i for i, word in enumerate(words) if "/" in word), default=-1)
    closing = _WORD.findall(" ".join(words[choice + 1 :]))[-_CLOSING_WORDS:]
    if not closing:
        return ""
    body = r"[\W_]+".join(map(re.escape, closing))
    after = (
        optional[-1] if optional and wording.rstrip(" .").endswith(optional[-1]) else ""
    )
    extra = _WORD.findall(after)
    if extra:
        body += r"(?:[\W_]+" + r"[\W_]+".join(map(re.escape, extra)) + ")?"
    return body


@lru_cache(maxsize=512)
def wording_bounds(code: str) -> WordingBounds | None:
    """How a statement with *code* begins and where it ends (SDB-51).

    The end is the regulation's last words after its last hole or choice:
    "allergische Reaktionen hervorrufen" for EUH208, "zuführen" for P501,
    "tragen" for P280, "Hilfe hinzuziehen" for "Ärztlichen Rat
    einholen/ärztliche Hilfe hinzuziehen". A combination the regulation does
    not list begins like its first part and ends like its last ("P304+P312":
    "BEI EINATMEN: Bei Unwohlsein … anrufen."). None for a code the regulation
    does not word.
    """
    joined = base_code(re.sub(r"\s*\+\s*", "+", code.strip()))
    if joined in _EFFECT_OPENINGS:
        return WordingBounds(_EFFECT_OPENINGS[joined], None)
    catalogue = _catalogue()
    first = last = catalogue.get(joined)
    if first is None and "+" in joined:
        parts = joined.split("+")
        first, last = catalogue.get(parts[0]), catalogue.get(parts[-1])
    if first is None or last is None:
        return None
    opening, closing = _opening(first), _closing(last)
    if not opening:
        return None
    head = _HOLE.split(_OPTIONAL.sub("", first))[0].split()[0]
    return WordingBounds(
        re.compile(rf"(?<![^\W_]){opening}(?![^\W_])", re.IGNORECASE),
        re.compile(rf"\b{closing}\b[.!?)\]\"“”]*", re.IGNORECASE) if closing else None,
        tuple(_WORD.findall(head)) if "/" in head else (),
    )


# A sentence's end, and what may stand behind it on its line.
_SENTENCE_TAIL = r"[^.!?\n]*[.!?][)\]\"“”]*"


@lru_cache(maxsize=512)
def open_end(code: str) -> re.Pattern[str] | None:
    """Where a statement ends whose regulation wording ends in a hole (SDB-108).

    "Kann die Organe schädigen <…> bei längerer oder wiederholter Exposition
    <Expositionsweg …>." names no last words: the supplier's follow. The
    statement is whole at the end of the sentence that holds the last words
    the regulation does fix. None for a code whose wording has an end of its
    own, or none at all.
    """
    bounds = wording_bounds(code)
    if bounds is None or bounds.closing is not None:
        return None
    wording = _catalogue().get(re.sub(r"\s*\+\s*", "+", code.strip()).split("+")[-1])
    fixed = [
        words
        for part in _HOLE.split(_OPTIONAL.sub("", wording or ""))
        if (words := _WORD.findall(part))
    ]
    if not fixed or base_code(code.strip()) in _EFFECT_OPENINGS:
        # H360 and H361 are printed with one effect or both: any sentence.
        return re.compile(_SENTENCE_TAIL)
    tail = r"[\W_]+".join(map(re.escape, fixed[-1][-_CLOSING_WORDS:]))
    return re.compile(rf"\b{tail}\b{_SENTENCE_TAIL}", re.IGNORECASE)


# H360 and H361 begin with either effect (see _EFFECT_WORDINGS): "Kann das
# Kind im Mutterleib schädigen." is H360 as much as "Kann die Fruchtbarkeit
# beeinträchtigen …". They end in a hole, as in the catalogue.
_EFFECT_OPENINGS = {
    "H360": re.compile(
        r"(?<![^\W_])Kann[\W_]+(?:die[\W_]+Fruchtbarkeit|das[\W_]+Kind)(?![^\W_])",
        re.IGNORECASE,
    ),
    "H361": re.compile(
        r"(?<![^\W_])Kann[\W_]+vermutlich[\W_]+(?:die[\W_]+Fruchtbarkeit|das[\W_]+Kind)"
        r"(?![^\W_])",
        re.IGNORECASE,
    ),
}
# Where a sentence can begin inside running text: at its start, or behind the
# end of the sentence or the label before it ("Prävention: Freisetzung …").
_SENTENCE_START = re.compile(r"(?:^|(?<=[.:!?] ))")
# A label left at the end of what a statement was cut from: "… Gebrauch.
# Reaktion:" before the next statement.
_LABEL_AT_END = re.compile(r"(?<=[.!?])\s+[A-ZÄÖÜ][\wäöüß /-]{0,40}:\s*$")


# A sentence's end, and a word that carries the sentence on behind a wording.
_SENTENCE_STOP = re.compile(r"[.!?](?:\s|$)")
_GOES_ON = re.compile(r"\s+[a-zäöüß]")


def _runs_on(text: str, start: int, closing: re.Pattern[str] | None) -> bool:
    """Whether the sentence at *start* carries a longer wording than this one.

    "Sehr giftig für Wasserorganismen" is all of H400 and the beginning of
    H410, "… mit langfristiger Wirkung.": where the sentence goes on behind
    the wording's last words, it is another code's.
    """
    if closing is None:
        return False
    whole = closing.search(text, start)
    if whole is None or _SENTENCE_STOP.search(text, start, whole.start()):
        return False
    return _GOES_ON.match(text, whole.end()) is not None


def _is_its_choice(text: str, start: int, bounds: WordingBounds) -> bool:
    """Whether the sentence at *start* is the wording, where one word may begin it.

    A wording that begins with a choice begins with any one of its words, and
    so does much else: "Behälter kann bei Erwärmung bersten." is not P501.
    Its sentence also holds the wording's end ("Behälter … der
    Wertstoffsammlung zuführen!") or a second word of the choice ("Inhalt und
    Behälter … entsorgen.").
    """
    if not bounds.choices:
        return True
    stop = _SENTENCE_STOP.search(text, start)
    sentence = text[start : stop.end() if stop else len(text)]
    if bounds.closing and bounds.closing.search(sentence):
        return True
    named = [
        choice
        for choice in bounds.choices
        if re.search(
            rf"(?<![^\W_]){re.escape(choice)}(?![^\W_])", sentence, re.IGNORECASE
        )
    ]
    return len(named) > 1


def wordings_apart(codes: Sequence[str], passages: Sequence[str]) -> list[str] | None:
    """The sheet's sentence for each of *codes*, printed apart from them (SDB-52).

    *passages* is the text that carries no code, each passage one run of lines
    a sentence can run through. The codes are looked for in their order, each
    by how the regulation's wording begins, at the start of a sentence; a
    statement runs to the next one's start or to its passage's end, and no
    further than the last words of its wording where it holds them. None unless
    every code is found: half a row of codes with the sheet's sentences and
    half without would say that the others have none.
    """
    texts = [re.sub(r"\s+", " ", passage).strip() for passage in passages]
    index = offset = 0
    found: list[tuple[str, int, int, re.Pattern[str] | None]] = []
    for code in codes:
        bounds = wording_bounds(code)
        if bounds is None:
            return None
        while index < len(texts):
            start = next(
                (
                    match.start()
                    for match in bounds.opening.finditer(texts[index], offset)
                    if _SENTENCE_START.match(texts[index], match.start())
                    and not _runs_on(texts[index], match.start(), bounds.closing)
                    and _is_its_choice(texts[index], match.start(), bounds)
                ),
                None,
            )
            if start is not None:
                break
            index, offset = index + 1, 0
        else:
            return None
        found.append((code, index, start, bounds.closing))
        # The next one begins behind this one's wording: "Behälter dicht
        # verschlossen halten." closes P403+P233 and does not open P501.
        whole = bounds.closing.search(texts[index], start) if bounds.closing else None
        offset = whole.end() if whole else start + 1
    statements: list[str] = []
    for position, (code, index, start, closing) in enumerate(found):
        following = found[position + 1] if position + 1 < len(found) else None
        end = following[2] if following and following[1] == index else None
        sentence = texts[index][start:end]
        # The last time the wording ends a sentence: "Schutzhandschuhe tragen.
        # Augenschutz oder Gesichtsschutz tragen." is whole, and "… vor
        # erneutem Tragen waschen." behind it is not P280's.
        ends = [
            match.end()
            for match in (closing.finditer(sentence) if closing else ())
            if match.end() == len(sentence) or sentence[match.end() - 1] in ".!?)]"
        ]
        if ends:
            sentence = sentence[: ends[-1]]
        statements.append(f"{code} {_LABEL_AT_END.sub('', sentence).strip()}")
    return statements


def holds_a_wording_of(text: str, codes: list[str]) -> bool:
    """Whether *text* carries the opening of a wording of any of *codes*.

    Every kind counts here, unlike for reading codes off a label: "P280, P501:
    Schutzhandschuhe tragen. Inhalt/Behälter … zuführen." is the sheet's own
    statement although neither wording is fixed, and so is a list of
    combinations ("P302+P352, P333+P313: BEI BERÜHRUNG MIT DER HAUT: …").
    A combination counts by its own wording and by each part's.
    """
    haystack = _comparable(text)
    catalogue = _catalogue()
    for code in codes:
        joined = re.sub(r"\s*\+\s*", "+", code)
        for candidate in (joined, *joined.split("+")):
            wording = catalogue.get(candidate)
            if not wording:
                continue
            opening = re.split(r"[/<…]", wording, maxsplit=1)[0]
            words = _comparable(opening).split()[:_OPENING_WORDS]
            # Whole words: "Inhalt" is not in "Gefährliche Inhaltsstoffe".
            if words and f" {' '.join(words)} " in f" {haystack} ":
                return True
    return False


def wordings_in_print_order(
    codes: Collection[str], passages: Sequence[str]
) -> list[str] | None:
    """The sheet's sentence for each of *codes* where the label prints no code (SDB-52).

    A label that prints its statements as sentences alone (SDB-6) gives the
    codes no order; they take the one their sentences stand in.
    """
    texts = [re.sub(r"\s+", " ", passage).strip() for passage in passages]
    places: list[tuple[int, int, str]] = []
    for code in codes:
        bounds = wording_bounds(code)
        place = next(
            (
                (index, match.start())
                for index, text in enumerate(texts)
                for match in (bounds.opening.finditer(text) if bounds else ())
                if _SENTENCE_START.match(text, match.start())
            ),
            None,
        )
        if place is None:
            return None
        places.append((*place, code))
    return wordings_apart([code for *_, code in sorted(places)], passages)


# A statement of the same kind as the line's own: H and EUH share a field, P
# has its own.
_SAME_KIND = {
    "H": re.compile(r"(?<![A-Za-z0-9])(?:EUH|H)\d{3}(?!\d)"),
    "P": re.compile(r"(?<![A-Za-z0-9])P\d{3}(?!\d)"),
}


def _holds_another(code: str, wording: str) -> bool:
    """Whether *wording* carries a further statement of the line's own kind.

    Replacing such a line's wording would delete that statement: a sheet that
    joins codes ("H335-H336 Kann …") leaves several on one line. A code of the other kind is
    text that ran in from the next block, which the other field carries, and
    the replacement still drops it.
    """
    return bool(_SAME_KIND["P" if code.startswith("P") else "H"].search(wording))


def _comparable(text: str) -> str:
    """Reduce a sentence to what identifies it, and nothing else.

    Case, punctuation and spacing all vary between sheets printing the same
    statement -- one prints "Giftig für Wasserorganismen mit langfristiger
    Wirkung", the regulation writes it with a comma -- and none of that
    distinguishes one statement from another.
    """
    lowered = text.casefold().replace("ß", "ss")
    return re.sub(r"\s+", " ", re.sub(r"[^\wäöü ]+", " ", lowered)).strip()


@lru_cache(maxsize=1)
def _wordings() -> tuple[tuple[str, str], ...]:
    """Every statement wording that identifies exactly one code.

    Longest first, which is what makes the lookup safe: "Entzündbares Aerosol"
    is a substring of "Extrem entzündbares Aerosol", and the two are mutually
    exclusive categories. Scanning shortest-first reported both on 352 sheets;
    longest-first reports the right one on all of them.

    Parameter and alternatives statements are excluded -- their wording carries
    a hole the supplier fills, so it never appears verbatim. Disputed ones are
    kept: the disagreement is over which wording to *print*, and either form
    still identifies the code.

    EUH statements are left out: they are read from their wording whether or
    not the label prints codes (SDB-28, `euh_statements_by_wording`), and H and
    P only where it prints none (SDB-6).
    """
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []
    for code, entry in raw.get("statements", {}).items():
        if "+" in code or code.startswith("EUH"):
            continue
        if entry.get("kind") not in ("fixed", "disputed"):
            continue
        wording = _comparable(entry.get("text") or "")
        if wording:
            pairs.append((wording, code))
    pairs.extend((_comparable(wording), code) for wording, code in _EFFECT_WORDINGS)
    return tuple(sorted(pairs, key=lambda pair: -len(pair[0])))


# H360 and H361 name the effect where it is known, and CLP gives each effect
# its sentence and a letter behind the code (Annex VI, 1.1.2.1.2): H360D "Kann
# das Kind im Mutterleib schädigen.", H361f "Kann vermutlich die Fruchtbarkeit
# beeinträchtigen.". The catalogue holds the two codes with their holes, which
# no label prints; these are the sentences labels do print. A sentence that
# names one effect is that effect's lettered code (SDB-155); the sentence with
# "oder" names none, and stays the bare code.
_EFFECT_WORDINGS: tuple[tuple[str, str], ...] = (
    (
        "Kann die Fruchtbarkeit beeinträchtigen oder das Kind im Mutterleib schädigen",
        "H360",
    ),
    ("Kann die Fruchtbarkeit beeinträchtigen", "H360F"),
    ("Kann das Kind im Mutterleib schädigen", "H360D"),
    (
        "Kann vermutlich die Fruchtbarkeit beeinträchtigen oder das Kind im "
        "Mutterleib schädigen",
        "H361",
    ),
    ("Kann vermutlich die Fruchtbarkeit beeinträchtigen", "H361f"),
    ("Kann vermutlich das Kind im Mutterleib schädigen", "H361d"),
)

# The codes of Annex VI, 1.1.2.1.2, with their wording there (SDB-155). A
# capital letter is an effect shown (category 1), a small one an effect
# suspected (category 2); H361 has small letters only.
LETTERED_WORDINGS: dict[str, str] = {
    "H360F": "Kann die Fruchtbarkeit beeinträchtigen.",
    "H360D": "Kann das Kind im Mutterleib schädigen.",
    "H361f": "Kann vermutlich die Fruchtbarkeit beeinträchtigen.",
    "H361d": "Kann vermutlich das Kind im Mutterleib schädigen.",
    "H360FD": (
        "Kann die Fruchtbarkeit beeinträchtigen. Kann das Kind im Mutterleib schädigen."
    ),
    "H361fd": (
        "Kann vermutlich die Fruchtbarkeit beeinträchtigen. "
        "Kann vermutlich das Kind im Mutterleib schädigen."
    ),
    "H360Fd": (
        "Kann die Fruchtbarkeit beeinträchtigen. "
        "Kann vermutlich das Kind im Mutterleib schädigen."
    ),
    "H360Df": (
        "Kann das Kind im Mutterleib schädigen. "
        "Kann vermutlich die Fruchtbarkeit beeinträchtigen."
    ),
}

_LETTERED = re.compile(r"^(H36[01])([A-Za-z]{1,2})$")


def lettered_code(code: str) -> str:
    """The code of Annex VI that *code* stands for, letters as the regulation sets them.

    The letters a sheet prints are read as the regulation means them: for H360 a
    capital is an effect shown and a small one an effect suspected, in either
    order; H361 has only suspected effects, so its letters count whatever their
    case. Letters that name no code of the Annex (a small letter alone behind
    H360, a letter that is no effect) leave the bare code (SDB-155).

    >>> lettered_code("H360DF"), lettered_code("H361FD"), lettered_code("H360dF")
    ('H360FD', 'H361fd', 'H360Fd')
    >>> lettered_code("H360d"), lettered_code("H315")
    ('H360', 'H315')
    """
    match = _LETTERED.match(code)
    if match is None:
        return code
    base, letters = match.groups()
    if base == "H361":
        effects = {letter.lower() for letter in letters}
        if not effects <= {"f", "d"} or len(effects) != len(letters):
            return base
        return base + "".join(letter for letter in "fd" if letter in effects)
    chosen = set(letters)
    if len(chosen) != len(letters) or not chosen <= set("FDfd"):
        return base
    for candidate in ("F", "D", "FD", "Fd", "Df"):
        if set(candidate) == chosen:
            return base + candidate
    return base


def base_code(code: str) -> str:
    """*code* without the letters of an effect: "H360FD" is H360."""
    match = _LETTERED.match(code)
    return match.group(1) if match else code


def with_effects_joined(codes: Collection[str]) -> set[str]:
    """*codes* with the effects of H360 and H361 joined into the Annex's code (SDB-155).

    A label that names both effects in two sentences, "Kann die Fruchtbarkeit
    beeinträchtigen. Kann das Kind im Mutterleib schädigen.", carries H360FD,
    not H360F beside H360D. The bare code goes where a lettered one names the
    effect.

    >>> sorted(with_effects_joined({"H360F", "H360D", "H315"}))
    ['H315', 'H360FD']
    >>> sorted(with_effects_joined({"H360F", "H361d"}))
    ['H360Fd']
    >>> sorted(with_effects_joined({"H360", "H360D"}))
    ['H360D']
    """
    shown = {
        base + letter
        for base, letter in (("H360", "F"), ("H360", "D"))
        if base + letter in codes
    }
    suspected = {code for code in ("H361f", "H361d") if code in codes}
    joined = set(codes)
    target = None
    if shown == {"H360F", "H360D"}:
        target = "H360FD"
    elif shown == {"H360F"} and suspected == {"H361d"}:
        target = "H360Fd"
    elif shown == {"H360D"} and suspected == {"H361f"}:
        target = "H360Df"
    elif not shown and suspected == {"H361f", "H361d"}:
        target = "H361fd"
    if target is not None:
        joined -= shown | suspected
        joined.add(target)
    for base in ("H360", "H361"):
        if base in joined and any(base_code(c) == base and c != base for c in joined):
            joined.discard(base)
    return joined


def codes_from_wording(text: str) -> set[str]:
    """The codes whose wording appears in *text*.

    For labels that print the sentences and not the codes, which is how 20
    sheets in the corpus are written: "Gefahrenhinweise : Giftig für
    Wasserorganismen mit langfristiger Wirkung." and nothing else.

    A match consumes what it covers, so a longer statement wins over any
    shorter one inside it. No wording here identifies more than one code.
    """
    if not text:
        return set()
    haystack = _comparable(text)
    found: set[str] = set()
    for wording, code in _wordings():
        if wording in haystack:
            found.add(code)
            haystack = haystack.replace(wording, " ")
    # A condition is half a statement ("BEI EINATMEN:"): among the words of a
    # sentence it says nothing, unless a precautionary statement stands
    # beside it (SDB-122).
    precautionary = {code for code in found if code.startswith("P")}
    if precautionary <= _conditions():
        found -= precautionary
    return found


@lru_cache(maxsize=1)
def _conditions() -> frozenset[str]:
    """The precautionary codes whose wording is only a condition, ending in a colon."""
    return frozenset(
        code
        for code, wording in _fixed_statements().items()
        if code.startswith("P") and "+" not in code and wording.rstrip().endswith(":")
    )


# A hole holds substance names, never the next element of the label: not a line
# that starts with a code or a label heading. Without this "Enthält Xylol" on a
# components line and a bare "Kann allergische Reaktionen hervorrufen." further
# down read as one EUH208 with the signal word and the H statements inside.
_NOT_A_NEW_ELEMENT = (
    r"(?!\n[^\S\n]*(?:EUH\s?\d{3}|[HP]\d{3}|Signalwort|Gefahrenhinweis"
    r"|Sicherheitshinweis|Gefahrenpiktogramm|Piktogramm))"
)
# A hole in a wording: "<Name des sensibilisierenden Stoffes>" or "…".
_HOLE = re.compile(r"<[^>]*>|…")
_WORD = re.compile(r"[^\W_]+")
# What a hole may hold: the substance names, not a page of text. The longest
# in the corpus is one supplier's 520 characters of benzotriazole reaction masses.
_HOLE_LIMIT = 1000


def _wording_pattern(wording: str, *, partial: bool = False) -> re.Pattern[str]:
    """*wording* as a pattern that matches it however a sheet typesets it.

    Between two words anything that is not a word may stand -- a space, a line
    break, a hyphen, a comma the regulation does not have. A hole becomes a gap
    of up to _HOLE_LIMIT characters that does not run past another start of the
    same sentence, so "Enthält A. Kann allergische Reaktionen hervorrufen.
    Enthält B. …" reads as two statements, not one.
    """
    # "Achtung!" opens EUH206, 207, 211 and 212, and sheets leave it out as often
    # as they print it; the sentence after it is what identifies the statement.
    warning = re.match(r"Achtung!\s*", wording)
    if warning:
        wording = wording[warning.end() :]
    parts = _HOLE.split(wording)
    if partial and len(parts) > 1:
        # Only what follows the hole: "Kann allergische Reaktionen hervorrufen."
        parts = [parts[-1]]
    first = _WORD.findall(parts[0])[:1]
    not_first = rf"(?!{re.escape(first[0])})" if first else ""
    gap = rf"(?:{not_first}{_NOT_A_NEW_ELEMENT}[\s\S]){{1,{_HOLE_LIMIT}}}?"
    pieces = [r"[\W_]+".join(map(re.escape, _WORD.findall(part))) for part in parts]
    body = rf"[\W_]+{gap}[\W_]+".join(piece for piece in pieces if piece)
    if warning:
        body = rf"(?:Achtung[\W_]+)?{body}"
    return re.compile(rf"(?<![^\W_]){body}(?![^\W_])\.?", re.IGNORECASE)


@lru_cache(maxsize=2)
def _euh_patterns(
    partial: bool = False,
) -> tuple[tuple[str, re.Pattern[str], bool], ...]:
    """Each EUH statement that a wording identifies, longest wording first,
    and whether its wording has a hole.

    Fixed ones before those with a hole, so EUH204's "Enthält Isocyanate. Kann
    allergische Reaktionen hervorrufen." is read as EUH204 and not as EUH208
    with "Isocyanate" in its hole. Alternatives are left out: EUH018 is a menu,
    and EUH201 and EUH209 hold two statements in one entry.
    """
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    entries = [
        (code, entry)
        for code, entry in raw.get("statements", {}).items()
        if code.startswith("EUH")
        and entry.get("kind") in ("fixed", "disputed", "parameter")
    ]
    entries.sort(
        key=lambda item: (item[1]["kind"] == "parameter", -len(item[1]["text"]))
    )
    return tuple(
        (
            code,
            _wording_pattern(entry["text"], partial=partial),
            entry["kind"] == "parameter",
        )
        for code, entry in entries
    )


# A label saying that a safety data sheet is to be had on request, in the
# wording of CLP or of the Preparations Directive (SDB-76).
SHEET_ON_REQUEST = re.compile(
    r"(?<![^\W_])Sicherheitsdatenblatt[\W_]+auf[\W_]+Anfrage[\W_]+"
    r"(?:für[\W_]+berufsmäßige[\W_]+(?:Verwender|Benutzer|Anwender)[\W_]+)?"
    r"erhältlich(?![^\W_])",
    re.IGNORECASE,
)
# The sentence of the Preparations Directive (SDB-123): "Sicherheitsdatenblatt
# auf Anfrage für berufsmäßige Verwender erhältlich." It is that directive's
# phrase and no EUH210; the parser keeps it in the text as printed.
OLD_REQUEST_SENTENCE = re.compile(
    r"(?<![^\W_])Sicherheitsdatenblatt[\W_]+auf[\W_]+Anfrage[\W_]+für[\W_]+"
    r"berufsmäßige[\W_]+(?:Verwender|Benutzer|Anwender)[\W_]+erhältlich(?![^\W_])\.?",
    re.IGNORECASE,
)


def euh_statements_by_wording(
    text: str,
    *,
    skip: Collection[str] = (),
    partial: bool = False,
    standing: bool = False,
) -> list[tuple[str, str]]:
    """The EUH statements *text* prints by their wording, in the order it prints them.

    Returns (code, the sheet's sentence) pairs, the sentence on one line and
    with what the sheet put into a hole (SDB-28). Codes in *skip* are not
    reported -- the label prints them, and their wording is read with the
    code. A match consumes what it covers, a skipped one included.

    *partial* also takes a statement with a hole by what follows the hole
    alone. That is too loose to label a product with, but enough to notice a
    sheet that means EUH208 and writes it in a form the regulation does not
    ("… Kann allergische Reaktionen hervorrufen. 2-Butanonoxim.").

    *standing* takes a sentence only where it begins its line or follows
    its code (SDB-219): one that runs on from other words on its line is
    part of a description, not a statement printed without its code. A
    sentence with a hole is exempt: what it begins with is the sheet's own.

    >>> euh_statements_by_wording(
    ...     "Kann Augen reizen. Wiederholter Kontakt\\nkann zu spröder oder "
    ...     "rissiger Haut führen.",
    ...     standing=True,
    ... )
    []
    >>> euh_statements_by_wording(
    ...     "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.",
    ...     standing=True,
    ... )
    [('EUH066', 'Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.')]
    """
    if not text:
        return []
    found: list[tuple[int, str, str]] = []
    haystack = text
    for code, pattern, holed in _euh_patterns(partial):
        # A code in *skip* still consumes its wording: printed as "EUH204
        # Enthält Isocyanate. Kann allergische …", it is not EUH208 as well.
        for match in [] if code in skip else pattern.finditer(haystack):
            # Where the sentence itself begins: a match may take the space
            # before it.
            begins = match.start() + len(match.group(0)) - len(match.group(0).lstrip())
            if (
                standing
                and not holed
                and not _STANDS.fullmatch(
                    text[text.rfind("\n", 0, begins) + 1 : begins]
                )
            ):
                continue
            # A name broken at a line's end is joined as the reader joins
            # it (SDB-32), also across the empty line the reader leaves where
            # a column ends (SDB-45).
            lines = join_broken_words(re.sub(r"\n\s*\n", "\n", match.group(0)))
            sentence = re.sub(r"\s+", " ", lines).strip()
            found.append((match.start(), code, sentence))
        haystack = pattern.sub(lambda m: " " * len(m.group(0)), haystack)
    return [(code, sentence) for _, code, sentence in sorted(found)]


# What may stand before a statement on its line: a mark of a list, its code.
_STANDS = re.compile(r"[\s·•∙*\-–]*(?:EUH\s?\d{3}[A-Za-z]?\s*[:.\-–]?\s*)?")


@dataclass(frozen=True, slots=True)
class StatementWording:
    """One statement of a label: what the sheet prints and what the regulation says."""

    code: str
    # As the parser read it; None for a code in a list (SDB-30) or without text.
    sheet: str | None
    # None where the regulation gives the code no single wording.
    regulation: str | None
    # PRINTED where the label prints the code, FROM_WORDING where it prints
    # only the sentence and the parser assigned the code (SDB-174).
    code_source: str = "printed"


PRINTED = "printed"
FROM_WORDING = "from_wording"


def _assigned(code: str, from_wording: Collection[str]) -> bool:
    """Whether every code of *code* ("P305+P351+P338" counts as its parts)
    is one the parser assigned to a sentence (SDB-174)."""
    return all(part in from_wording for part in code.split("+"))


def as_printed(text: str | None, codes_from_wording: Collection[str]) -> str | None:
    r"""*text* with the codes the label does not print taken off its lines (SDB-174).

    A line whose leading code -- every part of a combination -- the parser
    assigned to the sheet's sentence keeps the sentence and loses the code;
    every other line stays as it is.

    >>> as_printed(
    ...     "P280: Schutzhandschuhe tragen.\nP501 Inhalt/Behälter … entsorgen",
    ...     ["P501"],
    ... )
    'P280: Schutzhandschuhe tragen.\nInhalt/Behälter … entsorgen'
    >>> as_printed("EUH208: Enthält Musterol. Kann allergische Reaktionen "
    ...            "hervorrufen.", ["EUH208"])
    'Enthält Musterol. Kann allergische Reaktionen hervorrufen.'
    >>> as_printed("P305+P351+P338: BEI KONTAKT MIT DEN AUGEN: …", ["P338"])
    'P305+P351+P338: BEI KONTAKT MIT DEN AUGEN: …'
    """
    if not text or not codes_from_wording:
        return text
    lines = []
    for line in text.split("\n"):
        statement = STATEMENT_LINE.match(line)
        if statement is not None and statement.group(4).strip():
            code = re.sub(r"\s*\+\s*", "+", statement.group(2))
            if _assigned(code.upper(), codes_from_wording):
                line = statement.group(1) + statement.group(4).strip()
        lines.append(line)
    return "\n".join(lines)


# Codes standing first in a wording: the rest of a row of codes joined by
# dashes, commas or plus signs ("H314-H335", "P102-P303+P361+P353-P310").
_LEADING_CODES = re.compile(
    r"^((?:EUH\d{3}|[HP]\d{3})(?:\s*\+\s*(?:EUH\d{3}|[HP]\d{3}))*)\s*[-–,;:]?\s*"
)


def label_statements(hazards: HazardStatements) -> list[StatementWording]:
    """Every H-, P- and EUH-statement of the label, each with both wordings (SDW-5).

    Read from the statement texts, one statement per line (SDB-17), and only for
    codes the label carries. A code the sheet prints with a wording is listed
    with each wording it prints; a code it prints only bare, in a list (SDB-30)
    or in a row of codes, or not at all, once with none.

    >>> label = HazardStatements(
    ...     hazard_codes=["H315"],
    ...     precautionary_codes=["P280"],
    ...     hazard_text="H315: Reizt die Haut.",
    ...     precautionary_text="P280: Schutzhandschuhe tragen.",
    ... )
    >>> for statement in label_statements(label):
    ...     print(statement.code, "|", statement.sheet, "|", statement.regulation)
    H315 | Reizt die Haut. | Verursacht Hautreizungen.
    P280 | Schutzhandschuhe tragen. | None
    """
    on_label = {
        *hazards.hazard_codes,
        *hazards.precautionary_codes,
        *hazards.supplemental_codes,
    }
    wordings: dict[str, list[str]] = {}

    def add(code: str, wording: str | None) -> None:
        code = re.sub(r"\s*\+\s*", "+", code.strip())
        if not set(code.split("+")) <= on_label:
            return
        known = wordings.setdefault(code, [])
        if wording and wording not in known:
            known.append(wording)

    for text, prefixes in (
        (hazards.hazard_text, ("H", "EUH")),
        (hazards.precautionary_text, ("P",)),
        (hazards.supplemental_text, ("EUH",)),
    ):
        if not text:
            continue
        for line in normalize_statements(text, prefixes).split("\n"):
            listed = CODE_LIST_LINE.match(line)
            if listed:
                for code in re.split(r"\s*[,;]\s*", listed.group(2)):
                    add(code, None)
                continue
            statement = STATEMENT_LINE.match(line)
            if statement is None:
                continue
            codes = [statement.group(2)]
            wording = statement.group(4).strip()
            while leading := _LEADING_CODES.match(wording):
                codes.append(leading.group(1))
                wording = wording[leading.end() :].strip()
            # A row of codes carries no wording of its own; codes joined in
            # front of one wording ("H335-H336 Kann …") share it.
            for code in codes:
                add(code, wording or None)

    for code in sorted(on_label - {part for c in wordings for part in c.split("+")}):
        add(code, None)
    assigned = set(hazards.codes_from_wording)
    return [
        StatementWording(
            code,
            wording,
            canonical_text(code),
            FROM_WORDING if assigned and _assigned(code, assigned) else PRINTED,
        )
        for code, printed in wordings.items()
        for wording in (printed or (None,))
    ]


# A negation does not tell where a wording begins: a sheet that leaves it out
# still begins the statement with the rest of its words (SDW-50).
_NEGATIONS = frozenset({"nicht", "kein", "keine"})


def _same_opening(printed: str, official: str) -> bool:
    """Whether *printed* begins with *official*'s first three words, negations
    not counted, and articles and auxiliaries not counted either where the
    two differ in those (SDW-50)."""
    for ignored in (_NEGATIONS, _NEGATIONS | _ARTICLES):
        first = [w for w in _comparable(printed).split() if w not in ignored]
        second = [w for w in _comparable(official).split() if w not in ignored]
        if first[:_OPENING_WORDS] == second[:_OPENING_WORDS]:
            return True
    return False


def deviates_from_regulation(code: str, wording: str) -> bool:
    """Whether the sheet's *wording* departs from the regulation's for *code* (SDW-50).

    Only a wording that begins with the regulation's first three words is
    compared, negations not counted and, where they make the difference,
    articles and auxiliaries neither (``_same_opening``): one that begins
    otherwise is mostly text the parser found under the code. It
    deviates where it begins with none of the code's official forms
    (``_official_forms``), strict or loose; text after a complete form is
    mostly a heading the parser read on into, and does not count.

    >>> deviates_from_regulation("P243", "Maßnahmen gegen elektrostatische Aufladungen treffen.")
    False
    >>> deviates_from_regulation("P243", "Maßnahmen gegen elektrostatische Entladung treffen.")
    True
    """
    canonical = canonical_text(code)
    if canonical is None or not wording.strip() or _holds_another(code, wording):
        return False
    if not _same_opening(wording, canonical):
        return False
    if holds_official_form(code, wording):
        return False
    text = re.sub(r"^[\W_]+", "", _normalised(re.sub(r"\s+", " ", wording)))
    return not any(form.match(text) for form in _official_forms(code, loose=True))


def holds_official_form(code: str, wording: str) -> bool:
    """Whether *wording* begins with one of *code*'s official forms (SDW-50).

    False for a code the regulation gives no single wording.

    >>> holds_official_form("H315", "Verursacht Hautreizungen. Berechnungsmethode.")
    True
    >>> holds_official_form("H315", "Verursacht | Methode Hautreizungen.")
    False
    """
    code = re.sub(r"\s*\+\s*", "+", code.strip())
    if canonical_text(code) is None:
        return False
    text = re.sub(r"^[\W_]+", "", _normalised(re.sub(r"\s+", " ", wording)))
    return any(form.match(text) for form in _official_forms(code))


def interleaves_wording(code: str, wording: str) -> bool:
    """Whether *wording* holds the regulation's words for *code* in their
    order, with other text between them, and no official form (SDB-185).

    That is a cell of the table beside the statement read into it: "Kann
    allergische Hautreaktionen | Berechnungsmethode. (Skin Sens. 1)
    verursachen." for H317.

    >>> interleaves_wording(
    ...     "H317", "Kann allergische Hautreaktionen | Berechnung. (Skin Sens. 1) verursachen."
    ... )
    True
    >>> interleaves_wording("H317", "Kann allergische Reaktionen verursachen.")
    False
    """
    canonical = canonical_text(re.sub(r"\s*\+\s*", "+", code.strip()))
    if canonical is None or holds_official_form(code, wording):
        return False
    printed = iter(_comparable(wording).split())
    return all(word in printed for word in _comparable(canonical).split())


# Precautionary statements printed as wording only, in the forms Annex IV of
# the CLP Regulation itself allows (SDB-163). Its introduction says what a
# statement's signs mean: a slash separates texts to choose from, three dots
# mark details the supplier gives, square brackets a part that applies only
# under conditions. From each statement's wording those signs give a pattern,
# compiled once per statement, never per combination of its choices.
_JOINER = r"\s*(?:/|,|\bund\b|\boder\b)\s*"
# What "…" holds: a short stretch of the same sentence.
_FILL = r"[^.!?:\n]{1,60}?"
# Between two words of the regulation's wording: spaces and punctuation, a
# sentence's end included, as the wording itself may hold one ("… fernhalten.
# Nicht rauchen.").
_GAP = r"[^\w]{0,4}"
# The articles and auxiliaries a sheet may leave out or add (SDW-50). A
# negation is no such word: "nicht", "kein" and "keine" have to stand as the
# regulation has them.
_ARTICLES = frozenset({"der", "die", "das", "ist", "sind"})
_LOOSE_GAP = rf"{_GAP}(?:(?:{'|'.join(sorted(_ARTICLES))})(?!\w){_GAP})*"
# At most this many choices in one slash group are spelt out as their ordered
# selections; P260 and P261 have six, the most in the Annex.
_MOST_CHOICES = 6


def _normalised(text: str) -> str:
    """Case, ß and the degree sign the way both sides are compared (SDB-163)."""
    return _normalised_at(text)[0]


def _normalised_at(text: str) -> tuple[str, list[int]]:
    """*text* normalised, and for each of its characters the place it came from.

    >>> _normalised_at("Über  50 °C")
    ('über 50°c', [0, 1, 2, 3, 4, 6, 7, 9, 10])
    """
    characters: list[str] = []
    places: list[int] = []
    for place, character in enumerate(text):
        if character.isspace() and character != "\n":
            if characters and characters[-1] in " °":
                continue
            character = " "
        elif character == "°" and characters and characters[-1] == " ":
            characters.pop()
            places.pop()
        for folded in character.casefold().replace("ß", "ss"):
            characters.append(folded)
            places.append(place)
    return "".join(characters), places


def _piece(text: str) -> str:
    """A word or a choice, "…" in it a fill: "…°c" is any value in degrees."""
    parts = [re.escape(part) for part in text.split("…")]
    return _FILL.join(parts) if len(parts) > 1 else parts[0]


def _with_zu(token: str) -> str:
    """*token* as a pattern; an infinitive also with "zu" inside it (SDW-50):
    "einhalten" admits "einzuhalten"."""
    if "…" in token or not token.endswith("en") or len(token) < 6:
        return _piece(token)
    forms = [token[:at] + "zu" + token[at:] for at in range(2, len(token) - 3)]
    return "(?:" + "|".join(map(re.escape, [token, *forms])) + ")"


def _choices(token: str) -> str:
    """A slash group as its ordered, non-empty selections (SDB-163).

    "staub/rauch/gas" admits "staub", "staub/gas", "rauch und gas" and the
    other selections in the regulation's order, joined by a slash, a comma,
    "und" or "oder". A choice that is only "…" is the supplier's own detail;
    a selection of it alone does not identify the statement.
    """
    options = [option for option in token.split("/") if option]
    named = [index for index, option in enumerate(options) if option != "…"]
    if len(options) > _MOST_CHOICES:
        alternative = "|".join(_piece(option) for option in options)
        return rf"(?:{alternative})(?:{_JOINER}(?:{alternative}))*"
    selections = []
    for mask in range(1, 2 ** len(options)):
        chosen = [index for index in range(len(options)) if mask >> index & 1]
        if named and not set(chosen) & set(named):
            continue
        selections.append(_JOINER.join(_piece(options[index]) for index in chosen))
    selections.sort(key=len, reverse=True)
    return "(?:" + "|".join(selections) + ")"


def _variant_body(
    wording: str, *, choice_for_brackets: bool = False, loose: bool = False
) -> tuple[str, int]:
    """The forms Annex IV allows for *wording* as a pattern, and how many of its
    words are fixed.

    With *choice_for_brackets*, a part in square brackets that begins with
    "oder" may also stand without it, behind a slash: "Haut mit Wasser
    abwaschen/duschen" for "abwaschen [oder duschen]" (SDW-50).

    With *loose*, an article or auxiliary may be left out or added between
    any two words, and an infinitive may take "zu" inside it ("einzuhalten"
    for "einhalten", SDW-50).
    """
    text = _normalised(wording)
    text = re.sub(r"(\d+|…) o ([cf])\b", r"\1°\2", text)
    text = re.sub(r"\s*/\s*", "/", text)
    parts: list[str] = []
    fixed_words = 0
    for optional, segment in re.findall(r"(\[)?([^\[\]]+)\]?", text):
        tokens = [token.strip(".,:;()") for token in segment.split()]
        pieces = []
        for token in filter(None, tokens):
            if "/" in token:
                pieces.append(_choices(token))
                fixed_words += any(
                    option not in ("", "…") for option in token.split("/")
                )
            elif token == "…":  # noqa: S105 -- a word, not a secret
                pieces.append(_FILL)
            elif loose and token in _ARTICLES:
                continue
            else:
                pieces.append(_with_zu(token) if loose else _piece(token))
                fixed_words += "…" not in token
        if not pieces:
            continue
        joined = (_LOOSE_GAP if loose else _GAP).join(pieces)
        gap = _LOOSE_GAP if loose else _GAP
        if optional and choice_for_brackets and len(pieces) > 1 and tokens[0] == "oder":
            joined = f"(?:oder{gap})?" + gap.join(pieces[1:])
        parts.append(f"(?:{gap}{joined})?" if optional else gap + joined)
    if loose:
        return _LOOSE_GAP + "".join(parts).removeprefix(_LOOSE_GAP), fixed_words
    return "".join(parts).removeprefix(_GAP), fixed_words


def _variant_pattern(wording: str) -> re.Pattern[str] | None:
    """The forms Annex IV allows for *wording*, or None where they say too little."""
    body, fixed_words = _variant_body(wording)
    if fixed_words < 2:
        return None
    return re.compile(rf"(?<!\w){body}(?!\w)")


@lru_cache(maxsize=1)
def _variant_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """A pattern for every statement of its own (SDB-163).

    H and EUH statements too: their wording can hold a precautionary one's
    ("EUH212 … Staub nicht einatmen.", "EUH211 … Aerosol oder Nebel nicht
    einatmen."), and the longer statement is the one printed.
    """
    patterns = []
    for code, wording in _catalogue().items():
        if "+" in code:
            continue
        pattern = _variant_pattern(wording)
        if pattern is not None:
            patterns.append((code, pattern))
    return tuple(patterns)


def _earlier_wordings() -> dict[str, tuple[str, ...]]:
    """Per code, the wordings earlier consolidations of the regulation gave it
    and today's does not (SDW-50; tools/clp/earlier_wordings.py)."""
    raw = json.loads(EARLIER_PATH.read_text(encoding="utf-8"))
    return {
        code: tuple(entry["text"] for entry in entries)
        for code, entries in raw["statements"].items()
    }


@lru_cache(maxsize=1)
def _wordings_ever() -> dict[str, tuple[str, ...]]:
    """Per code, every wording the regulation gives it or gave it, today's first."""
    earlier = _earlier_wordings()
    return {
        code: (wording, *earlier.get(code, ()))
        for code, wording in _catalogue().items()
    }


# A wording's units: each sentence, and a condition that ends in a colon
# ("BEI EINATMEN:").
_UNIT = re.compile(r"[^.:]*[.:]|[^.:]+$")


def _units(wording: str) -> list[str]:
    return [unit.strip() for unit in _UNIT.findall(wording.strip()) if unit.strip()]


def _forms_inside(code: str, ever: dict[str, tuple[str, ...]]) -> list[set[str]]:
    """Per part of the combination *code*, the forms it takes inside the
    combination's wordings (SDW-50).

    A wording of the combination is cut where it has as many units as its
    parts together, each part counted by its wordings of its own (which have
    to agree), and each part takes its units in order: P351 is "Einige
    Minuten lang behutsam mit Wasser spülen." inside P305+P351+P338. A
    combination that joins its parts into one sentence ("Giftig bei
    Verschlucken oder Hautkontakt", "… ausziehen und vor erneutem Tragen
    waschen.") gives its parts no form.

    >>> forms = _forms_inside("P305+P351+P338", _wordings_ever())
    >>> sorted(forms[1])
    ['Einige Minuten lang behutsam mit Wasser spülen.']
    """
    parts = code.split("+")
    counts = []
    for part in parts:
        sizes = {len(_units(wording)) for wording in ever.get(part, ())}
        if len(sizes) != 1:
            return [set() for _ in parts]
        counts.append(sizes.pop())
    inside: list[set[str]] = [set() for _ in parts]
    for wording in ever.get(code, ()):
        units = _units(wording)
        if len(units) != sum(counts):
            continue
        start = 0
        for forms, count in zip(inside, counts, strict=True):
            forms.add(" ".join(units[start : start + count]))
            start += count
    return inside


@lru_cache(maxsize=512)
def _official_forms(code: str, *, loose: bool = False) -> tuple[re.Pattern[str], ...]:
    """What a sheet may print for *code* without deviating, as patterns (SDW-50).

    Each wording the regulation gives or gave the code and, for a
    combination, its parts' wordings one after the other, each part in any
    of its own or in the form it has inside a wording of the combination
    (``_forms_inside``): P305+P351+P338 as "… mit Wasser ausspülen. … Weiter
    ausspülen." (the wordings of P351 and P338) or "… mit Wasser ausspülen.
    … Weiter spülen.". A form matches the start of the normalised text, in
    the forms Annex IV allows (SDB-163), a bracketed part also behind a
    slash (``_variant_body``). With *loose*, articles and auxiliaries may be
    left out or added and an infinitive may take "zu" (SDW-50).
    """
    ever = _wordings_ever()
    # canonical_text first: it also words the lettered H360 and H361.
    wordings = [canonical_text(code) or "", *ever.get(code, ())]
    if "+" in code:
        parts = code.split("+")
        own = [ever.get(part, ()) for part in parts]
        if all(own):
            inside = _forms_inside(code, ever)
            choices = [
                tuple(dict.fromkeys([*forms, *sorted(extra)]))
                for forms, extra in zip(own, inside, strict=True)
            ]
            wordings.extend(" ".join(chosen) for chosen in itertools.product(*choices))
    return tuple(
        re.compile(
            _variant_body(wording, choice_for_brackets=True, loose=loose)[0] + r"(?!\w)"
        )
        for wording in dict.fromkeys(wordings)
        if wording
    )


# A line that begins with a statement's code, behind a bullet or not. The
# marks before the code are read from the first of them only, and once.
_CODE_FIRST = re.compile(r"(?<![^\w\n])[^\w\n]*(?:euh|h|p)\s?\d{3}")


def variant_wordings_in_print_order(
    codes: Collection[str], passages: Sequence[str]
) -> list[str] | None:
    """The sheet's sentence for each of *codes* read in an Annex IV form (SDB-163).

    Like wordings_in_print_order, for codes whose sentences only a form the
    regulation allows matched: each takes the words its form covers, in the
    order the sheet prints them, and None unless every code is found.

    >>> variant_wordings_in_print_order(
    ...     ["P280", "P310"], ["Sofort Arzt anrufen. Schutzhandschuhe und Augenschutz tragen."]
    ... )
    ['P310 Sofort Arzt anrufen.', 'P280 Schutzhandschuhe und Augenschutz tragen.']
    """
    patterns = dict(_variant_patterns())
    texts = [re.sub(r"\s+", " ", passage).strip() for passage in passages]
    normalised = [_normalised_at(text) for text in texts]
    places: list[tuple[int, int, str, str]] = []
    for code in codes:
        pattern = patterns.get(code)
        match = next(
            (
                (index, found)
                for index, (haystack, _) in enumerate(normalised)
                for found in ([pattern.search(haystack)] if pattern else [])
                if found
            ),
            None,
        )
        if match is None:
            return None
        index, found = match
        at = normalised[index][1]
        start, end = at[found.start()], at[found.end() - 1] + 1
        if texts[index][end : end + 1] in (".", "!", ":"):
            end += 1
        places.append((index, start, code, texts[index][start:end].strip()))
    return [f"{code} {sentence}" for *_, code, sentence in sorted(places)]


def precautionary_by_variants(text: str) -> tuple[set[str], list[list[str]]]:
    """The precautionary codes whose wording *text* holds in a form Annex IV allows.

    Used only on a label that prints no precautionary code (SDB-6, SDB-163).
    Where two statements' forms cover the same words, the longer one is the
    statement ("Schutzhandschuhe mit Kälteisolierung … tragen" is P282, not
    P280); where they cover them alike, neither is taken, and the codes come
    back as an ambiguity.

    >>> codes, unclear = precautionary_by_variants(
    ...     "Schutzhandschuhe und Augenschutz tragen. Sofort Arzt anrufen."
    ... )
    >>> sorted(codes), unclear
    (['P280', 'P310'], [])
    """
    haystack = _normalised(text)
    found = [
        (match.start(), match.end(), code)
        for code, pattern in _variant_patterns()
        for match in pattern.finditer(haystack)
    ]
    found.sort(key=lambda hit: (-(hit[1] - hit[0]), hit[0]))
    taken: list[tuple[int, int, str]] = []
    unclear: list[list[str]] = []
    dropped: set[tuple[int, int]] = set()
    for start, end, code in found:
        overlapping = [hit for hit in taken if hit[0] < end and start < hit[1]]
        if not overlapping:
            if (start, end) not in dropped:
                taken.append((start, end, code))
            continue
        alike = [hit for hit in overlapping if (hit[0], hit[1]) == (start, end)]
        if alike and any(hit[2] != code for hit in alike):
            taken = [hit for hit in taken if (hit[0], hit[1]) != (start, end)]
            dropped.add((start, end))
            unclear.append(sorted({code, *(hit[2] for hit in alike)}))
    codes = {
        code
        for start, _, code in taken
        if code.startswith("P")
        # A sentence on a line that begins with a code is that code's.
        and not _CODE_FIRST.match(haystack, haystack.rfind("\n", 0, start) + 1)
    }
    unclear = [codes for codes in unclear if any(c.startswith("P") for c in codes)]
    # A condition alone ("BEI EINATMEN:") says nothing among a sentence's words
    # (SDB-122).
    if codes <= _conditions():
        codes = set()
    return codes, unclear
