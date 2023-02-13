from base64 import b64encode, b64decode
import json


def base64_encode(byte_string):
    """Convert bytes to base64"""
    return b64encode(byte_string).replace(b"\n", b"")


def base64_decode(string):
    """Convert an ASCII base64 string to bytes"""
    return b64decode(string.encode('ascii'))


def to_json(obj):
    """Convert an object to a maximally compact json representation"""
    return json.dumps(obj, separators=(',', ':'))
