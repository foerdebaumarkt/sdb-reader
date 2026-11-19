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

## Documentation

The documentation is at <https://foerdebaumarkt.github.io/sdb-reader/>, one
edition per released version. The same pages are in the repository under
[docs/](https://github.com/foerdebaumarkt/sdb-reader/tree/main/docs).

| You want to | Read |
| --- | --- |
| run the command and understand what it prints | [Using the command line](https://foerdebaumarkt.github.io/sdb-reader/latest/usage/README.html), in German: [Bedienung](https://foerdebaumarkt.github.io/sdb-reader/latest/bedienung/README.html) |
| read sheets from a Python program | [Using the library](https://foerdebaumarkt.github.io/sdb-reader/latest/api/README.html) |
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
