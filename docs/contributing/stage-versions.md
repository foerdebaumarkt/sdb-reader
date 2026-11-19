# Stage versions

The library reads in two stages, and each has a version in
`src/sdb_reader/versions.py`. Callers keep texts and readings and compare
these numbers to know whether what they kept still holds
([Keeping texts](../api/stored-texts.md)). A forgotten increase lets them
keep outdated readings without anybody noticing, so a test asks every time.

| Version | Raise it when | Its code |
| --- | --- | --- |
| `EXTRACTION_VERSION` | the same PDF can give another text | `extraction.py`, `layout.py`, `line_breaks.py` |
| `PARSER_VERSION` | the same text can give another reading: the verdict, the sheet, the statements and their tables, the findings, the JSON form | `parser.py`, `verification.py`, `compliance.py`, `statements.py`, `pictograms.py`, `reading.py`, `schema.py`, `serialise.py`, `messages.py`, `clp_statements_de.json` |

A version never falls. Raising `EXTRACTION_VERSION` makes every caller read
all its PDFs again, which for a large stock takes time; raising
`PARSER_VERSION` makes it read again from stored texts, which takes seconds.

## The fingerprints

`tests/test_stage_versions.py` holds, for each stage, a fingerprint of its
code at the version named. Comments, docstrings and formatting do not enter
it, and it is the same on every supported Python version. When you change a stage's code, the test fails and tells you the new
fingerprint. Then decide:

- **The same input can now give another result:** raise the version in
  `versions.py` and in the test, and set the new fingerprint.
- **It cannot** (a refactoring, a message's internals that the output does
  not show): keep the version and set the new fingerprint.

Say in the pull request which it was and why, and in
[CHANGELOG.md](../../CHANGELOG.md) when a version rose. The catalogs of
sentences are in neither stage: a reworded sentence changes no reading.

The exact list of files per stage is in the test; the table above is its
summary.
