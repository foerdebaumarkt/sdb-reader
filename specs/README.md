# Specs

Die Regeln, nach denen die Bibliothek arbeitet. Sie sind deutsch geschrieben,
und der deutsche Text ist verbindlich: Die Bibliothek liest deutsche
Sicherheitsdatenblätter, und die Regeln nennen deren Wörter.

| Datei | Gebiet |
| --- | --- |
| `sicherheitsdatenblatt.md` | wie die Bibliothek eine Datei liest, prüft und ihre Angaben ausgibt (SDB) |
| `sdb-werkzeug.md` | was das Werkzeug `sdb-reader` ausgibt (SDW) |
| `bibliothek.md` | was ein Programm, das die Bibliothek benutzt, erwarten kann (BIB) |

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

Eine Regel, die nicht mehr gilt, wird nicht gelöscht, sondern zurückgezogen:
`- **SDW-12.** *Zurückgezogen 2026-11-16, ersetzt durch SDW-13:* <der alte Text>`.

## Wie eine Änderung abläuft

1. **Zuerst die Spec:** neue oder geänderte Regeln als Vorschlag, mit einem
   Eintrag im Entscheidungsprotokoll.
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

`tests/test_specs.py` liest jede `specs/*.md` und jeden `spec`-Marker unter
`tests/`. Sie schlägt fehl, wenn eine geltende Regel keinen Test hat, wenn ein
Test eine unbekannte, zurückgezogene oder nur vorgeschlagene ID nennt, oder wenn
eine Spec eine ID zweimal festlegt.
