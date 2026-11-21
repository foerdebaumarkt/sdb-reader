"""Set two runs beside each other and say where they differ (SDW-27, SDW-28).

A run is what ``read`` or ``ask`` wrote: a record per file. Two readings of
one parser show what a change to it does; a reading and a model's answers
show where to look for a reading error; two models' answers show how far a
model is to be trusted. Nothing here reads a PDF or asks anybody.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import HazardStatements
from .statements import _comparable, label_statements

# What two readings are compared in: every field of a reading that can differ.
READ_FIELDS = (
    "kind",
    "stated_classification",
    "stated_voluntary",
    "stated_article",
    "sheet_required",
    "countries",
    "signal_word",
    "pictograms",
    "hazard_codes",
    "precautionary_codes",
    "supplemental_codes",
    "hazard_text",
    "precautionary_text",
    "supplemental_text",
    "revision_date",
    "issue_date",
    "version",
    "product_identifier",
    "supplier_name",
    "supplier_address",
    "supplier_phone",
    "supplier_email",
    "supplier_website",
    "information_email",
    "emergency_phone",
    "findings",
    "embedded_differences",
    "errors",
)
# What a model is asked for, and so what a comparison with one looks at.
MODEL_FIELDS = (
    "hazard_codes",
    "precautionary_codes",
    "supplemental_codes",
    "wording",
    "supplier_name",
    "supplier_email",
    "revision_date",
)

READ = "read"
ASK = "ask"


class DiffError(Exception):
    """A run cannot be read, or the two cannot be matched."""


@dataclass(frozen=True, slots=True)
class Run:
    """The records of one run, by what identifies a file."""

    path: Path
    # "read" or "ask".
    kind: str
    records: Mapping[str, Mapping[str, Any]]
    stages: frozenset[str]
    models: frozenset[str]
    questions: frozenset[str]


def load(path: Path, *, by_name: bool) -> Run:
    """The run in *path*: a JSON Lines file or one JSON list.

    Where a file has several records, the last holds (SDW-22). With
    *by_name* files are known by their name, otherwise by their path.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DiffError(f"cannot read {path}: {exc}") from exc
    try:
        if text.lstrip().startswith("["):
            rows = json.loads(text)
        else:
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    except ValueError as exc:
        raise DiffError(f"{path} is neither JSON Lines nor a JSON list: {exc}") from exc

    records: dict[str, Mapping[str, Any]] = {}
    names: Counter[str] = Counter()
    kinds: set[str] = set()
    paths: dict[str, str] = {}
    for row in rows:
        try:
            location = row["file"]
            key = location["filename"] if by_name else location["path"]
            kinds.add(_kind_of(row))
        except (KeyError, TypeError) as exc:
            raise DiffError(
                f"{path} holds a record that is not one of read or ask"
            ) from exc
        if by_name and paths.get(key, location["path"]) != location["path"]:
            names[key] += 1
        paths[key] = location["path"]
        records[key] = row
    if names:
        raise DiffError(
            f"{path} holds {len(names)} file name(s) under several paths; "
            "they cannot be matched by name"
        )
    if len(kinds) > 1:
        raise DiffError(f"{path} mixes records of read and of ask")
    if not records:
        raise DiffError(f"{path} holds no record")
    asked = [row for row in records.values() if row.get("asked")]
    return Run(
        path,
        kinds.pop(),
        records,
        frozenset(_stage_of(row) for row in records.values()) - {""},
        frozenset(str(row["model"]) for row in asked),
        frozenset(str(row["question"]) for row in asked),
    )


def _kind_of(record: Mapping[str, Any]) -> str:
    if "asked" in record:
        return ASK
    if "verification" in record:
        return READ
    raise KeyError("verification")


def _stage_of(record: Mapping[str, Any]) -> str:
    """The reading stage a record's text came from, where the record says."""
    extraction = record.get("extraction")
    named = record.get("stage") or (
        extraction.get("stage") if isinstance(extraction, Mapping) else None
    )
    return str(named or "")


@dataclass(frozen=True, slots=True)
class FieldDifference:
    """One field in which the two records of a file differ."""

    field: str
    a: Any
    b: Any
    # The statement, where the field is a wording.
    code: str | None = None

    @property
    def how(self) -> str:
        if self.a is None:
            return "gained"
        return "lost" if self.b is None else "changed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            **({"code": self.code} if self.code else {}),
            "a": self.a,
            "b": self.b,
        }


@dataclass(slots=True)
class FieldCount:
    """How many files differ in one field, shown and only counted."""

    shown: Counter[str] = field(default_factory=Counter)
    counted_only: Counter[str] = field(default_factory=Counter)
    examples: list[tuple[str, FieldDifference]] = field(default_factory=list)


@dataclass(slots=True)
class Result:
    """What setting two runs beside each other gave."""

    a: Run
    b: Run
    fields: dict[str, FieldCount]
    both: int = 0
    only_a: int = 0
    only_b: int = 0
    # Files in both of which one record holds no reading to compare.
    not_compared: int = 0
    differing: int = 0
    differing_counted_only: int = 0
    # Every differing file that may be shown, with its differences.
    details: list[tuple[str, list[FieldDifference]]] = field(default_factory=list)

    @property
    def differs(self) -> bool:
        return bool(self.differing or self.differing_counted_only)


def compare_runs(
    a: Run, b: Run, *, count_only: frozenset[str] = frozenset(), examples: int = 3
) -> Result:
    """Where the records of *a* and *b* differ, file by file (SDW-27).

    A file one of *count_only*'s lines names is counted in a group of its
    own and is in no example and no detail (SDW-28).
    """
    with_model = ASK in (a.kind, b.kind)
    names = MODEL_FIELDS if with_model else READ_FIELDS
    result = Result(a, b, {name: FieldCount() for name in names})
    result.only_a = len(a.records.keys() - b.records.keys())
    result.only_b = len(b.records.keys() - a.records.keys())
    for key in sorted(a.records.keys() & b.records.keys()):
        result.both += 1
        one, other = a.records[key], b.records[key]
        if with_model:
            if not (_has_reading(one) and _has_reading(other)):
                result.not_compared += 1
                continue
            found = model_differences(one, other)
        else:
            found = read_differences(one, other)
        if not found:
            continue
        hidden = _is_named(one["file"], count_only)
        if hidden:
            result.differing_counted_only += 1
        else:
            result.differing += 1
            result.details.append((str(one["file"]["path"]), found))
        seen: set[str] = set()
        for difference in found:
            count = result.fields[difference.field]
            # A file counts once per field, however many statements differ.
            if difference.field not in seen:
                seen.add(difference.field)
                (count.counted_only if hidden else count.shown)[difference.how] += 1
            if not hidden and len(count.examples) < examples:
                count.examples.append((str(one["file"]["path"]), difference))
    return result


def _is_named(location: Mapping[str, Any], lines: frozenset[str]) -> bool:
    """Whether a line names the file: its name, its path, or the end of its path."""
    if not lines:
        return False
    path = str(location["path"])
    if location["filename"] in lines or path in lines:
        return True
    posix = path.replace("\\", "/")
    return any(posix.endswith("/" + line.lstrip("/")) for line in lines)


def _has_reading(record: Mapping[str, Any]) -> bool:
    return isinstance(record.get("sheet") or record.get("reading"), Mapping)


# ---------------------------------------------------------------------------
# Two readings
# ---------------------------------------------------------------------------


def read_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    """The compared fields of a ``read`` record; a field without a value is absent."""
    verification = record.get("verification") or {}
    out: dict[str, Any] = {"kind": verification.get("kind")}
    sheet = record.get("sheet")
    if isinstance(sheet, Mapping):
        label = sheet.get("hazard_statements") or {}
        contact = sheet.get("contact_info") or {}
        for name in (
            "stated_classification",
            "stated_voluntary",
            "stated_article",
            "sheet_required",
            "countries",
            "revision_date",
            "issue_date",
            "version",
            "product_identifier",
        ):
            out[name] = sheet.get(name)
        for name in (
            "signal_word",
            "pictograms",
            "hazard_codes",
            "precautionary_codes",
            "supplemental_codes",
            "hazard_text",
            "precautionary_text",
            "supplemental_text",
        ):
            out[name] = label.get(name)
        for name in (
            "supplier_name",
            "supplier_address",
            "supplier_phone",
            "supplier_email",
            "supplier_website",
            "information_email",
            "emergency_phone",
        ):
            out[name] = contact.get(name)
    out["findings"] = sorted({_code(f) for f in record.get("findings") or []})
    out["errors"] = sorted({_code(e) for e in record.get("errors") or []})
    embedded = record.get("embedded_data")
    # Compared only for a German sheet; an empty list then says they agree.
    if isinstance(embedded, Mapping) and embedded.get("compared"):
        out["embedded_differences"] = sorted(
            str(d.get("field")) for d in embedded.get("differences") or []
        )
    return {key: value for key, value in out.items() if value not in (None, [], "")}


def _code(message: Any) -> str:
    return str(message.get("code")) if isinstance(message, Mapping) else str(message)


def read_differences(
    a: Mapping[str, Any], b: Mapping[str, Any]
) -> list[FieldDifference]:
    """The fields in which two ``read`` records of one file differ."""
    one, other = read_fields(a), read_fields(b)
    return [
        FieldDifference(name, one.get(name), other.get(name))
        for name in READ_FIELDS
        if one.get(name) != other.get(name)
    ]


# ---------------------------------------------------------------------------
# A reading and a model's answer, or two answers
# ---------------------------------------------------------------------------


def _reading_of(record: Mapping[str, Any]) -> Mapping[str, Any]:
    reading = record.get("sheet") or record.get("reading") or {}
    return reading if isinstance(reading, Mapping) else {}


def _label(record: Mapping[str, Any]) -> Mapping[str, Any]:
    label = _reading_of(record).get("hazard_statements") or {}
    return label if isinstance(label, Mapping) else {}


def _wordings(record: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """Per code as printed, its wordings by what identifies them (SDW-27)."""
    if "asked" in record:
        label = _label(record)
        pairs: Iterable[tuple[str, str | None]] = (
            (s.code, s.sheet)
            for s in label_statements(
                HazardStatements(
                    hazard_codes=list(label.get("hazard_codes") or []),
                    precautionary_codes=list(label.get("precautionary_codes") or []),
                    supplemental_codes=list(label.get("supplemental_codes") or []),
                    hazard_text=label.get("hazard_text"),
                    precautionary_text=label.get("precautionary_text"),
                    supplemental_text=label.get("supplemental_text"),
                )
            )
        )
    else:
        # A reading names its statements itself, as its reader made them out.
        pairs = (
            (str(s.get("code")), s.get("sheet")) for s in record.get("statements") or []
        )
    worded: dict[str, dict[str, str]] = {}
    for code, wording in pairs:
        if wording and _comparable(wording):
            worded.setdefault(code, {})[_comparable(wording)] = wording
    return worded


def _parts(codes: Any) -> set[str]:
    """Each code of a joined one on its own: "P305+P351" is P305 and P351."""
    return {
        part.strip()
        for code in codes or []
        for part in str(code).split("+")
        if part.strip()
    }


def _folded(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def model_differences(
    a: Mapping[str, Any], b: Mapping[str, Any]
) -> list[FieldDifference]:
    """Where two records differ in what a model is asked for (SDW-27).

    The codes of the statements, a joined code as its parts; the wording per
    code both name; the supplier's name and e-mail; the date of revision. A
    model that names no date has said nothing about the one a reading holds:
    that is a difference only between two models.
    """
    found: list[FieldDifference] = []
    for name in ("hazard_codes", "precautionary_codes", "supplemental_codes"):
        one, other = _parts(_label(a).get(name)), _parts(_label(b).get(name))
        if one != other:
            found.append(
                FieldDifference(name, sorted(one) or None, sorted(other) or None)
            )

    ours, theirs = _wordings(a), _wordings(b)
    for code in sorted(ours.keys() & theirs.keys()):
        if not ours[code].keys() & theirs[code].keys():
            found.append(
                FieldDifference(
                    "wording",
                    sorted(ours[code].values()),
                    sorted(theirs[code].values()),
                    code=code,
                )
            )

    contact_a = _reading_of(a).get("contact_info") or {}
    contact_b = _reading_of(b).get("contact_info") or {}
    for name in ("supplier_name", "supplier_email"):
        one_text, other_text = contact_a.get(name), contact_b.get(name)
        if _folded(one_text) != _folded(other_text):
            found.append(FieldDifference(name, one_text or None, other_text or None))

    date_a, date_b = (
        _reading_of(a).get("revision_date"),
        _reading_of(b).get("revision_date"),
    )
    silent_model = ("asked" in a and not date_a and "asked" not in b) or (
        "asked" in b and not date_b and "asked" not in a
    )
    if date_a != date_b and not silent_model:
        found.append(FieldDifference("revision_date", date_a or None, date_b or None))
    return found


# ---------------------------------------------------------------------------
# What the comparison says
# ---------------------------------------------------------------------------


def to_json(result: Result) -> dict[str, Any]:
    """The comparison for a program."""
    return {
        "a": _run_to_json(result.a),
        "b": _run_to_json(result.b),
        "files": {
            "both": result.both,
            "only_a": result.only_a,
            "only_b": result.only_b,
            "not_compared": result.not_compared,
            "differing": result.differing,
            "differing_counted_only": result.differing_counted_only,
        },
        "fields": {
            name: {
                **_hows(count.shown),
                "counted_only": _hows(count.counted_only),
                "examples": [
                    {"file": path, **difference.to_dict()}
                    for path, difference in count.examples
                ],
            }
            for name, count in result.fields.items()
            if count.shown or count.counted_only
        },
    }


def _run_to_json(run: Run) -> dict[str, Any]:
    return {
        "path": str(run.path),
        "kind": run.kind,
        "files": len(run.records),
        "stages": sorted(run.stages),
        "models": sorted(run.models),
    }


def _hows(counts: Counter[str]) -> dict[str, int]:
    return {how: counts[how] for how in ("gained", "lost", "changed")}


def detail_lines(result: Result) -> Sequence[str]:
    """Every differing file that may be shown, a JSON line each."""
    return [
        json.dumps(
            {"file": path, "differences": [d.to_dict() for d in differences]},
            ensure_ascii=False,
        )
        for path, differences in result.details
    ]


def count_only_lines(path: Path | None) -> frozenset[str]:
    """The lines of a list of files that are only counted (SDW-28)."""
    if path is None:
        return frozenset()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DiffError(f"cannot read {path}: {exc}") from exc
    return frozenset(
        stripped
        for line in text.splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#")
    )
