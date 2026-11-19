#!/bin/bash
# Re-import + publish ONLY the crypto workflow (same id, keeps the Telegram router) after editing
# n8n/make_vps_workflow.py or n8n/make_crypto_upgrades.py.
REPO=/root/crypto-news-pipeline; S=/root/shared; ST=/root/stack
cd $ST || exit 1
LT_ID=$(cat $ST/lt_wf_id 2>/dev/null || echo LtNewsPipeLine01)
VIKOPS_ID=$(cat $ST/vikops_wf_id 2>/dev/null || echo VikopsAdPipeln01)
FIVEHU_ID=$(cat $ST/5hu_wf_id 2>/dev/null || echo FiveHuFashion001)
WF_ID=$(cat $ST/wf_id)
python3 $REPO/n8n/make_vps_workflow.py $REPO/n8n/workflow.json $S/wf_cr0.json "$LT_ID" "$VIKOPS_ID" "$FIVEHU_ID" >/dev/null || exit 1
python3 $REPO/n8n/make_crypto_upgrades.py $S/wf_cr0.json $S/wf_cr.json || exit 1
python3 -c "import json,sys;w=json.load(open('$S/wf_cr.json'));w['id']='$WF_ID';json.dump(w,open('$S/wf_cr.json','w'))"
chown 1000:1000 $S/wf_cr.json
docker compose exec -T n8n n8n import:workflow --input=/data/shared/wf_cr.json </dev/null && echo "CRYPTO_UPDATED $WF_ID"
docker compose exec -T n8n n8n publish:workflow --id="$WF_ID" </dev/null && docker compose restart n8n >/dev/null && echo "CRYPTO_PUBLISHED (n8n restarted)"
rm -f $S/wf_cr0.json $S/wf_cr.json
