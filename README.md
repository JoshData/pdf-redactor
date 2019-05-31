pdf-redactor
============

A general-purpose PDF text-layer redaction tool, in pure Python, by Joshua Tauberer and Antoine McGrath.

pdf-redactor uses [pdfrw](https://github.com/pmaupin/pdfrw) under the hood to parse and write out the PDF.

* * *

This Python module is a general tool to help you automatically redact text from PDFs. The tool operates on:

* the text layer of the document's pages (content stream text)
* plain text annotations
* link target URLs
* the Document Information Dictionary, a.k.a. the PDF metadata like Title and Author
* embedded XMP metadata, if present

Graphical elements, images, and other embedded resources are not touched.

You can:

* Use regular expressions to perform text substitution on the text layer (e.g. replace social security numbers with "XXX-XX-XXXX").
* Rewrite, remove, or add new metadata fields on a field-by-field basis (e.g. wipe out all metadata except for certain fields).
* Rewrite, remove, or add XML metadata using functions that operate on the parsed XMP DOM (e.g. wipe out XMP metadata).

## How to use pdf-redactor

Get this module and then install its dependencies with:

	pip3 install -r requirements.txt

`pdf_redactor.py` processes a PDF given on standard input and writes a new, redacted PDF to standard output:

	python3 pdf_redactor.py < document.pdf > document-redacted.pdf

However, you should use the `pdf_redactor` module as a library and pass in text filtering functions written in Python, since the command-line version of the tool does not yet actually do anything to the PDF. The [example.py](example.py) script shows how to redact Social Security Numbers:

	python3 example.py < tests/test-ssns.pdf > document-redacted.pdf

## Limitations

### Not all content may be redacted

The PDF format is an incredibly complex data standard that has hundreds, if not thousands,
of exotic capabilities used rarely or in specialized circumstances. Besides a document's text layer, metadata, and other components of a PDF document which this tool scans and can redact text from, there are many other components of PDF documents that this tool **does not look at**, such as:

* embedded files, multimedia, and scripts
* rich text annotations
* forms
* internal object names
* digital signatures

There are so many exotic capabilities in PDF documents that it would be difficult to list them all, so this list is a very partial list. It would take a lot more effort to write a redaction tool that scanned all possible places content can be hidden inside a PDF besides the places that this tool looks at, so please be aware that it is **your responsibility** to ensure that the PDFs you use this tool on only use the capabilities of the PDF format that this tool knows how to redact.

### Character replacement

One of the PDF format's strengths is that it embeds font information so that documents can be displayed even if the fonts used to create the PDF aren't available when the PDF is viewed. Most PDFs are optimized to only embed the font information for characters that are actually used in the document. So if a document doesn't contain a particular letter or symbol, information for rendering the letter or symbol is not stored in the PDF.

This has an unfortunate consequence for redaction in the text layer. Since redaction in the text layer works by performing simple text substitution in the text stream, you may create replacement text that contains characters that were _not_ previously in the PDF. Those characters simply won't show up when the PDF is viewed because the PDF didn't contain any information about how to display them.

To get around this problem, pdf_redactor checks your replacement text for new characters and replaces them with characters from the `content_replacement_glyphs` list (defaulting to `?`, `#`, `*`, and a space) if any of those characters _are_ present in the font information already stored in the PDF. Hopefully at least one of those characters _is_ present (maybe none are!), and in that case your replacement text will at least show up as something and not disappear.

### Content stream compression

Because pdfrw doesn't support all content stream compression methods, you should use a tool like [qpdf](http://qpdf.sourceforge.net/) to decompress the PDF prior to using this tool, and then to re-compress and web-optimize (linearize) the PDF after. The full command would be something like:

	qpdf --stream-data=uncompress document.pdf - \
	 | python3 pdf_redactor.py > /tmp/temp.pdf
	 && qpdf --linearize /tmp/temp.pdf document-redacted.pdf

(qpdf's first argument can't be standard input, unfortunately, so a one-liner isn't possible.)

### Exotic fonts

This tool has a limited understanding of glyph-to-Unicode codepoint mappings. Some unusual fonts may not be processed correctly, in which case text layer redaction regular expressions may not match or substitution text may not render correctly.

## Testing that it worked

If you're redacting metadata, you should check the output using `pdfinfo` from the `poppler-utils` package:

	# check that the metadata is fully redacted
	pdfinfo -meta document-redacted.pdf

## Developing/testing the library

Tests require some additional packages:

	pip install -r requirements-dev.txt
	python tests/run_tests.py

The file `tests/test-ssns.pdf` was generating by converting the file `tests/test-ssns.odft` to PDF in LibreOffice with the `Archive PDF/A-1a` option turned on so that it generates XMP metadata and `Export comments` turned on to export the comment.