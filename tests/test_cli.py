"""sdb-reader reads the files it is given and prints what each says."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from sdb_reader import cli

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


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, list[dict], str]:
    code = cli.main(["read", *argv])
    out, err = capsys.readouterr()
    return code, json.loads(out), err


@pytest.mark.spec("SDW-2")
def test_a_sheet_is_printed_with_what_it_says(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)

    code, records, _ = _run(capsys, str(path))

    assert code == 0
    [record] = records
    assert record["file"]["filename"] == "farbe.pdf"
    assert record["verification"]["kind"] == "safety-data-sheet"
    assert "H412" in record["sheet"]["hazard_statements"]["hazard_codes"]
    assert "raw_text" not in record["extraction"]


@pytest.mark.spec("SDW-2")
def test_a_document_that_is_no_sheet_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _pdf(tmp_path / "prospekt.pdf", LEAFLET)

    code, [record], _ = _run(capsys, str(path))

    assert code == 0
    assert record["verification"]["kind"] == "document"
    assert record["verification"]["errors"]
    assert "sheet" not in record


@pytest.mark.spec("SDW-1")
def test_the_file_name_does_not_matter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A name in a supplier's pattern does not make a leaflet a negative
    control or a sheet: the tool reads the content only."""
    path = _pdf(tmp_path / "0000000000000_00000_UP_2.pdf", SHEET)

    _, [record], _ = _run(capsys, str(path))

    assert record["verification"]["kind"] == "safety-data-sheet"
    assert "ean" not in record["file"]


@pytest.mark.spec("SDW-2")
def test_the_raw_text_on_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)

    _, [record], _ = _run(capsys, "--include-raw-text", str(path))

    assert "Bad- und Küchenfarbe" in record["extraction"]["raw_text"]


@pytest.mark.spec("SDW-4")
def test_a_missing_file_stops_before_reading(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stopped:
        cli.main(["read", str(tmp_path / "missing.pdf")])

    assert stopped.value.code == 2
    assert "not a file" in capsys.readouterr().err


@pytest.mark.spec("SDW-4")
def test_one_file_that_breaks_costs_only_itself(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good = _pdf(tmp_path / "good.pdf", SHEET)
    bad = _pdf(tmp_path / "bad.pdf", SHEET)
    read = cli.read_sheet

    def breaking(path, **kwargs):  # type: ignore[no-untyped-def]
        if path.name == "bad.pdf":
            raise RuntimeError("parser broke")
        return read(path, **kwargs)

    monkeypatch.setattr(cli, "read_sheet", breaking)

    code, records, err = _run(capsys, str(bad), str(good))

    assert code == 1
    assert [r["file"]["filename"] for r in records] == ["good.pdf"]
    assert "bad.pdf: RuntimeError: parser broke" in err


@pytest.mark.spec("SDW-3")
def test_log_lines_stay_out_of_the_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An impossible date is logged while parsing; `sdb-reader read x.pdf | jq` must
    still read stdout."""
    path = _pdf(tmp_path / "farbe.pdf", SHEET + "Überarbeitet am: 31.02.2020\n")

    code, [record], err = _run(capsys, str(path))

    assert code == 0
    assert record["verification"]["kind"] == "safety-data-sheet"
    assert "sds.date.invalid" in err


@pytest.mark.spec("SDW-5", "SDW-7")
def test_a_sheet_comes_with_its_statements_and_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET + "Überarbeitet am: 13.04.2018\n")

    _, [record], _ = _run(capsys, str(path))

    h412 = next(s for s in record["statements"] if s["code"] == "H412")
    assert h412["sheet"] == "Schädlich für Wasserorganismen, mit langfristiger Wirkung."
    assert h412["regulation"] == h412["sheet"]
    assert [f["code"] for f in record["findings"]] == ["predates-annex-ii"]


@pytest.mark.spec("SDW-5")
def test_a_document_that_is_no_sheet_has_no_statements(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _pdf(tmp_path / "prospekt.pdf", LEAFLET)

    _, [record], _ = _run(capsys, str(path))

    assert "statements" not in record
    assert record["findings"] == []


ITALIAN = "Scheda di dati di sicurezza\n" + "".join(
    f"SEZIONE {n}: titolo\n{n}.1 Informazioni\nH315 P261 P280\n" for n in range(1, 17)
)


@pytest.mark.spec("SDW-8")
def test_every_file_comes_with_its_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sheet = _pdf(tmp_path / "sheet.pdf", SHEET)
    leaflet = _pdf(tmp_path / "leaflet.pdf", LEAFLET)

    _, records, _ = _run(capsys, str(sheet), str(leaflet))

    assert [r["verification"]["kind"] for r in records] == [
        "safety-data-sheet",
        "document",
    ]
    assert records[0]["verification"]["prints_statement_codes"] is None
    assert records[1]["verification"]["prints_statement_codes"] is False


@pytest.mark.spec("SDW-8", "SDB-68")
def test_a_sheet_in_another_language_needs_a_german_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _pdf(tmp_path / "scheda.pdf", ITALIAN)

    code, [record], _ = _run(capsys, str(path))

    assert code == 0
    assert record["verification"]["kind"] == "safety-data-sheet-other-language"
    assert record["verification"]["prints_statement_codes"] is True
    assert "sheet" not in record
    assert [f["code"] for f in record["findings"]] == ["not-german"]


@pytest.mark.spec("SDW-8", "SDB-69", "SDB-72", "SDB-75", "SDB-76")
def test_a_sheet_says_what_its_product_needs_and_for_which_countries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _pdf(
        tmp_path / "sheet.pdf", SHEET + "ABSCHNITT 15: Rechtsvorschriften\nWGK 1\n"
    )

    _, [record], _ = _run(capsys, str(path))

    assert record["sheet"]["sheet_required"] is True
    assert record["sheet"]["stated_classification"] in {"classified", "not-stated"}
    assert record["sheet"]["countries"] == ["DE"]


@pytest.mark.spec("SDW-4")
def test_a_file_without_readable_text_is_in_the_output_and_fails_the_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = _pdf(tmp_path / "good.pdf", SHEET)
    blank = tmp_path / "blank.pdf"
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(blank)
    no_pdf = tmp_path / "notes.pdf"
    no_pdf.write_text("just a text file", encoding="utf-8")

    code, records, err = _run(capsys, str(blank), str(no_pdf), str(good))

    assert code == 1
    assert [r["file"]["filename"] for r in records] == [
        "blank.pdf",
        "notes.pdf",
        "good.pdf",
    ]
    for record in records[:2]:
        assert record["verification"]["kind"] == "document"
        assert record["warnings"] == [
            {
                "code": "unreadable",
                "params": {},
                "message": (
                    "Der Text der Datei ließ sich nicht lesen; es wurde nichts geprüft."
                ),
            }
        ]
        assert "extraction" not in record
        assert record["errors"]
        # The reason does not name the file (BIB-2); stderr does, in front of it.
        assert str(tmp_path) not in json.dumps(record["errors"])
        assert f"{record['file']['path']}: {record['errors'][0]['message']}" in err
    assert "good.pdf" not in err


@pytest.mark.spec("SDW-19")
def test_a_record_has_the_same_keys_for_every_file_of_its_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lists are empty, not missing; only a German sheet has sheet, statements
    and parser, and then always."""
    sheet = _pdf(tmp_path / "sheet.pdf", SHEET)
    leaflet = _pdf(tmp_path / "prospekt.pdf", LEAFLET)
    foreign = _pdf(tmp_path / "scheda.pdf", ITALIAN)
    blank = tmp_path / "blank.pdf"
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(blank)

    _, records, _ = _run(capsys, str(sheet), str(leaflet), str(foreign), str(blank))

    always = {"file", "verification", "warnings", "errors", "findings"}
    assert [set(record) for record in records] == [
        always
        | {"extraction", "sheet", "statements", "parser", "sheet_count"}
        | {"cover_page", "display_term"},
        always | {"extraction"},
        always | {"extraction"},
        always,
    ]
    for record in records:
        for name in ("warnings", "errors", "findings"):
            assert isinstance(record[name], list)
    assert isinstance(records[0]["parser"]["warnings"], list)
    assert [finding["code"] for finding in records[2]["findings"]] == ["not-german"]


@pytest.mark.spec("SDW-19")
def test_a_sheet_the_parser_notes_nothing_about_still_has_its_parser_part() -> None:
    from sdb_reader import extraction_from_dict, read_extraction, reading_to_dict

    reading = read_extraction(
        extraction_from_dict(
            {"text": SHEET, "extractor": "pymupdf", "pages_sampled": 1, "warnings": []}
        )
    )
    assert reading.parser_result is not None
    reading.parser_result.warnings.clear()

    assert reading_to_dict(reading)["parser"] == {"warnings": []}


@pytest.mark.spec("SDW-20")
def test_the_command_says_its_version(capsys: pytest.CaptureFixture[str]) -> None:
    from importlib import metadata

    with pytest.raises(SystemExit) as ended:
        cli.main(["--version"])

    assert ended.value.code == 0
    assert capsys.readouterr().out.strip() == (
        f"sdb-reader {metadata.version('sdb-reader')}"
    )


@pytest.mark.spec("SDW-34")
def test_read_reports_a_revision_date_after_the_day_it_runs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import date

    path = _pdf(tmp_path / "blatt.pdf", SHEET + "Überarbeitet am: 28.11.2028\n")

    monkeypatch.setattr(cli, "_today", lambda: date(2026, 11, 18))
    _, [record], _ = _run(capsys, str(path))
    codes = [finding["code"] for finding in record["findings"]]
    assert "revised-in-future" in codes
    assert "undated" in codes
    future = next(f for f in record["findings"] if f["code"] == "revised-in-future")
    assert future["params"] == {"revised": "2028-11-28", "today": "2026-11-18"}
    # The date stays in the record as the sheet prints it.
    assert record["sheet"]["revision_date"] == "2028-11-28"

    monkeypatch.setattr(cli, "_today", lambda: date(2028, 11, 28))
    _, [record], _ = _run(capsys, str(path))
    assert "revised-in-future" not in [f["code"] for f in record["findings"]]
