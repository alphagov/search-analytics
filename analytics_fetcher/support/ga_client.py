"""Wrap access to GA in a high level client with a "fetch" endpoint.

"""

from analytics_fetcher.support.auth import open_client, AuthFileManager
from analytics_fetcher.support.cache_manager import (
    cached_iterator,
    CacheManager,
)
from apiclient.errors import HttpError
from datetime import datetime, timedelta
from oauth2client.client import AccessTokenRefreshError
import logging
import os
import time


logger = logging.getLogger(__name__)


class GAError(Exception):
    pass


class GAClient(object):
    def __init__(self, afm, cache_manager):
        self.afm = afm
        self.cache_manager = cache_manager

        # A mapping from readable profile names to the profile ID.
        self.profile_ids = {
            'search': 'ga:56562468',
        }

        # Last time that a request was made.  Used to avoid hitting GA too
        # frequently.
        self._last_request = time.time()

        # Worst sampling rate that we've seen.  None if none seen.
        # Callers of the client may reset this to None, and read it.
        self.worst_sample_rate = None

        # Time until we can trust that GA has processed the data.
        self.ga_latency = timedelta(hours=4)

    def oauth_client(self):
        if getattr(self, '_oauth_client', None) is None:
            self._oauth_client = open_client(self.afm)
        return self._oauth_client

    def build_ga_params(self, profile_name, date, kwargs):
        """Build parameters for making a call to GA.

        """
        ga_date = date.strftime("%Y-%m-%d")
        params = dict(
            ids=self.profile_ids[profile_name],
            start_date=ga_date,
            end_date=ga_date,
            samplingLevel="HIGHER_PRECISION",
            max_results=10000,
        )
        params.update(kwargs)
        return params

    def _rate_limit(self):
        """Rate limit requests by simplest possible means.

        """
        since = time.time() - self._last_request
        if since < 1:
            time.sleep(1.0 - since)
        self._last_request = time.time()

    def _check_ga_latency(self, date):
        now = datetime.now()
        if date + timedelta(days=1) + self.ga_latency > now:
            # We're not grouping by hour, so can't rely on any of the data.
            raise RuntimeError(
                "Can't reliably get data from GA for this day (%s) yet." % (
                    date.isoformat(),
                )
            )

    @cached_iterator
    def _fetch_from_ga(self, profile_name, date, name_map, kwargs):
        """Call GA with the given profile, date and args.

        Yield an iterator of the result.

        """
        self._check_ga_latency(date)
        self._rate_limit()
        params = self.build_ga_params(profile_name, date, kwargs)

        try:
            start_index = 1
            while True:
                resp = self.oauth_client().query.get_raw_response(
                    start_index=start_index,
                    **params
                )

                if resp.get('containsSampledData'):
                    sample_size = int(resp.get('sampleSize', 0))
                    sample_space = int(resp.get('sampleSpace', 1))
                    sample_rate = sample_size * 100.0 / sample_space
                    logger.warning(
                        "GA query in %r profile used sampled data (%.2f%%: %s of %s): params %r",
                        profile_name,
                        sample_rate, sample_size, sample_space,
                        params)
                else:
                    sample_rate = None
                total_results = resp['totalResults']

                headers = [
                    name_map.get(header['name'][3:], header['name'][3:])
                    for header in resp['columnHeaders']
                ]
                header_types = [
                    {
                        'STRING': unicode,
                        'INTEGER': int,
                        'PERCENT': float,
                    }[header['dataType']]
                    for header in resp['columnHeaders']
                ]

                def makerow(row):
                    ret = dict(zip(
                        headers,
                        (header_type(value)
                         for (header_type, value) in zip(header_types, row))))
                    if 'hour' in ret:
                        hour = int(ret['hour'])
                        ret['hour'] = hour
                    if sample_rate:
                        ret['sampled'] = sample_rate
                    return ret

                rows = resp.get('rows', ())
                for row in rows:
                    start_index += 1
                    row = makerow(row)
                    if row is not None:
                        yield row
                logger.info(
                    "Fetched %d of %d rows", start_index - 1, total_results
                )

                if start_index > total_results:
                    return
        except AccessTokenRefreshError:
            logger.exception(
                "Credentials error fetching data from GA",
            )
            raise GAError("Credentials error fetching data from GA")
        except HttpError as error:
            logger.exception(
                "HTTP error fetching data from GA: %s: %s",
                error.resp.status, error._get_reason(),
            )
            raise GAError("HTTP error fetching data from GA")

    @staticmethod
    def _remove_time_components_from_date(date):
        return datetime(year=date.year, month=date.month, day=date.day)

    def fetch(self, profile_name, date, name_map=None, **kwargs):
        """Fetch some metrics.

        :param profile_name: The textual name of the GA profile to use.
        :param date: The date to fetch data for.
        :param name_map: A mapping from google column name to a name to return.

        Any other arguments are passed to the call to GA.

        Yields a sequence of rows.  In each row, values are mapped to the
        appropriate string, integer or float datatype.

        Date fields are added automatically:
         - a 'date' column holding an ISO format date string
         - a 'year' column holding the year number
         - a 'week' column holding the week number in the year
         - a 'week_day' column holding the ISO week-day number (1==mon, 7==sun)

        Data which is more recent than ga_latency will not be returned.

        """
        if name_map is None:
            name_map = {}

        date = self._remove_time_components_from_date(date)

        for row in self._fetch_from_ga(profile_name, date, name_map, kwargs):
            sample_rate = row.get('sampled')
            if (
                self.worst_sample_rate is None or
                self.worst_sample_rate > sample_rate
            ):
                self.worst_sample_rate = sample_rate
            yield row


class ClientContext(object):
    def __init__(self, cache_days):
        self.cache_days = cache_days
        self.afm = None
        self.cache_manager = None

    def __enter__(self):
        assert self.afm is None
        assert self.cache_manager is None
        self.afm = AuthFileManager()
        self.afm.__enter__()
        self.afm.from_env_var(os.environ["GAAUTH"])
        self.cache_manager = CacheManager(self.cache_days)
        return GAClient(self.afm, self.cache_manager)

    def __exit__(self, exc, value, tb):
        self.cache_manager.cleanup()
        return self.afm.__exit__(exc, value, tb)
