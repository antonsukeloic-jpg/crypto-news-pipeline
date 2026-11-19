#!/bin/bash
# Import + publish the "Social Publish (Metricool)" workflow. Needs the n8n Header Auth credential named "Metricool"
# (X-Mc-Auth = Metricool REST API token, created by the owner in the n8n UI).
REPO=/root/crypto-news-pipeline; S=/root/shared; ST=/root/stack
cd $ST || exit 1
CID=$(python3 - <<'P'
import sqlite3
c=sqlite3.connect('/root/stack/n8n_data/database.sqlite')
r=c.execute("select id from credentials_entity where name='Metricool' and type='httpHeaderAuth' order by updatedAt desc limit 1").fetchone()
print(r[0] if r else '')
P
)
[ -n "$CID" ] || { echo "NO_METRICOOL_CREDENTIAL (create Header Auth 'Metricool' in n8n)"; exit 1; }
python3 $REPO/n8n/make_publish_workflow.py "$CID" $S/wf_pub.json || exit 1
chown 1000:1000 $S/wf_pub.json
docker compose exec -T n8n n8n import:workflow --input=/data/shared/wf_pub.json </dev/null && echo "PUBLISH_WF_IMPORTED cred=$CID"
docker compose exec -T n8n n8n publish:workflow --id=SocialPublish001 </dev/null && docker compose restart n8n >/dev/null && echo "PUBLISH_WF_LIVE (n8n restarted)"
rm -f $S/wf_pub.json
