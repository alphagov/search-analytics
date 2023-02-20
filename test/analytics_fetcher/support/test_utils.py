"""
Unit tests for utils.py
"""
import unittest

from analytics_fetcher.support.utils import base64_encode, base64_decode, to_json

class TestUtils(unittest.TestCase):
    """
    Testing utils.py methods
    """
    def test_base64_encode(self):
        """
        Testing converting bytes object to base64
        """
        bytes_object = bytes('abc', 'utf-8')
        self.assertEqual(base64_encode(bytes_object), b'YWJj')


    def test_base64_decode(self):
        """
        Testing an ASCII base64 string to bytes
        """
        string_object = ascii('abc')
        self.assertEqual(base64_decode(string_object + "=="), b'i\xb7')


    def test_to_json(self):
        """
        Testing converting an object to json
        """
        obj = {'key': 'value'}
        expected_output = '{"key":"value"}'
        self.assertEqual(to_json(obj), expected_output)
