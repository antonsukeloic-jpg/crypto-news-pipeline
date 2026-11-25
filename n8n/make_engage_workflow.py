#!/usr/bin/env python3
"""5HU engagement assistant: one Telegram message every morning with who to engage with + ready comments.

Fully automatic commenting on other accounts is NOT built on purpose (Instagram/TikTok spam detection -> shadowban
or lost account). This prepares everything; the owner taps a link, taps a comment to copy it, pastes it. ~5 min/day.

Source: /data/shared/5hu_featured.jsonl (one line per published 5HU Reel, written by engine/watch_vps.sh:
ts, title, hook, creators [{name, instagram, tiktok, website}], episode).

    python3 n8n/make_engage_workflow.py out.json
"""
import json, sys, uuid

OWNER_CHAT = "694708370"
TG_CRED = {"telegramApi": {"id": "MsHdBVyurDnoXcyo", "name": "Telegram account"}}
ANTH_CRED = {"anthropicApi": {"id": "3pYNdkLM3jdNYjyM", "name": "Anthropic account"}}
WF_ID = "FiveHuEngage0001"

COLLECT_JS = r"""
// featured designers of the last 7 days (newest first, unique, only accounts we verified when we posted)
let lines = [];
try {
  const buf = await this.helpers.getBinaryDataBuffer(0, 'data');
  lines = buf.toString('utf8').split('\n').map(l => { try { return JSON.parse(l); } catch (e) { return null; } }).filter(Boolean);
} catch (e) { lines = []; }
const since = Date.now() - 7 * 24 * 3600 * 1000;
const seen = new Set(); const designers = [];
for (const l of lines.filter(l => Number(l.ts) >= since).sort((a, b) => b.ts - a.ts)) {
  for (const c of (l.creators || [])) {
    const key = String(c.name || '').toLowerCase();
    if (!key || seen.has(key) || !(c.instagram || c.tiktok)) continue;
    seen.add(key);
    designers.push({ name: c.name, instagram: c.instagram || '', tiktok: c.tiktok || '', story: String(l.title || l.hook || '').slice(0, 160) });
  }
}
const stories = lines.filter(l => Number(l.ts) >= since).map(l => String(l.title || l.hook || '').slice(0, 120)).slice(-8);
return [{ json: { designers: designers.slice(0, 6), stories } }];
"""

PROMPT = (
    "=You help the owner of 5HU (an account that spots fashion's next big names first) engage by hand on Instagram and TikTok. "
    "Write comments a real fashion insider would leave: specific, warm, a real opinion, 6-16 words, lowercase-friendly, at most one emoji. "
    "Never generic (\"nice post\", \"love this\", \"great work\"), never links, never hashtags, never ask for a follow, never mention 5HU "
    "except in the second comment for a featured designer, which may say we featured them (e.g. \"had to feature this on our page\").\n\n"
    "DESIGNERS WE FEATURED THIS WEEK (name, our story about them):\n{{ JSON.stringify($json.designers.map(d => ({name: d.name, story: d.story}))) }}\n\n"
    "THIS WEEK'S STORIES (for tone):\n{{ JSON.stringify($json.stories) }}\n\n"
    "Output ONLY JSON: {\"designers\":[{\"name\":\"...\",\"comments\":[\"...\",\"...\"]}],\"discover\":[\"...\",\"...\",\"...\"]}\n"
    "- designers: same order and names as given, 2 comments each, about their work in general (we don't know which post they made last).\n"
    "- discover: 3 comments that fit most emerging-designer posts (a look, a new collection, a studio shot) without sounding copy-pasted."
)

FORMAT_JS = r"""
const esc = (t) => String(t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const base = $('Collect').first().json;
let out = { designers: [], discover: [] };
try { const raw = $input.first().json.content[0].text; out = JSON.parse(raw.slice(raw.indexOf('{'), raw.lastIndexOf('}') + 1)); } catch (e) {}
const byName = {}; for (const d of (out.designers || [])) byName[String(d.name || '').toLowerCase()] = d.comments || [];
const L = [];
L.push('🤝 <b>5HU engagement</b> · about 5 minutes');
L.push('Tap a comment to copy it, open the link, paste. Change a word or two so it sounds like you.');
L.push('');
L.push('1️⃣ <b>Reply to everyone who commented on us</b>');
L.push('<a href="https://www.instagram.com/5hu.fashion/">Instagram</a> · <a href="https://www.tiktok.com/@5hu.fashion">TikTok</a> · <a href="https://www.youtube.com/@5hu.fashion/shorts">YouTube</a> · <a href="https://www.facebook.com/5hu.fashion">Facebook</a>');
if ((base.designers || []).length) {
  L.push('');
  L.push('2️⃣ <b>Designers we featured</b> - comment on their newest post');
  base.designers.forEach((d, i) => {
    const links = [];
    if (d.instagram) links.push('<a href="https://www.instagram.com/' + encodeURIComponent(d.instagram) + '/">IG @' + esc(d.instagram) + '</a>');
    if (d.tiktok) links.push('<a href="https://www.tiktok.com/@' + encodeURIComponent(d.tiktok) + '">TikTok @' + esc(d.tiktok) + '</a>');
    L.push((i + 1) + '. <b>' + esc(d.name) + '</b> · ' + links.join(' · '));
    for (const c of (byName[String(d.name).toLowerCase()] || []).slice(0, 2)) L.push('   ▸ <code>' + esc(c) + '</code>');
  });
}
L.push('');
L.push((base.designers || []).length ? '3️⃣' : '2️⃣');
L[L.length - 1] += ' <b>Discover</b> - 3 comments on fresh posts here:';
L.push('<a href="https://www.instagram.com/explore/tags/newdesigners/">IG #newdesigners</a> · <a href="https://www.instagram.com/explore/tags/emergingdesigners/">IG #emergingdesigners</a> · <a href="https://www.tiktok.com/tag/newdesigners">TikTok #newdesigners</a>');
for (const c of (out.discover || []).slice(0, 3)) L.push('   ▸ <code>' + esc(c) + '</code>');
L.push('');
L.push('<i>Real opinions get replies and profile visits. Never links or "follow us".</i>');
let text = L.join('\n');
if (text.length > 4000) text = text.slice(0, 3990) + '…';
return [{ json: { text } }];
"""


def node(name, typ, ver, params, pos, **extra):
    n = {"parameters": params, "type": typ, "typeVersion": ver, "position": pos, "id": str(uuid.uuid4()), "name": name}
    n.update(extra)
    return n


nodes = [
    node("Every morning", "n8n-nodes-base.scheduleTrigger", 1.2,
         {"rule": {"interval": [{"field": "cronExpression", "expression": "5 10 * * *"}]}}, [0, 0]),
    node("Read featured", "n8n-nodes-base.readWriteFile", 1,
         {"operation": "read", "fileSelector": "/data/shared/5hu_featured.jsonl", "options": {}}, [220, 0],
         onError="continueRegularOutput", alwaysOutputData=True),
    node("Collect", "n8n-nodes-base.code", 2, {"jsCode": COLLECT_JS}, [440, 0]),
    node("Write comments", "@n8n/n8n-nodes-langchain.anthropic", 1,
         {"modelId": {"__rl": True, "value": "claude-sonnet-4-6", "mode": "list", "cachedResultName": "claude-sonnet-4-6"},
          "messages": {"values": [{"content": PROMPT}]}, "options": {"maxTokens": 1200}}, [660, 0],
         credentials=ANTH_CRED, onError="continueRegularOutput", alwaysOutputData=True),
    node("Format", "n8n-nodes-base.code", 2, {"jsCode": FORMAT_JS}, [880, 0]),
    node("Send to Telegram", "n8n-nodes-base.telegram", 1.2,
         {"chatId": OWNER_CHAT, "text": "={{ $json.text }}",
          "additionalFields": {"appendAttribution": False, "parse_mode": "HTML", "disable_web_page_preview": True}},
         [1100, 0], credentials=TG_CRED),
]
names = [n["name"] for n in nodes]
wf = {
    "id": WF_ID, "name": "5HU Engagement Assistant", "nodes": nodes,
    "connections": {a: {"main": [[{"node": b, "type": "main", "index": 0}]]} for a, b in zip(names, names[1:])},
    "settings": {"executionOrder": "v1", "timezone": "Europe/Vilnius"}, "active": False, "pinData": {},
}
out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/wf_engage.json"
json.dump(wf, open(out, "w"), ensure_ascii=False, indent=1)
print("OK ->", out)
