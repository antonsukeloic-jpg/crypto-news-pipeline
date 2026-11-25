#!/usr/bin/env python3
"""5HU Growth Agent - looks at our own numbers twice a week and tunes the pipeline by itself (owner: no approvals, no messages).

Loop: Metricool analytics (IG Reels, TikTok, YouTube Shorts, FB Reels, last 21 days) + what we posted
(/data/shared/5hu_featured.jsonl) -> Claude analyses and decides -> validated, bounded changes to
/data/shared/5hu_strategy.json, which the 5HU workflow, the publish workflow and the render watcher read on every run.
Every run is logged in /data/shared/5hu_growth_log.json (observations, changes, reasons) - ask Claude to read it.

What the agent may change (nothing else): story_focus, hook_notes, caption_notes (short text notes added to the prompts,
they never override the brand rules), words_min / words_max (script length, 16-34), carousel on/off,
tiktok_carousel (ab | photo | slideshow | off). Brand rules, posting, schedule, accounts and code are out of its reach.

    python3 n8n/make_growth_workflow.py <metricool_credential_id> out.json
"""
import json, sys, uuid

CID = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/wf_growth.json"
ANTH_CRED = {"anthropicApi": {"id": "3pYNdkLM3jdNYjyM", "name": "Anthropic account"}}
MC_CRED = {"httpHeaderAuth": {"id": CID, "name": "Metricool"}}
BLOG, USER = "8237757", "6373812"
WF_ID = "FiveHuGrowth0001"


def node(name, typ, ver, params, pos, **extra):
    n = {"parameters": params, "type": typ, "typeVersion": ver, "position": pos, "id": str(uuid.uuid4()), "name": name}
    n.update(extra)
    return n


def metricool(name, path, x):
    q = [("blogId", BLOG), ("userId", USER), ("timezone", "Europe/Vilnius"),
         ("from", "={{ $now.minus({days: 21}).toFormat(\"yyyy-MM-dd'T'00:00:00\") }}"),
         ("to", "={{ $now.toFormat(\"yyyy-MM-dd'T'23:59:59\") }}")]
    return node(name, "n8n-nodes-base.httpRequest", 4.2, {
        "url": "https://app.metricool.com/api/v2/analytics/" + path,
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendQuery": True, "queryParameters": {"parameters": [{"name": k, "value": v} for k, v in q]},
        "options": {"timeout": 60000, "response": {"response": {"neverError": True}}}},
        [x, 0], credentials=MC_CRED, executeOnce=True, onError="continueRegularOutput", alwaysOutputData=True)


def read_text(name, path, x):
    return [
        node("Read " + name, "n8n-nodes-base.readWriteFile", 1, {"operation": "read", "fileSelector": path, "options": {}}, [x, 200],
             executeOnce=True, onError="continueRegularOutput", alwaysOutputData=True),
        node(name + " Text", "n8n-nodes-base.extractFromFile", 1, {"operation": "text", "binaryPropertyName": "data", "destinationKey": "data", "options": {}},
             [x + 200, 200], executeOnce=True, onError="continueRegularOutput", alwaysOutputData=True),
    ]


COMPILE_JS = r"""
// one row per 5HU Reel we posted: what it was + how it did on each platform (only what's needed, compact)
const arr = (n) => { try { const j = $(n).first().json; const d = j.data !== undefined ? j.data : j; return Array.isArray(d) ? d : []; } catch (e) { return []; } };
const txt = (n) => { try { return String($(n).first().json.data || ''); } catch (e) { return ''; } };
const ms = (v) => {   // Metricool dates: "2026-11-24T16:27:51", {dateTime, timezone}, epoch s/ms
  if (v == null) return 0;
  if (typeof v === 'number') return v < 1e12 ? v * 1000 : v;
  if (typeof v === 'object') v = v.dateTime || v.date || '';
  const t = Date.parse(String(v).length <= 19 ? String(v) + 'Z' : String(v));
  return isNaN(t) ? 0 : t;
};
const featured = txt('Featured Text').split('\n').map(l => { try { return JSON.parse(l); } catch (e) { return null; } }).filter(Boolean)
  .filter(r => Number(r.ts) > Date.now() - 21 * 864e5).sort((a, b) => a.ts - b.ts);
const ig = arr('IG Reels').map(r => ({ t: ms(r.publishedAt), views: r.views, reach: r.reach, avgWatchSec: r.averageWatchTime, skipRate: r.reelsSkipRate,
  likes: r.likes, saves: r.saved, shares: r.shares, comments: r.comments, lenSec: r.durationSeconds }));
const tt = arr('TikTok').map(r => ({ t: ms(r.createTime), type: r.type, views: r.viewCount, likes: r.likeCount, shares: r.shareCount, comments: r.commentCount, lenSec: r.duration }));
const yt = arr('YouTube').map(r => ({ t: ms(r.publishedAt), views: r.views, avgViewSec: r.averageViewDuration, likes: r.likes, comments: r.comments, shares: r.shares, lenSec: r.durationSeconds }));
const fb = arr('FB Reels').map(r => ({ t: ms(r.created), plays: r.blueReelsPlayCount, avgWatchSec: r.postVideoAvgTimeWatchedSeconds, reactions: r.postVideoReactions, lenSec: r.length }));
const near = (list, t, lo, hi) => { let best = null, bd = 1e15; for (const x of list) { const d = x.t - t; if (d >= lo && d <= hi && Math.abs(d) < bd) { bd = Math.abs(d); best = x; } } return best; };
const strip = (x) => { if (!x) return null; const o = Object.assign({}, x); delete o.t; return o; };
const H = 3600e3;
const posts = featured.map(f => {
  const tr = near(tt, f.ts, -1 * H, 1 * H);                         // the Reel on TikTok (createTime is epoch, no timezone shift)
  const tc = near(tt.filter(x => x !== tr), f.ts, 1.5 * H, 6 * H);   // the carousel ~3 h later: PHOTO = photo carousel, VIDEO = slideshow
  return { episode: f.episode, hoursOld: Math.round((Date.now() - f.ts) / H), title: f.title, hook: f.hook,
    // IG / YT / FB lists hold only Reels/Shorts; their dates may come in local time (Vilnius +2/+3 h), so allow a wider window
    instagram: strip(near(ig, f.ts, -3 * H, 3.5 * H)), tiktok: strip(tr), youtube: strip(near(yt, f.ts, -3 * H, 3.5 * H)), facebook: strip(near(fb, f.ts, -3 * H, 3.5 * H)),
    tiktokCarousel: tc ? { variant: tc.type === 'PHOTO' ? 'photo' : 'slideshow', views: tc.views, likes: tc.likes, shares: tc.shares } : null };
});
let strategy = {}; try { strategy = JSON.parse(txt('Strategy Text') || '{}'); } catch (e) { strategy = {}; }
let log = []; try { log = JSON.parse(txt('Log Text') || '[]'); } catch (e) { log = []; }
const judged = posts.filter(p => p.hoursOld >= 24).length;
return [{ json: { posts, judged, strategy, recentLog: log.slice(-6), logLen: log.length,
  apiOk: { instagram: ig.length, tiktok: tt.length, youtube: yt.length, facebook: fb.length } } }];
"""

PROMPT = (
    "=You are the growth agent of 5HU, a fully automatic short-video account (TikTok, Instagram Reels, YouTube Shorts, Facebook Reels) "
    "that spots fashion's next big names first. Two videos a day are made and posted by a pipeline without any human. Your job: read our own "
    "numbers and tune the pipeline's strategy so more people watch to the end, save, share, comment and follow. Nobody reviews your changes, "
    "so be careful: small, evidence-based steps, keep what works, undo what made things worse.\n\n"
    "WHAT DRIVES GROWTH (in this order): 1) people not swiping away in the first 2-3 s (Instagram skipRate, avg watch time vs length, "
    "YouTube avgViewSec, TikTok views as a proxy for distribution), 2) shares and saves per view, 3) comments, 4) likes.\n\n"
    "OUR POSTS (last 21 days, newest last; only posts at least 24 h old are fair to judge; tiktokCarousel = the carousel posted ~3 h after the Reel):\n"
    "{{ JSON.stringify($json.posts) }}\n\nPosts old enough to judge: {{ $json.judged }}. Data rows from Metricool: {{ JSON.stringify($json.apiOk) }}\n\n"
    "CURRENT STRATEGY:\n{{ JSON.stringify($json.strategy) }}\n\n"
    "YOUR LAST DECISIONS (oldest first, with your reasons - check whether they worked):\n{{ JSON.stringify($json.recentLog) }}\n\n"
    "WHAT YOU CAN CHANGE (nothing else exists for you):\n"
    "- story_focus: a short note (max 400 chars) for the story picker - which kinds of stories to prefer or avoid, based on what performed "
    "(e.g. clothes and accessories you can see beat store openings and business news). The picker still only picks new/independent designers.\n"
    "- hook_notes: a short note (max 400 chars) for the scriptwriter about openings, first images, pacing and the closing question that worked or failed.\n"
    "- caption_notes: a short note (max 300 chars) for the caption writer (style, length, which kind of question gets comments).\n"
    "- words_min / words_max: voiceover length in words (16-34; the video is ~0.6 s per word + 3 s outro).\n"
    "- carousel: true/false (the photo carousel 3 h after each Reel on Instagram/Facebook/TikTok).\n"
    "- tiktok_carousel: ab (keep alternating) | photo (swipe carousel, TikTok adds music) | slideshow (video with our music) | off. "
    "Only leave 'ab' when each variant has at least 4 judged posts and one is clearly better.\n\n"
    "RULES: notes must be concrete and grounded in the numbers, in English, no URLs, no @handles, never contradict the brand (new names only, "
    "no big houses, no celebrities, no links to other platforms). With fewer than 6 judged posts change at most ONE thing (or nothing) and say "
    "what you are watching. Never change more than 3 things in one run. If a past change made things worse, revert it. If the data is missing "
    "or broken, change nothing.\n\n"
    "Output ONLY JSON: {\"observations\":[\"max 6 short facts with numbers\"],\"changes\":[{\"knob\":\"...\",\"to\":...,\"why\":\"...\"}],"
    "\"watching\":\"what you'll check next time\"}"
)

VALIDATE_JS = r"""
const c = $('Compile').first().json;
const cur = Object.assign({ story_focus: '', hook_notes: '', caption_notes: '', words_min: 22, words_max: 28, carousel: true, tiktok_carousel: 'ab' }, c.strategy || {});
let out = { observations: [], changes: [], watching: '' };
try { const raw = $input.first().json.content[0].text; out = JSON.parse(raw.slice(raw.indexOf('{'), raw.lastIndexOf('}') + 1)); } catch (e) { out = { observations: ['agent output unreadable - nothing changed'], changes: [], watching: '' }; }
const clean = (x, n) => String(x || '').replace(/https?:\/\/\S+/g, '').replace(/@\w[\w.]*/g, '').replace(/\s+/g, ' ').trim().slice(0, n);
const next = Object.assign({}, cur); const applied = [];
const limit = (c.judged || 0) < 6 ? 1 : 3;
for (const ch of (Array.isArray(out.changes) ? out.changes : []).slice(0, limit)) {
  const k = String(ch.knob || ''); let v = ch.to;
  if (k === 'story_focus') v = clean(v, 400);
  else if (k === 'hook_notes') v = clean(v, 400);
  else if (k === 'caption_notes') v = clean(v, 300);
  else if (k === 'words_min') v = Math.min(30, Math.max(16, parseInt(v, 10) || cur.words_min));
  else if (k === 'words_max') v = Math.min(34, Math.max(20, parseInt(v, 10) || cur.words_max));
  else if (k === 'carousel') v = v === true || v === 'true';
  else if (k === 'tiktok_carousel') { v = String(v); if (!['ab', 'photo', 'slideshow', 'off'].includes(v)) continue; }
  else continue;   // unknown knob: ignored
  if (JSON.stringify(next[k]) === JSON.stringify(v)) continue;
  applied.push({ knob: k, from: next[k], to: v, why: clean(ch.why, 300) });
  next[k] = v;
}
if (next.words_max < next.words_min + 4) next.words_max = Math.min(34, next.words_min + 4);
next.updated = new Date().toISOString();
const entry = { at: next.updated, judged: c.judged, data: c.apiOk, observations: (out.observations || []).slice(0, 6).map(o => clean(o, 300)),
  changes: applied, watching: clean(out.watching, 300) };
let log = []; try { log = JSON.parse($('Log Text').first().json.data || '[]'); } catch (e) { log = []; }
log = log.concat([entry]).slice(-60);
const b1 = await this.helpers.prepareBinaryData(Buffer.from(JSON.stringify(next, null, 1), 'utf8'), '5hu_strategy.json', 'application/json');
const b2 = await this.helpers.prepareBinaryData(Buffer.from(JSON.stringify(log, null, 1), 'utf8'), '5hu_growth_log.json', 'application/json');
return [{ json: { file: '/data/shared/5hu_strategy.json', applied }, binary: { data: b1 } },
        { json: { file: '/data/shared/5hu_growth_log.json' }, binary: { data: b2 } }];
"""

nodes = [
    node("Twice a week", "n8n-nodes-base.scheduleTrigger", 1.2,
         {"rule": {"interval": [{"field": "cronExpression", "expression": "40 6 * * 1,4"}]}}, [0, 0]),
    metricool("IG Reels", "reels/instagram", 220),
    metricool("TikTok", "posts/tiktok", 440),
    metricool("YouTube", "posts/youtube", 660),
    metricool("FB Reels", "reels/facebook", 880),
]
nodes += read_text("Featured", "/data/shared/5hu_featured.jsonl", 1100)
nodes += read_text("Strategy", "/data/shared/5hu_strategy.json", 1500)
nodes += read_text("Log", "/data/shared/5hu_growth_log.json", 1900)
nodes += [
    node("Compile", "n8n-nodes-base.code", 2, {"jsCode": COMPILE_JS}, [2300, 0]),
    node("Decide", "@n8n/n8n-nodes-langchain.anthropic", 1,
         {"modelId": {"__rl": True, "value": "claude-sonnet-4-6", "mode": "list", "cachedResultName": "claude-sonnet-4-6"},
          "messages": {"values": [{"content": PROMPT}]}, "options": {"maxTokens": 2000}}, [2520, 0],
         credentials=ANTH_CRED, onError="continueRegularOutput", alwaysOutputData=True),
    node("Validate", "n8n-nodes-base.code", 2, {"jsCode": VALIDATE_JS}, [2740, 0]),
    node("Write Files", "n8n-nodes-base.readWriteFile", 1,
         {"operation": "write", "fileName": "={{ $json.file }}", "dataPropertyName": "data", "options": {}}, [2960, 0]),
]
names = [n["name"] for n in nodes]
wf = {"id": WF_ID, "name": "5HU Growth Agent", "nodes": nodes,
      "connections": {a: {"main": [[{"node": b, "type": "main", "index": 0}]]} for a, b in zip(names, names[1:])},
      "settings": {"executionOrder": "v1", "timezone": "Europe/Vilnius"}, "active": False, "pinData": {}}
json.dump(wf, open(OUT, "w"), ensure_ascii=False, indent=1)
print("OK ->", OUT)
