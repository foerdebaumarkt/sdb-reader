"""read and ask over a whole collection (SDW-21 to SDW-24)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_ask import AGREEING, _Model, model  # noqa: F401 - fixture
from test_cli import LEAFLET, SHEET, _pdf

from sdb_reader import ask, cli, scan


def _collection(root: Path) -> list[Path]:
    """Five PDFs in a tree, and a file that is none."""
    (root / "b" / "deep").mkdir(parents=True)
    (root / "a").mkdir()
    files = [
        _pdf(root / "a" / "one.pdf", SHEET),
        _pdf(root / "a" / "two.PDF", LEAFLET),
        _pdf(root / "b" / "three.pdf", SHEET.replace("Küchenfarbe", "Wandfarbe")),
        _pdf(root / "b" / "deep" / "four.pdf", LEAFLET),
        _pdf(root / "five.pdf", SHEET.replace("Küchenfarbe", "Deckenfarbe")),
    ]
    (root / "notes.txt").write_text("no PDF")
    return sorted(files)


def _read(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = cli.main(["read", *argv])
    out, err = capsys.readouterr()
    return code, out, err


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _names(records: list[dict[str, Any]]) -> list[str]:
    return [record["file"]["filename"] for record in records]


@pytest.mark.spec("SDW-21")
def test_a_directory_stands_for_every_pdf_under_it_in_sorted_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _collection(tmp_path / "sheets")

    code, out, _ = _read(capsys, str(tmp_path / "sheets"))

    assert code == 0
    assert [r["file"]["path"] for r in json.loads(out)] == [
        str(path.resolve()) for path in files
    ]


@pytest.mark.spec("SDW-21")
def test_files_and_directories_mix_and_a_file_named_twice_is_read_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _collection(tmp_path / "sheets")
    five = tmp_path / "sheets" / "five.pdf"

    _, out, _ = _read(capsys, str(five), str(tmp_path / "sheets" / "a"), str(five))

    assert _names(json.loads(out)) == ["five.pdf", "one.pdf", "two.PDF"]


@pytest.mark.spec("SDW-21")
@pytest.mark.parametrize("given", ["empty", "missing"])
def test_a_directory_without_a_pdf_and_a_path_that_is_nothing_end_the_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], given: str
) -> None:
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / "notes.txt").write_text("no PDF")
    good = _pdf(tmp_path / "good.pdf", SHEET)

    with pytest.raises(SystemExit) as ended:
        cli.main(["read", str(good), str(tmp_path / given)])

    assert ended.value.code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.spec("SDW-21")
def test_files_a_list_names_are_left_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """By name, by path under the directory given, by absolute path; a line
    that is a comment or empty names nothing."""
    root = tmp_path / "sheets"
    _collection(root)
    excluded = tmp_path / "held-back.txt"
    excluded.write_text(
        f"# held back\n\none.pdf\nb/deep/four.pdf\n{(root / 'five.pdf').resolve()}\n"
    )

    code, out, err = _read(capsys, str(root), "--exclude-from", str(excluded))

    assert code == 0
    assert _names(json.loads(out)) == ["two.PDF", "three.pdf"]
    assert "ausgenommen: 3" in err
    for name in ("one.pdf", "four.pdf", "five.pdf"):
        assert name not in out


@pytest.mark.spec("SDW-21")
def test_a_list_that_leaves_no_file_ends_the_call(tmp_path: Path) -> None:
    good = _pdf(tmp_path / "good.pdf", SHEET)
    excluded = tmp_path / "all.txt"
    excluded.write_text("good.pdf\n")

    with pytest.raises(SystemExit) as ended:
        cli.main(["read", str(good), "--exclude-from", str(excluded)])

    assert ended.value.code == 2


@pytest.mark.spec("SDW-22", "SDW-16")
def test_an_output_file_holds_one_record_a_line_and_stdout_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _collection(tmp_path / "sheets")
    target = tmp_path / "run.jsonl"

    code, out, _ = _read(capsys, str(tmp_path / "sheets"), "--output", str(target))
    _, plain, _ = _read(capsys, str(tmp_path / "sheets"), "--indent", "0")

    assert code == 0
    assert out == ""
    assert target.read_text().endswith("\n")
    # A line is the record the list holds for the file.
    assert _lines(target) == json.loads(plain)
    assert len(_lines(target)) == len(files)


@pytest.mark.spec("SDW-22")
def test_an_existing_output_file_is_refused_without_resume(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = _pdf(tmp_path / "good.pdf", SHEET)
    target = tmp_path / "run.jsonl"
    target.write_text("")

    with pytest.raises(SystemExit) as ended:
        cli.main(["read", str(good), "--output", str(target)])

    assert ended.value.code == 2
    assert target.read_text() == ""


@pytest.mark.spec("SDW-22")
def test_resume_without_an_output_file_is_a_wrong_call(tmp_path: Path) -> None:
    good = _pdf(tmp_path / "good.pdf", SHEET)

    with pytest.raises(SystemExit) as ended:
        cli.main(["read", str(good), "--resume"])

    assert ended.value.code == 2


@pytest.mark.spec("SDW-22", "SDW-24")
def test_a_run_that_was_broken_off_is_continued_without_reading_a_file_twice(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files = _collection(tmp_path / "sheets")
    target = tmp_path / "run.jsonl"
    read: list[str] = []
    real = cli.read_sheet

    def interrupted_at_the_third(path: Path, **kwargs: Any) -> Any:
        if len(read) == 2:
            raise KeyboardInterrupt
        read.append(path.name)
        return real(path, **kwargs)

    monkeypatch.setattr(cli, "read_sheet", interrupted_at_the_third)
    code, out, err = _read(capsys, str(tmp_path / "sheets"), "--output", str(target))

    assert code == 130
    assert out == ""
    assert "--resume" in err
    assert "2 von 5" in err
    assert _names(_lines(target)) == read == [files[0].name, files[1].name]

    def counted(path: Path, **kwargs: Any) -> Any:
        read.append(path.name)
        return real(path, **kwargs)

    monkeypatch.setattr(cli, "read_sheet", counted)
    code, _, err = _read(
        capsys, str(tmp_path / "sheets"), "--output", str(target), "--resume"
    )

    assert code == 0
    assert sorted(read) == sorted(path.name for path in files)
    assert sorted(_names(_lines(target))) == sorted(path.name for path in files)
    assert "früher erledigt: 2" in err


@pytest.mark.spec("SDW-22")
def test_a_file_that_was_replaced_is_read_again(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _pdf(tmp_path / "sheet.pdf", SHEET)
    other = _pdf(tmp_path / "other.pdf", LEAFLET)
    target = tmp_path / "run.jsonl"
    _read(capsys, str(path), str(other), "--output", str(target))

    _pdf(path, SHEET + "Ein weiterer Absatz, der die Datei größer macht.\n")
    _, _, err = _read(
        capsys, str(path), str(other), "--output", str(target), "--resume"
    )

    assert _names(_lines(target)) == ["sheet.pdf", "other.pdf", "sheet.pdf"]
    assert "früher erledigt: 1" in err


@pytest.mark.spec("SDW-22")
def test_a_half_last_line_is_removed_and_its_file_read_again(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _collection(tmp_path / "sheets")
    target = tmp_path / "run.jsonl"
    _read(capsys, str(tmp_path / "sheets"), "--output", str(target))
    whole = target.read_text().splitlines(keepends=True)
    target.write_text("".join(whole[:2]) + whole[2][:40])

    code, _, err = _read(
        capsys, str(tmp_path / "sheets"), "--output", str(target), "--resume"
    )

    assert code == 0
    assert "unvollständig" in err
    assert sorted(_names(_lines(target))) == sorted(path.name for path in files)


@pytest.mark.spec("SDW-22")
def test_an_output_file_with_a_line_that_is_no_record_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = _pdf(tmp_path / "good.pdf", SHEET)
    target = tmp_path / "run.jsonl"
    target.write_text(
        '{"something": "else"}\n{"file": {"path": "x", "size_bytes": 1}}\n'
    )

    with pytest.raises(SystemExit) as ended:
        cli.main(["read", str(good), "--output", str(target), "--resume"])

    assert ended.value.code == 2


@pytest.mark.spec("SDW-22")
def test_a_file_without_a_record_is_tried_again_on_resume(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good = _pdf(tmp_path / "good.pdf", SHEET)
    bad = _pdf(tmp_path / "bad.pdf", SHEET)
    target = tmp_path / "run.jsonl"
    real = cli.read_sheet

    def breaking(path: Path, **kwargs: Any) -> Any:
        if path.name == "bad.pdf":
            raise RuntimeError("parser broke")
        return real(path, **kwargs)

    monkeypatch.setattr(cli, "read_sheet", breaking)
    code, _, err = _read(capsys, str(good), str(bad), "--output", str(target))

    assert code == 1
    assert "gescheitert: 1" in err
    assert _names(_lines(target)) == ["good.pdf"]

    monkeypatch.setattr(cli, "read_sheet", real)
    code, _, err = _read(
        capsys, str(good), str(bad), "--output", str(target), "--resume"
    )

    assert code == 0
    assert _names(_lines(target)) == ["good.pdf", "bad.pdf"]
    # Done before is not failed.
    assert "früher erledigt: 1" in err
    assert "gescheitert: 0" in err


@pytest.mark.spec("SDW-23")
def test_what_is_said_about_a_file_does_not_depend_on_how_many_are_read_at_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Four processes and an output file give, as a set, the plain run's records."""
    files = _collection(tmp_path / "sheets")
    target = tmp_path / "run.jsonl"

    _, plain, _ = _read(capsys, str(tmp_path / "sheets"))
    code, _, _ = _read(
        capsys, str(tmp_path / "sheets"), "--jobs", "4", "--output", str(target)
    )

    def by_path(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(records, key=lambda record: record["file"]["path"])

    assert code == 0
    assert by_path(_lines(target)) == by_path(json.loads(plain))
    assert len(_lines(target)) == len(files)


@pytest.mark.spec("SDW-23")
def test_the_list_on_stdout_keeps_the_order_given_with_several_at_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = _collection(tmp_path / "sheets")

    _, out, _ = _read(capsys, str(tmp_path / "sheets"), "--jobs", "3")

    assert _names(json.loads(out)) == [path.name for path in files]


@pytest.mark.spec("SDW-24")
def test_a_run_over_several_files_says_at_the_end_what_it_did(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _collection(tmp_path / "sheets")
    one = _pdf(tmp_path / "one.pdf", SHEET)

    _, _, several = _read(capsys, str(tmp_path / "sheets"))
    _, _, single = _read(capsys, str(one))
    _, _, english = _read(capsys, str(tmp_path / "sheets"), "--lang", "en")

    assert "Dateien: 5; früher erledigt: 0; ausgenommen: 0; gescheitert: 0" in several
    assert "files: 5; done before: 0; excluded: 0; failed: 0" in english
    # One file needs no summing up.
    assert single == ""


@pytest.mark.spec("SDW-24")
def test_a_long_run_says_how_far_it_is(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _collection(tmp_path / "sheets")
    monkeypatch.setattr(scan, "PROGRESS_SECONDS", 0.0)

    _, out, err = _read(capsys, str(tmp_path / "sheets"))

    assert "1 von 5 Dateien fertig" in err
    assert "4 von 5 Dateien fertig" in err
    # Never on stdout, which holds the list and nothing else.
    assert len(json.loads(out)) == 5


def _ask(
    capsys: pytest.CaptureFixture[str], served: _Model, *argv: str
) -> tuple[int, str, str]:
    code = cli.main(["ask", "--endpoint", served.url, "--model", "some-model", *argv])
    out, err = capsys.readouterr()
    return code, out, err


@pytest.mark.spec("SDW-25")
def test_a_request_the_endpoint_was_too_busy_for_is_sent_again_on_demand(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)
    waits: list[float] = []
    monkeypatch.setattr(ask, "_wait", waits.append)

    model.statuses = [503]
    refused, _, err = _ask(capsys, model, str(path))
    model.statuses = [503, 429]
    code, out, _ = _ask(capsys, model, str(path), "--retries", "2")

    # Without the option a request is not repeated.
    assert refused == 1
    assert "503" in err
    assert code == 0
    assert json.loads(out)[0]["asked"] is True
    assert len(model.requests) == 1 + 3
    assert waits == [1.0, 2.0]


@pytest.mark.spec("SDW-25")
def test_the_wait_the_endpoint_names_is_taken_up_to_a_minute(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)
    waits: list[float] = []
    monkeypatch.setattr(ask, "_wait", waits.append)

    model.retry_after = "7"
    model.statuses = [429]
    _ask(capsys, model, str(path), "--retries", "1")
    model.retry_after = "3600"
    model.statuses = [429]
    _ask(capsys, model, str(path), "--retries", "1")

    assert waits == [7.0, 60.0]


@pytest.mark.spec("SDW-25")
def test_a_failure_that_does_not_pass_fails_at_once_and_retries_run_out(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _pdf(tmp_path / "farbe.pdf", SHEET)
    monkeypatch.setattr(ask, "_wait", lambda seconds: None)

    model.statuses = [401]
    denied, _, _ = _ask(capsys, model, str(path), "--retries", "3")
    asked_once = len(model.requests)
    model.status = 503
    busy, _, err = _ask(capsys, model, str(path), "--retries", "2")

    assert denied == 1
    assert asked_once == 1
    assert busy == 1
    assert len(model.requests) == 1 + 3
    assert "503" in err


@pytest.mark.spec("SDW-26", "SDW-24")
def test_what_the_requests_cost_is_in_the_record_and_summed_up(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,  # noqa: F811
) -> None:
    _collection(tmp_path / "sheets")
    model.body = json.dumps(
        {
            "choices": [{"message": {"content": json.dumps(AGREEING)}}],
            "usage": {"prompt_tokens": 1200, "completion_tokens": 80},
        }
    ).encode()
    target = tmp_path / "asked.jsonl"

    code, out, err = _ask(
        capsys, model, str(tmp_path / "sheets"), "--jobs", "2", "--output", str(target)
    )

    records = _lines(target)
    asked = [record for record in records if record["asked"]]
    assert code == 0
    assert out == ""
    assert len(records) == 5
    assert len(asked) == 3
    assert all(
        record["usage"] == {"prompt_tokens": 1200, "completion_tokens": 80}
        for record in asked
    )
    assert all("usage" not in r for r in records if not r["asked"])
    assert "Dateien: 5" in err
    assert "gefragt: 3" in err
    assert "Token gesendet: 3600, empfangen: 240" in err
    # Only a sheet is sent.
    assert len(model.requests) == 3


@pytest.mark.spec("SDW-22")
def test_a_run_of_ask_is_continued_without_asking_twice(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    model: _Model,  # noqa: F811
) -> None:
    _collection(tmp_path / "sheets")
    target = tmp_path / "asked.jsonl"
    _ask(capsys, model, str(tmp_path / "sheets" / "a"), "--output", str(target))
    asked = len(model.requests)

    code, _, err = _ask(
        capsys, model, str(tmp_path / "sheets"), "--output", str(target), "--resume"
    )

    assert code == 0
    assert len(_lines(target)) == 5
    assert "früher erledigt: 2" in err
    # a/one.pdf was asked about before; the two other sheets are asked now.
    assert asked == 1
    assert len(model.requests) == 3
