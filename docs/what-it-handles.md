# What it handles

Every product with hazardous ingredients, such as a paint, an adhesive or a
cleaner, comes with a safety data sheet: a mandatory document that says how
hazardous the product is and how to handle it safely. Every manufacturer
lays it out differently, the rules have changed several times, and some of
it is printed only as pictures. sdb-reader reads these PDF files and turns
them into reliable data.
Deutsch: [Was es abdeckt](was-es-abdeckt.md).

## Files

- **Thousands of files at once.** A whole folder is read in one run.
- **Scans too.** Scanned sheets are read by text recognition.
- **Knows what a file is.** Not everything called a safety data sheet is
  one. Sheets in other languages and other documents are recognised and not
  read as a German sheet.
- **Several sheets in one file.** Some files hold sheets for several
  countries or for each part of a set. Each is read on its own.

## Hazard warnings and symbols

- **The product's hazard warnings,** such as "Causes skin irritation", with
  the sheet's wording and the official wording side by side.
- **Hazard symbols, also as pictures.** The red-framed diamonds are
  recognised even where they are printed only as pictures, in colour, in
  grey or scanned.
- **Special cases stay apart.** Very small packages and certain product
  groups have their own information. It is not mixed with the rest.

## Product details

- **Product, manufacturer, contact details and emergency number.**
- **Date and version,** in the many ways manufacturers write them.
- **The current sheet.** Where a product has several sheets, sdb-reader
  picks the current one.

## Old and new

- **Outdated sheets are recognised.** A sheet under rules that have not
  applied since mid-2017 is marked as such; its hazard warnings are not
  given out as valid.
- **Renewal due.** A sheet that is valid but not up to the latest standard
  is reported.

## Errors in the sheet

- **Reports the manufacturer's errors,** such as missing or contradictory
  hazard warnings or a symbol that does not fit.
- **Only certain reports.** Where a question depends on something the sheet
  does not say, there is no report. The reports were checked one by one on
  about 14,850 real sheets.

## Reliable

- **On the safe side.** Where a sheet's hazard warnings are incomplete,
  sdb-reader does not pass them on unless asked, so that no product is shown
  without its warnings by mistake. Nor does it conclude from an outdated
  sheet that a product is harmless.
- **Same file, same result.** Fixed, written rules instead of AI; every
  result can be traced back.
- **On your own computer.** No cloud, no cost per page.
- **For people and programs.** The result comes as a readable report or as
  data, in German or English. Open source.

How sdb-reader works in detail is in [How it works](how-it-works.md); the
binding rules are in [specs/](../specs/README.md), in German.
