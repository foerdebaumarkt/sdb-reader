"""Names vulture cannot see being used. Meant to stay short.

Every entry is a promise that the name *is* used, just not in a way an AST
scan can follow -- a string annotation under `if TYPE_CHECKING`, a `Protocol`
method's parameters, the arguments Python passes to `__exit__`. Each entry
should say who does the using, because an entry that stops being true hides a
dead symbol for good.

The file is never imported; vulture reads it as a list of usages. Regenerate
candidates with `vulture --make-whitelist`, then keep only what you can
justify.
"""

# Part of the answer `current_state` gives (BIB-8); read by callers.
instead_of  # current.py: Choice

# Part of the answer `clp_expected` gives (BIB-25); read by callers.
signal_word_differs  # expected.py: ClpExpected

# Called by docs/conf.py for every page Sphinx reads (make docs); docs/ is
# not among the scanned paths, its settings are names Sphinx reads.
for_site  # tools/docs/site_links.py

# Called by the XML parser when a file declares a document type (SDW-11):
# `doctype` as a method of the parser's target, `StartDoctypeDeclHandler` as
# a handler of the Expat parser underneath.
doctype  # embedded.py: _NoDocumentType
StartDoctypeDeclHandler  # embedded.py: _parser_without_document_type
