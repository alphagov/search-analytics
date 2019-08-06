Search analytics processing for GOV.UK
======================================

This code extracts analytics data from google analytics and processes it such
that it can be used by the site search on gov.uk for improving search result
quality.

Installation
------------

Requires python 3.4.

    virtualenv ENV
    source ENV/bin/activate
    pip install -r requirements.txt

Note for those unfamiliar with virtualenv: the "source ENV/bin/activate" line
will need to be run in each shell that you want to run the scripts in this
repository from.

Authentication with Google Analytics
------------------------------------

To make the data-fetch from Google Analytics work, you'll need to fetch a
`client_secrets.json` file from google containing credentials, and use that to
generate a refresh token.  This refresh token must then be passed to the script
via an environment variable.

Some details on generating these credentials are given in [the GA
tutorial](https://developers.google.com/analytics/solutions/articles/hello-analytics-api),
but in summary:

 - create (or already have) a google account with access to the google
   analytics profile for www.gov.uk.
 - create a project in [the google developers
   console](https://console.developers.google.com/project)
 - For the project, go to the "APIs & auth" section on the dashboard, and
   ensure that the "Analytics API" is turned on.
 - Go to the "Credentials" section on the dashboard, and click the "Create New
   Client ID" button, to create a new OAuth 2.0 client ID.
 - Pick the "Installed Application" option, and a type of "other"
 - Download the JSON for the newly created client (using the "Download JSON"
   button underneath it).
 - Run the following command to generate the refresh token.

       PYTHONPATH=. python scripts/setup_auth.py /path/to/client_secrets.json

   It will display a url which you'll need to open with a browser that's signed
   in to the google account that the client JSON was downloaded from; paste the
   result into the prompt.  The command will output (to stdout) a "GAAUTH"
   environment variable value which needs to be set when calling the fetching
   script.
 - Delete the `client_secrets.json` file after use - it shouldn't be needed
   again, and this ensures it doesn't get leaked (eg, by committing it to git).
 - Run the fetch script (`scripts/fetch.py`) with environment variables set.
   See below for details.
 - Don't commit any of the generated secrets to this git repo!  For regular
   runs from Jenkins, pass the environment variables in from the Jenkins jobs.

Fetching data
-------------

Ensure that the virtualenv is activated, and then run:

    GAAUTH='...' PYTHONPATH=. python scripts/fetch.py page-traffic.dump 14

(Where `GAAUTH` is the value obtained from the `setup_auth.py` script, and
the final argument `14` is the number of days to fetch analytics data for.)

This will generate a file called `page-traffic.dump`, which is in elasticsearch
bulk load format, and can be loaded into the search index using the `bulk_load`
script in search-api.  This contains information on the amount of traffic each
page on GOV.UK got (after some normalisation).

The fetching script fetches data from GA by making requests for each day's
data.  It caches the results for each day, so that it doesn't need to repeat
all the requests when run on a subsequent day.  By default, the cache is placed
in a directory "cache" at the top level of a checkout.  The location of the
cache can be controlled by passing a path in the `CACHE_DIR` environment
variable.  Entries which are older than 30 days will be removed from the cache
at the end of each run of the fetch script.

Running popularity update without retrieving GA data
----------------------------------------------------

When running the full script on integration and staging it is desirable that
we don't retrieve new data from GA.

This can be achieved with the following command:

```bash
./nightly-run.sh SKIP_TRAFFIC_LOAD=true
```
