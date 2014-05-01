"""Provide access to google analytics data for search.

"""

from .ga_client import GAClient, GAError
from collections import Counter
from urlparse import urlparse, parse_qs
import hashlib
import logging
import math
import re
import unicodedata


__all__ = ['GAData', 'GAError']
logger = logging.getLogger(__name__)
linkpos_re = re.compile('\Aposition=(?P<pos>[0-9]+)(?:&sublink=(?P<sublink>[^&]+))?\Z')

# String used to mark inconsistent values
INCONSISTENT = '(inconsistent)'


def extract_search(url):
    '''Extract a search from a url.'''
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    q = query.get('q', ())
    if q:
        q = q[0]
    else:
        q = u''
    return q


def normalise_search(search):
    return unicodedata.normalize('NFKC', search).strip().lower()


def id_from_string(s):
    '''Make a unique id by hashing a string.'''
    return hashlib.sha1(s.encode('utf8')).digest() \
          .encode('base64').replace('\n', '')[:10]


def split_path(path):
    '''Split a path appropriately for indexing.

    Returns a dict containing:
     - path: the full path
     - path1: component 1 of the path
     - path2: components 1 to 2 of the path if there are at least 2 components
     - path3: components 1 to 3 of the path if there are at least 3 components

    '''
    num_components = 3
    result = {
        'path': path,
    }
    if path.startswith('/'):
        components = path.lstrip('/').split('/', num_components + 1)
        for i in range(1, num_components + 1):
            if len(components) < i:
                break
            result['path%d' % (i, )] = '/' + '/'.join(components[:i])
    return result


def parse_position(posstr):
    mo = linkpos_re.search(posstr)
    if not mo:
        logger.error('Invalid position %r', posstr)
        return 0, None
    return int(mo.group('pos')), mo.group('sublink')


class SearchAggregator(object):
    """Aggregate information on searches.

    Provides aggregated information in a form suitable for indexing in
    elasticsearch.

    """
    def __init__(self, date_info):
        self.date_info = date_info

        # One doc for each search-path pair
        self.searches_by_page = {}

        # One doc for each path searches started on
        self.pages_starting_searches = {}

        # One doc for each search performed
        self.searches = {}

    @staticmethod
    def page_info_fields(info):
        """Calculate fields which hold information about a page.

        Returns a dict.

        """
        orgs = info.get('orgs', ())
        format = info.get('format')
        doc = {}
        doc['orgs'] = tuple(orgs)
        doc['org_count'] = len(orgs)
        if orgs:
            doc['first_org'] = orgs[0]
        if format:
            doc['formats'] = (format,)
        return doc

    @staticmethod
    def update_page_info_fields(doc, info):
        """Update page info fields in an existing document.

        Similar to page_info_fields(), but merges the fields with those in an
        existing document.

        """
        orgs = info.get('orgs') or ()
        format = info.get('format')
        if orgs:
            doc['orgs'] = tuple(sorted(set(doc['orgs'] + tuple(orgs))))
            doc['org_count'] = len(doc['orgs'])
        if format:
            doc['formats'] = tuple(sorted(set(doc.get('formats', ()) + (format,))))

    def add_search(self, search_fields, views, info):
        search_id = id_from_string(search_fields['search'])
        if search_id in self.searches:
            doc = self.searches[search_id]
            doc['views'] += views
            self.update_page_info_fields(doc, info)
        else:
            doc = dict(search_fields)
            doc['views'] = views
            doc.update(self.date_info)
            doc.update(self.page_info_fields(info))
            self.searches[search_id] = doc

    def add_page(self, page_fields, views, info):
        path = page_fields['path']
        if path in self.pages_starting_searches:
            doc = self.pages_starting_searches[path]
            doc['views'] += views
        else:
            doc = dict(page_fields)
            doc['views'] = views
            if info.get('not_found'):
                doc['not_found'] = True
            doc['total_views'] = info.get('total_views', 0)
            doc.update(self.date_info)
            doc.update(self.page_info_fields(info))
            self.pages_starting_searches[path] = doc

    def add_search_page(self, search_fields, page_fields, views, info):
        path = page_fields['path']
        search = search_fields['search']
        search_by_page_id = id_from_string('%s!!!%s' % (path, search))
        if search_by_page_id in self.searches_by_page:
            doc = self.searches_by_page[search_by_page_id]
            doc['views'] += views
            self.update_page_info_fields(doc, info)
        else:
            doc = dict(page_fields)
            doc.update(search_fields)
            doc['views'] = views
            doc.update(self.date_info)
            doc.update(self.page_info_fields(info))
            if info.get('not_found'):
                doc['page_not_found'] = True
            self.searches_by_page[search_by_page_id] = doc


class GAData(object):
    def __init__(self, date):
        self.client = GAClient()
        self.date = date
        self.date_idstr = date.strftime("%Y%m%d")
        self.date_str = '%04d-%02d-%02dT00:00:00Z' % (
            self.date.year,
            self.date.month,
            self.date.day,
        )

    def _date_info(self):
        """Return date information in a format to be indexed in elasticsearch.

        Returns a dict, so we can easily add extra breakdowns of date (such as
        day of week) as separate fields.

        """
        return {
            'date': self.date_str,
        }

    def _fetch_search_clicks_with_position(self):
        """Fetch counts of search click positions.

        This theoretically represents all clicks on search results, but
        sometimes the cookie value doesn't get through (eg, browsers not
        permitting cookies) so we only get a proportion of these clicks.

        Returns three dicts:
         - { offset: count }
         - { norm_query: { offset: { (query, path): count }}}
         - FIXME

        """
        total_positions = Counter()
        positions_by_query = {}
        top_clicks_by_query = {}

        for row in self.client.fetch(
            'search', self.date,
            dimensions='ga:pagePath,ga:previousPagePath,ga:customVarValue21',
            metrics='ga:pageViews',
            sort='-ga:pageViews',
            filters='ga:previousPagePath=~^/search\\\?;ga:pagePath!~^/search\\\?;ga:customVarValue21=~.',
            name_map={
                'customVarValue21': 'position',
                'pageViews': 'views',
                'pagePath': 'path',
                'previousPagePath': 'search_path',
            },
        ):
            views = row['views']
            search = extract_search(row['search_path'])
            path = row['path']
            norm_search = normalise_search(search)
            position, sublink = parse_position(row['position'])
            if not position:
                logger.warn("Unable to parse position %r", position)
                # If this happens frequently, it will increase the estimate at
                # which cookie loss is happening, and mess up the statistics.
                continue

            total_positions[position] += views

            positions_by_query.setdefault(norm_search, {}) \
                .setdefault(position, Counter())[(search, path)] += views

            if position == 1:
                top = top_clicks_by_query.get(norm_search)
                if top is None:
                    top_clicks_by_query[norm_search] = [path, views]
                else:
                    if top[0] != INCONSISTENT:
                        if top[0] != path:
                            top[0] = INCONSISTENT
                        else:
                            top[1] += views

        return total_positions, positions_by_query, top_clicks_by_query

    def _fetch_search_next_pages(self):
        """Fetch counts of page views following a search page.
        
        Excludes search refinements.  This can be compared to counts on clicks
        with positions, to identify page views following a search page which
        _weren't_ clicks on search results; these are an indication of users
        who weren't satisfied by the search results.

        Returns three dicts.  Values in all cases are the total number of page
        views of the destination page which were preceded by a search page.
        The keys are:

         - Mapping from query to views
         - Mapping from page path to views.
         - Mapping from (query, page path) to views.

        """
        next_page_counts_by_query = Counter()
        next_page_counts_by_path = Counter()
        next_page_counts = Counter()
        # Fetch all page views following a search page.  This can be compared
        # to the previous results, to identify page views following a search
        # page which _weren't_ clicks on search results; these are an
        # indication of users who weren't satisfied by the search results.
        for row in self.client.fetch(
            'search', self.date,
            dimensions='ga:pagePath,ga:previousPagePath',
            metrics='ga:pageViews',
            sort='-ga:pageViews',
            filters='ga:previousPagePath=~^/search\\\?;ga:pagePath!~^/search\\\?',
            name_map={
                'pageViews': 'views',
                'pagePath': 'path',
                'previousPagePath': 'search_path',
            },
        ):
            views = row['views']
            search = extract_search(row['search_path'])
            norm_search = normalise_search(search)
            path = row['path']
            next_page_counts_by_query[norm_search] += views
            next_page_counts_by_path[path] += views
            next_page_counts[(norm_search, path)] += views
        return next_page_counts_by_query, next_page_counts_by_path, next_page_counts

    def _fetch_search_refinements(self):
        """Fetch all search refinements.

        Returns a dict mapping from (normalised) search to a Counter, which in
        turn maps from (normalised) refinement search to views.

        """
        # Fetch all search refinements.
        refinements_by_search = {}
        for row in self.client.fetch(
            'search', self.date,
            dimensions='ga:pagePath,ga:previousPagePath',
            metrics='ga:pageViews',
            sort='-ga:pageViews',
            filters='ga:previousPagePath=~^/search\\\?;ga:pagePath=~^/search\\\?',
            name_map={
                'pageViews': 'views',
                'pagePath': 'path',
                'previousPagePath': 'search_path',
            },
        ):
            views = row['views']
            search = extract_search(row['search_path'])
            norm_search = normalise_search(search)
            refinement = extract_search(row['path'])
            norm_refinement = normalise_search(refinement)
            refinements_by_search.setdefault(norm_search, Counter())[norm_refinement] += views
        return refinements_by_search

    def _fetch_search_exits(self):
        """Fetch a count of exits from search pages.

        This returns a dict mapping from (normalised) search query to a count
        of the number of sessions which ended on the results page for that
        query.

        """
        exits = Counter()
        for row in self.client.fetch(
            'search', self.date,
            dimensions='ga:exitPagePath',
            metrics='ga:pageViews',
            sort='-ga:pageViews',
            filters='ga:exitPagePath=~^/search\\\?',
            name_map={
                'pageViews': 'views',
                'exitPagePath': 'search_path',
            },
        ):
            views = row['views']
            search = extract_search(row['search_path'])
            norm_search = normalise_search(search)
            exits[norm_search] += views
        return exits

    def _fetch_searches(self):
        """Fetch details of how often searches were performed.

        Returns a dict mapping from normalised search to count of times it was
        performed.

        """
        searches = Counter()
        for row in self.client.fetch(
            'search', self.date,
            dimensions='ga:pagePath,ga:previousPagePath', 
            metrics='ga:pageViews',
            sort='-ga:pageViews',
            filters='ga:pagePath=~^/search\\\?',
            name_map={
                'pageViews': 'views',
                'pagePath': 'search_path',
            },
        ):
            views = row['views']
            search = extract_search(row['search_path'])
            norm_search = normalise_search(search)
            searches[norm_search] += views
        return searches

    def _estimate_cookie_visibility(self,
                                    top_clicks_by_query,
                                    next_page_counts):
        """Estimate the rate at which we are seeing the position tracking cookies.

        We don't always get the cookie values which are set when a user clicks
        on a link in a search result page.  This method tries to determine what
        rate this happens at.

        Assumptions:
         - cookie loss is evenly distributed across queries.
         - for queries where the top result is clicked on more than 5 times,
           all cases where the next page viewed is the top result were a result
           of the top result being clicked (ie, no external navigation / going
           via google, etc, happened).  We only assume this is true for items
           with 5 clicks, because

        Method:
         - select queries where the top result was clicked more than 5 times
           (and there was a consistent top result).
         - count the number of times we have a recorded position for that
           result.
         - count the number of times that result was viewed after the page for
           that query.

        Returns (number of times we have cookie) / (number of views)

        """
        # Number of views of the selected search result pages with an
        # associated cookie.
        total_with_cookie = 0
        # Number of views of the selected search result page following the
        # search page.
        total = 0
        for query, (path, views) in top_clicks_by_query.items():
            if path == INCONSISTENT or views < 5:
                continue
            total_with_cookie += views
            total += next_page_counts.get((query, path), 0)
        if total == 0:
            visibility = 1.0
        else:
            visibility = float(total_with_cookie) / float(total)
        logger.info(
            "Estimating cookie visibility at %0.2f%% based on %d cookie views",
            visibility * 100.0, total_with_cookie)
        return visibility

    def _calculate_overall_stats(
        self,
        total_positions,
        next_page_counts,
        refinements_by_search,
        searches,
        cookie_visibility,
    ):
        """Calculate overall statistics about search performance.

        """
        count_with_cookie = sum(total_positions.values())
        if count_with_cookie == 0:
            average_position = 0
        else:
            average_position = (
                float(sum(position * count for position, count in total_positions.items()))
                / count_with_cookie
            )


        count_next_pages = sum(next_page_counts.values())
        logger.info("Number of search -> result transitions with cookie: %d",
                    count_with_cookie)
        logger.info("Number of search -> result transitions with cookie, adjusted: %d",
                    count_with_cookie / cookie_visibility)
        logger.info("Number of search -> next_page transitions: %d",
                    count_next_pages)
        search_abandons = int(count_next_pages - (count_with_cookie / cookie_visibility))
        logger.info("Search with no click, but continued on site: %d",
                    search_abandons)

        refinements = sum(
            sum(refinement_counts.values())
            for refinement_counts in refinements_by_search.values()
        )

        searches_performed = sum(searches.values())
        logger.info("Searches performed: %d", searches_performed)
        logger.info("Search refinements: %d", refinements)
        search_exits = int(
            searches_performed
            - refinements
            - count_next_pages
        )
        logger.info("Search exits: %d", search_exits)
        search_1_click = (
            searches_performed
            - refinements
            - search_exits
            - search_abandons
        )

        return dict(
            _type='result_click_stats',
            _id=self.date_str,
            date=self.date,
            cookie_visibility=cookie_visibility,
            average_position=average_position,
            searches_performed=searches_performed,
            refinements=refinements,
            refinements_rate=(float(refinements) / searches_performed),
            search_exits=search_exits,
            search_exits_rate=(float(search_exits) / searches_performed),
            search_abandons=search_abandons,
            search_abandons_rate=(float(search_abandons) / searches_performed),
            search_1_click=search_1_click,
            search_1_click_rate=(float(search_1_click) / searches_performed),
            sampled=self.client.worst_sample_rate,
        )

    def fetch_search_result_clicks(self):
        """Fetch info on clicks on search results.

        This uses the tracking of positions of clicks, combined with tracking
        the previous page path, to get counts of the number of queries which
        led to a click on the result.

        It does a separate lookup for page views following a search result page
        which 

        Finally it does a lookup to get counts of search exits for the queries.

        """
        # Fetch the data we need.
        (
            total_positions,
            positions_by_query,
            top_clicks_by_query,
        ) = self._fetch_search_clicks_with_position()
        (
            next_page_counts_by_query,
            next_page_counts_by_path,
            next_page_counts,
        ) = self._fetch_search_next_pages()
        refinements_by_search = self._fetch_search_refinements()
        searches = self._fetch_searches()

        cookie_visibility = self._estimate_cookie_visibility(
            top_clicks_by_query,
            next_page_counts,
        )

        # Yield documents about individual searches.
        for doc in self._search_result_clicks(positions_by_query):
            yield doc

        # Yield a document about overall statistics of search
        stats = self._calculate_overall_stats(
            total_positions,
            next_page_counts,
            refinements_by_search,
            searches,
            cookie_visibility,
        )
        stats['date'] = self.date_str
        stats['_id'] = self.date_idstr
        stats['total_clicks'] = self.total_clicks
        stats['missed_clicks'] = self.missed_clicks
        stats['total_clicks'] = self.total_clicks
        yield stats


    def _search_result_clicks(self, positions_by_query):
        """Yield a doc for every search-result combination seen.

        Also yield a doc for every search, indicating the ranking performance
        of that search.

        """
        # Yield a doc for each combination of (search, destination page, rank)
        # recording number of times that was viewed.
        queries = []
        total_clicks = 0
        missed_clicks = 0
        for norm_search, positions in positions_by_query.items():
            max_position = max(positions.keys())
            counts = [0] * max_position
            for position, result_info in positions.items():
                for (search, path), count in result_info.items():
                    doc = {
                        '_type': 'search_result_click',
                        '_id': id_from_string('%s!%s!%s!%s' % (
                            self.date_idstr,
                            search,
                            position,
                            path,
                        )),
                        'date': self.date_str,
                        'search': search,
                        'position': position,
                        'path': path,
                        # Combined position_path field is used for facet
                        # calculations; this is only needed because the
                        # terms_stats facet doesn't allow a script to be used
                        # for the key field - with elasticsearch 1.0
                        # aggregations, this field wouldn't be needed.
                        'position_path': "%04d%s" % (position, path),
                        'norm_search': norm_search,
                        'clicks': count,
                    }
                    doc.update(split_path(path))
                    yield doc
                counts[position - 1] = sum(result_info.values())
            missed = estimate_missed_clicks(counts)
            missed_clicks += missed
            total_clicks += sum(counts)
            doc = {
                '_type': 'search_stats',
                '_id': id_from_string('%s!%s' % (
                    self.date_idstr,
                    norm_search,
                )),
                'date': self.date_str,
                'norm_search': norm_search,
                'clicks': sum(counts),
                'missed': missed,
            }
            yield doc

        # Want to return this value, but can't because we're a generator
        self.missed_clicks = missed_clicks
        self.total_clicks = total_clicks

    def fetch_traffic_info(self):
        """Fetch info on views of pages.

        Returns a dict keyed by path.  Values are a tuple of:

         - total number of views (unique per session)
         - boolean: True iff the page consistently returns a not found error.

        """
        not_found_title = 'Page not found - 404 - GOV.UK'
        result = {}
        for row in self.client.fetch(
            'search', self.date,
            metrics='ga:uniquePageViews',
            dimensions='ga:pagePath,ga:pageTitle',
            sort='-ga:uniquePageViews',
            name_map={
                'uniquePageViews': 'views',
                'pagePath': 'path',
                'pageTitle': 'title',
            },
        ):
            path = row['path']
            views = row['views']
            title = row['title']
            not_found = (title == not_found_title)
            item = result.get(path)
            if item is None:
                result[path] = [views, not_found]
            else:
                item[0] += views
                item[1] = (item[1] and not_found)
        return result

    def fetch_search_traffic_by_start(self, traffic_info):
        """Fetch information on traffic from pages associated with an org.

        Yields an item for each combination of start page and search.
        
        number of searches which started on a page
        associated with an org.
        
        Specifically, for each page that a search led
        to which is marked with any organisation codes, the number of pageviews
        divided by the number of organisation codes is added to a count for
        each organisation. This may be based on sampled data.

        """
        date_info = self._date_info(self.date)

        agg = SearchAggregator(date_info)

        for row in self.client.fetch(
            'search', self.date,
            name_map={
                'uniquePageviews': 'views',
                'pagePath': 'search_path',
                'previousPagePath': 'path',
            },
            metrics='ga:uniquePageviews',
            filters='ga:pagePath=~^/search\\?;ga:previousPagePath!~^/search\\?',
            dimensions="ga:previousPagePath,ga:pagePath",
        ):
            # Look up and normalise associated information
            views = row['views']
            path = row['path']
            search_path = row['search_path']
            sample_rate = row.get('sample_rate')

            traffic = traffic_info.get(path)
            if traffic is None:
                # This can happen if the GA query to get the traffic was
                # sampled.  In this case, missing entries are likely to be low
                # traffic, so we just guess that they had the same number of
                # views as the query.
                not_found = False
                total_views = views
            else:
                total_views, not_found = traffic

            if not_found:
                info = {
                    'not_found': True,
                    'total_views': total_views
                }
            else:
                info = self.url_to_info.lookup(path)
                info['total_views'] = total_views
            search = extract_search(search_path)
            norm_search = normalise_search(search)

            search_fields = {
                'search': search,
                'norm_search': norm_search,
            }
            page_fields.update(split_path(path))

            # Build or update a document for each search
            agg.add_search(search_fields, views, info)
            agg.add_page(page_fields, views, info)
            agg.add_search_page(search_fields, page_fields, views, info)

            row['search'] = search
            row['norm_search'] = norm_search
            if not_found:
                row['not_found'] = not_found

        from pprint import pprint
        pprint(agg.searches.values()[0])
        pprint(agg.pages_starting_searches.values()[0])
        pprint(agg.searches_by_page.values()[0])

        for id, doc in agg.searches.items():
            doc['_id'] = id
            doc['_type'] = 'search'
            yield doc

        for id, doc in agg.pages_starting_searches.items():
            doc['search_from_rate'] = float(doc['views']) / doc['total_views']
            doc['_id'] = id
            doc['_type'] = 'start_page'
            yield doc

        for id, doc in agg.searches_by_page.items():
            doc['_id'] = id
            doc['_type'] = 'search_start_page'
            yield doc

    def fetch_search_traffic_destination_orgs(self):
        """Fetch traffic info on searches leading to pages marked with orgs.

        Returns an indication of the number of searches which led to a page
        associated with an org. Specifically, for each page that a search led
        to which is marked with any organisation codes, the number of pageviews
        divided by the number of organisation codes is added to a count for
        each organisation. This may be based on sampled data.

        """
        scores = Counter()
        for row in self.client.fetch(
            'search', self.date,
            name_map={
                'uniquePageviews': 'views',
                'customVarValue9': 'org_codes',
            },
            metrics='ga:uniquePageviews',
            sort='-ga:uniquePageviews',
            filters='ga:previousPagePath=~^/search',
            dimensions="ga:customVarValue9",
        ):
            orgs = filter(None, row['org_codes'].lstrip('<').rstrip('>').split('><'))
            if len(orgs) == 0:
                continue
            # Sampling sometimes causes the views count to be returned as 0.
            # Force it to be at least 1.
            views = max(int(row['views']), 1)
            score = float(views) / len(orgs)
            for org in orgs:
                scores[org] += score
        date_info = self._date_info()
        return [
            dict(
                org_code=org_code,
                score=score,
                _id=org_code,
                _type='search_dest_by_org',
                **date_info
            )
            for (org_code, score) in scores.items()
        ]

    def fetch_search_traffic_destination_formats(self):
        """Fetch traffic info on searches leading to pages marked with formats.

        Returns an count of the number of searches which led to a page
        associated with a format.  This may be based on sampled data.

        """
        scores = Counter()
        for row in self.client.fetch(
            'search', self.date,
            name_map={
                'uniquePageviews': 'views',
                'customVarValue2': 'format',
            },
            metrics='ga:uniquePageviews',
            sort='-ga:uniquePageviews',
            filters='ga:previousPagePath=~^/search',
            dimensions="ga:customVarValue2",
        ):
            # Sampling sometimes causes the views count to be returned as 0.
            # Force it to be at least 1.
            views = max(int(row['views']), 1)
            scores[row['format']] += views
        date_info = self._date_info()
        return [
            dict(
                format=format,
                score=score,
                _id=format,
                _type='search_dest_by_format',
                **date_info
            )
            for (format, score) in scores.items()
        ]
