# Using the library

For developers who read safety data sheets from a Python program. Whoever
only runs the command needs none of this and reads
[Using the command line](../usage/README.md) instead.

| Page | What it covers |
| --- | --- |
| [Getting started](getting-started.md) | installing the package and reading a first file |
| [A reading and its parts](reading.md) | what `read_sheet` returns, for a sheet and for any other file; a reading as JSON |
| [Messages and catalogs](messages.md) | warnings, errors and findings as codes; sentences in a language of your choice |
| [Judging a sheet](judging.md) | findings, the classification, whether the product needs a sheet |
| [What the regulation expects](expected.md) | the signal word and pictograms a label's codes call for, and where the reading differs |
| [Statements and pictograms](statements.md) | the label's statements with the regulation's wording; pictograms from H codes |
| [Keeping texts](stored-texts.md) | storing the text of a PDF, reading from it again, and the two stage versions |
| [Which sheet is the current one](current-sheet.md) | choosing among several sheets of one product |
| [Embedded data](embedded.md) | the eSDScom file some PDFs carry |
| [The JSON schema](schema.md) | the description of a record, shipped in the package |
| [What is promised](stability.md) | which names, codes and shapes you can build on |

Asking a language model, comparing two runs and the report for people
(`sdb-reader ask`, `diff` and `show`) are features of the command line: the
package exports no names for them, and the modules behind them can change
without notice. They are described in
[Asking a language model](../usage/asking.md),
[Comparing two runs](../usage/comparing-runs.md) and
[Showing sheets as a report](../usage/showing.md).

[How it works](../how-it-works.md) describes the path of a file through the
library. The [reference](../reference.md) lists every exported name with its
signature and description, made from the descriptions in the code.

The Python examples on these pages are run by the test suite. They build on
one another in the order of the table: `path`, `reading` and `sheet` are made
in [Getting started](getting-started.md) and used on the pages after it.
[Which sheet is the current one](current-sheet.md) stands on its own.
