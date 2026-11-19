# Bedienung der Befehlszeile

Diese Anleitung ist für alle, die `sdb-reader` starten und lesen, was es
ausgibt. Programmieren muss man dafür nicht. Dieselbe Anleitung auf Englisch: [Using the command line](../usage/README.md).

Die Anleitung steht mit der übrigen Dokumentation auch im Netz, unter
<https://foerdebaumarkt.github.io/sdb-reader/>, je veröffentlichter Version
des Programms eine Ausgabe.

`sdb-reader` liest PDF-Dateien und sagt zu jeder, ob sie ein deutsches
Sicherheitsdatenblatt ist und, wenn ja, was darin steht: die Kennzeichnung,
die Einstufung, die Daten, der Lieferant und was an dem Blatt als Dokument
zu beanstanden ist. Es arbeitet nach festen Regeln und ohne Sprachmodell;
dieselbe Datei ergibt deshalb immer dasselbe Ergebnis.

| Seite | Was sie beantwortet |
| --- | --- |
| [Installation](installation.md) | Was brauche ich, und wie bekomme ich den Befehl? |
| [Blätter lesen](lesen.md) | Wie lese ich eine Datei oder einen Ordner, und was bedeuten die Exit-Codes? |
| [Blätter als Bericht anzeigen](anzeigen.md) | Wie bekomme ich einen Bericht, den ich selbst lesen kann, für eine Datei oder einen Ordner? |
| [Einen ganzen Bestand lesen](bestand.md) | Wie lese ich tausende Dateien, setze einen Lauf fort und nehme Dateien aus? |
| [Die Ausgabe verstehen](ausgabe.md) | Was sagt jeder Teil des Ergebnisses? |
| [Die eingebettete Datei](eingebettete-datei.md) | Was ist die Datei, die manche PDFs in sich tragen, und wie hole ich sie heraus? |
| [Ein Sprachmodell fragen](fragen.md) | Wie bekomme ich eine zweite Lesung von einem Modell, was wird wohin geschickt, und wie behalte ich die Antworten? |
| [Zwei Läufe vergleichen](laeufe-vergleichen.md) | Wo liest ein Modell ein Blatt anders als das Programm, und was hat eine Änderung am Programm bewirkt? |
| [Alle Meldungen](meldungen.md) | Welche Meldungen gibt es, und was sagt jede? |
| [Wenn etwas nicht geht](fehlerbehebung.md) | Was tue ich, wenn das Ergebnis anders ist als erwartet? |

Der Befehl hat fünf Unterbefehle:

| Unterbefehl | Tut |
| --- | --- |
| `read` | liest Dateien und gibt aus, was sie sagen, als JSON |
| `show` | liest Dateien und gibt aus, was sie sagen, als Bericht zum Lesen |
| `xml` | gibt die Datei heraus, die das Programm eines Lieferanten in ein PDF eingebettet hat |
| `ask` | fragt ein Sprachmodell, was in jedem Blatt steht, und behält seine Antworten |
| `diff` | stellt zwei Läufe von `read` oder `ask` nebeneinander und zählt, wo sie abweichen |
