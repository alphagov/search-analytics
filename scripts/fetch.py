#!/usr/bin/env python

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analytics_fetcher.fetch import fetch
import argparse
import logging
import sys


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description='Fetch data from Google Analytics.'
    )
    parser.add_argument('outfile',
                        type=str, nargs=1,
                        help='path to write output to')
    parser.add_argument('days_ago',
                        type=int, nargs=1,
                        help='days ago to fetch data for')
    options = parser.parse_args(argv[1:])
    return {
        'outfile': options.outfile[0],
        'days_ago': options.days_ago[0],
    }


def main(argv):
    options = parse_args(argv)
    fetch(**options)
    return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main(sys.argv))
