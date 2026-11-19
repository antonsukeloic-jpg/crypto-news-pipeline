#!/bin/bash
# Public, read-only media URLs for Metricool: https://n8n.visualforma.cloud/m/<random>/<file>.mp4
# served by Caddy from /root/shared/public (only files copied there are public). Idempotent; rolls back on error.
set -u
ST=/root/stack; cd $ST || exit 1
mkdir -p /root/shared/public && chown 1000:1000 /root/shared/public
cp -n Caddyfile Caddyfile.bak-media
cp docker-compose.yml docker-compose.yml.bak-media
if ! grep -q "handle_path /m/\*" Caddyfile; then
python3 - <<'P'
s=open('/root/stack/Caddyfile').read()
old="n8n.visualforma.cloud {\n    reverse_proxy n8n:5678\n}"
assert old in s, 'unexpected Caddyfile'
s=s.replace(old,"""n8n.visualforma.cloud {
    handle_path /m/* {
        root * /srv/public
        file_server
        header Cache-Control "public, max-age=86400"
    }
    handle {
        reverse_proxy n8n:5678
    }
}""")
open('/root/stack/Caddyfile','w').write(s)
P
fi
if ! grep -q "/srv/public" docker-compose.yml; then
python3 - <<'P'
s=open('/root/stack/docker-compose.yml').read()
old="      - ./caddy_config:/config\n"
assert s.count(old)==1
s=s.replace(old, old+"      - /root/shared/public:/srv/public:ro\n")
open('/root/stack/docker-compose.yml','w').write(s)
P
fi
if docker run --rm -v $ST/Caddyfile:/etc/caddy/Caddyfile:ro caddy:2 caddy validate --config /etc/caddy/Caddyfile >/tmp/caddy_validate.log 2>&1; then
  docker compose up -d caddy </dev/null 2>&1 | tail -2
  sleep 4
  mkdir -p /root/shared/public/_t && echo ok > /root/shared/public/_t/ping.txt
  curl -s -m 10 https://n8n.visualforma.cloud/m/_t/ping.txt; echo " <- media route"
  curl -s -o /dev/null -m 10 -w "n8n UI %{http_code}\n" https://n8n.visualforma.cloud/
  rm -rf /root/shared/public/_t
  echo MEDIA_READY
else
  tail -5 /tmp/caddy_validate.log; cp Caddyfile.bak-media Caddyfile; cp docker-compose.yml.bak-media docker-compose.yml; echo MEDIA_ROLLED_BACK
fi
