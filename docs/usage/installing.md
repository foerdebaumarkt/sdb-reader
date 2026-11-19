# Installing

## What you need

- **Python 3.12 or newer.** The command is a Python program. `python3 --version`
  shows which version you have. Supported is every Python version that is
  still maintained, from 3.12 on.
- **`tesseract` with German language data**, only if you read scanned sheets.
  A scanned sheet is a PDF whose pages are pictures. The program reads such a
  page by text recognition, and `tesseract` is the program that does it. A
  PDF that carries its text needs none.

## Install the command

The package `sdb-reader` is installed from the Python Package Index. Without
a version the newest one is installed; `sdb-reader==<version>` names one.
[CHANGELOG.md](../../CHANGELOG.md) says what each version changed.

With [uv](https://docs.astral.sh/uv/), which also fetches a Python if your
machine lacks one:

```bash
uv tool install sdb-reader
```

With pip, in an environment of its own:

```bash
python3 -m venv sdb-reader-env
sdb-reader-env/bin/pip install sdb-reader
```

With pip the command is then `sdb-reader-env/bin/sdb-reader`. Check that it
runs; the command prints its version:

```bash
sdb-reader --version
```

The command brings two packages with it: `structlog` and `pymupdf-lite`,
the lean distribution of the PDF library PyMuPDF. If the environment already
holds the full `PyMuPDF`, remove it first: both provide the same module, and
two copies of it in one environment overwrite each other.

## Install text recognition

On macOS with Homebrew:

```bash
brew install tesseract tesseract-lang
```

On Debian or Ubuntu:

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-deu
```

On Windows, install Tesseract with the German language data selected and make
sure `tesseract` can be started from the command line.

Tesseract version 5 or later is needed. With an older version the program
reads no scan and says so in its output (`ocr-too-old`). Check the version and
that the German data is there; the second command prints `deu` if it is:

```bash
tesseract --version
tesseract --list-langs | grep -x deu
```

The program is tested with Tesseract 5.5. Which version read a scan is in the
output, under `extraction.tesseract`.

## Licence

`sdb-reader` is free software under the GNU Affero General Public License,
version 3 or later ([LICENSE](../../LICENSE)). You may use it for any
purpose. If you pass it on, or offer a service built on it over a network,
the licence obliges you to offer the source code under the same licence.
