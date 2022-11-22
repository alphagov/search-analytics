"""Provide access to google analytics data for search.

    Example data...
    [
        {
            'path': '/fred',
            'views': 100,
            'title': 'ignored'
        },
        {
            'path': '/fred',
            'views': 200,
            'title': 'ignored'
        },
        {
            'path': '/wilma',
            'views': 200,
            'title': 'ignored'
        }
    ]

    Result...
    {
        '/fred': [300, False],
        '/wilma': [200, False]
    }
"""


class GAData():
    """Gets page view data via the Google API"""
    def __init__(self, ga_client, date):
        self.client = ga_client
        self.date = date
        self.date_idstr = date.strftime("%Y%m%d")
        self.date_str = f'{self.date.year}-{self.date.month:02d}-{self.date.day:02d}T00:00:00Z'

    def fetch_traffic_info(self):
        """Fetch info on views of pages.

        Returns a dict keyed by path.  Values are a tuple of:

         - total number of views (unique per path)
         - boolean: True iff the page consistently returns a not found error.

        """
        not_found_title = 'Page not found - 404 - GOV.UK'
        result = {}
        for row in self.get_traffic_from_api():
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

    def get_traffic_from_api(self):
        """Searches the Google API for page view data and returns
            all matching rows.
        """
        return self.client.fetch(
            'search', self.date,
            metrics='ga:uniquePageViews',
            dimensions='ga:pagePath,ga:pageTitle',
            sort='-ga:uniquePageViews',
            name_map={
                'uniquePageViews': 'views',
                'pagePath': 'path',
                'pageTitle': 'title',
            },
        )
