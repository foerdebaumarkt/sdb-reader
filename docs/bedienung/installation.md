# Installation

## Was Sie brauchen

- **Python 3.12 oder neuer.** Der Befehl ist ein Python-Programm. `python3 --version`
  zeigt, welche Version Sie haben. Unterstützt wird jede Python-Version, die
  noch gepflegt wird, von 3.12 an.
- **`tesseract` mit deutschen Sprachdaten**, nur wenn Sie gescannte Blätter
  lesen. Ein gescanntes Blatt ist ein PDF, dessen Seiten Bilder sind. Eine
  solche Seite liest das Programm per Texterkennung, und `tesseract` ist das
  Programm, das sie ausführt. Ein PDF, das seinen Text mitbringt, braucht es
  nicht.

## Den Befehl installieren

Das Paket `sdb-reader` wird aus dem Python Package Index installiert. Ohne
Angabe einer Version kommt die neueste; `sdb-reader==<Version>` nennt eine
bestimmte. [CHANGELOG.md](../../CHANGELOG.md) sagt, was jede Version geändert
hat.

Mit [uv](https://docs.astral.sh/uv/), das auch ein Python holt, wenn auf
Ihrem Rechner keines ist:

```bash
uv tool install sdb-reader
```

Mit pip, in einer eigenen Umgebung:

```bash
python3 -m venv sdb-reader-env
sdb-reader-env/bin/pip install sdb-reader
```

Mit pip heißt der Befehl dann `sdb-reader-env/bin/sdb-reader`. Prüfen Sie,
dass er läuft; der Befehl nennt seine Version:

```bash
sdb-reader --version
```

Der Befehl bringt zwei Pakete mit: `structlog` und `pymupdf-lite`, die
schlanke Ausgabe der PDF-Bibliothek PyMuPDF. Enthält die Umgebung schon das
volle `PyMuPDF`, entfernen Sie es vorher: Beide liefern dasselbe Modul, und
zwei Fassungen davon in einer Umgebung überschreiben einander.

## Die Texterkennung installieren

Unter macOS mit Homebrew:

```bash
brew install tesseract tesseract-lang
```

Unter Debian oder Ubuntu:

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-deu
```

Unter Windows installieren Sie Tesseract mit ausgewählten deutschen
Sprachdaten und sorgen dafür, dass sich `tesseract` von der Befehlszeile
starten lässt.

Nötig ist Tesseract ab Version 5. Mit einer älteren Version liest das Programm
keinen Scan und sagt das in der Ausgabe (`ocr-too-old`). Prüfen Sie die Version
und dass die deutschen Daten da sind; der zweite Befehl gibt dann `deu` aus:

```bash
tesseract --version
tesseract --list-langs | grep -x deu
```

Getestet ist das Programm mit Tesseract 5.5. Welche Version einen Scan gelesen
hat, steht in der Ausgabe unter `extraction.tesseract`.

## Lizenz

`sdb-reader` ist freie Software unter der GNU Affero General Public License,
Version 3 oder später ([LICENSE](../../LICENSE)). Sie dürfen es zu jedem
Zweck benutzen. Wenn Sie es weitergeben oder einen Dienst, der darauf
aufbaut, über ein Netz anbieten, verpflichtet die Lizenz Sie, den Quelltext
unter derselben Lizenz anzubieten.
