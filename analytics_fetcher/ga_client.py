"""Wrap access to GA in a high level client with a "fetch" endpoint.

"""

from .dirs import CACHE_DIR
from .ga_auth import perform_auth
from .ga_profile import get_profile
from apiclient.errors import HttpError
from datetime import datetime, timedelta
from oauth2client.client import AccessTokenRefreshError
import hashlib
import json
import logging
import os
import time


logger = logging.getLogger(__name__)


class GAError(Exception):
    pass


def cached_iterator(fn):
    cache_dir = os.path.join(CACHE_DIR, 'gacache')
    if not os.path.isdir(cache_dir):
        logger.info("Making cache dir %s", cache_dir)
        os.makedirs(cache_dir)

    def wrapped(self, *args, **kwargs):
        assert isinstance(self, GAClient)
        h = hashlib.sha1(repr([args, kwargs])).hexdigest()
        path = os.path.join(cache_dir, h)
        if os.path.exists(path):
            logger.info("Serving GA request from cache")
            with open(path) as fobj:
                for row in fobj:
                    yield json.loads(row)
            return
        logger.info("Performing GA request %s", path)
        sampled = False
        try:
            with open(path + '.tmp', 'wb') as fobj:
                for result in fn(self, *args, **kwargs):
                    if result.get('sampled') is not None:
                        sampled = True
                    fobj.write(json.dumps(result, separators=(',', ':')) + '\n')
                    yield result
        except:
            os.unlink(path + '.tmp')
            raise
        if False and sampled:
            # Don't cache sampled results
            os.unlink(path + '.tmp')
        else:
            os.rename(path + '.tmp', path)

    return wrapped


class GAClient(object):
    def __init__(self):
        self._last_request = None

        # Worst sampling rate that we've seen.  None if none seen.
        # Callers of the client may reset this to None, and read it.
        self.worst_sample_rate = None

        # Time until we can trust that GA has processed the data.
        self.ga_latency = timedelta(hours=4)

    def _ensure_init_ga(self):
        """Initialise GA connection if not already done.

        Looks up profile ids, etc.

        """
        if self._last_request is not None:
            return
        try:
            self.service = perform_auth()
            self.profiles = {
                'search': get_profile(
                    self.service, 'www.gov.uk', 'UA-26179049-1',
                    'Q. Site search (entire site with query strings)'),
            }
        except AccessTokenRefreshError:
            logger.exception(
                "Credentials error initialising GA access",
            )
            raise GAError("Credentials error initialising GA access")
        except HttpError as error:
            logger.exception(
                "HTTP error initialising GA access: %s: %s",
                error.resp.status, error._get_reason(),
            )
            raise GAError("HTTP error initialising GA access")
        self._last_request = time.time()

    def build_ga_params(self, profile_name, ga_date, kwargs):
        profile = self.profiles[profile_name]
        params = dict(
            ids='ga:' + profile['profile_id'],
            start_date=ga_date,
            end_date=ga_date,
            samplingLevel="HIGHER_PRECISION",
            max_results=10000,
        )
        params.update(kwargs)
        return params

    @cached_iterator
    def _fetch_from_ga(self, profile_name, date, name_map, kwargs):
        """Call GA with the given profile, date and args.

        Yield an iterator of the result.

        """
        self._ensure_init_ga()

        # Rate limit by simplest possible means.
        since = time.time() - self._last_request
        if since < 1:
            time.sleep(1.0 - since)
        self._last_request = time.time()

        ga_date = date.strftime("%Y-%m-%d")

        now = datetime.now()
        latest_hour = None
        if date + timedelta(days=1) + self.ga_latency > now:
            # Some data for the selected date is not yet reliably available.
            if "ga:hour" in kwargs.get('dimensions', ''):
                # Grouping by hour, so can rely on some of the old hours.
                latest_hour = ((now - self.ga_latency).hour + 23) % 24
                if latest_hour < 0:
                    return
            else:
                # We're not grouping by hour, so can't rely on any of the data.
                return

        try:
            params = self.build_ga_params(profile_name, ga_date, kwargs)

            start_index = 1
            while True:
                resp = self.service.query.get_raw_response(
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
                        if latest_hour is not None and hour > latest_hour:
                            return None
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

        # Remove time components from date, if it has any.
        date = datetime(year=date.year, month=date.month, day=date.day)

        for row in self._fetch_from_ga(profile_name, date, name_map, kwargs):
            sample_rate = row.get('sampled')
            if (
                self.worst_sample_rate is None or
                self.worst_sample_rate > sample_rate
            ):
                self.worst_sample_rate = sample_rate
            yield row
