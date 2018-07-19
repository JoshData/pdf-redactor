from setuptools import setup

setup(
	name='pdf-redactor',
	version='0.0.1',
	description=' A general purpose PDF text-layer redaction tool for Python 2/3.',
	author='Joshua Tauberer',
	author_email='jt@occams.info',
	long_description='''
	A general-purpose PDF text-layer redaction tool, in pure Python, by Joshua Tauberer and Antoine McGrath.

	pdf-redactor uses pdfrw under the hood to parse and write out the PDF.

	This Python module is a general tool to help you automatically redact text from PDFs. The tool operates on:

	* the text layer of the document's pages (content stream text)
	* the Document Information Dictionary, a.k.a. the PDF metadata like Title and Author
	* embedded XMP metadata, if present

	Graphical elements, images, and other embedded resources are not touched.

	You can:

	* Use regular expressions to perform text substitution on the text layer (e.g. replace social security numbers with "XXX-XX-XXXX").
	* Rewrite, remove, or add new metadata fields on a field-by-field basis (e.g. wipe out all metadata except for certain fields).
	* Rewrite, remove, or add XML metadata using functions that operate on the parsed XMP DOM (e.g. wipe out XMP metadata).
	''',
	url='https://github.com/JoshData/pdf-redactor',
	py_modules=['pdf_redactor'],
	classifiers=[
		'Development Status :: 4 - Beta',
		'Intended Audience :: Developers',
		'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
		'Operating System :: OS Independent',
		'Programming Language :: Python',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 3',
		'Topic :: Office/Business',
		'Topic :: Software Development :: Libraries',
		'Topic :: Software Development :: Libraries :: Python Modules',
		'Topic :: Utilities',
	],
	install_requires=[
		'pdfrw>=0.4',
		'defusedxml',
	],
	tests_require=[
		'nose',
		'textract',
	],
	test_suite='tests.run_tests.main',
)
