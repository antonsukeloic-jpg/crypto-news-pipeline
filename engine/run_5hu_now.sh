#!/bin/bash
# Make one 5HU fashion news video now, in the background. Log: /root/exec_5hu.log
cd /root/stack || exit 1
nohup docker compose exec -T -e N8N_RUNNERS_BROKER_PORT=5684 n8n \
  n8n execute --id="$(cat /root/stack/5hu_wf_id)" > /root/exec_5hu.log 2>&1 &
echo "5HU pipeline started (log: /root/exec_5hu.log)"
