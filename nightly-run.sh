#!/bin/bash
set -e
set -o pipefail

if [[ -z $TARGET_APPLICATION ]]; then
  TARGET_APPLICATION=search-api
fi

SEARCH_NODE=$(/usr/local/bin/govuk_node_list -c search --single-node)
if [[ -z $SKIP_TRAFFIC_LOAD ]]; then
  docker run --rm -e GAAUTH="$GAAUTH" -v "$(pwd)/:/govuk-search-analytics" python:3.8.0 bash -c """
  cd /govuk-search-analytics
  pip install -r requirements.txt
  rm -f page-traffic.dump
  python3 scripts/fetch.py page-traffic.dump 14
  """

  ssh deploy@${SEARCH_NODE} "(cd /var/apps/${TARGET_APPLICATION}; govuk_setenv ${TARGET_APPLICATION} bundle exec ./bin/page_traffic_load)" < page-traffic.dump
  ssh deploy@${SEARCH_NODE} "(cd /var/apps/${TARGET_APPLICATION}; govuk_setenv ${TARGET_APPLICATION} bundle exec rake search:clean SEARCH_INDEX=page-traffic)"
fi

ssh deploy@${SEARCH_NODE} "(cd /var/apps/${TARGET_APPLICATION}; PROCESS_ALL_DATA=true SEARCH_INDEX=detailed govuk_setenv ${TARGET_APPLICATION} bundle exec rake search:update_popularity)"

# Wait 40 minutes, to let the Sidekiq jobs be processed to avoid
# taking up lots of Redis memory
echo "Going to sleep for 40 minutes to let the Sidekiq jobs get processed"
sleep 2400

ssh deploy@${SEARCH_NODE} "(cd /var/apps/${TARGET_APPLICATION}; PROCESS_ALL_DATA=true SEARCH_INDEX=government govuk_setenv ${TARGET_APPLICATION} bundle exec rake search:update_popularity)"

# Wait 40 minutes, to let the Sidekiq jobs be processed to avoid
# taking up lots of Redis memory
echo "Going to sleep for a second time (40 minutes again) to let the Sidekiq jobs get processed"
sleep 2400

ssh deploy@${SEARCH_NODE} "(cd /var/apps/${TARGET_APPLICATION}; SEARCH_INDEX=govuk govuk_setenv ${TARGET_APPLICATION} bundle exec rake search:update_popularity)"
