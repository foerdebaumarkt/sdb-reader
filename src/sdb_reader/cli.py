"""sdb-reader: read safety data sheets, or hand out the data embedded in their PDFs.

``read`` prints what each file says, as JSON; ``xml`` prints the eSDScom
file a supplier embedded in the PDF, byte for byte (SDW-13); ``ask`` asks a
language model about each file and keeps its answer (SDW-25); ``diff`` sets
two runs of ``read`` or ``ask`` beside each other (SDW-27); ``show`` reads
like ``read`` and prints a report for a person instead (SDW-37).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from functools import cache
from importlib import metadata
from pathlib import Path
from typing import Any

import structlog

from . import ask, diff, presets, scan, show
from .embedded import read_embedded
from .extraction import ExtractionError, ExtractionResult, extract_pdf_text
from .messages import (
    DEFAULT_LANGUAGE,
    Catalog,
    Message,
    load_catalog,
    shipped_catalog,
    shipped_languages,
)
from .reading import read_sheet, within_line_limit
from .scan import Outcome
from .serialise import reading_to_dict
from .verification import DocumentKind, SDSVerifier, Verification

ENDPOINT_VARIABLE = "SDB_READER_ENDPOINT"
MODEL_VARIABLE = "SDB_READER_MODEL"
API_KEY_VARIABLE = "SDB_READER_API_KEY"
REQUEST_VARIABLE = "SDB_READER_REQUEST_JSON"
PRESET_VARIABLE = "SDB_READER_PRESET"
LANGUAGE_VARIABLE = "SDB_READER_LANG"


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdb-reader",
        description="Read safety data sheet PDFs, or the data embedded in them.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"sdb-reader {metadata.version('sdb-reader')}",
        help="Print the version of sdb-reader and exit.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    read = commands.add_parser(
        "read",
        help="Whether each file is a safety data sheet, and what it says, as JSON.",
    )
    read.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="PDF files to read; a directory stands for every PDF under it.",
    )
    read.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Read at most this many pages of each file (default: all).",
    )
    read.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indent level for JSON output (default: 2). Use 0 for compact output.",
    )
    read.add_argument(
        "--include-raw-text",
        action="store_true",
        help="Include the raw extracted text in the output.",
    )
    _add_label_option(read)

    _add_run_options(read)
    _add_language_options(read)

    showing = commands.add_parser(
        "show",
        help="What each file is and says, as a report to read; `read` gives JSON.",
        description=(
            "Reads the files like `read` and prints a report for a person: the "
            "full report for a file named singly, one line for each file of a "
            "directory. The text can change with any release; a program takes "
            "`read`."
        ),
    )
    showing.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="PDF files to show; a directory stands for every PDF under it.",
    )
    showing.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Read at most this many pages of each file (default: all).",
    )
    _add_label_option(showing)
    _add_selection_options(showing)
    _add_language_options(showing)

    xml = commands.add_parser(
        "xml",
        help="The eSDScom file embedded in a PDF, unchanged, on stdout.",
    )
    xml.add_argument("paths", nargs="+", type=Path, help="PDF files.")
    xml.add_argument(
        "--save",
        type=Path,
        metavar="DIRECTORY",
        default=None,
        help=(
            "Write each PDF's embedded file to DIRECTORY as <PDF name>.xml "
            "instead of printing it; takes several PDFs. An existing file is "
            "not overwritten."
        ),
    )

    _add_language_options(xml)

    asking = commands.add_parser(
        "ask",
        help="What a language model says each sheet holds, a record per file, as JSON.",
        description=(
            "Asks a language model about every German safety data sheet and keeps "
            "its answer: a record per file, to set beside a reading with `diff`. "
            "The file's text up to section 3 is sent to the endpoint. An API key "
            f"is taken from {API_KEY_VARIABLE} only."
        ),
    )
    asking.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="PDF files to ask about; a directory stands for every PDF under it.",
    )
    _add_model_options(asking)
    asking.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indent level for JSON output (default: 2). Use 0 for compact output.",
    )
    _add_run_options(asking)
    _add_language_options(asking)

    runs = commands.add_parser(
        "diff",
        help="Where two runs of `read` or `ask` differ, field by field.",
        description=(
            "Sets two runs beside each other: files of records as `read` or `ask` "
            "wrote them, JSON Lines or one JSON list. Reads no PDF and asks no "
            "model. Exit code 0 where no file differs, 1 where one does."
        ),
    )
    runs.add_argument("a", type=Path, metavar="A", help="The first run's records.")
    runs.add_argument("b", type=Path, metavar="B", help="The second run's records.")
    runs.add_argument(
        "--match",
        choices=("path", "name"),
        default="path",
        help=(
            "What tells that two records are of the same file: its path "
            "(default), or its name where the runs read copies in different "
            "places."
        ),
    )
    runs.add_argument(
        "--examples",
        type=int,
        default=3,
        metavar="N",
        help="Show up to N files per field (default: 3).",
    )
    runs.add_argument(
        "--json",
        action="store_true",
        help="Print the counts and examples as JSON instead of text.",
    )
    runs.add_argument(
        "--details",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Write every differing file with both values to FILE, as JSON "
            "Lines; an existing FILE is replaced."
        ),
    )
    runs.add_argument(
        "--count-only-from",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Count the files FILE names in a group of their own and show them "
            "in no example and no detail; one per line: a file name, a path, "
            "or the end of a path."
        ),
    )
    runs.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indent level for --json (default: 2). Use 0 for compact output.",
    )
    _add_language_options(runs)
    return parser


def _add_model_options(command: argparse.ArgumentParser) -> None:
    """Whom to ask, and how (SDW-25)."""
    command.add_argument(
        "--endpoint",
        default=os.environ.get(ENDPOINT_VARIABLE),
        help=(
            "Address of an OpenAI-compatible API, such as http://localhost:11434/v1 "
            f"(default: {ENDPOINT_VARIABLE})."
        ),
    )
    command.add_argument(
        "--model",
        default=os.environ.get(MODEL_VARIABLE),
        help=f"The model's name at the endpoint (default: {MODEL_VARIABLE}).",
    )
    command.add_argument(
        "--pages",
        type=int,
        default=4,
        help=(
            "Pages of the PDF the model gets where the file's text has no "
            "heading of section 3 to end at (default: 4)."
        ),
    )
    command.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Seconds to wait for the model's answer (default: 300).",
    )
    command.add_argument(
        "--retries",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Send a request again up to N times when the endpoint is busy or "
            "not reachable (HTTP 429, 500, 502, 503, 504, a timeout, no "
            "connection), after a growing wait (default: 0)."
        ),
    )
    command.add_argument(
        "--preset",
        default=os.environ.get(PRESET_VARIABLE),
        metavar="NAME",
        help=(
            "Request fields for a known model family, such as switching its "
            f"reasoning off; see --list-presets (default: {PRESET_VARIABLE})."
        ),
    )
    command.add_argument(
        "--presets",
        type=Path,
        default=None,
        metavar="FILE",
        help="A TOML file of presets like the shipped one, to take --preset from.",
    )
    command.add_argument(
        "--list-presets",
        action=_ListPresets,
        help="Print the presets --preset can name, and exit.",
    )
    command.add_argument(
        "--request-json",
        default=os.environ.get(REQUEST_VARIABLE),
        metavar="JSON",
        help=(
            "A JSON object merged into every request, on top of a preset's "
            "fields, for what a service needs beyond them; it may not set "
            f"model or messages (default: {REQUEST_VARIABLE})."
        ),
    )


def _known_presets(file: Path | None) -> dict[str, presets.Preset]:
    """The presets a call can name: the shipped ones, or those of *file*."""
    return presets.load_presets(file) if file is not None else presets.shipped_presets()


class _ListPresets(argparse.Action):
    """Print the presets and end, like --version: no file is needed (SDW-31).

    What stands before it on the line counts: --lang for the language of the
    lines, --presets for a file of one's own.
    """

    def __init__(self, option_strings: Sequence[str], dest: str, **kwargs: Any) -> None:
        super().__init__(
            option_strings, dest, nargs=0, default=argparse.SUPPRESS, **kwargs
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        _values: Any,
        _option_string: str | None = None,
    ) -> None:
        language = getattr(namespace, "lang", None) or DEFAULT_LANGUAGE
        try:
            known = _known_presets(getattr(namespace, "presets", None))
        except ValueError as exc:
            parser.error(str(exc))
        for preset in known.values():
            print(f"{preset.name}: {preset.describe(language)}")
            if preset.request:
                print(f"  request: {json.dumps(dict(preset.request))}")
            if preset.omit:
                print(f"  omit: {', '.join(sorted(preset.omit))}")
            if preset.tested_with and preset.tested_on:
                print(f"  tested: {preset.tested_with}, {preset.tested_on.isoformat()}")
        parser.exit()


def _add_label_option(command: argparse.ArgumentParser) -> None:
    """Whether a label that surely lacks what it must show is given (SDB-217)."""
    command.add_argument(
        "--accept-incomplete-label",
        action="store_true",
        help=(
            "Give a label that surely lacks a pictogram, the signal word or a "
            "hazard statement, with its findings, instead of withholding it "
            "with the error label-incomplete."
        ),
    )


def _add_run_options(command: argparse.ArgumentParser) -> None:
    """What a run over many files needs (SDW-21 to SDW-23)."""
    command.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Write the records to FILE as JSON Lines, one line per file as it "
            "is done, instead of printing one JSON list. An existing FILE is "
            "refused unless --resume is given."
        ),
    )
    command.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue the run that wrote --output FILE: files whose record is "
            "in it already are left out."
        ),
    )
    _add_selection_options(command)


def _add_selection_options(command: argparse.ArgumentParser) -> None:
    """Which files a call works on, and how many at once (SDW-21, SDW-23)."""
    command.add_argument(
        "--jobs",
        type=int,
        default=1,
        metavar="N",
        help="Work on N files at once (default: 1).",
    )
    command.add_argument(
        "--exclude-from",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Leave out the files FILE names, one per line: a file name, a "
            "path relative to a directory given, or an absolute path."
        ),
    )


def _add_language_options(command: argparse.ArgumentParser) -> None:
    """The language of the messages, and a catalog of the caller's own (SDW-17)."""
    command.add_argument(
        "--lang",
        default=os.environ.get(LANGUAGE_VARIABLE) or DEFAULT_LANGUAGE,
        help=(
            "Language of the messages: "
            f"{', '.join(shipped_languages())} (default: {LANGUAGE_VARIABLE}, "
            f"else {DEFAULT_LANGUAGE}). The machine's language plays no part."
        ),
    )
    command.add_argument(
        "--messages",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "A message catalog of your own, a TOML file like the shipped ones; "
            "it replaces --lang, and what it lacks is said in English."
        ),
    )


def _catalog(parser: argparse.ArgumentParser, args: argparse.Namespace) -> Catalog:
    """The catalog the run words its messages with; exit code 2 without one."""
    try:
        messages = getattr(args, "messages", None)
        if messages is not None:
            return load_catalog(messages)
        return shipped_catalog(getattr(args, "lang", DEFAULT_LANGUAGE))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    # stdout carries the subcommand's output and nothing else: the parser's
    # log lines, which structlog prints to stdout unless told otherwise, go to
    # stderr, in structlog's default form whatever a host configured before.
    structlog.reset_defaults()
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(sys.stderr))

    # Before any file is read: a language without a catalog ends here.
    catalog = _catalog(parser, args)
    if args.command == "xml":
        missing = [str(path) for path in args.paths if not path.is_file()]
        if missing:
            parser.error(f"not a file: {', '.join(missing)}")
        if args.save is None and len(args.paths) > 1:
            parser.error("xml prints one file; several PDFs need --save DIRECTORY")
        if args.save is not None and not args.save.is_dir():
            parser.error(f"not a directory: {args.save}")
        return _xml(args.paths, args.save, catalog)

    if args.command == "diff":
        if args.examples < 0:
            parser.error("--examples takes a number from 0")
        return _diff(parser, args, catalog)

    if args.jobs < 1:
        parser.error("--jobs takes a number from 1")
    if args.command == "show":
        return _show(
            parser,
            args,
            catalog,
            # The day of the run, once for all its files (SDW-34).
            _ReadOptions(
                args.max_pages,
                False,
                args.lang,
                args.messages,
                _today(),
                args.accept_incomplete_label,
            ),
        )
    if args.resume and args.output is None:
        parser.error("--resume continues an output file: give --output FILE")
    if args.command == "ask":
        options = _AskOptions(
            _endpoint(parser, args), args.pages, args.retries, args.lang, args.messages
        )
        return _run(parser, args, catalog, _ask_one, options, processes=False)
    return _run(
        parser,
        args,
        catalog,
        _read_one,
        _ReadOptions(
            args.max_pages,
            args.include_raw_text,
            args.lang,
            args.messages,
            # The day of the run, once for all its files (SDW-34).
            _today(),
            args.accept_incomplete_label,
        ),
        processes=True,
    )


def _today() -> date:
    """The machine's date: the one place the command reads a clock (SDW-34)."""
    return datetime.now().astimezone().date()


def _endpoint(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> ask.Endpoint:
    """Whom the call asks; exit code 2 where it does not say, or says it wrongly."""
    if args.retries < 0:
        parser.error("--retries takes a number from 0")
    if args.pages < 1:
        parser.error("--pages takes a number from 1")
    if not args.endpoint or not args.model:
        parser.error(
            f"{args.command} needs an endpoint and a model: --endpoint and "
            f"--model, or {ENDPOINT_VARIABLE} and {MODEL_VARIABLE}"
        )
    chosen: presets.Preset | None = None
    if args.presets is not None and not args.preset:
        parser.error("--presets is where --preset is taken from: give --preset NAME")
    if args.preset:
        try:
            known = _known_presets(args.presets)
        except ValueError as exc:
            parser.error(str(exc))
        chosen = known.get(args.preset)
        if chosen is None:
            parser.error(
                f"no preset {args.preset!r}; there are: {', '.join(sorted(known))}"
            )
    extra: Any = {}
    if args.request_json:
        try:
            extra = json.loads(args.request_json)
        except ValueError as exc:
            parser.error(f"--request-json is no JSON: {exc}")
        if not isinstance(extra, dict):
            parser.error("--request-json takes a JSON object")
    try:
        return ask.Endpoint(
            args.endpoint,
            args.model,
            api_key=os.environ.get(API_KEY_VARIABLE) or None,
            timeout=args.timeout,
            # The preset first, then what the call adds or replaces (SDW-31).
            request={**(chosen.request if chosen else {}), **extra},
            omit=(chosen.omit if chosen else frozenset()) - extra.keys(),
            preset=chosen.name if chosen else None,
        )
    except ValueError as exc:
        parser.error(str(exc))


@cache
def _catalog_for(lang: str, messages: Path | None) -> Catalog:
    """The run's catalog again, in a worker process."""
    return load_catalog(messages) if messages is not None else shipped_catalog(lang)


@dataclass(frozen=True, slots=True)
class _ReadOptions:
    max_pages: int | None
    include_raw_text: bool
    lang: str
    messages: Path | None
    today: date
    accept_incomplete_label: bool = False


@dataclass(frozen=True, slots=True)
class _AskOptions:
    endpoint: ask.Endpoint
    pages: int
    retries: int
    lang: str
    messages: Path | None


def _run[T](
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    catalog: Catalog,
    work: Callable[[Path, T], Outcome],
    options: T,
    *,
    processes: bool,
) -> int:
    """Work on every file of the call and put out the records (SDW-21 to SDW-24)."""
    try:
        selection = scan.select(args.paths, args.exclude_from)
        lines = (
            scan.Lines.open(args.output, resume=args.resume)
            if args.output is not None
            else None
        )
    except scan.ScanError as exc:
        parser.error(str(exc))

    files = list(selection.files)
    skipped = 0
    if lines is not None:
        if lines.repaired:
            _say(catalog, "cli-half-line-removed", output=str(args.output))
        todo = [path for path in files if not lines.has(path)]
        skipped = len(files) - len(todo)
        files = todo

    counted = len(files) + skipped
    several = counted > 1
    progress = scan.Progress(
        len(files),
        lambda done, total, failed: _say(
            catalog, "cli-progress", done=done, total=total, failed=failed
        ),
    )
    records: dict[int, dict[str, Any]] = {}
    asked = prompt_tokens = completion_tokens = 0
    interrupted = False
    try:
        for index, outcome in scan.outcomes(
            files, work, options, jobs=args.jobs, processes=processes
        ):
            for line in outcome.said:
                print(line, file=sys.stderr)
            if outcome.record is not None:
                if lines is not None:
                    lines.write(outcome.record)
                else:
                    records[index] = outcome.record
            asked += outcome.asked
            prompt_tokens += outcome.prompt_tokens
            completion_tokens += outcome.completion_tokens
            progress.step(failed=outcome.failed)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if lines is not None:
            lines.close()

    if lines is None and not interrupted:
        indent = args.indent if args.indent > 0 else None
        print(
            json.dumps(
                [records[index] for index in sorted(records)],
                indent=indent,
                ensure_ascii=False,
            )
        )
    if interrupted:
        _say(
            catalog,
            "cli-interrupted",
            done=progress.done,
            total=progress.total,
        )
        return 130
    if several:
        if args.command == "ask":
            _say(
                catalog,
                "cli-summary-ask",
                files=counted,
                skipped=skipped,
                excluded=selection.excluded,
                asked=asked,
                failed=progress.failed,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        else:
            _say(
                catalog,
                "cli-summary-read",
                files=counted,
                skipped=skipped,
                excluded=selection.excluded,
                failed=progress.failed,
            )
    return 1 if progress.failed else 0


def _show(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    catalog: Catalog,
    options: _ReadOptions,
) -> int:
    """Read every file of the call and print its report (SDW-37 to SDW-41)."""
    try:
        selection = scan.select(args.paths, args.exclude_from)
    except scan.ScanError as exc:
        parser.error(str(exc))
    files = list(selection.files)
    # A file named on the line gets the full report, one that stands for its
    # directory a line (SDW-40).
    named = {path.resolve() for path in args.paths if path.is_file()}
    progress = scan.Progress(
        len(files),
        lambda done, total, failed: _say(
            catalog, "cli-progress", done=done, total=total, failed=failed
        ),
    )
    counts = {"sheets": 0, "others": 0, "with_notes": 0}
    waiting: dict[int, Outcome] = {}
    printed = 0
    # Whether the last thing printed was a full report: it stands apart.
    after_report = False
    try:
        for index, outcome in scan.outcomes(
            files, _read_one, options, jobs=args.jobs, processes=True
        ):
            waiting[index] = outcome
            progress.step(failed=outcome.failed)
            # In the order of the call, whichever file ends first (SDW-23).
            while printed in waiting:
                done = waiting.pop(printed)
                path = files[printed]
                full = path.resolve() in named
                if done.record is None:
                    # It broke the reader: the line and the trace on stderr.
                    for said in done.said:
                        print(said, file=sys.stderr)
                    lines = show.broke(str(path), catalog, full=full)
                elif full:
                    lines = show.report(done.record, str(path), catalog)
                else:
                    lines = [show.line(done.record, str(path), catalog)]
                if done.record is not None and show.is_sheet(done.record):
                    counts["sheets"] += 1
                    counts["with_notes"] += show.notes_count(done.record) > 0
                elif done.record is not None and not show.is_unreadable(done.record):
                    counts["others"] += 1
                if printed and (full or after_report):
                    print()
                print("\n".join(lines), flush=True)
                after_report = full
                printed += 1
    except KeyboardInterrupt:
        _say(catalog, "show-interrupted", done=progress.done, total=progress.total)
        return 130
    if len(files) > 1:
        print()
        print(
            _line(
                catalog,
                "show-summary",
                files=len(files),
                failed=progress.failed,
                excluded=selection.excluded,
                **counts,
            )
        )
    return 1 if progress.failed else 0


def _read_one(path: Path, options: _ReadOptions) -> Outcome:
    """Read one file: its record, and what is to be said about it (SDW-2, SDW-4)."""
    catalog = _catalog_for(options.lang, options.messages)
    said: list[str] = []
    try:
        reading = read_sheet(
            path,
            max_pages=options.max_pages,
            accept_incomplete_label=options.accept_incomplete_label,
        )
        # A file no text could be read from is in the output, named on
        # stderr, and fails the exit code (SDW-4). It may be no PDF at
        # all, so nothing is looked for inside it.
        unreadable = reading.extraction is None
        embedded = None if unreadable else read_embedded(path)
        if unreadable:
            reason = " ".join(catalog.render(error) for error in reading.errors)
            said.append(
                _line(catalog, "cli-file-failed", path=str(path), reason=reason)
            )
        record = {
            "file": _file(path),
            **reading_to_dict(
                reading,
                include_raw_text=options.include_raw_text,
                embedded=embedded,
                catalog=catalog,
                today=options.today,
            ),
        }
    # One file that breaks the parser must not cost the output for the
    # others; it is named on stderr and fails the exit code.
    except Exception as exc:  # noqa: BLE001
        return Outcome(None, tuple(_broke(catalog, path, exc)), failed=True)
    return Outcome(record, tuple(said), failed=unreadable)


@dataclass(frozen=True, slots=True)
class _Asked:
    """What asking about one file gave: its record, and what is to be said."""

    record: dict[str, Any]
    said: tuple[str, ...] = ()
    failed: bool = False
    asked: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _ask_about(
    path: Path,
    extraction: ExtractionResult | None,
    verification: Verification,
    unreadable: Sequence[Message],
    options: _AskOptions,
    catalog: Catalog,
) -> _Asked:
    """The record of ``ask`` for one file whose text was read (SDW-25, SDW-26).

    Raises ask.ModelError where the endpoint gives no answer that can be read.
    """
    record: dict[str, Any] = {"file": _file(path), "kind": verification.kind.value}
    if extraction is None:
        # No text, so nothing to send; named on stderr like in read (SDW-4).
        reason = " ".join(catalog.render(error) for error in unreadable)
        record["asked"] = False
        record["reason"] = catalog.to_dict(unreadable[0])
        line = _line(catalog, "cli-file-failed", path=str(path), reason=reason)
        return _Asked(record, (line,), failed=True)
    if verification.kind is not DocumentKind.SAFETY_DATA_SHEET:
        record["asked"] = False
        record["reason"] = catalog.to_dict(Message("model-not-asked"))
        return _Asked(record)
    # One request per sheet of the file (SDW-30); one that fails, fails the file.
    requests = ask.build_requests(extraction, path.name, pages=options.pages)
    replies = [
        ask.send(options.endpoint, request.prompt, retries=options.retries)
        for request in requests
    ]
    answers = [ask.read_model_answer(reply.content) for reply in replies]
    record.update(ask.asked_record(options.endpoint, requests, replies, answers))
    return _Asked(
        record,
        asked=True,
        prompt_tokens=sum(reply.prompt_tokens or 0 for reply in replies),
        completion_tokens=sum(reply.completion_tokens or 0 for reply in replies),
    )


def _model_failed(catalog: Catalog, path: Path, exc: ask.ModelError) -> Outcome:
    line = _line(
        catalog,
        "cli-file-failed",
        path=str(path),
        reason=catalog.render(exc.message),
    )
    return Outcome(None, (line,), failed=True)


def _ask_one(path: Path, options: _AskOptions) -> Outcome:
    """Ask the model about one file and keep what it says (SDW-25)."""
    catalog = _catalog_for(options.lang, options.messages)
    try:
        # The verdict decides whether the model is asked; the parser plays no
        # part, so its errors cannot keep a sheet from a second reading.
        try:
            extraction = extract_pdf_text(path)
        except ExtractionError as exc:
            errors = [exc.message]
            done = _ask_about(
                path,
                None,
                SDSVerifier().refuse_unreadable(errors),
                errors,
                options,
                catalog,
            )
        else:
            done = _ask_about(
                path,
                extraction,
                # Judged on the text as the reading judges it (SDB-167).
                SDSVerifier().verify(within_line_limit(extraction)[0]),
                (),
                options,
                catalog,
            )
    except ask.ModelError as exc:
        return _model_failed(catalog, path, exc)
    # As in read: one file that breaks costs only itself.
    except Exception as exc:  # noqa: BLE001
        return Outcome(None, tuple(_broke(catalog, path, exc)), failed=True)
    return _outcome(done)


def _outcome(done: _Asked) -> Outcome:
    return Outcome(
        done.record,
        done.said,
        failed=done.failed,
        asked=done.asked,
        prompt_tokens=done.prompt_tokens,
        completion_tokens=done.completion_tokens,
    )


def _diff(
    parser: argparse.ArgumentParser, args: argparse.Namespace, catalog: Catalog
) -> int:
    """Set two runs beside each other and say where they differ (SDW-27, SDW-28)."""
    try:
        by_name = args.match == "name"
        a = diff.load(args.a, by_name=by_name)
        b = diff.load(args.b, by_name=by_name)
        count_only = diff.count_only_lines(args.count_only_from)
    except diff.DiffError as exc:
        parser.error(str(exc))
    result = diff.compare_runs(a, b, count_only=count_only, examples=args.examples)

    for code, one, other in (
        ("diff-stages-differ", a.stages, b.stages),
        ("diff-models-differ", a.models, b.models),
        ("diff-questions-differ", a.questions, b.questions),
    ):
        # Said only where both runs name it: a record of old names no stage.
        if one and other and one != other:
            _say(
                catalog,
                code,
                a=", ".join(sorted(one)),
                b=", ".join(sorted(other)),
            )

    if args.details is not None:
        try:
            with args.details.open("w", encoding="utf-8") as handle:
                handle.writelines(line + "\n" for line in diff.detail_lines(result))
        except OSError as exc:
            parser.error(f"cannot write {args.details}: {exc}")
    if args.json:
        indent = args.indent if args.indent > 0 else None
        print(json.dumps(diff.to_json(result), indent=indent, ensure_ascii=False))
    else:
        for line in _diff_text(result, catalog):
            print(line)
    return 1 if result.differs else 0


def _diff_text(result: diff.Result, catalog: Catalog) -> list[str]:
    """The comparison for a reader, in the run's language."""
    lines = [
        _line(
            catalog,
            "diff-run",
            side=side,
            path=str(run.path),
            kind=run.kind,
            files=len(run.records),
        )
        for side, run in (("A", result.a), ("B", result.b))
    ]
    lines.append(
        _line(
            catalog,
            "diff-files",
            both=result.both,
            only_a=result.only_a,
            only_b=result.only_b,
            not_compared=result.not_compared,
        )
    )
    lines.append(
        _line(
            catalog,
            "diff-differing",
            differing=result.differing,
            counted_only=result.differing_counted_only,
        )
    )
    if not result.differs:
        lines.append(_line(catalog, "diff-none"))
    for name, count in result.fields.items():
        for code, counts in (
            ("diff-field", count.shown),
            ("diff-field-counted-only", count.counted_only),
        ):
            if counts:
                lines.append(
                    _line(
                        catalog,
                        code,
                        field=name,
                        gained=counts["gained"],
                        lost=counts["lost"],
                        changed=counts["changed"],
                    )
                )
            if code == "diff-field":
                for path, difference in count.examples:
                    statement = f" [{difference.code}]" if difference.code else ""
                    lines.append(f"    {path}{statement}")
                    lines.append(f"      A: {_short(difference.a)}")
                    lines.append(f"      B: {_short(difference.b)}")
    return lines


# An example shows where to look; --details and --json hold the whole value.
LONGEST_EXAMPLE = 220


def _short(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= LONGEST_EXAMPLE:
        return text
    return text[: LONGEST_EXAMPLE - 1] + "…"


def _xml(paths: Sequence[Path], directory: Path | None, catalog: Catalog) -> int:
    """Hand out each PDF's embedded eSDScom file (SDW-13).

    Byte for byte, because the file's declaration names its encoding. A file
    this tool refuses to read is not handed on either.
    """
    failed = 0
    handed_out = 0
    for path in paths:
        try:
            embedded = read_embedded(path)
            if embedded is None:
                # Among many PDFs most carry none; asked for one, it is the answer.
                if directory is None:
                    failed += 1
                _say(catalog, "cli-no-embedded-file", path=str(path))
                continue
            if embedded.content is None:
                failed += 1
                _say(
                    catalog,
                    "cli-embedded-not-handed-out",
                    path=str(path),
                    filename=embedded.filename,
                    reason=catalog.render(embedded.unreadable)
                    if embedded.unreadable
                    else "",
                )
                continue
            if directory is None:
                sys.stdout.buffer.write(embedded.content)
                sys.stdout.buffer.flush()
                handed_out += 1
                continue
            target = directory / f"{path.stem}.xml"
            with target.open("xb") as handle:
                handle.write(embedded.content)
            handed_out += 1
            _say(catalog, "cli-saved", path=str(path), target=str(target))
        # One PDF that cannot be opened, or whose target exists, costs only
        # itself; it is named on stderr and fails the exit code.
        except Exception as exc:  # noqa: BLE001
            failed += 1
            _report(catalog, path, exc)
    # With --save a PDF without an embedded file is passed over; a run that
    # handed out nothing at all has not done what it was asked (SDW-13).
    return 1 if failed or not handed_out else 0


def _file(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "filename": path.name,
        "size_bytes": path.stat().st_size,
    }


def _line(catalog: Catalog, code: str, **params: Any) -> str:
    return catalog.render(Message(code, params))


def _say(catalog: Catalog, code: str, **params: Any) -> None:
    """One line on stderr, in the run's language (SDW-17)."""
    print(_line(catalog, code, **params), file=sys.stderr)


def _broke(catalog: Catalog, path: Path, exc: Exception) -> list[str]:
    """What is said about a file that broke the reader: the line and the trace."""
    return [
        _line(
            catalog,
            "cli-file-broke",
            path=str(path),
            error=f"{type(exc).__name__}: {exc}",
        ),
        "".join(traceback.format_exception(exc)).rstrip("\n"),
    ]


def _report(catalog: Catalog, path: Path, exc: Exception) -> None:
    _say(
        catalog,
        "cli-file-broke",
        path=str(path),
        error=f"{type(exc).__name__}: {exc}",
    )
    traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover - import-time behaviour
    raise SystemExit(main())
