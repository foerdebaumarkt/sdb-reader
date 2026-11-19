# Reference

Every name the package `sdb_reader` exports, with its signature, its fields
and its description: the interface the library promises
([What is promised](api/stability.md)), and nothing beside it. What is
reached only through a submodule is not listed here and can change without
notice.

The descriptions are the ones in the code. The pages under
[Using the library](api/README.md) explain how the names work together; the
sections below follow them.

```{eval-rst}
.. py:module:: sdb_reader
```

## Reading a file

What `read_sheet` and its relatives give back is described in [A reading and its parts](api/reading.md).

```{eval-rst}
.. autofunction:: read_sheet

.. autofunction:: extract_pdf_text

.. autofunction:: read_extraction

.. autoclass:: SheetReading
   :members:
   :undoc-members:

.. autoclass:: Verification
   :members:
   :undoc-members:

.. autoclass:: DocumentKind
   :members:
   :undoc-members:

.. autoclass:: ParsedSheet
   :members:
   :undoc-members:

.. autoclass:: SheetPart
   :members:
   :undoc-members:

.. autoclass:: ExtractionResult
   :members:
   :undoc-members:

.. autoexception:: ExtractionError
```

## A sheet

The parts of a parsed sheet.

```{eval-rst}
.. autoclass:: SafetyDataSheet
   :members:
   :undoc-members:

.. autoclass:: HazardStatements
   :members:
   :undoc-members:

.. autoclass:: ContactInfo
   :members:
   :undoc-members:

.. autoclass:: StatedClassification
   :members:
   :undoc-members:

.. autoclass:: Section
   :members:
   :undoc-members:
```

## Keeping readings and texts

See [Keeping texts](api/stored-texts.md) and [The JSON schema](api/schema.md).

```{eval-rst}
.. autofunction:: reading_to_dict

.. autofunction:: sheet_to_dict

.. autofunction:: sheet_from_dict

.. autofunction:: verification_to_dict

.. autofunction:: extraction_to_dict

.. autofunction:: extraction_from_dict

.. autofunction:: extraction_stage
```

## Judging a sheet

See [Judging a sheet](api/judging.md).

```{eval-rst}
.. autofunction:: sheet_findings

.. autofunction:: classification

.. autoclass:: Classification
   :members:
   :undoc-members:

.. autofunction:: requires_sheet

.. autofunction:: contradicts_label

.. autofunction:: euh_outside_label

.. autofunction:: predates_annex_ii

.. autofunction:: predates_clp
```

## Statements and pictograms

See [Statements and pictograms](api/statements.md).

```{eval-rst}
.. autofunction:: label_statements

.. autoclass:: StatementWording
   :members:
   :undoc-members:

.. autofunction:: canonical_text

.. autofunction:: normalize_statements

.. autofunction:: tidy_statements

.. autofunction:: render_statements

.. autofunction:: pictograms_for
```

## Messages and catalogs

See [Messages and catalogs](api/messages.md).

```{eval-rst}
.. autoclass:: Message
   :members:
   :undoc-members:

.. autoclass:: Catalog
   :members:
   :undoc-members:

.. autofunction:: shipped_catalog

.. autofunction:: load_catalog
```

## Choosing the current sheet

See [Which sheet is the current one](api/current-sheet.md).

```{eval-rst}
.. autofunction:: current_state

.. autoclass:: SheetState
   :members:
   :undoc-members:

.. autoclass:: Choice
   :members:
   :undoc-members:

.. autoclass:: ChoiceReason
   :members:
   :undoc-members:
```

## Embedded data

See [Embedded data](api/embedded.md).

```{eval-rst}
.. autofunction:: read_embedded

.. autofunction:: parse_embedded

.. autofunction:: embedded_differences

.. autoclass:: EmbeddedData
   :members:
   :undoc-members:

.. autoclass:: EmbeddedSheet
   :members:
   :undoc-members:

.. autoclass:: EmbeddedDifference
   :members:
   :undoc-members:
```

## Versions and codes

See [Keeping texts](api/stored-texts.md) for the two stage versions and
[Messages and catalogs](api/messages.md) for the codes.

```{eval-rst}
.. py:data:: EXTRACTION_VERSION
   :type: int

   The version of the reading stage, the part that makes the text out of a
   PDF. It rises with every change after which the same PDF can give another
   text, and never falls (BIB-4). Compare ``extraction_stage()``, which names
   it together with the PDF library's version, with what a stored text says.

.. py:data:: PARSER_VERSION
   :type: int

   The version of the parser stage, the part that makes the reading out of
   the text. It rises with every change after which the same text can give
   another reading, and never falls (BIB-4). A reading kept at another value
   is made again from the text.

.. py:data:: MESSAGE_CODES
   :type: Mapping[str, tuple[str, ...]]

   Every message code with the names of the values it carries. The codes and
   these names are part of the interface: a code never changes its meaning,
   and one that goes is not given out again (BIB-10).
```
