"""An H statement of the classification in 2.1 that the label does not carry (SDB-173).

Every text here is invented.
"""

from __future__ import annotations

from functools import partial

import pytest

from sdb_reader import extraction_from_dict, read_extraction
from sdb_reader.compliance import sheet_findings
from sdb_reader.parser import classification_hazard_codes

# These tests are about what a label lacks, so they read it as printed
# instead of withheld (SDB-217).
read_extraction = partial(read_extraction, accept_incomplete_label=True)

_SHEET = (
    "Sicherheitsdatenblatt\n"
    "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs\n"
    "Handelsname: Musterlack\n"
    "Überarbeitet am: 02.09.2024\n"
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.1 Einstufung des Stoffs oder Gemischs\n"
    "Einstufung gemäß Verordnung (EG) Nr. 1272/2008\n"
    "{classification}\n"
    "2.2 Kennzeichnungselemente\n"
    "Signalwort: Achtung\n"
    "{label}\n"
    "P102 Darf nicht in die Hände von Kindern gelangen.\n"
    "2.3 Sonstige Gefahren\n"
    "Keine.\n"
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
)


def _not_in_label(classification: str, label: str) -> list[str]:
    result = read_extraction(
        extraction_from_dict(
            {
                "text": _SHEET.format(classification=classification, label=label),
                "extractor": "pymupdf",
                "pages_sampled": 1,
                "warnings": [],
            }
        )
    ).parser_result
    assert result is not None
    return [
        finding.params["statement"]
        for finding in sheet_findings(result.sheet, result.warnings)
        if finding.code == "hazard-statement-not-in-label"
    ]


@pytest.mark.spec("SDB-173")
@pytest.mark.spec("SDW-42")
def test_a_statement_of_the_classification_missing_from_the_label() -> None:
    assert _not_in_label(
        "Flam. Liq. 3, H226\nSkin Sens. 1, H317",
        "H226 Flüssigkeit und Dampf entzündbar.",
    ) == ["H317"]


@pytest.mark.spec("SDB-173")
def test_every_statement_on_the_label_gives_no_finding() -> None:
    assert (
        _not_in_label(
            "Flam. Liq. 3, H226\nSkin Irrit. 2, H315",
            "H226 Flüssigkeit und Dampf entzündbar.\nH315 Verursacht Hautreizungen.",
        )
        == []
    )


@pytest.mark.spec("SDB-173")
def test_annex_iii_lets_the_label_leave_out_h400_and_h318() -> None:
    assert (
        _not_in_label(
            "Aquatic Acute 1, H400\nAquatic Chronic 1, H410\n"
            "Skin Corr. 1B, H314\nEye Dam. 1, H318",
            "H314 Verursacht schwere Verätzungen der Haut und schwere Augenschäden.\n"
            "H410 Sehr giftig für Wasserorganismen mit langfristiger Wirkung.",
        )
        == []
    )


@pytest.mark.spec("SDB-173")
def test_an_aerosol_needs_no_h304_on_its_label() -> None:
    assert (
        _not_in_label(
            "Aerosol 1, H222, H229\nAsp. Tox. 1, H304",
            "H222 Extrem entzündbares Aerosol.\n"
            "H229 Behälter steht unter Druck: Kann bei Erwärmung bersten.",
        )
        == []
    )


@pytest.mark.spec("SDB-173")
def test_a_liquid_needs_h304_on_its_label() -> None:
    assert _not_in_label(
        "Flam. Liq. 3, H226\nAsp. Tox. 1, H304",
        "H226 Flüssigkeit und Dampf entzündbar.",
    ) == ["H304"]


@pytest.mark.spec("SDB-173")
def test_the_wording_without_its_code_carries_the_statement() -> None:
    assert (
        _not_in_label(
            "Flam. Liq. 3, H226\nAquatic Chronic 3, H412",
            "H226 Flüssigkeit und Dampf entzündbar.\n"
            "Schädlich für Wasserorganismen, mit langfristiger Wirkung.",
        )
        == []
    )


@pytest.mark.spec("SDB-173")
def test_a_wording_inside_another_statements_does_not_carry_it() -> None:
    # "Giftig für Wasserorganismen, mit langfristiger Wirkung" (H411) stands
    # inside the wording of H410. The sheet prints a small package's label as
    # well, so the label is that of a larger package (SDB-194).
    assert _not_in_label(
        "Aquatic Acute 1, H400\nAquatic Chronic 2, H411",
        "H410 Sehr giftig für Wasserorganismen mit langfristiger Wirkung.\n"
        "Kennzeichnung von Verpackungen bei einem Inhalt von nicht mehr als 125 ml\n"
        "Signalwort: Achtung",
    ) == ["H411"]


@pytest.mark.spec("SDB-173")
def test_h360_counts_whatever_its_letters() -> None:
    assert (
        _not_in_label(
            "Repr. 1B, H360D",
            "H360FD Kann die Fruchtbarkeit beeinträchtigen. "
            "Kann das Kind im Mutterleib schädigen.",
        )
        == []
    )


@pytest.mark.spec("SDB-173")
def test_a_label_without_any_hazard_statement_is_sdb_171s() -> None:
    assert _not_in_label("Skin Irrit. 2, H315", "Gefahrenhinweise: keine") == []


@pytest.mark.spec("SDB-173")
def test_the_ingredients_classification_is_not_the_products() -> None:
    assert classification_hazard_codes(
        "2.1 Einstufung des Stoffs oder Gemischs\n"
        "Skin Irrit. 2, H315\n"
        "Das Gemisch enthält einen Stoff, der als Acute Tox. 4\n"
        "(H302) eingestuft ist.\n"
        "Inhaltsstoff Musterol: Aquatic Chronic 2, H411\n"
        "2.2 Kennzeichnungselemente\n"
    ) == {"H315"}
    assert (
        _not_in_label(
            "Skin Irrit. 2, H315\nDas Gemisch enthält einen Stoff mit H302.",
            "H315 Verursacht Hautreizungen.",
        )
        == []
    )
