#!/usr/bin/env python3
"""Build the "5HU Fashion News" workflow (15 s English trending-fashion news) from the LT workflow.

Input : the LT workflow JSON (output of make_lt_workflow.py) - reuses its robust parsing
        (quote repair, selection fallback), dead-feed tolerance, caption checks and channel field.
Output: a SEPARATE workflow (own id, node ids, webhook ids), English, fashion feeds,
        "channel": "5hu", files prefixed 5hu_. Started by /run 5hu via the crypto router.

usage: make_5hu_workflow.py <lt.json> <out_5hu.json>
"""
import copy, json, sys, uuid

SRC = sys.argv[1] if len(sys.argv) > 1 else "n8n/workflow_lt.json"
DST = sys.argv[2] if len(sys.argv) > 2 else "n8n/workflow_5hu.json"
FIVEHU_WORKFLOW_ID = "FiveHuFashion001"     # fixed 16-char id
VOICE_ID = "FGY2WhTYpPnrIDTdsKH5"           # ElevenLabs premade "Laura" - young, upbeat, social-media voice (English)
MODEL = "eleven_v4"

# tested from the VPS 2026-11-15 (all fresh): luxury / industry / streetwear
FEEDS = [
    ("Vogue", "https://www.vogue.com/feed/rss"),
    ("Fashionista", "https://fashionista.com/.rss/excerpt/"),
    ("Hypebeast", "https://hypebeast.com/feed"),
]

src = json.load(open(SRC))
w = copy.deepcopy(src)
w["name"] = "5HU Fashion News"
w["id"] = FIVEHU_WORKFLOW_ID
for k in ("versionId", "staticData", "pinData", "tags", "meta"):
    w.pop(k, None)
for n in w["nodes"]:
    n["id"] = str(uuid.uuid4())
    if "webhookId" in n:
        n["webhookId"] = str(uuid.uuid4())
by_name = {n["name"]: n for n in w["nodes"]}
by_name["Every Hour"]["disabled"] = True

# ---- feeds
for (name, url), node in zip(FEEDS, ("RSS A", "RSS B", "RSS C")):
    by_name[node]["parameters"]["url"] = url
cf = by_name["Combine Feeds"]["parameters"]
old = "const srcs=[['LRT','RSS A'],['15min','RSS B'],['Lrytas','RSS C']];"
assert old in cf["jsCode"]
cf["jsCode"] = cf["jsCode"].replace(old, "const srcs=" + json.dumps([[n, f"RSS {c}"] for (n, _), c in zip(FEEDS, "ABC")]) + ";")

# ---- "all new": skip stories already used (workflow static data, kept by n8n for
#      scheduled/production runs) and prefer stories from the last 48 h
old = "all=all.filter(x=>x.title&&x.link);"
assert old in cf["jsCode"]
cf["jsCode"] = cf["jsCode"].replace(old, old + "\n"
    "const _st=$getWorkflowStaticData('global'); const _seen=new Set(_st.seen5hu||[]);\n"
    "all=all.filter(x=>!_seen.has(x.link));\n"
    "const _fresh=all.filter(x=>Date.now()-new Date(x.date||0).getTime()<48*3600e3); if(_fresh.length>=3) all=_fresh;\n"
    "if(!all.length) throw new Error('5HU: no new fashion stories since the last video');")
ps = by_name["Parse Selection"]["parameters"]
old = "return [{ json: { link: sel.link,"
assert ps["jsCode"].count(old) == 1
ps["jsCode"] = ps["jsCode"].replace(old,
    "const _st = $getWorkflowStaticData('global'); _st.seen5hu = [sel.link].concat(_st.seen5hu || []).slice(0, 500);\n" + old)

# ---- editor
by_name["Select Story"]["parameters"]["messages"]["values"][0]["content"] = (
    "=You are the editor of 5HU, a trending FASHION news channel on TikTok/Reels for a young, style-obsessed global audience. "
    "Choose the SINGLE best story from the candidates for a 15-second vertical video.\n\n"
    "PICK what people will talk about and share today: viral celebrity looks and red-carpet moments, runway shows and standout collections, "
    "designer moves (new creative directors, exits, debuts), big collabs and drops, sneaker and streetwear releases, brand deals, "
    "trend shifts with a clear name, and fashion-business news with a striking number.\n"
    "AVOID: deaths and obituaries, body-shaming or weight talk, anything about minors' bodies, crime and lawsuits with victims, "
    "pure shopping lists / sales roundups / affiliate deals, horoscopes, sponsored posts, long essays without news, "
    "and anything that can't be told accurately in 15 seconds.\n\n"
    "Output ONLY valid JSON, no markdown, no code fences. Inside JSON strings use typographic quotes “ ” instead of the ASCII double quote.\n"
    "{\"link\":\"<exact LINK of the chosen story>\",\"title\":\"<its title>\",\"reason\":\"<max 12 words>\"}\n\n"
    "CANDIDATES\n{{ $json.candidatesText }}")

# ---- script writer (same schema; English; entities from en.wikipedia)
msg = by_name["Message a model"]["parameters"]["messages"]["values"][0]
article_expr = msg["content"].split("ARTICLE\n", 1)[1]
msg["content"] = (
    "=You are the scriptwriter for 5HU, a trending fashion news channel (TikTok/Reels). Turn ONE fashion news article into a 15-second vertical video plan.\n\n"
    "Output ONLY valid JSON matching the SCHEMA below. No markdown, no code fences, no text before or after the JSON. "
    "Inside JSON strings use typographic quotes “ ” instead of the ASCII double quote.\n\n"
    "VOICE\n"
    "- English, spoken, fast and fun: a stylish insider spilling the news to a friend - confident, a little playful, never cringe. "
    "Short punchy sentences. Fashion vocabulary used correctly (collection, capsule, creative director, drop, silhouette). No made-up slang overload.\n"
    "- Say names exactly as they are spelled in the article.\n\n"
    "RULES\n"
    "- voiceover: ~35 words max (~15 s). Sentence 1 is the hook: lead with the look, the name or the number.\n"
    "- ACCURACY: use ONLY facts in the article. Never invent prices, dates, names, quotes, sales figures or who wore what. If it isn't in the article, don't say it.\n"
    "- No body or weight comments about anyone. Describe clothes, not bodies.\n"
    "- scenes: exactly 3 or 4. Each = 1 VO sentence + one short on_screen_text + one visual + duration_sec. Durations sum to exactly 15.\n"
    "- The scenes' vo_segment values, joined in order with spaces, MUST equal the voiceover.\n"
    "- on_screen_text: max ~5 words.\n"
    "- center: per scene, what shows in the MIDDLE of the frame. "
    "{\"type\":\"stat\",\"value\":\"2\",\"prefix\":\"$\",\"suffix\":\"B\",\"color\":\"green\",\"label\":\"max 5 words\"} for ONE striking number from the article "
    "(at most 1-2 scenes; value digits only; prefix/suffix short units like $, €, %, B, M, K; color red for a fall/loss, green for a rise, otherwise omit). "
    "{\"type\":\"entity\",\"kind\":\"person\",\"name\":\"Name\",\"wiki\":\"Exact English Wikipedia page title\"} when a well-known PUBLIC figure "
    "(designer, celebrity, model, CEO) is the subject, OR "
    "{\"type\":\"entity\",\"kind\":\"company\",\"name\":\"Brand\",\"wiki\":\"Exact English Wikipedia page title\"} when a fashion house, brand or retailer is the subject "
    "(we fetch its photo/logo from Wikipedia). Whenever a scene is centered on a named brand or public person you MUST use \"entity\". "
    "{\"type\":\"none\"} otherwise. NEVER invent a number.\n"
    "- hook: max 7 words. hashtags: 4-6, e.g. #fashion #fashionnews #5HU plus the brand/designer.\n\n"
    "VISUAL RULES (visual.query, English)\n"
    "- Show what the sentence is about: the garments, fabrics, accessories, shoes, a runway, a backstage rail, a boutique window, a sneaker on a pedestal, "
    "a street-style moment. Fashion-editorial, specific and literal to the sentence.\n"
    "- Do NOT depict real people's faces or recognisable celebrities: show anonymous models from behind or cropped at the shoulders, hands, silhouettes, "
    "or just the clothes. Do NOT draw real brand logos, monograms or trademarked patterns - describe colour, cut, material and mood instead.\n"
    "- No readable text, numbers or watermarks. No phone/computer screens with UI.\n"
    "- Each scene a clearly different shot and setting. Vertical 9:16, subject lower-middle, calmer space in the top third.\n\n"
    "SCHEMA\n"
    "{\"meta\":{\"title\":\"...\"},\"hook\":\"...\",\"hashtags\":[\"#...\"],\"voiceover\":\"...\","
    "\"scenes\":[{\"id\":1,\"vo_segment\":\"...\",\"on_screen_text\":\"...\",\"visual\":{\"query\":\"...\"},\"center\":{\"type\":\"none\"},\"duration_sec\":8},"
    "{\"id\":2,\"vo_segment\":\"...\",\"on_screen_text\":\"...\",\"visual\":{\"query\":\"...\"},\"center\":{\"type\":\"none\"},\"duration_sec\":7}]}\n\n"
    "ARTICLE\n" + article_expr)
assert "$json.articleText" in msg["content"]

# ---- code: 5hu_ files, channel, English Wikipedia first
code = by_name["Code in JavaScript"]["parameters"]["jsCode"]


def rep(old, new, count=1):
    global code
    assert code.count(old) == count, (old, code.count(old))
    code = code.replace(old, new)


for kind in ("img", "voice", "video", "job"):
    rep('"lt_%s_"+ts' % kind, '"5hu_%s_"+ts' % kind)
rep('"Lietuvos naujienos"', '"fashion runway editorial"', 2)
rep('channel:"lt",', 'channel:"5hu",')
rep("return (await wikiImage(title, 'lt')) || (await wikiImage(title, 'en'));", "return (await wikiImage(title, 'en')) || (await wikiImage(title, 'lt'));")
rep("return (await companyLogo(title, 'lt')) || (await companyLogo(title, 'en'));", "return (await companyLogo(title, 'en')) || (await companyLogo(title, 'lt'));")
by_name["Code in JavaScript"]["parameters"]["jsCode"] = code

# ---- image style
ss = by_name["Split Scenes"]["parameters"]
i0 = ss["jsCode"].index('const STYLE="')
i1 = ss["jsCode"].index('";', i0) + 2
ss["jsCode"] = ss["jsCode"][:i0] + (
    'const STYLE=" Style: high-fashion editorial photography, photorealistic, Vogue-style art direction, rich fabric texture, '
    'dramatic studio or runway lighting, bold but tasteful colour, shallow depth of field. Anonymous models only (no recognisable faces), '
    'no real brand logos. Vertical 9:16. No text, no numbers, no watermark.";') + ss["jsCode"][i1:]

# ---- voice
tts = by_name["Convert text to speech"]["parameters"]
tts["voice"] = {"__rl": True, "mode": "id", "value": VOICE_ID}
tts["additionalOptions"]["model"] = {"__rl": True, "value": MODEL, "mode": "list", "cachedResultName": "Eleven v4"}
tts["additionalOptions"]["voiceSettings"] = json.dumps(
    {"stability": 0.45, "similarity_boost": 0.85, "style": 0.35, "use_speaker_boost": True, "speed": 1.05}, indent=2)

# ---- sanity
names = [n["name"] for n in w["nodes"]]
for outs in w["connections"].values():
    for branch in outs.get("main", []):
        for c in branch or []:
            assert c["node"] in names, c
blob = json.dumps(w, ensure_ascii=False)
for gone in ("lrt.lt", "15min.lt", "lrytas", "lt_img_"):
    assert gone not in blob, gone
assert all(n["id"] != o["id"] for n in w["nodes"] for o in src["nodes"])
json.dump(w, open(DST, "w"), indent=2, ensure_ascii=False)
print(f"OK -> {DST}: {len(w['nodes'])} nodes, id={w['id']}")
