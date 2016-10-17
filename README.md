pdf-redactor
============

A general-purpose PDF text-layer redaction tool, in pure Python, by Joshua Tauberer and Antoine McGrath.

pdf-redactor uses [pdfrw](https://github.com/pmaupin/pdfrw) under the hood to parse and write out the PDF.

* * *

This Python module is a general tool to help you automatically redact text from PDFs. The tool operates on:

* the text layer of the document's pages (content stream text)
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

`pdf_redactor.py` processes a PDF given on standard input and writes a new, redacted PDF to standard output.

However, you should use the `pdf_redactor` module as a library and pass in text filtering functions written in Python, since the command-line version of the tool does not yet actually do anything to the PDF. That means you should make your own main module like this:

	import re
	from datetime import datetime

	from pdf_redactor import *

	options = RedactorOptions()

	options.metadata_filters = {
		# Perform some field filtering --- turn the Title into uppercase.
		"Title": [lambda value : value.upper()],

		# Set some values, overriding any value present in the PDF.
		"Producer": [lambda value : "My Name"],
		"CreationDate": [lambda value : datetime.utcnow()],

		# Clear all other fields.
		"DEFAULT": [lambda value : None],
	}

	# Clear any XMP metadata, if present.
	options.xmp_filters = [lambda xml : None]

	# Redact things that look like social security numbers, replacing the
	# text with X's.
	options.content_filters = [
		(re.compile("111-22-3333"), lambda m : "XXX-XX-XXXX"),
	]

	# Perform the redaction using PDF on standard input and writing to standard output.
	redactor(options)

and then run `python3 your_module.py` instead of executing `pdf_redactor.py` directly.

## Limitations

### Content Stream Compression

Because pdfrw doesn't support all content stream compression methods, you should use a tool like [qpdf](http://qpdf.sourceforge.net/) to decompress the PDF prior to using this tool, and then to re-compress and web-optimize (linearize) the PDF after. The full command would be something like:

	qpdf --stream-data=uncompress document.pdf - \
	 | python3 pdf_redactor.py > /tmp/temp.pdf
	 && qpdf --linearize /tmp/temp.pdf document-redacted.pdf

(qpdf's first argument can't be standard input, unfortunately, so a one-liner isn't possible.)

### Other limitations

This tool has a limited understanding of glyph-to-Unicode codepoint mappings.

pdfrw is also kind of broken in Python 3 because it improperly round-trips the entire PDF through Latin-1 encoding. I've monkey-patched it here and done some tricks to get around it. While I recommend sticking with Python 3, this module should also work with Python 2.

## Testing that it worked

If you're redacting metadata, you should check the output using `pdfinfo` from the `poppler-utils` package:

	# check that the metadata is fully redacted
	pdfinfo -meta document-redacted.pdf

