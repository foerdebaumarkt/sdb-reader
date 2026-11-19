# Showing sheets as a report

`show` reads files exactly like [`read`](reading.md) and prints what it found
as a report to read, not as JSON. Use it when you want to look at a sheet
yourself. A program that works with the result takes `read`.

## One file, several files, a folder

```bash
sdb-reader show sheet.pdf
sdb-reader show sheet.pdf other.pdf
sdb-reader show folder/
sdb-reader show folder/ folder/sheet.pdf
```

A file you name gets the full report. A folder gets one line for each PDF in
it and its subfolders. Files and folders can be mixed: a file that is named
itself and also lies in a folder you give gets the full report. Where the
call has more than one file, a closing line counts them.

## The report of one file

```text
musterlack.pdf
  Sicherheitsdatenblatt, deutsch, 1 Blatt

  Produkt        Musterlack seidenmatt
  Lieferant      Nordwerk GmbH, Hafenstraße 1, 24000 Musterstadt
  Kontakt        +49 30 0000000, info@nordwerk.example
  Notruf         Giftnotruf: +49 30 19240
  Überarbeitet   12.03.2019 (Version 4.1)

  Kennzeichnung  Achtung · GHS07
    H317  Kann allergische Hautreaktionen verursachen.
    P280  Schutzhandschuhe tragen.
    EUH208  Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.

  Braucht ein Sicherheitsdatenblatt: ja

  Hinweise
    - Überarbeitet am 12.03.2019, vor dem 01.01.2021: Das Blatt kann Anhang II der REACH-Verordnung in der Fassung der Verordnung (EU) 2020/878 nicht erfüllen.
```

From top to bottom:

| Part | What it says |
| --- | --- |
| first line | the file, as you named it |
| second line | what the file is; for a German safety data sheet, how many sheets it holds |
| `Produkt`, `Lieferant` | the product name, and the supplier's name and address, as the sheet prints them |
| `Kontakt` | the supplier's telephone number and e-mail address. Where the sheet names another address for the office that gives information, it follows as `Auskunft: …` |
| `Notruf` | the emergency number, as the sheet prints it |
| `Überarbeitet` | the revision date and, in brackets, the sheet's version. A sheet that gives only an issue date shows that under `Ausgegeben` |
| `Kennzeichnung` | the signal word and the pictograms, and below them every H, P and EUH statement of the label with the sheet's wording. Where the sheet prints a code without words, the regulation's wording stands |
| `Braucht ein Sicherheitsdatenblatt` | whether the product needs a safety data sheet by its classification and label. A line below says so where the sheet calls itself voluntary or its product an article |
| `Hinweise` | what is wrong with the sheet as a document, and what the program noted while reading it; `keine` where there is nothing |

What the sheet does not state is shown as `nicht genannt`. A sheet without
any label shows `keine` after `Kennzeichnung`; the notes that would only say
the same again (no H statement, no P statement) are then left out. `read`
still gives them.

The sentences under `Hinweise` are the messages of `read`:
[All messages](messages.md) lists them. The doubts the program had while
deciding that the file is a sheet, and the data some PDFs carry embedded, are
not in the report. `read` has both.

## A file with several sheets

```text
set.pdf
  Sicherheitsdatenblatt, deutsch, 2 Blätter
  Vor den Blättern steht ein Deckblatt; es wird nicht gelesen.

  Blatt 1 von 2
    Produkt        Musterkleber Komponente A
    …

  Blatt 2 von 2
    Produkt        Musterkleber Komponente B
    …

  Die Datei als Ganzes
    Braucht ein Sicherheitsdatenblatt: ja

    Hinweise
      - Die Datei enthält 2 Sicherheitsdatenblätter; ihre Kennzeichnungen sind zusammengeführt.
```

Each sheet is shown on its own, in the order of the file, with the notes
that belong to it. The last block is about the file: whether the product
needs a sheet when all sheets are taken together, and the notes that compare
the sheets or concern the file. A cover page in front of the sheets is named
and not read; if it names a display, the word is shown.

## A file that is no sheet

```text
prospekt.pdf
  Kein Sicherheitsdatenblatt
    - Das Dokument hat weder den Titel noch den Aufbau eines Sicherheitsdatenblatts.
```

The report says what the file is and why. A file no text could be read from
is shown as `Nicht lesbar` with the reason.

## A folder

```text
ordner/leer.pdf: Nicht lesbar
ordner/musterlack.pdf: Sicherheitsdatenblatt, deutsch, 1 Blatt · Musterlack seidenmatt · 12.03.2019 · 1 Hinweis
ordner/prospekt.pdf: Kein Sicherheitsdatenblatt
ordner/set.pdf: Sicherheitsdatenblatt, deutsch, 2 Blätter · mit Deckblatt · Musterkleber Komponente A (04.05.2023); Musterkleber Komponente B (02.03.2022) · 3 Hinweise

Dateien: 4; Sicherheitsdatenblätter: 2; andere Dokumente: 1; nicht lesbar: 1; mit Hinweisen: 2; ausgenommen: 0
```

A line gives the file, what it is and, for a German safety data sheet, the
product, the date and how many notes its full report has. A file that holds
several sheets names each of them, in the file's order and parted by
semicolons, with its date in brackets, and says before them whether a cover
page stands in front. To see the notes, name the file itself.

## Options

| Option | Effect |
| --- | --- |
| `--max-pages N` | read only the first N pages of each file; without it, all pages |
| `--jobs N` | work on N files at once; the reports stay in the order given |
| `--exclude-from FILE` | leave out the files FILE names, see [Reading a whole collection](collection.md#leaving-files-out) |
| `--lang de` or `--lang en` | language of the report; German unless you say otherwise |
| `--messages FILE` | take the words of the report from a file of your own |

The last two are explained under
[Understanding the output](output.md#messages). The names, the signal word
and the statements of a sheet are never translated: they stand as the sheet
prints them.

`show` writes no file and continues no run: `--output`, `--resume`,
`--indent` and `--include-raw-text` belong to `read`.

## Exit codes and error output

The exit codes are those of [`read`](reading.md#exit-codes): 0 when every
file was read, 1 when at least one could not be, 2 when the call cannot run,
130 after Ctrl-C. A file that is no safety data sheet is not a failure.

The report goes to the standard output. A file no text can be read from
stands in the report with its reason. Only a file that breaks the program is
also named on the error output, with the error.

## The text can change

The report is written for people. Its wording and layout can change with any
version, and nothing should be built on them. Whatever a script needs is in
the result of `read`, which is described by a schema and kept stable.
