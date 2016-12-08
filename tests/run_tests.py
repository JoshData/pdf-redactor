#!/usr/bin/env python

import nose
import os
import sys


def main(argv=None):
	if argv is None:
		argv = ["nosetests"]
	path = os.path.abspath(os.path.dirname(__file__))
	nose.run_exit(argv=argv, defaultTest=path)

if __name__ == "__main__":
	main(sys.argv)
