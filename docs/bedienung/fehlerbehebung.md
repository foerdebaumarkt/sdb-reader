# Wenn etwas nicht geht

## Der Befehl

| Was Sie sehen | Warum | Was zu tun ist |
| --- | --- | --- |
| `command not found: sdb-reader` | der Befehl liegt nicht in Ihrem Suchpfad | mit vollem Pfad starten oder mit `uv tool install` installieren, wie unter [Installation](installation.md) |
| `error: not a file or directory: …` und Exit-Code 2 | ein Pfad besteht nicht | den Pfad prüfen |
| `error: no PDF file under: …` und Exit-Code 2 | der Ordner enthält kein PDF | den Ordner prüfen; gelesen werden Dateien mit der Endung `.pdf` |
| `error: … exists; give another file, or --resume to continue it` | die Ergebnisdatei gibt es schon | eine andere Datei nennen oder den Lauf mit `--resume` fortsetzen |
| `error: no message catalog for '…'` | Sätze gibt es nur für `de` und `en` | eine der beiden nehmen oder eine eigene Datei mit `--messages` |
| `error: ask needs an endpoint and a model` | `ask` wurde ohne beides gestartet | `--endpoint` und `--model` angeben oder die beiden Variablen setzen |
| das Ergebnis ist mit anderen Zeilen vermischt | Ergebnis und Fehlerausgabe gehen beide auf den Bildschirm | das Ergebnis mit `> result.json` in eine Datei schreiben |

## Eine Datei wird nicht gelesen

| Was Sie sehen | Warum | Was zu tun ist |
| --- | --- | --- |
| `errors` trägt `ocr-too-old` | das installierte `tesseract` ist älter als Version 5 | Version 5 oder neuer installieren; die Meldung nennt die gefundene Version |
| `errors` trägt `ocr-language-missing` | `tesseract` ist ohne die deutschen Sprachdaten installiert | die Daten installieren, siehe [Installation](installation.md) |
| `errors` trägt `ocr-unavailable` | die Seiten sind Bilder, und `tesseract` ist nicht installiert | mit den deutschen Sprachdaten installieren, siehe [Installation](installation.md) |
| `errors` trägt `no-text` | die Seiten sind Bilder, und die Texterkennung hat nichts gelesen | die Datei ansehen: eine leere oder schlecht gescannte Seite lässt sich nicht lesen |
| `errors` trägt `pdf-unreadable` | die Datei ist kein PDF oder beschädigt | in einem PDF-Betrachter öffnen; die Datei neu besorgen |
| `errors` trägt `pdf-too-large` | die Datei ist größer, als das Programm liest | die Meldung nennt Größe und Grenze; eine solche Datei ist selten ein einzelnes Sicherheitsdatenblatt, also ansehen, was sie enthält |
| `errors` trägt `ocr-timeout` | die Texterkennung hat für eine Seite zu lange gebraucht | noch einmal versuchen; ein sehr großer Scan lässt sich womöglich nicht lesen |

## Die Datei ist nicht, was Sie erwartet haben

| Was Sie sehen | Warum | Was zu tun ist |
| --- | --- | --- |
| `kind` ist `safety-data-sheet-other-language` | das Blatt ist nicht deutsch | gelesen werden nur deutsche Blätter; beim Lieferanten das deutsche Blatt anfordern |
| `kind` ist `safety-information` | die Datei hat die Abschnitte eines Blatts, nennt sich aber nicht Sicherheitsdatenblatt | sie ist keines; Lieferanten geben sie für Produkte heraus, die kein Blatt brauchen |
| `kind` ist `document` bei einer Datei, die sicher ein Blatt ist | der Titel oder die Abschnitte wurden nicht erkannt | `verification.warnings` lesen; ein per Texterkennung gelesener Scan kann seinen Titel verloren haben |

## Ein Wert fehlt oder ist falsch

| Was Sie sehen | Warum | Was zu tun ist |
| --- | --- | --- |
| ein Feld ist leer, obwohl das Blatt den Wert druckt | der Wert wurde in diesem Layout nicht gefunden | `parser.warnings` und den `section_text` des Abschnitts lesen; das Layout melden |
| `countries` ist leer | das Blatt nennt kein Land | es zählt als Blatt für Ihr Land |
| `pictograms` ist leer, obwohl die Kennzeichnung Piktogramme zeigt | die Kennzeichnung ließ sich nicht als Bild ansehen (gescannt, keine Überschrift „Kennzeichnungselemente“), oder eine Raute blieb unbenannt | `parser.warnings` sagt, was (`label-images-not-read`, `pictograms-not-recognised`); `drawing_read` ist falsch |
| `signal_word` ist leer, obwohl das Blatt H-Sätze trägt | das Blatt druckt kein Signalwort, oder es wurde nicht gefunden | `findings` meldet `signal-word-not-found` mit dem Wort, das die Codes verlangen, außer die Kennzeichnung gibt an, keines zu tragen (`states_no_signal_word`) |
| ein Wert fehlt bei einem Blatt, das als Formular in zwei Spalten ohne Doppelpunkte gesetzt ist | außerhalb von Abschnitt 1 werden solche Zeilen als Tabelle gelesen, und Bezeichnung und Wert können auseinanderstehen | eine bekannte Grenze; `section_text` prüfen |
| die Meldung `short-text` oder `short-sample` | die Datei hat wenig Text für ein Blatt | sie kann abgeschnitten oder teils gescannt sein; die Datei ansehen |
| der Befund `wording-deviates` bei einem Satz, der richtig aussieht | der Wortlaut des Blatts weicht in einem Wort von jeder Form ab, die die Verordnung dem Satz gibt oder gab; ein früherer Wortlaut der Verordnung, ein verbundener Satz aus den Wortlauten seiner Teile und ein weggelassener Text in eckigen Klammern sind kein Befund | die beiden Wortlaute in den Angaben des Befunds vergleichen |

## Ein Problem melden

Nennen Sie die Version, die Sie benutzen (`sdb-reader --version`
zeigt sie), was Sie gestartet haben und was Sie erwartet haben. Hängen Sie
das Blatt eines Lieferanten nur an eine öffentliche Meldung, wenn Sie es
weitergeben dürfen; beschreiben Sie sonst das Layout oder bauen Sie ein
kleines Beispiel.
