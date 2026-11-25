#!/bin/bash
# Import + publish the "5HU Growth Agent" (twice a week: own metrics -> bounded strategy changes, silent).
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
[ -s $S/5hu_strategy.json ] || { echo '{"story_focus":"","hook_notes":"","caption_notes":"","words_min":22,"words_max":28,"carousel":true,"tiktok_carousel":"ab"}' > $S/5hu_strategy.json; chown 1000:1000 $S/5hu_strategy.json; }
python3 $REPO/n8n/make_growth_workflow.py "$CID" $S/wf_growth.json || exit 1
chown 1000:1000 $S/wf_growth.json
docker compose exec -T n8n n8n import:workflow --input=/data/shared/wf_growth.json </dev/null && echo "GROWTH_WF_IMPORTED"
docker compose exec -T n8n n8n publish:workflow --id=FiveHuGrowth0001 </dev/null && docker compose restart n8n >/dev/null && echo "GROWTH_WF_LIVE (n8n restarted)"
rm -f $S/wf_growth.json
