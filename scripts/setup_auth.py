#!/usr/bin/env python

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analytics_fetcher.support.auth import calc_env_var
import logging


def main(argv):
    if len(sys.argv) != 2:
        print "Usage: %s <path to client_secrets file>"
        return True

    value = calc_env_var(sys.argv[1])
    print
    print "GAAUTH='%s'" % (value, )
    return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    sys.exit(main(sys.argv))
