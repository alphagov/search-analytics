#!/usr/bin/env python

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analytics_fetcher.support.auth import AuthFileManager
from analytics_fetcher.support.auth import open_client
from analytics_fetcher.support.cache_manager import CacheManager
from analytics_fetcher.support.ga_client import GAClient
from analytics_fetcher.fetch import fetch_page_traffic
from analytics_fetcher.makebulk import page_info_docs
import datetime
import json
import logging
import os
import sys


logging.basicConfig(level=logging.INFO)


def call_with_client(fn, *args, **kwargs):
    with AuthFileManager() as afm:
        afm.from_env_var(os.environ["GAAUTH"])
        cache_manager = CacheManager(30)
        ga_client = GAClient(afm, cache_manager)
        result = fn(ga_client, *args, **kwargs)
        cache_manager.cleanup()
        return result


def fetch(outfile):
    if os.path.exists(outfile):
        raise ValueError("Output file %r already exists" % outfile)
    days_ago_buckets = [14]

    def fetch_data(ga_client):
        traffic_by_page = fetch_page_traffic(
            ga_client,
            datetime.date.today(),
            days_ago_buckets,
        )
        return traffic_by_page

    traffic_by_page = call_with_client(fetch_data)

    with open(outfile, "wb") as fobj:
        for action, data in page_info_docs(traffic_by_page):
            fobj.write("%s\n%s\n" % (
                json.dumps(action, separators=(',', ':')),
                json.dumps(data, separators=(',', ':'))
            ))


if __name__ == "__main__":
    fetch(sys.argv[1])
