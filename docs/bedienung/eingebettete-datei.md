# Die eingebettete Datei

## Was sie ist

Manche Programme, mit denen Lieferanten ihre Sicherheitsdatenblätter
schreiben, legen eine zweite Fassung der Daten des Blatts in das PDF: eine
Datei im Austauschformat eSDScom, das ist XML, ein Textformat für Programme.
Beim Öffnen des PDF sieht man sie nicht. Die meisten PDFs tragen keine.

`sdb-reader` liest das Blatt immer aus dem gedruckten Text. Trägt ein PDF
eine solche Datei, ist sie eine zweite Lesung, an der sich die erste prüfen
lässt.

## Was `read` dazu sagt

Bei einem PDF mit eingebetteter Datei hat der Datensatz einen Teil
`embedded_data`:

```json
{
  "format": "eSDScom",
  "filename": "sds.xml",
  "compared": true,
  "differences": [
    {"field": "hazard_codes", "embedded": ["H412"], "read": ["H315"]},
    {"field": "signal_word", "embedded": null, "read": "Achtung"}
  ],
  "version": "4.4.0",
  "system": "Example Author"
}
```

| Feld | Bedeutung |
| --- | --- |
| `filename` | der Name der eingebetteten Datei |
| `version`, `system` | die Fassung des Formats und das Programm, das die Datei geschrieben hat |
| `compared` | `true`, wenn sich die Datei lesen ließ und das PDF ein deutsches Sicherheitsdatenblatt ist; sonst gab es nichts zu vergleichen |
| `differences` | die Felder, in denen die eingebettete Datei und das gelesene Blatt abweichen, je mit beiden Werten; leer, wenn sie übereinstimmen oder nichts verglichen wurde |
| `unreadable` | bei einer eingebetteten Datei, die sich nicht lesen ließ: der Grund, als Meldung |

Verglichen werden das Datum, das Signalwort, die Piktogramme, die Codes der
H-, P- und EUH-Sätze sowie Name und E-Mail-Adresse des Lieferanten.

Eine Abweichung sagt, dass beide nicht übereinstimmen, nicht, wer recht hat.
Sehen Sie im gedruckten Blatt nach: Entweder hat das Programm des Lieferanten
etwas anderes ausgegeben als gedruckt, oder das Blatt wurde falsch gelesen.

## Die Datei herausholen

`xml` gibt die eingebettete Datei unverändert heraus, Byte für Byte:

```bash
sdb-reader xml sheet.pdf > sheet.xml
sdb-reader xml --save folder *.pdf
```

Ohne `--save` nimmt es ein PDF und gibt die Datei aus. Mit `--save` nimmt es
mehrere und schreibt die Datei jedes PDF als `<Name des PDF>.xml` in den
Ordner. Der Ordner muss bestehen, und eine Datei, die schon da ist, wird
nicht überschrieben.

| Exit-Code | Bedeutung |
| --- | --- |
| 0 | erledigt; mit `--save` werden PDFs ohne eingebettete Datei genannt und übergangen |
| 1 | das eine verlangte PDF hat keine eingebettete Datei, eine Datei ließ sich nicht herausgeben, ein Ziel besteht schon, oder mit `--save` wurde keine einzige Datei herausgegeben |
| 2 | ein Pfad ist keine Datei, der Ordner besteht nicht, oder mehrere PDFs wurden ohne `--save` angegeben |

`xml` nimmt `--lang` und `--messages` wie `read`, für die Zeilen, die es auf
die Fehlerausgabe schreibt.
