"""What the library notes about a file, as codes; the sentences come from catalogs.

Every warning, every reason a file could not be read and every finding is a
``Message``: a fixed code and named values (BIB-10). A program decides by the
code, which is the same in every language; the sentence a person reads is
looked up in a catalog, one text file per language (BIB-11). Nothing in the
library reads a sentence back (BIB-12).
"""

from __future__ import annotations

import string
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

# Every code and the names of its values. A code never changes its meaning,
# and one that goes is not given out again (BIB-10): the codes that have gone
# are listed in tests/test_messages.py, which refuses one that comes back.
MESSAGE_CODES: Mapping[str, tuple[str, ...]] = {
    # Reading the text of a PDF.
    "read-by-ocr-no-text-layer": (),
    "read-by-ocr-single-characters": (),
    "pages-read-by-ocr": ("pages",),
    "short-text": (),
    # Why no text could be read.
    "pdf-not-found": (),
    "pdf-too-large": ("size_bytes", "limit_bytes"),
    "pdf-unreadable": ("detail",),
    "no-text-layer": ("pages",),
    "no-text": ("pages", "extractor"),
    "ocr-unavailable": (),
    "ocr-too-old": ("version", "minimum"),
    "ocr-language-missing": ("language",),
    "ocr-timeout": (),
    "ocr-failed": ("detail",),
    # Judging what kind of document the text is.
    "no-title-keywords": (),
    "no-section-marker": (),
    "no-regulation-reference": (),
    "no-hazard-codes-in-text": (),
    "short-sample": (),
    "safety-information": ("sections",),
    "leaflet-title": (),
    "other-language": (),
    "cover-only": (),
    "title-in-running-text": (),
    "no-safety-data-sheet": (),
    # The reading as a whole.
    "not-a-sheet": (),
    "unreadable": (),
    # Parsing the sheet.
    "line-too-long": ("count", "length"),
    "no-label-section": (),
    "several-sheets": ("count",),
    "classified-before-clp": ("basis",),
    "label-before-clp": (),
    "no-hazard-codes": (),
    "label-undetermined": (),
    "no-precautionary-codes": (),
    "euh-wording-outside-label": ("statement", "sentence"),
    "signal-word-not-taken": ("signal_word",),
    "pictograms-derived": ("pictograms",),
    "precautionary-wording-unclear": ("codes",),
    "label-line-unassigned": ("line",),
    "statement-too-long": ("codes",),
    "signal-word-derived": (),
    "no-identification-section": (),
    "no-supplier-name": (),
    "no-supplier-address": (),
    "no-supplier-phone": (),
    "no-emergency-phone": (),
    # Findings: what is wrong with the sheet as a document.
    "wording-deviates": ("statement", "sheet", "regulation"),
    "undated": (),
    "predates-annex-ii": ("revised",),
    "revised-in-future": ("revised", "today"),
    "classification-undetermined": (),
    "old-classification": (),
    "old-format": ("revised",),
    "classification-not-stated": (),
    "classification-contradicts-label": (),
    "label-not-found": (),
    "label-without-hazard-statement": (),
    "hazard-statement-not-in-label": ("statement",),
    "label-without-precautionary-statement": (),
    "different-products": ("products",),
    "country-editions-differ": ("fields",),
    "euh-outside-label": ("statement", "sentence"),
    "not-german": (),
    # The eSDScom file embedded in a PDF.
    "embedded-too-large": ("limit_bytes",),
    "embedded-doctype": (),
    "embedded-not-xml": ("detail",),
    "embedded-wrong-root": ("root",),
    "embedded-no-datasheet": (),
    # Asking a language model (ask).
    "model-http-error": ("status",),
    "model-unreachable": ("reason",),
    "model-reply-not-json": (),
    "model-reply-without-message": (),
    "model-reply-empty": (),
    "model-answer-unreadable": ("detail",),
    "model-not-asked": (),
    # What the command line says on stderr.
    "cli-file-failed": ("path", "reason"),
    "cli-file-broke": ("path", "error"),
    "cli-no-embedded-file": ("path",),
    "cli-embedded-not-handed-out": ("path", "filename", "reason"),
    "cli-saved": ("path", "target"),
    "cli-half-line-removed": ("output",),
    "cli-progress": ("done", "total", "failed"),
    "cli-interrupted": ("done", "total"),
    "cli-summary-read": ("files", "skipped", "excluded", "failed"),
    "cli-summary-ask": (
        "files",
        "skipped",
        "excluded",
        "asked",
        "failed",
        "prompt_tokens",
        "completion_tokens",
    ),
    # What diff says about two runs.
    "diff-run": ("side", "path", "kind", "files"),
    "diff-files": ("both", "only_a", "only_b", "not_compared"),
    "diff-differing": ("differing", "counted_only"),
    "diff-none": (),
    "diff-field": ("field", "gained", "lost", "changed"),
    "diff-field-counted-only": ("field", "gained", "lost", "changed"),
    "diff-stages-differ": ("a", "b"),
    "diff-models-differ": ("a", "b"),
    "diff-questions-differ": ("a", "b"),
    # The report of show: its labels, what a file is, and its closing line.
    "show-kind-sheet": ("sheets",),
    "show-kind-other-language": (),
    "show-kind-safety-information": (),
    "show-kind-document": (),
    "show-kind-unreadable": (),
    "show-kind-broke": (),
    "show-cover-page": (),
    "show-cover-page-display": ("term",),
    "show-line-cover-page": (),
    "show-line-cover-page-display": ("term",),
    "show-sheet-of": ("number", "count"),
    "show-whole-file": (),
    "show-label-product": (),
    "show-label-supplier": (),
    "show-label-contact": (),
    "show-label-emergency": (),
    "show-label-revised": (),
    "show-label-issued": (),
    "show-label-labelling": (),
    "show-label-notes": (),
    "show-date": ("date",),
    "show-information-email": ("email",),
    "show-product-dated": ("product", "dated"),
    "show-with-version": ("value", "version"),
    "show-not-stated": (),
    "show-no-labelling": (),
    "show-no-signal-word": (),
    "show-no-pictograms": (),
    "show-no-statements": (),
    "show-needs-sheet": (),
    "show-needs-no-sheet": (),
    "show-stated-voluntary": (),
    "show-stated-article": (),
    "show-no-notes": (),
    "show-no-product": (),
    "show-undated": (),
    "show-notes": ("notes",),
    "show-summary": ("files", "sheets", "others", "failed", "with_notes", "excluded"),
    "show-interrupted": ("done", "total"),
    # A warning kept from before messages had codes, as it was written.
    "unknown": ("text",),
}

# The values that count something: a catalog may give such a message one
# sentence for exactly one and another for any other number (BIB-11).
MESSAGE_COUNTS: Mapping[str, str] = {
    "pages-read-by-ocr": "pages",
    "no-text-layer": "pages",
    "no-text": "pages",
    "safety-information": "sections",
    "several-sheets": "count",
    "show-kind-sheet": "sheets",
    "show-notes": "notes",
}
# The values that are dates. A message carries them in ISO form; a sentence
# shows them the way its catalog writes dates (BIB-10, BIB-11).
MESSAGE_DATES: Mapping[str, tuple[str, ...]] = {
    "predates-annex-ii": ("revised",),
    "revised-in-future": ("revised", "today"),
    "old-format": ("revised",),
    "show-date": ("date",),
}

DEFAULT_LANGUAGE = "de"
_FALLBACK_LANGUAGE = "en"


@dataclass(frozen=True, slots=True)
class Message:
    """One thing the library notes about a file: a code and its values.

    The code is one of ``MESSAGE_CODES``; *params* holds exactly the values
    that code names, in types that can be written as JSON. A message carries
    no sentence: ``Catalog.render`` gives one in the language asked for.

    >>> message = Message("pictograms-derived", {"pictograms": ["GHS07"]})
    >>> shipped_catalog("en").render(message)
    'Pictograms derived from the H statements, the sheet names none: GHS07'
    >>> shipped_catalog("de").render(message)
    'Piktogramme aus den H-Sätzen abgeleitet, das Blatt nennt keine: GHS07'
    """

    code: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        names = MESSAGE_CODES.get(self.code)
        if names is None:
            raise ValueError(f"unknown message code: {self.code!r}")
        if set(self.params) != set(names):
            raise ValueError(
                f"message {self.code!r} takes {sorted(names)}, got {sorted(self.params)}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Code and values, without a sentence: the form to store."""
        return {"code": self.code, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, stored: Mapping[str, Any]) -> Message:
        """Read back what ``to_dict`` gave."""
        return cls(stored["code"], dict(stored.get("params") or {}))


_ISO_DATE = "%Y-%m-%d"


@dataclass(frozen=True, slots=True)
class Catalog:
    """The sentences of one language, by message code (BIB-11).

    A sentence is a string with ``{name}`` for each value, or, for a message
    that counts something, two of them: ``one`` for exactly one and ``other``
    for any other number. *date_format* says how the catalog writes a date
    (``strftime``); a message itself always carries dates in ISO form.

    >>> german = shipped_catalog("de")
    >>> german.render(Message("no-text-layer", {"pages": 1}))
    'Das PDF hat keine Textschicht (1 Seite angesehen).'
    >>> german.render(Message("no-text-layer", {"pages": 3}))
    'Das PDF hat keine Textschicht (3 Seiten angesehen).'
    >>> german.render(Message("predates-annex-ii", {"revised": "2019-05-02"}))[:27]
    'Überarbeitet am 02.05.2019,'
    """

    language: str
    sentences: Mapping[str, str | Mapping[str, str]]
    date_format: str = _ISO_DATE

    def render(self, message: Message) -> str:
        """The sentence for *message*.

        A code this catalog lacks is said in English: a caller's own catalog
        need not be complete.
        """
        entry = self.sentences.get(message.code)
        if entry is None:
            return shipped_catalog(_FALLBACK_LANGUAGE).render(message)
        if not isinstance(entry, str):
            counted = message.params.get(MESSAGE_COUNTS[message.code])
            entry = entry["one"] if counted == 1 and "one" in entry else entry["other"]
        dates = MESSAGE_DATES.get(message.code, ())
        return entry.format(
            **{
                name: self._date(value) if name in dates else _shown(value)
                for name, value in message.params.items()
            }
        )

    def _date(self, value: Any) -> str:
        """An ISO date as this catalog writes dates; anything else as it is."""
        try:
            return date.fromisoformat(str(value)).strftime(self.date_format)
        except ValueError:
            return _shown(value)

    def to_dict(self, message: Message) -> dict[str, Any]:
        """Code, values and sentence: the form the command prints (SDW-17)."""
        return {**message.to_dict(), "message": self.render(message)}


def shipped_languages() -> tuple[str, ...]:
    """The languages a catalog ships for."""
    return tuple(
        sorted(
            entry.name.removesuffix(".toml")
            for entry in _catalog_directory().iterdir()
            if entry.name.endswith(".toml")
        )
    )


@cache
def shipped_catalog(language: str = DEFAULT_LANGUAGE) -> Catalog:
    """The catalog the package ships for *language*; German unless asked.

    The language is always named by the caller and never taken from the
    machine, so the same file gives the same output everywhere. Raises
    ValueError for a language no catalog ships for.
    """
    if language not in shipped_languages():
        raise ValueError(
            f"no message catalog for {language!r}; shipped: "
            f"{', '.join(shipped_languages())}"
        )
    text = _catalog_directory().joinpath(f"{language}.toml").read_text("utf-8")
    return _catalog(language, text, f"{language}.toml")


def load_catalog(path: Path) -> Catalog:
    """A caller's own catalog: a TOML file like the shipped ones.

    It may hold fewer codes than there are; the rest are said in English. A
    code or a placeholder the library does not know is refused, since nobody
    would ever see that sentence.
    """
    return _catalog(path.stem, path.read_text("utf-8"), str(path))


def _catalog_directory() -> resources.abc.Traversable:
    return resources.files("sdb_reader").joinpath("messages_data")


def _catalog(language: str, text: str, source: str) -> Catalog:
    data = tomllib.loads(text)
    sentences = data.get("messages")
    if not isinstance(sentences, dict):
        raise ValueError(f"{source}: no [messages] table")
    for code, entry in sentences.items():
        if code not in MESSAGE_CODES:
            raise ValueError(f"{source}: unknown message code {code!r}")
        for sentence in _forms(entry, code, source):
            unknown = placeholders(sentence) - set(MESSAGE_CODES[code])
            if unknown:
                raise ValueError(
                    f"{source}: {code!r} names {sorted(unknown)}, which the message "
                    "does not carry"
                )
    return Catalog(language, sentences, _date_format(data.get("format"), source))


def _forms(entry: Any, code: str, source: str) -> tuple[str, ...]:
    """The sentences of one catalog entry: one, or ``one`` and ``other``."""
    if isinstance(entry, str):
        return (entry,)
    if (
        isinstance(entry, dict)
        and code in MESSAGE_COUNTS
        and "other" in entry
        and set(entry) <= {"one", "other"}
        and all(isinstance(sentence, str) for sentence in entry.values())
    ):
        return tuple(entry.values())
    if isinstance(entry, dict) and code not in MESSAGE_COUNTS:
        raise ValueError(f"{source}: {code!r} counts nothing and takes one sentence")
    raise ValueError(
        f"{source}: {code!r} is neither a sentence nor the two sentences "
        "'one' and 'other'"
    )


def _date_format(form: Any, source: str) -> str:
    """How the catalog writes a date: ``date`` in its [format] table, else ISO."""
    if form is None:
        return _ISO_DATE
    written = form.get("date", _ISO_DATE) if isinstance(form, dict) else None
    if not isinstance(written, str) or set(form) - {"date"}:
        raise ValueError(f"{source}: [format] takes one entry, date, a string")
    try:
        date(2000, 1, 2).strftime(written)
    except ValueError as exc:
        raise ValueError(f"{source}: [format] date: {exc}") from exc
    return written


def placeholders(sentence: str) -> set[str]:
    """The names a catalog sentence asks for, as in ``str.format``."""
    return {name for _, name, _, _ in string.Formatter().parse(sentence) if name}


def _shown(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)
