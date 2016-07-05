if [ \! -d ENV ]; then virtualenv ENV; fi
. ENV/bin/activate
pip install -r requirements.txt
rm -f page-traffic.dump
PYTHONPATH=. python scripts/fetch.py page-traffic.dump 14
SEARCH_NODE=$(/usr/local/bin/govuk_node_list -c search --single-node)
ssh deploy@${SEARCH_NODE} '(cd /var/apps/rummager; govuk_setenv rummager bundle exec ./bin/bulk_load page-traffic)' < page-traffic.dump
ssh deploy@${SEARCH_NODE} '(cd /var/apps/rummager; SKIP_LINKS_INDEXING_TO_PREVENT_TIMEOUTS=1 RUMMAGER_INDEX=mainstream govuk_setenv rummager bundle exec rake rummager:migrate_index)'
ssh deploy@${SEARCH_NODE} '(cd /var/apps/rummager; SKIP_LINKS_INDEXING_TO_PREVENT_TIMEOUTS=1 RUMMAGER_INDEX=detailed govuk_setenv rummager bundle exec rake rummager:migrate_index)'
ssh deploy@${SEARCH_NODE} '(cd /var/apps/rummager; SKIP_LINKS_INDEXING_TO_PREVENT_TIMEOUTS=1 RUMMAGER_INDEX=government govuk_setenv rummager bundle exec rake rummager:migrate_index)'
ssh deploy@${SEARCH_NODE} '(cd /var/apps/rummager; SKIP_LINKS_INDEXING_TO_PREVENT_TIMEOUTS=1 RUMMAGER_INDEX=service-manual govuk_setenv rummager bundle exec rake rummager:migrate_index)'
ssh deploy@${SEARCH_NODE} '(cd /var/apps/rummager; SKIP_LINKS_INDEXING_TO_PREVENT_TIMEOUTS=1 RUMMAGER_INDEX=all govuk_setenv rummager bundle exec rake rummager:clean)'
