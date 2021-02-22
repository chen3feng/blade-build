#!/usr/bin/env python

"""
Dump the content of a `incchk` file.
"""


import pprint
import sys

try:
    import cPickle as pickle
except ImportError:
    import pickle


def main():
    if len(sys.argv) < 2:
        print("Usage: %s <filepath>" % sys.argv[0])
        sys.exit(1)
    filename = sys.argv[1]
    content = pickle.load(open(filename))
    pprint.pprint(content)


if __name__ == '__main__':
    main()
