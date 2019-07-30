from collections import Counter


def normalise_path(path):
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
