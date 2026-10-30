#!/bin/bash
# Re-import ONLY the LT News Pipeline workflow (same id) after a change to
# n8n/make_lt_workflow.py. Leaves the crypto workflow and n8n untouched.
REPO=/root/crypto-news-pipeline; S=/root/shared; ST=/root/stack
cd $ST || exit 1
python3 $REPO/n8n/make_vps_workflow.py $REPO/n8n/workflow.json $S/wf_base.json >/dev/null
python3 $REPO/n8n/make_lt_workflow.py $S/wf_base.json $S/wf_lt.json
chown 1000:1000 $S/wf_lt.json
docker compose exec -T n8n n8n import:workflow --input=/data/shared/wf_lt.json && echo "LT_UPDATED $(cat $ST/lt_wf_id)"
docker compose exec -T n8n n8n publish:workflow --id="$(cat $ST/lt_wf_id)" && docker compose restart n8n >/dev/null && echo "LT_PUBLISHED (n8n restarted)"
rm -f $S/wf_base.json $S/wf_lt.json
