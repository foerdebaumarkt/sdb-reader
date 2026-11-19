"""The hand-run tools that keep the CLP tables current (tools/clp/README.md)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools" / "clp"


def _tool(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_version_taken_is_the_newest_that_applies() -> None:
    """A consolidation published ahead of its date is not the law yet."""
    fetch = _tool("fetch_regulation")
    versions = ["20250901", "20260701", "20270101"]

    assert fetch.in_force(versions, "20261117") == "20260701"
    assert fetch.in_force(versions, "20270101") == "20270101"
    with pytest.raises(SystemExit):
        fetch.in_force(versions, "20200101")


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Verursacht Hautreizungen.", "fixed"),
        ("Bei Brand: … zum Löschen verwenden.", "parameter"),
        ("Schutzhandschuhe/Schutzkleidung tragen.", "alternatives"),
    ],
)
def test_only_a_fixed_sentence_is_marked_as_one(text: str, kind: str) -> None:
    assert _tool("extract_statements").classify(text) == kind


def test_a_table_cell_becomes_one_line_without_the_journals_marks() -> None:
    extract = _tool("extract_statements")

    assert (
        extract._cell_text("►M4 Giftig für Wasserorganismen, mit langfris\xad\ntiger")
        == "Giftig für Wasserorganismen, mit langfristiger"
    )
    assert extract._cell_text("Dampf/\nAerosol nicht einatmen.") == (
        "Dampf/Aerosol nicht einatmen."
    )
