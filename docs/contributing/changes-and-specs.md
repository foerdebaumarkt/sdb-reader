# Changes and the specs

## How a change runs

1. **The spec first.** A change of behaviour starts with its rule: a new
   rule, or an amended one, in the spec of its area, with an entry in that
   spec's decision log saying what was decided and why.
2. **Then the code**, which names the rule's ID where it carries it out.
3. **A test with the rule's marker**, which fails without the change:

   ```python
   @pytest.mark.spec("SDB-50")
   def test_a_bracket_around_the_country_code_stays() -> None: ...
   ```

4. **The versions.** If the same input can now give another result, a stage
   version rises ([Stage versions](stage-versions.md)), and
   [CHANGELOG.md](../../CHANGELOG.md) gets a line under "Unreleased".
5. **The measurement**, for a change to reading or parsing
   ([Measuring a change](measuring.md)).

No rule is needed for a change that leaves behaviour as it is: a refactoring,
a dependency update, a change to CI or tooling, documentation.

A review checks the code against the spec. Code that does what no rule says,
or contradicts one, is a finding.

## The three specs

| File | Area | IDs |
| --- | --- | --- |
| `specs/sicherheitsdatenblatt.md` | how a file is read, judged and parsed, and how statements are put out | SDB |
| `specs/sdb-werkzeug.md` | what the command line prints | SDW |
| `specs/bibliothek.md` | what a program that uses the library can rely on | BIB |

Withdrawn rules of all three are kept, with their old text, in
`specs/historie.md`. `specs/README.md` describes their form and how a rule is
written: one subject, short, word forms as lists, background only where the
rule needs it, a new word form added to the list it belongs to. An ID is never
given out twice and never renumbered. Gaps in the SDB numbers belong to rules of a program the
library was once part of; they are not reused.

## Reading the specs without German

The specs are in German, and the German text is the binding one. The reason
is their subject: the rules name the words German sheets print
("Überarbeitet am", "Kennzeichnungselemente", "Signalwort"), and a rule
about such a word is exact only in its own language. A translation would be
a second text that could disagree with the first.

You can still work with them:

- **Every spec has the same parts**, in this order:

  | Heading | Holds |
  | --- | --- |
  | Zweck | purpose: what the area is about |
  | Begriffe | terms: what the words mean the rules build on |
  | Regeln | rules: numbered, each a list item that begins with its ID in bold |
  | Vorgeschlagene Regeln (noch nicht umgesetzt) | proposed rules: decided, not built yet |
  | Entscheidungsprotokoll | decision log: date, decision, reason |
  | Offene Fragen | open questions and known limits |

- **Markers at the start of a rule:**

  | Marker | Meaning |
  | --- | --- |
  | `*Vorgeschlagen:*` | proposed: has its ID, is not in force, has no test |
  | `*Zurückgezogen 2026-11-17:*` | withdrawn on that date; the old text stays behind the marker, in `specs/historie.md` |
  | `*Zurückgezogen …, ersetzt durch SDB-75:*` | withdrawn and replaced by the rule named |
  | `*Zurückgezogen …, aufgenommen in SDB-57:*` | withdrawn; its content now stands in the rule named, which sums up several |
  | `*Hintergrund:*` | background: a note under a rule, mostly its legal basis; not a rule itself |

- **Words that link rules:**

  | German | Meaning |
  | --- | --- |
  | Abweichend von SDB-44 | departing from SDB-44: this rule overrides it for its case |
  | Ergänzend zu SDB-20 | in addition to SDB-20: this rule adds a case |
  | Über SDB-75 hinaus | beyond SDB-75: likewise |
  | Anstelle von SDB-83 | in place of SDB-83 |
  | Grenze | limit: a case the rule knowingly leaves out |
  | Grund | reason, in the decision log |

- **Words of the subject:**

  | German | English |
  | --- | --- |
  | Sicherheitsdatenblatt, Blatt | safety data sheet, sheet |
  | Datei | file |
  | Leser, Prüfung, Parser | the parts that read the text, judge the file, parse the sheet |
  | Lese-Stufe, Parse-Stufe | reading stage, parser stage |
  | Abschnitt, Unterabschnitt | section, subsection |
  | Überschrift, Zeile, Zelle | heading, line, cell |
  | Kennzeichnung | the label (section 2.2) |
  | Einstufung | classification (section 2.1) |
  | Gefahrenhinweis, Sicherheitshinweis | hazard statement (H), precautionary statement (P) |
  | Signalwort, Piktogramm | signal word, pictogram |
  | Wortlaut | wording |
  | Lieferant, Anschrift | supplier, address |
  | Überarbeitungsdatum, Ausgabedatum | revision date, issue date |
  | Meldung, Befund | message, finding |
  | Aufrufer | caller: a program that uses the library |

- **The examples in a rule are quotes from sheets**, in German quotation
  marks („…“). They show the form the rule is about and need no translation
  to be matched against a text.

- **The tests are in English** and name their rule. To see what a rule means
  in practice, search the tests for its ID.

A machine translation is good enough to understand a rule. If you write a
rule and German is not your language, write it in English in the pull
request; a maintainer puts it into the spec in German with you.
