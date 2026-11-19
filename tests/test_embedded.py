"""The eSDScom data embedded in a PDF is read and compared, never used (SDW-11)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pymupdf
import pytest

from sdb_reader import cli
from sdb_reader.embedded import EmbeddedSheet, differences, read_embedded
from sdb_reader.schema import ContactInfo, HazardStatements, SafetyDataSheet

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

NAMESPACE = ' xmlns="http://www.esdscom.eu/SDScom"'


def _feed(
    *,
    hazard: str = "412",
    precautionary: str = "101",
    signal: str = "",
    namespace: str = "",
    prolog: str = "",
) -> bytes:
    signal_word = (
        f"<ClpSignalWord><PhraseCode>{signal}</PhraseCode></ClpSignalWord>"
        if signal
        else ""
    )
    return f"""<?xml version="1.0"?>{prolog}
<DatasheetFeed{namespace}>
  <Datasheet>
    <InformationFromExportingSystem>
      <XmlStandardVersionNo>4.4.0</XmlStandardVersionNo>
      <SystemUsedInPreparation><Name>Example Author</Name></SystemUsedInPreparation>
    </InformationFromExportingSystem>
    <IdentificationSubstPrep>
      <SupplierInformation>
        <CompanyContact><Name>Regulatory Affairs</Name></CompanyContact>
      </SupplierInformation>
    </IdentificationSubstPrep>
    <HazardIdentification><HazardLabelling><ClpLabellingInfo>
      {signal_word}
      <ClpHazardStatement><PhraseCode>{hazard}</PhraseCode></ClpHazardStatement>
      <ClpPrecautionaryStatement><PhraseCode>{precautionary}</PhraseCode></ClpPrecautionaryStatement>
    </ClpLabellingInfo></HazardLabelling></HazardIdentification>
  </Datasheet>
</DatasheetFeed>""".encode()


def _pdf(
    path: Path, text: str, attachment: bytes | None, name: str = "sds.xml"
) -> Path:
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), text)
        if attachment is not None:
            doc.embfile_add(name, attachment)
        doc.save(path)
    return path


def _run(capsys: pytest.CaptureFixture[str], path: Path) -> dict:
    assert cli.main(["read", str(path)]) == 0
    return json.loads(capsys.readouterr().out)[0]


def _sheet(**statements: object) -> SafetyDataSheet:
    return SafetyDataSheet(
        product_identifier=None,
        issue_date=date(2022, 3, 30),
        revision_date=None,
        version=None,
        language="de",
        hazard_statements=HazardStatements(**statements),  # type: ignore[arg-type]
        contact_info=ContactInfo(
            supplier_name="Example  GmbH", supplier_email="Info@Example.com"
        ),
    )


@pytest.mark.spec("SDW-11")
def test_embedded_data_that_agrees_is_named_without_a_difference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _run(capsys, _pdf(tmp_path / "a.pdf", SHEET, _feed()))

    assert record["embedded_data"] == {
        "format": "eSDScom",
        "filename": "sds.xml",
        "version": "4.4.0",
        "system": "Example Author",
        "compared": True,
        "differences": [],
    }


@pytest.mark.spec("SDW-11")
def test_a_difference_comes_with_both_values_and_leaves_the_sheet_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _run(
        capsys, _pdf(tmp_path / "a.pdf", SHEET, _feed(hazard="318", signal="DGR"))
    )

    assert record["embedded_data"]["differences"] == [
        {"field": "signal_word", "embedded": "Gefahr", "read": None},
        {"field": "hazard_codes", "embedded": ["H318"], "read": ["H412"]},
    ]
    assert record["sheet"]["hazard_statements"]["hazard_codes"] == ["H412"]
    assert record["sheet"]["hazard_statements"]["signal_word"] is None


@pytest.mark.spec("SDW-11")
def test_the_root_element_counts_with_or_without_its_namespace(
    tmp_path: Path,
) -> None:
    with_namespace = read_embedded(
        _pdf(tmp_path / "a.pdf", SHEET, _feed(namespace=NAMESPACE))
    )
    without = read_embedded(_pdf(tmp_path / "b.pdf", SHEET, _feed()))

    assert with_namespace is not None
    assert without is not None
    assert with_namespace.sheet == without.sheet
    assert without.sheet is not None
    assert without.sheet.hazard_codes == frozenset({"H412"})


@pytest.mark.spec("SDW-11")
def test_another_attachment_is_no_embedded_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _run(
        capsys, _pdf(tmp_path / "a.pdf", SHEET, b"<Invoice/>", name="invoice.xml")
    )

    assert "embedded_data" not in record


@pytest.mark.spec("SDW-11")
def test_a_file_with_a_document_type_declaration_is_not_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bomb = _feed(prolog='<!DOCTYPE DatasheetFeed [<!ENTITY a "aaaa">]>')

    record = _run(capsys, _pdf(tmp_path / "a.pdf", SHEET, bomb))

    assert record["embedded_data"] == {
        "format": "eSDScom",
        "filename": "sds.xml",
        "compared": False,
        "differences": [],
        "unreadable": {
            "code": "embedded-doctype",
            "params": {},
            "message": "Die eingebettete Datei trägt eine Dokumenttyp-Deklaration.",
        },
    }
    assert record["sheet"]["hazard_statements"]["hazard_codes"] == ["H412"]


@pytest.mark.spec("SDW-11")
def test_a_file_that_is_not_well_formed_is_named_with_the_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _run(
        capsys, _pdf(tmp_path / "a.pdf", SHEET, b"<DatasheetFeed><Datasheet>")
    )

    assert record["embedded_data"]["unreadable"]["code"] == "embedded-not-xml"
    assert "sheet" in record


@pytest.mark.spec("SDW-11", "SDW-18")
def test_a_file_that_is_no_sheet_is_not_compared(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _run(capsys, _pdf(tmp_path / "a.pdf", LEAFLET, _feed()))

    assert record["embedded_data"]["version"] == "4.4.0"
    assert record["embedded_data"]["compared"] is False
    assert record["embedded_data"]["differences"] == []


@pytest.mark.spec("SDW-11")
def test_a_joined_code_counts_as_its_parts() -> None:
    embedded = EmbeddedSheet(
        date="2022-03-30",
        precautionary_codes=frozenset({"P305", "P351", "P338"}),
        supplier_name="Example GmbH",
        supplier_email="info@example.com",
    )

    assert differences(embedded, _sheet(precautionary_codes=["P305+P351+P338"])) == []


@pytest.mark.spec("SDW-11")
def test_the_issue_date_stands_in_where_the_sheet_has_no_revision() -> None:
    embedded = EmbeddedSheet(
        date="2022-03-31",
        supplier_name="example gmbh",
        supplier_email="info@example.com",
    )

    found = differences(embedded, _sheet())

    assert [(d.field, d.embedded, d.read) for d in found] == [
        ("date", "2022-03-31", "2022-03-30")
    ]


@pytest.mark.spec("SDW-11")
def test_the_supplier_is_the_company_not_its_contact_person(tmp_path: Path) -> None:
    feed = _feed().replace(
        b"<SupplierInformation>",
        b"<SupplierInformation><Name>Example GmbH</Name><Email>a@example.com</Email>",
    )

    embedded = read_embedded(_pdf(tmp_path / "a.pdf", SHEET, feed))

    assert embedded is not None
    assert embedded.sheet is not None
    assert embedded.sheet.supplier_name == "Example GmbH"
    assert embedded.sheet.supplier_email == "a@example.com"


@pytest.mark.spec("SDW-13")
def test_the_tool_wants_a_subcommand(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = _pdf(tmp_path / "a.pdf", SHEET, _feed())

    with pytest.raises(SystemExit) as stopped:
        cli.main([str(pdf)])

    assert stopped.value.code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.spec("SDW-13")
def test_xml_prints_the_embedded_file_and_nothing_else(
    tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    feed = (
        _feed()
        .decode()
        .replace('<?xml version="1.0"?>', '<?xml version="1.0" encoding="ISO-8859-1"?>')
        .replace("Example Author", "Prüfstelle")
        .encode("iso-8859-1")
    )
    pdf = _pdf(tmp_path / "a.pdf", SHEET, feed)

    code = cli.main(["xml", str(pdf)])

    assert code == 0
    assert capsysbinary.readouterr().out == feed


@pytest.mark.spec("SDW-13")
def test_xml_without_save_takes_one_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _pdf(tmp_path / "a.pdf", SHEET, _feed())
    second = _pdf(tmp_path / "b.pdf", SHEET, _feed())

    with pytest.raises(SystemExit) as stopped:
        cli.main(["xml", str(first), str(second)])

    assert stopped.value.code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.spec("SDW-13")
def test_xml_for_a_pdf_without_embedded_data_prints_nothing_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(["xml", str(_pdf(tmp_path / "a.pdf", SHEET, None))])

    out, err = capsys.readouterr()
    assert code == 1
    assert out == ""
    assert "keine eingebettete eSDScom-Datei" in err


@pytest.mark.spec("SDW-13", "SDW-11")
def test_xml_never_hands_out_a_file_the_tool_does_not_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    bomb = _feed(prolog='<!DOCTYPE DatasheetFeed [<!ENTITY a "aaaa">]>')
    pdf = _pdf(tmp_path / "a.pdf", SHEET, bomb)

    printed = cli.main(["xml", str(pdf)])
    saved = cli.main(["xml", "--save", str(out_dir), str(pdf)])

    out, err = capsys.readouterr()
    assert (printed, saved) == (1, 1)
    assert out == ""
    assert "trägt eine Dokumenttyp-Deklaration" in err
    assert list(out_dir.iterdir()) == []


@pytest.mark.spec("SDW-13")
def test_xml_saves_each_pdfs_file_unchanged_under_the_pdfs_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    first = _pdf(tmp_path / "sheet_1.pdf", SHEET, _feed(namespace=NAMESPACE))
    second = _pdf(tmp_path / "sheet_2.pdf", SHEET, _feed(hazard="318"))
    without = _pdf(tmp_path / "plain.pdf", SHEET, None)

    code = cli.main(
        ["xml", "--save", str(out_dir), str(first), str(without), str(second)]
    )

    out, err = capsys.readouterr()
    assert code == 0
    assert out == ""
    assert (out_dir / "sheet_1.xml").read_bytes() == _feed(namespace=NAMESPACE)
    assert (out_dir / "sheet_2.xml").read_bytes() == _feed(hazard="318")
    assert sorted(p.name for p in out_dir.iterdir()) == ["sheet_1.xml", "sheet_2.xml"]
    assert f"gespeichert als {out_dir / 'sheet_1.xml'}" in err
    assert "plain.pdf: keine eingebettete eSDScom-Datei" in err


@pytest.mark.spec("SDW-13")
def test_xml_does_not_overwrite_and_fails_only_that_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "a.xml").write_text("kept")
    first = _pdf(tmp_path / "a.pdf", SHEET, _feed())
    second = _pdf(tmp_path / "b.pdf", SHEET, _feed())

    code = cli.main(["xml", "--save", str(out_dir), str(first), str(second)])

    assert code == 1
    assert (out_dir / "a.xml").read_text() == "kept"
    assert (out_dir / "b.xml").exists()
    assert "FileExistsError" in capsys.readouterr().err


@pytest.mark.spec("SDW-13")
def test_xml_stops_before_reading_when_the_directory_does_not_exist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = _pdf(tmp_path / "a.pdf", SHEET, _feed())

    with pytest.raises(SystemExit) as stopped:
        cli.main(["xml", "--save", str(tmp_path / "missing"), str(pdf)])

    assert stopped.value.code == 2
    assert "not a directory" in capsys.readouterr().err


@pytest.mark.spec("SDW-13", "SDW-11")
def test_read_compares_and_does_not_carry_the_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _run(capsys, _pdf(tmp_path / "a.pdf", SHEET, _feed()))

    assert set(record["embedded_data"]) == {
        "format",
        "filename",
        "version",
        "system",
        "compared",
        "differences",
    }


@pytest.mark.spec("SDW-13")
def test_xml_save_fails_when_it_handed_out_nothing_at_all(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Among many PDFs most carry no embedded file, and that is passed over;
    a run that wrote none has not done what it was asked."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    one = _pdf(tmp_path / "a.pdf", SHEET, None)
    other = _pdf(tmp_path / "b.pdf", SHEET, None)

    code = cli.main(["xml", "--save", str(out_dir), str(one), str(other)])

    assert code == 1
    assert list(out_dir.iterdir()) == []
    assert capsys.readouterr().err.count("keine eingebettete eSDScom-Datei") == 2
