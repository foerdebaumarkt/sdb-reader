#!/usr/bin/env python3
"""Write the list of all message codes for the operator's manual.

One page per language of the manual, from the registry of codes and the
catalog of that language, so the list cannot fall behind the program:
``tests/test_docs.py`` fails when a page differs from what this writes.

    .venv/bin/python tools/docs/message_pages.py           # write both pages
"""

from __future__ import annotations

import sys
from pathlib import Path

from sdb_reader import MESSAGE_CODES, shipped_catalog

DOCS = Path(__file__).resolve().parents[2] / "docs"

# The codes by what they are about, in the order of the registry. A code that
# is in no group stops the tool: a new code needs its place on the page.
GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "Reading the text",
        "Text lesen",
        (
            "read-by-ocr-no-text-layer",
            "read-by-ocr-single-characters",
            "pages-read-by-ocr",
            "short-text",
        ),
    ),
    (
        "Why no text could be read",
        "Warum sich kein Text lesen ließ",
        (
            "pdf-not-found",
            "pdf-too-large",
            "pdf-unreadable",
            "no-text-layer",
            "no-text",
            "ocr-unavailable",
            "ocr-too-old",
            "ocr-language-missing",
            "ocr-timeout",
            "ocr-failed",
        ),
    ),
    (
        "What the file is",
        "Was die Datei ist",
        (
            "no-title-keywords",
            "no-section-marker",
            "no-regulation-reference",
            "no-hazard-codes-in-text",
            "short-sample",
            "safety-information",
            "leaflet-title",
            "other-language",
            "cover-only",
            "title-in-running-text",
            "no-safety-data-sheet",
            "not-a-sheet",
            "unreadable",
        ),
    ),
    (
        "Reading the sheet",
        "Das Blatt lesen",
        (
            "line-too-long",
            "no-label-section",
            "several-sheets",
            "classified-before-clp",
            "label-before-clp",
            "no-hazard-codes",
            "label-undetermined",
            "no-precautionary-codes",
            "euh-wording-outside-label",
            "signal-word-not-taken",
            "pictograms-derived",
            "precautionary-wording-unclear",
            "label-line-unassigned",
            "statement-too-long",
            "signal-word-derived",
            "no-identification-section",
            "no-supplier-name",
            "no-supplier-address",
            "no-supplier-phone",
            "no-emergency-phone",
        ),
    ),
    (
        "Findings",
        "Befunde",
        (
            "wording-deviates",
            "undated",
            "predates-annex-ii",
            "revised-in-future",
            "classification-undetermined",
            "old-classification",
            "old-format",
            "classification-not-stated",
            "classification-contradicts-label",
            "label-not-found",
            "label-without-hazard-statement",
            "label-without-precautionary-statement",
            "different-products",
            "country-editions-differ",
            "euh-outside-label",
            "not-german",
        ),
    ),
    (
        "The embedded file",
        "Die eingebettete Datei",
        (
            "embedded-too-large",
            "embedded-doctype",
            "embedded-not-xml",
            "embedded-wrong-root",
            "embedded-no-datasheet",
        ),
    ),
    (
        "Asking a language model",
        "Ein Sprachmodell fragen",
        (
            "model-http-error",
            "model-unreachable",
            "model-reply-not-json",
            "model-reply-without-message",
            "model-reply-empty",
            "model-answer-unreadable",
            "model-not-asked",
        ),
    ),
    (
        "Lines on the error output",
        "Zeilen auf der Fehlerausgabe",
        (
            "cli-file-failed",
            "cli-file-broke",
            "cli-no-embedded-file",
            "cli-embedded-not-handed-out",
            "cli-saved",
            "cli-half-line-removed",
            "cli-progress",
            "cli-interrupted",
            "cli-summary-read",
            "cli-summary-ask",
        ),
    ),
    (
        "Comparing two runs",
        "Zwei Läufe vergleichen",
        (
            "diff-run",
            "diff-files",
            "diff-differing",
            "diff-none",
            "diff-field",
            "diff-field-counted-only",
            "diff-stages-differ",
            "diff-models-differ",
            "diff-questions-differ",
        ),
    ),
    (
        "The report of show",
        "Der Bericht von show",
        (
            "show-kind-sheet",
            "show-kind-other-language",
            "show-kind-safety-information",
            "show-kind-document",
            "show-kind-unreadable",
            "show-kind-broke",
            "show-cover-page",
            "show-cover-page-display",
            "show-line-cover-page",
            "show-line-cover-page-display",
            "show-sheet-of",
            "show-whole-file",
            "show-label-product",
            "show-label-supplier",
            "show-label-contact",
            "show-label-emergency",
            "show-label-revised",
            "show-label-issued",
            "show-label-labelling",
            "show-label-notes",
            "show-date",
            "show-information-email",
            "show-product-dated",
            "show-with-version",
            "show-not-stated",
            "show-no-labelling",
            "show-no-signal-word",
            "show-no-pictograms",
            "show-no-statements",
            "show-needs-sheet",
            "show-needs-no-sheet",
            "show-stated-voluntary",
            "show-stated-article",
            "show-no-notes",
            "show-no-product",
            "show-undated",
            "show-notes",
            "show-summary",
            "show-interrupted",
        ),
    ),
    (
        "From stored texts of earlier versions",
        "Aus aufbewahrten Texten früherer Fassungen",
        ("unknown",),
    ),
)

PAGES = {
    "en": (
        DOCS / "usage" / "messages.md",
        "# All messages",
        "Every message the program can give, with its code, the values it "
        "carries\nand its sentence in English. The page is written by "
        "`tools/docs/message_pages.py`\nfrom the program's own list; do not "
        "edit it by hand. What a message is and\nhow to choose its language "
        "is in [Understanding the output](output.md#messages).",
        ("Code", "Values", "Sentence"),
    ),
    "de": (
        DOCS / "bedienung" / "meldungen.md",
        "# Alle Meldungen",
        "Jede Meldung, die das Programm geben kann, mit ihrem Code, ihren "
        "Angaben\nund ihrem Satz auf Deutsch. Die Seite schreibt "
        "`tools/docs/message_pages.py`\naus der Liste des Programms; sie "
        "wird nicht von Hand geändert. Was eine Meldung\nist und wie man "
        "ihre Sprache wählt, steht unter [Die Ausgabe verstehen](ausgabe.md#meldungen).",
        ("Code", "Angaben", "Satz"),
    ),
}


def page(language: str) -> str:
    """The page of *language* as it should stand on disk."""
    grouped = [code for _, _, codes in GROUPS for code in codes]
    if sorted(grouped) != sorted(MESSAGE_CODES):
        missing = sorted(set(MESSAGE_CODES) - set(grouped))
        gone = sorted(set(grouped) - set(MESSAGE_CODES))
        raise SystemExit(
            f"GROUPS is out of step with MESSAGE_CODES: missing {missing}, gone {gone}"
        )
    _, title, intro, header = PAGES[language]
    sentences = shipped_catalog(language).sentences
    lines = [title, "", intro, ""]
    for english, german, codes in GROUPS:
        lines += [f"## {german if language == 'de' else english}", ""]
        lines += [f"| {' | '.join(header)} |", "| --- | --- | --- |"]
        for code in codes:
            values = ", ".join(f"`{name}`" for name in MESSAGE_CODES[code]) or "–"
            entry = sentences[code]
            # A message that counts shows both its sentences, the one for exactly
            # one first.
            shown = (
                entry
                if isinstance(entry, str)
                else " / ".join(
                    entry[form] for form in ("one", "other") if form in entry
                )
            )
            sentence = shown.replace("|", "\\|")
            lines.append(f"| `{code}` | {values} | {sentence} |")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> int:
    for language, (path, *_) in PAGES.items():
        path.write_text(page(language), encoding="utf-8")
        print(f"wrote {path.relative_to(DOCS.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
