"""A record of ``read`` as a report for a person (SDW-37 to SDW-41).

``show`` reads a file exactly like ``read`` and words the same record: this
module looks at no PDF and no text, and judges nothing. Every label and
sentence comes from the message catalog; the sentences of the label and the
names a sheet prints stand as the sheet prints them. The text is for people
and may change with any release: a program takes the record itself.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from .messages import Catalog, Message

_INDENT = "  "
# Between the parts of one line: the signal word and the pictograms, and the
# columns of a file's line in a folder.
_BETWEEN = " · "
_SHEET = "safety-data-sheet"
# What the parser notes about a label that lacks one kind of statement. For a
# sheet that prints no label at all they only repeat that (SDW-38).
_REPEATS_NO_LABEL = frozenset({"no-hazard-codes", "no-precautionary-codes"})
_KINDS: Mapping[str, str] = {
    "safety-data-sheet-other-language": "show-kind-other-language",
    "safety-information": "show-kind-safety-information",
    "document": "show-kind-document",
}


def _say(catalog: Catalog, code: str, **params: Any) -> str:
    return catalog.render(Message(code, params))


def _one_line(text: str) -> str:
    """A value on one line: a name a sheet breaks over two lines is still one."""
    return " ".join(text.split())


def _stated(catalog: Catalog, value: Any) -> str:
    """A value as the sheet gives it, or the catalog's word for a missing one."""
    text = _one_line(str(value)) if value is not None else ""
    return text or _say(catalog, "show-not-stated")


def is_unreadable(record: Mapping[str, Any]) -> bool:
    """Whether no text could be read from the record's file (SDW-4)."""
    return "extraction" not in record


def is_sheet(record: Mapping[str, Any]) -> bool:
    """Whether the record is of a German safety data sheet that was read."""
    return "sheet" in record


def _kind(record: Mapping[str, Any], catalog: Catalog) -> str:
    """What the file is, in the catalog's words (SDW-8)."""
    if is_unreadable(record):
        return _say(catalog, "show-kind-unreadable")
    if is_sheet(record):
        return _say(catalog, "show-kind-sheet", sheets=record["sheet_count"])
    kind = record["verification"]["kind"]
    # A German sheet the parser was not run on does not occur; said as what
    # the verdict names it, should it ever.
    return _say(catalog, _KINDS.get(kind, "show-kind-document"))


def _sentences(
    messages: Sequence[Mapping[str, Any]], *, without: frozenset[str] = frozenset()
) -> Iterator[str]:
    """The sentences of *messages*, leaving out the codes in *without*."""
    for message in messages:
        if message["code"] not in without:
            yield _one_line(message["message"])


def _unlabelled(
    sheet: Mapping[str, Any], statements: Sequence[Mapping[str, Any]]
) -> bool:
    """Whether the sheet prints no label at all: no word, no sign, no statement."""
    labelling = sheet["hazard_statements"]
    return not (labelling["signal_word"] or labelling["pictograms"] or statements)


def _repeated(
    sheet: Mapping[str, Any], statements: Sequence[Mapping[str, Any]]
) -> frozenset[str]:
    """The parser's notes the report leaves out for this sheet, by code."""
    return _REPEATS_NO_LABEL if _unlabelled(sheet, statements) else frozenset()


def _unique(sentences: Iterator[str], seen: set[str]) -> list[str]:
    """The sentences not said before, in their order; *seen* grows by them."""
    fresh: list[str] = []
    for sentence in sentences:
        if sentence not in seen:
            seen.add(sentence)
            fresh.append(sentence)
    return fresh


def _reasons(record: Mapping[str, Any]) -> list[str]:
    """Why a file is no sheet that was read: the verdict's reasons (SDW-38)."""
    verification = record["verification"]

    def said() -> Iterator[str]:
        yield from _sentences(record["errors"])
        yield from _sentences(verification["errors"])
        yield from _sentences(record["findings"])

    reasons = _unique(said(), set())
    # A verdict that names no reason of its own gave its doubts as warnings.
    return reasons or _unique(_sentences(verification["warnings"]), set())


def _file_notes(record: Mapping[str, Any], seen: set[str]) -> list[str]:
    """What is noted about a sheet's file: findings first, then the reading."""

    def said() -> Iterator[str]:
        yield from _sentences(record["findings"])
        yield from _sentences(record["extraction"]["warnings"])
        yield from _sentences(
            record["parser"]["warnings"],
            without=_repeated(record["sheet"], record["statements"]),
        )

    return _unique(said(), seen)


def _part_notes(part: Mapping[str, Any]) -> list[str]:
    without = _repeated(part["sheet"], part["statements"])
    return _unique(_sentences(part["warnings"], without=without), set())


def _notes(record: Mapping[str, Any]) -> tuple[list[list[str]], list[str]]:
    """The notes of each sheet of a file of several, and those of the file.

    A sentence a sheet carries stands with every sheet that carries it, and
    not again with the file.
    """
    parts = [_part_notes(part) for part in record.get("parts", ())]
    return parts, _file_notes(record, {note for notes in parts for note in notes})


def notes_count(record: Mapping[str, Any]) -> int:
    """How many notes the full report of a sheet's file lists (SDW-40)."""
    parts, whole = _notes(record)
    return sum(len(notes) for notes in parts) + len(whole)


def _date(sheet: Mapping[str, Any], catalog: Catalog) -> tuple[str, str | None]:
    """The label and the date a sheet is dated by: revised, else issued."""
    if sheet["revision_date"]:
        return "show-label-revised", _say(
            catalog, "show-date", date=sheet["revision_date"]
        )
    if sheet["issue_date"]:
        return "show-label-issued", _say(catalog, "show-date", date=sheet["issue_date"])
    return "show-label-revised", None


def _sheet_block(
    sheet: Mapping[str, Any],
    statements: Sequence[Mapping[str, Any]],
    notes: list[str] | None,
    catalog: Catalog,
) -> list[str]:
    """One sheet: who and what, the label, whether it needs a sheet, the notes.

    *notes* None leaves the notes out: a sheet of several shows them only
    where it has some, the file as a whole always.
    """
    label_code, dated = _date(sheet, catalog)
    when = dated or _say(catalog, "show-not-stated")
    if sheet["version"]:
        when = _say(
            catalog,
            "show-with-version",
            value=when,
            version=_one_line(sheet["version"]),
        )
    contact = sheet["contact_info"]
    supplier = ", ".join(
        _one_line(part)
        for part in (contact["supplier_name"], contact["supplier_address"])
        if part
    )
    # The office that gives information, named as such, where the sheet
    # prints another address for it than the supplier's.
    office = contact["information_email"]
    if office and office == contact["supplier_email"]:
        office = None
    reached = ", ".join(
        part
        for part in (
            _one_line(contact["supplier_phone"] or ""),
            _one_line(contact["supplier_email"] or ""),
            _say(catalog, "show-information-email", email=_one_line(office))
            if office
            else "",
        )
        if part
    )
    labelling = sheet["hazard_statements"]
    # A sheet that prints no label at all says so in one word.
    unlabelled = _unlabelled(sheet, statements)
    head = (
        _say(catalog, "show-no-labelling")
        if unlabelled
        else _BETWEEN.join(
            (
                _one_line(labelling["signal_word"])
                if labelling["signal_word"]
                else _say(catalog, "show-no-signal-word"),
                ", ".join(labelling["pictograms"])
                if labelling["pictograms"]
                else _say(catalog, "show-no-pictograms"),
            )
        )
    )
    rows = (
        ("show-label-product", _stated(catalog, sheet["product_identifier"])),
        ("show-label-supplier", _stated(catalog, supplier or None)),
        ("show-label-contact", _stated(catalog, reached or None)),
        ("show-label-emergency", _stated(catalog, contact["emergency_phone"])),
        (label_code, when),
        ("show-label-labelling", head),
    )
    labels = [_say(catalog, code) for code, _ in rows]
    width = max(len(label) for label in labels) + 2
    lines = [
        f"{label:<{width}}{value}"
        for label, (_, value) in zip(labels, rows, strict=True)
    ]
    # The label stands apart from who and what, as on the sheet.
    lines.insert(len(rows) - 1, "")
    for statement in statements:
        # The sheet's wording; a code it prints without one is said in the
        # regulation's, and stands alone where that has none either.
        wording = statement["sheet"] or statement["regulation"]
        text = f"{statement['code']}  {_one_line(wording)}" if wording else None
        lines.append(_INDENT + (text or statement["code"]))
    if not statements and not unlabelled:
        lines.append(_INDENT + _say(catalog, "show-no-statements"))
    lines.append("")
    lines.append(
        _say(
            catalog,
            "show-needs-sheet" if sheet["sheet_required"] else "show-needs-no-sheet",
        )
    )
    if sheet["stated_voluntary"]:
        lines.append(_INDENT + _say(catalog, "show-stated-voluntary"))
    if sheet["stated_article"]:
        lines.append(_INDENT + _say(catalog, "show-stated-article"))
    if notes is not None:
        lines.append("")
        lines.extend(_notes_block(notes, catalog))
    return lines


def _notes_block(notes: list[str], catalog: Catalog) -> list[str]:
    listed = notes or [_say(catalog, "show-no-notes")]
    return [
        _say(catalog, "show-label-notes"),
        *(f"{_INDENT}- {note}" for note in listed),
    ]


def _indented(lines: Sequence[str], depth: int) -> list[str]:
    return [(_INDENT * depth + line) if line else "" for line in lines]


def report(record: Mapping[str, Any], name: str, catalog: Catalog) -> list[str]:
    """The full report of one file, as lines (SDW-38, SDW-39)."""
    lines = [name, _INDENT + _kind(record, catalog)]
    if not is_sheet(record):
        lines.extend(f"{_INDENT * 2}- {reason}" for reason in _reasons(record))
        return lines
    cover = _cover(record, catalog, short=False)
    if cover:
        lines.append(_INDENT + cover)
    part_notes, whole = _notes(record)
    parts = record.get("parts", ())
    if not parts:
        lines.append("")
        lines.extend(
            _indented(
                _sheet_block(record["sheet"], record["statements"], whole, catalog), 1
            )
        )
        return lines
    for number, (part, notes) in enumerate(
        zip(parts, part_notes, strict=True), start=1
    ):
        lines.append("")
        lines.append(
            _INDENT + _say(catalog, "show-sheet-of", number=number, count=len(parts))
        )
        lines.extend(
            _indented(
                _sheet_block(part["sheet"], part["statements"], notes or None, catalog),
                2,
            )
        )
    # What holds for the file: the sheets united need a sheet where one of
    # them does, and the findings compare them with one another.
    lines.append("")
    lines.append(_INDENT + _say(catalog, "show-whole-file"))
    needs = record["sheet"]["sheet_required"]
    lines.append(
        _INDENT * 2
        + _say(catalog, "show-needs-sheet" if needs else "show-needs-no-sheet")
    )
    lines.append("")
    lines.extend(_indented(_notes_block(whole, catalog), 2))
    return lines


def _cover(record: Mapping[str, Any], catalog: Catalog, *, short: bool) -> str | None:
    """What stands in front of a file's sheets, as a sentence or in a line."""
    if not record["cover_page"]:
        return None
    term = record["display_term"]
    if term:
        return _say(
            catalog,
            "show-line-cover-page-display" if short else "show-cover-page-display",
            term=_one_line(term),
        )
    return _say(catalog, "show-line-cover-page" if short else "show-cover-page")


def _product_and_date(sheet: Mapping[str, Any], catalog: Catalog) -> tuple[str, str]:
    """A sheet's product and date for a line; the catalog's words where missing."""
    _, dated = _date(sheet, catalog)
    product = sheet["product_identifier"]
    return (
        _one_line(product) if product else _say(catalog, "show-no-product"),
        dated or _say(catalog, "show-undated"),
    )


def line(record: Mapping[str, Any], name: str, catalog: Catalog) -> str:
    """One file of a folder on one line (SDW-40)."""
    kind = _kind(record, catalog)
    if not is_sheet(record):
        return f"{name}: {kind}"
    parts = record.get("parts", ())
    if parts:
        # Every sheet of the file, in its order: the first alone would hide
        # that a file holds the sheets of different products.
        sheets = "; ".join(
            _say(catalog, "show-product-dated", product=product, dated=dated)
            for product, dated in (
                _product_and_date(part["sheet"], catalog) for part in parts
            )
        )
        columns = [kind, _cover(record, catalog, short=True), sheets]
    else:
        columns = [kind, *_product_and_date(record["sheet"], catalog)]
    columns.append(_say(catalog, "show-notes", notes=notes_count(record)))
    return f"{name}: " + _BETWEEN.join(column for column in columns if column)


def broke(name: str, catalog: Catalog, *, full: bool) -> list[str]:
    """A file whose reading broke: it has no record, and is named all the same."""
    said = _say(catalog, "show-kind-broke")
    return [name, _INDENT + said] if full else [f"{name}: {said}"]
