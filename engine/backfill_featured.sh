#!/bin/bash
# One-time: rebuild /root/shared/5hu_featured.jsonl + the 5HU episode counter from the approval records (live since 2026-11-20 18:20).
python3 - <<'P'
import json, glob, os, re
A = '/root/shared/approvals'
rows = []
for d in glob.glob(A + '/*.done'):
    rec = dict(l.split('=', 1) for l in open(d).read().splitlines() if '=' in l)
    job = rec.get('job', '')
    m = re.search(r'5hu_job_(\d{13})', job)
    if not m or int(m.group(1)) < 1795191000000 or not os.path.exists(job):
        continue
    dec = A + '/' + os.path.basename(d)[:-5] + '.decision'
    act = open(dec).read().strip() if os.path.exists(dec) else 'auto'
    if act in ('skip', 'alt'):
        continue
    j = json.load(open(job))
    vo = j.get('voiceover', '') or ''
    hook = re.split(r'(?<=[.!?])\s', vo.strip(), 1)[0][:160] if vo else ''
    sc = j.get('scenes') or [{}]
    title = ((j.get('carousel') or {}).get('cover') or sc[0].get('on_screen_text') or hook)[:80]
    rows.append({'ts': int(m.group(1)), 'title': title, 'hook': hook,
                 'creators': j.get('creators', []), 'episode': None})
rows.sort(key=lambda r: r['ts'])
base = 2   # 2026-11-19 purple + 2026-11-20 09:10 Armani went out before the approval flow
for i, r in enumerate(rows):
    r['episode'] = base + i + 1
with open('/root/shared/5hu_featured.jsonl', 'w') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
open('/root/shared/5hu_episode', 'w').write(str(base + len(rows)))
print('featured rows:', len(rows), '| with accounts:', sum(1 for r in rows if any(c.get('instagram') or c.get('tiktok') for c in r['creators'])), '| episode counter:', base + len(rows))
P
