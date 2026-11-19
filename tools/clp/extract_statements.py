#!/usr/bin/env python3
"""Extract the German wording of H-, EUH- and P-statements from the CLP regulation.

Annex III lists the hazard statements, the EUH ones in its Parts 2 and 3, and
Annex IV the precautionary ones, each as a table of one row per language. This
reads the German row and writes the data file the library renders from, so the
text a reading gives is the one the regulation prescribes rather than the one a
supplier happened to type.

The regulation comes from tools/clp/fetch_regulation.py. Run this after
fetching a newer consolidation:

    python tools/clp/extract_statements.py
    python tools/clp/extract_statements.py --pdf data/clp/CELEX_...pdf

Each statement is classified, because only one of the four kinds can be
rendered without knowing what the label says:

    fixed         one wording, no choice        -- rendered
    parameter     "…" or "<…>" for the supplier -- left alone
    alternatives  a "/" list to pick from       -- left alone
    disputed      the regulation contradicts itself -- left alone

The third is the awkward one. "P280 Schutzhandschuhe/Schutzkleidung/
Augenschutz/Gesichtsschutz tragen" is a menu -- a label carrying only
"Augenschutz tragen" would gain three requirements it does not have. But
"P313 Ärztlichen Rat einholen/ärztliche Hilfe hinzuziehen" is the whole
sentence, slash included. The two cannot be told apart from the text, so both
are held back.

The fourth is the surprising one. The regulation states each statement more than
once and does not always say the same thing. Annex I lists the classification
criteria and quotes the hazard statement each category carries; Annex III holds
the wording. Annex IV Part 1 selects a precautionary statement and quotes it;
Part 2 holds the wording and opens by saying the statements are to be taken from
there. Seven codes disagree between the two places:

    P103  Teil 1: Lesen Sie sämtliche Anweisungen aufmerksam und befolgen
                  Sie diese.
          Teil 2: Vor Gebrauch Kennzeichnungsetikett lesen.
    H229  Anh. I: Behälter steht unter Druck: Kann bei Erwärmung bersten.
          Anh III: Behälter steht unter Druck: kann bei Erwärmung bersten.

Amendment M19 rewrote Annex IV Part 1 without touching Part 2, which is why
Part 2 still carries the 2008 sentence for P103 and the M4 one for P210. P338 is
a plain typo -- "Eventuell Vorhandene Kontaktlinsen", capital mid-sentence --
and H410 drops a comma its own annex uses when quoting it and its three
siblings keep. Deciding which half of a self-contradicting regulation governs is
not this script's to make, and putting a superseded sentence or a typo on a
product is worse than leaving the supplier's, so these are not rendered.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT = Path("src/sdb_reader/clp_statements_de.json")

CODE = re.compile(r"^(EUH ?\d{3}[A-Za-z]*|[HP]\d{3}(?:\s*\+\s*[HP]\d{3})*)\b")

# The consolidated text carries the amendment apparatus of the Official Journal
# inline -- "►C4 … ◄" marks a corrigendum, "▼M19" a modification, "___" an
# elision. None of it belongs to the sentence.
APPARATUS = re.compile(r"►[A-Z]\d*|◄|▼[A-Z]\d*|_{2,}")


def _cell_text(raw: str) -> str:
    """One table cell as a single line.

    The soft hyphen has to be handled before anything else: the regulation
    hyphenates across lines with U+00AD, and removing it without joining the
    halves turns "langfris­\ntiger" into two words.
    """
    text = re.sub(r"­\s*\n\s*", "", raw)
    text = re.sub(r"([\w)\]])-\s*\n\s*(\w)", r"\1\2", text)
    # A line that ends on a slash wrapped there; the alternatives it separates
    # belong together. Without this, "Dampf/\nAerosol" becomes "Dampf/ Aerosol"
    # and no supplier line matches the menu it is supposed to offer.
    text = re.sub(r"/\s*\n\s*", "/", text)
    text = APPARATUS.sub("", text.replace("\n", " "))
    return re.sub(r"\s+", " ", text).strip()


def classify(text: str) -> str:
    if "…" in text or "<" in text:
        return "parameter"
    if "/" in text:
        return "alternatives"
    return "fixed"


def _code_of(cell: str) -> str | None:
    match = CODE.match(_cell_text(cell))
    if not match:
        return None
    return re.sub(r"\s*\+\s*", "+", match.group(1)).replace("EUH ", "EUH")


def _comparable(text: str) -> str:
    """Reduce a sentence to what an etiquette would actually read differently.

    The criteria tables are set in narrow columns and quote their statements
    without a closing period, so a literal comparison finds a difference on
    almost every code. Three things are levelled, all of them typesetting and
    none of them wording:

      * the closing period, which Annex I omits throughout
      * hyphens, because a word broken across a column keeps its hyphen in the
        text layer even after the halves are rejoined ("Gesundheits-schädlich")
      * a cell holding two statements, cut at the second code

    Levelling is symmetric -- both sides go through this -- so it can hide a
    difference but never invent one.
    """
    text = re.sub(r"\s+(?:oder|und)?\s*$", "", text.rstrip(" ."))
    return re.sub(r"\s+", " ", text.replace("-", "")).strip()


ANNEX_HEADING = re.compile(r"\bANHANG (VIII|VII|VI|IV|III|II|I|V)\b")
CODE_IN_CELL = re.compile(r"^(EUH\d{3}[A-Za-z]*|H\d{3}):\s*(.+)$")
NEXT_CODE_IN_CELL = re.compile(r"\s+(?:oder\s+|und\s+)?(?:EUH\d{3}[A-Za-z]*|H\d{3}):")


def extract(pdf_path: Path) -> dict[str, dict[str, str]]:  # noqa: C901
    """Read the wordings and everywhere else the regulation states them.

    Three places matter. Annex III and Annex IV Part 2 hold the wording tables,
    one row per language, and are what a label is taken from. Annex I lists the
    classification criteria and quotes the hazard statement each category
    carries; Annex IV Part 1 does the same for the precautionary ones. Reading
    all three is what makes a contradiction visible -- see the module docstring.
    """
    import pymupdf

    statements: dict[str, dict[str, str]] = {}
    quoted: dict[str, set[str]] = {}
    with pymupdf.open(pdf_path) as document:
        current: str | None = None
        two_in_one = False
        annex: str | None = None
        in_selection = False
        for index in range(len(document)):
            page = document[index]
            text = page.get_text()
            heading = ANNEX_HEADING.search(text)
            if heading:
                annex = heading.group(1)
                in_selection = annex == "IV"
            if in_selection and "Teil 2: Sicherheitshinweise" in re.sub(
                r"\s+", " ", text
            ):
                in_selection = False
            if annex not in {"I", "III", "IV"}:
                continue

            for table in page.find_tables().tables:
                for row in table.extract():
                    if not row:
                        continue
                    if annex == "I":
                        for cell in row:
                            found = CODE_IN_CELL.match(_cell_text(str(cell or "")))
                            if not found:
                                continue
                            wording = found.group(2)
                            cut = NEXT_CODE_IN_CELL.search(wording)
                            quoted.setdefault(found.group(1), set()).add(
                                wording[: cut.start()] if cut else wording
                            )
                        continue

                    code = _code_of(str(row[0] or ""))
                    if code:
                        current = code
                        # "EUH 201/ 201A" is two statements in one row, and
                        # the German cell holds both sentences one after the
                        # other; neither is the wording of the first code.
                        two_in_one = "/" in _cell_text(str(row[0] or ""))
                    if in_selection:
                        if code and len(row) >= 2:
                            selected = _cell_text(str(row[1] or ""))
                            if selected:
                                quoted.setdefault(code, set()).add(selected)
                        continue
                    if len(row) < 3 or _cell_text(str(row[1] or "")) != "DE":
                        continue
                    wording = _cell_text(str(row[2] or ""))
                    if current and wording and current not in statements:
                        statements[current] = {
                            "text": wording,
                            "kind": "alternatives" if two_in_one else classify(wording),
                        }

    for code, entry in statements.items():
        elsewhere = quoted.get(code)
        if not elsewhere:
            continue
        target = _comparable(entry["text"])
        if any(_comparable(other) == target for other in elsewhere):
            continue
        entry["quoted_as"] = sorted(elsewhere)[0]
        # "kind" says why a statement is not rendered, so only the kind that
        # would be gets reclassified. A parameter or a menu is already held
        # back for a stronger reason than a disagreement over its notation --
        # ten of them differ only in "<Expositionsweg angeben>" against
        # "(Expositionsweg angeben)" -- and calling those disputed would hide
        # what they actually are. The conflict is recorded either way.
        if entry["kind"] == "fixed":
            entry["kind"] = "disputed"
    return statements


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    pdf_path = args.pdf
    if pdf_path is None:
        candidates = sorted(Path("data/clp").glob("CELEX_02008R1272-*_DE.pdf"))
        if not candidates:
            raise SystemExit(
                "No regulation in data/clp. Run tools/clp/fetch_regulation.py first."
            )
        pdf_path = candidates[-1]

    statements = extract(pdf_path)
    if len(statements) < 150:
        raise SystemExit(
            f"Only {len(statements)} statements found in {pdf_path.name}; "
            "the tables were not read as expected."
        )

    payload: dict[str, Any] = {
        "source": pdf_path.name,
        "statements": {
            code: {
                "text": entry["text"],
                "kind": entry["kind"],
                **({"quoted_as": entry["quoted_as"]} if "quoted_as" in entry else {}),
            }
            for code, entry in sorted(statements.items())
        },
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    kinds: dict[str, int] = {}
    for entry in statements.values():
        kinds[entry["kind"]] = kinds.get(entry["kind"], 0) + 1
    print(f"{len(statements)} statements from {pdf_path.name} -> {args.output}")
    for kind, count in sorted(kinds.items()):
        print(f"  {count:4d}  {kind}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
