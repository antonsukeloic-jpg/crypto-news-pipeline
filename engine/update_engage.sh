#!/bin/bash
# Import + publish the "5HU Engagement Assistant" workflow (daily Telegram list of who to engage with + ready comments).
REPO=/root/crypto-news-pipeline; S=/root/shared; ST=/root/stack
cd $ST || exit 1
python3 $REPO/n8n/make_engage_workflow.py $S/wf_engage.json || exit 1
chown 1000:1000 $S/wf_engage.json
docker compose exec -T n8n n8n import:workflow --input=/data/shared/wf_engage.json </dev/null && echo "ENGAGE_WF_IMPORTED"
docker compose exec -T n8n n8n publish:workflow --id=FiveHuEngage0001 </dev/null && docker compose restart n8n >/dev/null && echo "ENGAGE_WF_LIVE (n8n restarted)"
rm -f $S/wf_engage.json
