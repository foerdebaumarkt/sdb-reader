# Asking a language model

## What it is for

`read` never asks a language model. `ask` does: it sends the beginning of
each sheet to a model, asks what the sheet says, and keeps the answer, one
record per file. It compares nothing. Setting the answers beside a reading
is a step of its own, see [Comparing two runs](comparing-runs.md).

The model's answer is a second opinion to look at. It never changes a
reading, and where the two differ is a place to look, not a proven error.
Models make mistakes, and often the model is the one that is wrong.

The model is asked on its own. It gets the text of the file, not what the
program read from it, so it can also see what the program cut away or read
wrongly.

## What is sent where

**The text of the sheet is sent to the address you name.** If that is a
service on the internet, the text leaves your machine. A model that runs on
your own machine keeps it there.

Sent is the text of the file from its beginning up to the heading of
section 3, where the list of ingredients begins: the header of the first
page, section 1 with the supplier, and section 2 with the label. The
statements of single ingredients in section 3 are not the label's, so the
text ends before them. Where a file has no such heading, its first pages are
sent instead, four unless you say otherwise.

Where a file holds several sheets, each is sent on its own, see
[Several sheets in one file](#several-sheets-in-one-file).

Only a file the program judges a German safety data sheet is sent. Nothing
is sent for any other file or for a file without text.

The address has to speak the chat interface that OpenAI introduced and most
local programs and services offer.

## Running it

```bash
sdb-reader ask --endpoint http://localhost:11434/v1 --model some-model sheet.pdf
sdb-reader ask sheets/ --output answers.jsonl --jobs 4 --retries 3
```

| Option | Effect |
| --- | --- |
| `--endpoint ADDRESS` | where the model is asked; needed |
| `--model NAME` | the model's name at that address; needed |
| `--pages N` | how many pages of the PDF the model gets where the file has no heading of section 3; 4 unless you say otherwise |
| `--timeout SECONDS` | how long to wait for an answer; 300 unless you say otherwise |
| `--retries N` | send a request again up to N times when the service is busy or briefly out of reach, after a growing wait of at most a minute; 0 unless you say otherwise |
| `--preset NAME` | a preset for a known model family, see [Switching reasoning off](#switching-reasoning-off) |
| `--presets FILE` | take the presets from a TOML file of your own instead of the program's |
| `--list-presets` | print the presets and end; needs neither a file nor an endpoint |
| `--request-json JSON` | a JSON object whose fields go into every request, for what a service needs beyond the usual, such as `'{"seed": 7}'`; it goes on top of a preset and may set the temperature, which is 0 otherwise, but not `model` or `messages` |
| `--output FILE`, `--resume`, `--jobs N`, `--exclude-from FILE` | for a run over many files, see [Reading a whole collection](collection.md) |
| `--indent N`, `--lang`, `--messages` | as for `read` |

Five environment variables stand in for options or carry what must not be
on the command line:

| Variable | Stands for |
| --- | --- |
| `SDB_READER_ENDPOINT` | `--endpoint` |
| `SDB_READER_MODEL` | `--model` |
| `SDB_READER_PRESET` | `--preset` |
| `SDB_READER_REQUEST_JSON` | `--request-json` |
| `SDB_READER_API_KEY` | the key a service asks for; it is read from here and from nowhere else, so that it does not end up in the history of your command line or in a record |

Each sheet costs one request; a file with several sheets costs as many as
it holds sheets. A request that fails is not repeated, unless
you give `--retries`; any failure that does not pass by itself, such as a
wrong key, fails at once.

## What comes back

```json
[
  {
    "file": {"path": "/data/reiniger.pdf", "filename": "reiniger.pdf", "size_bytes": 181034},
    "kind": "safety-data-sheet",
    "asked": true,
    "model": "some-model",
    "sheet_count": 1,
    "sent": "before-section-3",
    "stage": "2+pymupdf-2.1",
    "question": "5f0c1d9a2b7e",
    "usage": {"prompt_tokens": 1210, "completion_tokens": 190},
    "reading": {
      "revision_date": "2022-07-20",
      "revision_date_named": "20.07.2022",
      "hazard_statements": {
        "hazard_codes": ["H315", "H319"],
        "precautionary_codes": ["P102", "P305+P351+P338"],
        "supplemental_codes": [],
        "hazard_text": "H315: Verursacht Hautreizungen.\nH319: Verursacht schwere Augenreizung.",
        "precautionary_text": "P102: Darf nicht in die Hände von Kindern gelangen.\nP305+P351+P338: BEI KONTAKT MIT DEN AUGEN: …",
        "supplemental_text": null
      },
      "contact_info": {
        "supplier_name": "Muster GmbH",
        "supplier_address": "Musterweg 1, 12345 Musterstadt",
        "supplier_phone": "0555-0142-0",
        "supplier_email": "info@muster.example",
        "supplier_website": null
      }
    },
    "answer": {"supplier": {"name": "Muster GmbH"}, "revision_date": "20.07.2022"}
  }
]
```

| Field | Meaning |
| --- | --- |
| `kind` | what the file is, as `read` judges it |
| `asked` | `true` if the model was asked; `false` for a file that is no German safety data sheet or has no text, with the `reason` as a message and nothing else |
| `model` | the model's name |
| `sheet_count` | how many sheets the file holds; nearly always 1 |
| `sent` | what the model got: `before-section-3` for the text up to the heading of section 3, `pages` for the first pages of the file; with several sheets `sheet` where one went whole |
| `stage` | the reading stage the text comes from; two runs of different stages may have been sent different text |
| `question` | a fingerprint of the question, which is the same for every file; answers with another fingerprint were given to another wording of the question |
| `preset` | the preset's name, where one was chosen |
| `request` | the fields added to the request: the preset's, with those of `--request-json` on top, where there were any |
| `usage` | how many tokens the requests about this file cost, where the service says |
| `reading` | the answer under the names `read` uses for a sheet, see [Understanding the output](output.md): the codes and texts of the H, P and EUH statements, the supplier, the date of revision |
| `answer` | the model's answer as it gave it; only for a file that is one sheet |
| `parts` | only for a file with several sheets: for each sheet, what was sent and what the model said about it |

The model is not asked for the signal word, the pictograms or the
classification; `reading` holds only what it is asked for. The form of a
record is laid down in a schema that ships with the program,
`sdb_reader/ask_record.schema.json`.

## Several sheets in one file

Some files hold several complete sheets one after another, such as those
for the two parts of a two-component adhesive. `ask` then asks about each
sheet on its own, with that sheet's text up to its own heading of
section 3; a sheet that has none is sent whole. Where a sheet begins is
decided by the same rule as in `read`: both count the same number of sheets
for every file, and a later sheet begins at the title above its section 1,
so the model sees the header of its first page. A cover page in front of
the sheets is never sent, also where only one sheet stands behind it.

The record then holds both, each sheet by itself and all of them united:

```json
{
  "sheet_count": 2,
  "sent": "before-section-3",
  "usage": {"prompt_tokens": 2300, "completion_tokens": 410},
  "reading": {"hazard_statements": {"hazard_codes": ["H315", "H318"]}},
  "parts": [
    {
      "sent": "before-section-3",
      "usage": {"prompt_tokens": 1200, "completion_tokens": 190},
      "reading": {"hazard_statements": {"hazard_codes": ["H315"]}},
      "answer": {"hazard_statements": "H315: Verursacht Hautreizungen."}
    },
    {
      "sent": "before-section-3",
      "usage": {"prompt_tokens": 1100, "completion_tokens": 220},
      "reading": {"hazard_statements": {"hazard_codes": ["H318"]}},
      "answer": {"hazard_statements": "H318: Verursacht schwere Augenschäden."}
    }
  ]
}
```

- `parts` holds for each sheet, in the file's order, what was sent
  (`sent`), what it cost (`usage`), the answer (`answer`) and the answer in
  the form of a reading (`reading`). The example is shortened; every
  `reading` has all its fields.
- `reading` at the top unites the sheets the way `read` does for such a
  file: the codes of all sheets, each once, in the order they first appear,
  and the statements one after the other, each on its line. Supplier and revision date are the
  first sheet's.
- `usage` at the top is the sum, `sent` is `sheet` as soon as one sheet
  went whole, and there is no `answer` there.
- If the request about one of the sheets fails, the whole file has failed
  and gets no record.

`diff` compares the united `reading`.

## Switching reasoning off

Some models reason before they answer. For this task that buys nothing: the
model is to copy from the page, not to deduce. In a run over 3,000 sheets,
asking without reasoning cost a third and took a quarter of the time, and
the model made fewer errors of its own. How reasoning is switched off
differs from service to service. For the model families the program knows,
it ships the fields needed as a preset:

```bash
sdb-reader ask --preset deepseek-no-reasoning sheets/ --output answers.jsonl
sdb-reader ask --list-presets
```

<!-- presets:begin -->
| Name | What for | What goes into the request | Measured with |
| --- | --- | --- | --- |
| `deepseek-no-reasoning` | DeepSeek: switch the model's reasoning off | `{"thinking": {"type": "disabled"}}` | `deepseek-flash`, 2026-11-18 |
| `ollama-no-reasoning` | Ollama: switch the reasoning of a reasoning model off | `{"reasoning_effort": "none"}` | `qwen3.8:27b-mlx`, 2026-11-18 |
<!-- presets:end -->

A preset can go out of date: a service can change what it takes. The
column "Measured with" names the model and the day the preset was measured
with this program; "not measured" means it is written from the service's
documentation. Whether reasoning is really off shows in `usage`: a model
that reasons sends back many times the tokens.

For another model, name the fields yourself with `--request-json`, or write
a file of your own and give it with `--presets`. It has one table per
preset:

```toml
[my-service]
description = "My service: no reasoning"
request = { reasoning = false }
omit = ["temperature"]
```

`request` names the fields that go into every request, `omit` those that
are left out; only `temperature` can be left out, for a service that takes
none. `--request-json` goes on top of the preset.

## The date

The model has to name the date of revision exactly as the sheet prints it,
and what it names counts only if that text stands in what it was sent and is
a date. So it cannot make a date up. `revision_date` holds a date that
counts; `revision_date_named` holds what the model wrote, also where it did
not count.

## Keeping the answers

A request costs time and, with a service, money. A comparison costs
neither. So ask once, keep the file, and compare as often as you like:

```bash
sdb-reader ask sheets/ --output answers.jsonl --jobs 4 --retries 3
sdb-reader ask sheets/ --output answers.jsonl --jobs 4 --retries 3 --resume
```

- The second call continues a run that was broken off and asks about no
  sheet twice.
- The same answers serve every later version of the program: read the
  sheets again and compare, without asking again.
- A model does not give the same answer twice. Answers of several runs, or
  of several models, each in a file of its own, can be compared with each
  other, and what two of them say alike weighs more.

For a run over more than one file the line at the end adds up what was
asked and what it cost:

```text
[sdb-reader] Dateien: 5000; früher erledigt: 0; ausgenommen: 500; gefragt: 4300; gescheitert: 3; Token gesendet: 5200000, empfangen: 1050000
```

What that is in money the command does not work out; the service names its
prices. A trial over a hundred sheets shows what a sheet costs on average
and how long it takes, before the whole collection runs.

## What it was tested with

Asking has been measured with DeepSeek V4 Flash (`deepseek-flash`), at the
provider through its interface, in a run over 3,000 sheets with eight
requests at once:

| Reasoning | Tokens per sheet, sent | Tokens per sheet, received | Time for 3,000 sheets |
| --- | --- | --- | --- |
| off (`--preset deepseek-no-reasoning`) | about 2,100 | about 250 | 18 minutes |
| on | about 2,200 | about 2,000 | 72 minutes |

On a machine of your own it has been measured with Qwen 3.8
(`qwen3.8:27b-mlx`) under Ollama, on ten sheets one after the other, with
`--preset ollama-no-reasoning`: about 2,100 tokens sent and about 260
received per sheet, four seconds per sheet on a machine with an Apple chip.
Its answers differed from those of DeepSeek V4 Flash on none of the ten
sheets.

A model has to read German text, give plain JSON when told to, and take in a
few thousand words. Smaller models are not tested; whether one
will do shows in a trial with sheets whose content you know.

## A sheet cannot give the model orders

A sheet is a file from somebody else, and its text goes to the model. So that
a text in it does not count as an instruction, it stands between two markers
with an id that is made anew for each request and that the sheet cannot know,
and the instructions tell the model that everything between them is a
document. What matters more is what an answer can do: nothing but be kept
and compared. It changes no reading, starts no action, and a date counts
only if it stands in the sheet.

## Exit codes

| Exit code | Meaning |
| --- | --- |
| 0 | every request was answered |
| 1 | a request failed or a file has no text; it is named on the error output, the others are in the result |
| 2 | endpoint or model is missing, `--request-json` is no JSON object or names `model` or `messages`, there is no such preset, or a path is neither a file nor a folder; nothing was read |
| 130 | the run was interrupted with Ctrl-C |
