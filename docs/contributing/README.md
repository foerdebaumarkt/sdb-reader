# Contributing to the reader

For whoever changes the reader: fixes a reading error, adds a rule, a
language, a test. [CONTRIBUTING.md](../../CONTRIBUTING.md) is the short
entry; these pages are the detail. Start with
[How it works](../how-it-works.md) for the lay of the land.

| Page | What it covers |
| --- | --- |
| [Setting up and the checks](setup.md) | the environment and every check a pull request has to pass |
| [Changes and the specs](changes-and-specs.md) | how a change runs, and how to read the German specs |
| [Stage versions](stage-versions.md) | when to raise `EXTRACTION_VERSION` and `PARSER_VERSION`, and the fingerprints |
| [Measuring a change](measuring.md) | how a change to reading or parsing is measured before it is merged |
| [Adding a language](adding-a-language.md) | what is bound to German today and what another language would need |
| [CI/CD](ci-cd.md) | the workflows and what each proves |
| [Releasing](releasing.md) | how a version is released, the documentation site, and what is set up once outside the repository |
| [Editor-agnostic repositories](editor-agnostic.md) | why no editor configuration is committed |

The copies of the CLP Regulation in the library, and the tools that keep
them current, are described in [tools/clp/README.md](../../tools/clp/README.md).

Issues and pull requests may be written in German or English.
