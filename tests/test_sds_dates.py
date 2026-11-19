"""What the parser reads as a sheet's dates and version (SDB-57, SDB-128 to SDB-130).

The sheets are invented; each shows one form a comparison over a body of
sheets turned up.
"""

from __future__ import annotations

from datetime import date

import pytest

from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import SDSParser
from sdb_reader.schema import SafetyDataSheet

SHEET = (
    "Sicherheitsdatenblatt\n"
    "{header}"
    "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
    "1.1 Produktidentifikator\nHandelsname: Musterprodukt\n"
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.2 Kennzeichnungselemente\nSignalwort: Achtung\n"
    "H315 Verursacht Hautreizungen.\n"
    "2.3 Sonstige Gefahren\nKeine bekannt.\n"
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
    "ABSCHNITT 16: Sonstige Angaben\n{section_16}"
)


def read(header: str, section_16: str = "Keine.\n") -> SafetyDataSheet:
    text = SHEET.format(header=header, section_16=section_16)
    extraction = ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )
    return SDSParser(language="de").parse(extraction).sheet


@pytest.mark.spec("SDB-57")
@pytest.mark.parametrize(
    "named",
    [
        "überarbeitet am: 30.11.2022; ersetzt Version 003 vom 12.03.2024\n",
        "Überarbeitet am 30.11.2022\nErsetzt version vom: 04.01.2024\n",
        "Überarbeitet am: 30.11.2022\n· Ersetzt die Version vom: 22.01.2024\n",
        "Überarbeitet am: 30.11.2022\n"
        "Dieses Sicherheitsdatenblatt ersetzt die vorherige Version vom 27.01.2024.\n",
        "Überarbeitet am: 30.11.2022\nErsatz für Version 2 vom 27.01.2024\n",
        "Überarbeitet am: 30.11.2022\n"
        "Version 1.4 (ungültig wird Version 1.3 vom 04.03.2024)\n",
        "Überarbeitet am: 30.11.2022\n"
        "Geänderte Daten in der Version 11 gegenüber der Version 10 vom 06.03.2024 "
        "sind gekennzeichnet.\n",
        "Überarbeitet am: 30.11.2022\nVorversion vom 31.05.2024\n",
    ],
)
def test_the_date_of_a_version_the_sheet_only_names_is_not_its_own(
    named: str,
) -> None:
    # Each names a later day for the other version: read, it would win.
    assert read(named).revision_date == date(2022, 11, 30)


@pytest.mark.spec("SDB-57")
def test_a_version_with_its_own_date_still_dates_the_sheet() -> None:
    assert read("Version 3 vom 14.11.2019\n").revision_date == date(2019, 11, 14)
    assert read("REV. 1 vom 14.11.2019\n").revision_date == date(2019, 11, 14)


@pytest.mark.spec("SDB-57")
def test_a_sheet_that_dates_only_the_version_before_it_has_no_revision_date() -> None:
    sheet = read("Ausgabedatum: 18.08.2021 Ersetzt Version vom: 19.12.2019\n")

    assert sheet.revision_date is None
    assert sheet.issue_date == date(2021, 8, 18)


@pytest.mark.spec("SDB-57")
def test_a_two_digit_year_counts_where_only_the_replaced_version_has_four() -> None:
    sheet = read("Überarbeitet am: 17.06.21\nErsetzt Version vom: 24.09.2020\n")

    assert sheet.revision_date == date(2021, 6, 17)


@pytest.mark.spec("SDB-128")
@pytest.mark.parametrize(
    "header",
    [
        "Aktuelle Version: 2.0.1, erstellt am: 20.03.2020\n"
        "Ersetzte Version: 2.0.0, erstellt am: 04.06.2019\nRegion: DE\n",
        "Aktuelle Version: 1.1 erstellt am 20.03.2020\n",
        "Version: 004 A3A |\nerstellt am: 20.03.2020\n",
        "Version 1.6 ungültig wird Version 1.5\nErstellt am 20.03.2020\n",
        "Version 1.5\nErstellt am 20.03.2020\n",
        "Erstellt am 20.03.2020\nVersion 1.2\nErsetzt Fassung von 2019\n",
    ],
)
def test_the_day_the_version_in_hand_was_made_is_its_revision_date(
    header: str,
) -> None:
    sheet = read(header)

    assert sheet.revision_date == date(2020, 3, 20)
    # The label still says when it was issued (SDB-57).
    assert sheet.issue_date == date(2020, 3, 20)


@pytest.mark.spec("SDB-128")
def test_the_day_the_replaced_version_was_made_is_not() -> None:
    sheet = read("Ersetzte Version: 2.0.0, erstellt am: 04.06.2019\n")

    assert sheet.revision_date is None


@pytest.mark.spec("SDB-128")
def test_a_day_of_issue_away_from_the_version_stays_one() -> None:
    sheet = read("Version: 3\nSeite 1 von 9\nErstellt am: 20.03.2020\n")

    assert sheet.revision_date is None
    assert sheet.issue_date == date(2020, 3, 20)


@pytest.mark.spec("SDB-128")
def test_the_version_s_day_goes_before_an_older_revision_named_elsewhere() -> None:
    sheet = read(
        "Version 1.6 ungültig wird Version 1.5\nErstellt am 30.03.2023\n",
        section_16="Hergestellt durch\nProduktsicherheit\nÜberarbeitet am\n03.08.2021\n",
    )

    assert sheet.revision_date == date(2023, 3, 30)


@pytest.mark.spec("SDB-129")
@pytest.mark.parametrize("joined", ["+", "und"])
def test_several_days_behind_one_label_all_count(joined: str) -> None:
    sheet = read(
        f"überarbeitet am: 30.04.2012 {joined} 10.06.2016\nDruckdatum: 13.07.2018\n"
    )

    assert sheet.revision_date == date(2016, 6, 10)


@pytest.mark.spec("SDB-130")
def test_a_day_is_no_version() -> None:
    sheet = read(
        "Revision: 11\nDatum: 13.03.2024\nLetzte Version: 06.03.2023\n",
        section_16="Grenzwert: 5 mg/m3\nVersion: 02.07.2021\n",
    )

    assert sheet.version == "11"
    # The day of the version before is not the sheet's either (SDB-57).
    assert sheet.revision_date == date(2024, 3, 13)


@pytest.mark.spec("SDB-130")
def test_a_sheet_whose_only_version_is_a_day_has_none() -> None:
    assert read("Grenzwert: 5 mg/m3\nVersion: 02.07.2021\n").version is None


@pytest.mark.spec("SDB-130")
def test_the_number_behind_the_day_is_the_version() -> None:
    sheet = read(
        "Überarbeitet am / Version: 31.05.2012 / 0007\n"
        "Ersetzt Fassung vom / Version: 19.01.2011 / 0006\n"
        "Gültig ab: 31.05.2012\n"
    )

    assert sheet.version == "0007"
    assert sheet.revision_date == date(2012, 5, 31)
