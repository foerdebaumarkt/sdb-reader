# Reading a whole collection

A folder with thousands of sheets is another job than one file: it takes
time, it can be interrupted, and with `ask` each request costs time and
money. For that, `read` and `ask` share four options.

## Folders instead of files

```bash
sdb-reader read sheets/
sdb-reader read sheets/ more/extra.pdf
```

A folder stands for every file ending in `.pdf` in it and in its
subfolders, in the order of the sorted paths. Files and folders can be
mixed; a file named twice is read once. A folder without a single PDF ends
the command with exit code 2 before it reads anything.

## A result file that grows

```bash
sdb-reader read sheets/ --output run.jsonl
```

Without `--output` the result comes as one list at the end, and an
interruption just before it costs everything. With `--output FILE` the
command writes one line to FILE for each file as soon as it is done. Each
line is that file's record, the same as in the list. The format is called
JSON Lines; many programs read it line by line.

If FILE exists already, the command refuses the run instead of overwriting it.

## Continuing a run

```bash
sdb-reader read sheets/ --output run.jsonl --resume
```

`--resume` continues a run that was broken off: the command reads FILE,
leaves out every file whose line is in it already, and appends the others.
So the same call can be repeated as often as it takes to get through.

- A file counts as the same if path and size match its line. A file that
  was replaced is read again; its old line stays, and the last line that
  names a file is the one that holds.
- A file that failed, and so has no line, is tried again when the run
  continues.
- If the run was killed in the middle of a line, `--resume` removes the
  half line and says so.

Ctrl-C interrupts a run at any time. The command says how far it got and
ends with exit code 130; the result file holds whole lines only.

## Several files at once

```bash
sdb-reader read sheets/ --output run.jsonl --jobs 8
```

`--jobs N` lets the command work on N files at once, `read` in N processes,
`ask` with N requests in flight. For `read` the number of processor
cores is a good value. For `ask` the service decides how many requests
it takes at once.

What the command prints for a file does not depend on it. Only the order of
the lines in the result file then follows completion, not the order given.
The list without `--output` stays in the order given.

## Leaving files out

```bash
sdb-reader read sheets/ --exclude-from held-back.txt
```

`--exclude-from FILE` takes files out of the run: FILE names one per line,
as a file name, a path relative to one of the folders given, or an absolute
path. Empty lines and lines beginning with `#` do not count.

```text
# zurückgehalten
farbe.pdf
lieferant-a/reiniger.pdf
```

A file left out is not read, not sent to a model, and not in the result. So
a part of a collection nobody is to look at stays out of every run, without
having to be moved.

## What the command says on the way and at the end

For more than one file the command writes to the error output how far it
is, at most every 15 seconds, and at the end one line about the run:

```text
[sdb-reader] 1200 von 5000 Dateien fertig, gescheitert: 2
[sdb-reader] Dateien: 5000; früher erledigt: 0; ausgenommen: 500; gescheitert: 3
```

| Value | Meaning |
| --- | --- |
| Dateien (files) | how many files the run had, without those left out |
| früher erledigt (done before) | how many `--resume` left out because their line was there |
| ausgenommen (excluded) | how many `--exclude-from` took out |
| gescheitert (failed) | how many could not be read, or whose request failed |

## Asking a model about the whole collection

```bash
sdb-reader ask sheets/ --output answers.jsonl --jobs 4 --retries 3
sdb-reader diff read.jsonl answers.jsonl
```

For `ask` two things come on top, see [Asking a language model](asking.md).

`--retries N` sends a request again, up to N times, when it fails because
the service is busy or briefly out of reach, after a growing wait of at
most a minute. Without the option no request is repeated. Any other
failure, such as a wrong key, fails at once.

Where the service says how many tokens a request cost, the record holds
that under `usage`, and the line at the end adds it up:

```text
[sdb-reader] Dateien: 5000; früher erledigt: 0; ausgenommen: 500; gefragt: 4300; gescheitert: 3; Token gesendet: 5200000, empfangen: 1050000
```

What that is in money the command does not work out; the service names its
prices. A trial over a hundred sheets shows what a sheet costs on average
and how long it takes, before the whole collection runs.

The answers stay in the result file. `diff` sets them beside a run of
`read`, as often as needed and without asking again, see
[Comparing two runs](comparing-runs.md).
