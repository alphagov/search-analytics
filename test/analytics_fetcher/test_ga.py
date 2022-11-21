import unittest
import datetime
from unittest.mock import Mock
from analytics_fetcher.ga import GAData


class TestGa(unittest.TestCase):
    def setUp(self):
        self.date = datetime.datetime(2020, 1, 1)
        self.client = Mock()
        self.client.fetch = Mock(return_value=[])
        self.ga_data = GAData(self.client, self.date)

    def test_init(self):
        self.assertEqual(self.ga_data.client, self.client)
        self.assertEqual(self.ga_data.date, self.date)
        self.assertEqual(self.ga_data.date_idstr, "20200101")
        self.assertEqual(self.ga_data.date_str, "2020-01-01T00:00:00Z")

    def test_fetch_traffic_info_empty(self):
        expected = {}
        self.assertEqual(self.ga_data.fetch_traffic_info(), expected)

    def test_fetch_traffic_info_without_any_duplicate_paths(self):
        self.client.fetch = Mock(return_value=[
                {
                    'path': '/fred',
                    'views': 100,
                    'title': 'ignored'
                },
                {
                    'path': '/wilma',
                    'views': 200,
                    'title': 'ignored'
                }
            ]
        )
        expected = {
            '/fred': [100, False],
            '/wilma': [200, False]
        }
        self.assertEqual(self.ga_data.fetch_traffic_info(), expected)

    def test_fetch_traffic_info_with_a_duplicate_path(self):
        self.client.fetch = Mock(return_value=[
                {
                    'path': '/fred',
                    'views': 100,
                    'title': 'ignored'
                },
                {
                    'path': '/fred',
                    'views': 200,
                    'title': 'ignored'
                }
            ]
        )
        expected = { '/fred': [300, False] }
        self.assertEqual(self.ga_data.fetch_traffic_info(), expected)
