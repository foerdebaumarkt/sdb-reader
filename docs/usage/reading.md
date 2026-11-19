# Reading sheets

## One file, several files, a folder

```bash
sdb-reader read sheet.pdf
sdb-reader read sheet.pdf other.pdf
sdb-reader read folder/ > result.json
```

`read` takes one or more PDF files; a folder stands for every PDF in it and
its subfolders. It prints one result, as JSON, with one
record per file in the order given. JSON is a text format programs can read;
a text editor or a browser shows it too. With `>` the result goes into a file
instead of the screen.

Each file is judged by its content alone. Its name plays no part.

To read the result yourself, [`show`](showing.md) prints the same as a
report instead of JSON.

## Options

| Option | Effect |
| --- | --- |
| `--max-pages N` | read only the first N pages of each file; without it, all pages |
| `--include-raw-text` | add the text read from each PDF to the result |
| `--indent N` | spaces of indentation in the JSON, 2 unless you say otherwise; `0` prints the whole result on one line |
| `--output FILE`, `--resume`, `--jobs N`, `--exclude-from FILE` | for a run over many files, see [Reading a whole collection](collection.md) |
| `--lang de` or `--lang en` | language of the messages; German unless you say otherwise |
| `--messages FILE` | take the sentences of the messages from a file of your own |

The last two are explained under
[Understanding the output](output.md#messages).

## What comes back

For a sheet the record looks like this, shortened:

```json
[
  {
    "file": {"path": "/data/reiniger.pdf", "filename": "reiniger.pdf", "size_bytes": 1385},
    "verification": {"kind": "safety-data-sheet"},
    "extraction": {"extractor": "pymupdf", "pages_sampled": 1},
    "sheet": {
      "product_identifier": "Musterreiniger",
      "revision_date": "2019-05-02",
      "version": "3.1",
      "stated_classification": "classified",
      "stated_voluntary": false,
      "stated_article": false,
      "sheet_required": true,
      "hazard_statements": {
        "signal_word": "Achtung",
        "pictograms": ["GHS07"],
        "hazard_codes": ["H315"],
        "precautionary_codes": ["P102"]
      },
      "contact_info": {"supplier_name": "Muster GmbH"}
    },
    "statements": [
      {
        "code": "P102",
        "sheet": "Darf nicht in Kinderhände gelangen.",
        "regulation": "Darf nicht in die Hände von Kindern gelangen."
      }
    ],
    "findings": [
      {
        "code": "predates-annex-ii",
        "params": {"revised": "2019-05-02"},
        "message": "Überarbeitet am 2019-05-02, vor dem 01.01.2021: Das Blatt kann Anhang II der REACH-Verordnung in der Fassung der Verordnung (EU) 2020/878 nicht erfüllen."
      }
    ]
  }
]
```

[Understanding the output](output.md) explains every part.

## Exit codes

A program that ends leaves a number behind, its exit code. A script can test
it; on the command line `echo $?` shows the last one.

| Exit code | Meaning |
| --- | --- |
| 0 | every file was read |
| 1 | at least one file could not be read; it and the others are in the result, and each failure is named on the error output |
| 2 | a path is neither a file nor a folder, a folder holds no PDF, an option is wrong, or there is no catalog for the language asked for; nothing was read |
| 130 | the run was interrupted with Ctrl-C |

A file that is not a safety data sheet is not a failure. It gets a record
that says what it is, and the exit code stays 0.

A file no text can be read from, such as an empty scan or a file that is not
a PDF, is a failure. It is still in the result, with the reason:

```text
[sdb-reader] FEHLER: leer.pdf: Aus dem PDF ließ sich kein Text lesen (1 Seite angesehen, gelesen mit pymupdf+ocr).
```

## Result and error output

The result goes to the standard output and nothing else does. Lines about
failures, and notes the program writes while reading, go to the error output.
So `> result.json` always gives a clean result file, and the failures stay on
the screen.
