# encoding: utf-8
import os
import pkg_resources
import re
import subprocess
import tempfile
import unittest

import pdf_redactor

FIXTURE_PATH = pkg_resources.resource_filename(__name__, "test-ssns.pdf")


class RedactFixture(object):
	def __init__(self, input_path, options):
		self.input_path = input_path
		self.options = options

	def __enter__(self):
		self.input_file = open(self.input_path, "rb")
		self.options.input_stream = self.input_file

		fd, self.redacted_path = tempfile.mkstemp(".pdf")
		self.redacted_file = os.fdopen(fd, "wb")
		self.options.output_stream = self.redacted_file

		pdf_redactor.redactor(self.options)
		self.redacted_file.close()

		return self.redacted_path

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.input_file.close()
		self.redacted_file.close()
		os.unlink(self.redacted_path)
		return False


def pdf_to_text(fn):
	import subprocess
	return subprocess.check_output(["pdftotext", fn, "-"]).decode("utf8")

def pdf_to_html(fn):
	import subprocess
	return subprocess.check_output(["pdftohtml", "-stdout", fn]).decode("utf8")

class RedactorTest(unittest.TestCase):
	def test_text_ssns(self):
		options = pdf_redactor.RedactorOptions()
		options.content_filters = [
			(
				re.compile(u"[−–—~‐]"),
				lambda m: "-"
			),
			(
				re.compile(r"(?<!\d)(?!666|000|9\d{2})([OoIli0-9]{3})([\s-]?)(?!00)([OoIli0-9]{2})\2(?!0{4})([OoIli0-9]{4})(?!\d)"),
				lambda m: "XXX-XX-XXXX"
			),
		]
		with RedactFixture(FIXTURE_PATH, options) as redacted_path:
			text = pdf_to_text(redacted_path)
			self.assertIn("Here are some fake SSNs\n\nXXX-XX-XXXX\n--\n\nXXX-XX-XXXX XXX-XX-XXXX\n\nAnd some more with common OCR character substitutions:\nXXX-XX-XXXX XXX-XX-XXXX XXX-XX-XXXX XXX-XX-XXXX XXX-XX-XXXX", text)

	def test_metadata(self):
		options = pdf_redactor.RedactorOptions()
		options.metadata_filters = {
			"Title": [lambda value: value.replace("test", "sentinel")],
			"Subject": [lambda value: value[::-1]],
			"DEFAULT": [lambda value: None],
		}
		with RedactFixture(FIXTURE_PATH, options) as redacted_path:
			metadata = subprocess.check_output(["pdfinfo", redacted_path])
			self.assertIn(b"this is a sentinel", metadata)
			self.assertIn(b"FDP a si", metadata)
			self.assertNotIn(b"CreationDate", metadata)
			self.assertNotIn(b"LibreOffice", metadata)

	def test_xmp(self):
		options = pdf_redactor.RedactorOptions()
		options.metadata_filters = {
			"DEFAULT": [lambda value: None],
		}
		def xmp_filter(doc):
			self.assertTrue(doc is not None)
			for elem in doc.iter():
				if elem.text == "Writer":
					elem.text = "Sentinel"
			return doc
		options.xmp_filters = [xmp_filter]
		with RedactFixture(FIXTURE_PATH, options) as redacted_path:
			metadata = subprocess.check_output(["pdfinfo", "-meta", redacted_path])
			self.assertIn(b"Sentinel", metadata)
			self.assertNotIn(b"Writer", metadata)

	def test_link(self):
		options = pdf_redactor.RedactorOptions()
		options.content_filters = [
			# replacement for the link text
			(
				re.compile(re.escape(u"link to issue #13")),
				lambda m: "this link was removed"
			),
		]
		options.link_filters = [
			lambda href, annotation : "https://www.google.com" 
		]
		with RedactFixture(FIXTURE_PATH, options) as redacted_path:
			text = pdf_to_text(redacted_path)
			self.assertNotIn("link to issue #13", text)
			self.assertIn("this link was re#o#e#", text) # glyph replacements	

			html = pdf_to_html(redacted_path)
			self.assertNotIn("github", html)
			self.assertIn('href="https://www.google.com"', html)

	def test_comment(self):
		options = pdf_redactor.RedactorOptions()
		options.content_filters = [
			# replacement for the comment text
			(
				re.compile(re.escape(u"I have a comment!")),
				lambda m: "all gone"
			),

			# replacement for the comment title
			(
				re.compile(re.escape(u"Unknown Author")),
				lambda m: "Some Person"
			),
		]
		with RedactFixture(FIXTURE_PATH, options) as redacted_path:
			text = pdf_to_text(redacted_path)
			# TODO: Test that the comment text and title have been replaced!
			# Unfortunately no easy-to-run tool seems to extract
			# comments.
