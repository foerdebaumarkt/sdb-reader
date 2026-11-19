# Tools for the tables from the CLP Regulation

Two things in the library are copies of Regulation (EC) No 1272/2008 (CLP):

| In the library | From the regulation |
| --- | --- |
| `src/sdb_reader/clp_statements_de.json`, the German wording of the H, EUH and P statements | Annex III and Annex IV |
| the signal words in `src/sdb_reader/pictograms.py` | the label-element tables of Annex I |

The regulation is amended about once a year. The three tools in this
directory keep the copies in line with it. They are run by hand from the
repository's directory, with its environment (`make venv`); they are not part
of the installed package, and nobody who only reads sheets needs them.

| Tool | What it does |
| --- | --- |
| `fetch_regulation.py` | downloads the consolidated regulation as a PDF from the EU's Publications Office into `data/clp/` |
| `extract_statements.py` | reads the German wording of every H, EUH and P statement from Annex III and IV and rewrites `clp_statements_de.json` |
| `verify_tables.py` | compares the signal words `pictograms.py` derives with the label-element tables of Annex I, category by category, and reports each difference |

```bash
.venv/bin/python tools/clp/fetch_regulation.py --list   # consolidated versions
.venv/bin/python tools/clp/fetch_regulation.py          # the one that applies today, into data/clp/
.venv/bin/python tools/clp/extract_statements.py        # rewrite clp_statements_de.json
.venv/bin/python tools/clp/verify_tables.py             # signal words against Annex I
```

`data/` is not in git: the regulation is 12 MB and is fetched when needed.

## When a new consolidation appears

1. `fetch_regulation.py`. Without `--version` it takes the newest
   consolidation that applies today; one published ahead of its date is
   listed as not yet applicable and has to be named.
2. `extract_statements.py`, then look at `git diff` of the JSON file. Every
   changed wording is a change to what the library gives for a statement:
   raise `PARSER_VERSION`.
3. `verify_tables.py`. It exits with 1 when a signal word
   `pictograms.py` derives differs from the regulation's. It only reports; what the
   table should say goes into a reviewed commit.

## Reading the report of `verify_tables.py`

```text
categories read from the tables        : 77
  the module derives the same word     : 71
  the module derives another           : 0
  word depends on the category         : 6
  ours, not assigned by any table      : 0
categories with 'Kein Piktogramm'      : 4
  the module derives one all the same  : 0
  tables skipped                       : 0
```

The tool compares category by category: a column of a label-element table
holds the hazard statements a category prints together and its signal word,
and the module has to derive that word from those statements. A statement on
its own has no signal word in the regulation. H229 shows why: its table gives
"Gefahr" in category 1 and "Achtung" in categories 2 and 3, but category 1
prints H222 beside it, and the word comes from there.

- **the module derives another** is the line that matters: a signal word the
  library derives that differs from the regulation's. Each one is listed with
  its table, and the tool exits with 1.
- **word depends on the category**: the same statements with two signal
  words, such as H228 in categories 1 and 2. The library holds one answer for
  each; the comment above the table in `pictograms.py` says which and why.
- **ours, not assigned by any table**: statements of the library the tool
  found in no table. Check those by hand.
- **categories with 'Kein Piktogramm'**: the one thing about pictograms the
  text can say. Where the regulation gives a category none and the library
  derives one, it is listed and the tool exits with 1; statements that carry
  a pictogram in another category are listed apart and not judged.
- **tables skipped**: tables whose rows did not line up, or signal words
  whose statements were not found on the next page. Check those by hand.

## What the tools leave to a person

- **Statements that are not one fixed sentence.** `extract_statements.py`
  marks each statement: `fixed`, `parameter` (the supplier fills in "…"),
  `alternatives` (a list to choose from) or `disputed` (the regulation states
  it in two places with different words). Only `fixed` ones are rendered with
  the regulation's wording.
- **Pictograms.** Their row in the Annex I tables holds images, so the text
  cannot say which pictogram a category carries, only that it carries none.
- **Statements with two signal words,** by category: `verify_tables.py`
  lists them.
