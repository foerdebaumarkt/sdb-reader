# Adding a language

Two different things go by this name. The first is small and welcome now;
the second is the large one, and this page says honestly where it stands.

## 1. The language of the messages

The sentences of warnings, errors and findings come from catalogs: one TOML
file per language in `src/sdb_reader/messages_data/`. German (`de.toml`) and
English (`en.toml`) ship. To add a language:

1. Copy `en.toml` to `<language code>.toml`, such as `fr.toml`.
2. Translate each sentence. Keep the codes and the `{placeholders}` as they
   are; a placeholder may move within its sentence.
3. Run the tests. `tests/test_messages.py` checks every shipped catalog: it
   has to hold every code, use only the values its code carries, and leave
   none out.
4. Add the language to the operator's manual only if you also translate the
   manual; otherwise the catalog alone is enough, and `--lang <code>` works.

Write the sentences for a person who reads a report about a sheet: plain,
concrete, in the words the sheets of that language use themselves.

## 2. Reading sheets in another language

**Today the reader reads German sheets only.** A safety data sheet in
another language is recognised as one, by the numbered subsections that the
regulation prescribes in every language, and is not parsed.

What is bound to German:

| Part | Where | What it holds |
| --- | --- | --- |
| Section headings and subsection titles | `parser.py` | "ABSCHNITT", "Bezeichnung des Stoffs …", "Kennzeichnungselemente", "Sonstige Gefahren" |
| Labels of values | `parser.py` | "Überarbeitet am", "Version", "Handelsname", "Signalwort", "Telefon", the many forms of a date's label |
| The title | `verification.py` | "Sicherheitsdatenblatt" as the title that makes a German sheet |
| Wordings that say "not classified", "no signal word", "not determined" | `parser.py` | the sentences suppliers use for them |
| The statements' wording | `clp_statements_de.json` | the German wording of every H, EUH and P statement from Annex III and IV of the CLP Regulation |
| Signal words | `pictograms.py` | "Gefahr", "Achtung" |
| Countries | `parser.py` | the national rules and advice centres of Germany, Austria and Switzerland that tell which country a sheet is issued for |
| The specs | `specs/` | the rules name the German words |

What is not bound to a language: the layout reader, the choice among several
sheets, the pictograms from H codes, the findings' logic, the messages, the
schema, the embedded file.

What another language would need:

1. **The statements' wording.** The regulation prints every statement in
   every official language. `tools/clp/extract_statements.py` reads the
   German row of those tables today and could read another; the result would
   be a file `clp_statements_<language>.json` beside the German one.
2. **The vocabulary of the parser as data.** Headings, labels and the
   fixed sentences would have to move out of the code into a table per
   language, with German as the first entry and no change in what German
   sheets read as. That is a large refactoring of `parser.py`, and it has to
   be measured sheet by sheet ([Measuring a change](measuring.md)).
3. **Rules for that language**, in a spec of their own, since they name its
   words; and sheets of that language to measure on.
4. **A decision on the country.** Which national rules tell that a sheet is
   issued for a given country is knowledge about that country, not about its
   language.

If you want to work on this, open an issue first. The first step that helps
without touching the parser is the statements' wording for another language.
