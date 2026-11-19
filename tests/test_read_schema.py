"""The schema describes what ``sdb-reader read`` prints (SDW-16)."""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import pymupdf
import pytest

from sdb_reader import cli

SHEET = """Sicherheitsdatenblatt
Überarbeitet am: 20.07.2022
Version: 2 / DE
ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
Produktname: Bad- und Küchenfarbe
1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt
Muster GmbH
Musterweg 1
12345 Musterstadt
Telefon: (+49) 0555-0142-0
E-Mail: info@muster.example
ABSCHNITT 2: Mögliche Gefahren
Verordnung (EG) Nr. 1907/2006
2.2 Kennzeichnungselemente
Signalwort: Achtung
GHS07
H315: Verursacht Hautreizungen.
P101: Ist ärztlicher Rat erforderlich, Verpackung oder Kennzeichnungsetikett bereithalten.
EUH208: Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.
"""

UNLABELLED = """Sicherheitsdatenblatt
ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
Produktname: Quarzsand
ABSCHNITT 2: Mögliche Gefahren
Verordnung (EG) Nr. 1907/2006
Das Produkt ist nicht eingestuft. Kein Signalwort.
"""

LEAFLET = """Produktprospekt
ABSCHNITT 1: Allgemeine Hinweise
Dekorativer Anstrich für Innenräume.
"""

FEED = b"""<?xml version="1.0"?>
<DatasheetFeed>
  <Datasheet>
    <InformationFromExportingSystem>
      <XmlStandardVersionNo>4.4.0</XmlStandardVersionNo>
      <SystemUsedInPreparation><Name>Example Author</Name></SystemUsedInPreparation>
    </InformationFromExportingSystem>
    <HazardIdentification><HazardLabelling><ClpLabellingInfo>
      <ClpHazardStatement><PhraseCode>412</PhraseCode></ClpHazardStatement>
    </ClpLabellingInfo></HazardLabelling></HazardIdentification>
  </Datasheet>
</DatasheetFeed>"""


def _schema() -> dict[str, Any]:
    text = (
        resources.files("sdb_reader")
        .joinpath("read_record.schema.json")
        .read_text(encoding="utf-8")
    )
    schema: dict[str, Any] = json.loads(text)
    return schema


def _pdf(path: Path, text: str, attachment: bytes | None = None) -> Path:
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), text, fontsize=8)
        if attachment is not None:
            doc.embfile_add("sds.xml", attachment)
        doc.save(path)
    return path


def _read(capsys: pytest.CaptureFixture[str], *argv: str) -> list[dict[str, Any]]:
    cli.main(["read", *argv])
    records: list[dict[str, Any]] = json.loads(capsys.readouterr().out)
    return records


def _validator() -> jsonschema.Draft202012Validator:
    schema = _schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )


@pytest.mark.spec("SDW-16")
def test_the_schema_holds_for_every_kind_of_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {
        "labelled.pdf": _pdf(tmp_path / "labelled.pdf", SHEET),
        "unlabelled.pdf": _pdf(tmp_path / "unlabelled.pdf", UNLABELLED),
        "leaflet.pdf": _pdf(tmp_path / "leaflet.pdf", LEAFLET),
        "embedded.pdf": _pdf(tmp_path / "embedded.pdf", SHEET, FEED),
        "broken-feed.pdf": _pdf(
            tmp_path / "broken-feed.pdf", SHEET, b"<DatasheetFeed><Datasheet>"
        ),
        "leaflet-feed.pdf": _pdf(tmp_path / "leaflet-feed.pdf", LEAFLET, FEED),
    }
    # A page without any text: nothing to read, with or without text recognition.
    unreadable = tmp_path / "unreadable.pdf"
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(unreadable)

    records = _read(capsys, *(str(path) for path in files.values()), str(unreadable))
    records += _read(capsys, "--include-raw-text", str(files["labelled.pdf"]))

    validator = _validator()
    for record in records:
        problems = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
        assert not problems, (record["file"]["filename"], problems[0].message)

    # The records really are of the kinds the schema tells apart.
    by_name = {record["file"]["filename"]: record for record in records[:-1]}
    assert by_name["labelled.pdf"]["sheet"]["hazard_statements"]["signal_word"]
    assert by_name["labelled.pdf"]["findings"] is not None
    assert "sheet" not in by_name["leaflet.pdf"]
    assert by_name["embedded.pdf"]["embedded_data"]["differences"]
    assert "unreadable" in by_name["broken-feed.pdf"]["embedded_data"]
    assert by_name["leaflet-feed.pdf"]["embedded_data"]["compared"] is False
    assert by_name["leaflet-feed.pdf"]["embedded_data"]["differences"] == []
    assert "extraction" not in by_name["unreadable.pdf"]
    assert "raw_text" in records[-1]["extraction"]


HARDENER = (
    SHEET.replace("Bad- und Küchenfarbe", "Härter für Bauteilkleber")
    .replace(
        "Signalwort: Achtung\nGHS07\nH315: Verursacht Hautreizungen.",
        "Signalwort: Gefahr\nGHS05\nH318: Verursacht schwere Augenschäden.",
    )
    .replace("20.07.2022", "03.05.2021")
)
# Each sheet ends before the next begins: section 1 after a later section.
END = "ABSCHNITT 16: Sonstige Angaben\n"


def _two_sheets(path: Path) -> Path:
    with pymupdf.open() as doc:
        for text in (SHEET + END, HARDENER + END):
            doc.new_page().insert_text((72, 72), text, fontsize=8)
        doc.save(path)
    return path


@pytest.mark.spec("SDW-32")
def test_a_file_of_two_sheets_gives_each_sheet_beside_the_file_s_reading(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    [record] = _read(capsys, str(_two_sheets(tmp_path / "kleber.pdf")))

    assert not list(_validator().iter_errors(record))
    assert record["sheet_count"] == 2
    first, second = record["parts"]
    assert set(first) == {"sheet", "statements", "warnings"}
    assert set(first["sheet"]) == set(record["sheet"])
    assert first["sheet"]["hazard_statements"]["hazard_codes"] == ["H315"]
    assert first["sheet"]["hazard_statements"]["signal_word"] == "Achtung"
    assert first["sheet"]["revision_date"] == "2022-07-20"
    assert second["sheet"]["hazard_statements"]["hazard_codes"] == ["H318"]
    assert second["sheet"]["hazard_statements"]["signal_word"] == "Gefahr"
    assert second["sheet"]["revision_date"] == "2021-05-03"
    assert second["sheet"]["product_identifier"] == "Härter für Bauteilkleber"
    assert [s["code"] for s in second["statements"]] == ["H318", "P101", "EUH208"]
    assert first["sheet"]["content_hash"] != second["sheet"]["content_hash"]
    assert record["sheet"]["content_hash"] not in (
        first["sheet"]["content_hash"],
        second["sheet"]["content_hash"],
    )
    # The file's reading unites them, as before.
    assert record["sheet"]["hazard_statements"]["hazard_codes"] == ["H315", "H318"]
    assert record["sheet"]["hazard_statements"]["signal_word"] == "Gefahr"
    assert record["sheet"]["revision_date"] == "2022-07-20"
    assert any(w["code"] == "several-sheets" for w in record["parser"]["warnings"])


@pytest.mark.spec("SDW-32")
def test_a_file_that_is_one_sheet_names_one_and_no_parts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sheet, leaflet = _read(
        capsys,
        str(_pdf(tmp_path / "labelled.pdf", SHEET)),
        str(_pdf(tmp_path / "leaflet.pdf", LEAFLET)),
    )
    validator = _validator()

    assert sheet["sheet_count"] == 1
    assert "parts" not in sheet
    assert "sheet_count" not in leaflet
    assert "parts" not in leaflet
    # The schema asks for the count, and knows parts only as several.
    del sheet["sheet_count"]
    assert list(validator.iter_errors(sheet))
    sheet["sheet_count"] = 1
    sheet["parts"] = []
    assert list(validator.iter_errors(sheet))


@pytest.mark.spec("SDW-16")
def test_a_key_the_schema_does_not_know_fails_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    [record] = _read(capsys, str(_pdf(tmp_path / "labelled.pdf", SHEET)))
    validator = _validator()

    for holder in (record, record["sheet"], record["sheet"]["contact_info"]):
        holder["something_new"] = 1
        assert list(validator.iter_errors(record))
        del holder["something_new"]
    assert not list(validator.iter_errors(record))


@pytest.mark.spec("SDW-16")
def test_the_schema_names_every_value_the_code_can_give() -> None:
    """The enumerations are copies: of the document kinds, of what section 2
    can say, of the sections, and of the findings' kinds."""
    from sdb_reader import DocumentKind, Section, StatedClassification

    definitions = _schema()["$defs"]

    assert set(definitions["verification"]["properties"]["kind"]["enum"]) == {
        kind.value for kind in DocumentKind
    }
    assert set(definitions["sheet"]["properties"]["stated_classification"]["enum"]) == {
        stated.value for stated in StatedClassification
    }
    sections = jsonschema.Draft202012Validator(
        definitions["sheet"]["properties"]["section_text"]
    )
    for section in Section:
        assert sections.is_valid({section.value: "text"})
    assert not sections.is_valid({"section_17": "text"})

    from sdb_reader import MESSAGE_CODES

    assert set(definitions["message"]["properties"]["code"]["enum"]) == set(
        MESSAGE_CODES
    )
    # The findings are the messages the two places that give findings build.
    [_, narrowed] = definitions["finding"]["allOf"]
    findings = set(narrowed["properties"]["code"]["enum"])
    files = resources.files("sdb_reader")
    built = set(
        re.findall(
            r'Message\(\s*"([a-z-]+)"',
            files.joinpath("compliance.py").read_text("utf-8"),
        )
    ) | {"not-german"}
    assert findings == built


@pytest.mark.spec("SDW-19")
def test_the_schema_demands_the_keys_of_each_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    [sheet] = _read(capsys, str(_pdf(tmp_path / "labelled.pdf", SHEET)))
    [leaflet] = _read(capsys, str(_pdf(tmp_path / "leaflet.pdf", LEAFLET)))
    validator = _validator()
    assert not list(validator.iter_errors(sheet))
    assert not list(validator.iter_errors(leaflet))

    for name in ("warnings", "errors", "findings"):
        assert list(
            validator.iter_errors({k: v for k, v in leaflet.items() if k != name})
        )
    for name in ("sheet", "statements", "parser", "extraction"):
        assert list(
            validator.iter_errors({k: v for k, v in sheet.items() if k != name})
        )
    # What only a German sheet has is refused on any other file.
    assert list(validator.iter_errors({**leaflet, "parser": {"warnings": []}}))
