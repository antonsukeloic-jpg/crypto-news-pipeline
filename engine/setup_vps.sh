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

# 3) build the local-disk workflow and overwrite the existing one (same id)
python3 $REPO/n8n/make_vps_workflow.py $REPO/n8n/workflow.json $S/wf.json
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
print('WF_IDS', ids)
EOF
chown 1000:1000 $S/wf.json
$NX import:workflow --input=/data/shared/wf.json && say "WORKFLOW=imported $(python3 -c "import json;print(json.load(open('$S/wf.json')).get('id'))")" || say "WORKFLOW=IMPORT_FAILED"
rm -f $S/wf.json $S/all_wf.json

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
