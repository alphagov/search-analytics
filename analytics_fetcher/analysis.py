"""Utilities for turning page traffic data into
    a simplified and reduced list.
    Example traffic data...
    {
        '/fred': [250, False],
        '/fred?partner=wilma': [250, False]
    }
    Result...
    Counter(
        {
            '/fred': 500
        }
    )
"""

from collections import Counter


def normalise_path(path):
    """Reduces a given URL to a base path"""
    if not path.startswith('/'):
        return None
    # Ignore pages within smart answers.  We can identify smart answers by
    # looking for a url component which is exactly 'y'.
    if '/y/' in path:
        return None
    # Ignore query parameters
    path = path.split('?', 1)[0]
    # Ignore trailing /
    path = path.rstrip('/')
    # Special case so that / isn't represented as an empty string
    if len(path) == 0:
        path = '/'
    return path


def page_traffic(raw_traffic):
    """Agregates a number of records in the form:
        [URL, hit_count, is_erroring] to be a
        Counter containing records in the form:
        { "/base_path", total_hit_count }.
        Ignores all records where the url is
        erroring.
    """
    result = Counter()

    # Add up traffic to urls which normalise to the same thing.
    for path, (traffic, erroring) in raw_traffic.items():
        if erroring:
            continue
        path = normalise_path(path)
        if path is None:
            continue
        result[path] += traffic

    return result
