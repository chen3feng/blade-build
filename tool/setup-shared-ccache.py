#!/usr/bin/env python

"""
Setup shared ccache for multiple users in same develop box.
"""

from __future__ import print_function
import argparse
import os
import sys
import subprocess


_CONFIG_FILE_NAME = 'ccache.conf'


def check():
    # Check root
    if subprocess.call('ccache --version > /dev/null', shell=True) != 0:
        print('Error: ccache not found. please install it(apt, yum, dnf or from source, ...)')
        print('Exiting.')
        sys.exit(1)

    # Check ccache installation
    if os.geteuid() != 0:
        print("You need to have root privileges to run this script.\n"
              "Please try again, this time using 'sudo'. Exiting.", file=sys.stderr)
        sys.exit(1)


def parse_command_line():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-D', '--base-dir', dest='base_dir', required=True,
            help='Base dir under which to create the cache dir')
    parser.add_argument('-M', '--size', dest='max_size', required=True,
            help='Set the maximum size of the files stored in the cache.  SIZE should be a number '
                 'followed by an optional suffix: k, M, G, T (decimal), Ki, Mi, Gi or Ti (binary). '
                 'The default suffix is G. Use 0 for no limit.')
    return parser.parse_args()


def make_cache_dir(args):
    cache_dir = os.path.join(args.base_dir, 'ccache')
    os.umask(0o000)
    os.makedirs(cache_dir, 0o2777)
    # subprocess.check_call('chmod rw,g+s %s' % cache_dir, shell=True)
    print('Cache dir: %s' % cache_dir)
    return cache_dir


def write_cache_config(args, cache_dir):
    file_name = os.path.join(cache_dir, _CONFIG_FILE_NAME)
    with open(file_name, 'w') as config:
        values = [
            'max_size = %s' % args.max_size,
            'umask = 000',
        ]
        print('\n'.join(values), file=config)
    print('Cache config file: %s' % file_name)


def write_system_config(args, cache_dir):
    cache_dir = os.path.abspath(cache_dir)
    file_name = os.path.join('/etc', _CONFIG_FILE_NAME)
    with open(file_name, 'w') as config:
        print('cache_dir = %s' % cache_dir, file=config)
    print('System cache config file: %s' % file_name)


def main():
    args = parse_command_line()
    check()
    cache_dir = make_cache_dir(args)
    write_cache_config(args, cache_dir)
    write_system_config(args, cache_dir)
    print('Setup success. You can run `man ccache` to learn more.')


if __name__ == '__main__':
    main()
