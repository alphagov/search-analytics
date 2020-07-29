#!/usr/bin/env python

import os

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

packages = [
    "analytics_fetcher",
]

requires = [
    "requests==2.24.0",
    "pytest==6.0.0",
    "mock==1.0.1",
    "gapy==0.0.9",
]

try:
    long_description = open(
        os.path.join(os.path.dirname(__file__), 'README.md')).read()
except IOError:
    long_description = None

setup(
    name="govuk_search_analytics",
    version="0.1",
    description="gov.uk search analytics fetcher",
    long_description=long_description,
    author="Richard Boulton",
    author_email="richard.boulton@digital.cabinet-office.gov.uk",
    url="https://github.com/alphagov/govuk-search-analytics",
    packages=packages,
    package_dir={"analytics_fetcher": "analytics_fetcher"},
    include_package_data=True,
    install_requires=requires,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python",
    ]
)
