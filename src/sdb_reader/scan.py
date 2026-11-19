"""Running ``read`` or ``ask`` over many files (SDW-21 to SDW-24).

Which files a call stands for, where their records go, and how several are
worked on at once. What is read of one file, and what is said about it, is
the caller's: this module only carries it.
"""

from __future__ import annotations

import json
import signal
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import (
    Executor,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

import structlog

# How often a long run says how far it is, at most (SDW-24).
PROGRESS_SECONDS = 15.0


class ScanError(Exception):
    """The call cannot be run as given; nothing was read."""


@dataclass(frozen=True, slots=True)
class Outcome:
    """What working on one file gave."""

    # None where the file has no record: reading it or asking about it failed.
    record: dict[str, Any] | None
    # Lines for stderr, in the run's language.
    said: tuple[str, ...] = ()
    failed: bool = False
    # Whether a model was asked about the file.
    asked: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True, slots=True)
class Selection:
    """The files of a call, in the order they are worked on (SDW-21)."""

    files: tuple[Path, ...]
    excluded: int


def select(paths: Sequence[Path], exclude_from: Path | None) -> Selection:
    """The files *paths* stand for, without those *exclude_from* names.

    A directory stands for every PDF under it, in sorted order; a file named
    twice is taken once. Raises ScanError for a path that is neither, a
    directory without a PDF, and a call that leaves no file.
    """
    lines = _exclusions(exclude_from)
    found: dict[Path, None] = {}
    excluded = 0
    for path in paths:
        if path.is_file():
            candidates, root = [path], None
        elif path.is_dir():
            candidates = sorted(
                p for p in path.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"
            )
            if not candidates:
                raise ScanError(f"no PDF file under: {path}")
            root = path
        else:
            raise ScanError(f"not a file or directory: {path}")
        for candidate in candidates:
            if _is_excluded(candidate, root, lines):
                excluded += 1
            else:
                found.setdefault(candidate, None)
    if not found:
        raise ScanError("no file left to read")
    return Selection(tuple(found), excluded)


def _exclusions(exclude_from: Path | None) -> frozenset[str]:
    if exclude_from is None:
        return frozenset()
    try:
        text = exclude_from.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScanError(f"cannot read {exclude_from}: {exc}") from exc
    return frozenset(
        stripped
        for line in text.splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#")
    )


def _is_excluded(path: Path, root: Path | None, lines: frozenset[str]) -> bool:
    """Whether a line names *path*: by its name, relative to *root*, or absolutely."""
    if not lines:
        return False
    if path.name in lines or str(path.resolve()) in lines:
        return True
    return root is not None and path.relative_to(root).as_posix() in lines


def _identity(path: str, size: int) -> tuple[str, int]:
    return path, size


@dataclass(slots=True)
class Lines:
    """An output file of JSON Lines: a record a line, kept as it grows (SDW-22)."""

    handle: IO[str]
    # The files whose record is in the file already: resolved path and size.
    known: set[tuple[str, int]] = field(default_factory=set)
    # Whether a half line a broken-off run left was removed.
    repaired: bool = False

    @classmethod
    def open(cls, target: Path, *, resume: bool) -> Lines:
        """Open *target* for a run; with *resume*, after what it holds already."""
        if target.exists() and not resume:
            raise ScanError(
                f"{target} exists; give another file, or --resume to continue it"
            )
        known: set[tuple[str, int]] = set()
        repaired = False
        if target.exists():
            known, cut = _records_in(target)
            with target.open("r+b") as raw:
                if cut is not None:
                    # A run that was killed while writing left half a line.
                    raw.truncate(cut)
                    repaired = True
                elif raw.seek(0, 2) and _last_byte(raw) != b"\n":
                    # A whole record without its line end: the next starts anew.
                    raw.write(b"\n")
        try:
            handle = target.open("a", encoding="utf-8")
        except OSError as exc:
            raise ScanError(f"cannot write {target}: {exc}") from exc
        return cls(handle, known, repaired)

    def has(self, path: Path) -> bool:
        """Whether *path* as it is now has its record in the file."""
        return _identity(str(path.resolve()), path.stat().st_size) in self.known

    def write(self, record: dict[str, Any]) -> None:
        self.handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.handle.flush()

    def close(self) -> None:
        self.handle.close()


def _last_byte(raw: IO[bytes]) -> bytes:
    raw.seek(-1, 2)
    return raw.read(1)


def _records_in(target: Path) -> tuple[set[tuple[str, int]], int | None]:
    """The files recorded in *target*, and where to cut a half last line."""
    known: set[tuple[str, int]] = set()
    position = 0
    lines = target.read_bytes().split(b"\n")
    for number, line in enumerate(lines):
        if line.strip():
            try:
                record = json.loads(line)
                location = record["file"]
                known.add(_identity(location["path"], location["size_bytes"]))
            except (ValueError, KeyError, TypeError) as exc:
                if number == len(lines) - 1:
                    return known, position
                raise ScanError(
                    f"{target}, line {number + 1} is no record of this command"
                ) from exc
        position += len(line) + 1
    return known, None


def _in_a_worker() -> None:
    """Set a worker process up: it answers to its parent, not to the terminal.

    Ctrl-C reaches every process of the terminal; the parent ends the run
    and the workers with it. And a worker's log lines go where the parent's
    go, to stderr: stdout carries the output and nothing else (SDW-3).
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    structlog.reset_defaults()
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(sys.stderr))


def outcomes[T](
    files: Sequence[Path],
    work: Callable[[Path, T], Outcome],
    options: T,
    *,
    jobs: int,
    processes: bool,
) -> Iterator[tuple[int, Outcome]]:
    """Work on *files*, *jobs* at once; each one's position and outcome as it ends.

    One at a time in this process where *jobs* is 1. Otherwise in processes
    (*processes*, for work that computes) or threads (for work that waits).
    Closing the iterator early, or an interrupt, ends the workers.
    """
    if jobs <= 1:
        for index, path in enumerate(files):
            yield index, work(path, options)
        return

    executor: Executor = (
        ProcessPoolExecutor(jobs, initializer=_in_a_worker)
        if processes
        else ThreadPoolExecutor(jobs)
    )
    futures: dict[Future[Outcome], int] = {}
    try:
        futures = {
            executor.submit(work, path, options): index
            for index, path in enumerate(files)
        }
        for future in as_completed(futures):
            yield futures[future], future.result()
    finally:
        for future in futures:
            future.cancel()
        # A process in the middle of a file is not waited for: its record
        # would not be written anyway.
        for process in list(getattr(executor, "_processes", {}).values()):
            process.terminate()
        executor.shutdown(wait=False, cancel_futures=True)


@dataclass(slots=True)
class Progress:
    """Says how far a run is, not more often than every few seconds (SDW-24)."""

    total: int
    say: Callable[[int, int, int], None]
    done: int = 0
    failed: int = 0
    _last: float = field(default_factory=time.monotonic)

    def step(self, *, failed: bool) -> None:
        self.done += 1
        self.failed += failed
        now = time.monotonic()
        if (
            self.total > 1
            and self.done < self.total
            and now - self._last >= PROGRESS_SECONDS
        ):
            self._last = now
            self.say(self.done, self.total, self.failed)
