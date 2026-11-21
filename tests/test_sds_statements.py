"""The wording a product shows is the regulation's, not the supplier's."""

from __future__ import annotations

import json

import pytest

from sdb_reader import statements
from sdb_reader.schema import HazardStatements
from sdb_reader.statements import (
    canonical_text,
    codes_from_wording,
    deviates_from_regulation,
    euh_statements_by_wording,
    label_statements,
    normalize_statements,
    render_statements,
    tidy_statements,
    wording_bounds,
    wordings_apart,
)


class TestCanonicalText:
    def test_a_statement_with_one_wording_is_returned(self) -> None:
        assert canonical_text("H315") == "Verursacht Hautreizungen."

    def test_a_menu_is_held_back(self) -> None:
        """A label carrying only "Augenschutz tragen" would otherwise gain three
        requirements it does not have."""
        assert canonical_text("P280") is None

    def test_a_sentence_with_a_hole_is_held_back(self) -> None:
        """ "Inhalt/Behälter … zuführen" -- the filling is in the sheet."""
        assert canonical_text("P501") is None

    def test_a_combination_is_known_by_its_joined_form(self) -> None:
        assert canonical_text("P403+P233") == (
            "An einem gut belüfteten Ort aufbewahren. Behälter dicht verschlossen halten."
        )

    def test_spacing_around_the_plus_does_not_matter(self) -> None:
        assert canonical_text("P403 + P233") == canonical_text("P403+P233")

    def test_an_unknown_code_returns_nothing(self) -> None:
        assert canonical_text("H999") is None


class TestRender:
    @pytest.mark.spec("SDB-18")
    def test_a_paraphrase_is_corrected(self) -> None:
        text, replaced = render_statements("H315: Verursacht Hautreizung.")

        assert text == "H315: Verursacht Hautreizungen."
        assert replaced == 1

    @pytest.mark.spec("SDB-18")
    def test_a_menu_is_left_as_the_sheet_printed_it(self) -> None:
        text, replaced = render_statements("P280: Augenschutz tragen.")

        assert text == "P280: Augenschutz tragen."
        assert replaced == 0

    def test_the_order_of_the_label_is_kept(self) -> None:
        original = "P280: Augenschutz tragen.\nH315: Verursacht Hautreizung.\nP501: X"

        text, _ = render_statements(original)

        assert [line.split(":")[0] for line in text.split("\n")] == [
            "P280",
            "H315",
            "P501",
        ]

    def test_a_truncated_combination_is_completed(self) -> None:
        """Suppliers print one half of a combined statement and drop the other.

        Measured over the corpus, this is one of the three things rendering
        repairs -- beside wording and page furniture that ran into the line.
        """
        text, replaced = render_statements("P403 + P235- Kühl halten.")

        assert "An einem gut belüfteten Ort aufbewahren." in text
        assert replaced == 1

    def test_a_line_the_pattern_does_not_recognise_survives(self) -> None:
        """This corrects wording; it never removes a statement."""
        original = "Gefahrenhinweise:\nkein Code hier\nH315: Verursacht Hautreizungen."

        text, _ = render_statements(original)

        assert "Gefahrenhinweise:" in text
        assert "kein Code hier" in text

    @pytest.mark.spec("SDB-30")
    def test_a_list_of_codes_gets_one_line_per_code(self) -> None:
        """One supplier prints "P102, P101, P501:"
        apart from the wordings, and 2.3 follows. Given P102's wording, the line
        lost P101; P501's text was "Andere Gefahren …"."""
        text, replaced = render_statements(
            "P102, P101, P501: Andere Gefahren, die zu keiner Einstufung führen"
        )

        assert text == (
            "P102: Darf nicht in die Hände von Kindern gelangen.\n"
            "P101: Ist ärztlicher Rat erforderlich, Verpackung oder "
            "Kennzeichnungsetikett bereithalten.\n"
            "P501"
        )
        assert replaced == 2

    @pytest.mark.spec("SDB-30")
    def test_a_code_without_one_wording_stands_alone_in_a_list(self) -> None:
        """P314 is a menu, P501 has a
        hole."""
        text, _ = render_statements("P102, P314, P405, P501")

        assert text.split("\n") == [
            "P102: Darf nicht in die Hände von Kindern gelangen.",
            "P314",
            "P405: Unter Verschluss aufbewahren.",
            "P501",
        ]

    @pytest.mark.spec("SDB-30")
    def test_a_list_followed_by_its_own_wordings_stays(self) -> None:
        """One supplier prints both statements behind both codes."""
        original = (
            "H222, H229: Extrem entzündbares Aerosol. Behälter steht unter "
            "Druck: Kann bei Erwärmung bersten."
        )

        assert render_statements(original) == (original, 0)

    @pytest.mark.spec("SDB-30")
    @pytest.mark.parametrize(
        "line",
        [
            "P302+P352, P333+P313: BEI BERÜHRUNG MIT DER HAUT: Mit viel Wasser "
            "waschen. Bei Hautreizung oder -ausschlag: Ärztlichen Rat einholen.",
            "P280, P501: Schutzhandschuhe tragen. Inhalt/Behälter der "
            "Sondermüllsammlung zuführen.",
            "EUH066, EUH208: Wiederholter Kontakt kann zu spröder oder rissiger "
            "Haut führen. Enthält Linalool. Kann allergische Reaktionen hervorrufen.",
        ],
    )
    def test_a_list_keeps_wordings_that_are_not_fixed(self, line: str) -> None:
        """A combination, a menu, a hole or an EUH statement: the sheet's
        sentences, which the regulation's single wordings would not cover."""
        assert render_statements(line) == (line, 0)

    @pytest.mark.spec("SDB-18")
    def test_an_euh_statement_keeps_the_sheets_wording(self) -> None:
        """The catalogue holds EUH wordings since SDB-28; they are read, not
        printed in the sheet's place."""
        original = "EUH066: Wiederholter Kontakt kann zu spröder Haut führen."

        assert render_statements(original) == (original, 0)

    @pytest.mark.spec("SDB-18")
    def test_two_statements_on_one_line_are_both_kept(self) -> None:
        original = "H222;H229 Extrem entzündbares Aerosol. Behälter steht unter Druck."

        assert render_statements(original) == (original, 0)

    @pytest.mark.spec("SDB-18")
    def test_a_code_of_the_other_kind_is_still_replaced(self) -> None:
        """Text that ran in from the precautionary block; that field has it."""
        text, replaced = render_statements(
            "H315: Verursacht Hautreizungen. Sicherheitshinweise: P101 Ist ..."
        )

        assert text == "H315: Verursacht Hautreizungen."
        assert replaced == 1

    @pytest.mark.spec("SDB-17", "SDB-18")
    def test_an_answer_with_dashes_keeps_every_statement(self) -> None:
        """The model's answer for a fuel system cleaner,
        normalised and rendered as the output is built."""
        answer = (
            "H304-Kann bei Verschlucken und Eindringen in die Atemwege tödlich "
            "sein. H412-Schädlich für Wasserorganismen, mit langfristiger Wirkung."
        )

        text, _ = render_statements(normalize_statements(answer, ("H", "EUH")))

        assert text == (
            "H304: Kann bei Verschlucken und Eindringen in die Atemwege tödlich sein.\n"
            "H412: Schädlich für Wasserorganismen, mit langfristiger Wirkung."
        )

    @pytest.mark.spec("SDB-30")
    def test_an_empty_wording_is_not_filled_in(self) -> None:
        """A bare code with no sentence is a parsing artefact, not a statement
        waiting to be completed."""
        text, replaced = render_statements("H315")

        assert text == "H315"
        assert replaced == 0

    def test_nothing_to_do_reports_nothing(self) -> None:
        assert render_statements("") == ("", 0)


class TestData:
    def test_every_entry_carries_a_kind_the_renderer_understands(self) -> None:
        raw = json.loads(statements.DATA_PATH.read_text(encoding="utf-8"))
        kinds = {e["kind"] for e in raw["statements"].values()}

        assert kinds <= {"fixed", "parameter", "alternatives", "disputed"}

    def test_no_amendment_apparatus_survived_the_extraction(self) -> None:
        """The consolidated text carries "►C4 … ◄" inline; it is not part of the
        sentence."""
        raw = json.loads(statements.DATA_PATH.read_text(encoding="utf-8"))

        for code, entry in raw["statements"].items():
            assert "►" not in entry["text"], code
            assert "◄" not in entry["text"], code

    def test_the_data_names_the_consolidation_it_came_from(self) -> None:
        raw = json.loads(statements.DATA_PATH.read_text(encoding="utf-8"))

        assert raw["source"].startswith("CELEX_02008R1272-")


class TestDisputedStatements:
    """Where the regulation prints a sentence twice and the two disagree."""

    def test_disputed_statements_are_not_rendered(self) -> None:
        """P103's two halves differ, so the supplier's wording stands.

        Annex IV Part 2 still carries the 2008 sentence; amendment M19 revised
        only the selection table in Part 1. Replacing here would put the
        superseded wording on the product.
        """
        assert canonical_text("P103") is None
        original = (
            "P103: Lesen Sie sämtliche Anweisungen aufmerksam und befolgen Sie diese."
        )
        assert render_statements(original) == (original, 0)

    def test_disputed_statements_carry_the_other_wording(self) -> None:
        """The conflict is recorded, not silently dropped."""
        raw = json.loads(statements.DATA_PATH.read_text(encoding="utf-8"))
        entry = raw["statements"]["P338"]
        assert entry["kind"] == "disputed"
        assert entry["text"] != entry["quoted_as"]

    def test_hazard_statements_are_checked_against_the_criteria_too(self) -> None:
        """Annex I quotes H229 with a capital where Annex III has lowercase.

        The check has to reach both annexes. Reading only the wording tables
        would leave this one rendered, and a product would take the case of one
        half of the regulation over the other.
        """
        assert canonical_text("H229") is None
        original = "H229: Behälter steht unter Druck: Kann bei Erwärmung bersten."
        assert render_statements(original) == (original, 0)

    def test_a_notation_difference_does_not_mask_what_a_statement_is(self) -> None:
        """H370 is quoted with round brackets, but it stays a parameter."""
        raw = json.loads(statements.DATA_PATH.read_text(encoding="utf-8"))
        entry = raw["statements"]["H370"]
        assert entry["kind"] == "parameter"
        assert "quoted_as" in entry


class TestCodesFromWording:
    """Reading a label that prints the sentences and not the codes."""

    def test_a_statement_is_recognised_by_its_wording(self) -> None:
        """Twenty sheets here name no code at all."""
        text = (
            "Gefahrenhinweise : Giftig für Wasserorganismen mit langfristiger Wirkung."
        )

        assert codes_from_wording(text) == {"H411"}

    def test_punctuation_and_case_do_not_distinguish_statements(self) -> None:
        """The sheet drops the comma the regulation writes, and that is all.

        Umlauts are left alone deliberately: the sheets carry them properly,
        and transliterating would be a normalisation nobody asked for with
        collisions nobody has looked for.
        """
        mit = codes_from_wording(
            "Giftig für Wasserorganismen, mit langfristiger Wirkung."
        )
        ohne = codes_from_wording(
            "GIFTIG FÜR WASSERORGANISMEN MIT LANGFRISTIGER WIRKUNG"
        )

        assert mit == ohne == {"H411"}

    def test_the_longer_statement_wins(self) -> None:
        """ "Entzündbares Aerosol" sits inside "Extrem entzündbares Aerosol".

        The two are mutually exclusive categories. Scanning without this
        reported both on 352 sheets.
        """
        assert codes_from_wording("Extrem entzündbares Aerosol.") == {"H222"}
        assert codes_from_wording("Entzündbares Aerosol.") == {"H223"}

    def test_several_statements_in_one_block(self) -> None:
        text = (
            "Gefahr Extrem entzündbares Aerosol. "
            "Behälter steht unter Druck: Kann bei Erwärmung bersten. "
            "Verursacht schwere Augenreizung."
        )

        assert codes_from_wording(text) == {"H222", "H229", "H319"}

    def test_a_label_that_says_nothing_yields_nothing(self) -> None:
        assert codes_from_wording("Kennzeichnung entfällt.") == set()
        assert codes_from_wording("") == set()

    def test_parameter_statements_are_not_matched(self) -> None:
        """Their wording carries a hole, so it never appears verbatim."""
        assert (
            codes_from_wording("Bei Temperaturen nicht über … °C aufbewahren.") == set()
        )


class TestEuhByWording:
    """EUH statements a label prints without their code (SDB-28)."""

    @pytest.mark.spec("SDB-28")
    def test_euh208_is_read_with_what_the_sheet_puts_in_the_hole(self) -> None:
        """A wood stain's sheet, broken as the text
        layer breaks it."""
        text = (
            "Kennzeichnungselemente: Enthält 3-Iod-2-propinylbutylcarbamat, "
            "CMIT/MIT(3:1),\nOcthilinon (ISO). Kann allergische\nReaktionen "
            "hervorrufen."
        )

        assert euh_statements_by_wording(text) == [
            (
                "EUH208",
                "Enthält 3-Iod-2-propinylbutylcarbamat, CMIT/MIT(3:1), "
                "Octhilinon (ISO). Kann allergische Reaktionen hervorrufen.",
            )
        ]

    @pytest.mark.spec("SDB-28")
    def test_two_substances_are_two_statements(self) -> None:
        text = (
            "Enthält Geraniol. Kann allergische Reaktionen hervorrufen. "
            "Enthält Citral. Kann allergische Reaktionen hervorrufen."
        )

        assert [sentence for _, sentence in euh_statements_by_wording(text)] == [
            "Enthält Geraniol. Kann allergische Reaktionen hervorrufen.",
            "Enthält Citral. Kann allergische Reaktionen hervorrufen.",
        ]

    @pytest.mark.spec("SDB-28")
    def test_a_fixed_statement_wins_over_the_one_with_a_hole(self) -> None:
        """EUH204, not EUH208 with "Isocyanate" in its hole."""
        text = "Enthält Isocyanate. Kann allergische Reaktionen hervorrufen."

        assert [code for code, _ in euh_statements_by_wording(text)] == ["EUH204"]

    @pytest.mark.spec("SDB-28")
    def test_the_warning_before_the_sentence_may_be_missing(self) -> None:
        text = (
            "Beim Sprühen können gefährliche lungengängige Tröpfchen entstehen. "
            "Aerosol oder Nebel nicht einatmen."
        )

        assert [code for code, _ in euh_statements_by_wording(text)] == ["EUH211"]

    @pytest.mark.spec("SDB-28")
    def test_a_printed_code_is_not_looked_for(self) -> None:
        text = "Wiederholter Kontakt kann zu spröder oder rissiger Haut führen."

        assert euh_statements_by_wording(text, skip={"EUH066"}) == []

    @pytest.mark.spec("SDB-28")
    def test_the_part_after_the_hole_is_enough_only_when_asked(self) -> None:
        """One supplier writes EUH208 without
        "Enthält"; enough to report, not to label."""
        text = "Kann allergische Reaktionen hervorrufen. 2-Butanonoxim."

        assert euh_statements_by_wording(text) == []
        assert euh_statements_by_wording(text, partial=True) == [
            ("EUH208", "Kann allergische Reaktionen hervorrufen.")
        ]

    @pytest.mark.spec("SDB-28")
    def test_a_hole_does_not_run_into_the_next_label_element(self) -> None:
        """A components line, then the label, then a bare sentence."""
        text = (
            "Enthält Xylol\nSignalwort: Achtung\nH226 Flüssigkeit und Dampf "
            "entzündbar.\nKann allergische Reaktionen hervorrufen."
        )

        assert euh_statements_by_wording(text) == []

    @pytest.mark.spec("SDB-28")
    def test_a_printed_code_keeps_its_wording_from_another_code(self) -> None:
        """EUH204 printed: its sentence is not EUH208 with "Isocyanate" too."""
        text = "EUH204 Enthält Isocyanate. Kann allergische Reaktionen hervorrufen."

        assert euh_statements_by_wording(text, skip={"EUH204"}) == []


class TestNormalizeStatements:
    """Test normalize_statements function."""

    def test_empty_string_returns_empty(self) -> None:
        """Should return empty string for empty input."""
        assert normalize_statements("", ["H", "P"]) == ""

    def test_whitespace_only_returns_empty(self) -> None:
        """Should return empty string for whitespace-only input."""
        assert normalize_statements("   \n\t  ", ["H", "P"]) == ""

    def test_normalizes_line_endings(self) -> None:
        """Should normalize various line endings to \\n."""
        text = "Line1\r\nLine2\rLine3\nLine4"
        result = normalize_statements(text, ["H"])
        assert result == "Line1\nLine2\nLine3\nLine4"

    def test_strips_leading_trailing_whitespace(self) -> None:
        """Should strip leading and trailing whitespace."""
        text = "  \n  Content  \n  "
        result = normalize_statements(text, ["H"])
        assert result == "Content"

    def test_removes_empty_lines(self) -> None:
        """Should remove empty lines and strip individual lines."""
        text = "Line1\n\n  \nLine2\n  Line3  \n\n"
        result = normalize_statements(text, ["H"])
        assert result == "Line1\nLine2\nLine3"

    def test_breaks_h_statements_onto_new_lines(self) -> None:
        """Should break H-statements onto separate lines."""
        text = "H225: Highly flammable H315: Causes skin irritation"
        result = normalize_statements(text, ["H"])
        assert "H225:" in result
        assert "H315:" in result
        # Should be on separate lines
        lines = result.split("\n")
        assert len(lines) == 2
        assert lines[0].strip().startswith("H225:")
        assert lines[1].strip().startswith("H315:")

    def test_breaks_p_statements_onto_new_lines(self) -> None:
        """Should break P-statements onto separate lines."""
        text = "P210: Keep away from heat P280: Wear protective gloves"
        result = normalize_statements(text, ["P"])
        lines = result.split("\n")
        assert len(lines) == 2
        assert lines[0].strip().startswith("P210:")
        assert lines[1].strip().startswith("P280:")

    def test_handles_combined_statements_with_plus(self) -> None:
        """Should handle combined statements like H225+H315."""
        text = "H225+H315: Highly flammable and causes skin irritation"
        result = normalize_statements(text, ["H"])
        # Should keep the combined statement together
        assert "H225+H315:" in result

    def test_keeps_three_part_combination_whole(self) -> None:
        """A combination that already has its colon must not be cut open.

        The colon inserter used to backtrack past "P338" to satisfy its own
        "not followed by a colon" guard, insert a colon after "P351", and leave
        the sentence on a line of its own -- so the first line held nothing but
        a plus sign and the eye wash instruction lost its opening.
        """
        text = (
            "P305 + P351 + P338: BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang "
            "behutsam mit Wasser spülen."
        )
        result = normalize_statements(text, ["P"])
        assert result == text
        assert "\n" not in result

    def test_still_inserts_colon_after_a_combination(self) -> None:
        """The guard must keep working where no colon is there yet."""
        text = "P305 + P351 + P338 BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang"
        result = normalize_statements(text, ["P"])
        assert result.startswith("P305 + P351 + P338: BEI KONTAKT")
        assert "\n" not in result

    def test_a_dash_where_the_colon_belongs_is_taken_over(self) -> None:
        """Models differ on the separator and the prompt does not settle it.

        gpt-5-mini writes "H220: Extrem entzündbares Gas", qwen3.8 writes
        "H220 - Extrem entzündbares Gas". Inserting without absorbing gives
        "H220: - Extrem entzündbares Gas" -- which the rendering hides on
        statements with one fixed wording, and cannot hide on the 61 held back
        as parameter, alternatives or disputed.
        """
        result = normalize_statements("P103 - Vor Gebrauch lesen.", ["P"])

        assert result == "P103: Vor Gebrauch lesen."

    def test_a_hyphen_inside_the_wording_is_left_alone(self) -> None:
        """Only the separator is absorbed, not punctuation in the sentence."""
        result = normalize_statements(
            "EUH208 - Enthält 1,2-Benzisothiazol-3(2H)-on.", ["EUH"]
        )

        assert result == "EUH208: Enthält 1,2-Benzisothiazol-3(2H)-on."

    def test_a_dash_after_a_combination_is_taken_over_too(self) -> None:
        result = normalize_statements(
            "P305 + P351 + P338 - BEI KONTAKT MIT DEN AUGEN: spülen.", ["P"]
        )

        assert result == "P305 + P351 + P338: BEI KONTAKT MIT DEN AUGEN: spülen."

    @pytest.mark.spec("SDB-17")
    def test_a_dash_without_spaces_is_taken_over(self) -> None:
        """As the sheet prints it, and the model copies it.

        Not split, the line went on to the rendering whole, and the wording of
        H304 replaced the H412 behind it.
        """
        result = normalize_statements(
            "H304-Kann bei Verschlucken tödlich sein. H412-Schädlich für "
            "Wasserorganismen, mit langfristiger Wirkung.",
            ["H", "EUH"],
        )

        assert result == (
            "H304: Kann bei Verschlucken tödlich sein.\n"
            "H412: Schädlich für Wasserorganismen, mit langfristiger Wirkung."
        )

    @pytest.mark.spec("SDB-17")
    def test_codes_a_dash_joins_stay_on_one_line(self) -> None:
        """ "H335-H336" joins two statements as a plus does; split at the
        second code, the first was left dangling on the line before."""
        result = normalize_statements(
            "H226 Flüssigkeit und Dampf entzündbar. H335-H336 Kann die Atemwege "
            "reizen. Kann Schläfrigkeit und Benommenheit verursachen.",
            ["H", "EUH"],
        )

        assert result == (
            "H226: Flüssigkeit und Dampf entzündbar.\n"
            "H335-H336: Kann die Atemwege reizen. "
            "Kann Schläfrigkeit und Benommenheit verursachen."
        )

    @pytest.mark.spec("SDB-30")
    def test_a_list_of_codes_stays_on_one_line(self) -> None:
        """For the rendering to read it as a list: split at "P501:", the
        line left "P102, P101," on its own and P501 with the text of 2.3."""
        result = normalize_statements(
            "P102, P101, P501: Andere Gefahren, die zu keiner Einstufung führen",
            ["P"],
        )

        assert result == (
            "P102, P101, P501: Andere Gefahren, die zu keiner Einstufung führen"
        )

    def test_handles_multiple_prefixes(self) -> None:
        """Should handle multiple statement prefixes."""
        text = "H225: Flammable P210: Keep away H315: Skin irritation"
        result = normalize_statements(text, ["H", "P"])
        lines = result.split("\n")
        assert len(lines) == 3

    def test_case_insensitive_matching(self) -> None:
        """Should match statements case-insensitively."""
        text = "h225: Flammable H315: Irritation"
        result = normalize_statements(text, ["H"])
        lines = result.split("\n")
        assert len(lines) == 2

    def test_already_formatted_text_unchanged(self) -> None:
        """Should leave already formatted text unchanged."""
        text = "H225: Flammable\nH315: Irritation"
        result = normalize_statements(text, ["H"])
        assert result == text

    def test_no_prefixes_returns_cleaned_text(self) -> None:
        """Should just clean text when no prefixes provided."""
        text = "Line1\n\n  Line2  "
        result = normalize_statements(text, [])
        assert result == "Line1\nLine2"

    def test_empty_prefix_list_returns_cleaned_text(self) -> None:
        """Should handle empty prefix list."""
        text = "H225: Flammable"
        result = normalize_statements(text, [])
        assert result == "H225: Flammable"

    def test_none_prefix_in_list_handled(self) -> None:
        """Should handle None values in prefix list."""
        text = "H225: Flammable P280: Protective gear"
        # Empty string in prefix list should be filtered
        result = normalize_statements(text, ["H", "", "P"])
        lines = result.split("\n")
        assert len(lines) == 2

    def test_all_empty_prefixes_returns_cleaned_text(self) -> None:
        """Should handle all empty prefixes in list."""
        text = "Some text here"
        result = normalize_statements(text, ["", "", ""])
        assert result == "Some text here"

    def test_text_with_only_whitespace_lines_returns_empty(self) -> None:
        """Should return empty when all lines are whitespace after stripping."""
        text = "   \n  \n   "
        result = normalize_statements(text, ["H"])
        assert result == ""

    def test_preserves_content_after_statement_codes(self) -> None:
        """Should preserve all content after statement codes."""
        text = "H225: Highly flammable liquid and vapour"
        result = normalize_statements(text, ["H"])
        assert "Highly flammable liquid and vapour" in result

    def test_inserts_missing_colon_single_statement(self) -> None:
        """Should insert colon when statement code has no colon."""
        text = "P101 Ist ärztlicher Rat erforderlich"
        result = normalize_statements(text, ["P"])
        assert result == "P101: Ist ärztlicher Rat erforderlich"

    def test_inserts_missing_colon_multiple_statements(self) -> None:
        """Should insert colon for every code in a run-on single line."""
        text = "P101 Ist ärztlicher Rat erforderlich P102 Darf nicht in Kinderhände gelangen"
        result = normalize_statements(text, ["P"])
        lines = result.split("\n")
        assert len(lines) == 2
        assert lines[0] == "P101: Ist ärztlicher Rat erforderlich"
        assert lines[1] == "P102: Darf nicht in Kinderhände gelangen"

    def test_colon_insertion_is_idempotent(self) -> None:
        """Should not add a second colon when one is already present."""
        text = "P101: Ist ärztlicher Rat erforderlich"
        result = normalize_statements(text, ["P"])
        assert result == "P101: Ist ärztlicher Rat erforderlich"
        assert "P101::" not in result

    def test_inserts_missing_colon_combined_codes(self) -> None:
        """Should insert colon for combined codes like P302 + P352 without colon."""
        text = "P302 + P352 Bei Kontakt mit der Haut"
        result = normalize_statements(text, ["P"])
        assert result.startswith("P302 + P352:")
        assert "Bei Kontakt mit der Haut" in result

    def test_inserts_missing_colon_preserves_umlaut_spacing(self) -> None:
        """Colon insertion must not collapse the space in 'Ist ärztlicher'."""
        text = "P101 Ist ärztlicher Rat erforderlich"
        result = normalize_statements(text, ["P"])
        assert "Ist ärztlicher" in result

    def test_multiline_text_missing_colons_each_line_fixed(self) -> None:
        """Each pre-split line that lacks a colon should get one."""
        text = "P101 Ist ärztlicher Rat erforderlich\nP102 Darf nicht in Kinderhände"
        result = normalize_statements(text, ["P"])
        lines = result.split("\n")
        assert lines[0] == "P101: Ist ärztlicher Rat erforderlich"
        assert lines[1] == "P102: Darf nicht in Kinderhände"


@pytest.mark.spec("SDW-5")
class TestLabelStatements:
    def test_each_statement_carries_both_wordings(self) -> None:
        hazards = HazardStatements(
            hazard_codes=["H315"],
            precautionary_codes=["P280", "P305", "P351", "P338"],
            hazard_text="H315 Verursacht Hautreizung.",
            precautionary_text=(
                "P280 Schutzhandschuhe tragen.\n"
                "P305 + P351 + P338 BEI KONTAKT MIT DEN AUGEN: Einige Minuten "
                "lang behutsam mit Wasser spülen. Eventuell vorhandene "
                "Kontaktlinsen nach Möglichkeit entfernen. Weiter spülen."
            ),
        )

        by_code = {s.code: s for s in label_statements(hazards)}

        assert by_code["H315"].sheet == "Verursacht Hautreizung."
        assert by_code["H315"].regulation == "Verursacht Hautreizungen."
        # A menu has no single wording.
        assert by_code["P280"].regulation is None
        assert by_code["P305+P351+P338"].regulation is not None

    def test_a_code_in_a_list_has_no_wording_of_the_sheets(self) -> None:
        hazards = HazardStatements(
            precautionary_codes=["P101", "P102"],
            precautionary_text="P102, P101:",
        )

        statements = label_statements(hazards)

        assert [(s.code, s.sheet) for s in statements] == [
            ("P102", None),
            ("P101", None),
        ]
        assert all(s.regulation for s in statements)

    def test_a_label_code_without_a_line_comes_last(self) -> None:
        hazards = HazardStatements(
            hazard_codes=["H315", "H412"], hazard_text="H315 Verursacht Hautreizungen."
        )

        assert [(s.code, s.sheet) for s in label_statements(hazards)] == [
            ("H315", "Verursacht Hautreizungen."),
            ("H412", None),
        ]

    def test_bare_codes_and_rows_of_codes_add_no_entry_of_their_own(self) -> None:
        hazards = HazardStatements(
            hazard_codes=["H314", "H335"],
            hazard_text=(
                "H314\n"
                "H314 Verursacht schwere Verätzungen der Haut und schwere "
                "Augenschäden.\n"
                "H314-H335"
            ),
        )

        assert [(s.code, s.sheet) for s in label_statements(hazards)] == [
            (
                "H314",
                "Verursacht schwere Verätzungen der Haut und schwere Augenschäden.",
            ),
            ("H335", None),
        ]

    def test_codes_joined_before_a_wording_share_it(self) -> None:
        wording = (
            "Kann die Atemwege reizen. Kann Schläfrigkeit und Benommenheit verursachen."
        )
        hazards = HazardStatements(
            hazard_codes=["H335", "H336"], hazard_text=f"H335-H336 {wording}"
        )

        assert [(s.code, s.sheet) for s in label_statements(hazards)] == [
            ("H335", wording),
            ("H336", wording),
        ]

    def test_a_code_the_label_does_not_carry_is_left_out(self) -> None:
        hazards = HazardStatements(
            precautionary_codes=["P102"],
            precautionary_text=(
                "P102 Darf nicht in die Hände von Kindern gelangen.\n"
                "P405 Unter Verschluss aufbewahren."
            ),
        )

        assert [s.code for s in label_statements(hazards)] == ["P102"]


_EYES = "BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang behutsam mit Wasser "
_SKIN = (
    "BEI BERÜHRUNG MIT DER HAUT (oder dem Haar): Alle kontaminierten "
    "Kleidungsstücke sofort ausziehen. "
)


@pytest.mark.spec("SDW-50")
class TestDeviatesFromRegulation:
    def test_another_word_deviates(self) -> None:
        assert deviates_from_regulation(
            "P305+P351+P338",
            _EYES + "spülen. Eventuell vorhandene Kontaktlinsen nach Möglichkeit "
            "entfernen. Weiter waschen.",
        )

    def test_a_missing_word_deviates(self) -> None:
        assert deviates_from_regulation(
            "P102", "Darf nicht in die Hände der Kinder gelangen."
        )

    def test_a_combination_in_its_parts_wordings_does_not_deviate(self) -> None:
        """P351 alone says "ausspülen", P338 "Weiter ausspülen"; the
        combination says "spülen" in both places."""
        assert not deviates_from_regulation(
            "P305+P351+P338",
            _EYES + "ausspülen. Eventuell vorhandene Kontaktlinsen nach "
            "Möglichkeit entfernen. Weiter ausspülen.",
        )

    @pytest.mark.parametrize(
        ("rinse", "rinse_on"),
        [("ausspülen", "spülen"), ("spülen", "ausspülen")],
    )
    def test_each_part_may_take_its_form_inside_the_combination(
        self, rinse: str, rinse_on: str
    ) -> None:
        """P351 alone says "ausspülen", inside P305+P351+P338 "spülen"; a
        sheet may mix the two forms part by part."""
        assert not deviates_from_regulation(
            "P305+P351+P338",
            _EYES + f"{rinse}. Eventuell vorhandene Kontaktlinsen nach "
            f"Möglichkeit entfernen. Weiter {rinse_on}.",
        )

    def test_a_part_in_neither_form_deviates(self) -> None:
        assert deviates_from_regulation(
            "P305+P351+P338",
            _EYES + "ausspülen. Eventuell vorhandene Kontaktlinsen nach "
            "Möglichkeit entfernen. Weiter waschen.",
        )

    def test_a_part_takes_its_units_of_the_combination_in_order(self) -> None:
        forms = statements._forms_inside("P305+P351+P338", statements._wordings_ever())

        assert "BEI KONTAKT MIT DEN AUGEN:" in forms[0]
        assert "Einige Minuten lang behutsam mit Wasser spülen." in forms[1]
        assert (
            "Eventuell vorhandene Kontaktlinsen nach Möglichkeit entfernen. "
            "Weiter spülen."
        ) in forms[2]

    def test_a_combination_of_one_sentence_gives_its_parts_no_form(self) -> None:
        """ "Giftig bei Verschlucken oder Hautkontakt" cannot be cut into H301
        and H311."""
        forms = statements._forms_inside("H301+H311", statements._wordings_ever())

        assert forms == [set(), set()]

    @pytest.mark.parametrize(
        ("code", "wording"),
        [
            ("P243", "Maßnahmen gegen elektrostatische Aufladungen treffen."),
            (
                "P305+P351+P338",
                _EYES + "spülen. Vorhandene Kontaktlinsen nach Möglichkeit "
                "entfernen. Weiter spülen.",
            ),
            ("P302+P334", "BEI KONTAKT MIT DER HAUT: In kaltes Wasser tauchen."),
        ],
    )
    def test_an_earlier_wording_of_the_regulation_does_not_deviate(
        self, code: str, wording: str
    ) -> None:
        assert not deviates_from_regulation(code, wording)

    @pytest.mark.parametrize(
        "ending",
        [
            "Haut mit Wasser abwaschen.",
            "Haut mit Wasser abwaschen oder duschen.",
            "Haut mit Wasser abwaschen/duschen.",
            "Haut mit Wasser abwaschen / duschen.",
            "Haut mit Wasser abwaschen [oder duschen].",
        ],
    )
    def test_a_part_in_brackets_may_be_left_out_or_given(self, ending: str) -> None:
        assert not deviates_from_regulation("P303+P361+P353", _SKIN + ending)
        assert not deviates_from_regulation("P353", ending)

    def test_another_word_for_a_part_in_brackets_deviates(self) -> None:
        assert deviates_from_regulation(
            "P303+P361+P353", _SKIN + "Haut mit Wasser abspülen."
        )

    @pytest.mark.parametrize(
        ("code", "wording"),
        [
            ("P102", "Darf nicht in Hände von Kindern gelangen."),
            (
                "EUH401",
                "Zur Vermeidung von Risiken für Mensch und Umwelt ist die "
                "Gebrauchsanleitung einzuhalten.",
            ),
            (
                "P304+P340",
                "BEI EINATMEN: Die Person an die frische Luft bringen und für die "
                "ungehinderte Atmung sorgen.",
            ),
        ],
    )
    def test_articles_auxiliaries_and_zu_do_not_count(
        self, code: str, wording: str
    ) -> None:
        assert not deviates_from_regulation(code, wording)

    @pytest.mark.parametrize(
        ("code", "wording"),
        [
            ("P102", "Darf in die Hände von Kindern gelangen."),
            ("P251", "Nicht durchstechen oder verbrennen, auch nach Gebrauch."),
            ("P251", "Durchstechen oder verbrennen, auch nicht nach Gebrauch."),
        ],
    )
    def test_a_missing_negation_deviates(self, code: str, wording: str) -> None:
        assert deviates_from_regulation(code, wording)

    def test_an_extra_negation_deviates(self) -> None:
        assert deviates_from_regulation(
            "P251",
            "Nicht durchstechen oder nicht verbrennen, auch nicht nach Gebrauch.",
        )

    def test_another_content_word_still_deviates(self) -> None:
        assert deviates_from_regulation(
            "EUH401",
            "Zur Vermeidung von Risiken für Mensch und Umwelt ist die "
            "Gebrauchsanweisung einzuhalten.",
        )

    def test_another_sentence_under_the_code_still_deviates(self) -> None:
        assert deviates_from_regulation(
            "P262", "Nicht in die Augen, Wunden oder gereizte Haut auftragen."
        )

    def test_case_punctuation_and_spacing_do_not_count(self) -> None:
        assert not deviates_from_regulation(
            "H412", "schädlich für  Wasserorganismen mit langfristiger Wirkung"
        )

    def test_marks_before_the_wording_do_not_count(self) -> None:
        assert not deviates_from_regulation(
            "P102", "| Darf nicht in die Hände von Kindern gelangen."
        )

    def test_text_after_the_complete_wording_does_not_count(self) -> None:
        assert not deviates_from_regulation(
            "P102", "Darf nicht in die Hände von Kindern gelangen. Prävention:"
        )

    def test_a_wording_that_begins_otherwise_is_not_compared(self) -> None:
        assert not deviates_from_regulation(
            "H412", "Das Produkt ist als gefährlich eingestuft gemäß …"
        )

    def test_a_line_with_another_code_of_its_kind_is_not_compared(self) -> None:
        assert not deviates_from_regulation(
            "H335", "Kann die Atemwege reizen. H336 Kann Schläfrigkeit verursachen."
        )

    def test_a_code_without_a_single_wording_never_deviates(self) -> None:
        assert not deviates_from_regulation("P280", "Augenschutz tragen.")

    def test_a_lettered_code_is_compared_with_its_effects_wording(self) -> None:
        assert not deviates_from_regulation(
            "H360D", "Kann das Kind im Mutterleib schädigen."
        )
        assert deviates_from_regulation("H360D", "Kann das Kind im Bauch schädigen.")


@pytest.mark.spec("SDW-50")
class TestEarlierWordings:
    """The wordings of earlier consolidations, shipped with the package."""

    def test_each_differs_from_todays_and_names_its_versions(self) -> None:
        data = json.loads(statements.EARLIER_PATH.read_text(encoding="utf-8"))
        current = json.loads(statements.DATA_PATH.read_text(encoding="utf-8"))

        assert data["current"] == current["source"]
        today_version = current["source"].split("-")[1][:8]
        for code, entries in data["statements"].items():
            today = statements._comparable(current["statements"][code]["text"])
            for entry in entries:
                assert statements._comparable(entry["text"]) != today
                assert entry["versions"]
                assert set(entry["versions"]) <= set(data["versions"])
                assert all(version < today_version for version in entry["versions"])


@pytest.mark.spec("SDB-47")
class TestTidyStatements:
    """The statement fields from either source: one form, each statement once."""

    def test_a_dash_and_a_space_after_the_code_become_a_colon(self) -> None:
        assert (
            normalize_statements(
                "P102- Darf nicht in die Hände von Kindern gelangen.", ("P",)
            )
            == "P102: Darf nicht in die Hände von Kindern gelangen."
        )

    def test_codes_joined_by_a_dash_stay_together(self) -> None:
        assert normalize_statements(
            "H335- H336 Kann die Atemwege reizen.", ("H",)
        ).startswith("H335- H336: ")

    def test_a_statement_stands_once(self) -> None:
        text = (
            "H302: Gesundheitsschädlich bei Verschlucken.\n"
            "H315: Verursacht Hautreizungen.\n"
            "H302- Gesundheitsschädlich bei Verschlucken"
        )

        assert tidy_statements(text) == (
            "H302: Gesundheitsschädlich bei Verschlucken.\n"
            "H315: Verursacht Hautreizungen."
        )

    def test_a_bare_code_beside_its_worded_line_goes(self) -> None:
        assert tidy_statements("H220\nH220: Extrem entzündbares Gas.") == (
            "H220: Extrem entzündbares Gas."
        )

    def test_a_bare_code_takes_the_regulations_only_wording(self) -> None:
        assert tidy_statements("P102\nEUH066") == (
            "P102: Darf nicht in die Hände von Kindern gelangen.\n"
            "EUH066: Wiederholter Kontakt kann zu spröder oder rissiger Haut führen."
        )

    def test_a_bare_code_without_one_wording_stays_alone(self) -> None:
        assert tidy_statements("P501") == "P501"

    def test_two_wordings_of_one_code_both_stay(self) -> None:
        text = "EUH208: Enthält Linalool. Kann allergische Reaktionen hervorrufen.\nEUH208: Enthält Citral. Kann allergische Reaktionen hervorrufen."

        assert tidy_statements(text) == text

    def test_a_code_that_only_opens_a_combination_stays_alone(self) -> None:
        """ "P301: BEI VERSCHLUCKEN:" tells nobody what to do."""
        assert tidy_statements("P301") == "P301"

    def test_two_spaces_behind_the_dash_keep_a_combination_together(self) -> None:
        assert normalize_statements(
            "P301-  P310 BEI VERSCHLUCKEN: Sofort Arzt anrufen.", ("P",)
        ) == ("P301-  P310: BEI VERSCHLUCKEN: Sofort Arzt anrufen.")


@pytest.mark.spec("SDB-30")
def test_a_word_that_only_begins_like_a_wording_is_not_one() -> None:
    """ "Inhalt/Behälter …" is not in "Gefährliche Inhaltsstoffe"."""
    text, _ = render_statements(
        "P102, P501: Gefährliche Inhaltsstoffe: Nicht anwendbar."
    )

    assert text == "P102: Darf nicht in die Hände von Kindern gelangen.\nP501"


@pytest.mark.spec("SDB-51")
class TestWordingBounds:
    @pytest.mark.parametrize(
        ("code", "begins", "ends"),
        [
            ("EUH208", "Enthält Linalool.", "Kann allergische Reaktionen hervorrufen."),
            ("P501", "Behälter der Wertstoffsammlung", "der Entsorgung zuführen!"),
            ("P501", "Inhalt und Behälter in", "zuführen."),
            ("P280", "Augenschutz oder Gesichtsschutz", "tragen."),
            ("P264", "Nach Gebrauch Hände", "gründlich waschen."),
            ("P304+P312", "BEI EINATMEN: Bei", "Arzt anrufen."),
            (
                "P321",
                "Besondere Behandlung (siehe",
                "auf diesem Kennzeichnungsetikett).",
            ),
        ],
    )
    def test_a_wording_is_known_by_its_first_and_last_words(
        self, code: str, begins: str, ends: str
    ) -> None:
        bounds = wording_bounds(code)

        assert bounds is not None
        assert bounds.opening.match(begins)
        closing = bounds.closing.search(ends)
        assert closing is not None
        assert closing.end() == len(ends)

    def test_another_word_does_not_begin_it(self) -> None:
        bounds = wording_bounds("P501")

        assert bounds is not None
        assert bounds.opening.match("Inhaltsstoffe: Aceton") is None

    def test_a_code_the_regulation_does_not_word_has_none(self) -> None:
        assert wording_bounds("P999") is None


@pytest.mark.spec("SDB-52")
class TestWordingsApart:
    def test_each_code_takes_its_sentence_in_the_codes_order(self) -> None:
        assert wordings_apart(
            ["P102", "P273", "P501"],
            [
                "Darf nicht in die Hände von Kindern gelangen.",
                "Freisetzung in die Umwelt vermeiden.",
                "Inhalt und Behälter in Übereinstimmung mit allen Gesetzen entsorgen.",
            ],
        ) == [
            "P102 Darf nicht in die Hände von Kindern gelangen.",
            "P273 Freisetzung in die Umwelt vermeiden.",
            "P501 Inhalt und Behälter in Übereinstimmung mit allen Gesetzen entsorgen.",
        ]

    def test_a_statement_runs_to_the_next_ones_start(self) -> None:
        assert wordings_apart(
            ["P305+P351+P338", "P405"],
            [
                "BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang behutsam mit Wasser "
                "ausspülen. Weiter ausspülen. Unter Verschluss aufbewahren."
            ],
        ) == [
            "P305+P351+P338 BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang behutsam "
            "mit Wasser ausspülen. Weiter ausspülen.",
            "P405 Unter Verschluss aufbewahren.",
        ]

    def test_the_end_of_one_wording_does_not_begin_the_next(self) -> None:
        """ "Behälter dicht verschlossen halten." closes P403+P233."""
        assert wordings_apart(
            ["P403+P233", "P501"],
            [
                "An einem gut belüfteten Ort aufbewahren. Behälter dicht verschlossen "
                "halten.",
                "Inhalt und Behälter gemäß den Vorschriften entsorgen.",
            ],
        ) == [
            "P403+P233 An einem gut belüfteten Ort aufbewahren. Behälter dicht "
            "verschlossen halten.",
            "P501 Inhalt und Behälter gemäß den Vorschriften entsorgen.",
        ]

    def test_a_wording_begins_only_where_a_sentence_does(self) -> None:
        assert (
            wordings_apart(
                ["P264"], ["Nicht durchstechen, auch nicht nach Gebrauch gründlich."]
            )
            is None
        )

    def test_one_code_without_its_sentence_leaves_all_without(self) -> None:
        assert (
            wordings_apart(
                ["P102", "P501"], ["Darf nicht in die Hände von Kindern gelangen."]
            )
            is None
        )

    def test_a_longer_wording_is_another_codes(self) -> None:
        """All of H400 is the beginning of H410."""
        assert (
            wordings_apart(
                ["H400"],
                ["Sehr giftig für Wasserorganismen mit langfristiger Wirkung."],
            )
            is None
        )

    def test_a_sentence_ends_where_its_wording_last_ends_one(self) -> None:
        """ "Tragen" inside the next sentence is not P280's end."""
        assert wordings_apart(
            ["P102", "P280"],
            [
                "Darf nicht in die Hände von Kindern gelangen. Schutzhandschuhe tragen. "
                "Kontaminierte Kleidung ausziehen und vor erneutem Tragen waschen."
            ],
        ) == [
            "P102 Darf nicht in die Hände von Kindern gelangen.",
            "P280 Schutzhandschuhe tragen.",
        ]

    def test_one_word_of_a_choice_does_not_make_the_wording(self) -> None:
        assert (
            wordings_apart(
                ["P501"], ["Behälter kann bei Erwärmung über 50 °C bersten."]
            )
            is None
        )
