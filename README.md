Search analytics processing for GOV.UK
======================================

This code extracts analytics data from google analytics and processes it such
that it can be used by the site search on gov.uk for improving search result
quality.


Installation
------------

Requires python 2.7.

    virtualenv ENV
    . ENV/bin/activate
    pip install -r requirements.txt

Authentication with Google Analytics
------------------------------------

To make the data-fetch from Google Analytics work, a `client_secrets.json` file
containing credentials needs to be created and placed in the top level
directory of this repo.  Some details are given in [the GA
tutorial](https://developers.google.com/analytics/solutions/articles/hello-analytics-api),
but in summary:

 - create (or already have) a google account with access to the google
   analytics profile for gov.uk.
 - create a project in [the google developers
   console](https://console.developers.google.com/project)
 - For the project, go to the "APIs & auth" section on the dashboard, and
   ensure that the "Analytics API" is turned on.
 - Go to the "Credentials" section on the dashboard, and click the "Create New
   Client ID" button, to create a new OAuth 2.0 client ID.
 - Pick the "Installed Application" option, and a type of "other"
 - Download the JSON for the newly created client (using the "Download JSON" button underneath it).
 - Rename this to a file called `client_secrets.json` at the top level of the repo.

The generated `client_secrets.json` file should not be added to git!

Fetching data
-------------

Ensure that the virtualenv is activated, and then run:

    PYTHONPATH=. python scripts/fetch.py page-traffic.dump

This will generate a file called `page-traffic.dump`, which is in elasticsearch
bulk load format, and can be loaded into the search index using the `bulk_load`
script in rummager.  This contains information on the amount of traffic each
page on GOV.UK got (after some normalisation).
