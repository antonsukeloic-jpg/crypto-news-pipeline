#!/usr/bin/env python3
"""Copy a workflow's current staticData (n8n DB) into a freshly generated workflow JSON before re-import."""
import json, sqlite3, sys
wid, path = sys.argv[1], sys.argv[2]
c = sqlite3.connect('file:/root/stack/n8n_data/database.sqlite?mode=ro', uri=True)
r = c.execute("select staticData from workflow_entity where id=?", (wid,)).fetchone()
if r and r[0]:
    w = json.load(open(path)); w['staticData'] = json.loads(r[0]) if isinstance(r[0], str) else r[0]
    json.dump(w, open(path, 'w'), ensure_ascii=False); print('static data kept')
