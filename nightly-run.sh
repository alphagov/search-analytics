#!/bin/bash
set -e
set -o pipefail

if [[ -z $TARGET_APPLICATION ]]; then
  TARGET_APPLICATION=rummager
fi

SEARCH_NODE=$(/usr/local/bin/govuk_node_list -c search --single-node)
if [[ -z $SKIP_TRAFFIC_LOAD ]]; then
  if [ \! -d ENV ]; then virtualenv -p /opt/python2.7/bin/python ENV; fi
  . ENV/bin/activate
  pip install -r requirements.txt
  rm -f page-traffic.dump
  PYTHONPATH=. python scripts/fetch.py page-traffic.dump 14
  ssh deploy@${SEARCH_NODE} "(cd /var/apps/${TARGET_APPLICATION}; govuk_setenv ${TARGET_APPLICATION} bundle exec ./bin/page_traffic_load)" < page-traffic.dump
  ssh deploy@${SEARCH_NODE} "(cd /var/apps/${TARGET_APPLICATION}; govuk_setenv ${TARGET_APPLICATION} bundle exec rake rummager:clean RUMMAGER_INDEX=page-traffic)"
fi

ssh deploy@${SEARCH_NODE} "(cd /var/apps/${TARGET_APPLICATION}; PROCESS_ALL_DATA=true RUMMAGER_INDEX=detailed govuk_setenv ${TARGET_APPLICATION} bundle exec rake rummager:update_popularity)"

# Wait 40 minutes, to let the Sidekiq jobs be processed to avoid
# taking up lots of Redis memory
sleep 2400

ssh deploy@${SEARCH_NODE} "(cd /var/apps/${TARGET_APPLICATION}; PROCESS_ALL_DATA=true RUMMAGER_INDEX=government govuk_setenv ${TARGET_APPLICATION} bundle exec rake rummager:update_popularity)"

# Wait 40 minutes, to let the Sidekiq jobs be processed to avoid
# taking up lots of Redis memory
sleep 2400

ssh deploy@${SEARCH_NODE} "(cd /var/apps/${TARGET_APPLICATION}; RUMMAGER_INDEX=govuk govuk_setenv ${TARGET_APPLICATION} bundle exec rake rummager:update_popularity)"
