# Die Ausgabe verstehen

Jede Datei bekommt einen Datensatz. Diese Seite geht seine Teile in der
Reihenfolge durch, in der sie erscheinen.

## Was die Datei ist

`verification.kind` sagt, was die Datei ist. Es gibt vier Arten:

| `kind` | Die Datei ist | Was der Datensatz enthält |
| --- | --- | --- |
| `safety-data-sheet` | ein deutsches Sicherheitsdatenblatt | `sheet`, `statements`, `parser`, `findings`, `sheet_count`; `parts`, wo die Datei [mehrere Blätter](#mehrere-blätter-in-einer-datei) enthält |
| `safety-information` | aufgebaut wie ein Sicherheitsdatenblatt, ohne sich so zu nennen | nur das Urteil |
| `safety-data-sheet-other-language` | ein Sicherheitsdatenblatt in einer anderen Sprache | das Urteil und den Befund `not-german` |
| `document` | etwas anderes, oder eine Datei, aus der sich kein Text lesen ließ | das Urteil; `errors` nennt den Grund, wenn nichts zu lesen war |

Nur die erste Art wird weiter gelesen, und nur ihr Datensatz trägt `sheet`,
`statements`, `parser` und `sheet_count`. Jeder Datensatz trägt die Listen `warnings`, `errors`
und `findings`; eine Liste, zu der es nichts gibt, ist leer und fehlt nicht. `verification.errors` nennt,
warum eine Datei kein deutsches Sicherheitsdatenblatt ist, und
`verification.warnings`, was dabei auffiel.

Eine Sicherheitsinformation geben Lieferanten für Produkte heraus, die kein
Sicherheitsdatenblatt brauchen. Sie hat die sechzehn Abschnitte, aber nicht
den Titel. Dazu zählt auch ein Merkblatt zum Umgang mit einem Erzeugnis,
das sich „Sicherheitsdatenblatt zum sicheren Umgang mit …“ nennt und die
Verordnung (EG) Nr. 1907/2006 nicht nennt, etwa das eines
Batterieherstellers: Was es an Einstufungen druckt, gehört zu seinen
Inhaltsstoffen, nicht zur Kennzeichnung des Produkts.

## Wie der Text gelesen wurde

`extraction` sagt, wie der Text aus dem PDF gewonnen wurde:

| Feld | Bedeutung |
| --- | --- |
| `stage` | die Lese-Stufe, aus der der Text stammt: ihre Version und die der PDF-Bibliothek; zwei Läufe aus verschiedenen Stufen können abweichen, weil der Text ein anderer ist, siehe [Zwei Läufe vergleichen](laeufe-vergleichen.md) |
| `extractor` | `pymupdf` für ein PDF, das seinen Text mitbringt; `pymupdf+ocr`, wo die Texterkennung die Seiten gelesen hat |
| `pages_sampled` | wie viele Seiten gelesen wurden |
| `character_count` | wie viele Zeichen der Text hat |
| `tesseract` | die Version des Programms zur Texterkennung, das den Text gelesen hat; nur wo es Seiten gelesen hat |
| `warnings` | was auffiel, als [Meldungen](#meldungen) |

Text aus der Texterkennung ist weniger verlässlich als Text, den das PDF
mitbringt. Prüfen Sie ein solches Blatt genauer.

## Das Blatt

`sheet` enthält, was ein deutsches Sicherheitsdatenblatt sagt:

| Feld | Bedeutung |
| --- | --- |
| `product_identifier` | der Handelsname aus Abschnitt 1.1 |
| `revision_date`, `issue_date` | Überarbeitungsdatum und Ausgabedatum, als Jahr-Monat-Tag; das jüngste, wo das Blatt mehrere nennt |
| `version` | die Versionsnummer des Blatts |
| `countries` | die Länder, für die das Blatt ausgestellt ist, aus `DE`, `AT`, `CH`; leer, wo es keines nennt |
| `stated_classification` | was Abschnitt 2 über die Einstufung sagt, siehe unten |
| `stated_voluntary`, `stated_article` | ob das Blatt sich selbst freiwillig oder nicht vorgeschrieben nennt, und ob es das Produkt dabei ein Erzeugnis nennt, siehe unten |
| `sheet_required` | ob das Produkt nach dem Gesetz ein Sicherheitsdatenblatt braucht, siehe unten |
| `hazard_statements` | die Kennzeichnung aus Abschnitt 2.2, siehe unten |
| `contact_info` | der Lieferant aus Abschnitt 1.3 mit Name, Anschrift, Telefon, E-Mail und Internetseite, und die Notrufnummer aus Abschnitt 1.4, wie gedruckt mit dem, was das Blatt zu ihr sagt („(24 h)“, der Name des Giftnotrufs); `information_email` ist die E-Mail-Adresse der auskunftgebenden Stelle: die der sachkundigen Person („E-Mail-Adresse der sachkundigen Person“), sonst die einer auskunftgebenden Stelle („Auskunftgebender Bereich“). Sie ist leer, wo keine Adresse unter einer solchen Bezeichnung steht, kann dieselbe sein wie `email` und kann die eines Büros sein, das das Blatt für den Lieferanten erstellt hat |
| `section_text` | der Text jedes gefundenen Abschnitts |
| `content_hash` | ein Fingerabdruck des Texts; zwei Dateien mit demselben haben denselben Inhalt |

### Die Einstufung

`stated_classification` ist, was Abschnitt 2 sagt:

| Wert | Abschnitt 2 sagt |
| --- | --- |
| `classified` | das Produkt ist nach der CLP-Verordnung als gefährlich eingestuft |
| `classified-old-system` | es ist nach den Richtlinien vor der CLP-Verordnung eingestuft (R-Sätze, Gefahrensymbole) |
| `not-classified` | es ist nicht eingestuft |
| `not-stated` | keines von beidem |

### Ob das Produkt ein Blatt braucht

`sheet_required` ist `true`, wo Abschnitt 2 das Produkt einstuft oder die
Kennzeichnung einen Gefahrenhinweis (H oder EUH), ein Signalwort oder ein
Piktogramm trägt. Jedes andere Blatt ist freiwillig ausgestellt.
Sicherheitshinweise (P) allein zählen nicht: Ein Lieferant darf sie auf jedes
Produkt drucken.

`stated_voluntary` ist `true`, wo das Blatt von sich sagt, es sei freiwillig
ausgestellt oder für das Produkt sei kein Sicherheitsdatenblatt
vorgeschrieben („Für dieses Produkt ist gemäß Artikel 31 der
REACH-Verordnung kein Sicherheitsdatenblatt erforderlich.“, „Dieses
Sicherheitsdatenblatt wurde freiwillig erstellt“, „… für Erzeugnisse nicht
vorgeschrieben“). `stated_article` ist `true`, wo es das Produkt neben
diesem Satz ein Erzeugnis nennt, oder wo es sagt, das Produkt sei ein
Erzeugnis und deshalb nicht kennzeichnungspflichtig („Dieses Produkt ist ein
Erzeugnis, deshalb ist es … nicht kennzeichnungspflichtig“); ein solches
Blatt muss sich nicht freiwillig nennen. Was daraus für `sheet_required`
folgt:

| Das Blatt … | `sheet_required` |
| --- | --- |
| nennt das Produkt ein Erzeugnis | `false`, auch wenn die Kennzeichnung H-Sätze druckt |
| nennt sich freiwillig, und das Produkt ist nicht eingestuft (Abschnitt 2 stuft nicht ein, kein H-Satz) | `false` |
| nennt sich freiwillig, aber das Gemisch ist eingestuft und kein Erzeugnis genannt | `true`: Einem Händler oder gewerblichen Anwender, der es verlangt, ist das Blatt geschuldet |
| druckt in der Kennzeichnung EUH210 oder den Satz „auf Anfrage erhältlich“ | `true`, in jedem Fall |

Die Kennzeichnung steht immer in der Lesung, wie das Blatt sie druckt.

### Die Kennzeichnung

`hazard_statements` ist die Kennzeichnung aus Abschnitt 2.2:

| Feld | Bedeutung |
| --- | --- |
| `hazard_codes` | die Codes der Gefahrenhinweise (H); H360 und H361 mit den Buchstaben ihrer Wirkung, wie Anhang VI der CLP-Verordnung sie setzt (`H360D`, `H361fd`) |
| `precautionary_codes` | die Codes der Sicherheitshinweise (P) |
| `supplemental_codes` | die Codes der ergänzenden Gefahrenmerkmale (EUH) |
| `signal_word` | `Gefahr` oder `Achtung`, wie die Kennzeichnung es druckt, oder nichts |
| `pictograms` | die Codes der Piktogramme, die die Kennzeichnung druckt, `GHS01` bis `GHS09`: die, die ihr Text nennt, und die, die sie als Bild zeigt |
| `drawing_read` | ob die Kennzeichnung als Bild angesehen und jede rote Raute darin benannt ist |
| `states_no_signal_word`, `states_no_pictograms` | ob die Kennzeichnung angibt, keines zu tragen („Signalwort entfällt“, „Gefahrenpiktogramme: keine“) |
| `hazard_text`, `precautionary_text`, `supplemental_text` | die Sätze, wie das Blatt sie druckt; ein Code, den das Blatt nicht druckt, steht vor seinem Satz |
| `codes_from_wording` | die Codes, die die Kennzeichnung nicht druckt: Das Blatt druckt nur den Satz, und der Parser hat ihm den Code zugeordnet; jeder steht auch in seiner Liste oben |

Die Kennzeichnung enthält nur, was das Blatt druckt. Das Signalwort ist das
gedruckte. Piktogramme sind die gedruckten: Die meisten Blätter drucken sie
als Bild, und `read` sucht in der Kennzeichnung auf der Seite die roten
Rauten und benennt jede. Aus den Codes abgeleitet wird nichts. Weicht die
Kennzeichnung von dem ab, was ihre Codes nach der CLP-Verordnung verlangen,
sagen es die Befunde (`signal-word-not-found`, `pictogram-not-found`,
`pictogram-not-expected`, `pictogram-precedence`); eine Kennzeichnung, die
angibt, keines zu tragen, bekommt keinen Befund, dass eines nicht gefunden
wurde. Ließ sich die Kennzeichnung nicht als Bild ansehen (ein gescanntes
Blatt, eine Kennzeichnung ohne die Überschrift „Kennzeichnungselemente“)
oder blieb eine Raute unbenannt, sagt es `parser.warnings`
(`label-images-not-read`, `pictograms-not-recognised`), und `drawing_read`
ist falsch.

## Die Sätze

`statements` führt jeden Satz der Kennzeichnung mit zwei Wortlauten auf:

| Feld | Bedeutung |
| --- | --- |
| `code` | der Code des Satzes, etwa `P102` |
| `sheet` | der Wortlaut, den der Lieferant gedruckt hat |
| `regulation` | der Wortlaut der CLP-Verordnung; leer, wo die Verordnung keinen einzelnen hat, bei einem Satz mit Lücke oder mit Auswahl |
| `code_source` | `printed`, wo die Kennzeichnung den Code druckt, `from_wording`, wo sie nur den Satz druckt und der Parser den Code zugeordnet hat |

Wer die Sätze so zeigen will, wie das Blatt sie druckt, lässt den Code eines
Satzes weg, dessen `code_source` `from_wording` ist.

## Was die Verordnung erwartet

`clp_expected` steht neben dem Blatt und gehört nicht dazu: was die
CLP-Verordnung von der Kennzeichnung erwartet, aus ihren Codes ermittelt, und
worin die gelesene Kennzeichnung davon abweicht. Die Kennzeichnung selbst
steht unverändert, wie gedruckt, unter `sheet.hazard_statements`. Ob eine
Abweichung zählt, entscheiden Sie: eine Lücke damit füllen oder eine
Kennzeichnung damit prüfen.

| Feld | Bedeutung |
| --- | --- |
| `signal_word` | `Gefahr`, `Achtung` oder nichts: das Wort, das die H- und EUH-Codes verlangen; nie aus den Piktogrammen |
| `pictograms` | die Piktogramme, die die H-Codes verlangen, mit dem Vorrang nach Art. 26 CLP; nie GHS04 (Art. 33 CLP), kein GHS05, wo H290 sein einziger Grund ist (Anhang I Nr. 1.3.6 CLP) |
| `signal_word_missing` | die Codes verlangen ein Signalwort, und die gelesene Kennzeichnung hat keines |
| `signal_word_differs` | die gelesene Kennzeichnung hat ein anderes Signalwort, als die Codes verlangen |
| `pictograms_missing` | verlangt, und nicht in der gelesenen Kennzeichnung |
| `pictograms_not_expected` | in der gelesenen Kennzeichnung, und kein H-Code verlangt sie |
| `pictograms_left_out` | in der gelesenen Kennzeichnung und verlangt, aber Art. 26 lässt sie neben einem anderen weg, das sie hat |

Bevor Sie etwas fehlend nennen, sehen Sie unter `sheet.hazard_statements`
nach `drawing_read`, `states_no_signal_word` und `states_no_pictograms`: Eine
Kennzeichnung, die sich nicht als Bild ansehen ließ, kann ein Piktogramm
trotzdem zeigen, und eine, die angibt, keines zu tragen, hat geantwortet. Die
Befunde berücksichtigen beides, dieser Block nicht. Bei einer Datei mit
mehreren Blättern trägt jeder Eintrag von `parts` seinen eigenen. Ein früher
geschriebener Datensatz hat keinen solchen Block.

## Die Befunde

`findings` führt auf, was an dem Blatt als Dokument zu beanstanden ist. Jeder
Befund ist eine [Meldung](#meldungen).

| `code` | Bedeutung |
| --- | --- |
| `predates-annex-ii` | vor 2021 überarbeitet; das Blatt kann den heutigen Vorgaben für den Inhalt eines Blatts nicht folgen |
| `old-format` | seit 2021 überarbeitet, aber noch aufgebaut wie davor |
| `revised-in-future` | das Überarbeitungsdatum liegt nach dem Tag, an dem `read` lief; es kann nicht stimmen und ist kein Datum: `revision_date` ist `null`, und das Blatt wird nach seinem Ausgabedatum beurteilt, wenn dieses möglich ist, sonst als undatiert |
| `issued-in-future` | dasselbe für das Ausgabedatum: `issue_date` ist `null` |
| `undated` | kein lesbares Überarbeitungs- oder Ausgabedatum |
| `old-classification` | nach den Richtlinien vor der CLP-Verordnung eingestuft, ohne Kennzeichnung nach CLP |
| `classification-undetermined` | die Kennzeichnung sagt, die Einstufung sei nicht bestimmt |
| `classification-not-stated` | Abschnitt 2 nennt weder eine Gefahrenklasse noch sagt er, das Produkt sei nicht eingestuft, und die Kennzeichnung ist leer |
| `classification-contradicts-label` | Abschnitt 2 sagt „nicht eingestuft“, die Kennzeichnung trägt aber einen Gefahrenhinweis, ein Signalwort oder ein Piktogramm |
| `euh-outside-label` | ein ergänzendes Gefahrenmerkmal steht nur außerhalb der Kennzeichnung |
| `different-products` | die Datei enthält Blätter verschiedener Produkte; `products` nennt sie. Siehe [Mehrere Blätter in einer Datei](#mehrere-blätter-in-einer-datei) |
| `country-editions-differ` | die Datei enthält Blätter desselben Produkts für verschiedene Länder, und sie weichen in den genannten Feldern (`fields`) ab |
| `wording-deviates` | ein Satz weicht im Wortlaut von der Verordnung ab |
| `pictogram-not-found` | die H-Sätze verlangen ein Piktogramm, das die Kennzeichnung nicht druckt; nur wo `drawing_read` |
| `pictogram-not-expected` | die Kennzeichnung druckt ein Piktogramm, das keiner ihrer H-Sätze verlangt |
| `pictogram-precedence` | die Kennzeichnung druckt GHS07 neben einem Piktogramm, dem es nach Art. 26 CLP weicht |
| `not-german` | das Blatt ist in einer anderen Sprache |

Ein Befund ist eine Beobachtung am Dokument. Was daraus folgt, etwa beim
Lieferanten ein neueres Blatt anzufordern, entscheiden Sie.

## Meldungen

Alles, was das Programm zu einer Datei anmerkt, ist eine Meldung: was ihm
beim Lesen des Texts, beim Beurteilen der Datei und beim Lesen des Blatts
auffiel, der Grund, aus dem sich eine Datei nicht lesen ließ, und die
Befunde. Jede Meldung hat drei Teile:

```json
{
  "code": "wording-deviates",
  "params": {
    "statement": "P102",
    "sheet": "Darf nicht in Kinderhände gelangen.",
    "regulation": "Darf nicht in die Hände von Kindern gelangen."
  },
  "message": "P102: Das Blatt druckt „Darf nicht in Kinderhände gelangen.“, die Verordnung sagt „Darf nicht in die Hände von Kindern gelangen.“."
}
```

| Teil | Bedeutung |
| --- | --- |
| `code` | was angemerkt wird; fest und in jeder Sprache gleich |
| `params` | die Angaben, die der Code nennt |
| `message` | der Satz für einen Menschen, in der gewählten Sprache |

[Alle Meldungen](meldungen.md) führt jeden Code mit seinem Satz auf.

### Die Sprache wählen

Die Sätze sind deutsch, solange Sie nicht Englisch verlangen:

```bash
sdb-reader read --lang en sheet.pdf
SDB_READER_LANG=en sdb-reader read sheet.pdf
```

`SDB_READER_LANG` ist eine Umgebungsvariable: eine Einstellung, die die
Befehlszeile behält, damit Sie die Option nicht wiederholen müssen. Die
Sprache ist immer nur die, die Sie nennen. Die Sprache Ihres Rechners spielt
keine Rolle; dieselbe Datei ergibt deshalb überall dasselbe Ergebnis.

Nicht übersetzt werden die Schlüssel, feste Werte wie `safety-data-sheet`
und die Sätze der Kennzeichnung, die die Worte des Blatts selbst sind.

### Eigene Sätze

Die Sätze kommen aus einem Katalog, einer Textdatei, die jedem Code seinen
Satz zuordnet. Um Meldungen anders zu formulieren oder in einer weiteren
Sprache zu bekommen, schreiben Sie eine Datei wie diese und übergeben sie
mit `--messages`:

```toml
[messages]
"predates-annex-ii" = "Zu alt: überarbeitet am {revised}."
"undated" = "Das Blatt trägt kein Datum."
```

```bash
sdb-reader read --messages my-messages.toml sheet.pdf
```

`{revised}` steht für eine Angabe der Meldung; [Alle Meldungen](meldungen.md)
nennt die Angaben jedes Codes. Ihre Datei kann nur die Codes enthalten, die
Sie formulieren wollen; die übrigen kommen auf Englisch. Ein Code oder eine
Angabe, die das Programm nicht kennt, wird abgelehnt, bevor eine Datei
gelesen wird.

## Mehrere Blätter in einer Datei

Manche Dateien enthalten mehrere vollständige Blätter hintereinander: die
beiden Teile eines Zweikomponentenklebers, die Produkte einer Kombipackung
oder die Fassungen eines Blatts für mehrere Länder. `sheet_count` nennt, wie viele
die Datei enthält; bei den meisten Dateien ist es 1.

Für eine solche Datei gibt der Datensatz zwei Lesungen nebeneinander aus:

- `sheet`, `statements`, `parser` und `findings` gelten für die Datei, mit
  ihren Blättern vereinigt: jeder Code und jedes Piktogramm, das irgendein
  Blatt druckt, das stärkere Signalwort, das neueste Datum. Die Meldung
  `several-sheets` unter `parser.warnings` sagt das.
- `parts` nennt jedes Blatt für sich gelesen, in der Reihenfolge der Datei,
  als wäre es eine eigene Datei, jedes mit seinem eigenen `clp_expected`.
- `oldest_sheet` nennt das Blatt mit dem ältesten Datum; siehe
  [Das älteste Blatt](#das-älteste-blatt).

```json
{
  "sheet_count": 2,
  "sheet": {"revision_date": "2022-07-20", "hazard_statements": {"hazard_codes": ["H315", "H318"], "signal_word": "Gefahr"}},
  "parts": [
    {
      "sheet": {"product_identifier": "Harz", "revision_date": "2022-07-20", "hazard_statements": {"hazard_codes": ["H315"], "signal_word": "Achtung"}},
      "statements": [{"code": "H315", "sheet": "Verursacht Hautreizungen.", "regulation": "Verursacht Hautreizungen."}],
      "warnings": [],
      "findings": []
    },
    {
      "sheet": {"product_identifier": "Härter", "revision_date": "2021-05-03", "hazard_statements": {"hazard_codes": ["H318"], "signal_word": "Gefahr"}},
      "statements": [{"code": "H318", "sheet": "Verursacht schwere Augenschäden.", "regulation": "Verursacht schwere Augenschäden."}],
      "warnings": [],
      "findings": []
    }
  ],
  "oldest_sheet": {"sheet": 2, "date": "2021-05-03", "dated_by": "revision"}
}
```

(Gekürzt: Jedes `sheet` unter `parts` hat alle Felder aus [Das Blatt](#das-blatt).)

Welche Lesung die richtige ist, hängt von der Datei ab, und das Programm
kann es nicht wissen:

- Sind die Blätter die Teile eines Produkts, trägt das Produkt alle ihre
  Kennzeichnungen, und die vereinigte Lesung ist die des Produkts.
- Sind es verschiedene Produkte oder Fassungen, kann die vereinigte Lesung
  Gefahren nennen, die kein einzelnes Blatt nennt, und ihr Datum und ihre
  Version gehören zu keinem einzelnen Blatt. Nehmen Sie dann das Blatt, das
  Sie brauchen, aus `parts`.

Jeder Eintrag enthält `sheet` (mit dem Fingerabdruck `content_hash` des
Texts dieses Blatts), `statements` und `warnings`, was beim Lesen dieses
Blatts auffiel, und nennt seine Länder (`countries`, leer, wo keines erkannt
ist) und sein Produkt (`product_identifier`). Unter `findings` stehen die
Befunde zum Alter dieses Blatts, beurteilt an seinen eigenen Daten wie bei
einer Datei mit diesem einen Blatt: `revised-in-future`, `issued-in-future`,
`undated`, `predates-annex-ii` und `old-format`; die Liste steht auch leer da. Andere
Befunde je Blatt gibt es nicht: Ein Befund gilt dem Produkt, und ob ein
Blatt für sich das Produkt ist, weiß das Programm nicht. Ein späteres Blatt beginnt am Titel „Sicherheitsdatenblatt“ über
seinem Abschnitt 1, damit Datum und Version im Kopf seiner ersten Seite für
es zählen. Eine Änderungsliste, die die Abschnitte nennt, und dasselbe Blatt
noch einmal in einer anderen Sprache sind keine weiteren Blätter.
[Zwei Läufe vergleichen](laeufe-vergleichen.md) vergleicht die Lesung der
Datei, nicht `parts`.

### Das älteste Blatt

Die Lesung der Datei trägt das neueste Datum, das die Datei nennt, und ihre
Befunde zum Alter richten sich danach. Eine Datei, in der neben einem neuen
Harz ein Härter von 2014 steht, gilt deshalb nicht als alt. `oldest_sheet`
nennt das Blatt, nach dem Sie eine solche Datei beurteilen würden:

| Schlüssel | Bedeutung |
| --- | --- |
| `sheet` | die Nummer des Blatts in der Reihenfolge der Datei, ab 1 |
| `date` | sein Datum: das Überarbeitungsdatum, sonst das Ausgabedatum; ein Datum nach dem Tag des Laufs zählt nicht |
| `dated_by` | `revision` oder `issue`: welches der beiden Daten es ist |

Tragen mehrere Blätter dasselbe älteste Datum, zählt das erste; trägt keines
ein Datum, das zählt, steht dort `null`. Eine Datei mit einem Blatt hat kein
`oldest_sheet`. Wessen Datum für Ihr Produkt zählt, entscheiden Sie; die
Lesung der Datei und ihre Befunde bleiben, wie sie sind.

### Was die Blätter übereinander sagen

Das Programm vergleicht die Blätter einer Datei und meldet, was es sieht. Es
wählt keines aus und ändert die vereinigte Lesung nie: Welches Blatt für Ihr
Produkt gilt, wissen nur Sie.

- `different-products` unter `findings`: Die Produktnamen der Blätter sind
  nicht die eines Produkts. Die Teile eines Produkts („… Komponente A“ und
  „… Komponente B“, „… (Harz)“ und „… (Härter)“, Farben, die sich in einer
  Nummer am Ende unterscheiden) sind ein Produkt und werden nicht gemeldet.
  Eine solche Datei ist ein Kombipack oder ein Set, das als Einheit verkauft
  wird, oder eine Datei, die zu etwas anderem gehört als zu dem Produkt,
  unter dem sie abgelegt ist. Ließ sich ein Produktname nicht lesen, wird
  nichts gemeldet, weil es sich nicht sagen lässt.
- `country-editions-differ`: Zwei Blätter tragen denselben Produktnamen und
  gelten für verschiedene Länder, und sie weichen in den genannten Feldern
  ab (Codes der Sätze, Signalwort, Piktogramme, Einstufung).

### Ein Deckblatt

Manche Dateien beginnen mit einem Deckblatt: einer Seite mit dem Titel
„Deckblatt“ oder „Sicherheitsdatenblätter für …“, dem Informationsblatt
eines Kits, einer Liste „Set aus Sicherheitsdatenblättern bestehend aus:“
oder den Angaben eines Landes zu dem Blatt, das folgt. Ein Deckblatt ist kein Blatt. Von ihm wird nichts
gelesen: Kein Datum, keine Version, kein Lieferant und kein Satz des
Datensatzes stammt von ihm, und es steht nicht unter `parts`.

| Schlüssel | Bedeutung |
| --- | --- |
| `cover_page` | `true`, wo vor den Blättern der Datei ein Deckblatt steht |
| `display_term` | das Wort, mit dem das Deckblatt ein Display nennt, wie es gedruckt ist (etwa „Mix-Display“); `null`, wo es kein Deckblatt gibt oder es keines nennt |

Ein Display ist eine Aufstelleinheit, die ein Lieferant mit mehreren
Produkten für den Laden liefert. Eine Datei mit dem Deckblatt eines Displays
gehört zum Display, nicht zu einem seiner Produkte.

## Weitere Teile

| Teil | Enthält |
| --- | --- |
| `file` | Pfad, Name und Größe der Datei |
| `parser.warnings` | was beim Lesen des Blatts auffiel, etwa eine Kennzeichnung, die sich nicht als Bild ansehen ließ; leer, wo nichts auffiel |
| `warnings` | bei einer Datei, die kein deutsches Blatt ist oder sich nicht lesen ließ: dass nichts weiter gelesen wurde; sonst leer |
| `errors` | bei einer Datei, aus der sich kein Text lesen ließ: der Grund; sonst leer |
| `embedded_data` | bei einem PDF mit eingebetteter Datei: siehe [Die eingebettete Datei](eingebettete-datei.md) |
| `raw_text` unter `extraction` | mit `--include-raw-text`: der aus dem PDF gelesene Text |

Die vollständige Beschreibung eines Datensatzes, mit jedem Schlüssel und
seinem Typ, ist ein JSON-Schema, das mit dem Programm ausgeliefert wird;
Programmierer finden es unter [The JSON schema](../api/schema.md).
