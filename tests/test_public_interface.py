"""What a program that uses the library can rely on (specs/bibliothek.md)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pymupdf
import pytest

import sdb_reader

SHEET = """Sicherheitsdatenblatt
ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
Produktname: Bad- und Küchenfarbe
ABSCHNITT 2: Mögliche Gefahren
Verordnung (EG) Nr. 1907/2006
H412: Schädlich für Wasserorganismen, mit langfristiger Wirkung.
P101: Ist ärztlicher Rat erforderlich, Verpackung oder Kennzeichnungsetikett bereithalten.
"""

LEAFLET = """Produktprospekt
ABSCHNITT 1: Allgemeine Hinweise
Dekorativer Anstrich für Innenräume.
"""


def _pdf(path: Path, text: str) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


def _description(value: object) -> str:
    """The docstring someone wrote. A dataclass without one gets its
    signature as a docstring, which describes nothing."""
    doc = (inspect.getdoc(value) or "").strip()
    name = getattr(value, "__name__", "")
    return "" if doc.startswith(f"{name}(") else doc


@pytest.mark.spec("BIB-1")
def test_every_exported_name_exists_and_is_listed_once() -> None:
    names = sdb_reader.__all__

    assert len(set(names)) == len(names)
    assert [name for name in names if not hasattr(sdb_reader, name)] == []
    public = {
        name
        for name, value in vars(sdb_reader).items()
        if not name.startswith("_") and not inspect.ismodule(value)
    }
    assert public == set(names)


@pytest.mark.spec("BIB-1")
def test_every_exported_function_and_class_is_described() -> None:
    undescribed = [
        name
        for name in sdb_reader.__all__
        if (inspect.isclass(value := getattr(sdb_reader, name)) or callable(value))
        and not _description(value)
    ]

    assert undescribed == []


@pytest.mark.spec("BIB-2")
def test_a_file_is_read_from_its_path_alone(tmp_path: Path) -> None:
    """The same content under two names gives the same reading, and the
    reading does not name the file."""
    one = sdb_reader.read_sheet(_pdf(tmp_path / "0000000000000_00000_UP_2.pdf", SHEET))
    other = sdb_reader.read_sheet(_pdf(tmp_path / "anything.pdf", SHEET))

    assert one.verification.kind is sdb_reader.DocumentKind.SAFETY_DATA_SHEET
    assert sdb_reader.reading_to_dict(one) == sdb_reader.reading_to_dict(other)
    assert "0000000000000" not in json.dumps(sdb_reader.reading_to_dict(one))
    assert list(inspect.signature(sdb_reader.read_sheet).parameters) == [
        "path",
        "max_pages",
    ]


@pytest.mark.spec("BIB-3")
@pytest.mark.parametrize("text", [SHEET, LEAFLET])
def test_a_stored_text_reads_like_the_file(tmp_path: Path, text: str) -> None:
    path = _pdf(tmp_path / "a.pdf", text)
    from_file = sdb_reader.read_sheet(path)
    assert from_file.extraction is not None

    stored = json.loads(json.dumps(sdb_reader.extraction_to_dict(from_file.extraction)))
    images = (
        json.loads(json.dumps(sdb_reader.label_images_to_dict(from_file.label_images)))
        if from_file.label_images is not None
        else None
    )
    path.unlink()
    from_text = sdb_reader.read_extraction(
        sdb_reader.extraction_from_dict(stored),
        None if images is None else sdb_reader.label_images_from_dict(images),
    )

    assert sdb_reader.reading_to_dict(from_text) == sdb_reader.reading_to_dict(
        from_file
    )
    assert (from_text.parser_result is not None) == (text is SHEET)


@pytest.mark.spec("BIB-3", "BIB-4")
def test_a_stored_text_names_its_stage_and_keeps_no_pages(tmp_path: Path) -> None:
    extraction = sdb_reader.extract_pdf_text(_pdf(tmp_path / "a.pdf", SHEET))

    stored = sdb_reader.extraction_to_dict(extraction)

    assert stored["stage"] == sdb_reader.extraction_stage()
    assert sorted(stored) == ["extractor", "pages_sampled", "stage", "text", "warnings"]


@pytest.mark.spec("BIB-1")
def test_the_package_says_it_is_typed() -> None:
    """Without the marker a type checker treats every exported name as Any."""
    assert (Path(sdb_reader.__file__).parent / "py.typed").is_file()


@pytest.mark.spec("BIB-3")
@pytest.mark.parametrize(
    "stored",
    [
        {"code": "a-code-of-another-version", "params": {}},
        {"code": "pages-read-by-ocr", "params": {}},
        {"params": {"pages": 2}},
    ],
)
def test_a_stored_text_with_a_warning_this_version_does_not_know_is_read(
    stored: dict[str, object],
) -> None:
    """A code that has gone, values that no longer fit, no code at all: the
    text is read, and the warning is kept as it was stored."""
    extraction = sdb_reader.extraction_from_dict(
        {
            "text": "Sicherheitsdatenblatt",
            "extractor": "pymupdf",
            "pages_sampled": 1,
            "warnings": [stored],
        }
    )

    [warning] = extraction.warnings
    assert warning.code == "unknown"
    assert json.loads(warning.params["text"]) == stored


def _read_sheet_record(tmp_path: Path) -> tuple[sdb_reader.SafetyDataSheet, dict]:
    reading = sdb_reader.read_sheet(_pdf(tmp_path / "farbe.pdf", SHEET))
    assert reading.parser_result is not None
    assert reading.extraction is not None
    sheet = reading.parser_result.sheet
    # Through JSON, as a caller keeps it.
    stored = json.loads(json.dumps(sdb_reader.sheet_to_dict(sheet, reading.extraction)))
    return sheet, stored


@pytest.mark.spec("BIB-21")
def test_a_stored_sheet_is_read_back_as_the_sheet_it_was(tmp_path: Path) -> None:
    sheet, stored = _read_sheet_record(tmp_path)

    back = sdb_reader.sheet_from_dict(stored)

    assert back == sheet
    assert back.section_text.keys() == sheet.section_text.keys() != set()
    assert sdb_reader.requires_sheet(back) is stored["sheet_required"] is True
    assert sdb_reader.contradicts_label(back) is False
    # A key a later version may add is no reason to refuse the rest.
    assert sdb_reader.sheet_from_dict({**stored, "added_later": 1}) == sheet


@pytest.mark.spec("BIB-21")
@pytest.mark.parametrize(
    "change",
    [
        # As versions up to 0.5.0 stored it.
        lambda s: s["contact_info"].update(
            email=s["contact_info"].pop("supplier_email")
        ),
        lambda s: s["hazard_statements"].update(
            supplemental_phrases=s["hazard_statements"].pop("supplemental_codes")
        ),
        lambda s: s.update(section_text={"abschnitt_1": "Bezeichnung"}),
        # A value of another kind, a key that is missing, no sheet at all.
        lambda s: s.update(revision_date="am 1. März"),
        lambda s: s.update(stated_classification="vermutlich"),
        lambda s: s["hazard_statements"].update(hazard_codes="H412"),
        lambda s: s.pop("stated_article"),
        lambda s: s.clear(),
    ],
)
def test_a_sheet_stored_in_another_shape_is_refused_and_not_guessed(
    tmp_path: Path, change: object
) -> None:
    _, stored = _read_sheet_record(tmp_path)
    change(stored)

    with pytest.raises(ValueError, match="not a sheet as this version stores it"):
        sdb_reader.sheet_from_dict(stored)
