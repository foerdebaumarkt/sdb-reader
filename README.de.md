# sdb-reader

Liest deutsche Sicherheitsdatenblätter nach REACH und CLP aus PDF-Dateien,
ohne Sprachmodell: Dieselbe Datei ergibt immer dasselbe Ergebnis, und jede
Regel, der der Leser folgt, ist aufgeschrieben.

English: [README.md](README.md)

```bash
sdb-reader read sheet.pdf
```

Zu jedem PDF sagt es:

- **was die Datei ist:** ein deutsches Sicherheitsdatenblatt, eine
  Sicherheitsinformation, ein Sicherheitsdatenblatt in einer anderen Sprache
  oder ein anderes Dokument;
- **die Einstufung**, die Abschnitt 2 nennt;
- **die Kennzeichnung:** Signalwort, Piktogramme und die H-, P- und
  EUH-Sätze, mit dem Wortlaut des Blatts neben dem der Verordnung;
- **Daten und Version**, die Länder, für die das Blatt ausgestellt ist, und
  den Lieferanten;
- **was an dem Blatt als Dokument zu beanstanden ist:** vor 2021
  überarbeitet, kein lesbares Datum, Einstufung und Kennzeichnung, die sich
  widersprechen, ein Satz, der im Wortlaut von der Verordnung abweicht.

Das Ergebnis ist JSON. Warnungen und Befunde kommen als fester Code mit
einem Satz, auf Deutsch oder Englisch. Wer ein Blatt selbst lesen will,
bekommt dasselbe mit `show` als Bericht:

```bash
sdb-reader show sheet.pdf
```

## Dokumentation

Die Dokumentation steht unter <https://foerdebaumarkt.github.io/sdb-reader/>,
je veröffentlichter Version eine Ausgabe. Dieselben Seiten liegen im
Repository unter [docs/](docs/README.md).

| Sie wollen | Lesen Sie |
| --- | --- |
| den Befehl benutzen und verstehen, was er ausgibt | [Bedienung](docs/bedienung/README.md), auf Englisch: [Using the command line](docs/usage/README.md) |
| Blätter aus einem Python-Programm lesen | [Using the library](docs/api/README.md) (englisch) |
| verstehen, wie aus einer Datei eine Lesung wird | [How it works](docs/how-it-works.md) (englisch) |
| am Leser mitarbeiten | [Contributing](docs/contributing/README.md) (englisch) |
| wissen, was eine Version geändert hat | [CHANGELOG.md](CHANGELOG.md) (englisch) |
| die verbindlichen Regeln lesen | [specs/](specs/README.md) |

## Installation

Braucht Python 3.12 oder neuer. Installiert wird es aus dem Python Package
Index:

```bash
uv tool install sdb-reader
```

Gescannte Blätter werden per Texterkennung gelesen; dafür braucht es
`tesseract` mit deutschen Sprachdaten. Die Einzelheiten stehen unter
[Installation](docs/bedienung/installation.md).

## Grenzen

- Nur deutsche Blätter. Ein Blatt in einer anderen Sprache wird als solches
  erkannt und nicht gelesen.
- Es liest eine Datei nach der anderen. Welche Blätter zu einem Produkt
  gehören, weiß das Programm, das es benutzt; die Bibliothek wählt dann unter
  ihnen das geltende.
- Ob ein Produkt ein Sicherheitsdatenblatt braucht, wird aus Einstufung und
  Kennzeichnung gelesen. Abschnitt 2.3 (PBT, vPvB, Kandidatenliste) wird
  nicht gelesen.
- Ein älteres Blatt in einer anderen Sprache ohne nummerierte
  Unterabschnitte zählt als Dokument.
- Ein Formular in zwei Spalten ohne Doppelpunkte wird nur in Abschnitt 1 als
  Bezeichnung und Wert gelesen. In den übrigen Abschnitten eines solchen
  Blatts wird ein Wert womöglich nicht gefunden.

## Lizenz

GNU Affero General Public License, Version 3 oder später ([LICENSE](LICENSE)).
Die PDF-Bibliothek, auf der der Leser aufbaut, PyMuPDF (installiert als
`pymupdf-lite`), steht unter der AGPL;
ein Programm, das dieses Paket benutzt, übernimmt deren Pflichten.

Copyright © 2026 Förde-Baumarkt Holger Claussen GmbH & Co. KG
(<service@foerde-baumarkt.de>).
[NOTICE](NOTICE) nennt den Rechteinhaber und die Quelle des Wortlauts der
Verordnung, den das Paket mitbringt.
