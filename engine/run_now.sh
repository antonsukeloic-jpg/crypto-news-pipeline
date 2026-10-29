#!/bin/bash
# Run the pipeline once now, in the background. Log: /root/exec.log
# Watch progress: journalctl -u cnf-watcher -f
cd /root/stack || exit 1
nohup docker compose exec -T -e N8N_RUNNERS_BROKER_PORT=5681 n8n \
  n8n execute --id="$(cat /root/stack/wf_id)" > /root/exec.log 2>&1 &
echo "pipeline started (log: /root/exec.log)"
