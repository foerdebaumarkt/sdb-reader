"""Every reading finishes in time, whatever a sheet's text holds.

Hypothesis builds sheets from an invented one with a long run put into it: of
one mark, one letter, one word or one short piece of a label, at a place where
the parser reads it (the product's name, a name below its label, the
supplier, the classification, a line or a field of the label, behind the
label). The text goes through the same normalisation as an extracted PDF's,
so only runs that can reach the parser are tried; a run of blanks or of empty
lines cannot. A pattern that tries such a run again from each of its
characters takes seconds on it and fails here, however its source looks. A
run on one line longer than a sheet prints is not read at all (SDB-167); the
runs over several lines are what the parser still sees.

Below, the statement whose lines nothing ends: a reading takes the first
lines up to the limit of SDB-168 and reads past the rest.

In CI the examples are fixed (derandomised) and few, so the suite stays fast
and gives the same result on every run. `HYPOTHESIS_PROFILE=thorough` tries
many more (tests/conftest.py).
"""

from __future__ import annotations

import time

import pytest
from hypothesis import given, strategies as st

from sdb_reader import read_extraction
from sdb_reader.extraction import ExtractionResult, normalise_pdf_text

# Characters per run. A reading of an ordinary sheet with a run this long takes
# a fraction of a second; a pattern that is quadratic in the run takes seconds.
RUN = 30_000
LIMIT_SECONDS = 2.0

PIECES = (
    *"-–—·•∙,;:./()*!+&",
    *"aäA1",
    ": ",
    "- ",
    ", ",
    "a.",
    "a. ",
    "-\n",
    "·\n",
    ":\n",
    "Abc ",
    "Gefahr ",
    "keine ",
    "Signalwort ",
    "Art.-Nr. ",
    "H315 ",
    "P 280 ",
    "Skin Corr. 1, ",
    "(EU) ",
    "N/A ",
    "x@",
    "Display ",
    "Inhalt/Behälter ",
)

# Where the run goes: the slot in the sheet, and what stands around it there.
PLACES = {
    "name": ("name", "Musterkleber ", ""),
    "name-below-label": ("below_name", "", " 200 ml Art.Nr."),
    "supplier": ("supplier", "Musterwerk GmbH ", "."),
    "classification": ("classification", "", ""),
    "classification-field": ("classification", "Einstufung: ", ""),
    "label-line": ("label", "", ""),
    "label-field": ("label", "Gefahrenhinweise: ", ""),
    # Longer than the 40 characters a field may hold behind "keine" or a dash.
    "label-field-then-text": (
        "label",
        "Gefahrenhinweise: ",
        " Siehe Abschnitt 16 und die Angaben des Herstellers.",
    ),
    "classification-field-then-text": ("classification", "Einstufung: ", " gemäß"),
    "signal-word-field": ("label", "Signalwort: ", ""),
    "statement": ("label", "P280 Schutzhandschuhe tragen. ", ""),
    "after-label": ("after", "", ""),
}


def _sheet(place: str, run: str) -> str:
    slot, before, after = PLACES[place]

    def at(here: str) -> str:
        return f"{before}{run}{after}" if here == slot else ""

    name = (
        "Handelsname:\n" + at("below_name")
        if slot == "below_name"
        else "Handelsname: Musterkleber " + at("name")
    )
    supplier = at("supplier") or "Musterwerk GmbH"
    return (
        "Sicherheitsdatenblatt\n"
        "gemäß Verordnung (EG) Nr. 1907/2006\n"
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
        f"1.1 Produktidentifikator\n{name}\n"
        "1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt\n"
        f"{supplier}\nHafenstraße 4\n20457 Hamburg\n"
        "Telefon: +49 40 5550123\nE-Mail: info@musterwerk.example\n"
        "1.4 Notrufnummer\nGiftnotruf Musterstadt: +49 30 5550100\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        "2.1 Einstufung des Stoffs oder Gemischs\n"
        f"Skin Irrit. 2, H315\n{at('classification')}\n"
        "2.2 Kennzeichnungselemente\n"
        "Kennzeichnung gemäß Verordnung (EG) Nr. 1272/2008\n"
        "Gefahrenpiktogramme\nGHS07\nSignalwort\nAchtung\n"
        f"{at('label')}\n"
        "Gefahrenhinweise\nH315 Verursacht Hautreizungen.\n"
        "Sicherheitshinweise\nP280 Schutzhandschuhe tragen.\n"
        f"2.3 Sonstige Gefahren\nKeine bekannt.\n{at('after')}\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
        "ABSCHNITT 16: Sonstige Angaben\nÜberarbeitet am: 01.02.2025\n"
    )


def _extraction(text: str) -> ExtractionResult:
    text = normalise_pdf_text(text)
    return ExtractionResult(
        text=text,
        raw_text=text,
        extractor="unit-test",
        pages_sampled=1,
        warnings=[],
        metadata={},
    )


def test_the_sheet_without_a_run_is_read_whole() -> None:
    sheet = read_extraction(_extraction(_sheet("label-line", ""))).parser_result
    assert sheet is not None
    assert sheet.sheet.product_identifier == "Musterkleber"
    assert sheet.sheet.contact_info.supplier_name == "Musterwerk GmbH"
    assert sheet.sheet.hazard_statements.hazard_codes == ["H315"]
    assert sheet.sheet.hazard_statements.precautionary_codes == ["P280"]


_runs = st.sampled_from(PIECES).flatmap(
    lambda piece: st.integers(RUN // 2 // len(piece), RUN // len(piece)).map(
        lambda count: piece * count
    )
)


@given(place=st.sampled_from(sorted(PLACES)), run=_runs)
def test_a_long_run_anywhere_is_read_in_time(place: str, run: str) -> None:
    extraction = _extraction(_sheet(place, run))
    start = time.perf_counter()
    read_extraction(extraction)
    elapsed = time.perf_counter() - start
    assert elapsed < LIMIT_SECONDS, f"{elapsed:.1f} s, {place}: {run[:12]!r}…"


# Lines behind one statement that nothing ends, and the time a reading of them
# may take. Before the limit of SDB-168 each line had the whole statement
# joined and searched again: 50,000 lines of "-" behind a code alone took
# about half a minute.
LINES = 50_000
LINES_LIMIT_SECONDS = 3.0


def _with_lines_behind(statement: str, line: str) -> str:
    return _sheet("label-line", "").replace(
        "P280 Schutzhandschuhe tragen.\n",
        f"P280 Schutzhandschuhe tragen.\n{statement}\n{line * LINES}",
        1,
    )


@pytest.mark.parametrize(
    ("statement", "line"),
    [
        ("P280", "-\n"),
        ("P280 Schutzhandschuhe tragen.", ":\n"),
        ("H373 Kann die Organe schädigen", ":\n"),
        ("EUH208 Enthält Musterol. Kann allergische Reaktionen hervorrufen.", "-\n"),
        ("EUH208 Enthält Musterol. Kann allergische Reaktionen hervorrufen.", "abc\n"),
        ("P280 Schutz-", "ab-\n"),
    ],
    ids=[
        "code-alone-dashes",
        "worded-colons",
        "hazard-colons",
        "euh-dashes",
        "euh-words",
        "word-breaks",
    ],
)
def test_many_lines_behind_a_statement_are_read_in_time(
    statement: str, line: str
) -> None:
    extraction = _extraction(_with_lines_behind(statement, line))
    start = time.perf_counter()
    read_extraction(extraction)
    elapsed = time.perf_counter() - start
    assert elapsed < LINES_LIMIT_SECONDS, f"{elapsed:.1f} s"
