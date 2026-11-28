#!/usr/bin/env python3
"""5HU Growth Agent - every morning it reviews each of our posts once it has 2 days of numbers, keeps a playbook of lessons and
evolves the pipeline in small, checked steps (owner 2026-11-25: autopilot, every post examined, little by little better; no messages).

Loop: Metricool analytics (IG Reels, TikTok, YouTube Shorts, FB Reels, last 21 days) + what we posted
(/data/shared/5hu_featured.jsonl) -> Claude analyses and decides -> validated, bounded changes to
/data/shared/5hu_strategy.json, which the 5HU workflow, the publish workflow and the render watcher read on every run.
Every run is logged in /data/shared/5hu_growth_log.json (observations, changes, reasons); every post review in
/data/shared/5hu_reviews.json (verdict vs our own baseline, why, lesson). The playbook (max 8 lessons) lives in the strategy
file as `lessons` and goes into the story + script prompts. One change at a time; a knob can change again only after 4 judged
posts (except a revert), so every change gets a fair test.

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
// every 5HU Reel we posted (21 days): what it was + how it did; which ones need a review; our own baseline; open experiments
const arr = (n) => { try { const j = $(n).first().json; const d = j.data !== undefined ? j.data : j; return Array.isArray(d) ? d : []; } catch (e) { return []; } };
const txt = (n) => { try { return String($(n).first().json.data || ''); } catch (e) { return ''; } };
const ms = (v) => {   // Metricool dates: "2026-11-24T16:27:51", {dateTime, timezone}, epoch s/ms
  if (v == null) return 0;
  if (typeof v === 'number') return v < 1e12 ? v * 1000 : v;
  if (typeof v === 'object') v = v.dateTime || v.date || '';
  const t = Date.parse(String(v).length <= 19 ? String(v) + 'Z' : String(v));
  return isNaN(t) ? 0 : t;
};
const H = 3600e3, JUDGE_H = 48;
const featured = txt('Featured Text').split('\n').map(l => { try { return JSON.parse(l); } catch (e) { return null; } }).filter(Boolean)
  .filter(r => Number(r.ts) > Date.now() - 21 * 864e5).sort((a, b) => a.ts - b.ts);
const ig = arr('IG Reels').map(r => ({ t: ms(r.publishedAt), views: r.views, reach: r.reach, avgWatchSec: r.averageWatchTime, skipRate: r.reelsSkipRate,
  likes: r.likes, saves: r.saved, shares: r.shares, comments: r.comments, follows: r.follows, lenSec: r.durationSeconds }));
const tt = arr('TikTok').map(r => ({ t: ms(r.createTime), type: r.type, views: r.viewCount, likes: r.likeCount, shares: r.shareCount, comments: r.commentCount, lenSec: r.duration }));
const yt = arr('YouTube').map(r => ({ t: ms(r.publishedAt), views: r.views, avgViewSec: r.averageViewDuration, likes: r.likes, comments: r.comments, shares: r.shares, subs: r.subscribersGained, lenSec: r.durationSeconds }));
const fb = arr('FB Reels').map(r => ({ t: ms(r.created), plays: r.blueReelsPlayCount, avgWatchSec: r.postVideoAvgTimeWatchedSeconds, reactions: r.postVideoReactions, lenSec: r.length }));
const near = (list, t, lo, hi) => { let best = null, bd = 1e15; for (const x of list) { const d = x.t - t; if (d >= lo && d <= hi && Math.abs(d) < bd) { bd = Math.abs(d); best = x; } } return best; };
const strip = (x) => { if (!x) return null; const o = Object.assign({}, x); delete o.t; return o; };
const num = (x) => (typeof x === 'number' && isFinite(x)) ? x : null;
const r2 = (x) => x == null ? null : Math.round(x * 100) / 100;
let reviews = []; try { reviews = JSON.parse(txt('Reviews Text') || '[]'); if (!Array.isArray(reviews)) reviews = []; } catch (e) { reviews = []; }
const reviewed = new Set(reviews.map(r => String(r.ts)));
const posts = featured.map(f => {
  const tr = near(tt, f.ts, -1 * H, 1 * H);                         // the Reel on TikTok (createTime is epoch, no timezone shift)
  const tc = near(tt.filter(x => x !== tr), f.ts, 1.5 * H, 6 * H);   // the carousel ~3 h later: PHOTO = photo carousel, VIDEO = slideshow
  const i = near(ig, f.ts, -3 * H, 3.5 * H), y = near(yt, f.ts, -3 * H, 3.5 * H), b = near(fb, f.ts, -3 * H, 3.5 * H);
  // key scores (higher = better, except skip): what the reviews and experiments compare
  const score = {
    igSkip: i ? num(i.skipRate) : null,
    igWatchPct: i && num(i.avgWatchSec) != null && i.lenSec ? r2(100 * i.avgWatchSec / i.lenSec) : null,
    igEngPer1k: i && i.views ? r2(1000 * ((i.likes || 0) + (i.comments || 0) + (i.shares || 0) + (i.saves || 0)) / i.views) : null,
    ttViews: tr ? num(tr.views) : null,
    ytViewSec: y ? num(y.avgViewSec) : null,
    fbWatchSec: b ? num(b.avgWatchSec) : null };
  return { ts: f.ts, episode: f.episode, hoursOld: Math.round((Date.now() - f.ts) / H), title: f.title, hook: f.hook,
    words: f.words, endQuestion: f.end_question, collabInvite: !!f.collab, designerAccounts: (f.creators || []).length,
    slot: f.slot || 'main', sendCta: !!f.send_cta, storyType: f.story_type || '', famousLabel: !!f.known, silentEdit: !!f.silent,
    instagram: strip(i), tiktok: strip(tr), youtube: strip(y), facebook: strip(b), score,
    tiktokCarousel: tc ? { variant: tc.type === 'PHOTO' ? 'photo' : 'slideshow', views: tc.views, likes: tc.likes, shares: tc.shares } : null,
    reviewed: reviewed.has(String(f.ts)) };
});
const judgedPosts = posts.filter(p => p.hoursOld >= JUDGE_H);
const med = (k) => { const v = judgedPosts.map(p => p.score[k]).filter(x => x != null).sort((a, b) => a - b); return v.length ? v[Math.floor(v.length / 2)] : null; };
const baseline = { posts: judgedPosts.length, igSkip: med('igSkip'), igWatchPct: med('igWatchPct'), igEngPer1k: med('igEngPer1k'),
  ttViews: med('ttViews'), ytViewSec: med('ytViewSec'), fbWatchSec: med('fbWatchSec') };
const toReview = judgedPosts.filter(p => !p.reviewed).slice(0, 8);
let strategy = {}; try { strategy = JSON.parse(txt('Strategy Text') || '{}'); } catch (e) { strategy = {}; }
let log = []; try { log = JSON.parse(txt('Log Text') || '[]'); if (!Array.isArray(log)) log = []; } catch (e) { log = []; }
// experiments: every applied change, with the average scores of the 4 judged posts before vs the judged posts after it
const avg = (ps, k) => { const v = ps.map(p => p.score[k]).filter(x => x != null); return v.length ? r2(v.reduce((a, b) => a + b, 0) / v.length) : null; };
const sum = (ps) => ({ n: ps.length, igSkip: avg(ps, 'igSkip'), igWatchPct: avg(ps, 'igWatchPct'), igEngPer1k: avg(ps, 'igEngPer1k'), ttViews: avg(ps, 'ttViews'), ytViewSec: avg(ps, 'ytViewSec') });
const experiments = [];
for (const e of log.slice(-20)) for (const c of (e.changes || [])) {
  const at = Date.parse(e.at); if (!at) continue;
  experiments.push({ knob: c.knob, from: c.from, to: c.to, at: e.at, why: c.why,
    before: sum(judgedPosts.filter(p => p.ts < at).slice(-4)), after: sum(judgedPosts.filter(p => p.ts > at)) });
}
const lastChangeAt = experiments.length ? Date.parse(experiments[experiments.length - 1].at) : 0;
const postsSinceLastChange = judgedPosts.filter(p => p.ts > lastChangeAt).length;
return [{ json: { posts: posts.map(p => { const o = Object.assign({}, p); delete o.ts; return o; }), toReview, baseline, judged: judgedPosts.length,
  strategy, experiments: experiments.slice(-6), postsSinceLastChange, changeAllowed: !experiments.length || postsSinceLastChange >= 4,
  recentLog: log.slice(-4).map(e => ({ at: e.at, observations: e.observations, changes: e.changes, watching: e.watching })),
  recentReviews: reviews.slice(-12), reviewsAll: reviews,
  apiOk: { instagram: ig.length, tiktok: tt.length, youtube: yt.length, facebook: fb.length } } }];
"""

PROMPT = (
    "=You are the growth agent of 5HU, a fully automatic short-video account (TikTok, Instagram Reels, YouTube Shorts, Facebook Reels) "
    "that spots fashion's next big names first; the goal is followers in the fashion niche (designers, stylists, fashion lovers). "
    "Two videos a day are made and posted by a pipeline without any human. You run every morning. The owner wants every post examined "
    "and the channel to get a little better, step by step. Nobody reviews your work, so be careful and honest: small, evidence-based steps, "
    "keep what works, undo what made things worse.\n\n"
    "WHAT DRIVES GROWTH (in this order): 1) people not swiping away in the first 2-3 s (Instagram skipRate lower = better, igWatchPct = "
    "avg watch time as % of length, YouTube avgViewSec, TikTok views as a proxy for distribution), 2) shares and saves per view, "
    "3) comments (our videos end with a two-option question; Instagram/Facebook counts include our own first comment when we posted one), 4) follows/likes. collabInvite = the Reel invited the featured designer as an "
    "Instagram collaborator (only Nº012-13; tags are now off for good). Since 2026-11-27 there are 4 videos a day: slot main (08:20, 18:20) "
    "goes to all networks, slot extra (12:20, 23:20) only to TikTok, YouTube and Facebook (so no Instagram numbers). sendCta = A/B test on "
    "alternate episodes: the outro and caption ask viewers to send the video to a friend (aims at DM sends) - compare sendCta true vs false. storyType (since 2026-11-27): designer = a new name, piece = one new designer piece - compare them too; story_focus can steer the mix. famousLabel = the story was about a famous label (owner wants mostly niche). silentEdit (since 2026-11-28, every 2nd extra-slot video) = no AI voice, only words on screen + music - compare silent vs voiced on TikTok/YouTube/Facebook.\n\n"
    "TASK 1 - REVIEW each post in TO_REVIEW (it has 2+ days of numbers) against OUR BASELINE (median of our own judged posts): "
    "verdict better | average | worse, why (one sentence with the numbers that decide it), and lesson (one short, general, reusable rule "
    "that explains the result - about the story, hook, first image, length, question or designer - or empty if nothing can be learned). "
    "Compare with similar past posts in RECENT REVIEWS; don't invent causes the data can't support.\n"
    "TO_REVIEW:\n{{ JSON.stringify($json.toReview) }}\nOUR BASELINE:\n{{ JSON.stringify($json.baseline) }}\n"
    "RECENT REVIEWS (oldest first):\n{{ JSON.stringify($json.recentReviews) }}\n\n"
    "TASK 2 - PLAYBOOK: return the full updated list of at most 8 lessons (each max 140 characters, no episode numbers, written as an instruction 'do X' / 'avoid Y') that the story picker and scriptwriter "
    "follow. Keep lessons that keep holding, merge duplicates, drop or rewrite any that newer posts contradicted. A lesson needs support from "
    "at least 2 posts, or 1 post that was far from the baseline. Current playbook: {{ JSON.stringify($json.strategy.lessons || []) }}\n\n"
    "TASK 3 - AT MOST ONE CHANGE to the strategy, only if the evidence supports it. "
    "{{ $json.changeAllowed ? 'A change is allowed today.' : 'The last change has only ' + $json.postsSinceLastChange + ' judged posts after it (needs 4): make NO change today unless the last change clearly hurt (then revert it).' }} "
    "EXPERIMENTS (each past change with average scores of the 4 posts before vs the posts after; revert a change that made the key scores "
    "clearly worse once it has 4 posts after it):\n{{ JSON.stringify($json.experiments) }}\n"
    "CURRENT STRATEGY:\n{{ JSON.stringify($json.strategy) }}\n"
    "ALL OUR POSTS (last 21 days, newest last):\n{{ JSON.stringify($json.posts) }}\n"
    "Data rows from Metricool: {{ JSON.stringify($json.apiOk) }}\nYOUR LAST RUNS:\n{{ JSON.stringify($json.recentLog) }}\n\n"
    "WHAT YOU CAN CHANGE (nothing else exists for you):\n"
    "- story_focus: a short note (max 400 chars) for the story picker - which kinds of designer stories to prefer or avoid. The picker still "
    "only picks named new/independent designers.\n"
    "- hook_notes: a short note (max 400 chars) for the scriptwriter about openings, first images, pacing and the closing question.\n"
    "- caption_notes: a short note (max 300 chars) for the caption writer (style, length, which kind of question gets comments).\n"
    "- words_min / words_max: voiceover length in words (16-34; the video is ~0.45 s per word + 3.2 s outro).\n"
    "- carousel: true/false (the photo carousel 3 h after each Reel on Instagram/Facebook/TikTok).\n"
    "- tiktok_carousel: ab (keep alternating) | photo | slideshow | off. Only leave 'ab' when each variant has at least 4 judged posts and "
    "one is clearly better.\n\n"
    "RULES: everything in English, concrete and grounded in the numbers, no URLs, no @handles, never contradict the brand (named new "
    "designers only, no big houses, no celebrities, no links to other platforms). If the data is missing or broken, review nothing and change nothing.\n\n"
    "Output ONLY JSON: {\"reviews\":[{\"episode\":12,\"verdict\":\"better|average|worse\",\"why\":\"...\",\"lesson\":\"...\"}],"
    "\"lessons\":[\"...\"],\"observations\":[\"max 5 short facts with numbers\"],\"changes\":[{\"knob\":\"...\",\"to\":...,\"why\":\"...\"}],"
    "\"watching\":\"what you'll check next\"}"
)

VALIDATE_JS = r"""
const c = $('Compile').first().json;
const cur = Object.assign({ story_focus: '', hook_notes: '', caption_notes: '', words_min: 22, words_max: 28, carousel: true, tiktok_carousel: 'ab', lessons: [] }, c.strategy || {});
let out = null;
try { const raw = $input.first().json.content[0].text; out = JSON.parse(raw.slice(raw.indexOf('{'), raw.lastIndexOf('}') + 1)); } catch (e) { out = null; }
const ok = !!out;
if (!out) out = { observations: ['agent output unreadable - nothing reviewed or changed'], changes: [], watching: '' };
const clean = (x, n) => String(x || '').replace(/https?:\/\/\S+/g, '').replace(/@\w[\w.]*/g, '').replace(/\s+/g, ' ').trim().slice(0, n);
const next = Object.assign({}, cur); const applied = [];
// 1) reviews: only for posts we asked about
const byEp = {}; for (const p of (c.toReview || [])) byEp[String(p.episode)] = p;
const newReviews = [];
for (const r of (Array.isArray(out.reviews) ? out.reviews : [])) {
  const p = byEp[String(r.episode)]; if (!p) continue; delete byEp[String(r.episode)];
  const v = ['better', 'average', 'worse'].includes(r.verdict) ? r.verdict : 'average';
  newReviews.push({ ts: p.ts, episode: p.episode, title: clean(p.title, 80), at: new Date().toISOString(), verdict: v,
    why: clean(r.why, 300), lesson: clean(r.lesson, 160), score: p.score });
}
// 2) playbook
// lessons go into the prompts: no episode refs, whole clauses only (never cut mid-word)
const lessonClean = (x) => { let s = clean(x, 600).replace(/\s*\([^)]*\b(?:ep|episode|N\u00ba)\s?\d[^)]*\)/gi, '').replace(/\s*\([^)]*$/, '').trim();
  if (s.length > 170) { const cut = s.slice(0, 170); const i = Math.max(cut.lastIndexOf('. '), cut.lastIndexOf('; '), cut.lastIndexOf(', ')); s = i > 60 ? cut.slice(0, i) + '.' : cut.slice(0, cut.lastIndexOf(' ')) + '…'; }
  return s; };
if (ok && Array.isArray(out.lessons)) next.lessons = out.lessons.map(lessonClean).filter(Boolean).slice(0, 8);
// 3) at most one change; a knob changes again only after 4 judged posts, except an explicit revert to an earlier value
const isRevert = (k, v) => (c.experiments || []).some(e => e.knob === k && JSON.stringify(e.from) === JSON.stringify(v));
for (const ch of (Array.isArray(out.changes) ? out.changes : []).slice(0, 1)) {
  const k = String(ch.knob || ''); let v = ch.to;
  if (k === 'story_focus') v = clean(v, 400);
  else if (k === 'hook_notes') v = clean(v, 400);
  else if (k === 'caption_notes') v = clean(v, 300);
  else if (k === 'words_min') v = Math.min(30, Math.max(16, parseInt(v, 10) || cur.words_min));
  else if (k === 'words_max') v = Math.min(34, Math.max(20, parseInt(v, 10) || cur.words_max));
  else if (k === 'carousel') v = v === true || v === 'true';
  else if (k === 'tiktok_carousel') { v = String(v); if (!['ab', 'photo', 'slideshow', 'off'].includes(v)) continue; }
  else continue;   // unknown knob: ignored
  if (!c.changeAllowed && !isRevert(k, v)) continue;
  if (JSON.stringify(next[k]) === JSON.stringify(v)) continue;
  applied.push({ knob: k, from: next[k], to: v, why: clean(ch.why, 300) });
  next[k] = v;
}
if (next.words_max < next.words_min + 4) next.words_max = Math.min(34, next.words_min + 4);
for (const a of applied) a.to = next[a.knob];   // log what was really applied (after the min/max clamp)
next.updated = new Date().toISOString();
const entry = { at: next.updated, judged: c.judged, data: c.apiOk, baseline: c.baseline,
  reviewed: newReviews.map(r => 'Nº' + r.episode + ' ' + r.verdict), lessons: next.lessons.length,
  observations: (out.observations || []).slice(0, 5).map(o => clean(o, 300)), changes: applied, watching: clean(out.watching, 300) };
let log = []; try { log = JSON.parse($('Log Text').first().json.data || '[]'); if (!Array.isArray(log)) log = []; } catch (e) { log = []; }
log = log.concat([entry]).slice(-90);
const reviews = (c.reviewsAll || []).concat(newReviews).slice(-300);
const bin = async (o, n) => this.helpers.prepareBinaryData(Buffer.from(JSON.stringify(o, null, 1), 'utf8'), n, 'application/json');
return [{ json: { file: '/data/shared/5hu_strategy.json', applied }, binary: { data: await bin(next, '5hu_strategy.json') } },
        { json: { file: '/data/shared/5hu_growth_log.json' }, binary: { data: await bin(log, '5hu_growth_log.json') } },
        { json: { file: '/data/shared/5hu_reviews.json' }, binary: { data: await bin(reviews, '5hu_reviews.json') } }];
"""

nodes = [
    node("Every morning", "n8n-nodes-base.scheduleTrigger", 1.2,
         {"rule": {"interval": [{"field": "cronExpression", "expression": "40 6 * * *"}]}}, [0, 0]),
    metricool("IG Reels", "reels/instagram", 220),
    metricool("TikTok", "posts/tiktok", 440),
    metricool("YouTube", "posts/youtube", 660),
    metricool("FB Reels", "reels/facebook", 880),
]
nodes += read_text("Featured", "/data/shared/5hu_featured.jsonl", 1100)
nodes += read_text("Strategy", "/data/shared/5hu_strategy.json", 1500)
nodes += read_text("Log", "/data/shared/5hu_growth_log.json", 1900)
nodes += read_text("Reviews", "/data/shared/5hu_reviews.json", 2300)
nodes += [
    node("Compile", "n8n-nodes-base.code", 2, {"jsCode": COMPILE_JS}, [2700, 0]),
    node("Decide", "@n8n/n8n-nodes-langchain.anthropic", 1,
         {"modelId": {"__rl": True, "value": "claude-sonnet-4-6", "mode": "list", "cachedResultName": "claude-sonnet-4-6"},
          "messages": {"values": [{"content": PROMPT}]}, "options": {"maxTokens": 4000}}, [2920, 0],
         credentials=ANTH_CRED, onError="continueRegularOutput", alwaysOutputData=True, retryOnFail=True, maxTries=2, waitBetweenTries=5000),
    node("Validate", "n8n-nodes-base.code", 2, {"jsCode": VALIDATE_JS}, [3140, 0]),
    node("Write Files", "n8n-nodes-base.readWriteFile", 1,
         {"operation": "write", "fileName": "={{ $json.file }}", "dataPropertyName": "data", "options": {}}, [3360, 0]),
]
names = [n["name"] for n in nodes]
wf = {"id": WF_ID, "name": "5HU Growth Agent", "nodes": nodes,
      "connections": {a: {"main": [[{"node": b, "type": "main", "index": 0}]]} for a, b in zip(names, names[1:])},
      "settings": {"executionOrder": "v1", "timezone": "Europe/Vilnius"}, "active": False, "pinData": {}}
# manual run from the VPS: n8n execute --id=FiveHuGrowth0001 (needs an Execute Workflow Trigger; same chain as the schedule)
wf["nodes"].append(node("Run Now (CLI)", "n8n-nodes-base.executeWorkflowTrigger", 1.1, {"inputSource": "passthrough"}, [0, 220]))
wf["connections"]["Run Now (CLI)"] = {"main": [[{"node": names[1], "type": "main", "index": 0}]]}
json.dump(wf, open(OUT, "w"), ensure_ascii=False, indent=1)
print("OK ->", OUT)
