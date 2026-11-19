"""Messages carry codes; their sentences come from catalogs (specs/bibliothek.md)."""

from __future__ import annotations

import ast
import json
import re
from importlib import resources
from pathlib import Path

import pymupdf
import pytest

import sdb_reader
from sdb_reader import (
    MESSAGE_CODES,
    Catalog,
    Message,
    cli,
    extraction_from_dict,
    extraction_to_dict,
    load_catalog,
    read_extraction,
    reading_to_dict,
    sheet_findings,
    shipped_catalog,
)
from sdb_reader.messages import placeholders, shipped_languages

SHEET = """Sicherheitsdatenblatt
ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
Produktname: Bad- und Küchenfarbe
ABSCHNITT 2: Mögliche Gefahren
Verordnung (EG) Nr. 1907/2006
H412: Schädlich für Wasserorganismen, mit langfristiger Wirkung.
P101: Ist ärztlicher Rat erforderlich, Verpackung oder Kennzeichnungsetikett bereithalten.
"""
SOURCES = sorted(Path(sdb_reader.__file__).parent.glob("*.py"))


def _reading() -> sdb_reader.SheetReading:
    return read_extraction(
        extraction_from_dict(
            {"text": SHEET, "extractor": "pymupdf", "pages_sampled": 1, "warnings": []}
        )
    )


def _pdf(path: Path, text: str) -> Path:
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), text)
        doc.save(path)
    return path


def _codes_built_in_the_package() -> set[str]:
    """Every code the package's code builds a Message with, or names for one."""
    built: set[str] = set()
    for source in SOURCES:
        tree = ast.parse(source.read_text("utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in MESSAGE_CODES:
                built.add(node.value)
    return built


@pytest.mark.spec("BIB-10")
def test_a_message_takes_a_known_code_and_exactly_its_values() -> None:
    assert Message("several-sheets", {"count": 2}).params == {"count": 2}
    with pytest.raises(ValueError, match="unknown message code"):
        Message("no-such-code")
    with pytest.raises(ValueError, match="takes"):
        Message("several-sheets")
    with pytest.raises(ValueError, match="takes"):
        Message("undated", {"count": 2})


@pytest.mark.spec("BIB-10")
def test_codes_are_short_english_words_with_hyphens_and_all_in_use() -> None:
    for code, names in MESSAGE_CODES.items():
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", code), code
        assert all(re.fullmatch(r"[a-z_]+", name) for name in names), code
    assert _codes_built_in_the_package() == set(MESSAGE_CODES)


@pytest.mark.spec("BIB-10")
def test_everything_noted_about_a_file_is_a_message(tmp_path: Path) -> None:
    """Warnings of reading, judging and parsing, the reasons of an unreadable
    file, and the findings."""
    reading = _reading()
    assert reading.parser_result is not None
    noted = [
        *reading.verification.warnings,
        *reading.parser_result.warnings,
        *sheet_findings(reading.parser_result.sheet, reading.parser_result.warnings),
    ]
    blank = tmp_path / "blank.pdf"
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(blank)
    unreadable = sdb_reader.read_sheet(blank)
    noted += [*unreadable.warnings, *unreadable.errors, *unreadable.verification.errors]

    assert noted
    assert all(isinstance(message, Message) for message in noted)
    assert {"short-sample", "no-emergency-phone", "undated", "unreadable"} <= {
        message.code for message in noted
    }
    assert json.dumps([message.to_dict() for message in noted])


@pytest.mark.spec("BIB-11")
@pytest.mark.parametrize("language", ["de", "en"])
def test_a_shipped_catalog_knows_every_code_and_every_value(language: str) -> None:
    assert set(shipped_languages()) == {"de", "en"}
    sentences = shipped_catalog(language).sentences

    assert set(sentences) == set(MESSAGE_CODES)
    for code, names in MESSAGE_CODES.items():
        entry = sentences[code]
        forms = [entry] if isinstance(entry, str) else list(entry.values())
        # The sentence for any number names every value; the one for exactly
        # one may leave the count out ("Eine Seite …").
        assert placeholders(forms[-1]) == set(names), code
        for form in forms:
            assert placeholders(form) <= set(names), code


@pytest.mark.spec("BIB-11")
def test_the_language_is_named_and_german_unless_asked() -> None:
    message = Message("several-sheets", {"count": 2})

    assert shipped_catalog().language == "de"
    assert shipped_catalog().render(message) == (
        "Die Datei enthält 2 Sicherheitsdatenblätter; ihre Kennzeichnungen sind "
        "zusammengeführt."
    )
    assert shipped_catalog("en").render(message) == (
        "The file holds 2 safety data sheets; their labels are combined."
    )
    with pytest.raises(ValueError, match="no message catalog for 'fr'"):
        shipped_catalog("fr")


@pytest.mark.spec("BIB-11")
def test_the_machines_language_plays_no_part(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE"):
        monkeypatch.setenv(name, "en_US.UTF-8")

    record = reading_to_dict(_reading())

    assert record["findings"][0]["message"].startswith("Das Blatt trägt kein")


@pytest.mark.spec("BIB-11")
def test_a_callers_catalog_may_be_incomplete_and_must_be_right(
    tmp_path: Path,
) -> None:
    own = tmp_path / "nl.toml"
    own.write_text('[messages]\n"undated" = "Geen leesbare datum."\n', "utf-8")
    catalog = load_catalog(own)

    assert catalog.language == "nl"
    assert catalog.render(Message("undated")) == "Geen leesbare datum."
    # What it lacks is said in English.
    assert catalog.render(Message("no-supplier-name")) == (
        "No supplier name was found in section 1."
    )

    own.write_text('[messages]\n"no-such-code" = "x"\n', "utf-8")
    with pytest.raises(ValueError, match="unknown message code"):
        load_catalog(own)
    own.write_text('[messages]\n"undated" = "{statement}"\n', "utf-8")
    with pytest.raises(ValueError, match="does not carry"):
        load_catalog(own)


@pytest.mark.spec("BIB-12")
def test_nothing_decides_by_the_wording_of_a_message() -> None:
    """The same reading under a catalog whose every sentence is empty: the
    findings are the same, since they come from codes."""
    reading = _reading()
    assert reading.parser_result is not None
    silent = Catalog("none", dict.fromkeys(MESSAGE_CODES, ""))

    with_sentences = reading_to_dict(reading)
    without = reading_to_dict(reading, catalog=silent)

    def stripped(record: dict) -> str:
        return re.sub(r'"message": "[^"]*"', '"message": ""', json.dumps(record))

    assert stripped(with_sentences) == stripped(without)
    # And no module reads a sentence back: none asks a message for its text.
    for source in SOURCES:
        text = source.read_text("utf-8")
        assert ".startswith(LABEL" not in text, source.name
        assert "in warning" not in text, source.name


@pytest.mark.spec("BIB-3", "BIB-10")
def test_a_stored_text_keeps_codes_and_one_stored_before_them_is_still_read() -> None:
    extraction = extraction_from_dict(
        {
            "text": SHEET,
            "extractor": "pymupdf+ocr",
            "pages_sampled": 1,
            "warnings": [
                "No text layer; read by OCR. Expect spacing artefacts -- "
                "normalise_pdf_text repairs the common ones.",
                "2 page(s) without a text layer read by OCR.",
                "Extracted text is unusually short; document may be incomplete "
                "or scanned.",
                "Something a later version no longer says.",
                {"code": "read-by-ocr-single-characters", "params": {}},
            ],
        }
    )

    assert extraction.warnings == [
        Message("read-by-ocr-no-text-layer"),
        Message("pages-read-by-ocr", {"pages": 2}),
        Message("short-text"),
        Message("unknown", {"text": "Something a later version no longer says."}),
        Message("read-by-ocr-single-characters"),
    ]
    stored = extraction_to_dict(extraction)["warnings"]
    assert stored[1] == {"code": "pages-read-by-ocr", "params": {"pages": 2}}
    assert all(set(warning) == {"code", "params"} for warning in stored)


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, list, str]:
    code = cli.main(["read", *argv])
    out, err = capsys.readouterr()
    return code, json.loads(out) if out else [], err


@pytest.mark.spec("SDW-17")
def test_the_command_prints_each_message_with_code_values_and_sentence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(cli.LANGUAGE_VARIABLE, raising=False)
    path = str(_pdf(tmp_path / "farbe.pdf", SHEET))

    _, [german], _ = _run(capsys, path)
    _, [english], _ = _run(capsys, path, "--lang", "en")
    monkeypatch.setenv(cli.LANGUAGE_VARIABLE, "en")
    _, [by_variable], _ = _run(capsys, path)

    [finding] = german["findings"]
    assert finding == {
        "code": "undated",
        "params": {},
        "message": "Das Blatt trägt kein lesbares Überarbeitungs- oder Ausgabedatum.",
    }
    assert english["findings"][0]["message"] == (
        "The sheet carries no revision or issue date that can be read."
    )
    assert by_variable == english
    for part in (
        german["verification"]["warnings"],
        german["extraction"]["warnings"],
        german["parser"]["warnings"],
    ):
        assert part
        assert all(set(message) == {"code", "params", "message"} for message in part)
    # Keys, fixed values and the label's statements are in no language.
    assert german["sheet"] == english["sheet"]
    assert german["statements"] == english["statements"]
    assert german["verification"]["kind"] == "safety-data-sheet"


@pytest.mark.spec("SDW-17")
def test_a_language_without_a_catalog_ends_before_any_file_is_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = str(_pdf(tmp_path / "farbe.pdf", SHEET))
    monkeypatch.setattr(
        cli, "read_sheet", lambda *a, **k: pytest.fail("a file was read")
    )

    with pytest.raises(SystemExit) as ended:
        cli.main(["read", "--lang", "fr", path])

    assert ended.value.code == 2
    assert "no message catalog for 'fr'" in capsys.readouterr().err


@pytest.mark.spec("SDW-17")
def test_a_catalog_of_ones_own_words_output_and_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    own = tmp_path / "nl.toml"
    own.write_text(
        '[messages]\n"undated" = "Geen leesbare datum."\n'
        '"cli-file-failed" = "MISLUKT {path}: {reason}"\n',
        "utf-8",
    )
    blank = tmp_path / "blank.pdf"
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(blank)

    code, records, err = _run(
        capsys, "--messages", str(own), str(_pdf(tmp_path / "a.pdf", SHEET)), str(blank)
    )

    assert code == 1
    assert records[0]["findings"][0]["message"] == "Geen leesbare datum."
    assert err.startswith(f"MISLUKT {blank}: ")


# The codes that have gone, each with the last version that gave it out. The
# list only grows: a program or a stored text that still knows one of them
# must never meet it again with another meaning.
RETIRED_CODES = {
    # The summary of the command `compare`, gone with it.
    "cli-summary-compare": "0.5.0",
}


@pytest.mark.spec("BIB-10")
def test_a_code_that_has_gone_is_not_given_out_again() -> None:
    assert sorted(RETIRED_CODES.keys() & MESSAGE_CODES.keys()) == []


@pytest.mark.spec("SDW-18")
def test_the_output_states_each_value_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, [record], _ = _run(capsys, str(_pdf(tmp_path / "farbe.pdf", SHEET)))

    sheet = record["sheet"]
    for gone in (
        "hazard_statements_text",
        "precautionary_text",
        "supplemental_text",
        "extraction",
        "metadata_version",
    ):
        assert gone not in sheet
    assert sheet["hazard_statements"]["hazard_text"].startswith("H412")
    assert record["extraction"]["extractor"] == "pymupdf"
    schema = json.loads(
        resources.files("sdb_reader").joinpath("read_record.schema.json").read_text()
    )
    assert "metadata_version" not in schema["$defs"]["sheet"]["properties"]


@pytest.mark.spec("BIB-11")
def test_a_message_that_counts_has_a_sentence_for_one_and_for_more() -> None:
    german, english = shipped_catalog("de"), shipped_catalog("en")

    assert german.render(Message("no-text-layer", {"pages": 1})) == (
        "Das PDF hat keine Textschicht (1 Seite angesehen)."
    )
    assert german.render(Message("no-text-layer", {"pages": 3})) == (
        "Das PDF hat keine Textschicht (3 Seiten angesehen)."
    )
    assert english.render(Message("pages-read-by-ocr", {"pages": 1})) == (
        "One page without a text layer was read by text recognition."
    )
    assert english.render(Message("pages-read-by-ocr", {"pages": 0})).startswith(
        "0 pages"
    )


@pytest.mark.spec("BIB-10", "BIB-11")
def test_a_date_stays_iso_in_the_message_and_is_written_the_catalogs_way() -> None:
    message = Message("predates-annex-ii", {"revised": "2019-05-02"})

    assert message.to_dict()["params"] == {"revised": "2019-05-02"}
    assert (
        shipped_catalog("de")
        .render(message)
        .startswith("Überarbeitet am 02.05.2019, vor dem 01.01.2021")
    )
    assert shipped_catalog("en").render(message).startswith("Revised 2019-05-02,")
    assert shipped_catalog("de").to_dict(message)["params"] == {"revised": "2019-05-02"}


@pytest.mark.spec("BIB-11")
def test_a_callers_catalog_may_use_both_forms_and_only_where_they_fit(
    tmp_path: Path,
) -> None:
    own = tmp_path / "kurz.toml"
    own.write_text(
        '[format]\ndate = "%d/%m/%y"\n\n[messages]\n'
        '"several-sheets" = { one = "Ein Blatt.", other = "{count} Blätter." }\n'
        '"old-format" = "Alt seit {revised}."\n',
        "utf-8",
    )
    catalog = load_catalog(own)

    assert catalog.render(Message("several-sheets", {"count": 1})) == "Ein Blatt."
    assert catalog.render(Message("several-sheets", {"count": 4})) == "4 Blätter."
    assert catalog.render(Message("old-format", {"revised": "2022-03-01"})) == (
        "Alt seit 01/03/22."
    )

    for wrong, why in (
        ('[messages]\n"undated" = { one = "a", other = "b" }\n', "counts nothing"),
        ('[messages]\n"several-sheets" = { one = "a" }\n', "neither a sentence"),
        ('[messages]\n"several-sheets" = { other = "{pages}" }\n', "does not carry"),
        ('[format]\ndatum = "x"\n[messages]\n', "takes one entry"),
    ):
        own.write_text(wrong, "utf-8")
        with pytest.raises(ValueError, match=why):
            load_catalog(own)
