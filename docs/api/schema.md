# The JSON schema

What `sdb-reader read` prints for each file, and what `reading_to_dict`
returns, is described by a JSON Schema (draft 2020-12) that ships in the
package as `read_record.schema.json`: every key, its type, which keys can be
missing, and which values are fixed lists.

Load it from the installed package:

```python
import json
from importlib import resources

schema = json.loads(
    resources.files("sdb_reader").joinpath("read_record.schema.json").read_text("utf-8")
)

assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
```

The schema describes one record of the array the command prints. The command
adds the part `file` to what `reading_to_dict` returns; the schema asks for
it:

```python
assert "file" in schema["required"]
```

To validate, use any validator for draft 2020-12, such as the package
`jsonschema`, which is not a dependency of the library:

```python
import jsonschema

record = {
    "file": {
        "path": str(path),
        "filename": path.name,
        "size_bytes": path.stat().st_size,
    },
    **reading_to_dict(reading),
}
jsonschema.Draft202012Validator(schema).validate(record)
```

Where the output is fixed, the schema allows no other keys, so a key your
program reads and the schema does not know is a mistake in your program. The
test suite validates real output against the schema, so the two cannot drift
apart.

The fixed lists in the schema are the kinds of document, the classification
of section 2, the codes of the findings, the sections and the pictograms.

A second schema beside it, `ask_record.schema.json`, describes what
`sdb-reader ask` writes for each file; see
[Asking a language model](../usage/asking.md).
