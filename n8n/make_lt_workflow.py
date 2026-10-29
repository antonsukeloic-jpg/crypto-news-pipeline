#!/usr/bin/env python3
"""Build the "LT News Pipeline" workflow from the VPS crypto workflow.

Input : the crypto VPS workflow (output of make_vps_workflow.py).
Output: a SEPARATE workflow (own id, node ids, webhook ids) that reads
        Lithuanian news feeds (Delfi, 15min, Lrytas), writes the script in
        Lithuanian, speaks it with a Lithuanian ElevenLabs voice, and tags the
        job with "channel": "lt" and lt_ file prefixes.

It never touches the crypto workflow: the crypto JSON is read, deep-copied and
rewritten. The Telegram trigger lives in the crypto workflow (one bot = one
webhook), which calls this workflow through its "Run Now (CLI)" trigger.

usage: make_lt_workflow.py <crypto_vps.json> <out_lt.json>
"""
import copy, json, sys, uuid

SRC = sys.argv[1] if len(sys.argv) > 1 else "n8n/workflow_vps.json"
DST = sys.argv[2] if len(sys.argv) > 2 else "n8n/workflow_lt.json"

LT_WORKFLOW_ID = "LtNewsPipeLine01"          # fixed, 16 chars, never the crypto id
LT_VOICE_ID = "8crourjnsg8XHpBXQXHa"         # "Audrius" - cloned native Lithuanian voice
LT_MODEL = "eleven_v3"                       # Eleven v3 officially supports Lithuanian

FEEDS = [
    # delfi.lt/rss/feeds/daily.xml is now just an index of feeds; this is its "Dienos naujienos" feed
    ("Delfi", "https://feed.delfi.lt/v2/articles/6?format=rss"),
    ("15min", "https://www.15min.lt/rss"),
    ("Lrytas", "https://www.lrytas.lt/rss"),
]

src = json.load(open(SRC))
assert src.get("id") != LT_WORKFLOW_ID
w = copy.deepcopy(src)
w["name"] = "LT News Pipeline"
w["id"] = LT_WORKFLOW_ID
for k in ("versionId", "staticData", "pinData", "tags", "meta"):
    w.pop(k, None)
w["settings"] = dict(w.get("settings") or {}, callerPolicy="workflowsFromSameOwner")

# ---- 1) drop the Telegram command nodes: the crypto workflow is the router
DROP = {"Telegram Command", "Is /run from me?", "Reply: starting"}
w["nodes"] = [n for n in w["nodes"] if n["name"] not in DROP]
for d in DROP:
    w["connections"].pop(d, None)
by_name = {n["name"]: n for n in w["nodes"]}

# ---- 2) fresh node ids + webhook ids so nothing collides with the crypto workflow
for n in w["nodes"]:
    n["id"] = str(uuid.uuid4())
    if "webhookId" in n:
        n["webhookId"] = str(uuid.uuid4())
    if n["type"] == "n8n-nodes-base.scheduleTrigger":
        n["disabled"] = True                         # never runs on a schedule

# ---- 3) RSS feeds. A dead feed must not kill the run: continue with the others.
for (name, url), node in zip(FEEDS, ("RSS A", "RSS B", "RSS C")):
    by_name[node]["parameters"]["url"] = url
    by_name[node]["onError"] = "continueRegularOutput"
    by_name[node].update({"retryOnFail": True, "maxTries": 2, "waitBetweenTries": 3000})
cf = by_name["Combine Feeds"]["parameters"]
old = "const srcs=[['CoinDesk','RSS A'],['Cointelegraph','RSS B'],['Decrypt','RSS C']];"
assert old in cf["jsCode"]
cf["jsCode"] = cf["jsCode"].replace(
    old, "const srcs=[['Delfi','RSS A'],['15min','RSS B'],['Lrytas','RSS C']];")
# RSS node errors arrive as items with an "error" key: ignore those
cf["jsCode"] = cf["jsCode"].replace(
    "items=$(node).all().map(i=>i.json);",
    "items=$(node).all().map(i=>i.json).filter(j=>j&&!j.error);")
assert "filter(j=>j&&!j.error)" in cf["jsCode"]

# ---- 4) Select Story: Lithuanian general-news editor
by_name["Select Story"]["parameters"]["messages"]["values"][0]["content"] = (
    "=You are the editor of a Lithuanian general-news TikTok channel. Choose the SINGLE best story "
    "from the candidates for a 15-second vertical video for a Lithuanian audience.\n\n"
    "HARD RULES\n"
    "- Prefer concrete, surprising, number-driven, talked-about news: politics decisions, economy and prices, "
    "big events in Lithuania, science/tech, sport results, weather extremes, things people will share.\n"
    "- AVOID graphic tragedies, deaths of private persons, crime details, accidents with victims, suicide, "
    "violence against children, and anything that cannot be told accurately in 15 seconds.\n"
    "- Avoid pure opinion columns, horoscopes, recipes, sponsored or thin posts, live blogs, and paywalled teasers.\n"
    "- Prefer stories about Lithuania or directly affecting Lithuanians over distant foreign news.\n\n"
    "- Prefer not to pick obituaries or death announcements unless the story is clearly the day's biggest news.\n\n"
    "Output ONLY valid JSON, no markdown, no code fences. Inside JSON strings never use the ASCII double quote character; "
    "write Lithuanian quotes as „ and “ instead.\n"
    "{\"link\":\"<exact LINK of the chosen story>\",\"title\":\"<its title>\",\"reason\":\"<max 12 words>\"}\n\n"
    "CANDIDATES\n{{ $json.candidatesText }}")

# ---- 4b) Parse Selection: Lithuanian titles contain „ ... " quotes that break naive JSON;
#          recover the link with a regex and take the title from the candidates list.
by_name["Parse Selection"]["parameters"]["jsCode"] = (
    "const raw = $input.first().json.content[0].text;\n"
    "let sel = null;\n"
    "try { const s = raw.indexOf('{'); const e = raw.lastIndexOf('}'); sel = JSON.parse(raw.slice(s, e + 1)); } catch (err) { sel = null; }\n"
    "const cands = ($('Combine Feeds').first().json.candidates) || [];\n"
    "if (!sel || !sel.link) {\n"
    "  const m = raw.match(/\"link\"\\s*:\\s*\"([^\"\\s]+)\"/) || raw.match(/https?:\\/\\/[^\\s\"'<>]+/);\n"
    "  if (!m) throw new Error('Parse Selection: no link in: ' + raw.slice(0, 300));\n"
    "  const link = m[1] || m[0];\n"
    "  const rm = raw.match(/\"reason\"\\s*:\\s*\"([^\"]*)\"/);\n"
    "  sel = { link, title: '', reason: rm ? rm[1] : '' };\n"
    "}\n"
    "const hit = cands.find(c => c.link === sel.link) || cands.find(c => sel.link && c.link && (c.link.indexOf(sel.link) === 0 || sel.link.indexOf(c.link) === 0));\n"
    "if (hit && (!sel.title || sel.title.length < 4)) sel.title = hit.title;\n"
    "return [{ json: { link: sel.link, title: sel.title || '', source_url: sel.link, reason: sel.reason || '', source: hit ? hit.source : '' } }];")

# ---- 5) Script prompt: same schema, Lithuanian voiceover/text, English visual.query, no crypto fields
msg = by_name["Message a model"]["parameters"]["messages"]["values"][0]
article_expr = msg["content"].split("ARTICLE\n", 1)[1]        # keep the RSS-fallback expression
msg["content"] = (
    "=You are a short-form scriptwriter for a Lithuanian-language general news channel (TikTok/Reels). "
    "Turn ONE news article into a 15-second vertical video plan.\n\n"
    "Output ONLY valid JSON matching the SCHEMA below. No markdown, no code fences, no text before or after the JSON. "
    "Inside JSON strings never use the ASCII double quote character: write Lithuanian quotes as „ and “ instead.\n\n"
    "LANGUAGE\n"
    "- voiceover, every vo_segment, on_screen_text, hook, meta.title, center.label and hashtags are in NATURAL SPOKEN LITHUANIAN: "
    "the way a young Lithuanian news presenter actually talks. Correct grammar, correct cases and endings, correct diacritics "
    "(ą č ę ė į š ų ū ž). Short sentences. No anglicisms, no bureaucratic phrasing, no literal translations from English.\n"
    "- Write numbers so they are read correctly aloud in Lithuanian: prefer words for small numbers and keep units spoken "
    "(e.g. \"penkiais procentais\", \"du milijonai eurų\", \"trisdešimt metų\"). Use digits only where natural (years, big figures).\n"
    "- Names of people and places stay in their Lithuanian form with correct declension.\n"
    "- visual.query stays in ENGLISH (the image model works better in English).\n\n"
    "RULES\n"
    "- voiceover: punchy spoken-word, ~35 words max (~15s total). Strong hook in sentence 1. Plain language, active voice. "
    "TONE: a fast, confident, energetic news presenter - urgent but factual; lead with the number or the stakes. No clickbait lies.\n"
    "- ACCURACY: use ONLY facts in the article. Never invent numbers, prices, dates, names or quotes. If a figure isn't in the article, don't state it.\n"
    "- scenes: exactly 3 or 4. Each = 1 VO sentence + one short on_screen_text + one visual + a duration.\n"
    "- duration_sec: integer seconds the scene shows. Scene durations MUST sum to exactly 15.\n"
    "- The scenes' vo_segment values, joined in order with spaces, MUST equal the voiceover.\n"
    "- on_screen_text: max ~5 words, Lithuanian.\n"
    "- visual.query: a vivid 1-2 sentence ENGLISH description of an image that clearly SHOWS the key subject of THIS sentence (follow VISUAL RULES).\n"
    "- center: per scene, pick what shows in the MIDDLE of the frame. "
    "{\"type\":\"stat\",\"value\":\"635\",\"prefix\":\"\",\"suffix\":\"%\",\"color\":\"red\",\"label\":\"max 5 Lithuanian words\"} "
    "for a scene built on ONE striking number (at most 1-2 scenes, most impactful figures only; value = digits only with optional decimal; "
    "prefix/suffix are SHORT symbols or units ONLY (€, %, mln., mlrd., tūkst., km, °C, or empty) - NEVER whole words like \"žmonių\" (put those in the label); "
    "color \"red\" for a loss/fall/bad, \"green\" for a gain/rise/good, otherwise omit color). "
    "{\"type\":\"entity\",\"kind\":\"person\",\"name\":\"Vardas Pavardė\",\"wiki\":\"Exact lt.wikipedia page title\",\"wiki_en\":\"Exact en.wikipedia page title or none\"} "
    "when a specific well-known PUBLIC figure is the subject, OR "
    "{\"type\":\"entity\",\"kind\":\"company\",\"name\":\"Short Name\",\"wiki\":\"Exact lt.wikipedia page title\",\"wiki_en\":\"Exact en.wikipedia page title or none\"} "
    "when a specific company, institution, party, club, city or organization is the subject - we fetch its photo/logo from Wikipedia and show it with the name. "
    "Give the EXACT Lithuanian Wikipedia page title in the NOMINATIVE case (e.g. \"Gitanas Nausėda\", \"Vilnius\", \"Lietuvos bankas\", \"Maxima\", \"Žalgiris\") "
    "and the English one if it exists (e.g. \"Gitanas Nausėda\", \"Bank of Lithuania\"); use \"none\" if unsure. "
    "Only well-known public figures or organizations, never a private individual or a victim. "
    "{\"type\":\"none\"} otherwise (general beats - the image carries it). "
    "Whenever a scene is centered on a named company, institution, party, club, city or a named public person you MUST set \"entity\" (not \"none\"). "
    "Keep the middle engaged across the WHOLE video, not just the first scene. NEVER invent a number: only use \"stat\" for figures actually stated in the article.\n"
    "- hook: most scroll-stopping line in Lithuanian, max 7 words.\n"
    "- hashtags: 4-6 Lithuanian hashtags, no spaces (e.g. #lietuva #naujienos).\n\n"
    "VISUAL RULES (for every visual.query, in English)\n"
    "- FIRST pick the KEY SUBJECT or ACTION of this scene's vo_segment - the one thing the viewer should literally SEE while they hear that line. "
    "Then describe an image that clearly SHOWS that exact thing, so the picture matches the spoken words.\n"
    "- Be SPECIFIC and literal to the sentence, not abstract filler. Examples: \"prices rise\" -> a shopper staring at a supermarket shelf price tag; "
    "\"a new law\" -> a hand stamping an official document in a parliament hall; \"storm\" -> wind bending trees on a Lithuanian village road; "
    "\"a win\" -> basketball players celebrating on the court. If a viewer paused on the frame, they should guess the sentence.\n"
    "- Set scenes in Lithuania / Northern Europe when relevant (Baltic architecture, old town streets, pine forests, Baltic sea coast, grey autumn light) - never generic American imagery.\n"
    "- Each scene visualizes ITS OWN sentence - a clearly DIFFERENT subject and setting every time. Never reuse the same location or motif across scenes.\n"
    "- NO readable text, numbers, words, logos, flags with writing, signage or watermarks in the image (we add those). Do NOT depict real people's faces or real company branding/logos.\n"
    "- Do NOT draw phone/computer/TV screens showing UI, charts or symbols - the AI renders these as fake gibberish. Show the real-world scene or ACTION instead. "
    "Also do NOT depict a specific real building or branded storefront; show a neutral real-world scene or the action.\n"
    "- Match the real sentiment of the article - do not show panic or disaster unless the news is genuinely negative. No gore, no injured people.\n"
    "- Vertical 9:16, main subject in the lower-middle, clean darker empty space in the top third.\n\n"
    "SCHEMA\n"
    "{\"meta\":{\"title\":\"...\"},\"hook\":\"...\",\"hashtags\":[\"#...\"],\"voiceover\":\"...\","
    "\"scenes\":[{\"id\":1,\"vo_segment\":\"...\",\"on_screen_text\":\"...\",\"visual\":{\"query\":\"...\"},\"center\":{\"type\":\"none\"},\"duration_sec\":8},"
    "{\"id\":2,\"vo_segment\":\"...\",\"on_screen_text\":\"...\",\"visual\":{\"query\":\"...\"},\"center\":{\"type\":\"none\"},\"duration_sec\":7}]}\n\n"
    "ARTICLE\n" + article_expr)
assert "$json.articleText" in msg["content"]

# ---- 6) Code in JavaScript: lt_ file names, no BTC/ticker, lt.wikipedia first, Lithuanian STOP words, channel "lt"
code = by_name["Code in JavaScript"]["parameters"]["jsCode"]


def rep(old, new, count=1):
    global code
    assert code.count(old) == count, (old, code.count(old))
    code = code.replace(old, new)


rep('"crypto news"', '"Lietuvos naujienos"', 2)
rep('s.imageFile = "img_"+ts', 's.imageFile = "lt_img_"+ts')
rep('data.voiceFile = "voice_"+ts', 'data.voiceFile = "lt_voice_"+ts')
rep('data.outputFile = "video_"+ts', 'data.outputFile = "lt_video_"+ts')
rep('data.jobFile = "job_"+ts', 'data.jobFile = "lt_job_"+ts')
# no BTC price call, no ticker
btc_line = next(l for l in code.split("\n") if "api.coingecko.com/api/v3/simple/price" in l)
rep(btc_line + "\n", "")
rep('var ticker = (data.ticker || "").toLowerCase();', 'var ticker = "";')
# Wikipedia: lt first, then en (both for page images and for the Wikidata logo lookup)
rep("const wikiImage = async (title) => {\n  if (!title) return null;\n  try {\n    const u = 'https://en.wikipedia.org/w/api.php?",
    "const wikiImage = async (title, lang) => {\n  if (!title) return null;\n  if (!lang) { return (await wikiImage(title, 'lt')) || (await wikiImage(title, 'en')); }\n  try {\n    const u = 'https://' + lang + '.wikipedia.org/w/api.php?")
rep("const companyLogo = async (title) => {\n  if (!title) return null;\n  try {\n    const u1 = 'https://en.wikipedia.org/w/api.php?",
    "const companyLogo = async (title, lang) => {\n  if (!title) return null;\n  if (!lang) { return (await companyLogo(title, 'lt')) || (await companyLogo(title, 'en')); }\n  try {\n    const u1 = 'https://' + lang + '.wikipedia.org/w/api.php?")
# no CoinGecko fallbacks for a general-news channel
rep("  if (!img) img = await cgEntity(name);\n", "")
# entity lookup: lt title, then the English title the model gave (en only), then plain name
rep("let img = isPerson ? (await wikiImage(title) || (c.name && c.name !== title ? await wikiImage(c.name) : null)) : await resolveNonPerson(title);",
    "const enT = (c.wiki_en && c.wiki_en !== 'none') ? c.wiki_en : '';\n"
    "    let img = isPerson ? (await wikiImage(title) || (enT ? await wikiImage(enT, 'en') : null) || (c.name && c.name !== title ? await wikiImage(c.name) : null))\n"
    "                       : (await resolveNonPerson(title) || (enT ? (await companyLogo(enT, 'en') || await wikiImage(enT, 'en')) : null));")
# Lithuanian-aware capitalised-word extraction + STOP words (months, weekdays, country/cities when not the subject, common sentence starters)
rep("const looksPerson = (n) => /^[A-Z][a-z]+ [A-Z][a-z]+$/.test(n);",
    "const looksPerson = (n) => /^\\p{Lu}\\p{Ll}+ \\p{Lu}\\p{Ll}+$/u.test(n);")
rep("let m; const reBrand = /\\b([A-Za-z]*[A-Z][A-Za-z]*[A-Z][A-Za-z0-9]*)\\b/g; while ((m = reBrand.exec(vo))) add(m[1]);\n"
    "  const reMulti = /\\b([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)+)\\b/g; while ((m = reMulti.exec(vo))) add(m[1]);\n"
    "  const reSingle = /\\b([A-Z][a-z]{2,})\\b/g; while ((m = reSingle.exec(vo))) add(m[1]);",
    "let m; const reBrand = /(?<!\\p{L})(\\p{L}*\\p{Lu}\\p{L}*\\p{Lu}[\\p{L}0-9]*)(?!\\p{L})/gu; while ((m = reBrand.exec(vo))) add(m[1]);\n"
    "  const reMulti = /(?<!\\p{L})(\\p{Lu}\\p{Ll}+(?:\\s+\\p{Lu}\\p{Ll}+)+)(?!\\p{L})/gu;\n"
    "  while ((m = reMulti.exec(vo))) { let ws = m[1].split(/\\s+/); while (ws.length && STOP.has(ws[0])) ws.shift(); while (ws.length && STOP.has(ws[ws.length - 1])) ws.pop(); if (ws.length > 1) add(ws.join(' ')); }\n"
    "  const reSingle = /(?<!\\p{L})(\\p{Lu}\\p{Ll}{2,})(?!\\p{L})/gu; while ((m = reSingle.exec(vo))) add(m[1]);")
LT_STOP = [
    # months (all cases), weekdays, generic words that start sentences or are capitalised in Lithuanian news
    'Sausio','Sausis','Vasario','Vasaris','Kovo','Kovas','Balandžio','Balandis','Gegužės','Gegužė','Birželio','Birželis',
    'Liepos','Liepa','Rugpjūčio','Rugpjūtis','Rugsėjo','Rugsėjis','Spalio','Spalis','Lapkričio','Lapkritis','Gruodžio','Gruodis',
    'Pirmadienį','Pirmadienis','Antradienį','Antradienis','Trečiadienį','Trečiadienis','Ketvirtadienį','Ketvirtadienis',
    'Penktadienį','Penktadienis','Šeštadienį','Šeštadienis','Sekmadienį','Sekmadienis',
    'Lietuva','Lietuvos','Lietuvoje','Lietuvai','Lietuvą','Lietuviai','Lietuvių','Lietuviams','Lietuvis','Lietuvė',
    'Vilnius','Vilniuje','Vilniaus','Vilnių','Kaunas','Kaune','Kauno','Kauną','Klaipėda','Klaipėdoje','Klaipėdos',
    'Šiauliai','Šiauliuose','Panevėžys','Panevėžyje','Europa','Europos','Europoje','Europą','Rusija','Rusijos','Rusijoje',
    'Baltarusija','Baltarusijos','Latvija','Latvijos','Lenkija','Lenkijos','Ukraina','Ukrainos','Ukrainoje','JAV','ES','NATO',
    'Vyriausybė','Vyriausybės','Seimas','Seimo','Seime','Prezidentas','Prezidento','Ministras','Ministrė','Ministerija',
    'Policija','Policijos','Teismas','Teismo','Savivaldybė','Savivaldybės','Euras','Eurų','Eurai','Eurais',
    'Šiandien','Vakar','Rytoj','Šiąnakt','Šįryt','Tačiau','Todėl','Taip','Dabar','Jau','Dar','Bet','Ir','Kai','Nes','Kad',
    'Jis','Ji','Jie','Jos','Mes','Jūs','Tai','Tas','Ta','Tie','Tos','Čia','Ten','Tik','Net','Pagal','Anot','Po','Per','Nuo',
    'Iki','Prie','Apie','Dėl','Su','Be','Už','Ant','Iš','Į','O','Kaip','Kodėl','Kiek','Kur','Kas','Jei','Jeigu','Nors',
    'Milijonas','Milijonai','Milijonų','Milijardas','Milijardų','Tūkstančiai','Tūkstančių','Procentai','Procentų',
    'Naujienos','Delfi','Lrytas','BNS','ELTA','LRT','Pranešama','Pranešė','Teigiama','Sako','Teigia','Skelbia',
]
rep("'Saturday','Sunday'].concat(MONTHS));",
    "'Saturday','Sunday'].concat(MONTHS).concat(" + json.dumps(LT_STOP, ensure_ascii=False) + "));")
# job tags
rep("const job = { comp:\"main\", voice:\"assets/\"+data.voiceFile,",
    "const job = { comp:\"main\", channel:\"lt\", voice:\"assets/\"+data.voiceFile,")
rep("btc_price: btc_price, btc_change_24h: btc_change_24h, ", "")
assert "coingecko.com/api/v3/simple/price" not in code and 'channel:"lt"' in code
by_name["Code in JavaScript"]["parameters"]["jsCode"] = code

# ---- 7) image style: editorial/cinematic instead of crypto neon
ss = by_name["Split Scenes"]["parameters"]
assert "cyberpunk neon" in ss["jsCode"]
ss["jsCode"] = ss["jsCode"].replace(
    ss["jsCode"][ss["jsCode"].index('const STYLE="'):ss["jsCode"].index('";', ss["jsCode"].index('const STYLE="')) + 2],
    'const STYLE=" Style: cinematic editorial news photography, photorealistic, natural Northern European light, '
    'shallow depth of field, rich but realistic colours, high detail, dramatic but believable. Vertical 9:16. '
    'No text, no numbers, no logos, no flags with writing, no watermark.";')

# ---- 8) voice: Lithuanian cloned voice on Eleven v3
tts = by_name["Convert text to speech"]["parameters"]
tts["voice"] = {"__rl": True, "mode": "id", "value": LT_VOICE_ID}
tts["additionalOptions"]["model"] = {"__rl": True, "value": LT_MODEL, "mode": "list", "cachedResultName": "Eleven v3"}
tts["additionalOptions"]["voiceSettings"] = json.dumps(
    {"stability": 0.6, "similarity_boost": 0.9, "style": 0.2, "use_speaker_boost": True, "speed": 1.0}, indent=2)

# ---- 9) captions: if forced alignment can't follow Lithuanian, keep the evenly spaced fallback
ac = by_name["Add Captions"]["parameters"]
old = "if (job && captions.length) { job.captions = captions; }"
assert old in ac["jsCode"]
ac["jsCode"] = ac["jsCode"].replace(old,
    "const voWords = ((($('Code in JavaScript').first().json.voiceover) || '').trim().split(/\\s+/).filter(Boolean)).length;\n"
    "const sane = captions.length && Math.abs(captions.length - voWords) <= Math.max(3, Math.round(voWords * 0.35));\n"
    "if (job && sane) { job.captions = captions; }\n"
    "if (job) { job.align_words = captions.length; job.vo_words = voWords; }")

# ---- 10) sanity
names = [n["name"] for n in w["nodes"]]
assert "Run Now (CLI)" in names and "Every Hour" in names and "Telegram Command" not in names
for outs in w["connections"].values():
    for branch in outs.get("main", []):
        for c in branch or []:
            assert c["node"] in names, c
assert not any("coindesk" in json.dumps(n).lower() for n in w["nodes"])
assert all(n["id"] != o["id"] for n in w["nodes"] for o in src["nodes"])
json.dump(w, open(DST, "w"), indent=2, ensure_ascii=False)
print(f"OK -> {DST}: {len(w['nodes'])} nodes, id={w['id']}, voice={LT_VOICE_ID}/{LT_MODEL}")
