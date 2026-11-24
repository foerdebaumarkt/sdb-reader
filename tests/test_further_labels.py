"""The blocks of 2.2 beside the label, and conditions the label prints
(SDB-188 to SDB-196, SDW-51, BIB-24, BIB-25).

Every sheet here is invented; the pictograms are the public-domain drawings
the references are made from.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

import pytest
from test_pictograms_as_printed import _pages

from sdb_reader import (
    FurtherLabel,
    HazardStatements,
    LabelCondition,
    LabelImages,
    LabelImagesStatus,
    LabelKind,
    SheetDuty,
    clp_expected,
    extraction_from_dict,
    label_images_from_dict,
    label_images_stage,
    label_images_to_dict,
    read_extraction,
    read_label_images,
    read_sheet,
    sheet_duty,
    sheet_findings,
    sheet_from_dict,
    sheet_to_dict,
)
from sdb_reader.parser import ParsedSheet, omitted_codes, split_label_blocks

# These tests are about what a label lacks, so they read it as printed
# instead of withheld (SDB-217).
read_sheet = partial(read_sheet, accept_incomplete_label=True)
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
    "{label}\n"
    "2.3 Sonstige Gefahren\n"
    "Keine.\n"
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
)

_SMALL = "Kennzeichnung von Verpackungen bei einem Inhalt von nicht mehr als 125 ml"


def _parsed(label: str, classification: str = "Skin Sens. 1, H317") -> ParsedSheet:
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
    return result


def _findings(
    label: str, classification: str = "Skin Sens. 1, H317"
) -> list[tuple[str, str]]:

    result = _parsed(label, classification)
    return [
        (finding.code, next(iter(finding.params.values()), ""))
        for finding in sheet_findings(result.sheet, result.warnings)
    ]


_TWO_LABELS = (
    "Signalwort: Achtung\n"
    "H226 Flüssigkeit und Dampf entzündbar.\n"
    "H317 Kann allergische Hautreaktionen verursachen.\n"
    "P280 Schutzhandschuhe tragen.\n"
    f"{_SMALL}\n"
    "Signalwort: Gefahr\n"
    "Gefahrenpiktogramme: GHS06\n"
    "Gefahrenhinweise\n"
    "H317-H331\n"
    "Sicherheitshinweise\n"
    "P261-P501"
)


@pytest.mark.spec("SDB-188")
def test_a_small_package_s_label_stands_apart_from_the_label() -> None:
    label = _parsed(_TWO_LABELS, "Flam. Liq. 3, H226\nSkin Sens. 1, H317").sheet
    main = label.hazard_statements

    assert main.hazard_codes == ["H226", "H317"]
    assert main.precautionary_codes == ["P280"]
    assert main.signal_word == "Achtung"
    assert main.pictograms == []
    assert "P501" not in (main.precautionary_text or "")
    [small] = main.further_labels
    assert small.kind is LabelKind.SMALL_PACKAGE
    assert small.heading == _SMALL
    assert small.label.hazard_codes == ["H317", "H331"]
    assert small.label.precautionary_codes == ["P261", "P501"]
    assert small.label.signal_word == "Gefahr"
    assert small.label.pictograms == ["GHS06"]
    assert small.text is not None
    assert small.text.startswith("Signalwort: Gefahr")


@pytest.mark.spec("SDB-188")
@pytest.mark.parametrize(
    "heading",
    [
        f"· {_SMALL}",
        "Kennzeichnung gemäß: Ausnahme für Pakete mit einer Kapazität von 125 ml oder weniger",
        "Kennzeichnung gemäß: Ausnahme für Verpackungen mit einer Kapazität von 125 ml "
        "oder weniger",
        "Reduzierte Kennzeichnung (≤ 125 ml):",
    ],
)
def test_each_heading_of_a_small_package_begins_its_label(heading: str) -> None:
    main, [block] = split_label_blocks(
        f"H319 Verursacht schwere Augenreizung.\n{heading}\nH412 Schädlich."
    )

    assert main == "H319 Verursacht schwere Augenreizung."
    assert block.kind is LabelKind.SMALL_PACKAGE
    assert block.lines == ["H412 Schädlich."]


@pytest.mark.spec("SDB-188")
def test_what_follows_for_all_package_sizes_belongs_to_both() -> None:
    main, [block] = split_label_blocks(
        "H317 Kann allergische Hautreaktionen verursachen.\n"
        f"{_SMALL}\n"
        "H317 Kann allergische Hautreaktionen verursachen.\n"
        "Ergänzende Kennzeichnung (für alle Verpackungsgrößen)\n"
        ": Enthält: Linalool."
    )

    assert "Enthält: Linalool." in main
    assert block.lines[-1] == ": Enthält: Linalool."
    assert "Ergänzende Kennzeichnung (für alle Verpackungsgrößen)" in block.lines


@pytest.mark.spec("SDB-188")
def test_a_small_package_s_label_states_none_as_a_label_does() -> None:
    main = _parsed(
        "Signalwort: Achtung\nH317 Kann allergische Hautreaktionen verursachen.\n"
        f"{_SMALL}\n"
        "Gefahrenpiktogramme entfällt\nSignalwort entfällt\nGefahrenhinweise entfällt"
    ).sheet.hazard_statements

    [small] = main.further_labels
    assert small.label.states_no_pictograms
    assert small.label.states_no_signal_word
    assert not main.states_no_signal_word


@pytest.mark.spec("SDB-189")
def test_a_sentence_naming_what_a_small_package_leaves_out() -> None:
    main = _parsed(
        "Signalwort: Gefahr\nH225 Flüssigkeit und Dampf leicht entzündbar.\n"
        "H319 Verursacht schwere Augenreizung.\n"
        "Nach 1272/2008/EG I, 1.5.2 keine Kennzeichnung bei Gebinden < 125ml mit: H225, "
        "H319, P210,\n"
        "P303+361+353\n"
        "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.",
        "Flam. Liq. 2, H225\nEye Irrit. 2, H319",
    ).sheet.hazard_statements

    [small] = main.further_labels
    assert small.kind is LabelKind.SMALL_PACKAGE
    assert small.omitted_codes == ["H225", "H319", "P210", "P303", "P353", "P361"]
    assert small.label == HazardStatements()
    assert small.heading.startswith("Nach 1272/2008/EG I, 1.5.2")
    # The label goes on behind it, and its codes are no label's.
    assert main.supplemental_codes == ["EUH066"]
    assert main.precautionary_codes == []


@pytest.mark.spec("SDB-189")
def test_the_shorthand_of_a_combination_is_its_parts() -> None:
    assert omitted_codes(
        "Reduzierte Kennzeichnung <= 125 ml: H225 und H319 entfallen."
    ) == [
        "H225",
        "H319",
    ]
    assert omitted_codes("P305+351+338") == ["P305", "P338", "P351"]


@pytest.mark.spec("SDB-190")
def test_a_block_under_another_regulation_is_kept_as_printed() -> None:
    main = _parsed(
        "Signalwort: Gefahr\nH222 Extrem entzündbares Aerosol.\n"
        "P102 Darf nicht in die Hände von Kindern gelangen.\n"
        "Biozid-kennzeichnung\n"
        "Mit Konservierungsmittel MUSTERIN behandelte Ware. Kann allergische\n"
        "Reaktionen hervorrufen.\n"
        "Etikettierung von Wasch und\n"
        "Reinigungsmitteln\n"
        "5 - < 15% Nichtionische Tenside\n"
        "P264 Nach Gebrauch Hände gründlich waschen.",
        "Aerosol 1, H222, H229",
    ).sheet.hazard_statements

    biocides, detergents = main.further_labels
    assert biocides.kind is LabelKind.BIOCIDES
    assert biocides.heading == "Biozid-kennzeichnung"
    assert biocides.text == (
        "Mit Konservierungsmittel MUSTERIN behandelte Ware. Kann allergische\n"
        "Reaktionen hervorrufen."
    )
    assert biocides.label == HazardStatements()
    assert detergents.kind is LabelKind.DETERGENTS
    assert detergents.heading == "Etikettierung von Wasch und Reinigungsmitteln"
    assert detergents.text == "5 - < 15% Nichtionische Tenside"
    # The code behind it is the label's again, and nothing of the blocks is.
    assert main.precautionary_codes == ["P102", "P264"]
    assert main.supplemental_codes == []


@pytest.mark.spec("SDB-190")
@pytest.mark.parametrize(
    ("heading", "kind"),
    [
        ("Kennzeichnung gem. Verordnung (EU) Nr. 528/2012 ***", LabelKind.BIOCIDES),
        ("Verordnung (EG) Nr. 528/2012 über Biozidprodukte:", LabelKind.BIOCIDES),
        (
            "· Inhaltsstoffe nach Detergenzienverordnung EG 648/2004",
            LabelKind.DETERGENTS,
        ),
        (
            "Kennzeichnung der Inhaltsstoffe gemäß Verordnung (EG) Nr. 648/2004, Anhang VII:",
            LabelKind.DETERGENTS,
        ),
        (
            "Zusätzliche Angaben gemäß Verordnung (EG) Nr. 648/2004 (Detergenzienverordnung):",
            LabelKind.DETERGENTS,
        ),
    ],
)
def test_each_heading_of_another_regulation(heading: str, kind: LabelKind) -> None:
    main, [block] = split_label_blocks(
        f"P102 Darf nicht.\n{heading}\nEnthält Musterol.\n\nP280"
    )

    assert block.kind is kind
    assert block.lines == ["Enthält Musterol."]
    assert main == "P102 Darf nicht.\n\nP280"


@pytest.mark.spec("SDB-191")
def test_a_label_for_consumers_says_so() -> None:
    main = _parsed(
        "Signalwort: Achtung\nH317 Kann allergische Hautreaktionen verursachen.\n"
        "Obige Kennzeichnung gilt bei Abgabe an privaten Endverbraucher."
    ).sheet.hazard_statements

    assert main.condition is LabelCondition.CONSUMERS
    assert (
        main.condition_text
        == "Obige Kennzeichnung gilt bei Abgabe an privaten Endverbraucher."
    )
    assert main.hazard_codes == ["H317"]


@pytest.mark.spec("SDB-192")
def test_statements_for_consumers_carry_their_condition() -> None:
    main = _parsed(
        "Signalwort: Achtung\nH317 Kann allergische Hautreaktionen verursachen.\n"
        "Sicherheitshinweis:\n"
        '"***" ***Nur für private Endverbraucher: P101 Ist ärztlicher Rat erforderlich,\n'
        "Verpackung oder Kennzeichnungsetikett bereithalten. P102 Darf nicht in die Hände von\n"
        "Kindern gelangen.***\n"
        "P280 Schutzhandschuhe tragen."
    ).sheet.hazard_statements

    assert main.statement_conditions == {
        "P101": LabelCondition.CONSUMERS,
        "P102": LabelCondition.CONSUMERS,
    }
    assert main.precautionary_codes == ["P101", "P102", "P280"]


@pytest.mark.spec("SDB-192")
def test_statements_under_a_heading_for_consumers() -> None:
    main = _parsed(
        "Signalwort: Achtung\nH317 Kann allergische Hautreaktionen verursachen.\n"
        "P280 – Schutzhandschuhe tragen.\n"
        "Für den privaten Endabnehmer steht zusätzlich auf dem Etikett.:\n"
        "P102 – Darf nicht in die Hände von Kindern gelangen.\n"
        "Zusätzliche Angaben gemäß Verordnung (EG) Nr. 648/2004 (Detergenzienverordnung):\n"
        "Enthält: Unter 5 % anionische Tenside."
    ).sheet.hazard_statements

    assert main.statement_conditions == {"P102": LabelCondition.CONSUMERS}
    [detergents] = main.further_labels
    assert detergents.kind is LabelKind.DETERGENTS


@pytest.mark.spec("SDB-192")
@pytest.mark.parametrize(
    "remark",
    [
        "Die Kennzeichnung mit dem EUH210 muss auf dem Kennzeichnungsetikett der "
        "Verpackungen von Gemischen\nangebracht sein, die nicht für die breite "
        "Öffentlichkeit bestimmt sind.",
        "Die Kennzeichnung mit EUH210 darf entfallen, wenn das Produkt auch an die "
        "Breite Öffentlichkeit abgegeben wird.",
    ],
)
def test_euh210_for_others_than_the_general_public(remark: str) -> None:
    main = _parsed(
        f"EUH210\nSicherheitsdatenblatt auf Anfrage erhältlich.\nBemerkungen:\n{remark}",
        "Das Gemisch ist nicht eingestuft.",
    ).sheet.hazard_statements

    assert main.supplemental_codes == ["EUH210"]
    assert main.statement_conditions == {"EUH210": LabelCondition.NOT_GENERAL_PUBLIC}


@pytest.mark.spec("SDB-193")
def test_a_small_package_lacks_a_statement_the_regulation_keeps_there() -> None:
    findings = _findings(
        "Signalwort: Achtung\nH317 Kann allergische Hautreaktionen verursachen.\n"
        "H319 Verursacht schwere Augenreizung.\nP280 Schutzhandschuhe tragen.\n"
        f"{_SMALL}\nSignalwort: Achtung\nGefahrenhinweise entfällt\n"
        "P280 Schutzhandschuhe tragen.",
        "Skin Sens. 1, H317\nEye Irrit. 2, H319",
    )

    # H319 a small package may leave out (Annex I 1.5.2.1.1), H317 not.
    assert findings == [("small-package-hazard-statement-not-in-label", "H317")]


@pytest.mark.spec("SDB-193")
def test_a_small_package_keeps_the_signal_word_its_codes_call_for() -> None:
    findings = _findings(
        "Signalwort: Gefahr\n"
        "H271 Kann Brand oder Explosion verursachen; starkes Oxidationsmittel.\n"
        "P210 Von Hitze fernhalten.\n"
        f"{_SMALL}\nSignalwort:\nGefahrenhinweise\n"
        "H271 Kann Brand oder Explosion verursachen; starkes Oxidationsmittel.",
        "Ox. Sol. 1, H271",
    )

    assert findings == [("small-package-signal-word-not-found", "Gefahr")]


@pytest.mark.spec("SDB-193")
def test_a_small_package_s_label_of_sentences_alone_keeps_the_rest() -> None:
    findings = _findings(
        "Signalwort: Achtung\nH336 Kann Schläfrigkeit und Benommenheit verursachen.\n"
        "P102 Darf nicht in die Hände von Kindern gelangen.\n"
        f"{_SMALL}\nKann Schläfrigkeit und Benommenheit verursachen.\n"
        "Darf nicht in die Hände von Kindern gelangen.",
        "STOT SE 3, H336",
    )

    assert findings == []


@pytest.mark.spec("SDB-193")
def test_h290_calls_for_nothing_on_a_small_package() -> None:
    findings = _findings(
        "Signalwort: Achtung\nH290 Kann gegenüber Metallen korrosiv sein.\n"
        "P234 Nur in Originalverpackung aufbewahren.\n"
        f"{_SMALL}\nH290 Kann gegenüber Metallen korrosiv sein.",
        "Met. Corr. 1, H290",
    )

    assert findings == []


@pytest.mark.spec("SDB-198")
def test_a_small_aerosol_keeps_its_own_elements() -> None:
    expected = clp_expected(
        HazardStatements(hazard_codes=["H222", "H229", "H336"]), small_package=True
    )

    assert expected.signal_word == "Gefahr"
    assert expected.pictograms == ["GHS02", "GHS07"]


@pytest.mark.spec("SDB-198", "SDB-194")
def test_an_aerosol_s_own_statements_are_reported_missing() -> None:
    assert _findings(
        "Signalwort: Achtung\nP210 Von Hitze fernhalten.", "Aerosol 3, H229"
    ) == [("label-without-hazard-statement", "")]
    assert ("small-package-hazard-statement-not-in-label", "H229") in _findings(
        "Signalwort: Achtung\nH229 Behälter steht unter Druck: Kann bei Erwärmung bersten.\n"
        f"P210 Von Hitze fernhalten.\n{_SMALL}\nSignalwort: Achtung\nGefahrenhinweise entfällt",
        "Aerosol 3, H229",
    )


@pytest.mark.spec("SDB-199")
def test_a_signal_word_that_conflicts_with_the_codes() -> None:
    assert ("signal-word-conflicts", "Achtung") in _findings(
        "Signalwort: Achtung\nH318 Verursacht schwere Augenschäden.\nP280 Augenschutz tragen.",
        "Eye Dam. 1, H318",
    )
    assert ("signal-word-conflicts", "Gefahr") in _findings(
        "Signalwort: Gefahr\nH315 Verursacht Hautreizungen.\nP280 Schutzhandschuhe tragen.",
        "Skin Irrit. 2, H315",
    )
    # H228 is "Gefahr" in category 1 and "Achtung" in category 2.
    assert not [
        f
        for f in _findings(
            "Signalwort: Achtung\nH228 Entzündbarer Feststoff.\nP210 Von Hitze fernhalten.",
            "Flam. Sol. 1, H228",
        )
        if f[0] == "signal-word-conflicts"
    ]


@pytest.mark.spec("SDB-199", "SDB-193")
def test_a_small_package_s_signal_word_against_the_product_s_codes() -> None:
    assert ("small-package-signal-word-conflicts", "Achtung") in _findings(
        "Signalwort: Gefahr\nH270 Kann Brand verursachen oder verstärken; Oxidationsmittel.\n"
        "H280 Enthält Gas unter Druck; kann bei Erwärmung explodieren.\n"
        f"P220 Von Kleidung fernhalten.\n{_SMALL}\nSignalwort: Achtung\nGefahrenhinweise entfällt",
        "Ox. Gas 1, H270\nPress. Gas, H280",
    )


@pytest.mark.spec("SDB-193", "SDB-179")
def test_a_small_package_s_pictograms_are_its_own_drawing(tmp_path: Path) -> None:
    path = _pages(
        tmp_path / "zwei.pdf",
        [
            "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006",
            "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs",
            "Handelsname: Musterbleiche",
            "Überarbeitet am: 02.09.2024",
            "ABSCHNITT 2: Mögliche Gefahren",
            "2.1 Einstufung des Stoffs oder Gemischs",
            "Ox. Sol. 1, H271; Acute Tox. 4, H302",
            "2.2 Kennzeichnungselemente",
            "Gefahrenpiktogramme",
            ["GHS03", "GHS07"],
            "Signalwort: Gefahr",
            "H271 Kann Brand oder Explosion verursachen; starkes Oxidationsmittel.",
            "H302 Gesundheitsschädlich bei Verschlucken.",
            "P210 Von Hitze fernhalten.",
            _SMALL,
            "Gefahrenpiktogramme",
            ["GHS07"],
            "Signalwort: Gefahr",
            "H271 Kann Brand oder Explosion verursachen; starkes Oxidationsmittel.",
            "2.3 Sonstige Gefahren",
            "Keine.",
            "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen",
        ],
    )
    images = read_label_images(path)

    assert images.labels == [["GHS03", "GHS07"]]
    assert images.small_packages == [[["GHS07"]]]
    reading = read_sheet(path)
    assert reading.parser_result is not None
    main = reading.parser_result.sheet.hazard_statements
    [small] = main.further_labels
    assert main.pictograms == ["GHS03", "GHS07"]
    assert small.label.pictograms == ["GHS07"]
    assert small.label.drawing_read
    findings = sheet_findings(
        reading.parser_result.sheet, reading.parser_result.warnings
    )
    assert [(f.code, f.params) for f in findings] == [
        ("small-package-pictogram-not-found", {"pictogram": "GHS03"})
    ]


@pytest.mark.spec("SDB-194")
def test_a_label_may_be_a_small_package_s_where_the_sheet_prints_none() -> None:
    label = (
        "Signalwort: Achtung\nH317 Kann allergische Hautreaktionen verursachen.\n"
        "P280 Schutzhandschuhe tragen."
    )
    classification = "Skin Sens. 1, H317\nSkin Irrit. 2, H315\nAquatic Chronic 2, H411\nAcute Tox. 4, H302"

    assert _findings(label, classification) == []
    # Beside a small package's label it is a larger package's.
    beside = _findings(f"{label}\n{_SMALL}\nH317", classification)
    assert ("hazard-statement-not-in-label", "H315") in beside
    assert ("hazard-statement-not-in-label", "H411") in beside


@pytest.mark.spec("SDB-194")
def test_a_label_without_what_a_small_package_may_leave_out() -> None:
    assert _findings("Signalwort: Achtung", "Eye Irrit. 2, H319") == []
    assert (
        _findings(
            "Signalwort: Achtung\nH412 Schädlich für Wasserorganismen, mit langfristiger Wirkung.",
            "Aquatic Chronic 3, H412",
        )
        == []
    )
    assert ("label-without-precautionary-statement", "") in _findings(
        "Signalwort: Achtung\nH317 Kann allergische Hautreaktionen verursachen.",
        "Skin Sens. 1, H317",
    )


@pytest.mark.spec("SDB-194", "BIB-25")
def test_h290_calls_for_a_signal_word_only_beside_a_small_package_s_label() -> None:
    alone = HazardStatements(hazard_codes=["H290"], signal_word="Achtung")
    larger = HazardStatements(
        hazard_codes=["H290"],
        further_labels=[FurtherLabel(LabelKind.SMALL_PACKAGE, _SMALL)],
    )

    assert clp_expected(alone).signal_word is None
    assert not clp_expected(alone).signal_word_differs
    assert clp_expected(larger).signal_word == "Achtung"
    assert clp_expected(larger).signal_word_missing


@pytest.mark.spec("SDB-195")
def test_a_sealed_spray_attachment_needs_no_h304() -> None:
    label = (
        "Signalwort: Gefahr\nH226 Flüssigkeit und Dampf entzündbar.\n"
        "Die Kennzeichnung einer Aspirationsgefahr ist für Behälter mit\n"
        "versiegelter Sprühvorrichtung nicht vorgeschrieben.\n"
        f"P280 Schutzhandschuhe tragen.\n{_SMALL}\nH226"
    )
    with_it = _findings(label, "Flam. Liq. 3, H226\nAsp. Tox. 1, H304")
    without = _findings(
        label.replace("versiegelter Sprühvorrichtung", "Sprühflasche"),
        "Flam. Liq. 3, H226\nAsp. Tox. 1, H304",
    )

    assert ("hazard-statement-not-in-label", "H304") not in with_it
    assert ("hazard-statement-not-in-label", "H304") in without


@pytest.mark.spec("SDB-196", "SDB-28")
def test_a_treated_article_is_no_euh208() -> None:
    result = _parsed(
        "Signalwort: Gefahr\nH222 Extrem entzündbares Aerosol.\n"
        "P102 Darf nicht in die Hände von Kindern gelangen.",
        "Aerosol 1, H222\n"
        "Mit Konservierungsmittel MUSTERIN behandelte Ware. Kann allergische\n"
        "Reaktionen hervorrufen.",
    )

    assert "euh-wording-outside-label" not in [w.code for w in result.warnings]


@pytest.mark.spec("SDB-196", "SDB-28")
def test_an_euh_wording_outside_the_label_is_still_noted() -> None:
    result = _parsed(
        "Signalwort: Gefahr\nH222 Extrem entzündbares Aerosol.\n"
        "P102 Darf nicht in die Hände von Kindern gelangen.",
        "Aerosol 1, H222\nMusterol. Kann allergische Reaktionen hervorrufen.",
    )

    assert "euh-wording-outside-label" in [w.code for w in result.warnings]


@pytest.mark.spec("SDB-196")
def test_a_block_beside_the_label_and_its_empty_lines_are_inside_it() -> None:
    result = _parsed(
        "Signalwort: Gefahr\n\nH222 Extrem entzündbares Aerosol.\n\n"
        "P102 Darf nicht in die Hände von Kindern gelangen.\n"
        "Biozid-kennzeichnung\n"
        "Mit Konservierungsmittel MUSTERIN behandelte Ware. Kann allergische\n"
        "Reaktionen hervorrufen.\n\n"
        "Musterol. Kann allergische Reaktionen hervorrufen.",
        "Aerosol 1, H222",
    )

    assert "euh-wording-outside-label" not in [w.code for w in result.warnings]


@pytest.mark.spec("SDW-51", "BIB-21")
def test_the_record_keeps_the_blocks_and_reads_them_back() -> None:
    reading = read_extraction(
        extraction_from_dict(
            {
                "text": _SHEET.format(
                    classification="Flam. Liq. 3, H226\nSkin Sens. 1, H317",
                    label="Obige Kennzeichnung gilt bei Abgabe an privaten Endverbraucher.\n"
                    + _TWO_LABELS,
                ),
                "extractor": "pymupdf",
                "pages_sampled": 1,
                "warnings": [],
            }
        )
    )
    assert reading.parser_result is not None
    assert reading.extraction is not None
    sheet = reading.parser_result.sheet
    stored = sheet_to_dict(sheet, reading.extraction)
    label = stored["hazard_statements"]

    [small] = label["further_labels"]
    assert small["kind"] == "small-package"
    assert small["omitted_codes"] == []
    assert "further_labels" not in small["label"]
    assert label["condition"] == "consumers"
    assert label["statement_conditions"] == {}
    assert sheet_from_dict(stored) == sheet
    # A record stored before has none of the keys and reads back without them.
    for key in (
        "condition",
        "condition_text",
        "statement_conditions",
        "further_labels",
    ):
        del label[key]
    again = sheet_from_dict(stored).hazard_statements
    assert again.further_labels == []
    assert again.condition is None


@pytest.mark.spec("BIB-24")
def test_kept_pictograms_of_before_have_no_small_packages() -> None:
    images = LabelImages(
        label_images_stage(),
        LabelImagesStatus.READ,
        [["GHS07"]],
        [0],
        [[["GHS06"]]],
        [[0]],
    )
    stored = label_images_to_dict(images)

    assert label_images_from_dict(stored) == images
    del stored["small_packages"], stored["small_packages_unrecognised"]
    assert label_images_from_dict(stored).small_packages == [[]]


@pytest.mark.spec("SDB-190")
def test_a_page_break_ends_no_block() -> None:
    main, [block] = split_label_blocks(
        "EUH208 Enthält Musterol. Kann allergische Reaktionen hervorrufen.\n"
        "Kennzeichnung gem. Verordnung (EU) Nr. 528/2012\n"
        "Seite: 2 (9)\n"
        "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006\n"
        "\n"
        "Handelsname: Musterlack\n"
        "\n"
        "Enthält ein Biozidprodukt: Musterin\n"
        "\n"
        "P102 Darf nicht in die Hände von Kindern gelangen.",
        frozenset({"Handelsname: Musterlack"}),
    )

    assert block.kind is LabelKind.BIOCIDES
    assert block.lines == ["Enthält ein Biozidprodukt: Musterin"]
    assert "Musterin" not in main
    assert main.endswith("P102 Darf nicht in die Hände von Kindern gelangen.")


@pytest.mark.spec("SDB-76", "SDB-188")
def test_a_small_package_s_label_speaks_of_the_product_s_sheet() -> None:
    sheet = _parsed(
        "Kennzeichnung gemäß Verordnung (EG) Nr. 1272/2008 entfällt\n"
        "Signalwort entfällt\n"
        f"{_SMALL}\n"
        "Enthält Musterol. Kann allergische Reaktionen hervorrufen.",
        "Das Gemisch ist nicht eingestuft.",
    ).sheet

    assert sheet.hazard_statements.supplemental_codes == []
    [small] = sheet.hazard_statements.further_labels
    assert small.label.supplemental_codes == ["EUH208"]
    assert sheet_duty(sheet) is SheetDuty.REQUIRED


@pytest.mark.spec("SDB-197", "SDW-42")
def test_a_label_statement_the_classification_does_not_name() -> None:
    result = _parsed(
        "Signalwort: Achtung\n"
        "H410 Sehr giftig für Wasserorganismen mit langfristiger Wirkung.\n"
        "P273 Freisetzung in die Umwelt vermeiden.",
        "Aquatic Acute 1, H400\nAquatic Chronic 2, H411",
    )
    findings = sheet_findings(result.sheet, result.warnings)

    assert [(f.code, f.params) for f in findings] == [
        (
            "hazard-statement-not-classified",
            {"statement": "H410", "classified": "H400, H411"},
        )
    ]
    # The reading stays as printed.
    assert result.sheet.hazard_statements.hazard_codes == ["H410"]


@pytest.mark.spec("SDB-197")
def test_a_statement_the_order_of_precedence_lets_2_1_leave_out() -> None:
    assert (
        _findings(
            "Signalwort: Achtung\n"
            "H400 Sehr giftig für Wasserorganismen.\n"
            "H410 Sehr giftig für Wasserorganismen mit langfristiger Wirkung.\n"
            "P273 Freisetzung in die Umwelt vermeiden.",
            "Aquatic Chronic 1, H410",
        )
        == []
    )


@pytest.mark.spec("SDB-193")
def test_a_small_package_keeps_the_pictograms_of_the_product() -> None:
    text = _SHEET.format(
        classification="Ox. Gas 1, H270\nPress. Gas, H280",
        label=(
            "Signalwort: Gefahr\n"
            "H270 Kann Brand verursachen oder verstärken; Oxidationsmittel.\n"
            "H280 Enthält Gas unter Druck; kann bei Erwärmung explodieren.\n"
            "Gefahrenpiktogramme\nP220 Von Kleidung fernhalten.\n"
            f"{_SMALL}\nGefahrenpiktogramme\nSignalwort: Gefahr\n"
            "Gefahrenhinweise entfällt"
        ),
    )
    images = LabelImages(
        label_images_stage(),
        LabelImagesStatus.READ,
        [["GHS03"]],
        [0],
        [[["GHS04"]]],
        [[0]],
    )
    result = read_extraction(
        extraction_from_dict(
            {"text": text, "extractor": "pymupdf", "pages_sampled": 1, "warnings": []}
        ),
        images,
    ).parser_result
    assert result is not None

    findings = sheet_findings(result.sheet, result.warnings)

    # 1.5.2.1.1 lets H270 and H280 go, never the oxidiser's pictogram; GHS04
    # is never expected (Art. 33).
    assert [(f.code, f.params) for f in findings] == [
        ("small-package-pictogram-not-found", {"pictogram": "GHS03"})
    ]


@pytest.mark.spec("SDB-193", "SDB-173")
def test_a_small_aerosol_needs_no_pictogram_for_the_aspiration_hazard() -> None:
    text = _SHEET.format(
        classification="Aerosol 1, H222, H229\nAsp. Tox. 1, H304",
        label=(
            "Signalwort: Gefahr\nH222 Extrem entzündbares Aerosol.\n"
            "H229 Behälter steht unter Druck: Kann bei Erwärmung bersten.\n"
            "Gefahrenpiktogramme\nP210 Von Hitze fernhalten.\n"
            f"{_SMALL}\nGefahrenpiktogramme\nSignalwort: Gefahr\nGefahrenhinweise\n"
            "H222-H229"
        ),
    )
    images = LabelImages(
        label_images_stage(),
        LabelImagesStatus.READ,
        [["GHS02"]],
        [0],
        [[["GHS02"]]],
        [[0]],
    )
    result = read_extraction(
        extraction_from_dict(
            {"text": text, "extractor": "pymupdf", "pages_sampled": 1, "warnings": []}
        ),
        images,
    ).parser_result
    assert result is not None

    assert sheet_findings(result.sheet, result.warnings) == []


@pytest.mark.spec("SDB-199")
def test_a_small_package_s_code_does_not_make_the_label_s_word_wrong() -> None:
    # Only the small package's label prints H331 ("Gefahr"): the sheet is
    # inconsistent, and the label's "Achtung" is not surely wrong.
    findings = _findings(
        "Signalwort: Achtung\nH317 Kann allergische Hautreaktionen verursachen.\n"
        f"P280 Schutzhandschuhe tragen.\n{_SMALL}\nSignalwort: Gefahr\n"
        "Gefahrenhinweise\nH317-H331",
        "Skin Sens. 1, H317",
    )

    assert not [f for f in findings if f[0].endswith("signal-word-conflicts")]
