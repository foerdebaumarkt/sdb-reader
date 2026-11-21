"""The pictograms a label prints as images (SDB-179).

Most sheets print their pictograms as pictures, not as text: the text of a
sheet then holds no ``GHS07`` the parser could read. This stage looks at the
label as it is drawn. It finds the label on the PDF's pages by its text
positions, from the line with "Kennzeichnungselemente" to the next
subsection, renders that band, looks for the red-framed diamonds every GHS
pictogram has, and names each by comparing its inside with references made
from the public-domain drawings of the nine pictograms.

The stage needs the PDF, not the text read from it, and has a version of its
own (``label_images_stage()``): a caller that keeps texts keeps what this
stage found beside them, and a text stays valid when this stage changes. It is
deterministic and uses no model: the same file gives the same codes.
"""

from __future__ import annotations

import json
import re
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import pymupdf

from .versions import label_images_stage

# Where a label begins and ends on the page: the heading of 2.2, and the next
# subsection or the section after it.
_LABEL_START = re.compile(r"Kennzeichnungselemente", re.IGNORECASE)
_LABEL_END = re.compile(
    r"^\s*(?:·\s*)?(?:2\.3\.?\s|ABSCHNITT\s*3\b|3\.?\s+Zusammensetzung|Sonstige Gefahren)",
    re.IGNORECASE,
)
# A label with no end found runs over at most this many pages.
_LABEL_PAGES = 2

# The band is searched at this resolution: a pictogram of 1 cm is 39 pixels.
_SEARCH_DPI = 100
# A diamond is between 10 and 160 pixels wide at that resolution (2.5 mm to 4 cm).
_MIN_SIDE, _MAX_SIDE = 10, 160
# Diamonds set side by side with touching corners form one red area; up to
# this many in a row or column are split again.
_MAX_IN_A_ROW = 5
# A diamond is named from a rendering at this resolution.
_NAME_DPI = 150

# The fingerprint: the inside of the diamond, grey on white, cropped, scaled to
# _SIZE x _SIZE and cut to the diamond's inner part, so the red frame all
# pictograms share counts for nothing.
_SIZE = 32
_INNER = 0.62
_CENTRE = (_SIZE - 1) / 2
_MASK = [
    (j, i)
    for j in range(_SIZE)
    for i in range(_SIZE)
    if abs(i - _CENTRE) + abs(j - _CENTRE) < _INNER * (_SIZE / 2)
]
# A diamond is named when its best reference matches at least so well and
# better than the best of another pictogram by the margin beside it; otherwise
# it counts as not recognised. The second pair takes a weaker likeness with a
# wider margin: the environment pictogram (GHS09) is printed in a drawing
# bolder than the public-domain one, and matches it at 0.4 to 0.5 with the
# next pictogram 0.2 behind.
ACCEPTED = ((0.5, 0.08), (0.4, 0.12))

REFERENCES = "pictogram_references.json"


class LabelImagesStatus(StrEnum):
    """Whether the label was looked at as drawn."""

    # The label was found on the pages and searched for pictograms.
    READ = "read"
    # The PDF has no text layer: its pages are pictures, and the label cannot be
    # found on them by its text.
    NO_TEXT_LAYER = "no-text-layer"
    # No line "Kennzeichnungselemente" was found on the pages.
    NO_LABEL = "no-label-region"


@dataclass(frozen=True, slots=True)
class LabelImages:
    """What the label shows as pictures.

    *labels* has one entry for each label found on the pages, in the file's
    order, with the codes of the pictograms recognised in it; *unrecognised*
    counts, label by label, the red-framed diamonds no reference matched.
    """

    stage: str
    status: LabelImagesStatus
    labels: list[list[str]] = field(default_factory=list)
    unrecognised: list[int] = field(default_factory=list)


def label_images_to_dict(images: LabelImages) -> dict[str, Any]:
    """*images* as JSON values, to keep beside the text of the sheet."""
    return {
        "stage": images.stage,
        "status": images.status.value,
        "labels": images.labels,
        "unrecognised": images.unrecognised,
    }


def label_images_from_dict(stored: Mapping[str, Any]) -> LabelImages:
    """What ``label_images_to_dict`` stored. A caller compares ``stage`` with
    ``label_images_stage()`` and looks at the PDF again where they differ."""
    return LabelImages(
        stage=str(stored["stage"]),
        status=LabelImagesStatus(stored["status"]),
        labels=[[str(code) for code in label] for label in stored["labels"]],
        unrecognised=[int(count) for count in stored["unrecognised"]],
    )


def read_label_images(path: Path, *, max_pages: int | None = None) -> LabelImages:
    """The pictograms the labels of the PDF at *path* show as pictures.

    *max_pages* bounds the pages looked at, as in ``read_sheet``.
    """
    with pymupdf.open(path) as document:
        pages = range(
            document.page_count
            if max_pages is None
            else min(max_pages, document.page_count)
        )
        if not any(document[number].get_text("text").strip() for number in pages):
            return LabelImages(label_images_stage(), LabelImagesStatus.NO_TEXT_LAYER)
        regions = _label_regions(document, pages)
        if not regions:
            return LabelImages(label_images_stage(), LabelImagesStatus.NO_LABEL)
        labels: list[list[str]] = []
        unrecognised: list[int] = []
        for region in regions:
            codes: list[str] = []
            missed = 0
            for number, top, bottom in region:
                page = document[number]
                for rect in _diamonds(page, top, bottom):
                    code = _name(page, rect)
                    if code is None:
                        missed += 1
                    elif code not in codes:
                        codes.append(code)
            labels.append(codes)
            unrecognised.append(missed)
    return LabelImages(
        label_images_stage(), LabelImagesStatus.READ, labels, unrecognised
    )


# A band of one page: its number and the top and bottom of the band in points.
_Band = tuple[int, float, float]


def _lines(page: pymupdf.Page) -> list[tuple[float, str]]:
    """The top and text of each line of *page*, from the top down."""
    found: list[tuple[float, float, str]] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text:
                x0, y0 = line["bbox"][0], line["bbox"][1]
                found.append((round(y0), x0, text))
    found.sort()
    return [(float(top), text) for top, _, text in found]


def _label_regions(document: pymupdf.Document, pages: range) -> list[list[_Band]]:
    """Each label of the file as the bands of the pages it covers."""
    labels: list[list[_Band]] = []
    current: list[_Band] | None = None
    for number in pages:
        page = document[number]
        top: float | None = 0.0 if current is not None else None
        for y, text in _lines(page):
            if _LABEL_START.search(text) and (
                current is None or top is None or y > top
            ):
                if current is not None and top is not None:
                    current.append((number, top, y))
                    labels.append(current)
                current, top = [], y
                continue
            if (
                current is not None
                and top is not None
                and y > top
                and _LABEL_END.search(text)
            ):
                current.append((number, top, y))
                labels.append(current)
                current, top = None, None
        if current is not None:
            current.append((number, top or 0.0, page.rect.height))
            if len(current) >= _LABEL_PAGES:
                labels.append(current)
                current = None
    if current:
        labels.append(current)
    return labels


def _red(pixmap: pymupdf.Pixmap) -> bytearray:
    """A mask of the pixels of *pixmap* in the red of a pictogram's frame."""
    width, height, n, stride = pixmap.width, pixmap.height, pixmap.n, pixmap.stride
    samples = pixmap.samples
    mask = bytearray(width * height)
    for y in range(height):
        row = y * stride
        for x in range(width):
            i = row + x * n
            r, g, b = samples[i], samples[i + 1], samples[i + 2]
            if r > 170 and g < 110 and b < 110 and r - g > 90:
                mask[y * width + x] = 1
    return mask


def _components(
    mask: bytearray, width: int, height: int
) -> Iterator[tuple[int, int, int, int, int]]:
    """The box and pixel count of each connected red area."""
    seen = bytearray(width * height)
    for start in range(width * height):
        if not mask[start] or seen[start]:
            continue
        queue = deque([start])
        seen[start] = 1
        x0 = x1 = start % width
        y0 = y1 = start // width
        count = 0
        while queue:
            p = queue.popleft()
            count += 1
            px, py = p % width, p // width
            x0, x1, y0, y1 = min(x0, px), max(x1, px), min(y0, py), max(y1, py)
            for dy in (-1, 0, 1):
                ny = py + dy
                if not 0 <= ny < height:
                    continue
                for dx in (-1, 0, 1):
                    nx = px + dx
                    if 0 <= nx < width:
                        q = ny * width + nx
                        if mask[q] and not seen[q]:
                            seen[q] = 1
                            queue.append(q)
        yield x0, y0, x1, y1, count


def _share(
    mask: bytearray, width: int, box: tuple[int, int, int, int], centre: tuple[int, int]
) -> float:
    """The share of red pixels in a small box around *centre*."""
    x0, y0, x1, y1 = box
    rx, ry = max(1, (x1 - x0 + 1) // 10), max(1, (y1 - y0 + 1) // 10)
    cx, cy = centre
    total = hit = 0
    for y in range(max(y0, cy - ry), min(y1, cy + ry) + 1):
        for x in range(max(x0, cx - rx), min(x1, cx + rx) + 1):
            total += 1
            hit += mask[y * width + x]
    return hit / total if total else 0.0


def _is_diamond(mask: bytearray, width: int, box: tuple[int, int, int, int]) -> bool:
    """A diamond's frame leaves the corners of its box empty and runs through
    the middle of each side; a logo, a rectangle or a filled sign does not."""
    x0, y0, x1, y1 = box
    rx, ry = max(1, (x1 - x0 + 1) // 10), max(1, (y1 - y0 + 1) // 10)
    mx, my = (x0 + x1) // 2, (y0 + y1) // 2
    corners = [
        (x0 + rx, y0 + ry),
        (x1 - rx, y0 + ry),
        (x0 + rx, y1 - ry),
        (x1 - rx, y1 - ry),
    ]
    middles = [
        (mx, y0 + ry // 2),
        (mx, y1 - ry // 2),
        (x0 + rx // 2, my),
        (x1 - rx // 2, my),
    ]
    return (
        max(_share(mask, width, box, c) for c in corners) < 0.08
        and min(_share(mask, width, box, m) for m in middles) > 0.15
    )


def _candidates(
    x0: int, y0: int, x1: int, y1: int
) -> Iterator[tuple[int, int, int, int]]:
    """The box of a red area, or the boxes of the diamonds in a row or column
    of them that touch."""
    w, h = x1 - x0 + 1, y1 - y0 + 1
    for k in range(1, _MAX_IN_A_ROW + 1):
        if 0.8 <= w / (k * h) <= 1.25:
            for i in range(k):
                yield x0 + i * w // k, y0, x0 + (i + 1) * w // k - 1, y1
            return
        if k > 1 and 0.8 <= (k * w) / h <= 1.25:
            for i in range(k):
                yield x0, y0 + i * h // k, x1, y0 + (i + 1) * h // k - 1
            return


def _diamonds(page: pymupdf.Page, top: float, bottom: float) -> list[pymupdf.Rect]:
    """The red-framed diamonds in the band from *top* to *bottom*, in reading
    order, in page points."""
    clip = pymupdf.Rect(
        0, max(0.0, top - 4), page.rect.width, min(page.rect.height, bottom + 4)
    )
    if clip.is_empty:
        return []
    pixmap = page.get_pixmap(
        dpi=_SEARCH_DPI, clip=clip, colorspace=pymupdf.csRGB, alpha=False
    )
    width, height = pixmap.width, pixmap.height
    mask = _red(pixmap)
    scale = 72 / _SEARCH_DPI
    found: list[pymupdf.Rect] = []
    for x0, y0, x1, y1, count in _components(mask, width, height):
        if count / ((x1 - x0 + 1) * (y1 - y0 + 1)) > 0.6:
            continue  # a filled red area is no frame
        for box in _candidates(x0, y0, x1, y1):
            bw, bh = box[2] - box[0] + 1, box[3] - box[1] + 1
            if not (_MIN_SIDE <= bw <= _MAX_SIDE and _MIN_SIDE <= bh <= _MAX_SIDE):
                continue
            if _is_diamond(mask, width, box):
                found.append(
                    pymupdf.Rect(
                        clip.x0 + box[0] * scale,
                        clip.y0 + box[1] * scale,
                        clip.x0 + (box[2] + 1) * scale,
                        clip.y0 + (box[3] + 1) * scale,
                    )
                )
    found.sort(key=lambda rect: (round(rect.y0 / 20), rect.x0))
    return found


def grey(pixmap: pymupdf.Pixmap) -> list[list[int]]:
    """*pixmap* as rows of grey values, transparency laid on white."""
    n, alpha, stride = pixmap.n, pixmap.alpha, pixmap.stride
    samples = pixmap.samples
    rows: list[list[int]] = []
    for y in range(pixmap.height):
        row: list[int] = []
        base = y * stride
        for x in range(pixmap.width):
            i = base + x * n
            if n - alpha == 1:
                grey = samples[i]
            else:
                grey = (
                    299 * samples[i] + 587 * samples[i + 1] + 114 * samples[i + 2]
                ) // 1000
            if alpha:
                a = samples[i + n - 1]
                grey = (grey * a + 255 * (255 - a)) // 255
            row.append(grey)
        rows.append(row)
    return rows


def _cropped(rows: list[list[int]], threshold: int = 235) -> list[list[int]]:
    """*rows* without the white around what is drawn."""
    height = len(rows)
    width = len(rows[0]) if height else 0
    ys = [y for y in range(height) if min(rows[y]) < threshold]
    step = max(1, height // 64)
    xs = [
        x
        for x in range(width)
        if any(rows[y][x] < threshold for y in range(0, height, step))
    ]
    if not ys or not xs:
        return rows
    return [row[xs[0] : xs[-1] + 1] for row in rows[ys[0] : ys[-1] + 1]]


def _scaled(rows: list[list[int]]) -> list[list[float]]:
    """*rows* as _SIZE x _SIZE means of their areas."""
    height, width = len(rows), len(rows[0])
    out: list[list[float]] = []
    for j in range(_SIZE):
        y0 = j * height // _SIZE
        y1 = max(y0 + 1, (j + 1) * height // _SIZE)
        row: list[float] = []
        for i in range(_SIZE):
            x0 = i * width // _SIZE
            x1 = max(x0 + 1, (i + 1) * width // _SIZE)
            total = sum(sum(rows[y][x0:x1]) for y in range(y0, y1))
            row.append(total / ((y1 - y0) * (x1 - x0)))
        out.append(row)
    return out


def fingerprint(rows: list[list[int]]) -> list[float]:
    """The inside of a pictogram drawn as *rows* of grey values: cropped,
    scaled, cut to the diamond's inner part, centred on its mean and of
    length one, so that the dot product of two is their likeness."""
    small = _scaled(_cropped(rows))
    flat = [small[j][i] for j, i in _MASK]
    mean = sum(flat) / len(flat)
    centred = [value - mean for value in flat]
    norm = sum(value * value for value in centred) ** 0.5 or 1.0
    return [value / norm for value in centred]


@cache
def _references() -> dict[str, list[list[float]]]:
    """The fingerprints of the nine pictograms, several drawings each."""
    stored = json.loads(files("sdb_reader").joinpath(REFERENCES).read_text("utf-8"))
    return {
        code: [list(map(float, v)) for v in vectors]
        for code, vectors in stored["references"].items()
    }


def name_pictogram(vector: Sequence[float]) -> str | None:
    """The code of the pictogram whose references *vector* is most like, or
    None where no pictogram is clearly most like it."""
    scores = sorted(
        (
            (
                max(
                    sum(a * b for a, b in zip(vector, ref, strict=True)) for ref in refs
                ),
                code,
            )
            for code, refs in _references().items()
        ),
        reverse=True,
    )
    (best, code), (second, _) = scores[0], scores[1]
    accepted = any(
        best >= likeness and best - second >= margin for likeness, margin in ACCEPTED
    )
    return code if accepted else None


def _name(page: pymupdf.Page, rect: pymupdf.Rect) -> str | None:
    pixmap = page.get_pixmap(
        dpi=_NAME_DPI, clip=rect, colorspace=pymupdf.csRGB, alpha=False
    )
    return name_pictogram(fingerprint(grey(pixmap)))
