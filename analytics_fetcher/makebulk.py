"""Convert data into elasticsearch bulk_update format.

"""


def path_components(path):
    """Creates an array with the base path and all given paths.
    """
    result = []
    if path.startswith('/'):
        components = path.lstrip('/').split('/')
        for i in range(1, len(components) + 1):
            result.append('/' + '/'.join(components[:i]))
    return result


def page_info_docs(traffic_by_page):
    """Creates a result set containing two elements.
        First element contains the action details,
        and the second the data details. Both are
        dict's.

        Example traffic data...
        { "/fred": { 1: [1, 10, 0.1] } }

        Result: action...
        { "index": {"_type": "page-traffic", "_id": "/fred"} }

        Result: data...
        { "path_components": ["/fred"], "rank_1": 1, "vc_1": 10, "vf_1": 0.1 }
    """
    for page, info in traffic_by_page.items():
        action = {
            "index": {
                "_type": "page-traffic",
                "_id": page,
            }
        }
        data = {
            "path_components": path_components(page),
        }
        for days_ago, (rank, views, views_frac) in list(info.items()):
            data["rank_%i" % days_ago] = rank
            data["vc_%i" % days_ago] = views
            data["vf_%i" % days_ago] = views_frac
        yield action, data
