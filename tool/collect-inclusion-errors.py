#!/usr/bin/env python

"""Collect inclusion errors and report the summarized information."""

import argparse
import json
import os
import pprint

try:
    import cPickle as pickle
except ImportError:
    import pickle


def parse_args():
    parser = argparse.ArgumentParser(description='Process some integers.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--missing', action='store_true', default=False,
                       help='Colloect header dependency missing information')
    group.add_argument('--undeclared', action='store_true', default=False,
                       help='Colloect undeclared headers')

    return parser.parse_args()


def process_targets(build_targets, options):
    full_missing = {}
    undeclared_hdrs = set()
    for target in build_targets:
        dir, name = target.split(':')
        details_file = os.path.join('blade-bin', dir, name + '.incchk.details')
        if not os.path.exists(details_file):
            continue
        details = pickle.load(open(details_file, 'rb'))
        if details:
            if 'missing_dep' in details:
                full_missing[str(target)] = details['missing_dep']
            if 'undeclared' in details:
                undeclared_hdrs.update(details['undeclared'])

    if options.missing:
        pprint.pprint(full_missing, indent=4)
    if options.undeclared:
        pprint.pprint(sorted(undeclared_hdrs), indent=4)


def main():
    options = parse_args()
    stamp = json.load(open('blade-bin/blade_build_stamp.json'))
    process_targets(stamp['build_targets'], options)


if __name__ == '__main__':
    main()
