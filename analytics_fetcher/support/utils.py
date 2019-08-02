from base64 import b64encode, b64decode
import json


def base64_encode(bs):
    """Convert bytes to base64"""
    return b64encode(bs).replace("\n", "")

def base64_decode(s):
    """Convert an ASCII base64 string to bytes"""
    return b64decode(s.encode('ascii'))


def to_json(obj):
    """Convert an object to a maximally compact json representation"""
    return json.dumps(obj, separators=(',', ':'))
