"""Convert data into elasticsearch bulk_update format.

"""

def path_components(path):
    result = []
    if path.startswith('/'):
        components = path.lstrip('/').split('/')
        for i in range(1, len(components) + 1):
            result.append('/' + '/'.join(components[:i]))
    return result


def page_info_docs(traffic_by_page):
    for page, info in traffic_by_page.iteritems():
        action = {
            "index": {
                "_type": "page_traffic",
                "_id": page,
            }
        }
        data = {
            "path_components": path_components(page),
        }
        for days_ago, (rank, views, views_frac) in info.items():
            data["rank_%i" % days_ago] = rank
            data["vc_%i" % days_ago] = views
            data["vf_%i" % days_ago] = views_frac
        yield action, data
