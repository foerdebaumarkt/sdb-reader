#!/usr/bin/env python3
"""Download the consolidated CLP Regulation from the EU's Publications Office.

``sdb_reader.pictograms`` maps hazard statements to pictograms and signal
words, and ``clp_statements_de.json`` holds the statements' wording. Both come
from Regulation (EC) No 1272/2008, and both were wrong in places for as long as
checking them meant reading the regulation somewhere else: H225 is Flam. Liq. 2
and carries "Gefahr", not "Achtung", and H290 is Met. Corr. 1.

This fetches the regulation, so the tables can be verified against their source
rather than against memory. The Publications Office is the publisher of the
Official Journal; nothing else is used.

Three things this works around:

* EUR-Lex itself answers a script with an empty page. The Publications Office
  serves the same files by CELEX number, and lists the consolidated versions
  through its public query service.
* The consolidated version changes with every amendment, so no date is baked
  in. A consolidation can be published before it applies; without a version
  named, the newest one that applies today is taken.
* The file type differs between consolidations, so the known PDF types are
  asked for in turn.

Usage:
    python tools/clp/fetch_regulation.py --list
    python tools/clp/fetch_regulation.py
    python tools/clp/fetch_regulation.py --version 20250201 --language EN
    python tools/clp/fetch_regulation.py --output data/clp
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pymupdf

RESOURCE = "https://publications.europa.eu/resource/celex"
QUERY_SERVICE = "https://publications.europa.eu/webapi/rdf/sparql"
CELEX_CONSOLIDATED = "02008R1272"
USER_AGENT = "sdb-reader (CLP label-element verification)"
PDF_TYPES = ("pdfa2a", "pdfa1a", "pdfa1b", "pdf1x", "pdf")

VERSIONS_QUERY = f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?celex WHERE {{
  ?work cdm:resource_legal_id_celex ?celex .
  FILTER(STRSTARTS(STR(?celex), "{CELEX_CONSOLIDATED}-"))
}}
"""

# A consolidated CLP runs to roughly 1,600 pages; anything far below that is an
# error page dressed as a download.
MINIMUM_BYTES = 5_000_000
REQUIRED_MARKERS = ("ANHANG I", "ANNEX I")


def _get(url: str, headers: dict[str, str], *, timeout: int = 600) -> bytes:
    # Both addresses are the constants above: https, one host.
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload: bytes = response.read()
    return payload


def available_versions() -> list[str]:
    """Consolidation dates the Publications Office holds, oldest first."""
    url = f"{QUERY_SERVICE}?{urllib.parse.urlencode({'query': VERSIONS_QUERY})}"
    answer = json.loads(
        _get(url, {"Accept": "application/sparql-results+json"}, timeout=120)
    )
    found = {
        binding["celex"]["value"].partition("-")[2]
        for binding in answer["results"]["bindings"]
    }
    versions = sorted(v for v in found if len(v) == 8 and v.isdigit())
    if not versions:
        raise SystemExit(
            "The Publications Office listed no consolidated versions of "
            f"{CELEX_CONSOLIDATED}; its query service may have changed."
        )
    return versions


def in_force(versions: list[str], today: str) -> str:
    """The newest of *versions* that applies on *today* (YYYYMMDD)."""
    applying = [version for version in versions if version <= today]
    if not applying:
        raise SystemExit(f"No consolidated version applies on {today}.")
    return applying[-1]


def fetch(version: str, language: str) -> bytes:
    url = f"{RESOURCE}/{CELEX_CONSOLIDATED}-{version}"
    payload = None
    for pdf_type in PDF_TYPES:
        print(f"  fetching {url} as {pdf_type}")
        try:
            payload = _get(
                url,
                {
                    "Accept": f"application/pdf;type={pdf_type}",
                    "Accept-Language": language.lower(),
                },
            )
        except urllib.error.HTTPError as exc:
            with exc:
                if exc.code != 404:
                    raise
            continue
        break

    if payload is None or not payload.startswith(b"%PDF"):
        raise SystemExit(
            f"The Publications Office holds no PDF of {version} in {language}. "
            "Not every consolidation exists in every language."
        )
    if len(payload) < MINIMUM_BYTES:
        raise SystemExit(
            f"Got {len(payload):,} bytes, expected at least {MINIMUM_BYTES:,}. "
            "That is too small to be the consolidated regulation."
        )
    return payload


def verify(path: Path) -> None:
    """Confirm the annexes are actually in there before anyone relies on it."""
    with pymupdf.open(path) as document:
        pages = len(document)
        text = "".join(document[i].get_text() for i in range(pages))

    if not any(marker in text for marker in REQUIRED_MARKERS):
        raise SystemExit(
            f"None of {REQUIRED_MARKERS} appear in the download. "
            "It is a PDF of the right size but not the regulation."
        )
    print(f"  {pages} pages, {len(text):,} characters of text")
    for marker in ("Signalwort", "Signal word", "H225", "H290"):
        count = text.count(marker)
        if count:
            print(f"    {marker}: {count} occurrences")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", help="Consolidation date, e.g. 20260701")
    parser.add_argument("--language", default="DE", help="Two-letter language code")
    parser.add_argument("--output", default="data/clp", help="Target directory")
    parser.add_argument(
        "--list", action="store_true", help="List available consolidations and exit"
    )
    args = parser.parse_args()

    versions = available_versions()
    today = datetime.now(UTC).strftime("%Y%m%d")
    if args.list:
        print(f"{len(versions)} consolidated versions:")
        for version in versions:
            print(
                f"  {version}" + ("  (not yet applicable)" if version > today else "")
            )
        return 0

    version = args.version or in_force(versions, today)
    if version not in versions:
        raise SystemExit(
            f"{version} is not among the versions listed. "
            f"Newest is {versions[-1]}; use --list to see them all."
        )
    print(f"CLP consolidated {version}, language {args.language}")

    payload = fetch(version, args.language)
    directory = Path(args.output)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"CELEX_{CELEX_CONSOLIDATED}-{version}_{args.language}.pdf"
    target.write_bytes(payload)
    print(f"  wrote {target} ({len(payload):,} bytes)")

    verify(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
