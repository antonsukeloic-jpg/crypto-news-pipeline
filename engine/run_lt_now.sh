#!/bin/bash
# Run the Lithuanian news pipeline once now, in the background. Log: /root/exec_lt.log
# Watch progress: journalctl -u cnf-watcher -f
cd /root/stack || exit 1
nohup docker compose exec -T -e N8N_RUNNERS_BROKER_PORT=5682 n8n \
  n8n execute --id="$(cat /root/stack/lt_wf_id)" > /root/exec_lt.log 2>&1 &
echo "LT pipeline started (log: /root/exec_lt.log)"
