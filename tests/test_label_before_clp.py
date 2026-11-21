"""A label block under the directives before CLP (SDB-170)."""

from __future__ import annotations

import pytest

from sdb_reader import extraction_from_dict, read_extraction
from sdb_reader.compliance import sheet_findings
from sdb_reader.parser import label_before_clp

_SECTION_2 = (
    "Sicherheitsdatenblatt\n"
    "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs\n"
    "Handelsname: Musterspray\n"
    "{dated}"
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.1 Einstufung des Stoffs oder Gemischs\n"
    "Einstufung gemäß Verordnung (EG) Nr. 1272/2008\n"
    "Flam. Aerosol 1 H222 Extrem entzündbares Aerosol.\n"
    "2.2 Kennzeichnungselemente\n"
    "{label}\n"
    "2.3 Sonstige Gefahren\n"
    "Keine.\n"
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
)


def _read(
    label: str, dated: str = "Überarbeitet am: 02.09.2013\n"
) -> tuple[list[str], list[str]]:
    result = read_extraction(
        extraction_from_dict(
            {
                "text": _SECTION_2.format(label=label, dated=dated),
                "extractor": "pymupdf",
                "pages_sampled": 1,
                "warnings": [],
            }
        )
    ).parser_result
    assert result is not None
    findings = sheet_findings(result.sheet, result.warnings)
    return [w.code for w in result.warnings], [f.code for f in findings]


@pytest.mark.spec("SDB-170")
@pytest.mark.parametrize(
    "label",
    [
        "Kennzeichnung nach EWG-Richtlinien:\nDas Produkt ist nach EG-Richtlinien/GefStoffV "
        "nicht kennzeichnungspflichtig.",
        "Kennbuchstabe und Gefahrenbezeichnung des Produktes:\nF+ Hochentzündlich\n"
        "R-Sätze:\n12 Hochentzündlich.",
    ],
)
def test_an_old_label_is_noted_and_gets_no_label_finding(label: str) -> None:
    warnings, findings = _read(label)
    assert "label-before-clp" in warnings
    assert not {code for code in findings if code.startswith("label-")}


@pytest.mark.spec("SDB-170", "SDB-171")
def test_a_clp_label_without_hazard_statements_is_not_an_old_one() -> None:
    # Without a date the sheet is not due for renewal, so the label is judged.
    warnings, findings = _read(
        "Signalwort: Achtung\nP102 Darf nicht in die Hände von Kindern gelangen.",
        dated="",
    )
    assert "label-before-clp" not in warnings
    assert "label-without-hazard-statement" in findings


def test_a_code_makes_the_label_one_under_clp() -> None:
    assert not label_before_clp("Kennzeichnung nach EWG-Richtlinien\nEUH208 Enthält …")
