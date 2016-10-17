# A general-purpose PDF text-layer redaction tool.

import sys
from datetime import datetime

if sys.version_info >= (3,):
	# pdfrw is broken in Py 3 for xref tables. This monkeypatching fixes it
	# by making binascii.hexlify work with a (unicode) string passed to it.
	# Assume the string is Latin-1 encoded since that's what pdfrw assumes
	# throughout.
	import binascii
	original_hexlify = binascii.hexlify
	binascii.hexlify = lambda x : original_hexlify(x if isinstance(x, bytes) else x.encode("latin-1"))

class RedactorOptions:
	"""Redaction and I/O options."""

	# Input/Output
	if sys.version_info < (3,):
		input_stream = sys.stdin # input stream containing the PDF to redact
		output_stream = sys.stdout # output stream to write the new, redacted PDF to
	else:
		input_stream = sys.stdin.buffer # input byte stream containing the PDF to redact
		output_stream = sys.stdout.buffer # output byte stream to write the new, redacted PDF to

	# Metadata filters map names of entries in the PDF Document Information Dictionary
	# (e.g. "Title", "Author", "Subject", "Keywords", "Creator", "Producer", "CreationDate",
	# and "ModDate") to an array of functions to run on the values of those keys.
	#
	# Each function is given a pdfrw.objects.PdfString containing the current field value,
	# or None if the field is not present in the input PDF, as the function's first argument
	# and it must return either a string, a datetime.datetime value (CreationDate and ModDate
	# should datetime.datetime values), or None to replace the field's value with. Return
	# None to clear the field (unless a later function adds a new value).
	#
	# The functions are run in order. Each function is given the previous function's return
	# value. The last function's return value is put into the output PDF.
	#
	# If a datetime.datetime is returned without timezone info (a "naive" datetime), then
	# it must be in UTC. Use pytz.timezone.localize to encode a local time.
	#
	# Use "DEFAULT" as a key to apply functions to all metadata fields that have no specific
	# functions defined, which is useful to remove all unrecognized fields.
	#
	# Use "ALL" to appy functions to all metadata fields, after any field-specific
	# functions or DEFAULt functions are run.
	metadata_filters = { }

	# The XMP metadata filters are functions that are passed any existing XMP data and
	# return new XMP metadata. The functions are called in order and each is passed the
	# result of the previous function. The functions are given an xml.etree.Element object,
	# or None, as their first argument and must return an object of the same type, or None.
	xmp_filters = []

	# This function controls how XML returned by xmp_filters is serialized. Replace this
	# function with any function that takes an xml.etree.Element object and returns a string
	# (a unicode string --- don't serialize to bytes).
	xmp_serializer = None

	# The content filters are run on the combined content streams of the pages.
	#
	# Each filter is a tuple of a compiled regular expression and a function to generate
	# replacement text, which is given a re.Match object as its sole argument. It must return a string.
	#
	# Since spaces in PDFs are sometimes not encoded as text but instead as positional
	# offsets (like newlines), the regular expression should treat all spaces as optional.
	#
	# Since pdfrw doesn't support content stream compression, you should use a tool like qpdf
	# to decompress the streams before using this tool (see the README).
	content_filters = []

	# When replacement text isn't likely to have a glyph stored in the PDF's fonts,
	# replace the character with these other characters (if they don't have the same
	# problem):
	content_replacement_glyphs = ['?', '#', '*', ' ']


def redactor(options):
	# This is the function that performs redaction.

	from pdfrw import PdfReader, PdfWriter

	# Read the PDF.
	document = PdfReader(options.input_stream)

	# Modify its Document Information Dictionary metadata.
	update_metadata(document, options)

	# Modify its XMP metadata.
	update_xmp_metadata(document, options)

	if options.content_filters:
		# Build up the complete text stream of the PDF content.
		text_layer = build_text_layer(document, options)

		# Apply filters to the text stream.
		update_text_layer(options, *text_layer)

		# Replace page content streams with updated tokens.
		apply_updated_text(document, *text_layer)

	# Write the PDF back out.
	writer = PdfWriter()
	writer.trailer = document
	writer.write(options.output_stream)


def update_metadata(trailer, options):
	# Update the PDF's Document Information Dictionary, which contains keys like
	# Title, Author, Subject, Keywords, Creator, Producer, CreationDate, and ModDate
	# (the latter two containing Date values, the rest strings).

	import codecs
	from pdfrw.objects import PdfString, PdfName, PdfDict

	# Create the metadata dict if it doesn't exist, since the caller may be adding fields.
	if not trailer.Info:
		trailer.Info = PdfDict()

	# Get a list of all metadata fields that exist in the PDF plus any fields
	# that there are metadata filters for (since they may insert field values).
	keys = set(str(k)[1:] for k in trailer.Info.keys()) \
	     | set(k for k in options.metadata_filters.keys() if k not in ("DEFAULT", "ALL"))

	# Update each metadata field.
	for key in keys:
		# Get the functions to apply to this field.
		functions = options.metadata_filters.get(key)
		if functions is None:
			# If nothing is defined for this field, use the DEFAULT functions.
			functions = options.metadata_filters.get("DEFAULT", [])

		# Append the ALL functions.
		functions += options.metadata_filters.get("ALL", [])

		# Run the functions on any existing values.
		value = trailer.Info[PdfName(key)]
		for f in functions:
			# Before passing to the function, convert from a PdfString to a Python string.
			if isinstance(value, PdfString):
				# decode from PDF's "(...)" syntax.
				value = value.decode()

				# If it's a UTF-16BE string --- indicated with a BOM --- then decode it too.
				# In Py 3, pdfrw has decoded the string already as if it were Latin-1, so we
				# have to first go back to bytes.
				if sys.version_info >= (3,):
					# Decode in Py3 only.
					value_ = value.encode("Latin-1")
				else:
					value_ = value
				if value_.startswith(codecs.BOM_UTF16_BE):
					value = value_.decode("UTF-16BE")[1:] # remove BOM after decoding

			# Filter the value.
			value = f(value)

			# Convert Python data type to PdfString.
			if isinstance(value, str):
				# Convert string to a PdfString instance.
				#
				# PDFs have two string serialization formats: PDFDocEncoding and UTF-16BE with a BOM.
				# PDFDocEncoding is very similar or identical to Latin-1 (I'm not sure).
				#
				# In Py3, pdfrw will serialize every string using Latin-1. We must check that
				# that will be possible --- the str might contain other Unicode characters.
				# If it's not possible, we can trick it into serializing as UTF-16BE with a BOM
				# by decoding it as if it were Latin-1.
				try:
					value.encode("Latin-1").decode("Latin-1")
					# Ok Latin-1 works fine.
				except ValueError:
					# String contains non-Latin-1 characters. Serialize as UTF-16BE with a BOM
					# and then decode it as if it were Latin-1, so that when pdfrw writes it
					# back out it comes out correct as UTF-16BE again.
					value = (codecs.BOM_UTF16_BE + value.encode("UTF-16BE")).decode("latin1")
				value = PdfString.encode(value)

			elif sys.version_info < (3,) and isinstance(value, unicode):
				# This is a Py 2 Unicode instance. PDF allows this to be serialized to
				# UTF-16BE with a BOM.
				value = PdfString.encode(codecs.BOM_UTF16_BE + value.encode("UTF-16BE"))

			elif isinstance(value, datetime):
				# Convert datetime into a PDF "D" string format.
				value = value.strftime("%Y%m%d%H%M%S%z")
				if len(value) == 19:
					# If TZ info was include, add an apostrophe between the hour/minutes offsets.
					value = value[:17] + "'" + value[17:]
				value = PdfString("(D:%s)" % value)

			elif value is None:
				# delete the metadata value
				pass
			else:
				raise ValueError("Invalid type of value returned by metadata_filter function. %s was returned by %s." %
					(repr(value), f.__name__ or "anonymous function"))

			# Replace value.
			trailer.Info[PdfName(key)] = value


def update_xmp_metadata(trailer, options):
	if trailer.Root.Metadata:
		# Safely parse the existing XMP data.
		from defusedxml.ElementTree import fromstring
		value = fromstring(trailer.Root.Metadata.stream)
	else:
		# There is no XMP metadata in the document.
		value = None

	# Run each filter.
	for f in options.xmp_filters:
		value = f(value)

	# Set new metadata.
	if value is None:
		# Clear it.
		trailer.Root.Metadata = None
	else:
		# Serialize the XML and save it into the PDF metadata.

		# Get the serializer.
		serializer = options.xmp_serializer
		if serializer is None:
			# Use a default serializer based on xml.etree.ElementTre.tostring.
			def serializer(xml_root):
				import xml.etree.ElementTree
				if hasattr(xml.etree.ElementTree, 'register_namespace'):
					# Beginning with Python 3.2 we can define namespace prefixes.
					xml.etree.ElementTree.register_namespace("xmp", "adobe:ns:meta/")
					xml.etree.ElementTree.register_namespace("pdf13", "http://ns.adobe.com/pdf/1.3/")
					xml.etree.ElementTree.register_namespace("xap", "http://ns.adobe.com/xap/1.0/")
					xml.etree.ElementTree.register_namespace("dc", "http://purl.org/dc/elements/1.1/")
					xml.etree.ElementTree.register_namespace("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
				return xml.etree.ElementTree.tostring(xml_root, encoding='unicode')
		
		# Create a fresh Metadata dictionary and serialize the XML into it.
		from pdfrw.objects import PdfDict
		trailer.Root.Metadata = PdfDict()
		trailer.Root.Metadata.Type = "Metadata"
		trailer.Root.Metadata.Subtype = "XML"
		trailer.Root.Metadata.stream = serializer(value)
	

def build_text_layer(document, options):
	# Within each page's content stream, look for text-showing operators to
	# find the text content of the page. Construct a string that contains the
	# entire text content of the document AND a mapping from characters in the
	# text content to tokens in the content streams. That lets us modify the
	# tokens in the content streams when we find text that we want to redact.
	#
	# The text-showing operators are:
	#
	#   (text) Tj      -- show a string of text
	#   (text) '       -- move to next line and show a string of text
	#   aw ac (text) " -- show a string of text with word/character spacing parameters
	#   [ ... ] TJ     -- show text strings from the array, which are interleaved with spacing parameters
	#
	# (These operators appear only within BT ... ET so-called "text objects",
	# although we don't make use of it.)
	#
	# But since we don't understand any of the other content stream operators,
	# and in particular we don't know how many operands each (non-text) operator
	# takes, we can never be sure whether what we see in the content stream is
	# an operator or an operand. If we see a "Tj", maybe it is the operand of
	# some other operator?
	#
	# We'll assume we can get by just fine, however, assuming that whenever we
	# see one of these tokens that it's an operator and not an operand.
	#
	# But TJ remains a little tricky because its operand is an array that preceeds
	# it. Arrays are delimited by square brackets and we need to parse that.
	#
	# We also have to be concerned with the encoding of the text content, which
	# depends on the active font. With a simple font, the text is a string whose
	# bytes are glyph codes. With a composite font, a CMap maps multi-byte
	# character codes to glyphs. In either case, we must map glyphs to unicode
	# characters so that we can pattern match against it.
	#
	# To know the active font, we look for the "<font> <size> Tf" operator.

	from pdfrw import PdfTokens, PdfObject, PdfString, PdfArray
	from pdfrw.objects.pdfname import BasePdfName

	text_content = []
	text_map = []
	fontcache = { }

	class TextToken:
		value = None
		font = None
		def __init__(self, value, font):
			self.font = font
			self.raw_original_value = value
			self.original_value = toUnicode(value, font, fontcache)
			self.value = self.original_value
		def __str__(self):
			# __str__ is used for serialization
			if self.value == self.original_value:
				# If unchanged, return the raw original value without decoding/encoding.
				return PdfString.encode(self.raw_original_value)
			else:
				# If the value changed, encode it from Unicode according to the encoding
				# of the font that is active at the location of this token.
				return PdfString.encode(fromUnicode(self.value, self.font, fontcache, options))
		def __repr__(self):
			# __repr__ is used for debugging
			return "Token<%s>" % repr(self.value)

	def process_text(token):
		if token.value == "": return
		text_content.append(token.value)
		text_map.append((len(token.value), token))

	# For each page...
	page_tokens = []
	for page in document.pages:
		# For each token in the content stream...

		# Remember this page's revised token list.
		token_list = []
		page_tokens.append(token_list)

		if page.Contents is None:
			continue

		prev_token = None
		prev_prev_token = None
		array_stack = []
		current_font = None

		if isinstance(page.Contents, PdfArray):
			contents = list(page.Contents)
		else:
			contents = [page.Contents]

		for content in contents:
			# Iterate through the tokens.
			for token in iter(PdfTokens(content.stream)):
				# Replace any string token with our own class that hold a mutable
				# value, which is how we'll rewrite content.
				if isinstance(token, PdfString):
					token = TextToken(token.decode(), current_font)

					# Remember all unicode characters seen in this font so we can
					# avoid inserting characters that the PDF isn't likely to have
					# a glyph for.
					if current_font and current_font.BaseFont:
						fontcache.setdefault(current_font.BaseFont, set()).update(token.value)


				# Append the token into a new list that holds all tokens.
				token_list.append(token)

				# If the token is an operator and we're not inside an array...
				if isinstance(token, PdfObject) and len(array_stack) == 0:
					# And it's one that we recognize, process it.
					if token in ("Tj", "'", '"') and isinstance(prev_token, TextToken):
						# Simple text operators.
						process_text(prev_token)
					elif token == "TJ" and isinstance(prev_token, list):
						# The text array operator.
						for item in prev_token:
							# (item may not be a string! only the strings are text.)
							if isinstance(item, TextToken):
								process_text(item)
					elif token == "Tf" and isinstance(prev_prev_token, BasePdfName):
						# prev_prev_token holds the font 'name'. The name must be looked up
						# in the content stream's resource dictionary, which is page.Resources,
						# plus any resource dictionaries above it in the document hierarchy.
						current_font = None
						resources = page.Resources
						while resources and not current_font:
							current_font = resources.Font[prev_prev_token]
							resources = resources.Parent

				# Or something to do with arrays.
				elif token == '[':
					# Beginning of an array.
					array_stack.append([])
				elif token == ']':
					# End of an array.
					x = array_stack.pop(-1)
					if len(array_stack) > 0:
						# We were nested. Add this array into the outer array.
						array_stack[-1].append(x)
					else:
						# This is the top level. Remember it as the last token.
						token = x
				elif len(array_stack) > 0:
					array_stack[-1].append(token)

				# Remember the previously seen token in case the next operator is a text-showing
				# operator -- in which case this was the operand. Remember the token befor that
				# because it may be a font name for the Tf operator.
				prev_prev_token = prev_token
				prev_token = token

	# Join all of the strings together.
	text_content = "".join(text_content)

	return (text_content, text_map, page_tokens)


def toUnicode(string, font, fontcache):
	# This is hard!

	# In Py3, pdfrw decodes the whole stream as if it were Latin1. That's never
	# really the right encoding for fonts. Put it back to the original bytes.
	if sys.version_info >= (3,):
		string = string.encode("Latin-1")

	if not font:
		# There is no font for this text. Assume Latin-1.
		return string.decode("Latin-1")
	elif font.ToUnicode:
		# Use the CMap, which maps character codes to Unicode code points.
		# We'll use pdfminer's CMap parser and we'll cache the parsed CMap.
		# This seems to only work for two-byte CIDs -- is that normal?
		if font.ToUnicode.stream not in fontcache:
			from pdfminer.cmapdb import FileUnicodeMap, CMapParser
			import io
			cmap = FileUnicodeMap()
			CMapParser(cmap, (io.StringIO if sys.version_info>=(3,) else io.BytesIO)(font.ToUnicode.stream)).run()
			#print(font.ToUnicode.stream, file=sys.stderr)
			#cmap.dump(sys.stderr)
			fontcache[font.ToUnicode.stream] = cmap
		cmap = fontcache[font.ToUnicode.stream]
		def twobytechars(s):
			if sys.version_info < (3,): s = [ord(c) for c in s]
			for i in range(0, len(s), 2):
				if i == len(s)-1: break # odd number of bytes
				yield s[i+0]*256 + s[i+1]
		string = "".join(cmap.cid2unichr.get(c, '?') for c in twobytechars(string))
		#print(string, end='', file=sys.stderr)
		#sys.stderr.write(string)
		return string
	elif font.Encoding == "/WinAnsiEncoding":
		return string.decode("cp1252", "replace")
	elif font.Encoding == "/MacRomanEncoding":
		return string.decode("mac_roman", "replace")
	else:
		return "?"
		#raise ValueError("Don't know how to decode data from font %s." % font)

def fromUnicode(string, font, fontcache, options):
	# Filter out characters that are not likely to have renderable glyphs
	# because the character didn't occur in the original PDF in its font.
	# For any character that didn't occur in the original PDF, replace it
	# with the first character in options.content_replacement_glyphs that
	# did occur in the original PDF. If none ocurred, delete the character.
	if font and font.BaseFont in fontcache:
		char_occurs = fontcache[font.BaseFont]
		def map_char(c):
			for cc in [c] + options.content_replacement_glyphs:
				if cc in char_occurs:
					return cc
			return "" # no replacement glyph => omit character
		string = "".join(map_char(c) for c in string)

	# Encode the Unicode string in the same encoding that it was originally
	# stored in --- based on the font that was active when the token was
	# used in a text-showing operation.
	if not font:
		# There was no font for this text. Assume Latin-1.
		string = string.encode("Latin-1")

	elif font.ToUnicode and font.ToUnicode.stream in fontcache:
		# Convert the Unicode code points back to two-byte CIDs.
		cmap = fontcache[font.ToUnicode.stream]
		unichr2cid = dict(reversed(entry) for entry in cmap.cid2unichr.items())
		replacement_cid = list(cmap.cid2unichr)[0] # the first CID value
		def to_bytes(c):
			return [int(c/256), c & 255]
		byte_string = sum([to_bytes(unichr2cid.get(c, replacement_cid)) for c in string], [])

		# Convert the byte string to a bytes (Py3) or str (Py2) instance.
		from struct import pack
		string = b''.join(pack("B", b) for b in byte_string)

	# Convert using a simple encoding.
	elif font.Encoding == "/WinAnsiEncoding":
		string = string.encode("cp1252")
	elif font.Encoding == "/MacRomanEncoding":
		string = string.encode("mac_roman")

	# Don't know how to handle this sort of font.
	else:
		raise ValueError("Don't know how to encode data to font %s." % font)

	# In Py3, pdfrw encodes the whole stream back into Latin-1. We need to
	# get these bytes through, so decode as if it were Latin-1.
	if sys.version_info >= (3,):
		string = string.decode("Latin-1")

	return string

def update_text_layer(options, text_content, text_map, page_tokens):
	if len(text_map) == 0:
		# No text content.
		return

	# Apply each regular expression to the text content...
	for pattern, function in options.content_filters:
		# Finding all matches...
		text_map_index = 0
		text_map_charpos = 0
		text_map_token_xdiff = 0
		text_content_xdiff = 0
		for m in pattern.finditer(text_content):
			# We got a match at text_content[i1:i2].
			i1 = m.start()
			i2 = m.end()

			# Pass the matched text to the replacement function to get replaced text.
			replacement = function(m)

			# Do a text replacement in the tokens that produced this text content.
			# It may have been produced by multiple tokens, so loop until we find them all.
			while i1 < i2:
				# Find the original tokens in the content stream that
				# produced the matched text. Start by advancing over any
				# tokens that are entirely before this span of text.
				while text_map_charpos + text_map[text_map_index][0] <= i1:
					text_map_charpos += text_map[text_map_index][0]
					text_map_index += 1
					text_map_token_xdiff = 0
				assert(text_map_charpos <= i1)

				# The token at text_map_index, and possibly subsequent ones,
				# are responsible for this text. Replace the matched content
				# here with replacement content.
				tok = text_map[text_map_index][1]

				# Where does this match begin within the token's text content?
				mpos = i1 - text_map_charpos - text_map_token_xdiff
				assert mpos >= 0

				# How long is the match within this token?
				mlen = min(i2-i1, len(tok.value)-mpos)
				assert mlen >= 0

				# How much should we replace here?
				if mlen < (i2-i1):
					# There will be more replaced later, so take the same number
					# of characters from the replacement text.
					r = replacement[:mlen]
					replacement = replacement[mlen:]
				else:
					# This is the last token in which we'll replace text, so put
					# all of the remaining replacement content here.
					r = replacement
					replacement = None # sanity

				# Do the replacement.
				tok.value = tok.value[:mpos] + r + tok.value[mpos+mlen:]
				text_map_token_xdiff += len(r) - mlen

				# Also replace the text_content so that if we have multiple regexes
				# the later regexes see content that matches the tokens.
				text_content = text_content[0:i1+text_content_xdiff] + r + text_content[i2+text_content_xdiff:]
				text_content_xdiff += len(r) - mlen

				# Avance for next iteration.
				i1 += mlen

def apply_updated_text(document, text_content, text_map, page_tokens):
	# Create a new content stream for each page by concatenating the
	# tokens in the page_tokens lists.
	from pdfrw import PdfDict
	for i, page in enumerate(document.pages):
		if page.Contents is None: continue # nothing was here

		# Replace the page's content stream with our updated tokens.
		# The content stream may have been an array of streams before,
		# so replace the whole thing with a single new stream.
		page.Contents = PdfDict()
		page.Contents.stream = "\n".join(str(tok) for tok in page_tokens[i])
		page.Contents.Length = len(page.Contents.stream) # reset

if __name__ == "__main__":
	redactor(RedactorOptions())