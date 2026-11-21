# When something does not work

## The command

| What you see | Why | What to do |
| --- | --- | --- |
| `command not found: sdb-reader` | the command is not on your path | start it with its full path, or install it with `uv tool install` as under [Installing](installing.md) |
| `error: not a file or directory: …` and exit code 2 | a path does not exist | check the path |
| `error: no PDF file under: …` and exit code 2 | the folder holds no PDF | check the folder; files ending in `.pdf` are read |
| `error: … exists; give another file, or --resume to continue it` | the result file exists already | name another file, or continue the run with `--resume` |
| `error: no message catalog for '…'` | there are sentences for `de` and `en` only | use one of the two, or a file of your own with `--messages` |
| `error: ask needs an endpoint and a model` | `ask` was started without them | give `--endpoint` and `--model`, or set the two variables |
| the result is mixed with other lines | result and error output both go to the screen | write the result to a file with `> result.json` |

## A file is not read

| What you see | Why | What to do |
| --- | --- | --- |
| `errors` carries `ocr-too-old` | the installed `tesseract` is older than version 5 | install version 5 or later; the message names the version found |
| `errors` carries `ocr-language-missing` | `tesseract` is installed without the German language data | install the data, see [Installing](installing.md) |
| `errors` carries `ocr-unavailable` | the pages are pictures and `tesseract` is not installed | install it with the German language data, see [Installing](installing.md) |
| `errors` carries `no-text` | the pages are pictures and text recognition read nothing | look at the file: an empty or badly scanned page cannot be read |
| `errors` carries `pdf-unreadable` | the file is not a PDF, or it is damaged | open it in a PDF viewer; get the file again |
| `errors` carries `pdf-too-large` | the file is larger than the program reads | the message names the size and the limit; such a file is rarely a single safety data sheet, so look at what it holds |
| `errors` carries `ocr-timeout` | text recognition took too long on a page | try again; a very large scan may not be readable |

## The file is not what you expected

| What you see | Why | What to do |
| --- | --- | --- |
| `kind` is `safety-data-sheet-other-language` | the sheet is not in German | only German sheets are read; ask the supplier for the German sheet |
| `kind` is `safety-information` | the file has the sections of a sheet but does not call itself a safety data sheet | it is none; suppliers issue these for products that need no sheet |
| `kind` is `document` for a file you know is a sheet | the title or the sections were not recognised | read `verification.warnings`; a scan read by text recognition may have lost its title |

## A value is missing or wrong

| What you see | Why | What to do |
| --- | --- | --- |
| a field is empty although the sheet prints it | the value was not found in this layout | read `parser.warnings` and the `section_text` of the section; report the layout |
| `countries` is empty | the sheet names no country | it counts as a sheet for your country |
| `pictograms` although the sheet names none | they follow from the hazard statements | `parser.warnings` says so with `pictograms-derived` |
| `signal_word` is empty although the sheet carries H statements | the sheet prints no signal word, or it was not found | `expected_signal_word` names the one the codes call for, and `findings` reports `signal-word-not-found` |
| a value is missing on a sheet set as a form in two columns without colons | outside section 1 such rows are read as a table, and a label and its value can stand apart | a known limit; check `section_text` |
| the message `short-text` or `short-sample` | the file has little text for a sheet | it may be cut off or partly scanned; look at the file |
| the finding `wording-deviates` on a statement that looks right | the sheet's wording differs from the regulation's in a word | compare the two wordings in the finding's values |

## Reporting a problem

Say which version you use (`sdb-reader --version` shows it),
what you ran, and what you expected. Do not attach a supplier's sheet to a public report unless you
may pass it on; describe the layout instead, or make a small example.
