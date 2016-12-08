import os
import pkg_resources
import re
import tempfile
import textract
import unittest

import pdf_redactor

FIXTURE_PATH = pkg_resources.resource_filename(__name__, "test-ssns.pdf")


class RedactorTest(unittest.TestCase):
	def test_text_ssns(self):
		redacted_fd, redacted_path = tempfile.mkstemp(".pdf")
		redacted_file = os.fdopen(redacted_fd, "wb")
		try:
			with open(FIXTURE_PATH, "rb") as f:
				options = pdf_redactor.RedactorOptions()
				options.input_stream = f
				options.output_stream = redacted_file
				options.content_filters = [
					(
						re.compile(r"[−–—~‐]"),
						lambda m: "-"
					),
					(
						re.compile(r"(?<!\d)(?!666|000|9\d{2})([OoIli0-9]{3})([\s-]?)(?!00)([OoIli0-9]{2})\2(?!0{4})([OoIli0-9]{4})(?!\d)"),
						lambda m: "XXX-XX-XXXX"
					),
				]

				pdf_redactor.redactor(options)
				redacted_file.close()

				text = textract.process(redacted_path)
				self.assertIn(b"Here are some fake SSNs\n\nXXX-XX-XXXX\n--\n\nXXX-XX-XXXX XXX-XX-XXXX\n\nAnd some more with common OCR character substitutions:\nXXX-XX-XXXX XXX-XX-XXXX XXX-XX-XXXX XXX-XX-XXXX XXX-XX-XXXX", text)
		finally:
			redacted_file.close()
			os.unlink(redacted_path)
