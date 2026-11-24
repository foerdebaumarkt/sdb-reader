"""diff sets two runs beside each other (SDW-27, SDW-28). The records are invented."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from sdb_reader import cli

H315 = "H315: Verursacht Hautreizungen."
P102 = "P102: Darf nicht in die Hände von Kindern gelangen."


def _file(name: str, folder: str = "/sheets") -> dict[str, Any]:
    return {"path": f"{folder}/{name}", "filename": name, "size_bytes": 1000}


def _read(name: str, folder: str = "/sheets", **changes: Any) -> dict[str, Any]:
    """A record as `read` writes it for a German sheet, with *changes* to it.

    A change names a field of the sheet, of its label or of its supplier;
    "stage", "findings" and "statements" replace those.
    """
    record: dict[str, Any] = {
        "file": _file(name, folder),
        "verification": {"kind": "safety-data-sheet"},
        "warnings": [],
        "errors": [],
        "findings": [],
        "extraction": {"stage": "2+pymupdf-1.0", "extractor": "pymupdf"},
        "sheet": {
            "revision_date": "2022-07-20",
            "issue_date": None,
            "version": "2",
            "product_identifier": "Musterfarbe",
            "countries": ["DE"],
            "stated_classification": "classified",
            "stated_voluntary": False,
            "stated_article": False,
            "sheet_duty": "required",
            "hazard_statements": {
                "hazard_codes": ["H315"],
                "precautionary_codes": ["P102"],
                "supplemental_codes": [],
                "signal_word": "Achtung",
                "pictograms": ["GHS07"],
                "hazard_text": H315,
                "precautionary_text": P102,
                "supplemental_text": None,
            },
            "contact_info": {
                "supplier_name": "Muster GmbH",
                "supplier_address": "Musterweg 1, 12345 Musterstadt",
                "supplier_phone": "0555-0142-0",
                "emergency_phone": "0555-0142-9",
                "supplier_email": "info@muster.example",
                "supplier_website": None,
            },
        },
        "parser": {"warnings": []},
        "statements": [
            {"code": "H315", "sheet": "Verursacht Hautreizungen.", "regulation": None},
            {
                "code": "P102",
                "sheet": "Darf nicht in die Hände von Kindern gelangen.",
                "regulation": None,
            },
        ],
    }
    for key, value in changes.items():
        if key == "stage":
            record["extraction"]["stage"] = value
        elif key in ("findings", "statements"):
            record[key] = value
        elif key in record["sheet"]["hazard_statements"]:
            record["sheet"]["hazard_statements"][key] = value
        elif key in record["sheet"]["contact_info"]:
            record["sheet"]["contact_info"][key] = value
        else:
            assert key in record["sheet"], key
            record["sheet"][key] = value
    return record


def _leaflet(name: str) -> dict[str, Any]:
    return {
        "file": _file(name),
        "verification": {"kind": "document"},
        "warnings": [],
        "errors": [],
        "findings": [],
        "extraction": {"stage": "2+pymupdf-1.0", "extractor": "pymupdf"},
    }


def _ask(name: str, folder: str = "/sheets", **changes: Any) -> dict[str, Any]:
    """A record as `ask` writes it, the model agreeing with `_read` unless changed."""
    record: dict[str, Any] = {
        "file": _file(name, folder),
        "kind": "safety-data-sheet",
        "asked": True,
        "model": "some-model",
        "sent": "before-section-3",
        "stage": "2+pymupdf-1.0",
        "question": "0123456789ab",
        "reading": {
            "revision_date": "2022-07-20",
            "revision_date_named": "20.07.2022",
            "hazard_statements": {
                "hazard_codes": ["H315"],
                "precautionary_codes": ["P102"],
                "supplemental_codes": [],
                "hazard_text": H315,
                "precautionary_text": P102,
                "supplemental_text": None,
            },
            "contact_info": {
                "supplier_name": "Muster GmbH",
                "supplier_address": None,
                "supplier_phone": None,
                "supplier_email": "info@muster.example",
                "supplier_website": None,
            },
        },
        "answer": {},
    }
    for key, value in changes.items():
        if key in ("model", "stage", "question"):
            record[key] = value
        elif key in record["reading"]["hazard_statements"]:
            record["reading"]["hazard_statements"][key] = value
        elif key in record["reading"]["contact_info"]:
            record["reading"]["contact_info"][key] = value
        else:
            assert key in record["reading"], key
            record["reading"][key] = value
    return record


def _not_asked(name: str) -> dict[str, Any]:
    return {
        "file": _file(name),
        "kind": "document",
        "asked": False,
        "reason": {"code": "model-not-asked", "params": {}, "message": "…"},
    }


def _lines(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
    )
    return path


def _diff(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    a: list[dict[str, Any]],
    b: list[dict[str, Any]],
    *argv: str,
) -> tuple[int, str, str]:
    code = cli.main(
        [
            "diff",
            str(_lines(tmp_path / "a.jsonl", a)),
            str(_lines(tmp_path / "b.jsonl", b)),
            *argv,
        ]
    )
    out, err = capsys.readouterr()
    return code, out, err


def _counts(out: str) -> dict[str, Any]:
    fields: dict[str, Any] = json.loads(out)["fields"]
    return fields


# ---------------------------------------------------------------------------
# Two readings
# ---------------------------------------------------------------------------


@pytest.mark.spec("SDW-27")
def test_a_run_set_beside_itself_shows_no_difference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = [_read("one.pdf"), _read("two.pdf"), _leaflet("three.pdf")]

    code, out, err = _diff(capsys, tmp_path, run, copy.deepcopy(run))

    assert code == 0
    assert "Dateien in beiden: 3; nur in A: 0; nur in B: 0" in out
    assert "Dateien mit Abweichung: 0" in out
    assert "Keine Abweichung." in out
    assert err == ""


@pytest.mark.spec("SDW-27")
def test_two_readings_differ_field_by_field_gained_lost_and_changed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = [
        _read("gained.pdf", revision_date=None),
        _read("lost.pdf"),
        _read("changed.pdf"),
        _read("same.pdf"),
        _read("changed-too.pdf"),
    ]
    after = [
        _read("gained.pdf"),
        _read("lost.pdf", emergency_phone=None),
        _read("changed.pdf", hazard_codes=["H315", "H319"], signal_word="Gefahr"),
        _read("same.pdf"),
        _read("changed-too.pdf", signal_word="Gefahr"),
    ]

    code, out, _ = _diff(capsys, tmp_path, before, after, "--json")
    _, text, _ = _diff(capsys, tmp_path, before, after)

    counts = _counts(out)
    assert code == 1
    assert json.loads(out)["files"] == {
        "both": 5,
        "only_a": 0,
        "only_b": 0,
        "not_compared": 0,
        "differing": 4,
        "differing_counted_only": 0,
    }
    assert set(counts) == {
        "revision_date",
        "emergency_phone",
        "hazard_codes",
        "signal_word",
    }
    assert counts["revision_date"]["gained"] == 1
    assert counts["emergency_phone"]["lost"] == 1
    assert counts["signal_word"] == {
        "gained": 0,
        "lost": 0,
        "changed": 2,
        "counted_only": {"gained": 0, "lost": 0, "changed": 0},
        "examples": [
            {
                "file": "/sheets/changed-too.pdf",
                "field": "signal_word",
                "a": "Achtung",
                "b": "Gefahr",
            },
            {
                "file": "/sheets/changed.pdf",
                "field": "signal_word",
                "a": "Achtung",
                "b": "Gefahr",
            },
        ],
    }
    assert "Dateien mit Abweichung: 4" in text
    assert "revision_date: dazugekommen 1, weggefallen 0, geändert 0" in text
    assert "hazard_codes: dazugekommen 0, weggefallen 0, geändert 1" in text
    assert '      A: ["H315"]' in text
    assert '      B: ["H315", "H319"]' in text


@pytest.mark.spec("SDW-27")
def test_every_field_of_a_reading_is_compared(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = _read(
        "one.pdf",
        stated_classification="not-classified",
        stated_voluntary=True,
        stated_article=True,
        sheet_duty="not-required",
        countries=["DE", "AT"],
        signal_word="Gefahr",
        pictograms=["GHS05"],
        hazard_codes=["H318"],
        precautionary_codes=["P280"],
        supplemental_codes=["EUH208"],
        hazard_text="H318: Verursacht schwere Augenschäden.",
        precautionary_text="P280: Schutzhandschuhe tragen.",
        supplemental_text="EUH208: Enthält Musterstoff.",
        revision_date="2023-01-01",
        issue_date="2020-01-01",
        version="3",
        product_identifier="Musterlack",
        supplier_name="Beispiel AG",
        supplier_address="Beispielweg 2",
        supplier_phone="0555-0199",
        supplier_email="post@beispiel.example",
        supplier_website="www.beispiel.example",
        emergency_phone="0555-0100",
        findings=[{"code": "undated", "params": {}, "message": "…"}],
    )
    other["verification"]["kind"] = "safety-information"
    other["errors"] = [{"code": "no-text", "params": {"pages": 1}, "message": "…"}]
    other["embedded_data"] = {
        "compared": True,
        "differences": [{"field": "hazard_codes", "embedded": [], "read": ["H318"]}],
    }

    code, out, _ = _diff(capsys, tmp_path, [_read("one.pdf")], [other], "--json")

    assert code == 1
    assert list(_counts(out)) == [
        "kind",
        "stated_classification",
        "stated_voluntary",
        "stated_article",
        "sheet_duty",
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
        "emergency_phone",
        "findings",
        "embedded_differences",
        "errors",
    ]


@pytest.mark.spec("SDW-27")
def test_a_run_is_json_lines_or_one_list_and_the_last_line_of_a_file_holds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lines = _lines(
        tmp_path / "a.jsonl",
        [_read("one.pdf", signal_word="Gefahr"), _read("two.pdf"), _read("one.pdf")],
    )
    listed = tmp_path / "b.json"
    listed.write_text(json.dumps([_read("one.pdf"), _read("two.pdf")], indent=2))

    code = cli.main(["diff", str(lines), str(listed)])
    out, _ = capsys.readouterr()

    assert code == 0
    assert "Dateien: 2" in out.splitlines()[0]


@pytest.mark.spec("SDW-27")
def test_files_are_matched_by_path_or_on_demand_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    here = [_read("one.pdf", "/here"), _read("two.pdf", "/here")]
    there = [
        _read("one.pdf", "/there", signal_word="Gefahr"),
        _read("three.pdf", "/there"),
    ]

    by_path, out, _ = _diff(capsys, tmp_path, here, there)
    by_name, named, _ = _diff(capsys, tmp_path, here, there, "--match", "name")

    # Files only one run names are counted; they are no difference.
    assert by_path == 0
    assert "Dateien in beiden: 0; nur in A: 2; nur in B: 2" in out
    assert by_name == 1
    assert "Dateien in beiden: 1; nur in A: 1; nur in B: 1" in named
    assert "signal_word: dazugekommen 0, weggefallen 0, geändert 1" in named


@pytest.mark.spec("SDW-27")
def test_a_name_under_several_paths_cannot_be_matched_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    twice = [_read("one.pdf", "/here"), _read("one.pdf", "/there")]

    with pytest.raises(SystemExit) as stopped:
        _diff(capsys, tmp_path, twice, [_read("one.pdf")], "--match", "name")

    assert stopped.value.code == 2
    assert "several paths" in capsys.readouterr().err


@pytest.mark.spec("SDW-27")
@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json\n",
        json.dumps({"something": "else"}) + "\n",
        json.dumps(_read("one.pdf")) + "\n" + json.dumps(_ask("two.pdf")) + "\n",
    ],
)
def test_a_file_that_is_no_run_ends_the_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str
) -> None:
    good = _lines(tmp_path / "good.jsonl", [_read("one.pdf")])
    bad = tmp_path / "bad.jsonl"
    bad.write_text(content)

    for argv in ([str(good), str(bad)], [str(bad), str(good)]):
        with pytest.raises(SystemExit) as stopped:
            cli.main(["diff", *argv])
        assert stopped.value.code == 2
    with pytest.raises(SystemExit) as missing:
        cli.main(["diff", str(good), str(tmp_path / "missing.jsonl")])
    assert missing.value.code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.spec("SDW-27")
def test_examples_are_bounded_and_details_hold_every_differing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    names = [f"sheet-{n}.pdf" for n in range(5)]
    before = [_read(name) for name in names]
    after = [_read(name, version="3", signal_word=None) for name in names]
    details = tmp_path / "details.jsonl"
    details.write_text("left from an earlier call\n")

    code, out, _ = _diff(
        capsys,
        tmp_path,
        before,
        after,
        "--json",
        "--examples",
        "2",
        "--details",
        str(details),
    )
    _, none, _ = _diff(capsys, tmp_path, before, after, "--examples", "0")

    rows = [json.loads(line) for line in details.read_text().splitlines()]
    assert code == 1
    assert _counts(out)["version"]["changed"] == 5
    assert len(_counts(out)["version"]["examples"]) == 2
    assert [row["file"] for row in rows] == [f"/sheets/{name}" for name in names]
    assert rows[0]["differences"] == [
        {"field": "signal_word", "a": "Achtung", "b": None},
        {"field": "version", "a": "2", "b": "3"},
    ]
    assert "sheet-0.pdf" not in none
    assert "version: dazugekommen 0, weggefallen 0, geändert 5" in none


@pytest.mark.spec("SDW-27")
def test_a_long_value_is_cut_in_the_text_and_whole_as_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    long = "H315: " + "Verursacht Hautreizungen. " * 30
    before, after = [_read("one.pdf")], [_read("one.pdf", hazard_text=long)]

    _, text, _ = _diff(capsys, tmp_path, before, after)
    _, out, _ = _diff(capsys, tmp_path, before, after, "--json")

    [line] = [line for line in text.splitlines() if line.startswith("      B:")]
    assert line.endswith("…")
    assert len(line) < 240
    assert _counts(out)["hazard_text"]["examples"][0]["b"] == long


@pytest.mark.spec("SDW-17", "SDW-27")
def test_the_report_is_in_the_language_asked_for(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = _diff(
        capsys,
        tmp_path,
        [_read("one.pdf")],
        [_read("one.pdf", version="3")],
        "--lang",
        "en",
    )

    assert code == 1
    assert "files in both: 1; only in A: 0; only in B: 0; not comparable: 0" in out
    assert "version: gained 0, lost 0, changed 1" in out


# ---------------------------------------------------------------------------
# A reading and a model's answers, or two models' answers
# ---------------------------------------------------------------------------


@pytest.mark.spec("SDW-27")
def test_a_model_that_agrees_shows_no_difference_in_what_it_is_asked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Signal word, pictograms, address and the other fields of a reading are
    not asked for, so a model that says nothing about them does not differ."""
    reads = [_read("one.pdf"), _leaflet("two.pdf")]
    asks = [_ask("one.pdf"), _not_asked("two.pdf")]

    code, out, _ = _diff(capsys, tmp_path, reads, asks)
    back, _, _ = _diff(capsys, tmp_path, asks, reads)

    assert code == back == 0
    assert "(read)" in out.splitlines()[0]
    assert "(ask)" in out.splitlines()[1]
    assert "nicht vergleichbar: 1" in out


@pytest.mark.spec("SDW-27")
def test_a_joined_code_counts_as_its_parts_and_spelling_is_no_difference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    joined = "P305+P351+P338: BEI KONTAKT MIT DEN AUGEN: Mit Wasser spülen."
    read = _read(
        "one.pdf",
        precautionary_codes=["P305+P351+P338"],
        precautionary_text=joined,
        statements=[
            {"code": "H315", "sheet": "Verursacht Hautreizungen.", "regulation": None},
            {
                "code": "P305+P351+P338",
                "sheet": "BEI KONTAKT MIT DEN AUGEN: Mit Wasser spülen.",
                "regulation": None,
            },
        ],
    )
    asked = _ask(
        "one.pdf",
        precautionary_codes=["P305", "P351+P338"],
        hazard_text="H315:  verursacht hautreizungen",
        precautionary_text="P305: BEI KONTAKT MIT DEN AUGEN. P351+P338: Spülen.",
        supplier_name="MUSTER  GmbH",
        supplier_email="Info@Muster.example",
    )

    code, out, _ = _diff(capsys, tmp_path, [read], [asked])

    assert code == 0, out


@pytest.mark.spec("SDW-27")
def test_what_a_model_says_otherwise_differs_in_codes_wording_supplier_and_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    asked = _ask(
        "one.pdf",
        hazard_codes=["H315", "H319"],
        precautionary_codes=[],
        supplemental_codes=["EUH208"],
        hazard_text="H315: Reizt die Haut.\nH319: Verursacht schwere Augenreizung.",
        precautionary_text=None,
        supplemental_text="EUH208: Enthält Musterstoff.",
        supplier_name="Beispiel AG",
        supplier_email=None,
        revision_date="2023-02-01",
    )
    details = tmp_path / "details.jsonl"

    code, out, _ = _diff(
        capsys,
        tmp_path,
        [_read("one.pdf")],
        [asked],
        "--json",
        "--details",
        str(details),
    )

    [row] = [json.loads(line) for line in details.read_text().splitlines()]
    assert code == 1
    assert row["differences"] == [
        {"field": "hazard_codes", "a": ["H315"], "b": ["H315", "H319"]},
        {"field": "precautionary_codes", "a": ["P102"], "b": None},
        {"field": "supplemental_codes", "a": None, "b": ["EUH208"]},
        {
            "field": "wording",
            "code": "H315",
            "a": ["Verursacht Hautreizungen."],
            "b": ["Reizt die Haut."],
        },
        {"field": "supplier_name", "a": "Muster GmbH", "b": "Beispiel AG"},
        {"field": "supplier_email", "a": "info@muster.example", "b": None},
        {"field": "revision_date", "a": "2022-07-20", "b": "2023-02-01"},
    ]
    counts = _counts(out)
    assert counts["precautionary_codes"]["lost"] == 1
    assert counts["supplemental_codes"]["gained"] == 1
    assert counts["wording"]["changed"] == 1
    assert counts["wording"]["examples"][0]["code"] == "H315"


@pytest.mark.spec("SDW-27")
def test_a_model_without_a_date_is_no_difference_to_a_reading_but_to_a_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    silent = [_ask("one.pdf", revision_date=None)]

    to_reading, _, _ = _diff(capsys, tmp_path, [_read("one.pdf")], silent)
    from_reading, _, _ = _diff(capsys, tmp_path, silent, [_read("one.pdf")])
    read_without, out, _ = _diff(
        capsys, tmp_path, [_read("one.pdf", revision_date=None)], [_ask("one.pdf")]
    )
    to_model, between, _ = _diff(capsys, tmp_path, silent, [_ask("one.pdf")])

    assert to_reading == from_reading == 0
    # A date the parser did not read and the model names is what to look at.
    assert read_without == 1
    assert "revision_date: dazugekommen 1" in out
    assert to_model == 1
    assert "revision_date: dazugekommen 1" in between


@pytest.mark.spec("SDW-27")
def test_runs_of_another_stage_model_or_question_are_compared_with_a_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, stages = _diff(
        capsys,
        tmp_path,
        [_read("one.pdf", stage="1+pymupdf-1.0")],
        [_read("one.pdf")],
    )
    _, _, mixed = _diff(
        capsys, tmp_path, [_read("one.pdf", stage="1+pymupdf-1.0")], [_ask("one.pdf")]
    )
    _, _, models = _diff(
        capsys,
        tmp_path,
        [_ask("one.pdf", model="another-model", question="ba9876543210")],
        [_ask("one.pdf")],
    )
    old = _read("one.pdf")
    del old["extraction"]["stage"]
    _, _, unnamed = _diff(capsys, tmp_path, [old], [_read("one.pdf")])
    _, _, english = _diff(
        capsys,
        tmp_path,
        [_read("one.pdf", stage="1+pymupdf-1.0")],
        [_read("one.pdf")],
        "--lang",
        "en",
    )

    # A warning, not an error: the stage is no field of a reading.
    assert code == 0
    assert "WARNUNG" in stages
    assert "A: 1+pymupdf-1.0; B: 2+pymupdf-1.0" in stages
    assert "Lese-Stufen" in mixed
    assert "verschiedene Modelle gefragt (A: another-model; B: some-model)" in models
    assert "nicht dieselbe Frage" in models
    assert "Lese-Stufen" not in models
    # A record written before records named their stage says nothing about it.
    assert unnamed == ""
    assert "WARNING: the runs come from different reading stages" in english


# ---------------------------------------------------------------------------
# Files that are only counted
# ---------------------------------------------------------------------------


@pytest.mark.spec("SDW-28")
def test_files_that_are_only_counted_are_in_no_example_and_no_detail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = [
        _read("shown.pdf"),
        _read("held-by-name.pdf"),
        _read("held-by-path.pdf", "/sheets/deep"),
        _read("held-by-end.pdf", "/sheets/deep"),
        _read("held-and-same.pdf"),
    ]
    after = [
        _read("shown.pdf", version="3"),
        _read("held-by-name.pdf", version="3", product_identifier="Geheimlack"),
        _read("held-by-path.pdf", "/sheets/deep", version="3"),
        _read("held-by-end.pdf", "/sheets/deep", version=None),
        _read("held-and-same.pdf"),
    ]
    held = tmp_path / "held-back.txt"
    held.write_text(
        "# held back\n"
        "held-by-name.pdf\n"
        "\n"
        "/sheets/deep/held-by-path.pdf\n"
        "deep/held-by-end.pdf\n"
        "held-and-same.pdf\n"
    )
    details = tmp_path / "details.jsonl"
    argv = ["--count-only-from", str(held), "--details", str(details)]

    code, text, _ = _diff(capsys, tmp_path, before, after, *argv)
    _, out, _ = _diff(capsys, tmp_path, before, after, *argv, "--json")

    counted = json.loads(out)
    assert code == 1
    assert counted["files"]["differing"] == 1
    assert counted["files"]["differing_counted_only"] == 3
    assert counted["fields"]["version"]["changed"] == 1
    assert counted["fields"]["version"]["counted_only"] == {
        "gained": 0,
        "lost": 1,
        "changed": 2,
    }
    assert counted["fields"]["product_identifier"]["counted_only"]["changed"] == 1
    assert counted["fields"]["product_identifier"]["examples"] == []
    assert "Dateien mit Abweichung: 1; nur gezählt: 3" in text
    assert "version, nur gezählt: dazugekommen 0, weggefallen 1, geändert 2" in text
    for shown in (text, out, details.read_text()):
        assert "held-" not in shown
        assert "Geheimlack" not in shown
    assert len(details.read_text().splitlines()) == 1


@pytest.mark.spec("SDW-28")
def test_a_difference_only_in_counted_files_still_fails_the_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    held = tmp_path / "held-back.txt"
    held.write_text("one.pdf\n")

    code, out, _ = _diff(
        capsys,
        tmp_path,
        [_read("one.pdf")],
        [_read("one.pdf", version="3")],
        "--count-only-from",
        str(held),
    )

    assert code == 1
    assert "Keine Abweichung." not in out
    with pytest.raises(SystemExit) as stopped:
        cli.main(
            [
                "diff",
                str(tmp_path / "a.jsonl"),
                str(tmp_path / "b.jsonl"),
                "--count-only-from",
                str(tmp_path / "missing.txt"),
            ]
        )
    assert stopped.value.code == 2
    capsys.readouterr()
