# Ein Sprachmodell fragen

## Wofür

`read` fragt nie ein Sprachmodell. `ask` tut es: Es schickt den Anfang jedes
Blatts an ein Modell, fragt, was im Blatt steht, und behält die Antwort, je
Datei einen Datensatz. Es vergleicht nichts. Die Antworten neben eine Lesung
zu stellen ist ein eigener Schritt, siehe
[Zwei Läufe vergleichen](laeufe-vergleichen.md).

Die Antwort des Modells ist eine zweite Meinung zum Ansehen. Sie ändert nie
eine Lesung, und wo die beiden abweichen, ist eine Stelle zum Nachsehen,
kein bewiesener Fehler. Modelle irren, und oft irrt das Modell.

Das Modell wird für sich gefragt. Es bekommt den Text der Datei, nicht das,
was das Programm daraus gelesen hat, und kann deshalb auch sehen, was das
Programm abgeschnitten oder falsch gelesen hat.

## Was wohin geschickt wird

**Der Text des Blatts wird an die Adresse geschickt, die Sie angeben.** Ist
das ein Dienst im Internet, verlässt der Text Ihren Rechner. Ein Modell, das
auf dem eigenen Rechner läuft, behält ihn dort.

Geschickt wird der Text der Datei von seinem Anfang bis vor die Überschrift
von Abschnitt 3, wo die Liste der Inhaltsstoffe beginnt: der Kopf der ersten
Seite, Abschnitt 1 mit dem Lieferanten und Abschnitt 2 mit der
Kennzeichnung. Die Sätze einzelner Inhaltsstoffe in Abschnitt 3 gehören
nicht zur Kennzeichnung, deshalb endet der Text davor. Hat eine Datei keine
solche Überschrift, gehen stattdessen ihre ersten Seiten hinaus, vier, wenn
Sie nichts anderes angeben.

Hält eine Datei mehrere Blätter, geht jedes für sich hinaus, siehe
[Mehrere Blätter in einer Datei](#mehrere-blätter-in-einer-datei).

Geschickt wird nur eine Datei, die das Programm als deutsches
Sicherheitsdatenblatt einstuft. Für jede andere Datei und für eine Datei
ohne Text wird nichts geschickt.

Die Adresse muss die Chat-Schnittstelle sprechen, die OpenAI eingeführt hat
und die die meisten lokalen Programme und Dienste anbieten.

## Aufruf

```bash
sdb-reader ask --endpoint http://localhost:11434/v1 --model some-model sheet.pdf
sdb-reader ask sheets/ --output answers.jsonl --jobs 4 --retries 3
```

| Option | Wirkung |
| --- | --- |
| `--endpoint ADRESSE` | wo das Modell gefragt wird; nötig |
| `--model NAME` | der Name des Modells an dieser Adresse; nötig |
| `--pages N` | wie viele Seiten des PDFs das Modell bekommt, wenn die Datei keine Überschrift von Abschnitt 3 hat; ohne Angabe 4 |
| `--timeout SEKUNDEN` | wie lange auf eine Antwort gewartet wird; ohne Angabe 300 |
| `--retries N` | eine Anfrage bis zu N-mal neu stellen, wenn der Dienst überlastet oder kurz nicht erreichbar ist, mit wachsender Wartezeit von höchstens einer Minute; ohne Angabe 0 |
| `--preset NAME` | eine Voreinstellung für eine bekannte Modellfamilie, siehe [Das Nachdenken abschalten](#das-nachdenken-abschalten) |
| `--presets DATEI` | die Voreinstellungen aus einer eigenen TOML-Datei nehmen statt aus dem Programm |
| `--list-presets` | die Voreinstellungen ausgeben und enden; braucht weder Datei noch Endpunkt |
| `--request-json JSON` | ein JSON-Objekt, dessen Felder in jede Anfrage übernommen werden, für das, was ein Dienst über das Übliche hinaus braucht, etwa `'{"seed": 7}'`; es gilt über einer Voreinstellung und kann die Temperatur setzen, die sonst 0 ist, aber weder `model` noch `messages` |
| `--output DATEI`, `--resume`, `--jobs N`, `--exclude-from DATEI` | für einen Lauf über viele Dateien, siehe [Einen ganzen Bestand lesen](bestand.md) |
| `--indent N`, `--lang`, `--messages` | wie bei `read` |

Fünf Umgebungsvariablen stehen für Optionen oder tragen, was nicht auf die
Befehlszeile gehört:

| Variable | Steht für |
| --- | --- |
| `SDB_READER_ENDPOINT` | `--endpoint` |
| `SDB_READER_MODEL` | `--model` |
| `SDB_READER_PRESET` | `--preset` |
| `SDB_READER_REQUEST_JSON` | `--request-json` |
| `SDB_READER_API_KEY` | den Schlüssel, den ein Dienst verlangt; er wird nur von hier gelesen, damit er weder im Verlauf Ihrer Befehlszeile noch in einem Datensatz landet |

Jedes Blatt kostet eine Anfrage; eine Datei mit mehreren Blättern kostet
so viele, wie sie Blätter hält. Eine Anfrage, die scheitert, wird nicht
wiederholt, außer mit `--retries`; ein Fehler, der nicht von allein vergeht,
etwa ein falscher Schlüssel, scheitert sofort.

## Was zurückkommt

```json
[
  {
    "file": {"path": "/data/reiniger.pdf", "filename": "reiniger.pdf", "size_bytes": 181034},
    "kind": "safety-data-sheet",
    "asked": true,
    "model": "some-model",
    "sheet_count": 1,
    "sent": "before-section-3",
    "stage": "2+pymupdf-2.1",
    "question": "5f0c1d9a2b7e",
    "usage": {"prompt_tokens": 1210, "completion_tokens": 190},
    "reading": {
      "revision_date": "2022-07-20",
      "revision_date_named": "20.07.2022",
      "hazard_statements": {
        "hazard_codes": ["H315", "H319"],
        "precautionary_codes": ["P102", "P305+P351+P338"],
        "supplemental_codes": [],
        "hazard_text": "H315: Verursacht Hautreizungen.\nH319: Verursacht schwere Augenreizung.",
        "precautionary_text": "P102: Darf nicht in die Hände von Kindern gelangen.\nP305+P351+P338: BEI KONTAKT MIT DEN AUGEN: …",
        "supplemental_text": null
      },
      "contact_info": {
        "supplier_name": "Muster GmbH",
        "supplier_address": "Musterweg 1, 12345 Musterstadt",
        "supplier_phone": "0555-0142-0",
        "supplier_email": "info@muster.example",
        "supplier_website": null
      }
    },
    "answer": {"supplier": {"name": "Muster GmbH"}, "revision_date": "20.07.2022"}
  }
]
```

| Feld | Bedeutung |
| --- | --- |
| `kind` | was die Datei ist, wie `read` sie einstuft |
| `asked` | `true`, wenn das Modell gefragt wurde; `false` für eine Datei, die kein deutsches Sicherheitsdatenblatt ist oder keinen Text hat, mit dem Grund als Meldung unter `reason` und sonst nichts |
| `model` | der Name des Modells |
| `sheet_count` | wie viele Blätter die Datei hält; fast immer 1 |
| `sent` | was das Modell bekam: `before-section-3` für den Text bis vor die Überschrift von Abschnitt 3, `pages` für die ersten Seiten der Datei; bei mehreren Blättern `sheet`, wenn eines ganz hinausging |
| `stage` | die Lese-Stufe, aus der der Text stammt; zwei Läufe aus verschiedenen Stufen haben womöglich verschiedenen Text geschickt |
| `question` | ein Fingerabdruck der Frage, die für jede Datei dieselbe ist; Antworten mit einem anderen Fingerabdruck galten einer anders formulierten Frage |
| `preset` | der Name der Voreinstellung, wenn eine gewählt war |
| `request` | die Felder, die zur Anfrage dazukamen: die der Voreinstellung und darüber die aus `--request-json`, wenn es welche gab |
| `usage` | wie viele Token die Anfragen zu dieser Datei gekostet haben, wenn der Dienst es nennt |
| `reading` | die Antwort unter den Namen, die `read` für ein Blatt benutzt, siehe [Die Ausgabe verstehen](ausgabe.md): die Codes und Texte der H-, P- und EUH-Sätze, der Lieferant, das Überarbeitungsdatum |
| `answer` | die Antwort des Modells, wie es sie gab; nur bei einer Datei, die ein Blatt ist |
| `parts` | nur bei einer Datei mit mehreren Blättern: je Blatt, was hinausging und was das Modell dazu sagte |

Nach Signalwort, Piktogrammen und Einstufung wird das Modell nicht gefragt;
`reading` enthält nur, wonach gefragt wird. Die Form eines Datensatzes ist in
einem Schema festgehalten, das mit dem Programm ausgeliefert wird,
`sdb_reader/ask_record.schema.json`.

## Mehrere Blätter in einer Datei

Manche Dateien enthalten mehrere vollständige Blätter hintereinander, etwa
für die beiden Teile eines Zweikomponentenklebers. `ask` fragt dann für
jedes Blatt einzeln, mit dem Text dieses Blatts bis vor dessen eigene
Überschrift von Abschnitt 3; hat ein Blatt keine, geht es ganz hinaus. Wo
ein Blatt beginnt, entscheidet dieselbe Regel wie bei `read`: Beide zählen
für jede Datei gleich viele Blätter, und ein späteres Blatt beginnt am Titel
über seinem Abschnitt 1, sodass das Modell den Kopf seiner ersten Seite
sieht. Ein Deckblatt vor den Blättern geht nie hinaus, auch wenn dahinter
nur ein Blatt steht.

Der Datensatz enthält dann beides, jedes Blatt einzeln und alle vereinigt:

```json
{
  "sheet_count": 2,
  "sent": "before-section-3",
  "usage": {"prompt_tokens": 2300, "completion_tokens": 410},
  "reading": {"hazard_statements": {"hazard_codes": ["H315", "H318"]}},
  "parts": [
    {
      "sent": "before-section-3",
      "usage": {"prompt_tokens": 1200, "completion_tokens": 190},
      "reading": {"hazard_statements": {"hazard_codes": ["H315"]}},
      "answer": {"hazard_statements": "H315: Verursacht Hautreizungen."}
    },
    {
      "sent": "before-section-3",
      "usage": {"prompt_tokens": 1100, "completion_tokens": 220},
      "reading": {"hazard_statements": {"hazard_codes": ["H318"]}},
      "answer": {"hazard_statements": "H318: Verursacht schwere Augenschäden."}
    }
  ]
}
```

- `parts` enthält je Blatt, in der Reihenfolge der Datei, was hinausging
  (`sent`), was es gekostet hat (`usage`), die Antwort (`answer`) und die
  Antwort in der Form einer Lesung (`reading`). Das Beispiel ist gekürzt;
  jedes `reading` hat alle Felder.
- `reading` auf oberster Ebene vereinigt die Blätter so, wie `read` es für
  eine solche Datei tut: die Codes aller Blätter, jeder einmal, in der
  Reihenfolge, in der sie zuerst vorkommen, und die Sätze nacheinander, je Satz eine Zeile.
  Lieferant und Überarbeitungsdatum sind die des ersten Blatts.
- `usage` auf oberster Ebene ist die Summe, `sent` ist `sheet`, sobald ein
  Blatt ganz hinausging, und `answer` gibt es dort nicht.
- Scheitert die Anfrage zu einem der Blätter, ist die ganze Datei
  gescheitert und bekommt keinen Datensatz.

`diff` vergleicht das vereinigte `reading`.

## Das Nachdenken abschalten

Manche Modelle denken nach, bevor sie antworten. Für diese Aufgabe bringt
das nichts: Das Modell soll von der Seite abschreiben, nicht schließen. In
einem Lauf über 3.000 Blätter kostete das Fragen ohne Nachdenken ein Drittel
und dauerte ein Viertel so lang, und das Modell machte weniger eigene
Fehler. Wie man das Nachdenken abschaltet, heißt bei jedem Dienst anders.
Für die Modellfamilien, die das Programm kennt, liefert es die nötigen
Felder als Voreinstellung mit:

```bash
sdb-reader ask --preset deepseek-no-reasoning sheets/ --output answers.jsonl
sdb-reader ask --list-presets
```

<!-- presets:begin -->
| Name | Wofür | Was in die Anfrage kommt | Gemessen mit |
| --- | --- | --- | --- |
| `deepseek-no-reasoning` | DeepSeek: das Nachdenken des Modells abschalten | `{"thinking": {"type": "disabled"}}` | `deepseek-flash`, 2026-11-18 |
| `ollama-no-reasoning` | Ollama: das Nachdenken eines Modells abschalten, das nachdenkt | `{"reasoning_effort": "none"}` | `qwen3.8:27b-mlx`, 2026-11-18 |
<!-- presets:end -->

Eine Voreinstellung kann veralten: Ein Dienst kann ändern, was er annimmt.
Die Spalte „Gemessen mit“ nennt das Modell und den Tag, an dem die
Voreinstellung mit diesem Programm gemessen wurde; „nicht gemessen“ heißt,
dass sie nach der Dokumentation des Dienstes geschrieben ist. Ob das
Nachdenken wirklich aus ist, zeigt `usage`: Ein Modell, das nachdenkt,
schickt ein Vielfaches an Token zurück.

Für ein anderes Modell nennen Sie die Felder selbst mit `--request-json`
oder legen eine eigene Datei an und geben sie mit `--presets` an. Sie hat
je Voreinstellung eine Tabelle:

```toml
[my-service]
description = "My service: no reasoning"
request = { reasoning = false }
omit = ["temperature"]
```

`request` nennt die Felder, die in jede Anfrage kommen, `omit` die, die
wegfallen; weglassen lässt sich nur `temperature`, für einen Dienst, der
keine annimmt. `--request-json` gilt über der Voreinstellung.

## Das Datum

Das Modell muss das Überarbeitungsdatum genau so nennen, wie das Blatt es
druckt, und was es nennt, zählt nur, wenn dieser Text in dem steht, was es
bekommen hat, und ein Datum ist. Es kann also kein Datum erfinden.
`revision_date` enthält ein Datum, das zählt; `revision_date_named` enthält,
was das Modell geschrieben hat, auch wenn es nicht zählte.

## Die Antworten behalten

Eine Anfrage kostet Zeit und bei einem Dienst Geld. Ein Vergleich kostet
beides nicht. Fragen Sie deshalb einmal, behalten Sie die Datei und
vergleichen Sie, so oft Sie wollen:

```bash
sdb-reader ask sheets/ --output answers.jsonl --jobs 4 --retries 3
sdb-reader ask sheets/ --output answers.jsonl --jobs 4 --retries 3 --resume
```

- Der zweite Aufruf setzt einen abgebrochenen Lauf fort und fragt zu keinem
  Blatt zweimal.
- Dieselben Antworten dienen jeder späteren Fassung des Programms: die
  Blätter neu lesen und vergleichen, ohne neu zu fragen.
- Ein Modell antwortet nicht zweimal gleich. Die Antworten mehrerer Läufe
  oder mehrerer Modelle, jede in einer eigenen Datei, lassen sich
  miteinander vergleichen, und was zwei von ihnen gleich sagen, wiegt mehr.

Bei einem Lauf über mehr als eine Datei zählt die Zeile am Ende zusammen,
was gefragt wurde und was es gekostet hat:

```text
[sdb-reader] Dateien: 5000; früher erledigt: 0; ausgenommen: 500; gefragt: 4300; gescheitert: 3; Token gesendet: 5200000, empfangen: 1050000
```

Was das in Geld ist, rechnet der Befehl nicht aus; die Preise nennt der
Dienst. Ein Probelauf über hundert Blätter zeigt, was ein Blatt im Mittel
kostet und wie lange es dauert, bevor der ganze Bestand läuft.

## Womit es erprobt ist

Das Fragen ist mit DeepSeek V4 Flash (`deepseek-flash`) gemessen, beim
Anbieter über dessen Schnittstelle, in einem Lauf über 3.000 Blätter mit
acht Anfragen zugleich:

| Nachdenken | Token je Blatt, gesendet | Token je Blatt, empfangen | Dauer für 3.000 Blätter |
| --- | --- | --- | --- |
| aus (`--preset deepseek-no-reasoning`) | etwa 2.100 | etwa 250 | 18 Minuten |
| an | etwa 2.200 | etwa 2.000 | 72 Minuten |

Auf dem eigenen Rechner ist es mit Qwen 3.8 (`qwen3.8:27b-mlx`) unter Ollama
gemessen, an zehn Blättern nacheinander, mit `--preset ollama-no-reasoning`:
etwa 2.100 Token gesendet und etwa 260 empfangen je Blatt, vier Sekunden je
Blatt auf einem Rechner mit Apple-Chip. Seine Antworten wichen bei keinem der
zehn Blätter von denen von DeepSeek V4 Flash ab.

Ein Modell muss deutschen Text lesen, auf Anweisung reines JSON liefern und
einige tausend Wörter aufnehmen können. Kleinere Modelle
sind nicht erprobt; ob eines taugt, zeigt ein Versuch mit Blättern, deren
Inhalt Sie kennen.

## Ein Blatt kann dem Modell nichts befehlen

Ein Blatt ist eine Datei aus fremder Hand, und sein Text geht an das Modell.
Damit ein Text darin nicht als Anweisung gilt, steht er zwischen zwei
Markierungen mit einer Kennung, die für jede Anfrage neu erzeugt wird und
die das Blatt nicht kennen kann, und die Anweisung sagt dem Modell, dass
alles dazwischen ein Dokument ist. Wichtiger ist, was eine Antwort bewirken
kann: nichts, außer behalten und verglichen zu werden. Sie ändert keine
Lesung, löst nichts aus, und ein Datum zählt nur, wenn es im Blatt steht.

## Exit-Codes

| Exit-Code | Bedeutung |
| --- | --- |
| 0 | jede Anfrage wurde beantwortet |
| 1 | eine Anfrage ist gescheitert oder eine Datei hat keinen Text; sie steht auf der Fehlerausgabe, die übrigen stehen im Ergebnis |
| 2 | Endpunkt oder Modell fehlt, `--request-json` ist kein JSON-Objekt oder nennt `model` oder `messages`, eine Voreinstellung gibt es nicht, oder ein Pfad ist weder Datei noch Ordner; es wurde nichts gelesen |
| 130 | der Lauf wurde mit Strg-C abgebrochen |
