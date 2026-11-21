# Messages and catalogs

## A message is a code and its values

Whatever the library notes about a file is a `Message`: the warnings of
reading the text, of judging the file and of parsing the sheet, the reasons
a file could not be read, and the findings. A message has a `code` and
`params`, the values that code names. It carries no sentence.

```python
from sdb_reader import MESSAGE_CODES, Message

derived = Message("pictograms-derived", {"pictograms": ["GHS07"]})

assert derived.code == "pictograms-derived"
assert derived.params == {"pictograms": ["GHS07"]}
assert derived in reading.parser_result.warnings
```

`MESSAGE_CODES` maps every code to the names of its values. A `Message` with
a code that is not in it, or with other values than the code names, cannot
be made:

```python
assert MESSAGE_CODES["pictograms-derived"] == ("pictograms",)
assert MESSAGE_CODES["undated"] == ()

try:
    Message("no-such-code")
except ValueError as error:
    assert "unknown message code" in str(error)
```

**Decide by the code, never by a sentence.** The code is the same in every
language and keeps its meaning; a sentence can be reworded with any release.
[All messages](../usage/messages.md) lists the codes with their sentences.

```python
parser_codes = {message.code for message in reading.parser_result.warnings}

if "pictograms-derived" in parser_codes:
    ...  # the label named no pictogram; they follow from the H codes
```

## Sentences come from a catalog

A `Catalog` holds the sentences of one language. `shipped_catalog` gives one
the package ships, German unless you name another:

```python
from sdb_reader import shipped_catalog

german = shipped_catalog()
english = shipped_catalog("en")

assert german.render(derived) == (
    "Piktogramme aus den H-Sätzen abgeleitet, das Blatt nennt keine: GHS07"
)
assert english.render(derived) == (
    "Pictograms derived from the H statements, the sheet names none: GHS07"
)
```

The language is always the one you name. It is never taken from the machine,
so the same file gives the same output everywhere. A language without a
shipped catalog raises `ValueError`.

`catalog.to_dict(message)` gives the form the command prints, with all three
parts:

```python
assert english.to_dict(derived) == {
    "code": "pictograms-derived",
    "params": {"pictograms": ["GHS07"]},
    "message": "Pictograms derived from the H statements, the sheet names none: GHS07",
}
```

`reading_to_dict` words every message with the catalog you pass:

```python
from sdb_reader import reading_to_dict

record = reading_to_dict(reading, catalog=english)

[noted] = [w for w in record["parser"]["warnings"] if w["code"] == derived.code]
assert noted["message"] == english.render(derived)
```

## A catalog of your own

A catalog is a TOML file with one table, `[messages]`, that gives codes their
sentences. `{name}` stands for a value of the message. `load_catalog` reads
one:

```python
from sdb_reader import load_catalog

own_file = path.with_name("kurz.toml")
own_file.write_text(
    '[messages]\n"pictograms-derived" = "Piktogramme ergänzt: {pictograms}"\n',
    encoding="utf-8",
)
own = load_catalog(own_file)

assert own.render(derived) == "Piktogramme ergänzt: GHS07"
assert own.language == "kurz"
```

A catalog of your own need not be complete. A code it lacks is said in
English:

```python
assert own.render(Message("undated")) == english.render(Message("undated"))
```

A message that counts something may have two sentences, `one` for exactly
one and `other` for any other number, and a catalog says in its `[format]`
table how it writes a date. The values of the message stay as they are: a
date is ISO there in every language.

```python
own_file.write_text(
    '[format]\ndate = "%d.%m.%Y"\n\n[messages]\n'
    '"several-sheets" = { one = "Ein Blatt.", other = "{count} Blätter." }\n'
    '"old-format" = "Alter Aufbau, Stand {revised}."\n',
    encoding="utf-8",
)
own = load_catalog(own_file)

assert own.render(Message("several-sheets", {"count": 1})) == "Ein Blatt."
assert own.render(Message("several-sheets", {"count": 3})) == "3 Blätter."
old = Message("old-format", {"revised": "2022-03-01"})
assert own.render(old) == "Alter Aufbau, Stand 01.03.2022."
assert own.to_dict(old)["params"] == {"revised": "2022-03-01"}
```

Which messages count, and which of their values, is fixed by the library:
`pages` in `pages-read-by-ocr`, `no-text-layer` and `no-text`, `sections` in
`safety-information`, `count` in `several-sheets`. The dates are `revised` in
`predates-annex-ii` and `old-format`. Two sentences on any other message are
refused. Without `[format]` a date stands as the message carries it.

A code or a placeholder the library does not know is refused with
`ValueError` when the file is loaded, since nobody would ever see that
sentence. To add a language, copy a shipped catalog from the package's
`messages_data/` directory and translate the sentences
([Adding a language](../contributing/adding-a-language.md)).

## Storing a message

Store code and values, not the sentence: `to_dict` gives them, `from_dict`
reads them back. Render the sentence where a person reads it.

```python
stored = derived.to_dict()

assert stored == {"code": "pictograms-derived", "params": {"pictograms": ["GHS07"]}}
assert Message.from_dict(stored) == derived
```
