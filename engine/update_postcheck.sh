#!/bin/bash
# Import + publish "5HU Post Check" (every 30 min: Metricool publish failures -> repost IG Reel without collab + Telegram note).
REPO=/root/crypto-news-pipeline; S=/root/shared; ST=/root/stack
cd $ST || exit 1
CID=$(python3 - <<'P'
import sqlite3
c=sqlite3.connect('/root/stack/n8n_data/database.sqlite')
r=c.execute("select id from credentials_entity where name='Metricool' and type='httpHeaderAuth' order by updatedAt desc limit 1").fetchone()
print(r[0] if r else '')
P
)
[ -n "$CID" ] || { echo "NO_METRICOOL_CREDENTIAL"; exit 1; }
python3 $REPO/n8n/make_postcheck_workflow.py "$CID" $S/wf_postcheck.json || exit 1
# keep what the check already knows (which failures it reported) across re-imports
python3 $REPO/engine/keep_static.py FiveHuPostChk01 $S/wf_postcheck.json
chown 1000:1000 $S/wf_postcheck.json
docker compose exec -T n8n n8n import:workflow --input=/data/shared/wf_postcheck.json </dev/null && echo "POSTCHECK_WF_IMPORTED"
docker compose exec -T n8n n8n publish:workflow --id=FiveHuPostChk01 </dev/null && docker compose restart n8n >/dev/null && echo "POSTCHECK_WF_LIVE (n8n restarted)"
rm -f $S/wf_postcheck.json
