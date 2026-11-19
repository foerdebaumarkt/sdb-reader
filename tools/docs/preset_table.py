#!/usr/bin/env python3
"""Write the table of presets into the manual's pages about asking.

From the file the package ships, so the table cannot fall behind the
program: ``tests/test_docs.py`` fails when a page differs from what this
writes.

    .venv/bin/python tools/docs/preset_table.py           # write both pages
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sdb_reader.presets import shipped_presets

DOCS = Path(__file__).resolve().parents[2] / "docs"
PAGES = {"de": DOCS / "bedienung" / "fragen.md", "en": DOCS / "usage" / "asking.md"}
BEGIN, END = "<!-- presets:begin -->", "<!-- presets:end -->"
HEAD = {
    "de": ("Name", "Wofür", "Was in die Anfrage kommt", "Gemessen mit"),
    "en": ("Name", "What for", "What goes into the request", "Measured with"),
}
NOT_MEASURED = {"de": "nicht gemessen", "en": "not measured"}
LEFT_OUT = {"de": "ohne", "en": "without"}


def table(language: str) -> str:
    """The table of the shipped presets in *language*."""
    lines = [
        "| " + " | ".join(HEAD[language]) + " |",
        "| " + " | ".join("---" for _ in HEAD[language]) + " |",
    ]
    for preset in shipped_presets().values():
        fields = [f"`{json.dumps(dict(preset.request))}`"] if preset.request else []
        fields += [f"{LEFT_OUT[language]} `{name}`" for name in sorted(preset.omit)]
        measured = (
            f"`{preset.tested_with}`, {preset.tested_on.isoformat()}"
            if preset.tested_with and preset.tested_on
            else NOT_MEASURED[language]
        )
        lines.append(
            f"| `{preset.name}` | {preset.describe(language)} | "
            f"{', '.join(fields)} | {measured} |"
        )
    return "\n".join(lines)


def page(language: str) -> str:
    """The page of *language* with its table as this tool writes it."""
    text = PAGES[language].read_text(encoding="utf-8")
    before, _, rest = text.partition(BEGIN)
    _, found, after = rest.partition(END)
    if not found:
        raise SystemExit(f"{PAGES[language]} lacks {BEGIN} … {END}")
    return f"{before}{BEGIN}\n{table(language)}\n{END}{after}"


def main() -> int:
    for language, path in PAGES.items():
        path.write_text(page(language), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
