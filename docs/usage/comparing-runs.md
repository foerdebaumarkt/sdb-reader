# Comparing two runs

## What it is for

A run is what `read` or `ask` wrote for a set of files: one record per
file. `diff` sets two runs beside each other and says, field by field, in
how many files they differ, with examples. It reads no PDF and asks no
model, so it takes seconds and can be repeated at will.

| Runs | What the comparison shows |
| --- | --- |
| `read` and `ask` | where a model reads a sheet otherwise than the program: places to look for reading errors |
| `read` and `read` | what a change to the program does to a collection, before and after |
| `ask` and `ask` | where two models, or two runs of one model, disagree |

## Running it

```bash
sdb-reader read sheets/ --output read.jsonl --jobs 8
sdb-reader ask sheets/ --output answers.jsonl --jobs 4 --retries 3
sdb-reader diff read.jsonl answers.jsonl
```

The two runs are named A and B in the order given. Each is a file of
records as `read` or `ask` wrote it: JSON Lines from `--output`, or the JSON
list the command prints otherwise. Where a file of JSON Lines names a PDF
several times, the last line holds.

| Option | Effect |
| --- | --- |
| `--match path` | two records are of the same file if their paths are the same; this is the default |
| `--match name` | two records are of the same file if their file names are the same, for runs over copies in different places; a name that a run holds under several paths ends the command |
| `--examples N` | show up to N files per field; 3 unless you say otherwise |
| `--json` | print counts and examples as JSON instead of text |
| `--details FILE` | write every differing file with all its differences and both values to FILE, as JSON Lines; an existing FILE is replaced |
| `--count-only-from FILE` | count the files FILE names in a group of their own and show none of them, see below |
| `--indent N`, `--lang`, `--messages` | as for `read` |

Files that only one run names are counted and not compared.

## What is compared

Two runs of `read` are compared in every field of a reading. The fields are
named as in the output of `read`:

| `field` | What is compared |
| --- | --- |
| `kind` | what the file is |
| `stated_classification`, `stated_voluntary`, `stated_article`, `sheet_duty`, `countries` | what section 2 says about the classification, whether the sheet calls itself voluntary and the product an article there, whether the product needs a sheet, the countries |
| `signal_word`, `pictograms` | the signal word and the pictograms |
| `hazard_codes`, `precautionary_codes`, `supplemental_codes` | the codes of the H, P and EUH statements |
| `hazard_text`, `precautionary_text`, `supplemental_text` | the texts of the statements |
| `revision_date`, `issue_date`, `version`, `product_identifier` | dates, version and product name |
| `supplier_name`, `supplier_address`, `supplier_phone`, `email`, `supplier_website`, `information_email`, `emergency_phone` | the supplier, the address of whoever answers for the sheet, and the emergency number |
| `findings` | the codes of the findings |
| `embedded_differences` | the fields in which the embedded file differs from the sheet as read |
| `errors` | why a file could not be read |

Where one of the runs is of `ask`, only what a model is asked for is
compared:

| `field` | What is compared |
| --- | --- |
| `hazard_codes`, `precautionary_codes`, `supplemental_codes` | the codes of the H, P and EUH statements; a joined code such as P305+P351 counts as its parts |
| `wording` | the wording of a statement both name, with its `code`; capitals, punctuation and spaces do not count |
| `supplier_name`, `supplier_email` | the supplier's name and e-mail; capitals and spaces do not count |
| `revision_date` | the date of revision; a model that names no date that counts does not differ from a reading, but from another model that names one |

A file for which one of the two records has nothing to compare, such as a
file that is no sheet, counts as not comparable.

## What comes back

```text
A: read.jsonl (read), Dateien: 5000
B: answers.jsonl (ask), Dateien: 5000
Dateien in beiden: 5000; nur in A: 0; nur in B: 0; nicht vergleichbar: 700
Dateien mit Abweichung: 610; nur gezählt: 0
hazard_codes: dazugekommen 12, weggefallen 85, geändert 140
    /data/sheets/reiniger.pdf
      A: ["H315"]
      B: ["H315", "H319"]
wording: dazugekommen 0, weggefallen 0, geändert 96
    /data/sheets/lack.pdf [P102]
      A: ["Darf nicht in die Hände von Kindern"]
      B: ["Darf nicht in die Hände von Kindern gelangen."]
```

| Value | Meaning |
| --- | --- |
| dazugekommen (gained) | A has no value, B has one |
| weggefallen (lost) | A has a value, B has none |
| geändert (changed) | both have a value, and the two differ |

A file counts once per field, however many of its statements differ. In the
text a long value is cut after 220 characters; `--json` and `--details`
hold it whole. A line of `--details`:

```json
{"file": "/data/sheets/reiniger.pdf", "differences": [{"field": "hazard_codes", "a": ["H315"], "b": ["H315", "H319"]}, {"field": "wording", "code": "P102", "a": ["Darf nicht in die Hände von Kindern"], "b": ["Darf nicht in die Hände von Kindern gelangen."]}]}
```

## The program against a model

```bash
sdb-reader diff read.jsonl answers.jsonl --details differences.jsonl
```

Every difference is a place to look, in the PDF itself. Where the model is
right, the program has a reading error; where the program is right, nothing
follows. The answers are kept, so after a change to the program only `read`
runs again, and the same answers show whether the change did what it
should.

## The program before and after a change

```bash
sdb-reader read sheets/ --output before.jsonl --jobs 8
sdb-reader read sheets/ --output after.jsonl --jobs 8
sdb-reader diff before.jsonl after.jsonl
```

The first run is made with the program as it was, the second with the
changed one. Exit code 0 says the change altered no reading. Otherwise the
counts show how far the change reaches: a rule meant for a few sheets that
changes hundreds is too wide.

## Files that are only counted

```bash
sdb-reader diff before.jsonl after.jsonl --count-only-from held-back.txt
```

A part of a collection that nobody is to look at while working on the
program can still be counted. `--count-only-from FILE` names those files,
one per line: a file name, an absolute path, or the end of a path such as
`lieferant-a/reiniger.pdf`. Empty lines and lines beginning with `#` do not
count. Such a file is counted in a group of its own for each field and is
in no example and no line of `--details`:

```text
Dateien mit Abweichung: 41; nur gezählt: 5
revision_date: dazugekommen 38, weggefallen 0, geändert 3
revision_date, nur gezählt: dazugekommen 4, weggefallen 0, geändert 1
```

So the held-back files show whether a change holds on sheets it was not
made from, and nobody gets to see them. To keep them out of a run
altogether, `read` and `ask` have `--exclude-from`.

## Warnings

The command compares what it is given and says on the error output when the
two runs do not fit each other well:

| Warning | Meaning |
| --- | --- |
| different reading stages | the text of the PDFs was read by different versions; differences may come from the text, not from the reading |
| different models | two runs of `ask` asked different models; that may be what you want to compare |
| not the same question | two runs of `ask` were made with different wordings of the question |

A warning does not change the exit code.

## Exit codes

| Exit code | Meaning |
| --- | --- |
| 0 | no file differs in a compared field |
| 1 | at least one file differs, shown or only counted |
| 2 | a run cannot be read, mixes records of `read` and `ask` or holds none, or the files cannot be matched; nothing was compared |

Files that only one run names do not change the exit code.
