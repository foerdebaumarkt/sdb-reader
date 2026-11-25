# Specs

Die Regeln, nach denen die Bibliothek arbeitet. Sie sind deutsch geschrieben,
und der deutsche Text ist verbindlich: Die Bibliothek liest deutsche
Sicherheitsdatenblätter, und die Regeln nennen deren Wörter.

| Datei | Gebiet |
| --- | --- |
| `sicherheitsdatenblatt.md` | wie die Bibliothek eine Datei liest, prüft und ihre Angaben ausgibt (SDB) |
| `sdb-werkzeug.md` | was das Werkzeug `sdb-reader` ausgibt (SDW) |
| `bibliothek.md` | was ein Programm, das die Bibliothek benutzt, erwarten kann (BIB) |
| `historie.md` | die zurückgezogenen Regeln aller drei, mit ihrem alten Wortlaut |

## Aufbau einer Spec

- **Zweck** und **Begriffe.**
- **Regeln:** jede mit einer ID, die nie neu vergeben wird:
  `- **SDB-4.** <die Regel>`. Eine Regel sagt, was gilt, nicht, wie der Code
  es erreicht.
- **Vorgeschlagene Regeln (noch nicht umgesetzt)** (wo nötig): beschlossen,
  aber noch nicht gebaut: `- **SDB-22.** *Vorgeschlagen:* <die Regel>`. Sie
  tragen schon ihre ID.
- **Entscheidungsprotokoll:** was entschieden wurde und warum, mit Datum.
- **Offene Fragen:** auch bekannte Grenzen.

Eine Regel, die nicht mehr gilt, wird nicht gelöscht, sondern zurückgezogen
und mit ihrem alten Wortlaut nach `historie.md` verschoben; ihre ID bleibt
belegt. Sie nennt, was an ihre Stelle tritt:

- **ersetzt durch:** eine neue Regel gilt statt ihrer:
  `- **SDW-12.** *Zurückgezogen 2026-11-16, ersetzt durch SDW-13:* <der alte Text>`;
- **aufgenommen in:** ihr Inhalt steht unverändert in einer anderen Regel, die
  mehrere zusammenfasst und ihre ID behält, meist die am häufigsten genannte:
  `- **SDB-91.** *Zurückgezogen 2026-11-21, aufgenommen in SDB-57:* <der alte Text>`;
- **ohne Ersatz:** was sie sagte, gilt nicht mehr.

## Eine Regel schreiben

- **Eine Regel, ein Gegenstand:** was gilt, unter welcher Bedingung, mit
  welchem Ergebnis. Sie steht unter der Überschrift ihres Gegenstands
  („Lieferant“, „Hinweistexte“), nicht in der Reihenfolge der Nummern.
- **Zuerst, was gilt:** Eine Regel beginnt mit einem Satz, der für sich zu
  verstehen ist; die Einzelheiten folgen, in einer längeren Regel als Punkte
  mit einem Stichwort. Sie beginnt nicht mit dem Verweis auf eine andere Regel
  („Ergänzend zu …“, „Abweichend von …“): Trägt sie einer anderen nur eine
  Wortform oder einen Fall nach, gehört sie in diese; hat sie einen eigenen
  Gegenstand, nennt sie ihn und verweist in Klammern auf die andere.
- **Verständlich vor kurz:** Wortformen stehen als Liste, nicht als Kette von
  Sätzen. Wird eine Regel lang, weil sie zwei Fragen beantwortet, sind es zwei
  Regeln.
- **Beispiele** in „…“, mindestens eines je Fall; sie bleiben, wenn Regeln
  zusammengefasst werden.
- **Hintergrund** nur, wo die Regel ohne ihn nicht zu verstehen ist, etwa ihre
  Rechtsgrundlage: als eigene Zeile `*Hintergrund:* …` unter der Regel,
  höchstens zwei Sätze. Begründungen, Messungen und die Geschichte einer
  Entscheidung gehören ins Entscheidungsprotokoll, nicht in den Regeltext.
- **Erweitern statt anhängen:** Eine neue Wortform derselben Art (eine weitere
  Bezeichnung des Datums, ein weiterer Satz für „nicht eingestuft“) kommt in die
  Liste der Regel, zu der sie gehört, mit einem Eintrag im
  Entscheidungsprotokoll und einem Test. Ändert sich, was eine Regel bedeutet,
  wird sie zurückgezogen und ersetzt.

## Wie eine Änderung abläuft

1. **Zuerst die Spec:** neue oder geänderte Regeln als Vorschlag, mit einem
   Eintrag im Entscheidungsprotokoll. Eine neue Wortform in einer Liste braucht
   keinen Vorschlag; sie kommt mit ihrem Test und dem Eintrag im Protokoll.
2. **Dann die Umsetzung**, die die Regel in Kraft setzt und ihre ID nennt.
3. **Reviews prüfen den Code gegen die Spec.** Code, der etwas tut, das keine
   Regel sagt, oder einer Regel widerspricht, ist ein Befund.

Keine Regel brauchen: Umbauten ohne geändertes Verhalten, Updates von
Abhängigkeiten, Änderungen an CI und Werkzeugen.

## Tests verweisen auf Regeln

Ein Test, der eine Regel festhält, sagt das mit einem Marker; mehrere IDs sind
erlaubt:

```python
@pytest.mark.spec("SDB-4", "SDB-5")
def test_the_label_block() -> None: ...
```

Der Marker kann an einer Testfunktion oder einer Testklasse stehen.

## Die Prüfung

`tests/test_specs.py` liest jede `specs/*.md`, `historie.md` eingeschlossen,
und jeden `spec`-Marker unter `tests/`. Sie schlägt fehl, wenn eine geltende
Regel keinen Test hat, wenn ein Test eine unbekannte, zurückgezogene oder nur
vorgeschlagene ID nennt, oder wenn eine Spec eine ID zweimal festlegt, auch
eine zurückgezogene.
