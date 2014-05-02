from analytics_fetcher.fetch import fetch_page_traffic
from analytics_fetcher.makebulk import page_info_docs
import datetime
import json
import logging
import os
import sys


logging.basicConfig(level=logging.INFO)


def fetch(outfile):
    if os.path.exists(outfile):
        raise ValueError("Output file %r already exists" % outfile)
    days_ago_buckets = [14]
    traffic_by_page = fetch_page_traffic(
        datetime.date.today(),
        days_ago_buckets,
    )

    with open(outfile, "wb") as fobj:
        for action, data in page_info_docs(traffic_by_page):
            fobj.write("%s\n%s\n" % (
                json.dumps(action, separators=(',', ':')),
                json.dumps(data, separators=(',', ':'))
            ))


if __name__ == "__main__":
    fetch(sys.argv[1])
