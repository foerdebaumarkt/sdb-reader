# Which sheet is the current one

A product rarely has one safety data sheet. A supplier revises it, issues it
again for other countries, and whoever collects the files ends up with several
per product. `current_state` answers which of them counts today.

This page describes the problem, what the function decides, and how to use it.
The binding rules are BIB-6 to BIB-9 in
[specs/bibliothek.md](../../specs/bibliothek.md) (German).

## The problem

Take the files one product has collected over the years:

| File | Revised | Version | Issued for |
| --- | --- | --- | --- |
| a | 2021-04-08 | 1 | DE |
| b | 2021-04-08 | 1 | AT |
| c | 2022-07-20 | 2 | DE |
| d | 2022-07-20 | 2 | AT |
| e | 2023-07-10 | 2 | CH |

Someone selling the product in Germany needs sheet c. Three obvious ways of
finding it go wrong:

- **The newest date** picks e, the Swiss sheet. The supplier keeps one line of
  sheets per country and issued version 2 for Switzerland a year after the
  German one. Sheet e replaces the Swiss version 1, not sheet c.
- **The highest version** fails on other products. Version counters belong to
  one supplier and one line of sheets, and they restart: a sheet numbered 6.00
  from 2019 can sit beside one numbered 1.05 from 2025. Version first picks
  the old one.
- **The last file** is whatever order the files happen to have.

And one case must not be smoothed over. If the files were

| File | Revised | Version | Issued for |
| --- | --- | --- | --- |
| a | 2021-04-08 | 1 | DE |
| e | 2023-07-10 | 2 | CH |

then a German version 2 probably exists and is missing from the collection.
Falling back to sheet a would hide that. The caller has to learn about it.

## What the function decides

It takes what each sheet says about its own state and returns the position of
the current one, with the reason.

1. The newest revision date leads. It is the one signal that means the same
   on every sheet.
2. Among sheets of one date, a sheet for the wanted country comes first, then
   the higher version, then the newer issue date, then the later one given.
3. If the sheet chosen so far is issued for other countries only, the best
   sheet for the wanted country takes its place when both carry a readable
   version and its own is not lower.

Some details of the comparison:

- A missing date counts as the oldest.
- A version is read as numbers between dots, so 2.10 is above 2.9. A missing
  version, or one that is not made of numbers, counts as the lowest and never
  lets a sheet stand in for another under step 3.
- A sheet that names no country counts as one for the wanted country.

## The answer

`current_state` returns a `Choice` with `index`, `reason` and `instead_of`.

| `reason` | Meaning | What a caller usually does |
| --- | --- | --- |
| `ChoiceReason.NEWEST` | The sheet at `index` is first in the order and fits the wanted country. | Use it. |
| `ChoiceReason.STANDS_IN` | The sheet at `index` is for the wanted country. A newer sheet for another country, at `instead_of`, is not ahead of it in version. | Use it. The other sheet is no reason for concern. |
| `ChoiceReason.OTHER_COUNTRY` | The sheet at `index` is for other countries only, and no sheet for the wanted country can take its place. | Treat the wanted country's sheet as missing: ask the supplier, report it, or hold the product back. |

The function only reports. Whether a missing sheet stops a sale is the
caller's rule.

## How to use it

### With plain data

Build one `SheetState` per sheet, in any order, and pass the country you sell
in. Positions in the answer refer to the sequence you passed.

```python
from datetime import date

from sdb_reader import Choice, ChoiceReason, SheetState, current_state

states = [
    SheetState(date(2021, 4, 8), version="1", countries=("DE",)),
    SheetState(date(2021, 4, 8), version="1", countries=("AT",)),
    SheetState(date(2022, 7, 20), version="2", countries=("DE",)),
    SheetState(date(2022, 7, 20), version="2", countries=("AT",)),
    SheetState(date(2023, 7, 10), version="2", countries=("CH",)),
]

choice = current_state(states, country="DE")
assert choice == Choice(index=2, reason=ChoiceReason.STANDS_IN, instead_of=4)
```

The same files for someone selling in Switzerland:

```python
assert current_state(states, country="CH") == Choice(4, ChoiceReason.NEWEST)
```

The second table above, where the German version 2 is missing:

```python
incomplete = [
    SheetState(date(2021, 4, 8), version="1", countries=("DE",)),
    SheetState(date(2023, 7, 10), version="2", countries=("CH",)),
]

choice = current_state(incomplete, country="DE")
assert choice == Choice(1, ChoiceReason.OTHER_COUNTRY)
```

### With sheets read by this library

A sheet read by `read_sheet` carries the same four values. The function does
not take the sheet itself, so that it also works on data from elsewhere; the
conversion is one line per field.

```python
from pathlib import Path

from sdb_reader import DocumentKind, SafetyDataSheet, read_sheet


def state_of(sheet: SafetyDataSheet) -> SheetState:
    return SheetState(
        revision_date=sheet.revision_date,
        issue_date=sheet.issue_date,
        version=sheet.version,
        countries=tuple(sheet.countries),
    )


def current_file(files: list[Path]) -> tuple[Path, Choice] | None:
    """The current sheet among the files of one product."""
    sheets = []
    for path in files:
        reading = read_sheet(path)
        if (
            reading.verification.kind is DocumentKind.SAFETY_DATA_SHEET
            and reading.parser_result is not None
        ):
            sheets.append((path, reading.parser_result.sheet))
    if not sheets:
        return None
    choice = current_state([state_of(sheet) for _, sheet in sheets])
    return sheets[choice.index][0], choice
```

Two things in this example are the caller's part:

- **Which files belong together.** The function compares whatever it is
  given. Sheets of two products in one call give a meaningless answer.
- **Which files are sheets at all.** Pass only files that were recognised as
  safety data sheets. A leaflet with a recent date would otherwise win.

### Without a country

With `country=None` the countries play no part, and only date, version, issue
date and order decide. Use it when the sheets carry no country, or when any
country's sheet will do.

```python
assert current_state(states, country=None) == Choice(4, ChoiceReason.NEWEST)
```

### With an impossible date

A sheet with a misprinted year ("überarbeitet am: 28.11.28", read as 2028)
would be the newest of its product for years. The library reads no clock,
so tell it the day: with `today`, a revision or issue date after that day
counts as missing, and the sheet ranks as one without that date. It is
chosen only if no other sheet carries a date and country, version, issue
date and order decide for it. Without `today` every date counts as printed.

```python
from datetime import date

misprinted = [
    SheetState(date(2024, 3, 1), version="3"),
    SheetState(date(2028, 11, 28), version="4"),
]

assert current_state(misprinted).index == 1
assert current_state(misprinted, today=date(2026, 11, 18)).index == 0
```

## Things to know

- **Empty input** raises `ValueError`. A product without sheets has no current
  one, and the caller knows that before calling.
- **Copies of one file** under several names tie in every value, so the later
  one given is chosen. If it matters which copy you get, remove copies first.
- **The country, not the language.** What counts legally is the country a
  sheet is issued for. Sheets for Germany, Austria and Switzerland are all in
  German, so the language cannot tell them apart.
- **Country codes** are compared as given. This library's reader names `DE`,
  `AT` and `CH`; with your own data, use one spelling throughout.
- **A missing version blocks step 3 on purpose.** Sheets of one state share a
  layout, so a version on one and none on the other points to a faulty sheet
  or a reading error. The answer is then `OTHER_COUNTRY`, and a person should
  look.
