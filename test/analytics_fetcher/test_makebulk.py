import unittest

from analytics_fetcher.makebulk import page_info_docs, path_components


class TestMakebulk(unittest.TestCase):
    def test_single_component(self):
        self.assertEqual(path_components('/fred'), ['/fred'])

    def test_multiple_components(self):
        self.assertEqual(path_components('/fred/wilma'), ['/fred', '/fred/wilma'])

    def test_page_info_docs(self):
        traffic = {
            "/fred": { 1: [1, 10, 0.1] }
        }
        expected_action = {
            "index": {"_type": "page-traffic", "_id": "/fred"}
        }
        expected_data = {
            "path_components": ["/fred"],
            "rank_1": 1,
            "vc_1": 10,
            "vf_1": 0.1
        }

        results = list(page_info_docs(traffic))
        self.assertEqual(expected_action, results[0][0])
        self.assertEqual(expected_data, results[0][1])
