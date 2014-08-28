from .analysis import page_traffic
from .makebulk import page_info_docs
from .support.ga_client import ClientContext
from .ga import GAData
from collections import Counter
import datetime
import json
import os


def fetch(outfile, days_ago):
    if os.path.exists(outfile):
        raise ValueError("Output file %r already exists" % outfile)

    with ClientContext(cache_days=30) as client:
        traffic_by_page = fetch_page_traffic(
            client,
            datetime.date.today(),
            [days_ago],
        )

    with open(outfile, "wb") as fobj:
        for action, data in page_info_docs(traffic_by_page):
            fobj.write("%s\n%s\n" % (
                json.dumps(action, separators=(',', ':')),
                json.dumps(data, separators=(',', ':'))
            ))


def fetch_page_traffic(ga_client, today, days_ago_buckets):
    """Fetches page traffic for recent time periods.

    :param days_ago_buckets: A list of integers representing days_ago to fetch
    data for.  For example, [7, 14, 28] would return data on traffic in the
    last 7 days, the last 14 days, and the last 28 days.

    Returns a dict keyed by path, for which each value is a list of the same
    length as days_ago_buckets, containing the number of page views in the
    corresponding date range.

    """
    if today is None:
        today = datetime.date.today()
    oldest_days_ago = max(days_ago_buckets)
    traffic_buckets = {
        days_ago: Counter() for days_ago in days_ago_buckets
    }
    for days_ago in range(1, oldest_days_ago + 1):
        date = today - datetime.timedelta(days=days_ago)
        data = GAData(ga_client, date)
        raw_traffic = data.fetch_traffic_info()
        traffic = page_traffic(raw_traffic)
        for buckets_days_ago, bucket in traffic_buckets.items():
            if days_ago <= buckets_days_ago:
                bucket.update(traffic)

    views_per_day = {
        days_ago: sum(bucket.values())
        for days_ago, bucket in traffic_buckets.items()
    }

    traffic_by_page = {}
    for days_ago, bucket in traffic_buckets.items():
        ranked = sorted(bucket.items(), key=lambda x: x[1], reverse=True)
        for rank, (page, views) in enumerate(ranked, 1):
            traffic_by_page.setdefault(page, {})[days_ago] = [
                rank, views, float(views) / views_per_day[days_ago]
            ]
    return traffic_by_page
