"""The signal word as printed, and the one the codes call for (SDB-176, SDB-178,
SDB-180, BIB-25).

Every text here is invented.
"""

from __future__ import annotations

from functools import partial

import pytest

from sdb_reader import (
    clp_expected,
    extraction_from_dict,
    read_extraction,
    sheet_from_dict,
    sheet_to_dict,
)
from sdb_reader.compliance import sheet_findings
from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import ParsedSheet, read_signal_word

# These tests are about what a label lacks, so they read it as printed
# instead of withheld (SDB-217).
read_extraction = partial(read_extraction, accept_incomplete_label=True)

_SHEET = (
    "Sicherheitsdatenblatt\n"
    "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs\n"
    "Handelsname: Musterlack\n"
    "Überarbeitet am: 02.09.2024\n"
    "{identification}"
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.1 Einstufung des Stoffs oder Gemischs\n"
    "Einstufung gemäß Verordnung (EG) Nr. 1272/2008\n"
    "Flam. Liq. 2, H225\n"
    "2.2 Kennzeichnungselemente\n"
    "{label}"
    "H225 Flüssigkeit und Dampf leicht entzündbar.\n"
    "P210 Von Hitze fernhalten. Nicht rauchen.\n"
    "2.3 Sonstige Gefahren\n"
    "Keine.\n"
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
)


def _extraction(label: str, identification: str = "") -> ExtractionResult:
    return extraction_from_dict(
        {
            "text": _SHEET.format(label=label, identification=identification),
            "extractor": "pymupdf",
            "pages_sampled": 1,
            "warnings": [],
        }
    )


def _parsed(label: str, identification: str = "") -> ParsedSheet:
    result = read_extraction(_extraction(label, identification)).parser_result
    assert result is not None
    return result


def _found(parsed: ParsedSheet) -> list[dict[str, str]]:
    return [
        dict(finding.params)
        for finding in sheet_findings(parsed.sheet, parsed.warnings)
        if finding.code == "signal-word-not-found"
    ]


@pytest.mark.spec("SDB-176", "SDB-180", "BIB-25")
def test_a_silent_label_has_no_signal_word() -> None:
    label = _parsed("").sheet.hazard_statements
    assert label.signal_word is None
    assert not label.states_no_signal_word
    assert clp_expected(label).signal_word == "Gefahr"
    assert clp_expected(label).signal_word_missing


@pytest.mark.spec("SDB-178")
@pytest.mark.spec("SDW-47")
def test_the_signal_word_the_codes_call_for_is_a_finding() -> None:
    assert _found(_parsed("")) == [{"expected": "Gefahr"}]


@pytest.mark.spec("SDB-176", "SDB-178", "BIB-25")
def test_a_printed_signal_word_gives_no_finding() -> None:
    parsed = _parsed("Signalwort: Gefahr\n")
    assert parsed.sheet.hazard_statements.signal_word == "Gefahr"
    expected = clp_expected(parsed.sheet.hazard_statements)
    assert not expected.signal_word_missing
    assert not expected.signal_word_differs
    assert _found(parsed) == []


@pytest.mark.spec("SDB-176")
@pytest.mark.parametrize(
    "label",
    ["Signalwort: Achtung!\nH319 Reizt", "Signalwort\nAchtung!\nGefahrenhinweise"],
)
def test_a_named_signal_word_may_end_in_an_exclamation_mark(label: str) -> None:
    assert read_signal_word(label) == ("Achtung", True)


@pytest.mark.spec("SDB-176")
def test_the_opening_of_euh211_is_no_signal_word() -> None:
    label = "Signalwort\nAchtung! Beim Sprühen können gefährliche Tröpfchen entstehen."
    assert read_signal_word(label) == (None, False)


@pytest.mark.spec("SDB-178", "SDB-180")
def test_a_label_that_says_it_has_none_gives_no_finding() -> None:
    """ "Kein Signalwort" is the sheet's answer: the reading says so, and the
    finding stays away; the expectation is the codes' all the same."""
    parsed = _parsed("Signalwort: Kein Signalwort\n")
    label = parsed.sheet.hazard_statements
    assert label.signal_word is None
    assert label.states_no_signal_word
    assert clp_expected(label).signal_word_missing
    assert _found(parsed) == []


@pytest.mark.spec("SDB-178")
def test_an_article_gets_no_finding() -> None:
    parsed = _parsed(
        "",
        "Dieses Produkt ist ein Erzeugnis, deshalb ist es nicht kennzeichnungspflichtig.\n",
    )
    assert parsed.sheet.stated_article
    assert clp_expected(parsed.sheet.hazard_statements).signal_word == "Gefahr"
    assert _found(parsed) == []


@pytest.mark.spec("SDB-180")
@pytest.mark.spec("SDW-47")
def test_a_stored_reading_keeps_what_the_label_states() -> None:
    extraction = _extraction("Signalwort: Kein Signalwort\n")
    stored = sheet_to_dict(_parsed("Signalwort: Kein Signalwort\n").sheet, extraction)
    label = stored["hazard_statements"]
    assert label["signal_word"] is None
    assert label["states_no_signal_word"] is True
    assert "expected_signal_word" not in label
    assert sheet_from_dict(stored).hazard_statements.states_no_signal_word


@pytest.mark.spec("SDW-47")
def test_a_reading_stored_before_reads_back_without_a_statement() -> None:
    stored = sheet_to_dict(_parsed("").sheet, _extraction(""))
    del stored["hazard_statements"]["states_no_signal_word"]
    del stored["hazard_statements"]["states_no_pictograms"]
    back = sheet_from_dict(stored).hazard_statements
    assert not back.states_no_signal_word
    assert not back.states_no_pictograms
