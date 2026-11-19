"""Request fields for the model families the command knows (SDW-31).

A model that reasons before it answers is asked to copy from a page, not to
deduce: reasoning costs time and tokens there and buys nothing. How it is
switched off differs from service to service and is no part of the standard
interface, so the strings ship as data: ``presets.toml``, one table per
preset, with the model and the day it was measured with.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

from .ask import OMITTABLE_REQUEST_FIELDS, RESERVED_REQUEST_FIELDS

_KEYS = frozenset({"description", "request", "omit", "tested_with", "tested_on"})


@dataclass(frozen=True, slots=True)
class Preset:
    """What one preset puts into a request, and what is known about it."""

    name: str
    # One line per language.
    description: Mapping[str, str]
    # Merged into every request.
    request: Mapping[str, Any] = field(default_factory=dict)
    # Fields of the standard request left out.
    omit: frozenset[str] = frozenset()
    # The model and the day the preset was measured with, or neither.
    tested_with: str | None = None
    tested_on: date | None = None

    def describe(self, language: str) -> str:
        """The preset's line in *language*, in English where it has none."""
        return self.description.get(language) or self.description["en"]


def shipped_presets() -> dict[str, Preset]:
    """The presets the package ships, by name."""
    source = resources.files("sdb_reader").joinpath("presets.toml")
    return _presets(source.read_text(encoding="utf-8"), "presets.toml")


def load_presets(path: Path) -> dict[str, Preset]:
    """A caller's own presets: a TOML file like the shipped one.

    Raises ValueError for a file that cannot be read as presets.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    return _presets(text, str(path))


def _presets(text: str, source: str) -> dict[str, Preset]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{source} is no TOML: {exc}") from exc
    return {name: _preset(name, table, source) for name, table in data.items()}


def _preset(name: str, table: object, source: str) -> Preset:
    def refuse(why: str) -> ValueError:
        return ValueError(f"{source}, preset {name}: {why}")

    if not isinstance(table, dict):
        raise refuse("is no table")
    unknown = sorted(table.keys() - _KEYS)
    if unknown:
        raise refuse(f"unknown key {', '.join(unknown)}")
    description = table.get("description")
    if isinstance(description, str):
        description = {"en": description}
    if (
        not isinstance(description, dict)
        or not description.get("en")
        or not all(isinstance(line, str) for line in description.values())
    ):
        raise refuse("needs a description, a line or a table with a line for en")
    request = table.get("request", {})
    if not isinstance(request, dict):
        raise refuse("request is no table")
    taken = sorted(RESERVED_REQUEST_FIELDS & request.keys())
    if taken:
        raise refuse(f"request may not set {', '.join(taken)}")
    omit = table.get("omit", [])
    if not isinstance(omit, list) or not set(omit) <= OMITTABLE_REQUEST_FIELDS:
        allowed = ", ".join(sorted(OMITTABLE_REQUEST_FIELDS))
        raise refuse(f"omit is a list that may name only: {allowed}")
    if not request and not omit:
        raise refuse("changes nothing: it needs request or omit")
    tested_with, tested_on = table.get("tested_with"), table.get("tested_on")
    if (tested_with is None) != (tested_on is None):
        raise refuse("tested_with and tested_on go together")
    if tested_with is not None and (
        not isinstance(tested_with, str)
        or not tested_with
        or type(tested_on) is not date
    ):
        raise refuse("tested_with is a model's name and tested_on a date")
    return Preset(name, description, request, frozenset(omit), tested_with, tested_on)
