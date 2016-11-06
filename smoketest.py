#!/usr/bin/env python3

# Example script to check whether pdf-redactor crashes on a PDF.

from __future__ import print_function

import io
import os
import pdfrw
import xml.etree.ElementTree
import re
import sys
import traceback

import pdf_redactor


def metadata_filter(value):
	if isinstance(value, (list, dict)):
		return None
	return value


def smoke_test_file(path):
	options = pdf_redactor.RedactorOptions()
	options.input_stream = open(path, "rb")
	options.output_stream = io.BytesIO()
	options.content_filters = [(re.compile("\w+"), lambda match: match.group(0))]
	options.metadata_filters = {"ALL": [metadata_filter]}
	try:
		pdf_redactor.redactor(options)
	except (pdfrw.errors.PdfParseError,
			IndexError,
			AssertionError,
			xml.etree.ElementTree.ParseError,
			TypeError,
			AttributeError,
			StopIteration,
			ValueError) as e:
		print("{0} while reading {1}".format(e.__class__.__name__, path), file=sys.stderr)
		print(traceback.format_exc(), file=sys.stderr)
	finally:
		options.input_stream.close()


def main(paths):
	for path in paths:
		if os.path.isfile(path):
			smoke_test_file(path)
		elif os.path.isdir(path):
			for dirpath, dirnames, filenames in os.walk(path):
				for name in filenames:
					if name.lower().endswith(".pdf"):
						p = os.path.join(dirpath, name)
						smoke_test_file(p)

if __name__ == "__main__":
	main(sys.argv[1:])
