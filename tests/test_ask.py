"""Asking a model and keeping its answer (SDW-25, SDW-26)."""

from __future__ import annotations

import json
import re
import socket
import threading
from collections.abc import Iterator
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import pymupdf
import pytest

from sdb_reader import ask, cli, extraction_from_dict, presets
from sdb_reader.extraction import extract_pdf_text

SHEET = """Sicherheitsdatenblatt
ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
Produktname: Bad- und Küchenfarbe
ABSCHNITT 2: Mögliche Gefahren
Verordnung (EG) Nr. 1907/2006
H412: Schädlich für Wasserorganismen, mit langfristiger Wirkung.
P101: Ist ärztlicher Rat erforderlich, Verpackung oder Kennzeichnungsetikett bereithalten.
"""

# The same sheet with the list of ingredients, whose statements are not the label's.
WITH_INGREDIENTS = (
    SHEET
    + """ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen
Musterstoff 1 - 5 %
H226: Flüssigkeit und Dampf entzündbar.
"""
)

LEAFLET = """Produktprospekt
ABSCHNITT 1: Allgemeine Hinweise
Dekorativer Anstrich für Innenräume.
"""

AGREEING = {
    "supplier": {},
    "hazard_statements": "H412: Schädlich für Wasserorganismen, mit langfristiger Wirkung.",
    "precautionary_statements": (
        "P101: Ist ärztlicher Rat erforderlich, Verpackung oder "
        "Kennzeichnungsetikett bereithalten."
    ),
}


def _pdf(path: Path, text: str) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


class _Model:
    """A chat-completions endpoint on this machine, answering as told."""

    def __init__(self) -> None:
        self.status = 200
        # Statuses for the next requests, one each, before *status* applies;
        # and a Retry-After header to send with a status that is no 200.
        self.statuses: list[int] = []
        self.retry_after: str | None = None
        self.body: bytes = b""
        # Bodies for the next requests, one each, before *body* applies.
        self.bodies: list[bytes] = []
        self.requests: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []
        self.paths: list[str] = []
        model = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(length))
                model.requests.append(request)
                body = model.bodies.pop(0) if model.bodies else model.body
                model.headers.append(dict(self.headers.items()))
                model.paths.append(self.path)
                status = model.statuses.pop(0) if model.statuses else model.status
                self.send_response(status)
                if status != 200 and model.retry_after is not None:
                    self.send_header("Retry-After", model.retry_after)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}/v1"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @staticmethod
    def _reply(answer: Any, usage: tuple[int, int] | None = None) -> bytes:
        content = answer if isinstance(answer, str) else json.dumps(answer)
        reply: dict[str, Any] = {
            "choices": [{"message": {"role": "assistant", "content": content}}]
        }
        if usage is not None:
            reply["usage"] = {"prompt_tokens": usage[0], "completion_tokens": usage[1]}
        return json.dumps(reply).encode()

    def answers(self, answer: Any) -> None:
        self.body = self._reply(answer)

    def answers_in_turn(
        self, *answers: Any, usage: tuple[int, int] | None = None
    ) -> None:
        """Answer the next requests with *answers*, one each."""
        self.bodies = [self._reply(answer, usage) for answer in answers]

    def names_the_date(self, literal: str | None) -> None:
        """Answer as the sheet reads, with *literal* as the revision date."""
        self.answers({**AGREEING, "revision_date": literal})

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Model]:
    for name in (
        cli.ENDPOINT_VARIABLE,
        cli.MODEL_VARIABLE,
        cli.API_KEY_VARIABLE,
        cli.REQUEST_VARIABLE,
        cli.PRESET_VARIABLE,
    ):
        monkeypatch.delenv(name, raising=False)
    served = _Model()
    served.answers(AGREEING)
    yield served
    served.close()


def _ask(
    capsys: pytest.CaptureFixture[str], model: _Model, *argv: str
) -> tuple[int, list[dict[str, Any]], str]:
    code = cli.main(["ask", "--endpoint", model.url, "--model", "some-model", *argv])
    out, err = capsys.readouterr()
    return code, json.loads(out), err


def _document(request: dict[str, Any]) -> str:
    """The file's text as a request carries it, between its markers."""
    content = request["messages"][1]["content"]
    found = re.search(r"<(sds_content_[0-9a-f]{16})>\n(.*)\n</\1>", content, re.DOTALL)
    assert found is not None
    return found.group(2)


def _extraction(text: str, pages: list[str] | None = None) -> Any:
    extraction = extraction_from_dict(
        {"text": text, "extractor": "pymupdf", "pages_sampled": 1, "warnings": []}
    )
    if pages is not None:
        extraction.metadata["pages"] = pages
    return extraction


# ---------------------------------------------------------------------------
# What the model is sent
# ---------------------------------------------------------------------------

LABEL = (
    "Sicherheitsdatenblatt\n" + "Kennzeichnung nach Verordnung (EG) Nr. 1272/2008. " * 5
)


@pytest.mark.spec("SDW-25")
@pytest.mark.parametrize(
    "heading",
    [
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen",
        "Abschnitt 3: Zusammensetzung / Angaben zu Bestandteilen",
        "ABSCHNITT 3",
        "ABSCHNITT 3 - Angaben zu Bestandteilen",
        "ABSCHNITT 03: Zusammensetzung/Angaben zu Bestandteilen",
        "* ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen",
        "• Abschnitt 3: Zusammensetzung",
        "3. Zusammensetzung/Angaben zu Bestandteilen",
        "3 Zusammensetzung / Angaben zu Bestandteilen",
        "03 Zusammensetzung/Angaben zu Bestandteilen",
        "* 3 ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen",
        "Zusammensetzung/Angaben zu Bestandteilen",
        "Zusammensetzung, Angaben zu Bestandteilen",
    ],
)
def test_the_text_ends_before_the_heading_of_section_3(heading: str) -> None:
    text = (
        f"{LABEL}\nH315: Verursacht Hautreizungen.\n{heading}\nH226 im Inhaltsstoff\n"
    )

    sent, which = ask.text_for_the_model(_extraction(text), pages=4)

    assert which == "before-section-3"
    assert sent.endswith("H315: Verursacht Hautreizungen.")
    assert "H226" not in sent


@pytest.mark.spec("SDW-25")
@pytest.mark.parametrize(
    "line",
    [
        "Siehe Abschnitt 3 für die Inhaltsstoffe.",
        "Die Angaben in Abschnitt 3: Zusammensetzung gelten.",
        "13 Zusammensetzung der Verpackung",
        "3.2 Gemische",
        "Die Zusammensetzung, Angaben dazu fehlen.",
    ],
)
def test_a_line_that_only_mentions_section_3_does_not_end_the_text(line: str) -> None:
    text = f"{LABEL}\n{line}\nH315: Verursacht Hautreizungen.\n"

    sent, which = ask.text_for_the_model(_extraction(text), pages=4)

    assert which == "pages"
    assert sent == text


@pytest.mark.spec("SDW-25")
def test_without_the_heading_the_first_pages_go_with_a_repeated_header_once() -> None:
    header = "Musterfarbe Sicherheitsdatenblatt"
    pages = [f"{header}\nSeite {n} hat ihren eigenen Text.\n" for n in range(1, 7)]

    sent, which = ask.text_for_the_model(_extraction("".join(pages), pages), pages=2)

    assert which == "pages"
    assert sent.count(header) == 1
    assert "Seite 2 hat" in sent
    assert "Seite 3 hat" not in sent


@pytest.mark.spec("SDW-25")
def test_a_heading_at_the_very_top_is_a_table_of_contents() -> None:
    pages = [
        "Inhalt\n3. Zusammensetzung/Angaben zu Bestandteilen\n" + LABEL,
        "H315: Verursacht Hautreizungen.\n",
    ]

    sent, which = ask.text_for_the_model(_extraction("".join(pages), pages), pages=4)

    assert which == "pages"
    assert "H315" in sent


@pytest.mark.spec("SDW-25")
def test_the_request_holds_the_file_s_text_and_nothing_the_parser_made(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    """The label is printed once; a request that also carried what the parser
    extracted from it would hold its statements twice."""
    path = _pdf(tmp_path / "farbe.pdf", WITH_INGREDIENTS)

    code, [record], _ = _ask(capsys, model, str(path))

    text = extract_pdf_text(path).text
    [request] = model.requests
    document = _document(request)
    assert code == 0
    assert record["sent"] == "before-section-3"
    assert document == text[: text.index("ABSCHNITT 3")].rstrip()
    assert document.count("H412") == 1
    assert "H226" not in request["messages"][1]["content"]


@pytest.mark.spec("SDW-25")
def test_a_sheet_without_section_3_goes_as_its_first_pages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)

    _, [record], _ = _ask(capsys, model, str(path))

    assert record["sent"] == "pages"
    assert "H412" in _document(model.requests[0])


@pytest.mark.spec("SDW-25")
def test_the_model_is_asked_once_at_temperature_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)

    _ask(capsys, model, str(path))

    _, [record], _ = _ask(capsys, model, str(path))
    model.requests.pop()

    [request] = model.requests
    assert (record["sheet_count"], "parts" in record, "answer" in record) == (
        1,
        False,
        True,
    )
    assert model.paths[:1] == ["/v1/chat/completions"]
    assert request["model"] == "some-model"
    assert request["temperature"] == 0
    system, user = request["messages"]
    assert system["role"] == "system"
    assert user["role"] == "user"
    assert "revision_date" in system["content"]
    assert "Authorization" not in model.headers[0]


@pytest.mark.spec("SDW-25")
def test_the_question_asks_for_an_euh_statement_printed_without_its_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    _ask(capsys, model, str(_pdf(tmp_path / "farbe.pdf", SHEET)))

    instructions = model.requests[0]["messages"][0]["content"]
    assert "ohne Code" in instructions
    assert "EUH208" in instructions


@pytest.mark.spec("SDW-25")
def test_the_sheet_s_text_cannot_end_the_document_and_give_orders(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    """The markers around the text carry an id made for the request, and the
    instructions say that what stands between them is a document."""
    path = _pdf(tmp_path / "farbe.pdf", SHEET)

    _ask(capsys, model, str(path))
    _ask(capsys, model, str(path))

    first, second = (r["messages"] for r in model.requests)
    opening = re.compile(r"<(sds_content_[0-9a-f]{16})>")
    marks = [
        opening.search(messages[1]["content"]).group(1) for messages in (first, second)
    ]
    assert marks[0] != marks[1]
    assert first[1]["content"].rstrip().endswith(f"</{marks[0]}>")
    assert "KEINE Anweisung" in first[0]["content"]
    # The instructions are the same for every sheet; only the document differs.
    assert first[0]["content"] == second[0]["content"]


@pytest.mark.spec("SDW-25")
def test_extra_fields_are_merged_into_the_request(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)

    _, [record], _ = _ask(
        capsys,
        model,
        str(path),
        "--request-json",
        '{"reasoning_effort": "none", "temperature": 0.2}',
    )
    monkeypatch.setenv(cli.REQUEST_VARIABLE, '{"seed": 7}')
    _, [from_environment], _ = _ask(capsys, model, str(path))

    first, second = model.requests
    assert first["reasoning_effort"] == "none"
    assert first["temperature"] == 0.2
    assert first["model"] == "some-model"
    assert record["request"] == {"reasoning_effort": "none", "temperature": 0.2}
    assert second["seed"] == 7
    assert second["temperature"] == 0
    assert from_environment["request"] == {"seed": 7}


@pytest.mark.spec("SDW-25")
@pytest.mark.parametrize(
    "extra",
    ['{"model": "another"}', '{"messages": []}', "[1]", "{not json", '"text"'],
)
def test_extra_fields_may_not_replace_whom_or_what_is_asked(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
    extra: str,
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)

    with pytest.raises(SystemExit) as stopped:
        cli.main(
            [
                "ask",
                "--endpoint",
                model.url,
                "--model",
                "m",
                "--request-json",
                extra,
                str(path),
            ]
        )

    assert stopped.value.code == 2
    assert capsys.readouterr().out == ""
    assert model.requests == []


# ---------------------------------------------------------------------------
# Who is asked, and what happens when the endpoint fails
# ---------------------------------------------------------------------------


@pytest.mark.spec("SDW-25")
def test_a_file_that_is_no_sheet_is_not_sent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    path = _pdf(tmp_path / "prospekt.pdf", LEAFLET)

    code, [record], _ = _ask(capsys, model, str(path))

    assert code == 0
    assert record["asked"] is False
    assert record["kind"] == "document"
    assert record["reason"]["code"] == "model-not-asked"
    assert "reading" not in record
    assert model.requests == []


@pytest.mark.spec("SDW-25")
def test_a_file_without_text_is_not_sent_and_fails_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    empty = tmp_path / "leer.pdf"
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(empty)

    code, [record], err = _ask(capsys, model, str(empty))

    assert code == 1
    assert record["asked"] is False
    assert record["reason"]["code"] in {"no-text", "no-text-layer", "ocr-unavailable"}
    assert record["reason"]["message"]
    assert "leer.pdf" in err
    assert model.requests == []


@pytest.mark.spec("SDW-25")
def test_the_verdict_decides_and_the_parser_is_not_run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sdb_reader.parser import SDSParser

    def no_parser(self: SDSParser, extraction: Any) -> Any:
        raise AssertionError("ask does not parse")

    monkeypatch.setattr(SDSParser, "parse", no_parser)

    code, [record], _ = _ask(capsys, model, str(_pdf(tmp_path / "farbe.pdf", SHEET)))

    assert code == 0
    assert record["asked"] is True


@pytest.mark.spec("SDW-25")
@pytest.mark.parametrize(
    ("status", "reply", "reason"),
    [
        (500, "{}", "HTTP 500"),
        (200, "not json", "kein JSON"),
        (200, json.dumps({"choices": []}), "enthält keine Nachricht"),
        (
            200,
            json.dumps({"choices": [{"message": {"content": "Ich weiß es nicht."}}]}),
            "lässt sich nicht als Antwort lesen",
        ),
    ],
)
def test_a_failed_request_costs_only_its_file_and_is_not_repeated(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
    status: int,
    reply: str,
    reason: str,
) -> None:
    sheet = _pdf(tmp_path / "farbe.pdf", SHEET)
    leaflet = _pdf(tmp_path / "prospekt.pdf", LEAFLET)
    model.status, model.body = status, reply.encode()

    code, records, err = _ask(capsys, model, str(sheet), str(leaflet))

    assert code == 1
    assert [r["file"]["filename"] for r in records] == ["prospekt.pdf"]
    assert "farbe.pdf" in err
    assert reason in err
    assert len(model.requests) == 1


@pytest.mark.spec("SDW-25")
def test_an_endpoint_that_is_not_there_fails_the_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)
    # A port nothing listens on: taken, then given back.
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{taken.getsockname()[1]}/v1"

    code = cli.main(["ask", "--endpoint", url, "--model", "m", str(path)])
    out, err = capsys.readouterr()

    assert code == 1
    assert json.loads(out) == []
    assert "hat nicht geantwortet" in err


@pytest.mark.spec("SDW-25")
def test_endpoint_model_and_key_come_from_the_environment(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)
    monkeypatch.setenv(cli.ENDPOINT_VARIABLE, model.url)
    monkeypatch.setenv(cli.MODEL_VARIABLE, "from-the-environment")
    monkeypatch.setenv(cli.API_KEY_VARIABLE, "a-key")

    code = cli.main(["ask", str(path)])
    [record] = json.loads(capsys.readouterr().out)

    assert code == 0
    assert model.requests[0]["model"] == "from-the-environment"
    assert model.headers[0]["Authorization"] == "Bearer a-key"
    assert record["model"] == "from-the-environment"
    # The key is nowhere in what is kept.
    assert "a-key" not in json.dumps(record)


@pytest.mark.spec("SDW-25")
def test_there_is_no_option_for_the_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)

    with pytest.raises(SystemExit) as stopped:
        cli.main(
            [
                "ask",
                "--endpoint",
                model.url,
                "--model",
                "m",
                "--api-key",
                "k",
                str(path),
            ]
        )

    assert stopped.value.code == 2
    assert model.requests == []
    capsys.readouterr()


@pytest.mark.spec("SDW-25")
@pytest.mark.parametrize(
    "argv",
    [
        ["--model", "m"],
        ["--endpoint", "http://127.0.0.1:1/v1"],
        ["--endpoint", "file:///etc/passwd", "--model", "m"],
        ["--endpoint", "localhost:11434/v1", "--model", "m"],
    ],
)
def test_without_endpoint_and_model_nothing_is_read(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
    argv: list[str],
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)

    with pytest.raises(SystemExit) as stopped:
        cli.main(["ask", *argv, str(path)])

    assert stopped.value.code == 2
    assert capsys.readouterr().out == ""
    assert model.requests == []


@pytest.mark.spec("SDW-25")
def test_read_asks_no_model(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(cli.ENDPOINT_VARIABLE, model.url)
    monkeypatch.setenv(cli.MODEL_VARIABLE, "m")

    assert cli.main(["read", str(_pdf(tmp_path / "farbe.pdf", SHEET))]) == 0
    capsys.readouterr()

    assert model.requests == []


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------

DATED = SHEET.replace(
    "Sicherheitsdatenblatt\n",
    "Sicherheitsdatenblatt\nÜberarbeitet am: 20.07.2022\nDruckdatum: 01.02.2023\n",
    1,
)

FULL_ANSWER = {
    "supplier": {
        "name": "Muster GmbH",
        "address": "Musterweg 1, 12345 Musterstadt",
        "phone": "0555-0142-0",
        "email": "info@muster.example",
        "website": "www.muster.example",
    },
    "hazard_statements": (
        "H412: Schädlich für Wasserorganismen, mit langfristiger Wirkung.\n"
        "EUH208: Enthält Musterstoff. Kann allergische Reaktionen hervorrufen."
    ),
    "precautionary_statements": (
        "P305 + P351 + P338: BEI KONTAKT MIT DEN AUGEN: Einige Minuten lang "
        "behutsam mit Wasser spülen."
    ),
    "supplemental_phrases": "EUH210: Sicherheitsdatenblatt auf Anfrage erhältlich.",
    "revision_date": "20.07.2022",
}


def _ask_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(
        resources.files("sdb_reader")
        .joinpath("ask_record.schema.json")
        .read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )


@pytest.mark.spec("SDW-26")
def test_the_record_holds_the_answer_in_the_form_of_a_reading(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    from sdb_reader import extraction_stage

    path = _pdf(tmp_path / "farbe.pdf", DATED)
    model.answers(FULL_ANSWER)

    code, [record], _ = _ask(capsys, model, str(path))

    assert code == 0
    assert record["file"] == {
        "path": str(path.resolve()),
        "filename": "farbe.pdf",
        "size_bytes": path.stat().st_size,
    }
    assert record["kind"] == "safety-data-sheet"
    assert record["asked"] is True
    assert record["model"] == "some-model"
    assert record["stage"] == extraction_stage()
    assert re.fullmatch(r"[0-9a-f]{12}", record["question"])
    assert "request" not in record
    assert "usage" not in record
    assert record["reading"] == {
        "revision_date": "2022-07-20",
        "revision_date_named": "20.07.2022",
        "hazard_statements": {
            "hazard_codes": ["H412"],
            "precautionary_codes": ["P305+P351+P338"],
            # One the model listed among the H statements is an EUH statement.
            "supplemental_codes": ["EUH210", "EUH208"],
            "hazard_text": FULL_ANSWER["hazard_statements"],
            "precautionary_text": FULL_ANSWER["precautionary_statements"],
            "supplemental_text": FULL_ANSWER["supplemental_phrases"],
        },
        "contact_info": {
            "supplier_name": "Muster GmbH",
            "supplier_address": "Musterweg 1, 12345 Musterstadt",
            "supplier_phone": "0555-0142-0",
            "supplier_email": "info@muster.example",
            "supplier_website": "www.muster.example",
        },
    }
    assert record["answer"]["revision_date"] == "20.07.2022"
    assert record["answer"]["supplier"]["name"] == "Muster GmbH"


@pytest.mark.spec("SDW-26")
@pytest.mark.parametrize("literal", ["31.12.2024", "im Juli 2022", None])
def test_a_date_that_does_not_hold_up_is_kept_as_named_and_not_as_a_date(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
    literal: str | None,
) -> None:
    """A date that is not in the text sent, something that is no date, none."""
    path = _pdf(tmp_path / "farbe.pdf", DATED)
    model.names_the_date(literal)

    code, [record], _ = _ask(capsys, model, str(path))

    assert code == 0
    assert record["reading"]["revision_date"] is None
    assert record["reading"]["revision_date_named"] == literal


@pytest.mark.spec("SDW-26")
def test_the_question_s_fingerprint_is_that_of_the_instructions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    import hashlib

    one = _pdf(tmp_path / "farbe.pdf", SHEET)
    other = _pdf(tmp_path / "lack.pdf", DATED)

    _, records, _ = _ask(capsys, model, str(one), str(other))

    instructions = model.requests[0]["messages"][0]["content"]
    expected = hashlib.sha256(instructions.encode()).hexdigest()[:12]
    assert [record["question"] for record in records] == [expected, expected]


@pytest.mark.spec("SDW-25")
def test_the_question_asks_for_every_printed_statement_whatever_2_1_says(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    """An unclassified product can carry P101 and P102 on its label."""
    _, [record], _ = _ask(capsys, model, str(_pdf(tmp_path / "farbe.pdf", SHEET)))

    instructions = model.requests[0]["messages"][0]["content"]
    assert (
        "Nenne jeden H-, P- und EUH-Satz, den die Kennzeichnung druckt, "
        "gleichgültig, was Abschnitt 2.1 zur Einstufung sagt" in instructions
    )
    assert "Druckt die Kennzeichnung keinen Satz, lasse das Feld weg." in instructions
    assert "nicht eingestuft, lasse" not in instructions
    assert "NIEMALS aus '2.1 Einstufung'" in instructions
    # Whoever rewords the question asks another one: answers kept under the
    # old fingerprint are not laid beside the new ones.
    assert record["question"] == "f379fb5eeb7e"


@pytest.mark.spec("SDW-26")
def test_the_schema_holds_for_every_kind_of_ask_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    empty = tmp_path / "leer.pdf"
    with pymupdf.open() as doc:
        doc.new_page()
        doc.save(empty)
    model.body = json.dumps(
        {
            "choices": [{"message": {"content": json.dumps(FULL_ANSWER)}}],
            "usage": {"prompt_tokens": 1200, "completion_tokens": 80},
        }
    ).encode()

    _, records, _ = _ask(
        capsys,
        model,
        str(_pdf(tmp_path / "farbe.pdf", DATED)),
        str(_pdf(tmp_path / "zutaten.pdf", WITH_INGREDIENTS)),
        str(_pdf(tmp_path / "prospekt.pdf", LEAFLET)),
        str(empty),
        "--request-json",
        '{"seed": 7}',
    )
    model.answers({"hazard_statements": 5})
    _, [sparse], _ = _ask(capsys, model, str(tmp_path / "farbe.pdf"))

    validator = _ask_validator()
    for record in [*records, sparse]:
        problems = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
        assert not problems, (record["file"]["filename"], problems[0].message)
    by_name = {record["file"]["filename"]: record for record in records}
    assert by_name["farbe.pdf"]["usage"] == {
        "prompt_tokens": 1200,
        "completion_tokens": 80,
    }
    assert by_name["farbe.pdf"]["sent"] == "pages"
    assert by_name["zutaten.pdf"]["sent"] == "before-section-3"
    assert by_name["prospekt.pdf"]["asked"] is False
    assert by_name["leer.pdf"]["asked"] is False
    assert "usage" not in sparse


@pytest.mark.spec("SDW-26")
def test_a_key_the_ask_schema_does_not_know_fails_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    model.answers(FULL_ANSWER)
    _, [asked], _ = _ask(capsys, model, str(_pdf(tmp_path / "farbe.pdf", DATED)))
    _, [not_asked], _ = _ask(capsys, model, str(_pdf(tmp_path / "p.pdf", LEAFLET)))
    validator = _ask_validator()

    for holder in (
        asked,
        asked["reading"],
        asked["reading"]["hazard_statements"],
        asked["reading"]["contact_info"],
        not_asked,
    ):
        holder["something_new"] = 1
        assert list(validator.iter_errors(asked)) or list(
            validator.iter_errors(not_asked)
        )
        del holder["something_new"]
    assert not list(validator.iter_errors(asked))
    assert not list(validator.iter_errors(not_asked))
    # A record that says nobody was asked holds no answer.
    not_asked["reading"] = asked["reading"]
    assert list(validator.iter_errors(not_asked))


# ---------------------------------------------------------------------------
# Several sheets in one file
# ---------------------------------------------------------------------------


def _component(name: str, label: str, date: str) -> str:
    return (
        f"Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006\n"
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
        f"Überarbeitet am: {date}\n"
        f"Produktname: {name}\n"
        "Verwendung des Stoffs oder Gemischs: Klebstoff für Bauteile\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        f"2.2 Kennzeichnungselemente\n{label}\n"
        "2.3 Sonstige Gefahren\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
        "Musterstoff 1 - 5 %\n"
        "H226: Flüssigkeit und Dampf entzündbar.\n"
        "ABSCHNITT 16: Sonstige Angaben\n"
    )


RESIN_LABEL = "H315: Verursacht Hautreizungen.\nP102: Darf nicht in die Hände von Kindern gelangen."
HARDENER_LABEL = (
    "H318: Verursacht schwere Augenschäden.\n"
    "P102: Darf nicht in die Hände von Kindern gelangen.\n"
    "P280: Schutzhandschuhe tragen."
)
RESIN = _component("Harz", RESIN_LABEL, "20.07.2022")
HARDENER = _component("Härter", HARDENER_LABEL, "03.05.2021")
# The line ask's page furniture and PDF layout leave alone: the header is
# printed once per sheet here, as in a file put together from two.
TWO_SHEETS = RESIN + HARDENER


def _answer(label: str, name: str, date: str) -> dict[str, Any]:
    lines = label.split("\n")
    return {
        "supplier": {"name": name},
        "hazard_statements": "\n".join(x for x in lines if x.startswith("H")),
        "precautionary_statements": "\n".join(x for x in lines if x.startswith("P")),
        "revision_date": date,
    }


RESIN_ANSWER = _answer(RESIN_LABEL, "Muster GmbH", "20.07.2022")
HARDENER_ANSWER = _answer(HARDENER_LABEL, "Beispiel AG", "03.05.2021")


def _two_sheets(directory: Path) -> Path:
    """A PDF of two sheets, each beginning on a page of its own."""
    doc = pymupdf.open()
    for text in (RESIN, HARDENER):
        doc.new_page().insert_text((72, 72), text)
    doc.save(directory / "kleber.pdf")
    doc.close()
    return directory / "kleber.pdf"


@pytest.mark.spec("SDW-30")
def test_a_file_of_two_sheets_is_asked_about_sheet_by_sheet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    path = _two_sheets(tmp_path)
    model.answers_in_turn(RESIN_ANSWER, HARDENER_ANSWER, usage=(700, 90))

    code, [record], _ = _ask(capsys, model, str(path))

    first, second = (_document(request) for request in model.requests)
    assert code == 0
    assert "H315" in first
    assert "H318" not in first
    assert "H318" in second
    assert "H315" not in second
    # Each ends before its own section 3.
    assert "H226" not in first + second
    assert model.requests[0]["messages"][0] == model.requests[1]["messages"][0]
    assert record["sheet_count"] == 2
    assert record["sent"] == "before-section-3"
    assert record["usage"] == {"prompt_tokens": 1400, "completion_tokens": 180}
    assert not list(_ask_validator().iter_errors(record))


@pytest.mark.spec("SDW-30")
def test_the_record_holds_every_sheet_and_all_of_them_united(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    path = _two_sheets(tmp_path)
    model.answers_in_turn(RESIN_ANSWER, HARDENER_ANSWER, usage=(700, 90))

    _, [record], _ = _ask(capsys, model, str(path))

    resin, hardener = record["parts"]
    assert "answer" not in record
    assert resin["answer"] == RESIN_ANSWER
    assert resin["sent"] == "before-section-3"
    assert resin["usage"] == {"prompt_tokens": 700, "completion_tokens": 90}
    assert resin["reading"]["hazard_statements"]["hazard_codes"] == ["H315"]
    assert hardener["reading"]["hazard_statements"]["hazard_codes"] == ["H318"]
    # Each sheet's date counts against that sheet's text.
    assert resin["reading"]["revision_date"] == "2022-07-20"
    assert hardener["reading"]["revision_date"] == "2021-05-03"
    assert hardener["reading"]["contact_info"]["supplier_name"] == "Beispiel AG"
    united = record["reading"]
    label = united["hazard_statements"]
    assert label["hazard_codes"] == ["H315", "H318"]
    # In the order they first appear, each once.
    assert label["precautionary_codes"] == ["P102", "P280"]
    assert label["hazard_text"] == (
        "H315: Verursacht Hautreizungen.\nH318: Verursacht schwere Augenschäden."
    )
    # Supplier and date are the first sheet's.
    assert united["contact_info"]["supplier_name"] == "Muster GmbH"
    assert united["revision_date"] == "2022-07-20"
    assert united["revision_date_named"] == "20.07.2022"


@pytest.mark.spec("SDW-30")
def test_supplier_and_date_are_the_first_sheet_s_also_where_it_names_none() -> None:
    silent = ask.model_reading(
        {"hazard_statements": "H315: Verursacht Hautreizungen."}, ""
    )
    named = ask.model_reading(HARDENER_ANSWER, "03.05.2021")

    united = ask.united_reading([silent, named])

    assert united["contact_info"]["supplier_name"] is None
    assert united["revision_date"] is None
    assert united["hazard_statements"]["hazard_codes"] == ["H315", "H318"]
    assert united["hazard_statements"]["supplemental_text"] is None


@pytest.mark.spec("SDW-30")
def test_statements_a_model_wrote_in_one_line_stand_apart_in_the_union() -> None:
    first = ask.model_reading(
        {
            "hazard_statements": "H315 - Verursacht Hautreizungen. "
            "H317 - Kann allergische Hautreaktionen verursachen."
        },
        "",
    )
    second = ask.model_reading(
        {
            "hazard_statements": "H317 - Kann allergische Hautreaktionen verursachen. "
            "H319 - Verursacht schwere Augenreizung."
        },
        "",
    )

    united = ask.united_reading([first, second])

    assert united["hazard_statements"]["hazard_text"] == (
        "H315: Verursacht Hautreizungen.\n"
        "H317: Kann allergische Hautreaktionen verursachen.\n"
        "H319: Verursacht schwere Augenreizung."
    )


@pytest.mark.spec("SDW-30")
def test_one_failed_request_fails_the_whole_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    path = _two_sheets(tmp_path)
    model.statuses = [200, 500]

    code, records, err = _ask(capsys, model, str(path))

    assert code == 1
    assert records == []
    assert len(model.requests) == 2
    assert "kleber.pdf" in err


@pytest.mark.spec("SDW-30")
@pytest.mark.spec("SDB-2")
def test_read_and_ask_count_the_same_sheets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], model: _Model
) -> None:
    """A model answering each sheet rightly shows no difference in the codes."""
    path = _two_sheets(tmp_path)
    read, asked = tmp_path / "read.jsonl", tmp_path / "ask.jsonl"
    model.answers_in_turn(RESIN_ANSWER, HARDENER_ANSWER)

    assert cli.main(["read", str(path), "--output", str(read)]) == 0
    assert (
        cli.main(
            [
                "ask",
                "--endpoint",
                model.url,
                "--model",
                "m",
                str(path),
                "--output",
                str(asked),
            ]
        )
        == 0
    )
    cli.main(["diff", str(read), str(asked), "--json"])
    out, _ = capsys.readouterr()

    [sheet] = [json.loads(line) for line in read.read_text().splitlines()]
    [record] = [json.loads(line) for line in asked.read_text().splitlines()]
    several = [w for w in sheet["parser"]["warnings"] if w["code"] == "several-sheets"]
    assert [w["params"]["count"] for w in several] == [record["sheet_count"]]
    differing = set(json.loads(out)["fields"])
    assert not differing & {
        "hazard_codes",
        "precautionary_codes",
        "supplemental_codes",
    }


@pytest.mark.spec("SDW-30")
def test_a_sheet_among_several_without_section_3_goes_whole() -> None:
    without = HARDENER.replace(
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n", ""
    )

    resin, hardener = ask.build_requests(
        _extraction(RESIN + without, pages=[RESIN, without]), "kleber.pdf", pages=1
    )
    record = ask.asked_record(
        ask.Endpoint("http://localhost/v1", "m"),
        [resin, hardener],
        [ask.Reply("{}"), ask.Reply("{}")],
        [RESIN_ANSWER, HARDENER_ANSWER],
    )

    assert (resin.sent, hardener.sent) == ("before-section-3", "sheet")
    # A sheet begins at the title above its section 1 (SDB-2), goes to its end.
    assert hardener.text.startswith("Sicherheitsdatenblatt gemäß")
    assert not resin.text.endswith("1907/2006")
    assert hardener.text.endswith("ABSCHNITT 16: Sonstige Angaben\n")
    assert "H226" in hardener.text
    assert record["sent"] == "sheet"
    assert "usage" not in record
    assert "usage" not in record["parts"][0]


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

OWN = """
[plain]
description = "A service that takes no temperature"
omit = ["temperature"]

[seeded]
description = { en = "A fixed seed", de = "Ein fester Startwert" }
request = { seed = 7, temperature = 0.3 }
tested_with = "some-model"
tested_on = 2026-01-02
"""


@pytest.mark.spec("SDW-31")
def test_every_shipped_preset_is_a_request_s_fields_and_says_what_it_was_measured_with() -> (
    None
):
    shipped = presets.shipped_presets()

    assert {"deepseek-no-reasoning", "ollama-no-reasoning"} <= shipped.keys()
    for name, preset in shipped.items():
        assert json.loads(json.dumps(dict(preset.request))) == dict(preset.request)
        assert not ask.RESERVED_REQUEST_FIELDS & preset.request.keys()
        assert preset.request or preset.omit
        assert {"de", "en"} <= preset.description.keys()
        # Usable as it stands.
        ask.Endpoint(
            "http://localhost/v1", "m", request=preset.request, omit=preset.omit
        )
        # A shipped preset was measured with this command.
        assert preset.tested_with, name
        assert isinstance(preset.tested_on, date), name
    assert shipped["deepseek-no-reasoning"].request == {
        "thinking": {"type": "disabled"}
    }
    assert shipped["ollama-no-reasoning"].request == {"reasoning_effort": "none"}


@pytest.mark.spec("SDW-31")
def test_a_preset_s_fields_go_into_every_request_and_the_record_names_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)

    _, [record], _ = _ask(capsys, model, str(path), "--preset", "deepseek-no-reasoning")
    monkeypatch.setenv(cli.PRESET_VARIABLE, "ollama-no-reasoning")
    _, [from_environment], _ = _ask(capsys, model, str(path))
    monkeypatch.delenv(cli.PRESET_VARIABLE)
    _, [without], _ = _ask(capsys, model, str(path))

    first, second, _ = model.requests
    assert first["thinking"] == {"type": "disabled"}
    assert first["temperature"] == 0
    assert record["preset"] == "deepseek-no-reasoning"
    assert record["request"] == {"thinking": {"type": "disabled"}}
    assert second["reasoning_effort"] == "none"
    assert from_environment["preset"] == "ollama-no-reasoning"
    assert "preset" not in without


@pytest.mark.spec("SDW-31")
def test_the_call_s_own_fields_go_on_top_of_the_preset_s(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)
    own = tmp_path / "own.toml"
    own.write_text(OWN, encoding="utf-8")

    def asked(*argv: str) -> tuple[dict[str, Any], dict[str, Any]]:
        _, [record], _ = _ask(capsys, model, str(path), "--presets", str(own), *argv)
        return model.requests[-1], record

    plain, _ = asked("--preset", "plain")
    back, _ = asked("--preset", "plain", "--request-json", '{"temperature": 1}')
    seeded, record = asked("--preset", "seeded", "--request-json", '{"seed": 9}')

    # Left out by the preset; back where the call names it.
    assert "temperature" not in plain
    assert back["temperature"] == 1
    assert (seeded["seed"], seeded["temperature"]) == (9, 0.3)
    assert record["request"] == {"seed": 9, "temperature": 0.3}
    assert record["preset"] == "seeded"


@pytest.mark.spec("SDW-31")
@pytest.mark.parametrize(
    ("file", "argv", "said"),
    [
        (None, ["--preset", "no-such"], "deepseek-no-reasoning"),
        (OWN, ["--preset", "deepseek-no-reasoning"], "plain, seeded"),
        (OWN, [], "--preset"),
        (
            "[a]\nrequest = { model = 'x' }\ndescription = 'd'",
            ["--preset", "a"],
            "model",
        ),
        ("[a]\ndescription = 'd'", ["--preset", "a"], "changes nothing"),
        ("[a]\nrequest = { x = 1 }", ["--preset", "a"], "description"),
        (
            "[a]\ndescription = 'd'\nomit = ['messages']",
            ["--preset", "a"],
            "temperature",
        ),
        (
            "[a]\ndescription = 'd'\nomit = ['temperature']\nnote = 1",
            ["--preset", "a"],
            "note",
        ),
        (
            "[a]\ndescription = 'd'\nrequest = { x = 1 }\ntested_with = 'm'",
            ["--preset", "a"],
            "go together",
        ),
        ("[a", ["--preset", "a"], "no TOML"),
    ],
)
def test_a_preset_that_is_none_ends_the_call_before_anything_is_read(
    file: str | None,
    argv: list[str],
    said: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)
    if file is not None:
        (tmp_path / "own.toml").write_text(file, encoding="utf-8")
        argv = ["--presets", str(tmp_path / "own.toml"), *argv]

    with pytest.raises(SystemExit) as raised:
        cli.main(["ask", "--endpoint", model.url, "--model", "m", *argv, str(path)])

    assert raised.value.code == 2
    assert said in capsys.readouterr().err
    assert model.requests == []


@pytest.mark.spec("SDW-31")
def test_the_presets_are_listed_without_a_file_an_endpoint_or_a_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (cli.ENDPOINT_VARIABLE, cli.MODEL_VARIABLE, cli.LANGUAGE_VARIABLE):
        monkeypatch.delenv(name, raising=False)
    own = tmp_path / "own.toml"
    own.write_text(OWN, encoding="utf-8")

    def listed(*argv: str) -> str:
        with pytest.raises(SystemExit) as raised:
            cli.main(["ask", *argv, "--list-presets"])
        assert raised.value.code == 0
        return capsys.readouterr().out

    german, english, mine = (
        listed(),
        listed("--lang", "en"),
        listed("--presets", str(own)),
    )

    assert (
        "deepseek-no-reasoning: DeepSeek: das Nachdenken des Modells abschalten"
        in german
    )
    assert '  request: {"thinking": {"type": "disabled"}}' in german
    assert "  tested: deepseek-flash, 2026-11-18" in german
    assert "ollama-no-reasoning" in german
    assert "switch the model's reasoning off" in english
    assert "plain: A service that takes no temperature\n  omit: temperature\n" in mine
    assert "seeded: Ein fester Startwert" in mine
    assert "deepseek" not in mine
