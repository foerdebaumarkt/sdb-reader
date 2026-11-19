# Using the command line

This manual is for whoever runs `sdb-reader` and reads what it prints. It
needs no programming. The same manual in German: [Bedienung](../bedienung/README.md).

The manual is also on the web with the rest of the documentation, at
<https://foerdebaumarkt.github.io/sdb-reader/>, one edition per released
version of the program.

`sdb-reader` reads PDF files and says for each one whether it is a German
safety data sheet (Sicherheitsdatenblatt) and, if it is, what the sheet says:
the label, the classification, dates, the supplier, and what is wrong with
the sheet as a document. It does this by fixed rules, without a language
model, so the same file always gives the same result.

| Page | What it answers |
| --- | --- |
| [Installing](installing.md) | What do I need, and how do I get the command? |
| [Reading sheets](reading.md) | How do I read one file or a folder, and what do the exit codes mean? |
| [Showing sheets as a report](showing.md) | How do I get a report I can read myself, for one file or a folder? |
| [Reading a whole collection](collection.md) | How do I read thousands of files, continue a run and leave files out? |
| [Understanding the output](output.md) | What does each part of the result say? |
| [The embedded file](embedded-file.md) | What is the file some PDFs carry inside, and how do I get it out? |
| [Asking a language model](asking.md) | How do I get a second reading from a model, what is sent where, and how do I keep the answers? |
| [Comparing two runs](comparing-runs.md) | Where does a model read a sheet otherwise than the program, and what did a change to the program do? |
| [All messages](messages.md) | Which messages are there, and what does each say? |
| [When something does not work](troubleshooting.md) | What do I do when the result is not what I expected? |

The command has five subcommands:

| Subcommand | Does |
| --- | --- |
| `read` | reads files and prints what they say, as JSON |
| `show` | reads files and prints what they say, as a report to read |
| `xml` | hands out the file a supplier's system embedded in a PDF |
| `ask` | asks a language model what each sheet says and keeps its answers |
| `diff` | sets two runs of `read` or `ask` beside each other and counts where they differ |
