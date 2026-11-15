#!/bin/bash
# Make one Vikops ad video now (random angle), in the background. Log: /root/exec_vikops.log
cd /root/stack || exit 1
nohup docker compose exec -T -e N8N_RUNNERS_BROKER_PORT=5683 n8n \
  n8n execute --id="$(cat /root/stack/vikops_wf_id)" > /root/exec_vikops.log 2>&1 &
echo "Vikops pipeline started (log: /root/exec_vikops.log)"
