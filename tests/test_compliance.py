"""What one sheet says about itself as a document, judged from the parser's reading."""

from __future__ import annotations

from datetime import date

import pytest

from sdb_reader.compliance import (
    Classification,
    SheetDuty,
    classification,
    contradicts_label,
    euh_outside_label,
    predates_annex_ii,
    sheet_duty,
    sheet_findings,
)
from sdb_reader.messages import Message
from sdb_reader.schema import (
    HazardStatements,
    SafetyDataSheet,
    Section,
    StatedClassification,
)


class TestAnnexII:
    def test_a_sheet_revised_before_2021_cannot_meet_it(self) -> None:
        assert predates_annex_ii(date(2020, 12, 31))

    def test_the_boundary_is_the_first_of_january_2021(self) -> None:
        assert not predates_annex_ii(date(2021, 1, 1))


class TestClassification:
    def test_an_h_code_classifies(self) -> None:
        assert classification(["H315"], None, []) is Classification.CLASSIFIED

    @pytest.mark.parametrize("word", ["Gefahr", "achtung", " Achtung "])
    def test_a_signal_word_alone_classifies(self, word: str) -> None:
        assert classification([], word, []) is Classification.CLASSIFIED

    def test_neither_is_not_classified(self) -> None:
        assert classification([], None, []) is Classification.NOT_CLASSIFIED

    def test_another_word_in_the_signal_word_field_does_not_classify(self) -> None:
        assert classification([], "keines", []) is Classification.NOT_CLASSIFIED

    def test_a_label_without_an_answer_is_undetermined_whatever_else_is_read(
        self,
    ) -> None:
        warnings = [Message("label-undetermined")]
        assert classification(["H315"], "Achtung", warnings) is (
            Classification.UNDETERMINED
        )

    @pytest.mark.spec("SDB-73")
    def test_r_phrases_classify_under_the_old_system(self) -> None:
        warnings = [Message("classified-before-clp", {"basis": "R20/21/22"})]
        assert classification([], None, warnings) is Classification.OLD_SYSTEM


class TestEuhOutsideTheLabel:
    @pytest.mark.spec("SDB-28")
    def test_the_statements_come_back_as_the_parser_read_them(self) -> None:
        outside = Message(
            "euh-wording-outside-label",
            {
                "statement": "EUH208",
                "sentence": (
                    "Enthält 2-Butanonoxim. Kann allergische Reaktionen hervorrufen."
                ),
            },
        )
        warnings = [Message("no-precautionary-codes"), outside]
        assert euh_outside_label(warnings) == [outside]

    def test_none_means_none(self) -> None:
        assert euh_outside_label([Message("no-hazard-codes")]) == []


def _sheet(
    *,
    revised: date | None = date(2024, 1, 1),
    issued: date | None = None,
    hazards: HazardStatements | None = None,
    sections: dict[Section, str] | None = None,
    stated: StatedClassification | None = None,
) -> SafetyDataSheet:
    """A sheet whose section 2 agrees with its label, unless *stated* says otherwise."""
    if stated is None:
        stated = (
            StatedClassification.CLASSIFIED
            if hazards is not None and hazards.hazard_codes
            else StatedClassification.NOT_CLASSIFIED
        )
    return SafetyDataSheet(
        product_identifier="Beispiel",
        issue_date=issued,
        revision_date=revised,
        version="1",
        language="de",
        hazard_statements=hazards or HazardStatements(),
        section_text=sections or {},
        stated_classification=stated,
    )


# Sections 11 and 12 as a sheet printed them before the 2020 version of Annex II.
_BEFORE_2020 = {
    Section.TOXICOLOGY: "11.1 Angaben zu toxikologischen Wirkungen\nAkute Toxizität: keine Daten",
    Section.ECOLOGY: "12.1 Toxizität\n12.5 Ergebnisse der PBT- und vPvB-Beurteilung\n12.6 Andere schädliche Wirkungen",
}
_LABELLED = HazardStatements(
    hazard_codes=["H315"], precautionary_codes=["P280"], signal_word="Achtung"
)


def _stating(
    label: dict[str, object] | None = None,
    stated: str | None = None,
    *,
    voluntary: bool = False,
    article: bool = False,
) -> SafetyDataSheet:
    """A sheet with this label that states this about its product."""
    return SafetyDataSheet(
        None,
        None,
        None,
        None,
        "de",
        hazard_statements=HazardStatements(**(label or {})),
        stated_classification=StatedClassification(stated or "not-stated"),
        stated_voluntary=voluntary,
        stated_article=article,
    )


def _kinds(sheet: SafetyDataSheet, warnings: list[Message] | None = None) -> list[str]:
    return [f.code for f in sheet_findings(sheet, warnings or [])]


class TestSheetFindings:
    def test_a_current_clean_sheet_has_none(self) -> None:
        assert _kinds(_sheet()) == []

    @pytest.mark.spec("SDW-50")
    def test_a_deviating_wording_names_the_code_and_both_wordings(self) -> None:
        hazards = HazardStatements(
            precautionary_codes=["P305", "P351", "P338"],
            precautionary_text=(
                "P305+P351+P338 BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang "
                "behutsam mit Wasser waschen. Eventuell vorhandene Kontaktlinsen "
                "nach Möglichkeit entfernen. Weiter waschen."
            ),
        )

        [finding] = sheet_findings(_sheet(hazards=hazards), [])

        assert finding.code == "wording-deviates"
        assert finding.params["statement"] == "P305+P351+P338"
        assert "waschen" in finding.params["sheet"]
        assert "Weiter spülen." in finding.params["regulation"]

    @pytest.mark.spec("SDW-50")
    def test_euh_statements_are_compared_too(self) -> None:
        hazards = HazardStatements(
            supplemental_codes=["EUH401"],
            supplemental_text=(
                "EUH401 Zur Vermeidung von Risiken für Mensch und Umwelt die "
                "Gebrauchsanweisung einhalten."
            ),
        )

        assert _kinds(_sheet(hazards=hazards)) == ["wording-deviates"]

    @pytest.mark.spec("SDW-50")
    def test_a_combination_in_its_parts_wordings_is_no_finding(self) -> None:
        hazards = HazardStatements(
            precautionary_codes=["P305", "P351", "P338"],
            precautionary_text=(
                "P305+P351+P338 BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang "
                "behutsam mit Wasser ausspülen. Eventuell vorhandene Kontaktlinsen "
                "nach Möglichkeit entfernen. Weiter ausspülen."
            ),
        )

        assert _kinds(_sheet(hazards=hazards)) == []

    @pytest.mark.spec("SDW-7")
    def test_a_sheet_revised_before_2021(self) -> None:
        assert _kinds(_sheet(revised=date(2020, 12, 31))) == ["predates-annex-ii"]

    @pytest.mark.spec("SDW-7")
    def test_an_issue_date_stands_in_for_a_missing_revision_date(self) -> None:
        assert _kinds(_sheet(revised=None, issued=date(2019, 5, 1))) == [
            "predates-annex-ii"
        ]

    @pytest.mark.spec("SDW-7")
    def test_a_sheet_without_a_readable_date(self) -> None:
        assert _kinds(_sheet(revised=None)) == ["undated"]

    @pytest.mark.spec("SDW-7")
    def test_a_label_that_leaves_the_classification_undetermined(self) -> None:
        warnings = [Message("label-undetermined")]
        assert _kinds(_sheet(), warnings) == ["classification-undetermined"]

    @pytest.mark.spec("SDW-7", "SDB-28")
    def test_an_euh_statement_only_outside_the_label(self) -> None:
        sentence = "Wiederholter Kontakt kann zu spröder oder rissiger Haut führen."
        warnings = [
            Message(
                "euh-wording-outside-label",
                {"statement": "EUH066", "sentence": sentence},
            )
        ]

        [finding] = sheet_findings(_sheet(), warnings)

        assert finding == Message(
            "euh-outside-label", {"statement": "EUH066", "sentence": sentence}
        )

    @pytest.mark.spec("SDW-9", "SDB-73")
    def test_a_sheet_classified_under_the_old_system(self) -> None:
        warnings = [Message("classified-before-clp", {"basis": "Xi - Reizend"})]
        assert _kinds(_sheet(revised=date(2023, 7, 24)), warnings) == [
            "old-classification",
        ]

    @pytest.mark.spec("SDW-9")
    def test_a_labelled_sheet_dated_after_2020_in_the_older_format(self) -> None:
        sheet = _sheet(
            revised=date(2022, 3, 1), hazards=_LABELLED, sections=_BEFORE_2020
        )

        [finding] = sheet_findings(sheet, [])

        assert finding == Message("old-format", {"revised": "2022-03-01"})

    @pytest.mark.spec("SDW-9")
    @pytest.mark.parametrize(
        ("section", "line"),
        [
            (
                Section.HAZARDS,
                "Das Produkt enthält keine Stoffe mit endokrinschädlichen Eigenschaften.",
            ),
            (Section.TOXICOLOGY, "11.2 Angaben über sonstige Gefahren"),
            (Section.ECOLOGY, "12.7 Andere schädliche Wirkungen"),
        ],
    )
    def test_one_mark_of_the_2020_format_is_enough(
        self, section: Section, line: str
    ) -> None:
        sections = {**_BEFORE_2020}
        sections[section] = sections.get(section, "") + "\n" + line
        sheet = _sheet(revised=date(2022, 3, 1), hazards=_LABELLED, sections=sections)
        assert _kinds(sheet) == []

    @pytest.mark.spec("SDW-9")
    def test_a_sheet_without_a_label_owes_the_format_nothing(self) -> None:
        assert _kinds(_sheet(revised=date(2022, 3, 1), sections=_BEFORE_2020)) == []

    @pytest.mark.spec("SDW-9", "SDB-76")
    def test_a_sheet_with_p_statements_alone_owes_the_format_nothing(self) -> None:
        advice = HazardStatements(precautionary_codes=["P102"])
        sheet = _sheet(revised=date(2022, 3, 1), hazards=advice, sections=_BEFORE_2020)
        assert _kinds(sheet) == []

    @pytest.mark.spec("SDW-9", "SDB-76")
    def test_a_sheet_classified_in_section_2_owes_the_format(self) -> None:
        """An article "nicht kennzeichnungspflichtig", classified all the same."""
        sheet = _sheet(
            revised=date(2022, 3, 1),
            sections=_BEFORE_2020,
            stated=StatedClassification.CLASSIFIED,
        )
        # Due for renewal, and its label read all the same (SDB-216): the
        # findings on its age and on its label.
        found = _kinds(sheet)
        assert found[0] == "old-format"
        assert "label-without-hazard-statement" in found

    @pytest.mark.spec("SDW-8", "SDB-75")
    def test_a_sheet_that_states_no_classification_and_no_label(self) -> None:
        sheet = _sheet(stated=StatedClassification.NOT_STATED)
        assert _kinds(sheet) == ["classification-not-stated"]

    @pytest.mark.spec("SDW-8", "SDB-75")
    def test_a_label_answers_where_section_2_does_not(self) -> None:
        sheet = _sheet(hazards=_LABELLED, stated=StatedClassification.NOT_STATED)
        assert _kinds(sheet) == []

    @pytest.mark.spec("SDW-9")
    def test_a_sheet_from_before_2021_is_reported_by_its_date_alone(self) -> None:
        sheet = _sheet(
            revised=date(2019, 3, 1), hazards=_LABELLED, sections=_BEFORE_2020
        )
        assert _kinds(sheet) == ["predates-annex-ii"]

    @pytest.mark.spec("SDW-9")
    def test_without_sections_11_and_12_the_format_is_not_judged(self) -> None:
        """What was not read cannot be found missing."""
        assert _kinds(_sheet(revised=date(2022, 3, 1), hazards=_LABELLED)) == []


class TestSection2AgainstTheLabel:
    @pytest.mark.spec("SDW-10", "SDB-79")
    def test_not_classified_and_a_hazard_statement_on_the_label(self) -> None:
        sheet = _sheet(hazards=_LABELLED, stated=StatedClassification.NOT_CLASSIFIED)
        assert _kinds(sheet) == ["classification-contradicts-label"]

    @pytest.mark.spec("SDB-79")
    @pytest.mark.parametrize(
        ("hazards", "stated", "contradiction"),
        [
            ({"hazard_codes": ["H317"]}, "not-classified", True),
            ({"signal_word": "Gefahr"}, "not-classified", True),
            ({"pictograms": ["GHS07"]}, "not-classified", True),
            ({"supplemental_codes": ["EUH208"]}, "not-classified", False),
            ({"precautionary_codes": ["P102"]}, "not-classified", False),
            ({"hazard_codes": ["H317"]}, "classified", False),
            ({"hazard_codes": ["H317"]}, "not-stated", False),
            ({"hazard_codes": ["H317"]}, None, False),
        ],
    )
    def test_what_counts_as_a_contradiction(
        self, hazards: dict[str, object], stated: str | None, contradiction: bool
    ) -> None:
        assert contradicts_label(_stating(hazards, stated)) is contradiction


class TestWhatCallsForASheet:
    """REACH Article 31(1) and (3): classified, or EUH210 on the label."""

    @pytest.mark.spec("SDB-76")
    @pytest.mark.parametrize(
        ("hazards", "stated", "required"),
        [
            ({"hazard_codes": ["H319"]}, None, True),
            ({"signal_word": "Achtung"}, None, True),
            ({"pictograms": ["GHS07"]}, None, True),
            ({"supplemental_codes": ["EUH210"]}, "not-classified", True),
            ({"precautionary_codes": ["P102", "P301"]}, "not-classified", False),
            ({"precautionary_codes": ["P102"]}, None, False),
            ({}, "classified", True),
            ({}, "classified-old-system", True),
            ({}, "not-classified", False),
            ({}, "not-stated", False),
            ({}, None, False),
        ],
    )
    def test_what_a_sheet_says_about_its_product(
        self, hazards: dict[str, object], stated: str | None, required: bool
    ) -> None:
        assert (sheet_duty(_stating(hazards, stated)) is SheetDuty.REQUIRED) is required


class TestLabelOfAClassifiedProduct:
    """What the label of a product section 2 classifies should carry and the
    parser did not find: reported beside the reading, never added to it."""

    _FULL = HazardStatements(
        hazard_codes=["H315"], precautionary_codes=["P280"], signal_word="Achtung"
    )

    @pytest.mark.spec("SDB-169", "SDB-171")
    def test_a_missing_hazard_statement_is_reported_and_not_added(self) -> None:
        """An aerosol whose label prints its signal word and P statements, but not
        the H229 its section 2.1 names."""
        label = HazardStatements(
            precautionary_codes=["P210", "P251", "P410", "P412"],
            signal_word="Achtung",
        )
        sheet = _sheet(hazards=label, stated=StatedClassification.CLASSIFIED)
        assert _kinds(sheet) == ["label-without-hazard-statement"]
        assert sheet.hazard_statements.hazard_codes == []

    @pytest.mark.spec("SDW-42", "SDB-172")
    def test_a_label_with_hazard_statements_only(self) -> None:
        label = HazardStatements(hazard_codes=["H317"], signal_word="Achtung")
        sheet = _sheet(hazards=label, stated=StatedClassification.CLASSIFIED)
        assert _kinds(sheet) == ["label-without-precautionary-statement"]

    @pytest.mark.spec("SDW-42", "SDB-170")
    def test_no_label_at_all(self) -> None:
        sheet = _sheet(
            hazards=HazardStatements(), stated=StatedClassification.CLASSIFIED
        )
        assert _kinds(sheet, [Message("no-label-section")]) == ["label-not-found"]

    @pytest.mark.spec("SDB-170")
    def test_label_elements_without_their_heading_count_as_a_label(self) -> None:
        label = HazardStatements(precautionary_codes=["P102"])
        sheet = _sheet(hazards=label, stated=StatedClassification.CLASSIFIED)
        assert _kinds(sheet, [Message("no-label-section")]) == [
            "label-without-hazard-statement"
        ]

    @pytest.mark.spec("SDB-171", "SDB-172")
    def test_a_label_found_empty_names_both(self) -> None:
        sheet = _sheet(
            hazards=HazardStatements(), stated=StatedClassification.CLASSIFIED
        )
        assert _kinds(sheet) == [
            "label-without-hazard-statement",
            "label-without-precautionary-statement",
        ]

    @pytest.mark.spec("SDB-170", "SDB-171", "SDB-172")
    @pytest.mark.parametrize(
        "stated",
        [
            StatedClassification.NOT_CLASSIFIED,
            StatedClassification.NOT_STATED,
            StatedClassification.OLD_SYSTEM,
        ],
    )
    def test_only_a_product_classified_under_clp(
        self, stated: StatedClassification
    ) -> None:
        sheet = _sheet(hazards=HazardStatements(), stated=stated)
        found = _kinds(sheet, [Message("no-label-section")])
        assert not {code for code in found if code.startswith("label-")}

    @pytest.mark.spec("SDB-170")
    def test_not_where_section_2_classifies_by_the_old_law(self) -> None:
        sheet = _sheet(
            hazards=HazardStatements(), stated=StatedClassification.CLASSIFIED
        )
        warnings = [Message("classified-before-clp", {"basis": "R36/38"})]
        assert "label-not-found" not in _kinds(sheet, warnings)
        assert "label-without-hazard-statement" not in _kinds(sheet, warnings)

    @pytest.mark.spec("SDB-170")
    def test_not_for_an_article(self) -> None:
        sheet = _stating({}, "classified", article=True)
        found = _kinds(sheet, [Message("no-label-section")])
        assert not {code for code in found if code.startswith("label-")}

    def test_a_complete_label_has_none(self) -> None:
        sheet = _sheet(hazards=self._FULL, stated=StatedClassification.CLASSIFIED)
        assert _kinds(sheet) == []


class TestSheetDueForRenewal:
    """A sheet whose label the reading withholds gets the findings on its age
    and no other (SDW-49, SDB-216); one due for renewal whose label is read
    gets all its findings."""

    @pytest.mark.spec("SDW-49", "SDB-216")
    def test_a_withheld_label_only_the_age(self) -> None:
        sheet = _sheet(
            revised=date(2013, 9, 2),
            hazards=HazardStatements(),
            stated=StatedClassification.CLASSIFIED,
        )
        sheet.label_withheld = "before-2017-06"
        assert _kinds(sheet, [Message("label-before-clp")]) == ["predates-annex-ii"]

    @pytest.mark.spec("SDW-49", "SDB-216")
    @pytest.mark.parametrize(
        ("revised", "sections", "age"),
        [
            (date(2020, 12, 31), None, "predates-annex-ii"),
            (date(2023, 3, 1), _BEFORE_2020, "old-format"),
        ],
    )
    def test_due_for_renewal_with_its_label_read_all_findings(
        self, revised: date, sections: dict[Section, str] | None, age: str
    ) -> None:
        sheet = _sheet(
            revised=revised,
            hazards=HazardStatements(),
            sections=sections,
            stated=StatedClassification.CLASSIFIED,
        )
        found = _kinds(sheet)
        assert found[0] == age
        assert "label-without-hazard-statement" in found

    @pytest.mark.spec("SDW-49", "SDB-170")
    def test_without_a_date_the_findings_stay(self) -> None:
        sheet = _sheet(
            revised=None,
            hazards=HazardStatements(),
            stated=StatedClassification.CLASSIFIED,
        )
        found = _kinds(sheet, [Message("label-before-clp")])
        assert "undated" in found
        assert "label-without-hazard-statement" in found
