<!-- The start page of the documentation site (make docs). On GitHub the
     entry is README.md beside this file; the blocks below are the site's
     navigation. -->

# sdb-reader

*German safety data sheets, read by written rules: the same file gives the
same result, every time.*

`sdb-reader` reads safety data sheets (Sicherheitsdatenblätter) under REACH
and CLP from PDF files, without a language model. For each file it says what
the file is and, for a German sheet, what it states: the product and its
supplier, the classification, the label with its H, P and EUH statements,
the dates, and what is wrong with the sheet as a document.

```bash
uv tool install sdb-reader
sdb-reader show sheet.pdf
```

## Für Anwender · For operators

You run the command and read what it prints. No programming needed.

| | |
| --- | --- |
| **[Bedienung](bedienung/README.md)** (Deutsch) | [Installation](bedienung/installation.md) · [Blätter lesen](bedienung/lesen.md) · [als Bericht anzeigen](bedienung/anzeigen.md) · [die Ausgabe verstehen](bedienung/ausgabe.md) · [alle Meldungen](bedienung/meldungen.md) |
| **[Using the command line](usage/README.md)** (English) | [Installing](usage/installing.md) · [Reading sheets](usage/reading.md) · [as a report](usage/showing.md) · [Understanding the output](usage/output.md) · [All messages](usage/messages.md) |

The manual has the same pages in both languages.

## For developers

You read sheets from a Python program, or you want to change the reader.

| | |
| --- | --- |
| **[Using the library](api/README.md)** | [Getting started](api/getting-started.md) · [A reading and its parts](api/reading.md) · [Judging a sheet](api/judging.md) · [What is promised](api/stability.md) |
| **[Reference](reference.md)** | every exported name with its signature and description |
| **[Contributing](contributing/README.md)** | [Setting up](contributing/setup.md) · [Changes and the specs](contributing/changes-and-specs.md) · [Releasing](contributing/releasing.md) |

## Background

| | |
| --- | --- |
| **[How it works](how-it-works.md)** | the path of a file through the library on one page, with the rules that govern each step |
| **[Changelog](changelog.md)** | what each version changed for its users |
| **[specs/](../specs/README.md)** | the binding rules, in German, in the repository |

These pages describe the version named at the top. "Other versions" in the
navigation lists the others.

```{toctree}
:hidden:
:caption: Bedienung (Deutsch)

bedienung/README
bedienung/installation
bedienung/lesen
bedienung/anzeigen
bedienung/bestand
bedienung/ausgabe
bedienung/eingebettete-datei
bedienung/fragen
bedienung/laeufe-vergleichen
bedienung/meldungen
bedienung/fehlerbehebung
```

```{toctree}
:hidden:
:caption: Using the command line

usage/README
usage/installing
usage/reading
usage/showing
usage/collection
usage/output
usage/embedded-file
usage/asking
usage/comparing-runs
usage/messages
usage/troubleshooting
```

```{toctree}
:hidden:
:caption: Using the library

api/README
api/getting-started
api/reading
api/messages
api/judging
api/statements
api/stored-texts
api/current-sheet
api/embedded
api/schema
api/stability
reference
```

```{toctree}
:hidden:
:caption: Background

how-it-works
changelog
```

```{toctree}
:hidden:
:caption: Contributing

contributing/README
contributing/setup
contributing/changes-and-specs
contributing/stage-versions
contributing/measuring
contributing/adding-a-language
contributing/ci-cd
contributing/releasing
contributing/editor-agnostic
```
