"""The pictograms a label prints as images (SDB-179).

Most sheets print their pictograms as pictures, not as text: the text of a
sheet then holds no ``GHS07`` the parser could read. This stage looks at the
label as it is drawn. It finds the label on the PDF's pages by its text
positions, from the line with "Kennzeichnungselemente" or "GHS-Kennzeichnung"
(or a block of pictograms just above it) to the next subsection, without the
heads and feet of the pages; where there is none, section 2 (SDB-202, SDB-205).
On a scan the positions come from text recognition (SDB-204). It renders that
band, looks
for the red-framed diamonds every GHS
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
from collections import Counter, deque
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import pymupdf

from .extraction import OCR_MAX_PAGES, ExtractionError, ocr_lines
from .label_blocks import SMALL_PACKAGE_HEADING
from .versions import label_images_stage

# Where a label begins and ends on the page: the heading of 2.2, and the next
# subsection or the section after it.
# "GHS-Kennzeichnung" heads the label of a sheet without a 2.2 (SDB-202).
_LABEL_START = re.compile(
    r"Kennzeichnungselemente|^\s*GHS-Kennzeichnung\b", re.IGNORECASE
)
# Inside a label only the heading with its number begins another, as the text
# parser reads one label from "2.2 Kennzeichnungselemente" to its end (SDB-4):
# "Kennzeichnungselemente (CLP):" under it, or "ergänzende
# Kennzeichnungselemente" further down, is a line of the label.
_LABEL_HEADING = re.compile(r"2\s*\.\s*2\s*\.?\s*Kennzeichnungselemente", re.IGNORECASE)
# A block of pictograms set directly above that heading belongs to the label
# (SDB-187): its title, then nothing but the codes printed under the pictures.
_PICTOGRAMS_TITLE = re.compile(
    r"(?:[·•∙*]\s*)?(?:Gefahren)?piktogramm\w*\s*:?", re.IGNORECASE
)
_PICTOGRAM_CODES = re.compile(r"(?:GHS\s?0?\d{1,2}[\s,;]*)+", re.IGNORECASE)
_LABEL_END = re.compile(
    r"^\s*(?:·\s*)?(?:2\.3\.?\s|ABSCHNITT\s*3\b|3\.?\s+Zusammensetzung|Sonstige Gefahren)",
    re.IGNORECASE,
)
# A label with no end found runs over at most this many pages.
_LABEL_PAGES = 2
# Section 2, where no label is found in it (SDB-202): from its heading to that
# of section 3, over at most this many pages.
_SECTION_TWO = re.compile(
    r"^\s*(?:[·•]\s*)?(?:ABSCHNITT\s*0?2\b|2\s*\.?\s+M[öo]gliche\s+Gefahren)",
    re.IGNORECASE,
)
_SECTION_THREE = re.compile(
    r"^\s*(?:[·•]\s*)?(?:ABSCHNITT\s*0?3\b|3\s*\.?\s+Zusammensetzung)", re.IGNORECASE
)
_SECTION_TWO_PAGES = 3
# A page number, which stands in the page's head or foot.
_PAGE_NUMBER = re.compile(
    r"^(?:Seite|Page)\s*:?\s*\d{1,3}(?:\s*(?:/|von|of)\s*\d{1,3})?$"
    r"|^\d{1,3}\s*(?:/|von)\s*\d{1,3}$",
    re.IGNORECASE,
)

# The band is searched at this resolution: a pictogram of 1 cm is 39 pixels.
_SEARCH_DPI = 100
# A diamond is between 10 and 160 pixels wide at that resolution (2.5 mm to 4 cm).
_MIN_SIDE, _MAX_SIDE = 10, 160
# Diamonds set side by side with touching corners form one red area; up to
# this many in a row or column are split again.
_MAX_IN_A_ROW = 5
# A diamond is named from a rendering at this resolution.
_NAME_DPI = 150
# The second look, where the first names none (SDB-206).
_FINER_DPI = 300

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
    # The PDF has no text layer, and text recognition, which finds the label on
    # its pictures, is not at hand (SDB-204).
    NO_TEXT_LAYER = "no-text-layer"
    # Neither a label nor section 2 was found on the pages (SDB-202).
    NO_LABEL = "no-label-region"


@dataclass(frozen=True, slots=True)
class LabelImages:
    """What the label shows as pictures.

    *labels* has one entry for each label found on the pages, in the file's
    order, with the codes of the pictograms recognised in it; *unrecognised*
    counts, label by label, the red-framed diamonds no reference matched.
    Below a small package's heading in a label (SDB-188) the pictograms are
    that small package's: *small_packages* has, label by label, one entry for
    each such heading with its codes, *small_packages_unrecognised* the
    diamonds no reference matched there; neither counts in *labels*.
    """

    stage: str
    status: LabelImagesStatus
    labels: list[list[str]] = field(default_factory=list)
    unrecognised: list[int] = field(default_factory=list)
    small_packages: list[list[list[str]]] = field(default_factory=list)
    small_packages_unrecognised: list[list[int]] = field(default_factory=list)


def label_images_to_dict(images: LabelImages) -> dict[str, Any]:
    """*images* as JSON values, to keep beside the text of the sheet."""
    return {
        "stage": images.stage,
        "status": images.status.value,
        "labels": images.labels,
        "unrecognised": images.unrecognised,
        "small_packages": images.small_packages,
        "small_packages_unrecognised": images.small_packages_unrecognised,
    }


def label_images_from_dict(stored: Mapping[str, Any]) -> LabelImages:
    """What ``label_images_to_dict`` stored. A caller compares ``stage`` with
    ``label_images_stage()`` and looks at the PDF again where they differ.
    Without the small packages' keys the labels have none."""
    labels = [[str(code) for code in label] for label in stored["labels"]]
    return LabelImages(
        stage=str(stored["stage"]),
        status=LabelImagesStatus(stored["status"]),
        labels=labels,
        unrecognised=[int(count) for count in stored["unrecognised"]],
        small_packages=[
            [[str(code) for code in small] for small in label]
            for label in stored.get("small_packages", [[] for _ in labels])
        ],
        small_packages_unrecognised=[
            [int(count) for count in label]
            for label in stored.get("small_packages_unrecognised", [[] for _ in labels])
        ],
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
        lines = _page_lines(document, pages)
        if lines is None:
            return LabelImages(label_images_stage(), LabelImagesStatus.NO_TEXT_LAYER)
        regions = _label_regions(document, lines)
        if not regions and (section := _section_two(document, lines)):
            # No label on the pages: what section 2 shows is its (SDB-202).
            regions = [(section, [])]
        if not regions:
            return LabelImages(label_images_stage(), LabelImagesStatus.NO_LABEL)
        labels: list[list[str]] = []
        unrecognised: list[int] = []
        small_packages: list[list[list[str]]] = []
        small_unrecognised: list[list[int]] = []
        for region, splits in regions:
            # The label's own pictograms, then each small package's (SDB-188).
            codes: list[list[str]] = [[] for _ in range(len(splits) + 1)]
            missed = [0] * (len(splits) + 1)
            for number, top, bottom in region:
                page = document[number]
                for rect in _diamonds(page, top, bottom):
                    centre = (number, (rect.y0 + rect.y1) / 2)
                    part = sum(1 for split in splits if split < centre)
                    code = _name(page, rect)
                    if code is None:
                        missed[part] += 1
                    elif code not in codes[part]:
                        codes[part].append(code)
            labels.append(codes[0])
            unrecognised.append(missed[0])
            small_packages.append(codes[1:])
            small_unrecognised.append(missed[1:])
    return LabelImages(
        label_images_stage(),
        LabelImagesStatus.READ,
        labels,
        unrecognised,
        small_packages,
        small_unrecognised,
    )


# A band of one page: its number and the top and bottom of the band in points.
_Band = tuple[int, float, float]
# A line of a page: its top and bottom in points and its text.
_Line = tuple[float, float, str]


def _lines(page: pymupdf.Page) -> list[_Line]:
    """The top, bottom and text of each line of *page*, from the top down."""
    found: list[tuple[float, float, float, str]] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text:
                x0, y0, _, y1 = line["bbox"]
                found.append((round(y0), x0, y1, text))
    found.sort()
    return [(float(top), bottom, text) for top, _, bottom, text in found]


def _page_lines(
    document: pymupdf.Document, pages: range
) -> dict[int, list[_Line]] | None:
    """The lines of each page; read by text recognition where the file has no
    text layer (SDB-204). None where it has none and recognition cannot run."""
    if any(document[number].get_text("text").strip() for number in pages):
        return {number: _lines(document[number]) for number in pages}
    try:
        return {number: ocr_lines(document[number]) for number in pages[:OCR_MAX_PAGES]}
    except ExtractionError:
        return None


def _body(lines: dict[int, list[_Line]]) -> dict[int, tuple[float, float]]:
    """Where the body of each page begins and ends: below its head and above its
    foot, the lines that repeat on the pages and the page numbers (SDB-205).
    A label that runs on to the next page goes on below that page's head."""
    # A line of the head or foot stands at the same place on the pages, and
    # says something: a ":" or a bullet repeated in the body is no head.
    counts = Counter(
        key for page in lines.values() for key in {_place(t, x) for t, _, x in page}
    )
    repeated = max(2, (len(lines) + 1) // 2)

    def furniture(top: float, text: str) -> bool:
        if _PAGE_NUMBER.match(text):
            return True
        return len(_WORDS.findall(text)) >= 3 and counts[_place(top, text)] >= repeated

    body: dict[int, tuple[float, float]] = {}
    for number, page in lines.items():
        top, bottom = 0.0, float("inf")
        for line_top, line_bottom, text in page:
            if not furniture(line_top, text):
                break
            top = line_bottom
        for line_top, _, text in reversed(page):
            if not furniture(line_top, text) or line_top <= top:
                break
            bottom = line_top
        body[number] = (top, bottom)
    return body


_WORDS = re.compile(r"\w")


def _place(top: float, text: str) -> tuple[int, str]:
    """A line's text and its height on the page, to the nearest few points."""
    return round(top / 4), text


def _pictograms_above(lines: Sequence[_Line], heading: int) -> float:
    """The top of the label whose heading is *lines[heading]*: that of a block
    of pictograms directly above it on the page, else the heading's (SDB-187).
    Lines beside the heading, at its height, stand between neither."""
    y = lines[heading][0]
    for top, _, text in reversed(lines[:heading]):
        if top >= y or _PICTOGRAM_CODES.fullmatch(text):
            continue
        return top if _PICTOGRAMS_TITLE.fullmatch(text) else y
    return y


# Where a small package's label begins in a label: the page and the top of its
# heading (SDB-188).
_Split = tuple[int, float]


def _label_regions(
    document: pymupdf.Document, page_lines: dict[int, list[_Line]]
) -> list[tuple[list[_Band], list[_Split]]]:
    """Each label of the file as the bands of the pages it covers, with the
    places where a small package's label begins in it (SDB-188); on a page it
    runs on to, below the page's head, and to its foot (SDB-205)."""
    labels: list[tuple[list[_Band], list[_Split]]] = []
    current: list[_Band] | None = None
    splits: list[_Split] = []
    body = _body(page_lines)
    for number, lines in page_lines.items():
        page = document[number]
        head, foot = body[number]
        top: float | None = head if current is not None else None
        for index, (y, _, text) in enumerate(lines):
            if _LABEL_START.search(text) and (
                current is None
                or top is None
                or (y > top and _LABEL_HEADING.search(text) is not None)
            ):
                start = (
                    _pictograms_above(lines, index)
                    if _LABEL_HEADING.search(text)
                    else y
                )
                if current is not None and top is not None:
                    current.append((number, top, start))
                    labels.append((current, splits))
                current, top, splits = [], start, []
                continue
            if (
                current is not None
                and top is not None
                and y > top
                and _LABEL_END.search(text)
            ):
                current.append((number, top, y))
                labels.append((current, splits))
                current, top, splits = None, None, []
                continue
            if current is not None and SMALL_PACKAGE_HEADING.match(text):
                splits.append((number, y))
        if current is not None:
            current.append((number, top or head, min(foot, page.rect.height)))
            if len(current) >= _LABEL_PAGES:
                labels.append((current, splits))
                current, splits = None, []
    if current:
        labels.append((current, splits))
    return labels


def _section_two(
    document: pymupdf.Document, page_lines: dict[int, list[_Line]]
) -> list[_Band]:
    """Section 2 as the bands of the pages it covers, without their heads and
    feet (SDB-202, SDB-205); empty where its heading is not found."""
    bands: list[_Band] = []
    body = _body(page_lines)
    top: float | None = None
    for number, lines in page_lines.items():
        head, foot = body[number]
        if top is not None:
            top = head
        for y, _, text in lines:
            if top is None and _SECTION_TWO.search(text):
                top = y
            elif top is not None and y > top and _SECTION_THREE.search(text):
                bands.append((number, top, y))
                return bands
        if top is not None:
            bands.append((number, top, min(foot, document[number].rect.height)))
            if len(bands) >= _SECTION_TWO_PAGES:
                return bands
    return bands


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
    """The code of the pictogram in *rect*; looked at once more in finer detail
    where the first look names none, which a small one needs (SDB-206)."""
    for dpi in (_NAME_DPI, _FINER_DPI):
        pixmap = page.get_pixmap(
            dpi=dpi, clip=rect, colorspace=pymupdf.csRGB, alpha=False
        )
        if (code := name_pictogram(fingerprint(grey(pixmap)))) is not None:
            return code
    return None
