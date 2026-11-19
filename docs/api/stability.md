# What is promised

What a program that uses the library can build on, and where each promise is
written down. The binding text is the spec, in German
([specs/bibliothek.md](../../specs/bibliothek.md),
[specs/sdb-werkzeug.md](../../specs/sdb-werkzeug.md)); this page is its
summary for developers.

## Promised

| What | The promise | Rule |
| --- | --- | --- |
| The exported names | The names the package `sdb_reader` exports are its interface, and only they. Each carries a description. | BIB-1 |
| A stored sheet | A sheet stored with `sheet_to_dict` is read back by `sheet_from_dict` as the sheet it was. One stored in another shape is refused, not guessed at. | BIB-21 |
| A file is read by its content | `read_sheet` takes the path and nothing a caller knows about the file. A reading does not name its file. | BIB-2 |
| Stored texts | A text stored with `extraction_to_dict` can be read back and gives the reading the file gave, also when an earlier version stored it. | BIB-3 |
| Stage versions | `EXTRACTION_VERSION` rises with every change after which the same PDF can give another text, `PARSER_VERSION` with every change after which the same text can give another reading. Neither ever falls. | BIB-4, BIB-5 |
| Message codes | The codes and the names of their values are part of the interface. The library lists them (`MESSAGE_CODES`). A code never changes its meaning, and one that goes is not given out again. | BIB-10 |
| Language | The language of a sentence is the one the caller names, German by default. It is never taken from the machine. | BIB-11 |
| No decision by wording | The library never decides by the sentence of a message, and a caller need not either. | BIB-12 |
| The output's description | What `read` prints for a file is described by the shipped JSON Schema. The command prints no key the schema does not name. | SDW-16 |
| The choice among sheets | `current_state` follows a fixed order and says why it chose. | BIB-6 to BIB-9 |
| No clock | The library does not read the date. What depends on today takes it as an argument, `today`, and without it no result depends on the day. | BIB-19 |
| The output's schema | The schema is part of the promise, not only a description: a change that makes a formerly valid record invalid, or drops a key, is breaking. | BIB-15 |

Each of these has tests that fail when it is broken. The tests name the rule
they hold, and a test of the specs fails when a rule has none.

## Not promised

- **Submodules.** What is reached only through a submodule, such as
  `sdb_reader.parser` or `sdb_reader.layout`, can change without notice. That
  includes the parts that ask a language model (BIB-1).
- **Sentences.** The wording of a message can change with any release. Only
  its code and values are fixed.
- **The report of `show`.** What `sdb-reader show` prints is written for
  people: its wording and its layout can change with any release (SDW-41). A
  program takes the record of `read`.
- **What a sheet reads as.** The reading of a given PDF can change when a
  stage version rises: that is what the versions are for. A release that
  changes what the same file gives says so in the changelog.
- **Text recognition.** A sheet read by `tesseract` depends on the version of
  that program on the machine. It is not part of `extraction_stage()`.

## How the library changes

**Versions (BIB-13).** From version 1.0 on, versions follow semantic
versioning:

| Part | Rises with |
| --- | --- |
| major | a breaking change to an exported name, a message code or its values, the JSON schema, or the command line's options and exit codes |
| minor | an addition, and every rise of `EXTRACTION_VERSION` or `PARSER_VERSION`, since a caller has to read again |
| patch | a fix that changes no reading |

Before 1.0 a minor version may break. The changelog says so under
"Breaking".

**Notice (BIB-14).** An exported name that is to go stays for one minor
version and warns with `DeprecationWarning` when it is used, before the next
major version removes it.

**Python (BIB-16).** Every Python version that is still maintained at the
time of a release is supported, from 3.12 on: at present 3.12 to 3.15. A
version leaves when its maintenance ends and a new one joins when it is
released; neither is a breaking change. The package names the oldest in
`requires-python` and each in its classifiers, and the tests run with every
one of them.

**Fixes (BIB-17).** Only the newest release gets fixes. An older one is not
maintained; a program that needs it stays on the tag it builds on.

**The changelog (BIB-18).** Releases are tags of the repository.
[CHANGELOG.md](../../CHANGELOG.md) says for each one what changes for someone
who uses the command or the library. It names every breaking change under
"Breaking" and every rise of a stage version, with what to do about readings
and texts kept from before. What came since the last release stands under
"Unreleased"; before the first release that section says what the first
version offers and which stage versions it reads with.

**Releases (BIB-23).** A release is a tag `v<version>` of the repository,
and the package of that version on the Python Package Index is built from
it by the repository's own workflow, never by hand. The first published
version is 0.9.0.

**Documentation (BIB-22).** The documentation is at
<https://foerdebaumarkt.github.io/sdb-reader/>, one edition per released
version: `latest/` is the newest, `<version>/` the one of a version, and
`versions.html` lists them. An edition holds these pages, the changelog and
the [reference](../reference.md) of the exported names, built from its tag,
and does not change afterwards.

Pin the version you build on, and read the changelog before moving to
another.
