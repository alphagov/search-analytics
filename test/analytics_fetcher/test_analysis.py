from collections import Counter
import unittest

from analytics_fetcher.analysis import normalise_path, page_traffic


class TestAnalysis(unittest.TestCase):
    def test_normalise_path_without_slash(self):
        self.assertEqual(normalise_path('hello-world'), None)

    def test_normalise_path_with_smart_answer_start_page(self):
        self.assertEqual(normalise_path('/y/'), None)

    def test_normalise_path_with_smart_answer(self):
        self.assertEqual(normalise_path('/y/hello-world'), None)

    def test_normalise_path_with_query_params(self):
        self.assertEqual(normalise_path('/hello-world?foo=bar&baz=bar'), '/hello-world')

    def test_normalise_path_ignore_trailing_slash(self):
        self.assertEqual(normalise_path(
            '/hello-world/'), '/hello-world')

    def test_normalise_path_not_empty_string(self):
        self.assertEqual(normalise_path(
            '/'), '/')

    def test_page_traffic_no_errors_no_none(self):
        traffic = {
            '/fred': [250, False],
            '/wilma': [400, False],
            '/wilma?pet=dino': [99, False],
            '/barney?partner=betty': [1, False]
        }

        expected = Counter({'/wilma': 499, '/fred': 250, '/barney': 1})

        self.assertEqual(page_traffic(traffic), expected)

    def test_page_traffic_with_errors(self):
        traffic = {
            '/fred': [250, False],
            '/wilma': [400, False],
            '/wilma?pet=dino': [1, True],
            '/barney?partner=betty': [1, False]
        }

        expected = Counter({'/wilma': 400, '/fred': 250, '/barney': 1})

        self.assertEqual(page_traffic(traffic), expected)

    def test_page_traffic_with_none(self):
        traffic = {
            '/fred': [250, False],
            '/wilma': [400, False],
            '/wilma?pet=dino': [1, False],
            'barney?partner=betty': [1, False]
        }

        expected = Counter({'/wilma': 401, '/fred': 250})

        self.assertEqual(page_traffic(traffic), expected)
