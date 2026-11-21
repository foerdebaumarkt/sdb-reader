"""Write src/sdb_reader/pictogram_references.json from the drawings beside this file.

Each of the nine GHS pictograms is drawn once, in drawings/GHS0n.svg. A sheet
prints them in many sizes and line widths; the references are therefore the
drawing at two sizes with its lines thickened step by step, as a sheet's
smaller or bolder print looks. Nothing in the references comes from a sheet.

Run from the repository's directory: .venv/bin/python tools/pictograms/references.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf

from sdb_reader.label_images import REFERENCES, fingerprint, grey

HERE = Path(__file__).parent
TARGET = HERE.parent.parent / "src" / "sdb_reader" / REFERENCES
# The width in pixels each drawing is rendered at, and how many pixels its
# lines are thickened by at that width.
RENDERINGS = ((120, (0, 1)), (200, (0, 1, 2, 3)))
# Enough to tell nine pictograms apart; more only makes the file longer.
DIGITS = 3


def _thickened(rows: list[list[int]], radius: int) -> list[list[int]]:
    """*rows* with each dark line *radius* pixels wider on every side."""
    if radius == 0:
        return rows
    height, width = len(rows), len(rows[0])
    across = [
        [min(row[max(0, x - radius) : x + radius + 1]) for x in range(width)]
        for row in rows
    ]
    return [
        [
            min(
                across[yy][x]
                for yy in range(max(0, y - radius), min(height, y + radius + 1))
            )
            for x in range(width)
        ]
        for y in range(height)
    ]


def _rendered(drawing: Path, width: int) -> list[list[int]]:
    with pymupdf.open(drawing) as document:
        page = document[0]
        zoom = width / page.rect.width
        return grey(page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True))


def main() -> None:
    references: dict[str, list[list[float]]] = {}
    for drawing in sorted((HERE / "drawings").glob("GHS0*.svg")):
        references[drawing.stem] = [
            [round(value, DIGITS) for value in fingerprint(_thickened(rows, radius))]
            for width, radii in RENDERINGS
            for rows in [_rendered(drawing, width)]
            for radius in radii
        ]
    TARGET.write_text(
        json.dumps(
            {
                "source": "tools/pictograms/drawings, see tools/pictograms/README.md",
                "references": references,
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
