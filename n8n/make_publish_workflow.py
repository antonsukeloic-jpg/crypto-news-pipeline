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
    "5hu": {"blogId": "8237757", "networks": ["tiktok", "instagram", "youtube", "facebook"], "carousel": ["instagram", "tiktok", "facebook"],  # TikTok alternates: photo carousel + TikTok music / slideshow video + our music
            "style": "5HU - fashion's next big names first. Cool, effortless, insider. Lowercase-friendly. Hashtags: niche fashion + designer/label name + city, e.g. #newdesigners #fashiontok #copenhagenfashion (vary them)."},
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
// kind "carousel": photo slides (Instagram carousel, TikTok photo post, Facebook multi-photo), scheduled delayMin later
const kind = b.kind === 'carousel' ? 'carousel' : 'video';
const slideshowUrl = kind === 'carousel' && /^https:\/\/n8n\.visualforma\.cloud\/m\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+\.mp4$/.test(String(b.slideshowUrl || '')) ? b.slideshowUrl : '';
const pool = kind === 'carousel' ? (ch.carousel || []) : ch.networks;
const nets = only ? pool.filter(n => only.includes(n)) : pool;
if (!nets.length) return [{ json: { skip: true, reason: 'no matching networks for ' + b.channel + ' ' + kind } }];
const key = (kind === 'carousel' ? String(b.job) + '#carousel' : String(b.job)) + (only ? '@' + nets.join(',') : '');
const MEDIA = /^https:\/\/n8n\.visualforma\.cloud\/m\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+\.(mp4|jpg)$/;
const images = kind === 'carousel' ? (Array.isArray(b.images) ? b.images : []).map(String).filter(u => MEDIA.test(u) && u.endsWith('.jpg')).slice(0, 10) : [];
if (kind === 'carousel' && images.length < 3) return [{ json: { skip: true, reason: 'carousel needs 3+ slide images' } }];
if (kind === 'video' && !/^https:\/\/n8n\.visualforma\.cloud\/m\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+\.mp4$/.test(String(b.videoUrl || ''))) return [{ json: { skip: true, reason: 'bad videoUrl' } }];
const delayMin = Math.min(Math.max(parseInt(b.delayMin, 10) || 3, 3), 24 * 60);
const sd = $getWorkflowStaticData('global');
sd.published = sd.published || [];
if (sd.published.includes(key)) return [{ json: { skip: true, reason: 'already published ' + key } }];
sd.published = [key].concat(sd.published).slice(0, 300);
// TikTok carousel A/B: a swipeable photo carousel with music TikTok picks (the API can't choose a sound) vs the
// slideshow video over our own track. ABBA order so both versions get morning and evening slots; compare saves/shares.
let ttVariant = '';
if (kind === 'carousel' && nets.includes('tiktok')) {
  const n = sd.ttCarouselN || 0; sd.ttCarouselN = n + 1;
  ttVariant = slideshowUrl && (n % 4 === 1 || n % 4 === 2) ? 'slideshow' : 'photo';
}
return [{ json: { skip: false, kind, images, slideshowUrl, ttVariant, delayMin, job: b.job, channel: b.channel, blogId: ch.blogId, networks: nets, style: ch.style,
  slidesText: kind === 'carousel' ? String(b.slidesText || '').slice(0, 2000) : '',
  videoUrl: kind === 'video' ? b.videoUrl : '', voiceover: String(b.voiceover || '').slice(0, 1500), title: String(b.title || '').slice(0, 200),
  hashtags: (b.hashtags || []).slice(0, 10),
  thumbnailUrl: /^https:\/\/n8n\.visualforma\.cloud\/m\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+\.jpg$/.test(String(b.thumbnailUrl || '')) ? b.thumbnailUrl : '',
  creators: (Array.isArray(b.creators) ? b.creators : []).slice(0, 2).map(c => ({ name: String(c.name || '').slice(0, 60),
    instagram: /^[A-Za-z0-9._]{2,30}$/.test(c.instagram || '') ? c.instagram : '', tiktok: /^[A-Za-z0-9._]{2,30}$/.test(c.tiktok || '') ? c.tiktok : '',
    website: /^https:\/\/[a-z0-9.-]+\.[a-z]{2,}$/i.test(c.website || '') ? c.website : '' })).filter(c => c.name),
  credits: (Array.isArray(b.credits) ? b.credits : []).slice(0, 4).map(x => String(x).slice(0, 40)) } }];
""".replace("__CHANNELS__", json.dumps({k: {"blogId": v["blogId"], "networks": v["networks"], "carousel": v.get("carousel", []), "style": v["style"]}
                                      for k, v in CHANNELS.items()}))

CAPTION_PROMPT = (
    "=You write social media captions for {{ $json.kind === 'carousel' ? 'a swipeable photo carousel (Instagram carousel, Facebook multi-photo post, TikTok photo carousel or a short slideshow video of the same slides); it goes deeper than our earlier video on the same story, so the hook must work on its own and invite people to swipe and save' : 'a short vertical video' }}. Output ONLY valid JSON, no markdown.\n\n"
    "CHANNEL STYLE: {{ $json.style }}\n"
    "VIDEO VOICEOVER: {{ $json.voiceover }}\n"
    "{{ $json.kind === 'carousel' ? 'CAROUSEL SLIDES (this is what the post shows): ' + $json.slidesText + '\\n' : '' }}"
    "STORY TITLE: {{ $json.title }}\n"
    "SUGGESTED HASHTAGS: {{ ($json.hashtags || []).join(' ') }}\n"
    "CREATORS (verified accounts; empty = none found): {{ JSON.stringify($json.creators || []) }}\n\n"
    "RULES\n- Same language as the voiceover. Native to each platform, never copy-paste the same text.\n"
    "- Hook in the first line (it is all people see). No clickbait the video does not deliver. Facts only from the voiceover/title.\n"
    "- SEARCH FIRST (2026 best practice: platforms are search engines, hashtags only categorize): put the main searchable keyword (designer / label / trend / coin name) in the first ~80 characters of every text.\n"
    "- KEEP PEOPLE ON THE PLATFORM: never mention, tag or link any other social network or app (no TikTok / Instagram / Reels / YouTube / Shorts / Facebook / link-in-bio / follow us elsewhere). Each text is native to its own platform only.\n"
    "- Hashtags = search keywords: specific niche/mid-size tags over giant generic ones; NEVER #fyp #viral #explore #foryou; vary them per video.\n"
    "- tiktok.text: 1-2 short lines + 3-5 hashtags used as keywords (1 broad category like #fashiontok + niche/designer tags), max 150 characters total.\n"
    "- instagram.text: hook line, 1-2 sentences of context, a question to drive comments, then 4-5 hashtags (Instagram hard cap is 5, never more): 1 broad + 2 niche + 2 specific (designer/label/event/city).\n"
    "- youtube.title: max 90 characters, include #Shorts at the end; youtube.description: keyword-rich 1-2 sentences + 3 hashtags (first 3 show above the title); youtube.tags: 5-8 plain keywords.\n"
    "- facebook.text: 1-3 sentences, conversational, 1-2 hashtags.\n"
    "- CREDIT THE CREATOR FIRST: in instagram.text tag the designer/label once with their exact @instagram handle from CREATORS; in tiktok.text use their exact @tiktok handle; "
    "in youtube.description and facebook.text you may add their website URL from CREATORS (never a social-media link). Use ONLY handles/URLs given in CREATORS - never invent or guess one; if none is given, write the plain name.\n\n"
    'SCHEMA {"tiktok":{"text":"..."},"instagram":{"text":"..."},"youtube":{"title":"...","description":"...","tags":["..."]},"facebook":{"text":"..."}}'
)

BUILD = r"""
const p = $('Prepare').first().json;
let cap = {};
try { const raw = $input.first().json.content[0].text; cap = JSON.parse(raw.slice(raw.indexOf('{'), raw.lastIndexOf('}') + 1)); } catch (e) {}
const fallback = (p.title || p.voiceover.split(/[.!?]/)[0] || '').slice(0, 120) + ' ' + (p.hashtags || []).slice(0, 4).join(' ');
const when = new Date(Date.now() + (p.delayMin || 3) * 60 * 1000).toLocaleString('sv-SE', { timeZone: 'Europe/Vilnius' }).replace(' ', 'T').slice(0, 19);
const base = { publicationDate: { dateTime: when, timezone: 'Europe/Vilnius' }, autoPublish: true, draft: false, descendants: [],
  firstCommentText: '', hasNotReadNotes: false, media: p.kind === 'carousel' ? p.images : [p.videoUrl], mediaAltText: [], shortener: false, smartLinkData: { ids: [] } };
const cr = p.creators || [];
const credits = (p.credits || []).length ? '\n📸 ' + p.credits.join(' · ') : '';
const igComment = cr.some(c => c.instagram) ? '📍 ' + cr.filter(c => c.instagram).map(c => c.name + ' @' + c.instagram).join(' · ') + credits : (credits ? credits.trim() : '');
const fbComment = cr.some(c => c.website) ? '📍 ' + cr.filter(c => c.website).map(c => c.name + ' — ' + c.website).join(' · ') + credits : (credits ? credits.trim() : '');
const out = [];
for (const net of p.networks) {
  const post = Object.assign({}, base, { providers: [{ network: net }] });
  if (p.kind === 'carousel') {
    if (net === 'instagram') { post.text = (cap.instagram && cap.instagram.text) || fallback; post.instagramData = { type: 'POST', isAiGenerated: false }; post.firstCommentText = igComment; }
    if (net === 'facebook') { post.text = (cap.facebook && cap.facebook.text) || fallback; post.facebookData = { type: 'POST' }; post.firstCommentText = fbComment; }
    let label = net;
    if (net === 'tiktok') {
      const t = (cap.tiktok && cap.tiktok.text) || fallback; post.text = t;
      const tt = { privacyOption: 'PUBLIC_TO_EVERYONE', disableComment: false, disableDuet: false, disableStitch: false,
        commercialContentThirdParty: false, commercialContentOwnBrand: false };
      if (p.ttVariant === 'slideshow') {   // the slides as a video over our own light techno
        post.media = [p.slideshowUrl]; post.tiktokData = Object.assign(tt, { isAigc: false }); label = 'tiktok (slideshow, our music)';
      } else {                             // swipeable photo carousel; TikTok adds a recommended track (can be swapped in the app)
        post.tiktokData = Object.assign(tt, { autoAddMusic: true, photoCoverIndex: 0,
          title: t.split('\n')[0].replace(/#\S+/g, '').trim().slice(0, 90) }); label = 'tiktok (photo carousel, TikTok music)';
      } }
    if (post.text) out.push({ json: { network: net, label, blogId: p.blogId, body: post } });
    continue;
  }
  if (net === 'tiktok') { post.text = (cap.tiktok && cap.tiktok.text) || fallback;
    post.tiktokData = { privacyOption: 'PUBLIC_TO_EVERYONE', disableComment: false, disableDuet: false, disableStitch: false,
      commercialContentThirdParty: false, commercialContentOwnBrand: false, autoAddMusic: false, isAigc: true, title: '' }; }
  if (net === 'instagram') { post.text = (cap.instagram && cap.instagram.text) || fallback;
    post.instagramData = { type: 'REEL', showReelOnFeed: true, isAiGenerated: true };
    if (p.thumbnailUrl) post.videoThumbnailUrl = p.thumbnailUrl;
    post.firstCommentText = igComment; }
  if (net === 'youtube') { const y = cap.youtube || {}; post.text = y.description || fallback;
    post.youtubeData = { title: (y.title || fallback).slice(0, 100), type: 'short', privacy: 'public', tags: (y.tags || []).slice(0, 10),
      madeForKids: false, isAiGeneratedContent: true }; }
  if (net === 'facebook') { post.text = (cap.facebook && cap.facebook.text) || fallback; post.facebookData = { type: 'REEL' };
    if (p.thumbnailUrl) post.videoThumbnailUrl = p.thumbnailUrl;
    post.firstCommentText = fbComment; }
  out.push({ json: { network: net, blogId: p.blogId, body: post } });
}
return out;
"""

REPORT = r"""
const items = $input.all();
const posts = items.map((it, i) => {
  const r = it.json || {}; const bp = $('Build Posts').all()[i]; const net = bp ? (bp.json.label || bp.json.network) : '?';
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
