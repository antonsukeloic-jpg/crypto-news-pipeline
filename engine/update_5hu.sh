#!/bin/bash
# Re-import + publish ONLY the 5HU fashion workflow (same id) after editing n8n/make_5hu_workflow.py.
REPO=/root/crypto-news-pipeline; S=/root/shared; ST=/root/stack
cd $ST || exit 1
python3 $REPO/n8n/make_vps_workflow.py $REPO/n8n/workflow.json $S/wf_base.json >/dev/null
python3 $REPO/n8n/make_lt_workflow.py $S/wf_base.json $S/wf_lt.json >/dev/null
python3 $REPO/n8n/make_5hu_workflow.py $S/wf_lt.json $S/wf_5hu.json
chown 1000:1000 $S/wf_5hu.json
docker compose exec -T n8n n8n import:workflow --input=/data/shared/wf_5hu.json && echo "FIVEHU_UPDATED $(cat $ST/5hu_wf_id)"
docker compose exec -T n8n n8n publish:workflow --id="$(cat $ST/5hu_wf_id)" && docker compose restart n8n >/dev/null && echo "FIVEHU_PUBLISHED (n8n restarted)"
rm -f $S/wf_base.json $S/wf_lt.json $S/wf_5hu.json
