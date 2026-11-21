"""sdb-reader show: what `read` gives as JSON, as a report for a person."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pymupdf
import pytest

from sdb_reader import cli, shipped_catalog, show
from sdb_reader.extraction import ExtractionResult
from sdb_reader.messages import MESSAGE_CODES
from sdb_reader.reading import read_extraction
from sdb_reader.serialise import reading_to_dict

HEAD = """Sicherheitsdatenblatt
gemäß Verordnung (EG) Nr. 1907/2006
Überarbeitet am: 12.03.2024    Version: 4.1
ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
1.1 Produktidentifikator
Handelsname: {name}
1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt
Firma: Nordwerk GmbH
Hafenstraße 1
24000 Musterstadt
Telefon: +49 30 0000000
1.4 Notrufnummer
Giftnotruf: +49 30 19240
ABSCHNITT 2: Mögliche Gefahren
2.1 Einstufung des Stoffs oder Gemischs
{classified}
2.2 Kennzeichnungselemente
Gefahrenpiktogramme: GHS07
Signalwort: Achtung
Gefahrenhinweise
{hazard}
Sicherheitshinweise
P280 Schutzhandschuhe tragen.
P302+P352 BEI BERÜHRUNG MIT DER HAUT: Mit viel Wasser waschen.
Ergänzende Hinweise
EUH208 Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.
2.3 Sonstige Gefahren
Keine.
ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen
Gemisch.
ABSCHNITT 16: Sonstige Angaben
Keine.
"""
PAINT = HEAD.format(
    name="Musterlack seidenmatt",
    classified="Skin Sens. 1, H317",
    hazard="H317 Kann allergische Hautreaktionen verursachen.",
)
HARDENER = HEAD.format(
    name="Musterhärter",
    classified="Skin Irrit. 2, H315",
    hazard="H315 Verursacht Hautreizungen.",
)
# A sheet that names neither product nor supplier, prints no label and is
# dated by its issue only.
BARE = """Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006
Ausgabedatum: 05.06.2023
ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
1.1 Produktidentifikator
ABSCHNITT 2: Mögliche Gefahren
2.1 Einstufung des Stoffs oder Gemischs
Das Gemisch ist nicht eingestuft.
2.2 Kennzeichnungselemente
Keine.
2.3 Sonstige Gefahren
Keine.
ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen
Gemisch.
ABSCHNITT 16: Sonstige Angaben
Keine.
"""
COVER = """Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006
Musterpflege Mix-Display
Deckblatt
Sicherheitsdatenblätter für Kombipackungen
Inhalt
Musterlack seidenmatt
Musterhärter
"""
LEAFLET = "Produktprospekt\nDekorativer Anstrich für Innenräume.\n"

TODAY = date(2026, 1, 1)

PAINT_DE = """{name}
  Sicherheitsdatenblatt, deutsch, 1 Blatt

  Produkt        Musterlack seidenmatt
  Lieferant      Nordwerk GmbH, Hafenstraße 1, 24000 Musterstadt
  Kontakt        +49 30 0000000
  Notruf         Giftnotruf: +49 30 19240
  Überarbeitet   12.03.2024 (Version 4.1)

  Kennzeichnung  Achtung · GHS07
    H317  Kann allergische Hautreaktionen verursachen.
    P280  Schutzhandschuhe tragen.
    P302+P352  BEI BERÜHRUNG MIT DER HAUT: Mit viel Wasser waschen.
    EUH208  Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.

  Braucht ein Sicherheitsdatenblatt: ja

  Hinweise
    - keine
"""
PAINT_EN = """{name}
  Safety data sheet, German, 1 sheet

  Product    Musterlack seidenmatt
  Supplier   Nordwerk GmbH, Hafenstraße 1, 24000 Musterstadt
  Contact    +49 30 0000000
  Emergency  Giftnotruf: +49 30 19240
  Revised    2024-03-12 (version 4.1)

  Labelling  Achtung · GHS07
    H317  Kann allergische Hautreaktionen verursachen.
    P280  Schutzhandschuhe tragen.
    P302+P352  BEI BERÜHRUNG MIT DER HAUT: Mit viel Wasser waschen.
    EUH208  Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.

  Needs a safety data sheet: yes

  Notes
    - none
"""
BARE_DE = """leer.pdf
  Sicherheitsdatenblatt, deutsch, 1 Blatt

  Produkt        nicht genannt
  Lieferant      nicht genannt
  Kontakt        nicht genannt
  Notruf         nicht genannt
  Ausgegeben     05.06.2023

  Kennzeichnung  keine

  Braucht ein Sicherheitsdatenblatt: nein

  Hinweise
    - In Abschnitt 1 wurde kein Name des Lieferanten gefunden.
    - In Abschnitt 1 wurde keine Anschrift des Lieferanten gefunden.
    - In Abschnitt 1 wurde keine Telefonnummer des Lieferanten gefunden.
    - In Abschnitt 1 wurde keine Notrufnummer gefunden.
"""
BARE_EN = """leer.pdf
  Safety data sheet, German, 1 sheet

  Product    not stated
  Supplier   not stated
  Contact    not stated
  Emergency  not stated
  Issued     2023-06-05

  Labelling  none

  Needs a safety data sheet: no

  Notes
    - No supplier name was found in section 1.
    - No supplier address was found in section 1.
    - No supplier telephone number was found in section 1.
    - No emergency telephone number was found in section 1.
"""
MIX_DE = """mix.pdf
  Sicherheitsdatenblatt, deutsch, 2 Blätter
  Vor den Blättern steht ein Deckblatt; es nennt ein Display: „Mix-Display“.

  Blatt 1 von 2
    Produkt        Musterlack seidenmatt
    Lieferant      Nordwerk GmbH, Hafenstraße 1, 24000 Musterstadt
    Kontakt        +49 30 0000000
    Notruf         Giftnotruf: +49 30 19240
    Überarbeitet   12.03.2024 (Version 4.1)

    Kennzeichnung  Achtung · GHS07
      H317  Kann allergische Hautreaktionen verursachen.
      P280  Schutzhandschuhe tragen.
      P302+P352  BEI BERÜHRUNG MIT DER HAUT: Mit viel Wasser waschen.
      EUH208  Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.

    Braucht ein Sicherheitsdatenblatt: ja

  Blatt 2 von 2
    Produkt        Musterhärter
    Lieferant      Nordwerk GmbH, Hafenstraße 1, 24000 Musterstadt
    Kontakt        +49 30 0000000
    Notruf         Giftnotruf: +49 30 19240
    Überarbeitet   12.03.2024 (Version 4.1)

    Kennzeichnung  Achtung · GHS07
      H315  Verursacht Hautreizungen.
      P280  Schutzhandschuhe tragen.
      P302+P352  BEI BERÜHRUNG MIT DER HAUT: Mit viel Wasser waschen.
      EUH208  Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.

    Braucht ein Sicherheitsdatenblatt: ja

  Die Datei als Ganzes
    Braucht ein Sicherheitsdatenblatt: ja
    Ältestes Blatt: Blatt 1, überarbeitet am 12.03.2024

    Hinweise
      - Die Datei enthält Sicherheitsdatenblätter verschiedener Produkte: Musterlack seidenmatt, Musterhärter
      - Die Datei enthält 2 Sicherheitsdatenblätter; ihre Kennzeichnungen sind zusammengeführt.
"""
MIX_EN = """mix.pdf
  Safety data sheet, German, 2 sheets
  A cover page stands in front of the sheets; it names a display: 'Mix-Display'.

  Sheet 1 of 2
    Product    Musterlack seidenmatt
    Supplier   Nordwerk GmbH, Hafenstraße 1, 24000 Musterstadt
    Contact    +49 30 0000000
    Emergency  Giftnotruf: +49 30 19240
    Revised    2024-03-12 (version 4.1)

    Labelling  Achtung · GHS07
      H317  Kann allergische Hautreaktionen verursachen.
      P280  Schutzhandschuhe tragen.
      P302+P352  BEI BERÜHRUNG MIT DER HAUT: Mit viel Wasser waschen.
      EUH208  Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.

    Needs a safety data sheet: yes

  Sheet 2 of 2
    Product    Musterhärter
    Supplier   Nordwerk GmbH, Hafenstraße 1, 24000 Musterstadt
    Contact    +49 30 0000000
    Emergency  Giftnotruf: +49 30 19240
    Revised    2024-03-12 (version 4.1)

    Labelling  Achtung · GHS07
      H315  Verursacht Hautreizungen.
      P280  Schutzhandschuhe tragen.
      P302+P352  BEI BERÜHRUNG MIT DER HAUT: Mit viel Wasser waschen.
      EUH208  Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.

    Needs a safety data sheet: yes

  The file as a whole
    Needs a safety data sheet: yes
    Oldest sheet: sheet 1, revised 2024-03-12

    Notes
      - The file holds safety data sheets of different products: Musterlack seidenmatt, Musterhärter
      - The file holds 2 safety data sheets; their labels are combined.
"""


def _pdf(path: Path, *pages: str) -> Path:
    with pymupdf.open() as doc:
        for text in pages:
            doc.new_page().insert_text((72, 72), text, fontsize=8)
        doc.save(path)
    return path


def _show(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = cli.main(["show", *argv])
    out, err = capsys.readouterr()
    return code, out, err


def _record(text: str, language: str = "de") -> dict[str, Any]:
    """The record `read` gives for a file with this text."""
    extraction = ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=2,
        warnings=[],
        metadata={},
    )
    return reading_to_dict(
        read_extraction(extraction), catalog=shipped_catalog(language), today=TODAY
    )


def _report(text: str, name: str, language: str = "de") -> str:
    record = _record(text, language)
    return "\n".join(show.report(record, name, shipped_catalog(language))) + "\n"


@pytest.mark.spec("SDW-37", "SDW-38")
@pytest.mark.parametrize(("language", "expected"), [("de", PAINT_DE), ("en", PAINT_EN)])
def test_a_file_named_singly_gets_the_full_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], language: str, expected: str
) -> None:
    path = _pdf(tmp_path / "musterlack.pdf", PAINT)

    code, out, err = _show(capsys, "--lang", language, str(path))

    assert code == 0
    assert out == expected.format(name=path)
    assert err == ""


@pytest.mark.spec("SDW-37")
def test_the_report_says_what_the_record_of_read_says(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One reading: the report is the record of `read`, worded."""
    path = _pdf(tmp_path / "musterlack.pdf", PAINT, HARDENER)

    cli.main(["read", str(path)])
    [record] = json.loads(capsys.readouterr().out)
    _, out, _ = _show(capsys, str(path))

    assert out == "\n".join(show.report(record, str(path), shipped_catalog())) + "\n"


@pytest.mark.spec("SDW-37")
def test_show_takes_what_read_takes_to_choose_files_and_nothing_to_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _pdf(tmp_path / "a.pdf", PAINT)
    _pdf(tmp_path / "b.pdf", HARDENER)
    skip = tmp_path / "skip.txt"
    skip.write_text("b.pdf\n", encoding="utf-8")

    code, out, _ = _show(
        capsys, "--exclude-from", str(skip), "--max-pages", "1", str(tmp_path)
    )

    assert code == 0
    assert "a.pdf" in out
    assert "b.pdf" not in out
    for option in ("--output", "--resume", "--indent", "--include-raw-text"):
        with pytest.raises(SystemExit) as stopped:
            cli.main(["show", option, str(tmp_path)])
        assert stopped.value.code == 2
    capsys.readouterr()


@pytest.mark.spec("SDW-37")
def test_a_call_that_cannot_run_ends_with_2_before_reading(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stopped:
        cli.main(["show", str(tmp_path / "missing.pdf")])

    assert stopped.value.code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.spec("SDW-37", "SDW-38")
def test_a_file_without_text_is_in_the_report_and_fails_the_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "kaputt.pdf"
    broken.write_bytes(b"not a pdf")

    code, out, err = _show(capsys, str(broken))

    assert code == 1
    lines = out.splitlines()
    assert lines[:2] == [str(broken), "  Nicht lesbar"]
    assert lines[2].startswith("    - Die Datei lässt sich nicht als PDF öffnen")
    # Its reason stands in the report and is not said a second time.
    assert err == ""


@pytest.mark.spec("SDW-37", "SDW-40")
def test_a_file_that_breaks_the_reader_is_named_and_costs_only_itself(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good = _pdf(tmp_path / "good.pdf", PAINT)
    bad = _pdf(tmp_path / "bad.pdf", PAINT)
    read = cli.read_sheet

    def breaking(path, **kwargs):  # type: ignore[no-untyped-def]
        if path.name == "bad.pdf":
            raise RuntimeError("parser broke")
        return read(path, **kwargs)

    monkeypatch.setattr(cli, "read_sheet", breaking)

    code, out, err = _show(capsys, str(bad), str(good))

    assert code == 1
    assert out.startswith(
        f"{bad}\n  Beim Lesen ist ein Fehler aufgetreten; "
        "Näheres steht in der Fehlerausgabe.\n\n"
    )
    assert f"{good}\n  Sicherheitsdatenblatt, deutsch, 1 Blatt" in out
    assert "bad.pdf: RuntimeError: parser broke" in err
    assert out.rstrip().endswith(
        "Dateien: 2; Sicherheitsdatenblätter: 1; andere Dokumente: 0; "
        "nicht lesbar: 1; mit Hinweisen: 0; ausgenommen: 0"
    )


@pytest.mark.spec("SDW-38")
def test_a_file_that_is_no_sheet_says_what_it_is_and_why(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _pdf(tmp_path / "prospekt.pdf", LEAFLET)

    code, out, _ = _show(capsys, str(path))

    assert code == 0
    assert out == (
        f"{path}\n"
        "  Kein Sicherheitsdatenblatt\n"
        "    - Das Dokument hat weder den Titel noch den Aufbau eines "
        "Sicherheitsdatenblatts.\n"
    )


@pytest.mark.spec("SDW-38")
@pytest.mark.parametrize(
    ("kind", "said"),
    [
        ("safety-information", "Sicherheitsinformation, kein Sicherheitsdatenblatt"),
        (
            "safety-data-sheet-other-language",
            "Sicherheitsdatenblatt in einer anderen Sprache",
        ),
    ],
)
def test_each_kind_of_file_is_named_with_the_verdicts_reasons(
    kind: str, said: str
) -> None:
    record = _record(LEAFLET)
    record["verification"]["kind"] = kind
    record["verification"]["errors"] = [
        {"code": "other-language", "params": {}, "message": "Der Grund."}
    ]
    record["findings"] = [
        {"code": "not-german", "params": {}, "message": "Der Befund."},
        {"code": "not-german", "params": {}, "message": "Der Grund."},
    ]

    assert show.report(record, "x.pdf", shipped_catalog()) == [
        "x.pdf",
        f"  {said}",
        "    - Der Grund.",
        "    - Der Befund.",
    ]
    assert show.line(record, "x.pdf", shipped_catalog()) == f"x.pdf: {said}"
    # A verdict without a reason of its own gives its doubts instead.
    record["verification"]["errors"] = record["findings"] = []
    assert show.report(record, "x.pdf", shipped_catalog())[2].startswith("    - ")


@pytest.mark.spec("SDW-38", "SDW-41")
@pytest.mark.parametrize(("language", "expected"), [("de", BARE_DE), ("en", BARE_EN)])
def test_what_a_sheet_does_not_state_is_said_in_the_catalogs_words(
    language: str, expected: str
) -> None:
    """No product, no supplier, no label, an issue date only: never an empty
    line and never a value of the program's own."""
    report = _report(BARE, "leer.pdf", language)

    assert report == expected
    assert "None" not in report


@pytest.mark.spec("SDW-38")
def test_the_contact_names_phone_and_e_mail_and_the_office_where_it_differs() -> None:
    record = _record(PAINT)
    contact = record["sheet"]["contact_info"]
    contact.update(
        supplier_email="info@nordwerk.example",
        information_email="sdb@nordwerk.example",
    )

    def contact_line() -> str:
        report = show.report(record, "x.pdf", shipped_catalog())
        return next(line for line in report if line.startswith("  Kontakt"))

    assert contact_line() == (
        "  Kontakt        +49 30 0000000, info@nordwerk.example, "
        "Auskunft: sdb@nordwerk.example"
    )
    # The same address twice is said once.
    contact["information_email"] = "info@nordwerk.example"
    assert contact_line() == "  Kontakt        +49 30 0000000, info@nordwerk.example"
    # The office's address alone is still the office's.
    contact.update(supplier_phone=None, supplier_email=None)
    contact["information_email"] = "sdb@nordwerk.example"
    assert contact_line() == "  Kontakt        Auskunft: sdb@nordwerk.example"
    english = show.report(record, "x.pdf", shipped_catalog("en"))
    assert "  Contact    information: sdb@nordwerk.example" in english


@pytest.mark.spec("SDW-38")
def test_notes_that_only_repeat_a_missing_label_are_left_out_by_their_code() -> None:
    """For a sheet that prints no label; `read` keeps them, and a label that
    lacks one kind of statement keeps its note."""
    bare = _record(BARE)
    codes = [warning["code"] for warning in bare["parser"]["warnings"]]
    assert {"no-hazard-codes", "no-precautionary-codes"} <= set(codes)
    # By the code, never by the wording: other words change nothing.
    for warning in bare["parser"]["warnings"]:
        warning["message"] = f"Satz zu {warning['code']}"

    report = show.report(bare, "leer.pdf", shipped_catalog())

    assert "    - Satz zu no-hazard-codes" not in report
    assert "    - Satz zu no-precautionary-codes" not in report
    assert "    - Satz zu no-supplier-name" in report
    assert show.notes_count(bare) == len(codes) - 2

    labelled = _record(
        PAINT.replace("P280 Schutzhandschuhe tragen.\n", "").replace(
            "P302+P352 BEI BERÜHRUNG MIT DER HAUT: Mit viel Wasser waschen.\n", ""
        )
    )
    assert "no-precautionary-codes" in [
        warning["code"] for warning in labelled["parser"]["warnings"]
    ]
    assert "    - Die Kennzeichnung trägt keinen P-Satz." in show.report(
        labelled, "x.pdf", shipped_catalog()
    )


@pytest.mark.spec("SDW-39")
def test_a_sheet_of_several_without_a_label_drops_the_notes_for_itself_only() -> None:
    record = _record(COVER + PAINT + HARDENER)
    note = {"code": "no-hazard-codes", "params": {}, "message": "Kein H-Satz."}
    for part in record["parts"]:
        part["warnings"] = [note]
    record["parts"][1]["statements"] = []
    record["parts"][1]["sheet"]["hazard_statements"].update(
        signal_word=None, pictograms=[]
    )

    report = show.report(record, "mix.pdf", shipped_catalog())

    assert report.count("      - Kein H-Satz.") == 1
    second = report[report.index("  Blatt 2 von 2") :]
    assert "    Kennzeichnung  keine" in second
    assert "      - Kein H-Satz." not in second


@pytest.mark.spec("SDW-38")
def test_a_statement_takes_the_sheets_wording_then_the_regulations_then_none() -> None:
    record = _record(PAINT)
    record["statements"] = [
        {"code": "H317", "sheet": "Wie das Blatt\nes druckt.", "regulation": "Anders."},
        {"code": "H315", "sheet": None, "regulation": "Verursacht Hautreizungen."},
        {"code": "P280", "sheet": None, "regulation": None},
    ]

    report = show.report(record, "x.pdf", shipped_catalog())

    start = report.index("  Kennzeichnung  Achtung · GHS07")
    assert report[start + 1 : start + 4] == [
        "    H317  Wie das Blatt es druckt.",
        "    H315  Verursacht Hautreizungen.",
        "    P280",
    ]


@pytest.mark.spec("SDW-38")
def test_a_sheet_that_calls_itself_voluntary_or_its_product_an_article_says_so() -> (
    None
):
    record = _record(PAINT)
    record["sheet"].update(
        sheet_required=False, stated_voluntary=True, stated_article=True
    )

    report = show.report(record, "x.pdf", shipped_catalog())

    start = report.index("  Braucht ein Sicherheitsdatenblatt: nein")
    assert report[start + 1 : start + 3] == [
        "    Das Blatt nennt sich freiwillig ausgestellt oder nicht vorgeschrieben.",
        "    Das Blatt nennt sein Produkt ein Erzeugnis.",
    ]


@pytest.mark.spec("SDW-38")
def test_a_label_with_a_signal_word_and_nothing_else_names_what_is_missing() -> None:
    record = _record(PAINT)
    record["statements"] = []
    record["sheet"]["hazard_statements"]["pictograms"] = []

    report = show.report(record, "x.pdf", shipped_catalog())

    start = report.index("  Kennzeichnung  Achtung · keine Piktogramme")
    assert report[start + 1] == "    keine H-, P- oder EUH-Sätze"


@pytest.mark.spec("SDW-38")
def test_the_verdicts_doubts_about_a_sheet_and_the_embedded_file_stay_in_read() -> None:
    record = _record(PAINT)
    record["verification"]["warnings"] = [
        {"code": "short-sample", "params": {}, "message": "Zweifel der Prüfung."}
    ]
    record["embedded_data"] = {"format": "eSDScom", "filename": "sds.xml"}

    report = "\n".join(show.report(record, "x.pdf", shipped_catalog()))

    assert "Zweifel der Prüfung." not in report
    assert "sds.xml" not in report


@pytest.mark.spec("SDW-39")
@pytest.mark.parametrize(("language", "expected"), [("de", MIX_DE), ("en", MIX_EN)])
def test_a_file_of_several_sheets_shows_each_and_then_the_file(
    language: str, expected: str
) -> None:
    assert _report(COVER + PAINT + HARDENER, "mix.pdf", language) == expected


@pytest.mark.spec("SDW-39")
def test_a_note_stands_with_every_sheet_that_carries_it_and_not_with_the_file() -> None:
    record = _record(COVER + PAINT + HARDENER)
    shared = {"code": "no-precautionary-codes", "params": {}, "message": "Geteilt."}
    own = {"code": "no-hazard-codes", "params": {}, "message": "Nur das zweite."}
    record["parts"][0]["warnings"] = [shared]
    record["parts"][1]["warnings"] = [shared, own]
    record["parser"]["warnings"] = [shared, own, *record["parser"]["warnings"]]

    report = show.report(record, "mix.pdf", shipped_catalog())

    assert report.count("      - Geteilt.") == 2
    assert report.count("      - Nur das zweite.") == 1
    whole = report[report.index("  Die Datei als Ganzes") :]
    assert not any("Geteilt." in line or "Nur das" in line for line in whole)
    # A cover page that names no display is said without one.
    record["display_term"] = None
    assert show.report(record, "mix.pdf", shipped_catalog())[2] == (
        "  Vor den Blättern steht ein Deckblatt; es wird nicht gelesen."
    )
    assert show.notes_count(record) == 5


def _dated(sheet: str, day: str) -> str:
    """The sheet, revised on another day."""
    return sheet.replace("12.03.2024", day)


@pytest.mark.spec("SDW-45")
@pytest.mark.parametrize(
    ("text", "oldest", "line"),
    [
        (
            PAINT + _dated(HARDENER, "12.03.2014"),
            {"sheet": 2, "date": "2014-03-12", "dated_by": "revision"},
            "Ältestes Blatt: Blatt 2, überarbeitet am 12.03.2014",
        ),
        (
            PAINT + BARE,
            {"sheet": 2, "date": "2023-06-05", "dated_by": "issue"},
            "Ältestes Blatt: Blatt 2, ausgegeben am 05.06.2023",
        ),
        # A date after the day of the run does not count.
        (
            _dated(PAINT, "12.03.2027") + HARDENER,
            {"sheet": 2, "date": "2024-03-12", "dated_by": "revision"},
            "Ältestes Blatt: Blatt 2, überarbeitet am 12.03.2024",
        ),
        # Of two sheets of the same date, the first.
        (
            PAINT + HARDENER,
            {"sheet": 1, "date": "2024-03-12", "dated_by": "revision"},
            "Ältestes Blatt: Blatt 1, überarbeitet am 12.03.2024",
        ),
    ],
)
def test_a_file_of_several_sheets_names_the_sheet_with_the_oldest_date(
    text: str, oldest: dict[str, Any], line: str
) -> None:
    record = _record(text)

    assert record["oldest_sheet"] == oldest
    whole = show.report(record, "x.pdf", shipped_catalog())
    whole = whole[whole.index("  Die Datei als Ganzes") :]
    assert whole[2] == "    " + line


@pytest.mark.spec("SDW-45")
def test_the_oldest_sheet_is_null_where_no_sheet_carries_a_date_that_counts() -> None:
    record = _record(
        _dated(PAINT, "12.03.2027") + _dated(HARDENER, "01.01.2028"), language="en"
    )

    assert record["oldest_sheet"] is None
    assert "    Oldest sheet: none carries a date" in show.report(
        record, "x.pdf", shipped_catalog("en")
    )


@pytest.mark.spec("SDW-45")
def test_the_oldest_sheet_leaves_the_file_s_reading_and_findings_as_they_were() -> None:
    record = _record(PAINT + _dated(HARDENER, "12.03.2014"))

    # The file is dated by the newest date it names (SDB-20).
    assert record["sheet"]["revision_date"] == "2024-03-12"
    assert "predates-annex-ii" not in {f["code"] for f in record["findings"]}
    # A file of one sheet has no oldest sheet.
    assert "oldest_sheet" not in _record(PAINT)


@pytest.mark.spec("SDB-179")
def test_a_date_in_the_future_does_not_leave_a_file_of_several_sheets_undated() -> None:
    record = _record(_dated(PAINT, "12.03.2027") + _dated(HARDENER, "12.03.2014"))

    # The date in the future is no date: the file's is the newest that can
    # be right, the hardener's, and a finding names the other.
    assert record["sheet"]["revision_date"] == "2014-03-12"
    assert record["parts"][0]["sheet"]["revision_date"] is None
    codes = [f["code"] for f in record["findings"]]
    assert "revised-in-future" in codes
    assert "undated" not in codes
    assert "predates-annex-ii" in codes

    # Where no sheet names such a date, the file stays undated.
    none = _record(_dated(PAINT, "12.03.2027") + _dated(HARDENER, "01.01.2028"))
    assert "undated" in {f["code"] for f in none["findings"]}


@pytest.mark.spec("SDW-46")
def test_each_sheet_of_a_file_carries_the_findings_on_its_own_age() -> None:
    record = _record(PAINT + _dated(HARDENER, "12.03.2014"))

    first, second = record["parts"]
    assert first["findings"] == []
    assert [f["code"] for f in second["findings"]] == ["predates-annex-ii"]
    assert second["findings"][0]["params"] == {"revised": "2014-03-12"}

    future = _record(PAINT + _dated(HARDENER, "12.03.2027"))["parts"][1]
    assert [f["code"] for f in future["findings"]] == ["revised-in-future", "undated"]


@pytest.mark.spec("SDW-46")
def test_a_sheet_s_age_stands_with_the_sheet_and_not_again_with_the_file() -> None:
    record = _record(PAINT + _dated(HARDENER, "12.03.2027"))
    sentence = "      - " + record["parts"][1]["findings"][0]["message"]

    report = show.report(record, "x.pdf", shipped_catalog())

    whole = report.index("  Die Datei als Ganzes")
    assert report.index(sentence) < whole
    assert report.count(sentence) == 1


@pytest.mark.spec("SDW-40")
def test_a_directory_gives_a_line_per_file_and_a_closing_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "bestand"
    folder.mkdir()
    (folder / "kaputt.pdf").write_bytes(b"not a pdf")
    _pdf(folder / "leer.pdf", BARE)
    _pdf(folder / "musterlack.pdf", PAINT)
    _pdf(folder / "prospekt.pdf", LEAFLET)
    _pdf(folder / "zwei.pdf", PAINT, HARDENER)

    code, out, err = _show(capsys, str(folder))

    assert code == 1
    assert out == (
        f"{folder}/kaputt.pdf: Nicht lesbar\n"
        f"{folder}/leer.pdf: Sicherheitsdatenblatt, deutsch, 1 Blatt · "
        "Produkt nicht genannt · 05.06.2023 · 5 Hinweise\n"
        f"{folder}/musterlack.pdf: Sicherheitsdatenblatt, deutsch, 1 Blatt · "
        "Musterlack seidenmatt · 12.03.2024 · 0 Hinweise\n"
        f"{folder}/prospekt.pdf: Kein Sicherheitsdatenblatt\n"
        f"{folder}/zwei.pdf: Sicherheitsdatenblatt, deutsch, 2 Blätter · "
        "Musterlack seidenmatt (12.03.2024); Musterhärter (12.03.2024) · "
        "2 Hinweise\n"
        "\n"
        "Dateien: 5; Sicherheitsdatenblätter: 3; andere Dokumente: 1; "
        "nicht lesbar: 1; mit Hinweisen: 2; ausgenommen: 0\n"
    )
    assert err == ""


@pytest.mark.spec("SDW-40")
def test_a_sheet_without_a_date_and_one_note_are_said_so_in_the_line() -> None:
    record = _record(BARE.replace("Ausgabedatum: 05.06.2023\n", ""), "en")
    record["findings"] = record["findings"][:1]
    record["parser"]["warnings"] = []

    assert show.line(record, "x.pdf", shipped_catalog("en")) == (
        "x.pdf: Safety data sheet, German, 1 sheet · product not stated · "
        "undated · 1 note"
    )


@pytest.mark.spec("SDW-40")
@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (
            "de",
            "mix.pdf: Sicherheitsdatenblatt, deutsch, 2 Blätter · "
            "mit Deckblatt (Display: „Mix-Display“) · "
            "Musterlack seidenmatt (12.03.2024); Musterhärter (12.03.2024) · "
            "2 Hinweise",
        ),
        (
            "en",
            "mix.pdf: Safety data sheet, German, 2 sheets · "
            "with a cover page (display: 'Mix-Display') · "
            "Musterlack seidenmatt (2024-03-12); Musterhärter (2024-03-12) · "
            "2 notes",
        ),
    ],
)
def test_the_line_of_a_file_of_several_sheets_names_every_sheet(
    language: str, expected: str
) -> None:
    record = _record(COVER + PAINT + HARDENER, language)

    assert show.line(record, "mix.pdf", shipped_catalog(language)) == expected


@pytest.mark.spec("SDW-40")
def test_a_sheet_of_several_without_product_or_date_is_said_so_in_the_line() -> None:
    record = _record(COVER + PAINT + HARDENER)
    record["display_term"] = None
    record["parts"][0]["sheet"]["product_identifier"] = None
    record["parts"][1]["sheet"].update(revision_date=None, issue_date=None)

    assert show.line(record, "mix.pdf", shipped_catalog()) == (
        "mix.pdf: Sicherheitsdatenblatt, deutsch, 2 Blätter · mit Deckblatt · "
        "Produkt nicht genannt (12.03.2024); Musterhärter (ohne Datum) · 2 Hinweise"
    )
    record["cover_page"] = False
    assert " · mit Deckblatt" not in show.line(record, "mix.pdf", shipped_catalog())


@pytest.mark.spec("SDW-40")
def test_files_and_directories_mix_and_a_file_named_itself_gets_the_full_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "bestand"
    folder.mkdir()
    first = _pdf(folder / "a.pdf", PAINT)
    _pdf(folder / "b.pdf", HARDENER)
    _pdf(folder / "c.pdf", HARDENER)
    skip = tmp_path / "skip.txt"
    skip.write_text("c.pdf\n", encoding="utf-8")

    code, out, _ = _show(
        capsys, "--lang", "en", "--exclude-from", str(skip), str(folder), str(first)
    )

    assert code == 0
    assert out == (
        PAINT_EN.format(name=first)
        + "\n"
        + f"{folder}/b.pdf: Safety data sheet, German, 1 sheet · Musterhärter · "
        "2024-03-12 · 0 notes\n"
        "\n"
        "files: 2; safety data sheets: 2; other documents: 0; not readable: 0; "
        "with notes: 0; excluded: 1\n"
    )


@pytest.mark.spec("SDW-37", "SDW-40")
def test_the_reports_stand_in_the_order_of_the_call_whatever_ends_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    names = [f"{letter}.pdf" for letter in "abcdef"]
    for name in names:
        _pdf(tmp_path / name, PAINT)

    _, one, _ = _show(capsys, str(tmp_path))
    code, several, _ = _show(capsys, "--jobs", "3", str(tmp_path))

    assert code == 0
    assert several == one
    assert [line.split(": ")[0] for line in one.splitlines()[:6]] == [
        str(tmp_path / name) for name in names
    ]


@pytest.mark.spec("SDW-37")
def test_an_interrupt_ends_the_run_with_130_and_says_how_far_it_came(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _pdf(tmp_path / "a.pdf", PAINT)
    second = _pdf(tmp_path / "b.pdf", PAINT)
    read = cli.read_sheet

    def interrupted(path, **kwargs):  # type: ignore[no-untyped-def]
        if path.name == "b.pdf":
            raise KeyboardInterrupt
        return read(path, **kwargs)

    monkeypatch.setattr(cli, "read_sheet", interrupted)

    code, out, err = _show(capsys, str(first), str(second))

    assert code == 130
    assert out.startswith(f"{first}\n")
    assert err == "[sdb-reader] Abgebrochen nach 1 von 2 Dateien.\n"


@pytest.mark.spec("SDW-41")
def test_every_word_that_is_not_the_sheets_comes_from_the_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A catalog of one's own words the whole report: nothing is fixed in
    the program but the layout."""
    own = tmp_path / "xx.toml"
    codes = [code for code in MESSAGE_CODES if code.startswith("show-")]
    own.write_text(
        '[format]\ndate = "%d/%m/%y"\n\n[messages]\n'
        + "".join(
            f'"{code}" = "«{code}'
            + "".join(f" {{{name}}}" for name in MESSAGE_CODES[code])
            + '»"\n'
            for code in codes
        ),
        encoding="utf-8",
    )
    folder = tmp_path / "bestand"
    folder.mkdir()
    paths = [
        _pdf(folder / "zwei.pdf", PAINT, HARDENER),
        _pdf(folder / "leer.pdf", BARE),
        _pdf(folder / "einzeln.pdf", PAINT),
    ]

    _, out, _ = _show(
        capsys, "--messages", str(own), str(paths[0]), str(paths[1]), str(folder)
    )

    sheet_words = {
        "Musterlack seidenmatt",
        "Musterhärter",
        "Nordwerk GmbH, Hafenstraße 1, 24000 Musterstadt",
        "Achtung",
        "GHS07",
        "4.1",
        "+49 30 0000000",
        "Giftnotruf: +49 30 19240",
    }
    for line in out.splitlines():
        text = line.strip()
        if not text or re.match(r"(H|P|EUH)\d", text):
            continue
        # What is left of a line without the catalog's sentences, the
        # sheet's own values and the path is layout: indentation, the dash
        # of a list, the dot between two values.
        rest = text
        while re.search(r"«[^«»]*»", rest):
            rest = re.sub(r"«[^«»]*»", "", rest)
        for word in sorted(sheet_words, key=len, reverse=True):
            rest = rest.replace(word, "")
        for path in paths:
            rest = rest.replace(str(path), "")
        # A note is a message of `read`, said in English where the
        # caller's catalog lacks it (BIB-11).
        if text.startswith("- ") and "«" not in text:
            continue
        assert re.fullmatch(r"[\s·,:\-]*", rest), line
    assert "«show-date 12/03/24»" in out
    assert "«show-not-stated»" in out
    assert "«show-summary 3 3 0 0 2 0»" in out


@pytest.mark.spec("SDW-41")
def test_the_report_is_plain_text_and_a_value_stands_on_one_line() -> None:
    long_name = "Musterlack " + "sehr " * 60 + "lang"
    record = _record(PAINT.replace("Musterlack seidenmatt", long_name))
    record["sheet"]["product_identifier"] = long_name.replace(" lang", "\nlang")

    report = show.report(record, "x.pdf", shipped_catalog())

    assert f"  Produkt        {long_name}" in report
    for line in report:
        assert "\n" not in line
        assert line == line.rstrip()
        assert not re.search(r"[\x00-\x1f\x7f]", line)


@pytest.mark.spec("SDW-41")
def test_the_report_is_said_to_be_for_people_and_not_promised() -> None:
    root = Path(__file__).resolve().parents[1]
    page = (root / "docs" / "api" / "stability.md").read_text(encoding="utf-8")
    not_promised = page[page.index("## Not promised") :]

    assert "`show`" in not_promised[: not_promised.index("\n## ")]
    for manual in ("docs/usage/showing.md", "docs/bedienung/anzeigen.md"):
        assert "`read`" in (root / manual).read_text(encoding="utf-8")
