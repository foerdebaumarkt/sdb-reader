"""Ask a language model what a safety data sheet says, and keep its answer (SDW-25).

A second reading to look at, never a source. The model is asked on its own:
it gets the file's text up to section 3 and nothing the parser made of it,
so that it can also see what the parser cut away or read wrongly. A file
that holds several sheets is asked about sheet by sheet (SDW-30). What it
says is kept as a record (SDW-26); setting it beside a reading is another
step (diff.py), which can be repeated for every later version of the parser
without asking again.

The model is reached over the chat-completions interface that local runtimes
and hosted services alike speak, with the standard library: whoever only reads
sheets installs nothing for models.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .extraction import ExtractionResult, normalise_pdf_text, strip_page_furniture
from .messages import Message, shipped_catalog
from .model import Prompt, build_prompt, named_date, read_answer
from .parser import split_into_sheets
from .statements import normalize_statements
from .versions import extraction_stage

_H_CODE = re.compile(r"(?<![A-Za-z])H\d{3}(?!\d)(?:\s*\+\s*H\d{3}(?!\d))*")
_P_CODE = re.compile(r"(?<![A-Za-z])P\d{3}(?!\d)(?:\s*\+\s*P\d{3}(?!\d))*")
_EUH_CODE = re.compile(r"\bEUH\d{3}(?!\d)")

# The heading of section 3, where the text a model gets ends (SDW-25): the
# list of ingredients begins there, and their statements are not the label's.
# One rule, kept here: it must not depend on how the parser cuts sections.
_SECTION_3 = re.compile(
    r"^[ \t]*(?:[·•*!\-–][ \t]*)?(?:0?3[ \t]+)?"
    r"(?:abschnitt[ \t]*0?3[ \t]*[:.\-–]?[ \t]*(?:zusammensetzung|angaben\b|$)"
    r"|0?3[ \t]*[.:\-–]?[ \t]*zusammensetzung"
    # The title alone, where the layout sets its number on a line of its own.
    r"|zusammensetzung[ \t]*[/,][ \t]*ang)",
    re.IGNORECASE | re.MULTILINE,
)
# A heading this early is a table of contents, not the section.
EARLIEST_SECTION_3 = 200

# What a request may not replace: who is asked, and what.
RESERVED_REQUEST_FIELDS = frozenset({"model", "messages"})
# What a request can go without: all else it holds is whom and what is asked.
OMITTABLE_REQUEST_FIELDS = frozenset({"temperature"})


class ModelError(Exception):
    """The endpoint gave no answer that can be read.

    ``message`` says why, as a code and its values; ``str()`` of the error is
    that message in English.
    """

    def __init__(self, message: Message) -> None:
        super().__init__(shipped_catalog("en").render(message))
        self.message = message


@dataclass(frozen=True, slots=True)
class Endpoint:
    """Where the model is asked, and which one."""

    url: str
    model: str
    # Sent as a bearer token; a local runtime needs none.
    api_key: str | None = None
    timeout: float = 300.0
    # Fields a service needs beyond the standard ones, merged into each
    # request: switching a model's reasoning off, a response format.
    request: Mapping[str, Any] = field(default_factory=dict)
    # Fields of the request a service does not take, left out (SDW-31).
    omit: frozenset[str] = frozenset()
    # The preset the fields come from, if one was named (SDW-31).
    preset: str | None = None

    def __post_init__(self) -> None:
        parts = urlsplit(self.url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"not an http or https address: {self.url!r}")
        taken = sorted(RESERVED_REQUEST_FIELDS & self.request.keys())
        if taken:
            raise ValueError(
                f"the request's extra fields may not set {', '.join(taken)}"
            )
        kept = sorted(self.omit - OMITTABLE_REQUEST_FIELDS)
        if kept:
            raise ValueError(f"a request cannot go without {', '.join(kept)}")


@dataclass(frozen=True, slots=True)
class Request:
    """What the model is given for one sheet of a file."""

    prompt: Prompt
    # "before-section-3"; where no heading of section 3 was found, "pages"
    # for a file that is one sheet and "sheet" for one sheet among several.
    sent: str
    # The file's text as sent, without the file's name and the markers: what
    # a date the model names is checked against.
    text: str


def text_for_the_model(extraction: ExtractionResult, *, pages: int) -> tuple[str, str]:
    """The part of a file's text a model is asked about, and which part it is.

    From the beginning up to the heading of section 3. Where there is no such
    heading, or it stands at the very top, the first *pages* pages, with a
    page header that repeats kept once.
    """
    cut = _before_section_3(extraction.text)
    if cut is not None:
        return cut, "before-section-3"
    each = extraction.metadata.get("pages")
    if isinstance(each, list) and len(each) > 1:
        first = [str(page) for page in each[:pages]]
        return normalise_pdf_text(strip_page_furniture(first, keep_first=True)), "pages"
    # Read by text recognition, or a single page: the text is all there is.
    return extraction.text, "pages"


def _before_section_3(text: str) -> str | None:
    """*text* up to the heading of section 3, or None where it has none to end at."""
    found = _SECTION_3.search(text)
    if found is not None and found.start() >= EARLIEST_SECTION_3:
        return text[: found.start()].rstrip()
    return None


def build_requests(
    extraction: ExtractionResult, filename: str, *, pages: int
) -> list[Request]:
    """The questions about the file *extraction* was read from: one per sheet.

    A file that is one sheet gives one (SDW-25). One that holds several gives
    one for each, in the file's order: the sheet's text up to its own heading
    of section 3, or the whole sheet where it has none (SDW-30). A cover page
    in front of the sheets is not sent, also where one sheet stands behind it.
    """
    sheets = split_into_sheets(extraction.text)
    if sheets == [extraction.text]:
        text, sent = text_for_the_model(extraction, pages=pages)
        return [Request(build_prompt(text, filename), sent, text)]
    requests = []
    for sheet in sheets:
        cut = _before_section_3(sheet)
        text, sent = (cut, "before-section-3") if cut is not None else (sheet, "sheet")
        requests.append(Request(build_prompt(text, filename), sent, text))
    return requests


def question_fingerprint(prompt: Prompt) -> str:
    """What tells the answers to one wording of the question from another's.

    Of the half that is the same for every file: answers to another wording
    are answers to another question, and are not laid beside these.
    """
    return hashlib.sha256(prompt.instructions.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class Reply:
    """What the endpoint answered: the model's text, and what it cost if it says."""

    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


# A failure that passes by itself: the service is busy, or briefly gone.
RETRIED_STATUS = frozenset({429, 500, 502, 503, 504})
# The longest wait before a request is sent again, also where the endpoint
# names a longer one.
LONGEST_WAIT_SECONDS = 60.0
_wait = time.sleep


def send(endpoint: Endpoint, prompt: Prompt, *, retries: int = 0) -> Reply:
    """Send *prompt* and return the model's reply (SDW-25).

    Once, unless *retries* allows more: a request that fails with one of
    RETRIED_STATUS, a timeout or no connection is then sent again, up to
    *retries* times, after a growing wait. Any other failure, and a reply
    that cannot be read, fails at once.
    """
    standard = {"temperature": 0}
    body = json.dumps(
        {
            **{k: v for k, v in standard.items() if k not in endpoint.omit},
            **endpoint.request,
            "model": endpoint.model,
            "messages": [
                {"role": "system", "content": prompt.instructions},
                {"role": "user", "content": prompt.document},
            ],
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if endpoint.api_key:
        headers["Authorization"] = f"Bearer {endpoint.api_key}"
    for attempt in range(retries + 1):
        # The scheme is checked where the endpoint is made: http or https only.
        request = urllib.request.Request(
            endpoint.url.rstrip("/") + "/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )
        named: float | None = None
        try:
            with urllib.request.urlopen(request, timeout=endpoint.timeout) as response:
                payload = json.loads(response.read())
            break
        except urllib.error.HTTPError as exc:
            # The error is the response, and holds its connection until closed.
            with exc:
                failure = ModelError(Message("model-http-error", {"status": exc.code}))
                if exc.code not in RETRIED_STATUS:
                    raise failure from exc
                cause: Exception = exc
                named = _seconds(exc.headers.get("Retry-After"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", None) or exc
            failure = ModelError(Message("model-unreachable", {"reason": str(reason)}))
            cause = exc
        except json.JSONDecodeError as exc:
            raise ModelError(Message("model-reply-not-json")) from exc
        if attempt == retries:
            raise failure from cause
        _wait(min(LONGEST_WAIT_SECONDS, named if named is not None else 2.0**attempt))
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelError(Message("model-reply-without-message")) from exc
    if not isinstance(content, str) or not content.strip():
        raise ModelError(Message("model-reply-empty"))
    usage = payload.get("usage") if isinstance(payload, Mapping) else None
    usage = usage if isinstance(usage, Mapping) else {}
    return Reply(
        content,
        prompt_tokens=_count(usage.get("prompt_tokens")),
        completion_tokens=_count(usage.get("completion_tokens")),
    )


def _seconds(value: str | None) -> float | None:
    """A wait the endpoint names in seconds; a date or nonsense is no answer."""
    try:
        seconds = float(value) if value is not None else None
    except ValueError:
        return None
    return seconds if seconds is not None and seconds >= 0 else None


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def read_model_answer(raw: str) -> dict[str, Any]:
    """The model's reply as an answer, or ModelError when it is none."""
    try:
        return read_answer(raw)
    except ValueError as exc:
        raise ModelError(
            Message("model-answer-unreadable", {"detail": str(exc)})
        ) from exc


def model_reading(answer: Mapping[str, Any], text: str) -> dict[str, Any]:
    """What the model said, in the form a reading has it (SDW-26).

    The names are those of a ``read`` record's ``sheet``, as far as a model is
    asked: the label's statements and their codes, the supplier, the date of
    revision. *text* is what the model was sent: a date it names counts only
    if it stands there.
    """
    hazard = _string(answer.get("hazard_statements"))
    precautionary = _string(answer.get("precautionary_statements"))
    supplemental = _string(answer.get("supplemental_phrases"))
    supplier = answer.get("supplier")
    supplier = supplier if isinstance(supplier, Mapping) else {}
    named = answer.get("revision_date")
    date = named_date(named, text)
    return {
        "revision_date": date.value.isoformat() if date else None,
        # As the model wrote it, also where it did not hold up.
        "revision_date_named": named if isinstance(named, str) and named else None,
        "hazard_statements": {
            "hazard_codes": _codes(_H_CODE, hazard),
            "precautionary_codes": _codes(_P_CODE, precautionary),
            # A model now and then lists an EUH statement among the H statements.
            "supplemental_codes": _unique(
                _EUH_CODE.findall(supplemental) + _EUH_CODE.findall(hazard)
            ),
            "hazard_text": hazard or None,
            "precautionary_text": precautionary or None,
            "supplemental_text": supplemental or None,
        },
        "contact_info": {
            "supplier_name": _string(supplier.get("name")) or None,
            "supplier_address": _string(supplier.get("address")) or None,
            "supplier_phone": _string(supplier.get("phone")) or None,
            "supplier_email": _string(supplier.get("email")) or None,
            "supplier_website": _string(supplier.get("website")) or None,
        },
    }


# The texts of a label, and the kinds of code each holds.
_TEXT_PREFIXES = (
    ("hazard_text", ("H", "EUH")),
    ("precautionary_text", ("P",)),
    ("supplemental_text", ("EUH",)),
)


def united_reading(readings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The reading of a file from those of its sheets (SDW-30).

    The file carries every sheet's statements, as a reading does (SDB-9):
    the codes in the order they first appear, the statements one sheet after
    the other, each on its line, a statement two sheets share once. Supplier and date are the first
    sheet's.
    """
    first = readings[0]
    labels = [reading["hazard_statements"] for reading in readings]
    united: dict[str, Any] = {}
    for key in ("hazard_codes", "precautionary_codes", "supplemental_codes"):
        united[key] = _unique(code for label in labels for code in label[key])
    for key, prefixes in _TEXT_PREFIXES:
        # A model often writes a sheet's statements in one line: each is put
        # on its own before the sheets are joined, or the joined text would
        # read as one statement per sheet (SDB-17).
        lines = _unique(
            line
            for label in labels
            if label[key]
            for line in normalize_statements(label[key], prefixes).split("\n")
            if line.strip()
        )
        united[key] = "\n".join(lines) or None
    return {
        "revision_date": first["revision_date"],
        "revision_date_named": first["revision_date_named"],
        "hazard_statements": united,
        "contact_info": dict(first["contact_info"]),
    }


def _usage(replies: Sequence[Reply]) -> dict[str, int | None] | None:
    """What *replies* cost together, or None where no endpoint said."""

    def total(counts: list[int | None]) -> int | None:
        named = [count for count in counts if count is not None]
        return sum(named) if named else None

    usage = {
        "prompt_tokens": total([reply.prompt_tokens for reply in replies]),
        "completion_tokens": total([reply.completion_tokens for reply in replies]),
    }
    return usage if any(count is not None for count in usage.values()) else None


def asked_record(
    endpoint: Endpoint,
    requests: Sequence[Request],
    replies: Sequence[Reply],
    answers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The part of an ``ask`` record that a model's answers fill (SDW-26, SDW-30).

    One request, reply and answer per sheet of the file, in its order.
    """
    readings = [
        model_reading(answer, request.text)
        for request, answer in zip(requests, answers, strict=True)
    ]
    sent = {request.sent for request in requests}
    record: dict[str, Any] = {
        "asked": True,
        "model": endpoint.model,
        "sheet_count": len(requests),
        # Of several sheets: cut before section 3 only if every one was.
        "sent": sent.pop() if len(sent) == 1 else "sheet",
        "stage": extraction_stage(),
        "question": question_fingerprint(requests[0].prompt),
    }
    if endpoint.preset:
        record["preset"] = endpoint.preset
    if endpoint.request:
        record["request"] = dict(endpoint.request)
    usage = _usage(replies)
    if usage is not None:
        record["usage"] = usage
    if len(requests) == 1:
        record["reading"] = readings[0]
        record["answer"] = dict(answers[0])
        return record
    record["reading"] = united_reading(readings)
    parts = []
    for request, reply, reading, answer in zip(
        requests, replies, readings, answers, strict=True
    ):
        part: dict[str, Any] = {"sent": request.sent}
        cost = _usage([reply])
        if cost is not None:
            part["usage"] = cost
        part["reading"] = reading
        part["answer"] = dict(answer)
        parts.append(part)
    record["parts"] = parts
    return record


def _codes(pattern: re.Pattern[str], text: str) -> list[str]:
    """The codes of *text* in its order, a joined one as one: "P305+P351"."""
    return _unique(re.sub(r"\s+", "", code) for code in pattern.findall(text))


def _unique(codes: Any) -> list[str]:
    return list(dict.fromkeys(codes))


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""
