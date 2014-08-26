#!/usr/bin/env python

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analytics_fetcher.support.auth import calc_env_var
import argparse
import logging


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description='Setup Google Analytics authentication.'
    )
    parser.add_argument('client_secrets_path',
                        type=str, nargs=1,
                        help='path to client_scripts file')
    options = parser.parse_args(argv[1:])
    return {
        'client_secrets_path': options.client_secrets_path[0],
    }


def main(argv):
    options = parse_args(argv)
    value = calc_env_var(options['client_secrets_path'])
    print
    print "GAAUTH='%s'" % (value, )
    return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main(sys.argv))
