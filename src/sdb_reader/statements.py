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
    return _fixed_statements().get(re.sub(r"\s*\+\s*", "+", code.strip()))


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
    joined = re.sub(r"\s*\+\s*", "+", code.strip())
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
    if not fixed or code.strip() in _EFFECT_OPENINGS:
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
# no label prints; these are the sentences labels do print.
_EFFECT_WORDINGS: tuple[tuple[str, str], ...] = (
    (
        "Kann die Fruchtbarkeit beeinträchtigen oder das Kind im Mutterleib schädigen",
        "H360",
    ),
    ("Kann die Fruchtbarkeit beeinträchtigen", "H360"),
    ("Kann das Kind im Mutterleib schädigen", "H360"),
    (
        "Kann vermutlich die Fruchtbarkeit beeinträchtigen oder das Kind im "
        "Mutterleib schädigen",
        "H361",
    ),
    ("Kann vermutlich die Fruchtbarkeit beeinträchtigen", "H361"),
    ("Kann vermutlich das Kind im Mutterleib schädigen", "H361"),
)


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
def _euh_patterns(partial: bool = False) -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Each EUH statement that a wording identifies, longest wording first.

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
        (code, _wording_pattern(entry["text"], partial=partial))
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
    text: str, *, skip: Collection[str] = (), partial: bool = False
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
    """
    if not text:
        return []
    found: list[tuple[int, str, str]] = []
    haystack = text
    for code, pattern in _euh_patterns(partial):
        # A code in *skip* still consumes its wording: printed as "EUH204
        # Enthält Isocyanate. Kann allergische …", it is not EUH208 as well.
        for match in [] if code in skip else pattern.finditer(haystack):
            # A name broken at a line's end is joined as the reader joins
            # it (SDB-54), also across the empty line the reader leaves where
            # a column ends (SDB-45).
            lines = join_broken_words(re.sub(r"\n\s*\n", "\n", match.group(0)))
            sentence = re.sub(r"\s+", " ", lines).strip()
            found.append((match.start(), code, sentence))
        haystack = pattern.sub(lambda m: " " * len(m.group(0)), haystack)
    return [(code, sentence) for _, code, sentence in sorted(found)]


@dataclass(frozen=True, slots=True)
class StatementWording:
    """One statement of a label: what the sheet prints and what the regulation says."""

    code: str
    # As the parser read it; None for a code in a list (SDB-30) or without text.
    sheet: str | None
    # None where the regulation gives the code no single wording.
    regulation: str | None


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
    return [
        StatementWording(code, wording, canonical_text(code))
        for code, printed in wordings.items()
        for wording in (printed or (None,))
    ]


def deviates_from_regulation(code: str, wording: str) -> bool:
    """Whether the sheet's *wording* departs from the regulation's for *code* (SDW-6).

    Only a wording that begins with the regulation's first three words and then
    does not hold it in full: one that begins otherwise is mostly text the
    parser found under the code, and text after the complete wording mostly a
    heading it read on into. Case, punctuation and spacing do not count.
    """
    canonical = canonical_text(code)
    if canonical is None or not wording.strip() or _holds_another(code, wording):
        return False
    printed = _comparable(wording).split()
    official = _comparable(canonical).split()
    if printed[:_OPENING_WORDS] != official[:_OPENING_WORDS]:
        return False
    return printed[: len(official)] != official
