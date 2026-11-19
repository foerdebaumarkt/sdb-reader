#!/usr/bin/env python3
"""Check the signal words in sdb_reader.pictograms against Annex I of the CLP.

The module decides which signal word and which pictograms a product shows. Both
come from the label-element tables in Annex I of Regulation (EC) No 1272/2008,
but the module cited the regulation in one line and no entry named its table --
so two values sat wrong for as long as anyone can tell. H225 is Flam. Liq. 2 and
carries "Gefahr"; the module said "Achtung". H290 is Met. Corr. 1 and carries
"Achtung"; the module said "Gefahr".

This reads the regulation itself, fetched by tools/clp/fetch_regulation.py,
and reports every disagreement with the table it came from. It is a report, not
a fixer: what the tables should say is a legal question, and the answer belongs
in a reviewed commit rather than in an automatic rewrite.

It compares column by column: a column of a label-element table is one
category, with the hazard statements that category prints together and its
signal word, and the module must derive that word from those statements. Per
statement the comparison went wrong for H229: its table gives it "Gefahr" in
category 1 and "Achtung" in categories 2 and 3, so it counted as depending on
the category and was left without an entry -- but category 1 prints H222
beside it, and the word comes from there. A statement on its own has no signal
word in the regulation; a category has.

Signal words, and of the pictograms only their absence. The pictogram row of
every table holds images, not text, so the text layer cannot say which
pictogram a category carries; where a category has none, the cell says "Kein
Piktogramm", and that is compared.

Usage:
    python tools/clp/verify_tables.py
    python tools/clp/verify_tables.py --pdf data/clp/CELEX_02008R1272-20260701_DE.pdf
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sdb_reader.pictograms import H_TO_SIGNAL_WORD, get_signal_word, pictograms_for

# Most label-element tables sit under "Kennzeichnungselemente für ...", but not
# all: the aquatic ones are headed "KURZFRISTIG (AKUT) GEWÄSSERGEFÄHRDEND" and
# "LANGFRISTIG (CHRONISCH) ...". Selecting pages by that first heading skipped
# them, and with them H410 to H413 -- which is how H411 kept a signal word the
# regulation does not give it. Select on the row label instead: any page
# carrying a "Signalwort" row is worth reading.
TABLE_TITLE = re.compile(r"Signalwort")
TABLE_NUMBER = re.compile(r"Tabelle\s+(\d+\.\d+\.\d+)")
# "H 204:" in the table for explosives, "H204:" everywhere else.
HAZARD_CODE = re.compile(r"\b((?:EU)?H)\s?(\d{3})\s*:")
SIGNAL_WORDS = ("Gefahr", "Achtung")
NO_SIGNAL_WORD = re.compile(r"Kein\s*Signal\s*wort", re.IGNORECASE)
NO_PICTOGRAM = re.compile(r"Kein\s*Pikto\s*gramm", re.IGNORECASE)


def _clean(cell: str | None) -> str:
    # A word broken at the end of a line carries a soft hyphen and the line
    # break: "Gefahrenhin\xad\nweis". Left as a space, the row labelled so was
    # not found, and with it five tables went unread -- among them the one for
    # gases under pressure, whose signal word sat wrong in the module.
    joined = re.sub(r"\xad\s*", "", cell or "")
    return re.sub(r"\s+", " ", joined).strip()


def _row_starting_with(rows: list[list[str]], label: str) -> list[str] | None:
    for row in rows:
        if row and _clean(row[0]).startswith(label):
            return [_clean(c) for c in row]
    return None


def _hazard_rows(rows: list[list[str]]) -> list[list[str]]:
    """The row of hazard statements, and the rows that continue it.

    The table for acute toxicity gives one row per route ("— oral",
    "— dermal", "— inhalativ"), each a row of its own under the label.
    """
    found: list[list[str]] = []
    for row in rows:
        label = _clean(row[0]) if row else ""
        if label.startswith("Gefahrenhinweis") or (found and label.startswith("—")):
            found.append([_clean(c) for c in row])
        elif found:
            break
    return found


def _word(signal: str) -> tuple[bool, str | None]:
    """Whether the cell can be read, and the signal word it gives."""
    # "Kein Signalwort" is a value, not a blank. Reading it as a blank turns
    # "the regulation assigns none" into "could not be read", and that
    # difference is the whole point.
    if NO_SIGNAL_WORD.search(signal):
        return True, None
    word = next((w for w in SIGNAL_WORDS if w in signal), None)
    return word is not None or not signal.strip(), word


@dataclass(frozen=True)
class Column:
    """One category of a label-element table: its statements and its word."""

    table: str
    codes: frozenset[str]
    word: str | None
    # The table says "Kein Piktogramm" for the category. A pictogram itself is
    # an image and cannot be read; that there is none can.
    no_pictogram: bool


def columns_from(pdf_path: Path) -> tuple[list[Column], list[str]]:
    """Every category the label-element tables give a signal word or none."""

    import pymupdf

    columns: list[Column] = []
    skipped: list[str] = []
    # A table that breaks across a page: its signal words and pictogram row,
    # waiting for the statements on the next page.
    waiting: tuple[str, list[str], list[str] | None] | None = None

    with pymupdf.open(pdf_path) as document:
        for index in range(len(document)):
            page = document[index]
            text = page.get_text()
            carried, waiting = waiting, None
            if not TABLE_TITLE.search(text) and carried is None:
                continue
            # The table's number stands above it; a page can name others first.
            before = text[: text.find("Signalwort")] if "Signalwort" in text else ""
            numbers = TABLE_NUMBER.findall(before)
            number = numbers[-1] if numbers else f"Seite {index + 1}"

            for table in page.find_tables().tables:
                rows = table.extract()
                signal_row = _row_starting_with(rows, "Signalwort")
                pictogram_row = _row_starting_with(rows, "GHS-Piktogramm")
                hazard_rows = _hazard_rows(rows)
                if signal_row and not hazard_rows:
                    waiting = (number, signal_row, pictogram_row)
                    continue
                if not signal_row and hazard_rows and carried:
                    number, signal_row, pictogram_row = carried
                    carried = None
                if not signal_row or not hazard_rows:
                    continue
                if any(len(signal_row) != len(row) for row in hazard_rows):
                    skipped.append(
                        f"Tabelle {number}: {len(signal_row)} Signalwort-Spalten, "
                        "die Zeilen der Gefahrenhinweise haben andere"
                    )
                    continue

                # Column 0 holds the row labels; the data starts at column 1.
                if pictogram_row is None or len(pictogram_row) != len(signal_row):
                    pictogram_row = [""] * len(signal_row)
                for hazard_row in hazard_rows:
                    for signal, pictogram, hazards in zip(
                        signal_row[1:], pictogram_row[1:], hazard_row[1:], strict=True
                    ):
                        readable, word = _word(signal)
                        if not readable:
                            continue  # a cell we cannot interpret: do not judge
                        codes = frozenset(
                            prefix + digits
                            for prefix, digits in HAZARD_CODE.findall(hazards)
                        )
                        if codes:
                            columns.append(
                                Column(
                                    number,
                                    codes,
                                    word,
                                    bool(NO_PICTOGRAM.search(pictogram)),
                                )
                            )
            if carried is not None:
                skipped.append(
                    f"Tabelle {carried[0]}: Signalwörter ohne Gefahrenhinweise, "
                    "auch nicht auf der Seite danach"
                )

    return columns, skipped


def _named(codes: frozenset[str]) -> str:
    return " + ".join(sorted(codes))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf",
        default=None,
        help="Consolidated CLP PDF; the newest in data/clp by default",
    )
    args = parser.parse_args()

    if args.pdf:
        pdf_path = Path(args.pdf)
    else:
        candidates = sorted(Path("data/clp").glob("CELEX_02008R1272-*_DE.pdf"))
        if not candidates:
            raise SystemExit(
                "No regulation in data/clp. Run tools/clp/fetch_regulation.py first."
            )
        pdf_path = candidates[-1]
    print(f"Regulation: {pdf_path.name}\n")

    columns, skipped = columns_from(pdf_path)
    words: dict[frozenset[str], set[str | None]] = {}
    tables: dict[frozenset[str], set[str]] = {}
    for column in columns:
        words.setdefault(column.codes, set()).add(column.word)
        tables.setdefault(column.codes, set()).add(column.table)

    # The same statements with two words: the word hangs on the category, and
    # the statements cannot say which.
    by_category = {codes for codes, given in words.items() if len(given) > 1}
    agree, disagree = 0, []
    for codes, given in sorted(words.items(), key=lambda item: _named(item[0])):
        if codes in by_category:
            continue
        regulation = next(iter(given))
        ours = get_signal_word(set(codes))
        if ours == regulation:
            agree += 1
        else:
            disagree.append((codes, ours, regulation))

    # Pictograms are images; only "Kein Piktogramm" can be compared. Where the
    # same statements carry a pictogram in another category, the module cannot
    # tell the two apart and is not judged.
    without = {column.codes for column in columns if column.no_pictogram}
    always_without = without - {c.codes for c in columns if not c.no_pictogram}
    shows = sorted(
        (codes for codes in always_without if pictograms_for(set(codes))),
        key=_named,
    )
    by_category_pictogram = sorted(
        (codes for codes in without - always_without if pictograms_for(set(codes))),
        key=_named,
    )

    assigned = {code for codes in words for code in codes}
    ours_only = sorted(c for c in H_TO_SIGNAL_WORD if c not in assigned)

    print(f"categories read from the tables        : {len(words)}")
    print(f"  the module derives the same word     : {agree}")
    print(f"  the module derives another           : {len(disagree)}")
    print(f"  word depends on the category         : {len(by_category)}")
    print(f"  ours, not assigned by any table      : {len(ours_only)}")
    print(f"categories with 'Kein Piktogramm'      : {len(without)}")
    print(f"  the module derives one all the same  : {len(shows)}")
    print(f"  tables skipped                       : {len(skipped)}")

    if disagree:
        print("\nDISAGREEMENT -- derived by pictograms.py vs the regulation:")
        for codes, ours, regulation in disagree:
            print(
                f"  {_named(codes)}: pictograms.py={ours!r}  Anhang I={regulation!r}"
                f"   (Tabelle {', '.join(sorted(tables[codes]))})"
            )
    if shows:
        print("\nDISAGREEMENT -- a pictogram where the regulation gives none:")
        for codes in shows:
            print(
                f"  {_named(codes)}: pictograms.py="
                f"{sorted(pictograms_for(set(codes)))}"
                f"   (Tabelle {', '.join(sorted(tables[codes]))})"
            )
    if by_category_pictogram:
        print("\nThe same statements, with and without a pictogram by category:")
        for codes in by_category_pictogram:
            print(
                f"  {_named(codes)}: pictograms.py derives "
                f"{sorted(pictograms_for(set(codes)))}"
                f"   (Tabelle {', '.join(sorted(tables[codes]))})"
            )
    if by_category:
        print("\nThe same statements, two signal words by category:")
        for codes in sorted(by_category, key=_named):
            named = sorted(word or "none" for word in words[codes])
            print(
                f"  {_named(codes)}: {named}, pictograms.py derives "
                f"{get_signal_word(set(codes))!r}"
                f"   (Tabelle {', '.join(sorted(tables[codes]))})"
            )
    if ours_only:
        print("\nIn pictograms.py but not assigned by any table:")
        print(f"  {', '.join(ours_only)}")
        print(
            "  They stand in tables this cannot read, such as one that breaks "
            "across a page: check those by hand."
        )
    if skipped:
        print("\nTables this could not read:")
        for line in skipped[:10]:
            print(f"  {line}")

    return 1 if disagree or shows else 0


if __name__ == "__main__":
    sys.exit(main())
