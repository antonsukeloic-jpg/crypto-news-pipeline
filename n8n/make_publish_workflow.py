#!/usr/bin/env python3
"""Social Publish workflow (one for every channel): the render watcher POSTs a finished video here, Claude writes a
caption per platform, and the post goes to that brand in Metricool (publishes ~3 min later, visible in its calendar).

    python3 make_publish_workflow.py <metricool_credential_id> <out.json>

Webhook: POST https://n8n.visualforma.cloud/webhook/social-publish
  {"job": "5hu_job_123.json", "channel": "5hu", "videoUrl": "https://n8n.visualforma.cloud/m/<rand>/x.mp4",
   "voiceover": "...", "title": "...", "hashtags": [...], "only": ["instagram"] (optional: post to just these networks)}
Responds with {"ok": bool, "posts": [{network, ok, plannerUrl|error}]} so the watcher can report to Telegram.

Which networks each channel posts to is CHANNELS below (add a network only after it is connected in Metricool).
"""
import json, sys, uuid

cred_id, dst = sys.argv[1], sys.argv[2]
USER_ID = "6373812"
CHANNELS = {
    # channel: Metricool blogId, networks to post to, caption style
    "5hu": {"blogId": "8237757", "networks": ["tiktok", "instagram"],
            "style": "5HU - fashion's next big names first. Cool, effortless, insider. Lowercase-friendly. Hashtags: niche fashion + designer/label name + city, e.g. #emergingdesigners #fashiontok #copenhagenfashion."},
    "crypto": {"blogId": "", "networks": [],
               "style": "Fast crypto news. Lead with the number or the stakes. Always end with 'Not financial advice.' Hashtags: #crypto #bitcoin + coin/company names."},
    "vikops": {"blogId": "8107269", "networks": [],
               "style": "Lithuanian. Natural limestone floor tiles with fossils, Vilnius (vikops.lt, +370 664 88588). Warm, crafted, premium. Lithuanian hashtags."},
}

PREP = r"""
const CH = __CHANNELS__;
const b = $input.first().json.body || $input.first().json;
const ch = CH[String(b.channel || '')];
if (!ch || !ch.blogId || !(ch.networks || []).length) return [{ json: { skip: true, reason: 'channel not set up for publishing: ' + b.channel } }];
// optional "only": ["instagram"] = post an already-published video to just these (newly added) networks
const only = Array.isArray(b.only) ? b.only.map(String) : null;
const nets = only ? ch.networks.filter(n => only.includes(n)) : ch.networks;
if (!nets.length) return [{ json: { skip: true, reason: 'no matching networks for ' + b.channel } }];
const key = only ? String(b.job) + '@' + nets.join(',') : b.job;
if (!/^https:\/\/n8n\.visualforma\.cloud\/m\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+\.mp4$/.test(String(b.videoUrl || ''))) return [{ json: { skip: true, reason: 'bad videoUrl' } }];
const sd = $getWorkflowStaticData('global');
sd.published = sd.published || [];
if (sd.published.includes(key)) return [{ json: { skip: true, reason: 'already published ' + key } }];
sd.published = [key].concat(sd.published).slice(0, 300);
return [{ json: { skip: false, job: b.job, channel: b.channel, blogId: ch.blogId, networks: nets, style: ch.style,
  videoUrl: b.videoUrl, voiceover: String(b.voiceover || '').slice(0, 1500), title: String(b.title || '').slice(0, 200),
  hashtags: (b.hashtags || []).slice(0, 10) } }];
""".replace("__CHANNELS__", json.dumps({k: {"blogId": v["blogId"], "networks": v["networks"], "style": v["style"]} for k, v in CHANNELS.items()}))

CAPTION_PROMPT = (
    "=You write social media captions for a short vertical video. Output ONLY valid JSON, no markdown.\n\n"
    "CHANNEL STYLE: {{ $json.style }}\n"
    "VIDEO VOICEOVER: {{ $json.voiceover }}\n"
    "STORY TITLE: {{ $json.title }}\n"
    "SUGGESTED HASHTAGS: {{ ($json.hashtags || []).join(' ') }}\n\n"
    "RULES\n- Same language as the voiceover. Native to each platform, never copy-paste the same text.\n"
    "- Hook in the first line (it is all people see). No clickbait the video does not deliver. Facts only from the voiceover/title.\n"
    "- tiktok.text: 1-2 short lines + 4-5 hashtags (mix 1-2 broad like #fashiontok with niche/designer tags), max 150 characters total.\n"
    "- instagram.text: hook line, 1-2 sentences of context, a question to drive comments, then EXACTLY 5 hashtags (Instagram allows max 5): 1 broad + 2 niche + 2 specific (designer/label/event/city).\n"
    "- youtube.title: max 90 characters, include #Shorts at the end; youtube.description: 1-2 sentences + 3 hashtags; youtube.tags: 5-8 plain keywords.\n"
    "- facebook.text: 1-3 sentences, conversational, max 2 hashtags.\n\n"
    'SCHEMA {"tiktok":{"text":"..."},"instagram":{"text":"..."},"youtube":{"title":"...","description":"...","tags":["..."]},"facebook":{"text":"..."}}'
)

BUILD = r"""
const p = $('Prepare').first().json;
let cap = {};
try { const raw = $input.first().json.content[0].text; cap = JSON.parse(raw.slice(raw.indexOf('{'), raw.lastIndexOf('}') + 1)); } catch (e) {}
const fallback = (p.title || p.voiceover.split(/[.!?]/)[0] || '').slice(0, 120) + ' ' + (p.hashtags || []).slice(0, 4).join(' ');
const when = new Date(Date.now() + 3 * 60 * 1000).toLocaleString('sv-SE', { timeZone: 'Europe/Vilnius' }).replace(' ', 'T').slice(0, 19);
const base = { publicationDate: { dateTime: when, timezone: 'Europe/Vilnius' }, autoPublish: true, draft: false, descendants: [],
  firstCommentText: '', hasNotReadNotes: false, media: [p.videoUrl], mediaAltText: [], shortener: false, smartLinkData: { ids: [] } };
const out = [];
for (const net of p.networks) {
  const post = Object.assign({}, base, { providers: [{ network: net }] });
  if (net === 'tiktok') { post.text = (cap.tiktok && cap.tiktok.text) || fallback;
    post.tiktokData = { privacyOption: 'PUBLIC_TO_EVERYONE', disableComment: false, disableDuet: false, disableStitch: false,
      commercialContentThirdParty: false, commercialContentOwnBrand: false, autoAddMusic: false, isAigc: true, title: '' }; }
  if (net === 'instagram') { post.text = (cap.instagram && cap.instagram.text) || fallback;
    post.instagramData = { type: 'REEL', showReelOnFeed: true, isAiGenerated: true }; }
  if (net === 'youtube') { const y = cap.youtube || {}; post.text = y.description || fallback;
    post.youtubeData = { title: (y.title || fallback).slice(0, 100), type: 'short', privacy: 'public', tags: (y.tags || []).slice(0, 10),
      madeForKids: false, isAiGeneratedContent: true }; }
  if (net === 'facebook') { post.text = (cap.facebook && cap.facebook.text) || fallback; post.facebookData = { type: 'REEL' }; }
  out.push({ json: { network: net, blogId: p.blogId, body: post } });
}
return out;
"""

REPORT = r"""
const items = $input.all();
const posts = items.map((it, i) => {
  const r = it.json || {}; const net = $('Build Posts').all()[i] ? $('Build Posts').all()[i].json.network : '?';
  const d = r.data || r; const ok = !r.error && !(r.statusCode && r.statusCode >= 400);
  return { network: net, ok, plannerUrl: d.plannerUrl || (d.data && d.data.plannerUrl) || '', id: d.id || (d.data && d.data.id) || '',
           error: ok ? '' : JSON.stringify(r.error || r.body || r).slice(0, 300) };
});
return [{ json: { ok: posts.every(p => p.ok), posts } }];
"""


def node(name, ntype, ver, params, pos, **extra):
    n = {"parameters": params, "type": ntype, "typeVersion": ver, "position": pos, "id": str(uuid.uuid4()), "name": name}
    n.update(extra)
    return n


nodes = [
    node("Publish Webhook", "n8n-nodes-base.webhook", 2,
         {"httpMethod": "POST", "path": "social-publish", "responseMode": "responseNode", "options": {}}, [0, 0],
         webhookId=str(uuid.uuid4())),
    node("Prepare", "n8n-nodes-base.code", 2, {"jsCode": PREP}, [220, 0]),
    node("Skip?", "n8n-nodes-base.if", 2.2,
         {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                         "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.skip }}", "rightValue": "",
                                         "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}},
         [440, 0]),
    node("Respond Skipped", "n8n-nodes-base.respondToWebhook", 1.1,
         {"respondWith": "json", "responseBody": "={{ JSON.stringify({ ok: false, skipped: true, reason: $json.reason }) }}", "options": {}}, [660, -160]),
    node("Write Captions", "@n8n/n8n-nodes-langchain.anthropic", 1,
         {"modelId": {"__rl": True, "value": "claude-sonnet-4-6", "mode": "list", "cachedResultName": "claude-sonnet-4-6"},
          "messages": {"values": [{"content": CAPTION_PROMPT}]}, "options": {"maxTokens": 1200}},
         [660, 60], credentials={"anthropicApi": {"id": "3pYNdkLM3jdNYjyM", "name": "Anthropic account"}},
         retryOnFail=True, maxTries=3, waitBetweenTries=3000, onError="continueRegularOutput"),
    node("Build Posts", "n8n-nodes-base.code", 2, {"jsCode": BUILD}, [880, 60]),
    node("Metricool Post", "n8n-nodes-base.httpRequest", 4.2,
         {"method": "POST", "url": f"=https://app.metricool.com/api/v2/scheduler/posts?blogId={{{{ $json.blogId }}}}&userId={USER_ID}",
          "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
          "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.body) }}",
          "options": {"timeout": 60000, "response": {"response": {"neverError": True}}}},
         [1100, 60], credentials={"httpHeaderAuth": {"id": cred_id, "name": "Metricool"}},
         retryOnFail=True, maxTries=2, waitBetweenTries=5000, onError="continueRegularOutput"),
    node("Report", "n8n-nodes-base.code", 2, {"jsCode": REPORT}, [1320, 60]),
    node("Respond", "n8n-nodes-base.respondToWebhook", 1.1,
         {"respondWith": "json", "responseBody": "={{ JSON.stringify($json) }}", "options": {}}, [1540, 60]),
]
conn = {
    "Publish Webhook": {"main": [[{"node": "Prepare", "type": "main", "index": 0}]]},
    "Prepare": {"main": [[{"node": "Skip?", "type": "main", "index": 0}]]},
    "Skip?": {"main": [[{"node": "Respond Skipped", "type": "main", "index": 0}], [{"node": "Write Captions", "type": "main", "index": 0}]]},
    "Write Captions": {"main": [[{"node": "Build Posts", "type": "main", "index": 0}]]},
    "Build Posts": {"main": [[{"node": "Metricool Post", "type": "main", "index": 0}]]},
    "Metricool Post": {"main": [[{"node": "Report", "type": "main", "index": 0}]]},
    "Report": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
}
w = {"id": "SocialPublish001", "name": "Social Publish (Metricool)", "nodes": nodes, "connections": conn,
     "settings": {"executionOrder": "v1"}, "active": False}
json.dump(w, open(dst, "w"), indent=1)
print("OK ->", dst)
