"""Read a PDF page's text layer in print order, from the positions of its words.

PyMuPDF's plain text follows the order in which the file draws its text, and
for a two-column label:value form that is not the order of the page: Akzo
Nobel's sheets draw every label, then every colon, then every value, so
"Gefahrenhinweise" and "H412 - Schädlich für Wasserorganismen …" reach the text
several lines apart, and P101 under "Allgemein:" lands behind the 2.3 heading.

This reader puts the words where the page prints them instead (SDB-42 to
SDB-45):

1. words that share a baseline form a row, read left to right;
2. a wide gap splits a row into cells, the columns of the form or table;
3. a cell that is a colon, or begins with one, separates a label from its
   value, and so does a cell ending in one before a value; each label:value
   pair becomes one line, "label: value";
4. the rows below a pair continue it while their cells stay in its columns: a
   label printed over several lines ("Ergänzende / Kennzeichnungselemente")
   stays one label, and each further line of the value stays a line of its own;
5. a row of one cell -- a heading, a line of a paragraph -- is a line.

A form in two columns that prints no colons is read as pairs only where a
row says so itself (SDB-114): a numbered subsection heading of section 1 with
its content beside it, and, on a page that has shown one, a contact label
beside its value.

Any other rows of several cells with no label:value pair among them are a
table, and there the file's own order is kept. A table's cells can hold several lines
each, a heading over its value ("Überarbeitet am:" over "17.02.2025"), and
which cells belong together cannot be told from the positions alone; the
program that wrote the file knew, and wrote them in that order.

The output is text, as before, so the parser, the record and the model input
keep their shape.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field

import pymupdf

from .line_breaks import join_broken_words

# Text extraction flags: the same the plain reader uses (page.get_text()), so a
# word reads the same in both, ligatures and whitespace alike.
FLAGS = pymupdf.TEXTFLAGS_TEXT

# Two words share a row when their vertical centres are this close, as a share
# of the smaller height. A label and its value sit on one baseline but not
# always to the point: 274.1 against 274.5 on one supplier's sheets.
_ROW_TOLERANCE = 0.35

# A word more than this many times taller than the row's text is not part of
# it: a pictogram set in a symbol font ("d", "~" at 33 points) is centred on
# its caption's line.
_HEIGHT_RATIO = 2.0

# A gap wider than this, as a share of the word height, separates two cells.
# Measured over 300 sheets: a space between words is 0.2 to 0.3 of the height,
# a colon set apart from its value 0.6, a column gap 1.0 and more.
_CELL_GAP = 0.8

# Two rows of one label:value pair are closer than this, as a share of the
# height of their words; the next pair or a heading stands further off. Akzo
# Nobel sets the lines of a value 11.4 apart and the pairs 15, with words 11.1
# high. The height, not the font size: it follows the line spacing the font is
# set with, where the size does not -- one supplier's labels are 8 point type on lines
# 11.1 apart.
_CONTINUATION_PITCH = 1.2

# Space between two rows that reads as an empty line, as a share of the row
# height. It becomes one in the text, as an empty paragraph did in the plain
# reading: a word broken at the foot of a page ("Kenn-") otherwise meets the
# page number below it, and the line join makes "Kenn1 / 12" of it.
_BLANK_GAP = 0.8

# How far the first line of a right-aligned label may end from its last line,
# as a share of the row height. Right-aligned lines end within a point of each
# other; a looser bound took a heading or the end of a table line above a pair
# for the start of its label ("Handschutz Material: Nitrilkautschuk").
_HEAD_SLACK = 0.15

# How far a continuation may stand left of its column and still belong to it.
_COLUMN_SLACK = 2.0

# Text whose direction is further than this from horizontal is rotated.
_SKEW = 0.01

_COLON = ":"

# A page number in a cell of its own: "1/20", "2 / 21", "Seite 3 von 9",
# "Seite: 1/13", "Seite 3(8)". As a label's only value it has to say "Seite":
# "Stand: 05/22" is a date.
_PAGE_NUMBER = re.compile(
    r"(?:Seite\s*:?\s*)?\d{1,3}\s*(?:/|von|\()\s*\d{1,3}\)?", re.IGNORECASE
)
_NAMED_PAGE_NUMBER = re.compile(r"Seite\s*:?\s*\d.*", re.IGNORECASE)

# A form in two columns without colons (SDB-114): what stands at the left of
# a row and makes the row a pair with what stands right of it. A numbered
# subsection heading of section 1, "1.3 Einzelheiten zum Lieferanten, …" (some
# sheets write "1,3"), or a contact label that is the whole cell.
_SECTION_ONE_HEADING = re.compile(r"1[.,][1-4]\.?\s+[A-ZÄÖÜ]\w")
_CONTACT_LABEL = re.compile(
    r"(?:Telefon|Tel\.?|Telefax|Fax|E-?Mail|Internet|Homepage|Web(?:seite|site)?)"
    r"(?:[- ]?(?:Nr\.?|Nummer|Adresse)|nummer|adresse)?",
    re.IGNORECASE,
)

# The lines of a heading in the label column of such a form stand further
# apart than those of a label:value pair, 10.5 with words 8 high, and still
# closer than an empty line's worth.
_FORM_PITCH = 1.5

# A line the line join (SDB-32) would join to the next: a hyphen after a word
# character, a bracket or a slash, as join_broken_words reads it.
_BROKEN = re.compile(r"[\w)\]/]-$")


@dataclass(slots=True)
class _Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    # Where the file draws it: block, line and word, as PyMuPDF numbers them.
    order: tuple[int, int, int]

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def centre(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass(slots=True)
class _Cell:
    words: list[_Word]

    @property
    def x0(self) -> float:
        return self.words[0].x0

    @property
    def x1(self) -> float:
        return self.words[-1].x1

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)


@dataclass(slots=True)
class _Row:
    words: list[_Word]
    cells: list[_Cell] = field(default_factory=list)

    @property
    def y0(self) -> float:
        return min(word.y0 for word in self.words)

    @property
    def top(self) -> float:
        """Where the row's line begins: not moved by a cell set a little higher."""
        return statistics.median(word.y0 for word in self.words)

    @property
    def y1(self) -> float:
        return max(word.y1 for word in self.words)

    @property
    def height(self) -> float:
        return statistics.median(word.height for word in self.words)

    @property
    def text(self) -> str:
        return " ".join(cell.text for cell in self.cells)


@dataclass(slots=True, frozen=True)
class _Line:
    """A line of the text, and where on the page it begins."""

    text: str
    # None for a line placed by the file's order alone: rotated text, an
    # empty line, a page number written after its pair.
    top: float | None = None
    # Where the row the line stands in begins, and where the line ends.
    x0: float = 0.0
    x1: float = 0.0
    height: float = 0.0

    def runs_on_into(self, following: _Line) -> bool:
        """Whether *following* is the next line of this one's text block.

        Right below it, without an empty line's worth of space between
        (SDB-45), and beginning under its row: in its column, further in where
        a statement hangs its text beside its code ("EUH208- Enthält …
        2-Methyl-" over "2H-isothiazol-3-on"), or back at the code's column
        where it does not ("P101 Ist ärztlicher Rat …  Kenn-" over
        "zeichnungsetikett"). Only there does a word broken at the end of this
        line go on.
        """
        if self.top is None or following.top is None:
            return False
        height = max(self.height, following.height)
        return (
            0 < following.top - self.top <= (1 + _BLANK_GAP) * height
            and self.x0 - _COLUMN_SLACK <= following.x0 < self.x1
        )


@dataclass(slots=True)
class _Token:
    """A piece of a row's text, or the colon between a label and its value."""

    text: str
    x0: float
    x1: float


@dataclass(slots=True)
class _Pair:
    """A label and its value, as the rows of the form print them."""

    label: list[str]
    value: list[_Line]
    label_x: float
    top: float
    height: float
    # Where the label column ends (the colon) and the value column begins and
    # ends: the next pair of the row starts its own label column.
    separator_x: float
    value_x: float
    value_end: float
    # Page numbers set beside the pair, written after it.
    trailing: list[str] = field(default_factory=list)
    # A subsection heading with its content beside it (SDB-114): the heading
    # stays a line of its own, as where the content stands below it.
    heading: bool = False

    def lines(self) -> list[_Line]:
        label = _join_broken(self.label)
        if self.heading:
            return [
                _Line(label, self.top, self.label_x, self.separator_x, self.height),
                *self.value,
                *(_Line(text) for text in self.trailing),
            ]
        head = f"{label}:" if label else _COLON
        trailing = [_Line(text) for text in self.trailing]
        if not self.value:
            return [
                _Line(head, self.top, self.label_x, self.label_x, self.height),
                *trailing,
            ]
        first = self.value[0]
        return [
            _Line(
                f"{head} {first.text}", first.top, self.label_x, first.x1, first.height
            ),
            *self.value[1:],
            *trailing,
        ]


@dataclass(slots=True)
class _Pairs:
    """The pairs of one row, open for the rows below that continue them."""

    leading: _Line | None
    pairs: list[_Pair]
    last_top: float
    height: float
    # A footer row with a page number continues on the next page, if at all.
    open: bool
    # A pair of a form without colons (SDB-114). The two columns of such a
    # form are set apart from each other: the last line of a heading and the
    # value beside it can stand two points apart, and the row's middle then
    # lies lower than the heading's next line would.
    form: bool = False
    # Where the last line of a form's heading begins: a cell in its column
    # further down is the next label, not a further line of the heading.
    label_top: float = 0.0

    def lines(self) -> list[_Line]:
        lines = [self.leading] if self.leading else []
        for pair in self.pairs:
            lines.extend(pair.lines())
        return lines

    def continues(self, row: _Row) -> bool:
        """Take *row* as further lines of the pairs' labels and values, if it is."""
        if not self.open:
            return False
        # Below the pairs, in type of their size: a pictogram glyph split off
        # their row (_without_outsized) stands beside them, not under them.
        if row.top <= self.last_top or row.height > _HEIGHT_RATIO * self.height:
            return False
        top = row.y0 if self.form else row.top
        pitch = _FORM_PITCH if self.form else _CONTINUATION_PITCH
        if top - self.last_top > pitch * max(self.height, row.height):
            return False
        placed: list[tuple[_Pair, bool, _Cell]] = []
        for cell in row.cells:
            for pair in self.pairs:
                if pair.value_x - _COLUMN_SLACK <= cell.x0 < pair.value_end:
                    placed.append((pair, False, cell))
                    break
                if (
                    cell.x0 >= pair.label_x - _COLUMN_SLACK
                    and cell.x1 <= pair.separator_x
                ):
                    placed.append((pair, True, cell))
                    break
            else:
                return False
        if self.form and any(is_label for _, is_label, _ in placed):
            if top - self.label_top > pitch * max(self.height, row.height):
                return False
            self.label_top = top
        for pair in self.pairs:
            labels = [c.text for p, is_label, c in placed if p is pair and is_label]
            values = [c for p, is_label, c in placed if p is pair and not is_label]
            if labels:
                pair.label.append(" ".join(labels))
            if values:
                text = " ".join(c.text for c in values)
                pair.value.append(
                    _Line(text, row.top, row.cells[0].x0, values[-1].x1, row.height)
                )
        self.last_top = row.top
        return True


@dataclass(slots=True)
class _Table:
    """Rows of cells without a label:value pair: read in the file's order."""

    rows: list[_Row]

    def adjoins(self, row: _Row) -> bool:
        """Whether *row* stands right below the table, without an empty line."""
        return row.y0 - self.rows[-1].y1 <= _BLANK_GAP * row.height

    def fits(self, row: _Row) -> bool:
        """Whether a one-cell *row* is a further line of one of the table's columns.

        Only right below it: after an empty line's worth of space, a cell in
        one of its columns is the page number of the footer as often as it is
        a further line of the table.
        """
        if not self.adjoins(row):
            return False
        cell = row.cells[0]
        for column in self._columns():
            if (
                cell.x0 >= column[0] - _COLUMN_SLACK
                and cell.x1 <= column[1] + _COLUMN_SLACK
            ):
                return True
        return False

    def _columns(self) -> list[tuple[float, float]]:
        spans = sorted((c.x0, c.x1) for r in self.rows for c in r.cells)
        columns: list[tuple[float, float]] = []
        for x0, x1 in spans:
            if columns and x0 <= columns[-1][1]:
                columns[-1] = (columns[-1][0], max(columns[-1][1], x1))
            else:
                columns.append((x0, x1))
        return columns

    def lines(self) -> list[_Line]:
        """The table's lines in the file's order, each where the page prints it."""
        by_line: dict[tuple[int, int], list[_Word]] = {}
        row_start: dict[tuple[int, int], float] = {}
        for row in self.rows:
            for word in row.words:
                by_line.setdefault(word.order[:2], []).append(word)
                row_start.setdefault(word.order[:2], row.cells[0].x0)
        lines: list[_Line] = []
        for key, words in sorted(by_line.items()):
            words.sort(key=lambda w: w.order)
            lines.append(
                _Line(
                    " ".join(w.text for w in words),
                    statistics.median(w.y0 for w in words),
                    row_start[key],
                    words[-1].x1,
                    statistics.median(w.height for w in words),
                )
            )
        return lines


def page_text(page: pymupdf.Page, textpage: pymupdf.TextPage | None = None) -> str:
    """The text of *page* in the order it is printed.

    *textpage* is the page's text, extracted with FLAGS; a caller that also
    wants the plain text passes it to read the page once.
    """
    textpage = textpage or page.get_textpage(flags=FLAGS)
    directions = _Directions(page.get_text("dict", textpage=textpage)["blocks"])
    horizontal: list[_Word] = []
    rotated: dict[tuple[int, int], list[str]] = {}
    for x0, y0, x1, y1, text, block, line, number in page.get_text(
        "words", textpage=textpage
    ):
        dx, dy = directions.of(block, line, (x0 + x1) / 2, (y0 + y1) / 2)
        if dx < 1.0 - _SKEW or abs(dy) > _SKEW:
            # Rotated text, a margin note set vertically: kept, line by line in
            # the file's order, after the page.
            rotated.setdefault((block, line), []).append(text)
            continue
        horizontal.append(_Word(x0, y0, x1, y1, text, (block, line, number)))

    lines = _read_rows(_rows(horizontal), page.rect.width)
    lines.extend(_Line(" ".join(words)) for _, words in sorted(rotated.items()))
    return "\n".join(_with_breaks_kept(lines))


def _with_breaks_kept(lines: list[_Line]) -> list[str]:
    """The lines' text, an empty line after a hyphen that does not run on.

    The line join (SDB-32) joins a line ending in a hyphen to whatever line
    follows. That is the next line of the word only where it stands right
    below in the same column; elsewhere -- the next cell of a table in the
    file's order, a pair below a table, the page's end -- an empty line keeps
    them apart: "gewässergefähr-" / "H413: Kann für …" made "gewässergefährH413".
    """
    text: list[str] = []
    for index, line in enumerate(lines):
        text.append(line.text)
        following = lines[index + 1] if index + 1 < len(lines) else None
        if _BROKEN.search(line.text) and (
            following is None or (following.text and not line.runs_on_into(following))
        ):
            text.append("")
    return text


class _Directions:
    """The writing direction of each line, found by where its words stand.

    PyMuPDF numbers a word's line among every line of its block, but the
    "dict" output leaves out a line whose box is empty -- text set at zero
    height. Counting would then give the next line's direction, or none, so a
    word is matched to the line whose box holds it. A word in no line's box is
    on an empty line and reads as horizontal.
    """

    def __init__(self, blocks: Sequence[dict[str, object]]) -> None:
        self._lines: dict[int, list[tuple[tuple[float, ...], tuple[float, float]]]] = {}
        for block in blocks:
            number = block.get("number")
            lines = block.get("lines")
            if not isinstance(number, int) or not isinstance(lines, list):
                continue
            self._lines[number] = [
                (tuple(line["bbox"]), (line["dir"][0], line["dir"][1]))
                for line in lines
            ]

    def of(self, block: int, line: int, x: float, y: float) -> tuple[float, float]:
        lines = self._lines.get(block, [])
        candidates = ([lines[line]] if line < len(lines) else []) + lines
        for (x0, y0, x1, y1), direction in candidates:
            if x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1:
                return direction
        return (1.0, 0.0)


def _rows(words: list[_Word]) -> list[_Row]:
    """Group *words* into rows by their vertical centre, each read left to right."""
    clusters: list[list[_Word]] = []
    current: list[_Word] = []
    centre = 0.0
    for word in sorted(words, key=lambda w: (w.centre, w.x0)):
        if current and abs(word.centre - centre) <= _ROW_TOLERANCE * min(
            word.height, statistics.median(w.height for w in current)
        ):
            current.append(word)
            centre = sum(w.centre for w in current) / len(current)
            continue
        if current:
            clusters.append(current)
        current = [word]
        centre = word.centre
    if current:
        clusters.append(current)

    rows: list[_Row] = []
    for cluster in clusters:
        text, outsized = _without_outsized(cluster)
        for part in (text, outsized):
            if part:
                words_of_row = _joined_touching(
                    _without_doubles(sorted(part, key=lambda w: w.x0))
                )
                rows.append(_Row(words_of_row, _cells(words_of_row)))
    return rows


def _without_outsized(words: list[_Word]) -> tuple[list[_Word], list[_Word]]:
    """Split off the words more than _HEIGHT_RATIO times taller than the row's text.

    Taller only: a superscript stays in its row. The text's height is the
    median of the lower half, so two pictogram glyphs beside a two-word caption
    do not make the glyphs the norm.
    """
    heights = sorted(word.height for word in words)
    norm = statistics.median(heights[: (len(heights) + 1) // 2])
    text = [w for w in words if w.height <= _HEIGHT_RATIO * norm]
    return text, [w for w in words if w.height > _HEIGHT_RATIO * norm]


# Two pieces of a row end and begin at the same point when they are no
# further apart than this, as a share of their height. A space between words
# is 0.2 to 0.3 of the height (see _CELL_GAP); a narrow one after a colon
# still 0.03.
_TOUCHING = 0.01


def _joined_touching(words: list[_Word]) -> list[_Word]:
    """Join the pieces of a word the file draws apart (SDB-42).

    A file that sets single characters in another font draws a word in pieces:
    "24", ".0", "9", ".2025" for "24.09.2025", each piece a word of its own to
    PyMuPDF and not in the order the page shows. They stand where the page
    prints them, without a space between. The joined word takes the place in
    the file's order of its last piece.
    """
    joined: list[_Word] = []
    for word in words:
        if joined:
            previous = joined[-1]
            gap = word.x0 - previous.x1
            height = min(word.height, previous.height)
            # Drawn apart: in another line of the file. Words of one line
            # that touch are PyMuPDF's own division, at a space it found.
            if abs(gap) <= _TOUCHING * height and word.order[:2] != previous.order[:2]:
                joined[-1] = _Word(
                    previous.x0,
                    min(previous.y0, word.y0),
                    word.x1,
                    max(previous.y1, word.y1),
                    previous.text + word.text,
                    max(previous.order, word.order),
                )
                continue
        joined.append(word)
    return joined


def _without_doubles(words: list[_Word]) -> list[_Word]:
    """Drop a word printed twice on itself, the way some files fake bold type.

    On itself: the two boxes overlap by most of their width. Two dashes side by
    side ("- - -") are separate words, however narrow.
    """
    kept: list[_Word] = []
    for word in words:
        if any(
            other.text == word.text
            and abs(other.y0 - word.y0) < word.height / 2
            and min(other.x1, word.x1) - max(other.x0, word.x0)
            > 0.8 * min(other.x1 - other.x0, word.x1 - word.x0)
            for other in kept[-3:]
        ):
            continue
        kept.append(word)
    return kept


def _cells(words: list[_Word]) -> list[_Cell]:
    cells: list[_Cell] = []
    for word in words:
        if cells:
            previous = cells[-1].words[-1]
            gap = word.x0 - previous.x1
            if gap <= _CELL_GAP * min(word.height, previous.height):
                cells[-1].words.append(word)
                continue
        cells.append(_Cell([word]))
    return cells


def _tokens(row: _Row) -> list[_Token]:
    """The row as text and colons, each with the x where it begins and ends.

    A cell ending in a colon is a label only when the next cell is its value,
    one with no colon of its own: in a heading row over a row of values
    ("Überarbeitet am:", "SDB-Nummer:", "Datum der letzten Ausgabe: 15.10.2024")
    the next cell is another heading. Nor is a page number anybody's value:
    "Materialnummer:" in a page header has none, and "Seite 2 von 13" beside it
    is the page's. The label then ends where its last letter does, an average
    letter's width before the colon, so a line above can be matched to it.
    """
    tokens: list[_Token] = []
    cells = row.cells
    for index, cell in enumerate(cells):
        words = cell.words
        first = words[0]
        if first.text.startswith(_COLON):
            tokens.append(_Token(_COLON, first.x0, first.x0))
            rest = first.text[1:].strip()
            remainder = ([rest] if rest else []) + [w.text for w in words[1:]]
            if remainder:
                start = first.x0 if rest else words[1].x0
                tokens.append(_Token(" ".join(remainder), start, cell.x1))
            continue
        following = cells[index + 1].text if index + 1 < len(cells) else None
        if (
            cell.text.endswith(_COLON)
            and cell.text != _COLON
            and following is not None
            and _COLON not in following
            and not _NAMED_PAGE_NUMBER.fullmatch(following)
        ):
            last = words[-1]
            letter = (last.x1 - last.x0) / len(last.text)
            tokens.append(_Token(cell.text[:-1].rstrip(), cell.x0, cell.x1 - letter))
            tokens.append(_Token(_COLON, cell.x1, cell.x1))
            continue
        tokens.append(_Token(cell.text, cell.x0, cell.x1))
    return tokens


def _read_rows(rows: list[_Row], width: float) -> list[_Line]:
    lines: list[_Line] = []
    pairs: _Pairs | None = None
    table: _Table | None = None

    def close() -> None:
        nonlocal pairs, table
        if pairs is not None:
            lines.extend(pairs.lines())
            pairs = None
        if table is not None:
            lines.extend(table.lines())
            table = None

    above: _Row | None = None

    def begin(row: _Row) -> None:
        """Close what is open, and mark an empty line's worth of space above *row*."""
        close()
        if above is not None and row.y0 - above.y1 > _BLANK_GAP * row.height:
            lines.append(_Line(""))

    read = [(row, _tokens(row)) for row in rows]
    heads: dict[int, list[str]] = {}
    # Whether the page has shown itself to be a form without colons: a
    # subsection heading of section 1 with its content beside it.
    in_form = False
    for index, (row, tokens) in enumerate(read):
        colons = [i for i, token in enumerate(tokens) if token.text == _COLON]
        # A label whose value is not on its row, right beside a table: set
        # beside the middle of a value of several rows ("Sicherheitshinweise :"
        # between the lines of P101 on SAP's sheets), it belongs to the table.
        bare = colons == [len(tokens) - 1] and table is not None and table.adjoins(row)
        if colons and not bare:
            begin(row)
            pairs = _read_pairs(row, tokens, colons, heads)
            heads = {}
        elif (
            pairs is not None and not pairs.form and not colons and pairs.continues(row)
        ):
            # A further line of a label:value pair, whatever it says.
            pass
        elif not colons and (form := _form_pair(row, width, in_form)) is not None:
            # Before a continuation of a form's pair: "Telefon" beside its
            # number right below one is the next pair, not a further line of
            # that one's heading.
            begin(row)
            pairs = form
            in_form = True
            heads = {}
        elif pairs is not None and not colons and pairs.continues(row):
            pass
        elif (
            not colons
            and index + 1 < len(read)
            and (found := _label_heads(row, *read[index + 1])) is not None
        ):
            # The first lines of the labels of the row below: set to end on
            # the value's line, a label of two lines starts a row higher.
            heads = found
        elif bare or len(row.cells) > 1 or (table is not None and table.fits(row)):
            if table is None:
                begin(row)
                table = _Table([])
            table.rows.append(row)
        else:
            begin(row)
            lines.append(
                _Line(row.text, row.top, row.cells[0].x0, row.cells[-1].x1, row.height)
            )
        above = row
    close()
    return lines


def _form_pair(row: _Row, width: float, in_form: bool) -> _Pairs | None:
    """*row* as a pair of a form in two columns without colons (SDB-114).

    Only where the left cell says so itself: a numbered subsection heading of
    section 1, or, *in_form*, once the page has shown such a heading, a
    contact label. Any other row of several cells without a colon stays a
    table, whose cells cannot be told apart by position.

    And only where the value begins in the left half of a page *width* wide:
    on a page set in two columns of running text, what stands right of a
    heading is the other column, which begins at the middle.
    """
    if len(row.cells) < 2 or row.cells[1].x0 >= width / 2:
        return None
    # A colon anywhere in the row: the form prints them, and this row is
    # read by them or not at all ("1.4. Notrufnummer: +49 …" beside a remark).
    if any(_COLON in cell.text for cell in row.cells):
        return None
    left, *right = row.cells
    heading = _SECTION_ONE_HEADING.match(left.text) is not None
    if not heading and not (in_form and _CONTACT_LABEL.fullmatch(left.text)):
        return None
    value_x = right[0].x0
    pair = _Pair(
        label=[left.text],
        value=[
            _Line(
                " ".join(cell.text for cell in right),
                row.top,
                value_x,
                right[-1].x1,
                row.height,
            )
        ],
        label_x=left.x0,
        top=row.top,
        height=row.height,
        # A heading runs on below in its column; a contact label is one line,
        # and what stands under it is the next label.
        separator_x=value_x - _COLUMN_SLACK if heading else left.x0,
        value_x=value_x,
        value_end=float("inf"),
        heading=heading,
    )
    return _Pairs(
        leading=None,
        pairs=[pair],
        last_top=row.top,
        height=row.height,
        open=True,
        form=True,
        label_top=row.top,
    )


def _label_heads(
    above: _Row, row: _Row, tokens: list[_Token]
) -> dict[int, list[str]] | None:
    """The cells of *above* that begin the labels of *row*, by the label's colon.

    Only for a row of pairs right below in type of the same height, every pair
    with a value, and only cells that end where a label ends -- right-aligned
    labels of two lines: "Ausgabedatum/Überarbeitungsd" above "atum: 27.04.2020".
    None if any cell of *above* is not such a head.
    """
    if row.top - above.top > _CONTINUATION_PITCH * max(row.height, above.height):
        return None
    if abs(row.height - above.height) > _HEAD_SLACK * row.height:
        return None
    colons = [i for i, token in enumerate(tokens) if token.text == _COLON]
    if not colons or colons[0] == 0 or colons[-1] == len(tokens) - 1:
        return None
    heads: dict[int, list[str]] = {}
    for cell in above.cells:
        if cell.text.endswith(_COLON):
            return None
        left = float("-inf")
        for number, colon in enumerate(colons):
            label = tokens[colon - 1]
            # Right-aligned with the label's last letter, or with the colon
            # where the colon is the label's own ("atum:" under a line ending
            # exactly where the colon does).
            ends = [label.x1]
            if tokens[colon].x0 - label.x1 <= _HEAD_SLACK * 4 * row.height:
                ends.append(tokens[colon].x1)
            if (
                label.text != _COLON
                and cell.x0 >= left
                and any(abs(cell.x1 - end) <= _HEAD_SLACK * row.height for end in ends)
            ):
                heads.setdefault(colon, []).append(cell.text)
                break
            following = colons[number + 1] - 1 if number + 1 < len(colons) else None
            if following is not None and following > colon + 1:
                left = tokens[following - 1].x1
        else:
            return None
    return heads


def _read_pairs(
    row: _Row,
    tokens: list[_Token],
    colons: list[int],
    heads: dict[int, list[str]],
) -> _Pairs:
    """The row's pairs, open for the rows below.

    Text before the first label stands on its own; each colon takes the token
    before it as its label and what follows, up to the next label, as its value.
    *heads* are the first lines of labels, from the row above, by their colon.
    """
    first_label = colons[0] - 1
    leading = (
        _Line(
            " ".join(token.text for token in tokens[:first_label]),
            row.top,
            tokens[0].x0,
            tokens[first_label - 1].x1,
            row.height,
        )
        if first_label > 0
        else None
    )
    pairs: list[_Pair] = []
    has_page = False
    for number, colon in enumerate(colons):
        label_index = colon - 1
        label = tokens[label_index].text if label_index >= 0 else ""
        if label == _COLON:
            label = ""
        # "Telefon:" in one cell and ": 0221" in the next: one colon is enough.
        label = label.rstrip(_COLON).rstrip()
        end = colons[number + 1] - 1 if number + 1 < len(colons) else len(tokens)
        values = [t for t in tokens[colon + 1 : max(end, colon + 1)] if t.text]
        # A page number set in a cell of its own beside a footer pair is not
        # part of the value: on a line of its own, the statement texts read
        # past it as past any page number (SDB-27).
        page = [
            t
            for i, t in enumerate(values)
            if (_PAGE_NUMBER if i else _NAMED_PAGE_NUMBER).fullmatch(t.text)
        ]
        values = [t for t in values if t not in page]
        has_page = has_page or bool(page)
        next_label = tokens[end].x0 if end < len(tokens) else float("inf")
        pairs.append(
            _Pair(
                label=[*heads.get(colon, []), *([label] if label else [])],
                value=[
                    _Line(
                        " ".join(t.text for t in values),
                        row.top,
                        values[0].x0,
                        values[-1].x1,
                        row.height,
                    )
                ]
                if values
                else [],
                top=row.top,
                height=row.height,
                label_x=tokens[label_index].x0
                if label_index >= 0
                else tokens[colon].x0,
                separator_x=tokens[colon].x0,
                value_x=values[0].x0 if values else tokens[colon].x1,
                value_end=next_label - _COLUMN_SLACK,
                trailing=[t.text for t in page],
            )
        )
    return _Pairs(
        leading=leading,
        pairs=pairs,
        last_top=row.top,
        height=row.height,
        open=not has_page,
    )


def _join_broken(parts: list[str]) -> str:
    """Join the lines of a label, a word broken at a line end joined back (SDB-32)."""
    return join_broken_words("\n".join(parts)).replace("\n", " ")
