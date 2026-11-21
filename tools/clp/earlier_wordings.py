#!/usr/bin/env python3
"""Collect the wordings the CLP Regulation gave its statements before today's.

A sheet keeps the wording that was the regulation's when it was written, and
a sheet that does so prints no wording of its own. `wording-deviates` accepts
those wordings (SDW-50); this writes them, with the consolidations that hold
each, into the data file the library reads them from.

It reads every consolidated version under data/clp/ older than the one
`clp_statements_de.json` was extracted from, with the same extraction as
extract_statements.py, and keeps per statement each wording that differs from
today's by more than case, punctuation and spacing. Statements the regulation
no longer has are left out: no label is compared with them.

    for v in $(.venv/bin/python tools/clp/fetch_regulation.py --list | grep -Eo '^  [0-9]{8}$'); do
        .venv/bin/python tools/clp/fetch_regulation.py --version "$v"
    done
    .venv/bin/python tools/clp/earlier_wordings.py

The download of the oldest consolidation fails (the Publications Office holds
no PDF of it); the loop goes on, and the file names the versions it read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CURRENT = Path("src/sdb_reader/clp_statements_de.json")
DEFAULT_OUTPUT = Path("src/sdb_reader/clp_earlier_wordings_de.json")
VERSION = re.compile(r"^CELEX_02008R1272-(\d{8})_DE\.pdf$")


def comparable(text: str) -> str:
    """*text* without what does not tell two wordings apart: case,
    punctuation and spacing, as the library compares them."""
    lowered = text.casefold().replace("ß", "ss")
    return re.sub(r"\s+", " ", re.sub(r"[^\wäöü ]+", " ", lowered)).strip()


def earlier_wordings(
    current: Mapping[str, str], versions: Mapping[str, Mapping[str, str]]
) -> dict[str, list[dict[str, Any]]]:
    """Per code of *current*, its earlier wordings and the versions holding each.

    *current* is code to today's wording, *versions* consolidation date to
    code to that version's wording. A wording counts once however it was
    punctuated; the text kept is the newest version's.
    """
    found: dict[str, dict[str, dict[str, Any]]] = {}
    for version in sorted(versions):
        for code, text in versions[version].items():
            if code not in current or comparable(text) == comparable(current[code]):
                continue
            entry = found.setdefault(code, {}).setdefault(
                comparable(text), {"text": text, "versions": []}
            )
            entry["text"] = text
            entry["versions"].append(version)
    return {
        code: sorted(by_text.values(), key=lambda entry: entry["versions"][0])
        for code, by_text in sorted(found.items())
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--regulations", type=Path, default=Path("data/clp"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    # The tool beside this one: Python puts a script's directory on the path.
    from extract_statements import extract

    data = json.loads(CURRENT.read_text(encoding="utf-8"))
    today = VERSION.match(data["source"])
    if today is None:
        raise SystemExit(f"{CURRENT} names no consolidation: {data['source']!r}")
    current = {code: entry["text"] for code, entry in data["statements"].items()}

    versions: dict[str, dict[str, str]] = {}
    for pdf in sorted(args.regulations.glob("CELEX_02008R1272-*_DE.pdf")):
        match = VERSION.match(pdf.name)
        if match is None or match.group(1) >= today.group(1):
            continue
        statements = extract(pdf)
        if len(statements) < 150:
            raise SystemExit(
                f"Only {len(statements)} statements found in {pdf.name}; "
                "the tables were not read as expected."
            )
        versions[match.group(1)] = {
            code: entry["text"] for code, entry in statements.items()
        }
        print(f"  {match.group(1)}: {len(statements)} statements", file=sys.stderr)
    if not versions:
        raise SystemExit(
            f"No consolidation older than {today.group(1)} in {args.regulations}. "
            "Run tools/clp/fetch_regulation.py first."
        )

    wordings = earlier_wordings(current, versions)
    payload = {
        "current": data["source"],
        "versions": sorted(versions),
        "statements": wordings,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    count = sum(len(entries) for entries in wordings.values())
    print(
        f"{count} earlier wordings of {len(wordings)} statements "
        f"from {len(versions)} versions -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
