from setuptools import setup

setup(
	name='pdf-redactor',
	version='0.0.1',
	description=' A general purpose PDF text-layer redaction tool for Python 2/3.',
	author='Joshua Tauberer',
	author_email='jt@occams.info',
	long_description=open('README.md', 'r').read(),
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
		'pdfrw>=0.3',
		'defusedxml',
	],
	tests_require=[
		'nose',
		'textract',
	],
	test_suite='tests.run_tests.main',
)
