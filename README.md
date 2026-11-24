# sdb-reader

Reads German safety data sheets (Sicherheitsdatenblätter) under REACH and CLP
from PDF files, without a language model: the same file always gives the same
result, and every rule the reader follows is written down.

Deutsch: [README.de.md](https://github.com/foerdebaumarkt/sdb-reader/blob/main/README.de.md)

```bash
sdb-reader read sheet.pdf
```

For each PDF it says:

- **what the file is:** a German safety data sheet, a safety information, a
  safety data sheet in another language, or another document;
- **the classification** that section 2 states;
- **the label:** signal word, pictograms, and the H, P and EUH statements,
  with the sheet's wording beside the regulation's;
- **dates and version**, the countries the sheet is issued for, and the
  supplier;
- **what is wrong with the sheet as a document:** revised before 2021, no
  readable date, a classification and a label that contradict each other, a
  statement worded differently from the regulation.

The result is JSON. Warnings and findings come as a fixed code with a
sentence, in German or English. To read a sheet yourself, `show` prints the
same as a report:

```bash
sdb-reader show sheet.pdf
```

[What it
handles](https://foerdebaumarkt.github.io/sdb-reader/latest/what-it-handles.html)
says on one page, without technical terms, what the reader does.

## Why not just give the PDF to a language model?

For a single sheet you look at yourself, that works well. In a test in
November 2026 on 30 difficult sheets, current large commercial models read the
supplier, the date and the codes printed on the label almost without error,
and so did the smaller models of the same providers. `sdb-reader` is for when
you read many sheets and act on the result: decide whether a product may be
sold, fill a shop or a database, check a supplier's sheets. Then a few things
matter that a model does not give you:

- **One rule instead of a model's judgement.** Many labels print some
  statements only as a sentence, without the code. Asked for "the codes", one
  model names the code of such a sentence, another leaves it out, a third
  guesses: in the same test, an open model listed six precautionary codes for
  a spray that its label does not print, and none on a second run with the
  same input. `sdb-reader` applies a fixed rule and says for each code whether
  the sheet prints it or the reader assigned it from the sentence.
- **The same sheet, the same answer.** A model may answer differently on a
  second run. `sdb-reader` reads a file the same way every time, so a result
  you act on today is the result you get tomorrow.
- **Every value can be traced.** Each part of a reading comes from a numbered,
  tested rule. A wrong reading is a rule to fix, not a question to ask again.
- **Thousands of sheets, no cost per page, offline.** A large commercial model
  costs a few cents per sheet; a model on your own computer costs time and is
  less reliable. `sdb-reader` runs on an ordinary computer and sends no sheet
  anywhere.
- **A fixed format with findings.** The result is JSON with a published
  schema, with fixed codes for every warning and finding, including where a
  sheet falls short of the CLP Regulation.

**What kind of model it takes.** If you use a model anyway: current models
from the large providers read sheets very well, their small and cheap ones
included. Open models run on your own computer did noticeably worse in the
same test, even on a high-end workstation with 128 GB of memory, the most that
ordinary desktop and laptop computers offer (we tried models of about 27
billion parameters and a larger mixture-of-experts model). They read printed
codes reliably, but where a label prints only sentences, they leave statements
out or guess. Open models too large for such a machine were not tested. Asking
for a word-for-word quote of each sentence and checking it against the text
catches most guesses, but also drops correct answers where the sheet words a
statement differently from the regulation. (As of 2026; models change
quickly.)

`sdb-reader ask` puts a sheet to a model of your choice and keeps its answer
beside the reading, so the two can be compared. [How it
works](https://foerdebaumarkt.github.io/sdb-reader/latest/how-it-works.html) explains more.

**The idea behind it.** The reader gives what a sheet prints and reports,
separately, where the sheet falls short of the regulation; what to do about it
stays with you. [How it
works](https://foerdebaumarkt.github.io/sdb-reader/latest/how-it-works.html)
describes the philosophy behind it.

## Documentation

The documentation is at <https://foerdebaumarkt.github.io/sdb-reader/>, one
edition per released version. The same pages are in the repository under
[docs/](https://github.com/foerdebaumarkt/sdb-reader/tree/main/docs).

| You want to | Read |
| --- | --- |
| run the command and understand what it prints | [Using the command line](https://foerdebaumarkt.github.io/sdb-reader/latest/usage/README.html), in German: [Bedienung](https://foerdebaumarkt.github.io/sdb-reader/latest/bedienung/README.html) |
| read sheets from a Python program | [Using the library](https://foerdebaumarkt.github.io/sdb-reader/latest/api/README.html) |
| see what the reader deals with | [What it handles](https://foerdebaumarkt.github.io/sdb-reader/latest/what-it-handles.html), in German: [Was es abdeckt](https://foerdebaumarkt.github.io/sdb-reader/latest/was-es-abdeckt.html) |
| understand how a file becomes a reading | [How it works](https://foerdebaumarkt.github.io/sdb-reader/latest/how-it-works.html) |
| change the reader | [Contributing](https://foerdebaumarkt.github.io/sdb-reader/latest/contributing/README.html) |
| know what a version changed | [CHANGELOG.md](https://foerdebaumarkt.github.io/sdb-reader/latest/changelog.html) |
| read the binding rules | [specs/](https://github.com/foerdebaumarkt/sdb-reader/blob/main/specs/README.md), in German |

## Install

Needs Python 3.12 or newer. Install it from the Python Package Index:

```bash
uv tool install sdb-reader
```

Scanned sheets are read by text recognition, which needs `tesseract` with
German language data. [Installing](https://foerdebaumarkt.github.io/sdb-reader/latest/usage/installing.html) has the details.

## Limits

- German sheets only. A sheet in another language is recognised as one and
  not read.
- It reads one file at a time. Which sheets belong to one product is for the
  program that uses it; the library then chooses the current one among them.
- Whether a product needs a safety data sheet is read from the classification
  and the label. Section 2.3 (PBT, vPvB, candidate list) is not read.
- An older sheet in another language, without numbered subsections, counts as
  a document.
- A form in two columns without colons is read as label and value in
  section 1 only. In the other sections of such a sheet a value may not be
  found.

## Licence

GNU Affero General Public License, version 3 or later ([LICENSE](https://github.com/foerdebaumarkt/sdb-reader/blob/main/LICENSE)).
The PDF library the reader is built on, PyMuPDF (installed as `pymupdf-lite`), is under the AGPL, so a
program that uses this package takes on its obligations.

Copyright © 2026 Förde-Baumarkt Holger Claussen GmbH & Co. KG
(<service@foerde-baumarkt.de>).
[NOTICE](https://github.com/foerdebaumarkt/sdb-reader/blob/main/NOTICE) names the copyright holder and the source of the regulation's
wording that the package carries.
