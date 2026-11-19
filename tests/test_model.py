"""Reading a model's reply as an answer."""

from __future__ import annotations

import json

import pytest

from sdb_reader.model import read_answer


class TestReadAnswer:
    """The model's answer, tidied: strings always, a mapping always."""

    def test_missing_statement_fields_become_empty_strings(self) -> None:
        data = read_answer('{"supplier": {"name": "Muster GmbH"}}')
        assert data["hazard_statements"] == ""
        assert data["precautionary_statements"] == ""
        assert data["supplier"] == {"name": "Muster GmbH"}

    def test_a_supplier_that_is_not_a_mapping_becomes_empty(self) -> None:
        data = read_answer('{"supplier": "Muster GmbH"}')
        assert data["supplier"] == {}

    def test_statement_lists_are_joined_line_by_line(self) -> None:
        raw = json.dumps(
            {
                "hazard_statements": [
                    "H301: Giftig bei Verschlucken.",
                    "H315: Verursacht Hautreizungen.",
                ],
                "precautionary_statements": None,
            }
        )
        data = read_answer(raw)
        assert data["hazard_statements"] == (
            "H301: Giftig bei Verschlucken.\nH315: Verursacht Hautreizungen."
        )
        assert data["precautionary_statements"] == ""

    def test_a_statement_that_is_a_bare_number_becomes_its_text(self) -> None:
        data = read_answer('{"hazard_statements": 301}')
        assert data["hazard_statements"] == "301"

    def test_euh_continuation_lines_are_merged_onto_their_code(self) -> None:
        raw = json.dumps(
            {
                "supplemental_phrases": (
                    "EUH208: Enthält Permethrin. Kann allergische\n"
                    "Reaktionen hervorrufen.\n"
                    "EUH210: Sicherheitsdatenblatt auf Anfrage erhältlich."
                )
            }
        )
        data = read_answer(raw)
        assert data["supplemental_phrases"] == (
            "EUH208: Enthält Permethrin. Kann allergische Reaktionen hervorrufen.\n"
            "EUH210: Sicherheitsdatenblatt auf Anfrage erhältlich."
        )

    def test_a_leading_line_without_a_code_is_kept(self) -> None:
        raw = json.dumps(
            {"supplemental_phrases": "Enthält Permethrin.\nEUH210: Auf Anfrage."}
        )
        data = read_answer(raw)
        assert data["supplemental_phrases"] == (
            "Enthält Permethrin.\nEUH210: Auf Anfrage."
        )

    def test_the_legacy_supplemental_texts_key_is_normalised_too(self) -> None:
        """Older answers carry supplemental_texts."""
        raw = json.dumps(
            {
                "supplemental_texts": "EUH066: Wiederholter Kontakt kann zu\nspröder Haut führen."
            }
        )
        data = read_answer(raw)
        assert data["supplemental_texts"] == (
            "EUH066: Wiederholter Kontakt kann zu spröder Haut führen."
        )

    def test_prose_after_the_json_is_tolerated(self) -> None:
        raw = '```json\n{"hazard_statements": "H301: Giftig."}\n```\nMehr Text {hier}.'
        data = read_answer(raw)
        assert data["hazard_statements"] == "H301: Giftig."

    def test_an_answer_without_json_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no JSON object"):
            read_answer("kein JSON")
