# The references for pictograms drawn on a label

`src/sdb_reader/label_images.py` names each red-framed diamond in a label by
comparing it with references of the nine GHS pictograms
(`src/sdb_reader/pictogram_references.json`). This directory holds what the
references are made from and the tool that makes them. It is not part of the
installed package.

| Here | What it is |
| --- | --- |
| `drawings/GHS01.svg` … `GHS09.svg` | the nine pictograms as drawn on Wikimedia Commons, files `GHS-pictogram-explos.svg`, `-flamme`, `-rondflam`, `-bottle`, `-acid`, `-skull`, `-exclam`, `-silhouette`, `-pollu`, marked there as public domain |
| `references.py` | renders each drawing at two widths, thickens its lines step by step, and writes the fingerprints to `pictogram_references.json` |

Nothing in the references comes from a safety data sheet. A sheet prints the
pictograms smaller, bolder or blurred; the thickened renderings stand in for
that.

```bash
.venv/bin/python tools/pictograms/references.py
```

A new or changed drawing, or a change to `references.py`, changes the
references: raise `LABEL_IMAGES_VERSION` (`docs/contributing/stage-versions.md`).
