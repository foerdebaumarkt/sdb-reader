# Measuring a change

## Why a test is not enough

Safety data sheets come from hundreds of authoring systems, and each lays
its sheets out in its own way. A rule that reads one supplier's sheets
better can read another's worse, and no set of unit tests shows that. So a
change to how a PDF becomes text, or how a text becomes a reading, is
measured before it is merged: all sheets of a large collection are read
before and after the change, and every reading that differs is looked at.

The collection is private. It holds suppliers' sheets, which are theirs, and
cannot be published with the reader. A tenth of it is held back: nobody
looks at those sheets while working on a rule, and they are only counted, so
that they show whether a rule holds on sheets it was not written from.

## Measuring on sheets of your own

The measurement needs no tool beyond the command itself. With any folder of
sheets you have, read it with the program as it was (a checkout of `main`,
or the released package) and with your change, and set the two runs beside
each other:

```bash
sdb-reader read sheets/ --output before.jsonl --jobs 8   # the program as it was
sdb-reader read sheets/ --output after.jsonl --jobs 8    # with your change
sdb-reader diff before.jsonl after.jsonl --details changed.jsonl
```

`diff` counts for each field of a reading how many sheets gained a value,
lost one or changed it, shows examples, and ends with exit code 0 when the
change altered no reading. `--details` holds every sheet that differs with
both values, to look at one by one. `--count-only-from FILE` counts sheets
you have set aside without showing them. The manual has the details:
[Comparing two runs](../usage/comparing-runs.md).

Kept answers of a language model serve as a second reading for the same
purpose: `sdb-reader ask` once, then `diff` of each new run of `read`
against the same answers, without asking again
([Asking a language model](../usage/asking.md)). Mind where the sheets'
text goes when the model is a service.

## What a contributor without access does

You do not need the collection to contribute:

1. **Make the smallest sheet that shows the problem.** A text with invented
   names is enough for the parser (see the tests in
   `tests/test_sds_parser.py`, which build a sheet from a few lines); for
   the reading stage, a small PDF made in the test with PyMuPDF (see
   `tests/test_sds_layout.py` and `tests/test_ocr_real.py`).
2. **Write the test that fails**, with the marker of the rule it holds.
3. **Never put a supplier's sheet, name, address or number into the
   repository**, in a test, a spec, a commit or an issue. Use invented ones:
   "Muster GmbH", "Musterweg 1", a phone number in the range 0555. Describe
   the layout rather than the supplier.
4. **Open the pull request.** Say what a measurement on sheets of your own
   showed, if you made one. A maintainer runs the measurement on the
   collection and reports
   in the pull request what changed: how many sheets, in which fields, and
   whether any sheet lost a value that was read correctly before.

A change is merged when the measurement shows what the change set out to do
and nothing else, or when everything else is explained.

## What the measurement reports

For each field of a reading (the kind of file, the classification, the
codes, the statement texts, dates, version, supplier, findings): how many
sheets gained a value, lost one, or changed it, separately for the sheets
worked on and the held-back ones, with examples from the former only.

A rule that changes many sheets where it was meant to change a few is too
wide. Narrow it and measure again; the decision log of the spec records what
was tried and why it was dropped.
