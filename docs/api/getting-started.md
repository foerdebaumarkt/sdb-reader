# Getting started

## Install

The package needs Python 3.12 or newer and is installed from the Python
Package Index, as a dependency of your program:

```bash
uv add sdb-reader
pip install sdb-reader
```

Sheets whose pages are pictures are read by text recognition, which needs the
program `tesseract` with German language data on the machine
([Installing](../usage/installing.md#install-text-recognition)).

The package is under the AGPL, version 3 or later, because the PDF library it
is built on is. A program that uses it takes on the AGPL's obligations.

## What you import

Everything you need is exported by the package itself:

```python
import sdb_reader
```

What is reached only through a submodule, such as `sdb_reader.parser`, is
internal and can change with any release
([What is promised](stability.md)).

## A file to read

The examples need a file. This makes a small one; with a file of your own,
skip it and set `path`.

```python
import tempfile
from pathlib import Path

import pymupdf

text = """Sicherheitsdatenblatt
gemäß Verordnung (EG) Nr. 1907/2006
Überarbeitet am: 12.03.2024    Version: 3.1
ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens
1.1 Produktidentifikator
Handelsname: Musterreiniger
1.3 Einzelheiten zum Lieferanten, der das Sicherheitsdatenblatt bereitstellt
Muster GmbH
Musterweg 1
12345 Musterstadt
Telefon: +49 555 0142-0
E-Mail: info@muster.example
ABSCHNITT 2: Mögliche Gefahren
2.1 Einstufung des Stoffs oder Gemischs
Skin Irrit. 2, H315
2.2 Kennzeichnungselemente
Signalwort: Achtung
H315 Verursacht Hautreizungen.
P102 Darf nicht in die Hände von Kindern gelangen.
2.3 Sonstige Gefahren
Keine bekannt.
"""
path = Path(tempfile.mkdtemp()) / "sheet.pdf"
with pymupdf.open() as document:
    document.new_page().insert_text((72, 72), text, fontsize=9)
    document.save(path)
```

## Read it

`read_sheet` reads the file, judges what it is and, for a German safety data
sheet, parses it. It takes the path and nothing else: the file is judged by
its content, and its name plays no part.

```python
from sdb_reader import DocumentKind, read_sheet

reading = read_sheet(path)

assert reading.verification.kind is DocumentKind.SAFETY_DATA_SHEET
assert reading.parser_result is not None
assert reading.parser_result.sheet.product_identifier == "Musterreiniger"
```

`read_sheet` does not raise for a file it cannot read or that is something
else; the reading says so.

This sheet's label prints H315 but not the pictogram GHS07 that H315 calls
for. A label that surely lacks what it has to show (a pictogram, the signal
word or a hazard statement its codes call for) is not given: the reading has
the error `label-incomplete` and an empty `hazard_statements`, so that no
program shows a hazardous product without its warnings by mistake.

```python
assert [error.code for error in reading.errors] == ["label-incomplete"]
assert reading.parser_result.sheet.hazard_statements.hazard_codes == []
assert reading.parser_result.sheet.label_withheld == "incomplete"
```

To have such a label as printed, with findings that say what it lacks, ask
for it. The rest of this guide does:

```python
reading = read_sheet(path, accept_incomplete_label=True)
sheet = reading.parser_result.sheet

assert sheet.hazard_statements.hazard_codes == ["H315"]
assert sheet.hazard_statements.signal_word == "Achtung"
```

The label of a sheet of the rules before June 2017 is not read at all
(`label_withheld` is `"before-2017-06"`). [A reading and its parts](reading.md) goes through
what comes back.
