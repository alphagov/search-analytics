import json


def base64(s):
    """Convert a string to base64"""
    return s.encode('base64').replace("\n", "")


def to_json(obj):
    """Convert an object to a maximally compact json representation"""
    return json.dumps(obj, separators=(',', ':'))
