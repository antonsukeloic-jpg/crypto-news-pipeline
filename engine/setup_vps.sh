#!/bin/bash
# One-shot VPS setup: local-disk workflow, render watcher, Telegram delivery.
# Safe to re-run. Full log: /root/setup.log ; prints a short summary.
REPO=/root/crypto-news-pipeline; S=/root/shared; ST=/root/stack
exec 3>&1 >/root/setup.log 2>&1
say() { echo "$*" >&3; echo "$*"; }

# 1) shared folders, writable by the n8n container user (uid 1000)
mkdir -p $S/assets $S/jobs $S/outputs $S/processing $S/archive
chown -R 1000:1000 $S

# 2) let n8n write files into /data/shared
if ! grep -q N8N_RESTRICT_FILE_ACCESS_TO $ST/docker-compose.yml; then
  sed -i 's#^\(\s*\)- N8N_RUNNERS_ENABLED=true#&\n\1- N8N_RESTRICT_FILE_ACCESS_TO=/data/shared#' $ST/docker-compose.yml
fi
cd $ST && docker compose up -d n8n
for i in $(seq 1 30); do docker compose exec -T n8n n8n --version >/dev/null 2>&1 && break; sleep 2; done
say "N8N_FILE_ENV=$(grep -c N8N_RESTRICT_FILE_ACCESS_TO $ST/docker-compose.yml) n8n=$(docker compose exec -T n8n n8n --version 2>/dev/null | tail -1)"
NX="docker compose exec -T n8n n8n"

# 2b) community node used by the workflow (ElevenLabs), then restart n8n to load it
if ! docker compose exec -T n8n test -d /home/node/.n8n/nodes/node_modules/@elevenlabs/n8n-nodes-elevenlabs; then
  docker compose exec -T n8n sh -c 'mkdir -p ~/.n8n/nodes && cd ~/.n8n/nodes && rm -rf node_modules package-lock.json && npm install --no-audit --no-fund --omit=dev --omit=peer --legacy-peer-deps --ignore-scripts @elevenlabs/n8n-nodes-elevenlabs'
  docker compose restart n8n
  for i in $(seq 1 30); do docker compose exec -T n8n n8n --version >/dev/null 2>&1 && break; sleep 2; done
fi
say "ELEVENLABS_NODE=$(docker compose exec -T n8n test -d /home/node/.n8n/nodes/node_modules/@elevenlabs/n8n-nodes-elevenlabs && echo ok || echo missing)"

# 3) LT News Pipeline: a SEPARATE workflow (own fixed id), built from the crypto
#    VPS workflow. Imported first so the crypto router can point at its id.
#    It has no Telegram trigger and is not published: the crypto workflow's
#    /lt command and `n8n execute --id` start it.
python3 $REPO/n8n/make_vps_workflow.py $REPO/n8n/workflow.json $S/wf_base.json
python3 $REPO/n8n/make_lt_workflow.py $S/wf_base.json $S/wf_lt.json
LT_ID=$(python3 -c "import json;print(json.load(open('$S/wf_lt.json'))['id'])")
chown 1000:1000 $S/wf_lt.json
$NX import:workflow --input=/data/shared/wf_lt.json && say "LT_WORKFLOW=imported $LT_ID" || say "LT_WORKFLOW=IMPORT_FAILED"
echo "$LT_ID" > $ST/lt_wf_id
rm -f $S/wf_base.json $S/wf_lt.json

# 3a) build the local-disk crypto workflow (+ /lt router) and overwrite the existing one (same id)
python3 $REPO/n8n/make_vps_workflow.py $REPO/n8n/workflow.json $S/wf.json "$LT_ID"
$NX export:workflow --all --output=/data/shared/all_wf.json
python3 - <<'EOF'
import json
try: a = json.load(open('/root/shared/all_wf.json'))
except Exception: a = []
if isinstance(a, dict): a = [a]
w = json.load(open('/root/shared/wf.json'))
ids = [x['id'] for x in a if x.get('name') == 'Crypto Video Pipeline']
if ids: w['id'] = ids[0]
json.dump(w, open('/root/shared/wf.json', 'w'))
print('WF_IDS', ids, 'LT_IDS', [x['id'] for x in a if x.get('name') == 'LT News Pipeline'])
EOF
chown 1000:1000 $S/wf.json
$NX import:workflow --input=/data/shared/wf.json && say "WORKFLOW=imported $(python3 -c "import json;print(json.load(open('$S/wf.json')).get('id'))")" || say "WORKFLOW=IMPORT_FAILED"
python3 -c "import json;print(json.load(open('$S/wf.json')).get('id') or '')" > $ST/wf_id
rm -f $S/wf.json $S/all_wf.json

# 3b) publish (makes the Telegram /run trigger live; hourly node stays disabled),
#     then restart so n8n registers the Telegram webhook
$NX publish:workflow --id="$(cat $ST/wf_id)" && say "PUBLISHED=yes" || say "PUBLISHED=FAILED"
docker compose restart n8n
for i in $(seq 1 30); do docker compose exec -T n8n n8n --version >/dev/null 2>&1 && break; sleep 2; done
sleep 25
. $ST/telegram.env 2>/dev/null
say "TG_WEBHOOK=$(curl -s https://api.telegram.org/bot$TG_TOKEN/getWebhookInfo | python3 -c 'import json,sys;d=json.load(sys.stdin)["result"];print(d.get("url","")[:40] or "none", d.get("last_error_message",""))')"

# 4) Telegram bot token from the migrated n8n credential (never printed)
$NX export:credentials --all --decrypted --output=/data/shared/c.json
python3 - <<'EOF'
import json, os
try:
    cs = json.load(open('/root/shared/c.json'))
    tok = next((c['data'].get('accessToken') for c in cs if c.get('type') == 'telegramApi'), None)
except Exception:
    tok = None
if tok:
    open('/root/stack/telegram.env', 'w').write(f'TG_TOKEN={tok}\nTG_CHAT=694708370\n')
    os.chmod('/root/stack/telegram.env', 0o600)
print('TG_FOUND', bool(tok))
EOF
rm -f $S/c.json
say "TELEGRAM=$([ -f $ST/telegram.env ] && echo ok || echo missing)"

# 5) Remotion headless browser
cd $REPO/remotion && npm install --no-audit --no-fund && npx remotion browser ensure
say "REMOTION=$([ -d node_modules/@remotion/cli ] && echo ok || echo missing)"

# 6) watcher as a service
cat >/etc/systemd/system/cnf-watcher.service <<EOF
[Unit]
Description=CryptoNewsFactory render watcher
After=docker.service network-online.target
[Service]
ExecStart=/bin/bash $REPO/engine/watch_vps.sh
Restart=always
RestartSec=5
Environment=HOME=/root
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now cnf-watcher && systemctl restart cnf-watcher
sleep 2
say "WATCHER=$(systemctl is-active cnf-watcher)"
say "SETUP_DONE"
