#!/usr/bin/env python3

# Example script to check whether pdf-redactor crashes on a PDF.

from __future__ import print_function

import io
import os
import multiprocessing
import pdfrw
import re
import sys
import traceback
import xml.etree.ElementTree

import pdf_redactor

try:
	from tqdm import tqdm_gui as tqdm
except ImportError:
	try:
		from tqdm import tqdm
	except ImportError:
		tqdm = lambda it: it


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


def gen_filenames(paths):
	for path in paths:
		if os.path.isfile(path):
			yield path
		elif os.path.isdir(path):
			for dirpath, dirnames, filenames in os.walk(path):
				for name in filenames:
					if name.lower().endswith(".pdf"):
						yield os.path.join(dirpath, name)


def main(paths):
	with multiprocessing.Pool() as pool:
		open_tasks = []
		for fn in tqdm(list(gen_filenames(paths))):
			open_tasks.append(pool.apply_async(smoke_test_file, [fn]))
			if len(open_tasks) > 20:
				open_tasks.pop(0).wait()
		pool.close()
		pool.join()

if __name__ == "__main__":
	main(sys.argv[1:])
