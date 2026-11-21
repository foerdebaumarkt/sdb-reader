# All messages

Every message the program can give, with its code, the values it carries
and its sentence in English. The page is written by `tools/docs/message_pages.py`
from the program's own list; do not edit it by hand. What a message is and
how to choose its language is in [Understanding the output](output.md#messages).

## Reading the text

| Code | Values | Sentence |
| --- | --- | --- |
| `read-by-ocr-no-text-layer` | – | The PDF has no text layer; its pages were read by text recognition, so expect odd spacing. |
| `read-by-ocr-single-characters` | – | The PDF's text layer is split into single characters; its pages were read by text recognition, so expect odd spacing. |
| `pages-read-by-ocr` | `pages` | One page without a text layer was read by text recognition. / {pages} pages without a text layer were read by text recognition. |
| `short-text` | – | The text read is unusually short; the document may be incomplete or scanned. |

## Why no text could be read

| Code | Values | Sentence |
| --- | --- | --- |
| `pdf-not-found` | – | The file does not exist. |
| `pdf-too-large` | `size_bytes`, `limit_bytes` | The file is too large: {size_bytes} bytes, at most {limit_bytes} are read. |
| `pdf-unreadable` | `detail` | The file cannot be opened as a PDF: {detail} |
| `no-text-layer` | `pages` | The PDF has no text layer ({pages} page looked at). / The PDF has no text layer ({pages} pages looked at). |
| `no-text` | `pages`, `extractor` | No text could be read from the PDF ({pages} page looked at, read with {extractor}). / No text could be read from the PDF ({pages} pages looked at, read with {extractor}). |
| `ocr-unavailable` | – | Text recognition is not available: the program tesseract is not installed. Install it with the German language data. |
| `ocr-too-old` | `version`, `minimum` | Text recognition is not available: tesseract {version} is installed, version {minimum} or later is needed. |
| `ocr-language-missing` | `language` | Text recognition is not available: the program tesseract lacks the language data "{language}". |
| `ocr-timeout` | – | Text recognition took too long on a page and was stopped. |
| `ocr-failed` | `detail` | Text recognition failed: {detail} |

## What the file is

| Code | Values | Sentence |
| --- | --- | --- |
| `no-title-keywords` | – | The text names no safety data sheet. |
| `no-section-marker` | – | The text has no section heading such as 'ABSCHNITT 1'. |
| `no-regulation-reference` | – | The text refers to neither the REACH nor the CLP Regulation. |
| `no-hazard-codes-in-text` | – | The text prints no H statement code. |
| `short-sample` | – | The text is short for a safety data sheet; the document may be cut off or scanned. |
| `safety-information` | `sections` | No line carries 'Sicherheitsdatenblatt' as a title; with {sections} of the 16 sections the document is a safety information, not a safety data sheet. |
| `leaflet-title` | – | The document calls itself 'Sicherheitsdatenblatt zum sicheren Umgang mit …' and does not name Regulation (EC) No 1907/2006: a leaflet on an article, not a safety data sheet. |
| `other-language` | – | The document is laid out like a safety data sheet and has no German title: a safety data sheet in another language. |
| `cover-only` | – | The document carries the title of a safety data sheet and none of its sixteen sections: a cover without the sheet. |
| `title-in-running-text` | – | The document names a safety data sheet only in running text; no line carries it as a title. |
| `no-safety-data-sheet` | – | The document has neither the title nor the layout of a safety data sheet. |
| `not-a-sheet` | – | The file is not a German safety data sheet; nothing was parsed. |
| `unreadable` | – | The file's text could not be read; nothing was verified. |

## Reading the sheet

| Code | Values | Sentence |
| --- | --- | --- |
| `line-too-long` | `count`, `length` | {count} lines of more than 2,000 characters were not read, the longest with {length}; a sheet prints no lines that long. |
| `no-label-section` | – | Section 2.2 (Kennzeichnungselemente) was not found; the whole of section 2 was read instead. |
| `several-sheets` | `count` | The file holds {count} safety data sheets; their labels are combined. |
| `classified-before-clp` | `basis` | Section 2 classifies under the directives before CLP ({basis}); no label was read. |
| `label-before-clp` | – | The label (2.2) follows the directives before the CLP Regulation: no H, P or EUH code, but R or S phrases, a hazard symbol or a reference to the EC directives. |
| `no-hazard-codes` | – | The label carries no H statement. |
| `label-undetermined` | – | The label says that the classification was not determined; the sheet states no labelling for the product. |
| `no-precautionary-codes` | – | The label carries no P statement. |
| `euh-wording-outside-label` | `statement`, `sentence` | {statement} is printed only outside the label: {sentence} |
| `signal-word-not-taken` | `signal_word` | The signal word '{signal_word}' was not taken: section 2 says the product is not classified, and the label prints no H statement. |
| `pictograms-derived` | `pictograms` | Pictograms derived from the H statements, the sheet names none: {pictograms} |
| `precautionary-wording-unclear` | `codes` | A precautionary statement without its code fits {codes} alike; none of them was taken. |
| `label-line-unassigned` | `line` | A line of the label was assigned to nothing: {line} |
| `statement-too-long` | `codes` | The statement {codes} is cut off after 100 lines; what follows belongs to no statement. |
| `no-identification-section` | – | Section 1 was not found; the supplier cannot be read. |
| `no-supplier-name` | – | No supplier name was found in section 1. |
| `no-supplier-address` | – | No supplier address was found in section 1. |
| `no-supplier-phone` | – | No supplier telephone number was found in section 1. |
| `no-emergency-phone` | – | No emergency telephone number was found in section 1. |

## Findings

| Code | Values | Sentence |
| --- | --- | --- |
| `wording-deviates` | `statement`, `sheet`, `regulation` | {statement}: the sheet prints '{sheet}', the regulation says '{regulation}'. |
| `undated` | – | The sheet carries no revision or issue date that can be read. |
| `predates-annex-ii` | `revised` | Revised {revised}, before 2021-01-01: the sheet cannot meet Annex II of REACH as amended by Regulation (EU) 2020/878. |
| `revised-in-future` | `revised`, `today` | Revised {revised}, after {today}, the day of the check: the date cannot be right and does not count. |
| `issued-in-future` | `issued`, `today` | Issued {issued}, after {today}, the day of the check: the date cannot be right and does not count. |
| `revision-dates-on-one-line` | `dates` | The sheet names several days behind one revision label ({dates}): none of them counts as the revision date. |
| `classification-undetermined` | – | The label says that the classification was not determined. |
| `old-classification` | – | Section 2 classifies under Directive 67/548/EEC or 1999/45/EC (R phrases, hazard symbols) and carries no CLP label; mixtures have had to be classified under Regulation (EC) No 1272/2008 since 1 June 2015. |
| `old-format` | `revised` | Revised {revised}, but laid out as before Regulation (EU) 2020/878: no endocrine-disrupting properties, no subsection 11.2, no subsection 12.7. |
| `classification-not-stated` | – | Section 2 neither names a hazard class nor says that the product is not classified, and the label carries no H statement, signal word or pictogram. |
| `classification-contradicts-label` | – | Section 2 says the product is not classified, and the label carries an H statement, a signal word or a pictogram: the sheet contradicts itself, or one of the two was read wrongly. |
| `label-not-found` | – | Section 2 classifies the product, and no label (2.2) was found; Annex II of REACH requires it there. |
| `label-without-hazard-statement` | – | Section 2 classifies the product, and no H statement was found in the label; the classification requires its hazard statements on the label (CLP Article 27). |
| `label-without-precautionary-statement` | – | Section 2 classifies the product, and no P statement was found in the label; the classification requires the relevant precautionary statements on the label (CLP Article 22). |
| `hazard-statement-not-in-label` | `statement` | Section 2.1 names {statement} for the classification, and the statement was not found in the label; the classification requires it on the label (CLP Article 27). |
| `signal-word-not-found` | `expected` | The label's codes call for the signal word '{expected}', and none was found (CLP Article 20). |
| `different-products` | `products` | The file holds safety data sheets of different products: {products} |
| `country-editions-differ` | `fields` | The sheets of the same product for different countries differ in: {fields} |
| `euh-outside-label` | `statement`, `sentence` | {statement} is printed only outside the label: {sentence} |
| `not-german` | – | A safety data sheet in another language: for sale in Germany the sheet has to be in German (REACH Article 31(5)). |

## The embedded file

| Code | Values | Sentence |
| --- | --- | --- |
| `embedded-too-large` | `limit_bytes` | The embedded file is larger than {limit_bytes} bytes. |
| `embedded-doctype` | – | The embedded file carries a document type declaration. |
| `embedded-not-xml` | `detail` | The embedded file is not well-formed XML: {detail} |
| `embedded-wrong-root` | `root` | The embedded file is no eSDScom file: its root element is {root}. |
| `embedded-no-datasheet` | – | The embedded file holds no Datasheet element. |

## Asking a language model

| Code | Values | Sentence |
| --- | --- | --- |
| `model-http-error` | `status` | The endpoint answered HTTP {status}. |
| `model-unreachable` | `reason` | The endpoint did not answer: {reason} |
| `model-reply-not-json` | – | The endpoint's reply is no JSON. |
| `model-reply-without-message` | – | The endpoint's reply holds no message. |
| `model-reply-empty` | – | The model's message is empty. |
| `model-answer-unreadable` | `detail` | The model's reply cannot be read as an answer: {detail} |
| `model-not-asked` | – | Not a German safety data sheet: the model is not asked. |

## Lines on the error output

| Code | Values | Sentence |
| --- | --- | --- |
| `cli-file-failed` | `path`, `reason` | [sdb-reader] ERROR: {path}: {reason} |
| `cli-file-broke` | `path`, `error` | [sdb-reader] ERROR: {path}: {error} |
| `cli-no-embedded-file` | `path` | [sdb-reader] {path}: no embedded eSDScom file |
| `cli-embedded-not-handed-out` | `path`, `filename`, `reason` | [sdb-reader] ERROR: {path}: the embedded file '{filename}' is not handed out. {reason} |
| `cli-saved` | `path`, `target` | [sdb-reader] {path}: saved as {target} |
| `cli-half-line-removed` | `output` | [sdb-reader] {output}: the last line was incomplete and is removed; its file is read again. |
| `cli-progress` | `done`, `total`, `failed` | [sdb-reader] {done} of {total} files done, failed: {failed} |
| `cli-interrupted` | `done`, `total` | [sdb-reader] Interrupted after {done} of {total} files. With --output and --resume the same call continues the run. |
| `cli-summary-read` | `files`, `skipped`, `excluded`, `failed` | [sdb-reader] files: {files}; done before: {skipped}; excluded: {excluded}; failed: {failed} |
| `cli-summary-ask` | `files`, `skipped`, `excluded`, `asked`, `failed`, `prompt_tokens`, `completion_tokens` | [sdb-reader] files: {files}; done before: {skipped}; excluded: {excluded}; asked: {asked}; failed: {failed}; tokens sent: {prompt_tokens}, received: {completion_tokens} |

## Comparing two runs

| Code | Values | Sentence |
| --- | --- | --- |
| `diff-run` | `side`, `path`, `kind`, `files` | {side}: {path} ({kind}), files: {files} |
| `diff-files` | `both`, `only_a`, `only_b`, `not_compared` | files in both: {both}; only in A: {only_a}; only in B: {only_b}; not comparable: {not_compared} |
| `diff-differing` | `differing`, `counted_only` | files that differ: {differing}; counted only: {counted_only} |
| `diff-none` | – | No difference. |
| `diff-field` | `field`, `gained`, `lost`, `changed` | {field}: gained {gained}, lost {lost}, changed {changed} |
| `diff-field-counted-only` | `field`, `gained`, `lost`, `changed` | {field}, counted only: gained {gained}, lost {lost}, changed {changed} |
| `diff-stages-differ` | `a`, `b` | [sdb-reader] WARNING: the runs come from different reading stages (A: {a}; B: {b}): differences may come from the text of the PDF files, not from the reading. |
| `diff-models-differ` | `a`, `b` | [sdb-reader] WARNING: the runs asked different models (A: {a}; B: {b}). |
| `diff-questions-differ` | `a`, `b` | [sdb-reader] WARNING: the runs did not ask the same question (A: {a}; B: {b}): the answers are to different questions. |

## The report of show

| Code | Values | Sentence |
| --- | --- | --- |
| `show-kind-sheet` | `sheets` | Safety data sheet, German, 1 sheet / Safety data sheet, German, {sheets} sheets |
| `show-kind-other-language` | – | Safety data sheet in another language |
| `show-kind-safety-information` | – | Safety information, not a safety data sheet |
| `show-kind-document` | – | Not a safety data sheet |
| `show-kind-unreadable` | – | Not readable |
| `show-kind-broke` | – | Reading the file failed with an error; see the error output. |
| `show-cover-page` | – | A cover page stands in front of the sheets; it is not read. |
| `show-cover-page-display` | `term` | A cover page stands in front of the sheets; it names a display: '{term}'. |
| `show-line-cover-page` | – | with a cover page |
| `show-line-cover-page-display` | `term` | with a cover page (display: '{term}') |
| `show-sheet-of` | `number`, `count` | Sheet {number} of {count} |
| `show-whole-file` | – | The file as a whole |
| `show-oldest-revised` | `number`, `date` | Oldest sheet: sheet {number}, revised {date} |
| `show-oldest-issued` | `number`, `date` | Oldest sheet: sheet {number}, issued {date} |
| `show-oldest-none` | – | Oldest sheet: none carries a date |
| `show-label-product` | – | Product |
| `show-label-supplier` | – | Supplier |
| `show-label-contact` | – | Contact |
| `show-label-emergency` | – | Emergency |
| `show-label-revised` | – | Revised |
| `show-label-issued` | – | Issued |
| `show-label-labelling` | – | Labelling |
| `show-label-notes` | – | Notes |
| `show-date` | `date` | {date} |
| `show-information-email` | `email` | information: {email} |
| `show-product-dated` | `product`, `dated` | {product} ({dated}) |
| `show-with-version` | `value`, `version` | {value} (version {version}) |
| `show-not-stated` | – | not stated |
| `show-no-labelling` | – | none |
| `show-no-signal-word` | – | no signal word |
| `show-no-pictograms` | – | no pictograms |
| `show-no-statements` | – | no H, P or EUH statements |
| `show-needs-sheet` | – | Needs a safety data sheet: yes |
| `show-needs-no-sheet` | – | Needs a safety data sheet: no |
| `show-stated-voluntary` | – | The sheet calls itself voluntary or not prescribed. |
| `show-stated-article` | – | The sheet calls its product an article. |
| `show-no-notes` | – | none |
| `show-no-product` | – | product not stated |
| `show-undated` | – | undated |
| `show-notes` | `notes` | 1 note / {notes} notes |
| `show-summary` | `files`, `sheets`, `others`, `failed`, `with_notes`, `excluded` | files: {files}; safety data sheets: {sheets}; other documents: {others}; not readable: {failed}; with notes: {with_notes}; excluded: {excluded} |
| `show-interrupted` | `done`, `total` | [sdb-reader] Interrupted after {done} of {total} files. |

## From stored texts of earlier versions

| Code | Values | Sentence |
| --- | --- | --- |
| `unknown` | `text` | {text} |
