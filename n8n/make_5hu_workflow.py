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
VOICE_ID = "Hx5CHMHGoSXR9An8HMln"           # "5HU Voice" - designed 2026-11-15 (owner picked A): smoky, breathy, slow-dramatic, slight Eastern European accent
MODEL = "eleven_v4"

# all tested from the VPS 2026-11-15 (fresh, readable).
# tiers: "emerging" (new designers / local scenes) > "niche" (indie, streetwear, craft) > "main" (big titles).
FEEDS = [
    # emerging designers + local scenes: Scandinavia, London, New York, Berlin, Madrid/Seoul
    ("Scandinavian MIND", "https://www.scandinavianmind.com/feed", "emerging"),
    ("BON (Stockholm)", "https://bon.se/feed", "emerging"),
    ("10 Magazine (London)", "https://www.10magazine.com/feed/", "emerging"),
    ("Office Magazine (NY)", "https://www.officemagazine.net/rss.xml", "emerging"),
    ("Kaltblut (Berlin)", "https://www.kaltblut-magazine.com/feed/", "emerging"),
    ("Highxtar", "https://highxtar.com/feed/", "emerging"),
    ("Numero", "https://www.numero.com/en/rss", "niche"),
    ("Interview", "https://www.interviewmagazine.com/feed", "niche"),
    ("NYLON", "https://www.nylon.com/feeds/feed.rss", "niche"),
    ("The Fashionisto", "https://www.thefashionisto.com/feed/", "niche"),
    ("FashionUnited", "https://fashionunited.uk/rss-news", "main"),
    ("Coveteur", "https://coveteur.com/feeds/feed.rss", "main"),
    # mainstream / industry
    ("Vogue", "https://www.vogue.com/feed/rss", "main"),
    ("British Vogue", "https://www.vogue.co.uk/feed/rss", "main"),
    ("WWD", "https://wwd.com/feed/", "main"),
    ("Harper's Bazaar", "https://www.harpersbazaar.com/rss/all.xml/", "main"),
    ("Elle", "https://www.elle.com/rss/all.xml/", "main"),
    ("Fashionista", "https://fashionista.com/.rss/excerpt/", "main"),
    ("Who What Wear", "https://www.whowhatwear.com/rss", "main"),
    ("Esquire Style", "https://www.esquire.com/rss/style.xml/", "main"),
    # streetwear / sneakers
    ("Hypebeast", "https://hypebeast.com/feed", "niche"),
    ("Hypebae", "https://www.hypebae.com/feed", "niche"),
    ("Highsnobiety", "https://www.highsnobiety.com/feed/", "niche"),
    # culture / indie / niche
    ("Dazed", "https://www.dazeddigital.com/rss", "niche"),
    ("i-D", "https://i-d.co/feed/", "niche"),
    ("PAPER", "https://www.papermag.com/feeds/feed.rss", "niche"),
    ("Refinery29 Fashion", "https://www.refinery29.com/en-us/fashion/rss.xml", "niche"),
    # menswear / craft / denim
    ("Permanent Style", "https://www.permanentstyle.com/feed", "niche"),
    ("Put This On", "https://www.putthison.com/rss", "niche"),
    ("Heddels", "https://www.heddels.com/feed/", "niche"),
    ("DMARGE", "https://www.dmarge.com/feed", "niche"),
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

# ---- feeds: one node reads every feed in parallel (replaces RSS A/B/C).
#      Keeps the name "Combine Feeds" and the same output shape, so later nodes work unchanged.
DROP = {"RSS A", "RSS B", "RSS C"}
w["nodes"] = [n for n in w["nodes"] if n["name"] not in DROP]
for d in DROP:
    w["connections"].pop(d, None)
by_name = {n["name"]: n for n in w["nodes"]}
w["connections"]["Run Now (CLI)"] = {"main": [[{"node": "Combine Feeds", "type": "main", "index": 0}]]}
w["connections"]["Every Hour"] = {"main": [[{"node": "Combine Feeds", "type": "main", "index": 0}]]}
cf = by_name["Combine Feeds"]
cf["parameters"]["jsCode"] = (
    "const FEEDS = " + json.dumps(FEEDS, ensure_ascii=False) + ";\n"
    + r"""const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36';
const decode = (s) => String(s || '')
  .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1').replace(/<[^>]+>/g, ' ')
  .replace(/&#8217;|&rsquo;|&#8216;|&lsquo;|&#039;|&#39;|&apos;/g, "'").replace(/&#8220;|&#8221;|&ldquo;|&rdquo;|&quot;/g, '"')
  .replace(/&#8211;|&ndash;/g, '-').replace(/&#8212;|&mdash;/g, '-').replace(/&nbsp;|&#160;/g, ' ')
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&#(\d+);/g, (m, n) => String.fromCharCode(+n)).replace(/&amp;/g, '&')
  .replace(/\s+/g, ' ').trim();
const tag = (b, t) => { const m = b.match(new RegExp('<' + t + '(?:\\s[^>]*)?>([\\s\\S]*?)</' + t + '>', 'i')); return m ? m[1] : ''; };
const parse = (xml, source, tier) => {
  const blocks = xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || xml.match(/<entry[\s>][\s\S]*?<\/entry>/gi) || [];
  return blocks.map(b => {
    let link = decode(tag(b, 'link'));
    if (!link) { const m = b.match(/<link[^>]*href="([^"]+)"/i); link = m ? m[1] : ''; }
    if (!link) link = decode(tag(b, 'guid'));
    const date = decode(tag(b, 'pubDate') || tag(b, 'published') || tag(b, 'updated') || tag(b, 'dc:date'));
    const snippet = decode(tag(b, 'description') || tag(b, 'summary') || tag(b, 'content:encoded')).slice(0, 240);
    return { source, tier, title: decode(tag(b, 'title')), link: link.trim(), snippet, date };
  }).filter(x => x.title && /^https?:/.test(x.link));
};
const res = await Promise.allSettled(FEEDS.map(([name, url, tier]) =>
  this.helpers.httpRequest({ url, timeout: 15000, headers: { 'User-Agent': UA, 'Accept': 'application/rss+xml,application/xml,text/xml,*/*' } })
    .then(body => parse(typeof body === 'string' ? body : String(body), name, tier))));
let all = [], ok = 0;
res.forEach(r => { if (r.status === 'fulfilled' && r.value.length) { ok++; all = all.concat(r.value); } });
// only new stories: skip links already used (kept in workflow static data) and older than 72 h
const _st = $getWorkflowStaticData('global'); const _seen = new Set(_st.seen5hu || []);
const age = (x) => Date.now() - (new Date(x.date).getTime() || 0);
all = all.filter(x => !_seen.has(x.link) && age(x) < (x.tier === 'emerging' ? 120 : 72) * 3600e3);
if (!all.length) throw new Error('5HU: no new fashion stories (feeds read: ' + ok + ')');
// newest 2 per source, then a pool with niche sources first: up to 8 niche + 4 mainstream, shuffled
const per = {}; all.sort((a, b) => age(a) - age(b));
all = all.filter(x => (per[x.source] = (per[x.source] || 0) + 1) <= 2);
const shuffle = (a) => { for (let i = a.length - 1; i > 0; i--) { const k = Math.floor(Math.random() * (i + 1)); [a[i], a[k]] = [a[k], a[i]]; } return a; };
const RISING = /\b(emerging|newcomer|debut (collection|show|runway|store|season)|first (collection|show|runway|store)|designers? to (watch|know)|labels? to (watch|know)|rising (star|label|designer|brand)|new (label|brand|designer)|up-and-coming|graduate collection|LVMH Prize|ANDAM|Woolmark|Fashion East|NEWGEN|Copenhagen Fashion Week|Stockholm|Oslo|Helsinki|Scandinavian (label|brand|designer|fashion)|Nordic (label|brand|designer|fashion)|Tokyo Fashion Week|Seoul Fashion Week|independent (label|brand|designer)|indie (label|brand|designer)|young designer|breakout|cult (label|brand|sneaker|favourite|favorite))\b/i;
const rising = (x) => RISING.test(x.title + ' ' + x.snippet);
const used = new Set(); const take = (arr, n) => arr.filter(x => !used.has(x.link)).slice(0, n).map(x => (used.add(x.link), x));
const pool = [].concat(
  take(shuffle(all.filter(rising)), 6),
  take(shuffle(all.filter(x => x.tier === 'emerging')), 4),
  take(shuffle(all.filter(x => x.tier === 'niche')), 3),
  take(shuffle(all.filter(x => x.tier === 'main')), 2));
const candidates = shuffle(pool.length ? pool : all.slice(0, 12));
const candidatesText = candidates.map((x, i) => (i + 1) + '. [' + x.source + (x.tier !== 'main' ? ', ' + x.tier : '') + (rising(x) ? ', RISING' : '') + '] ' + x.title + '\n   ' + x.snippet + '\n   LINK: ' + x.link).join('\n\n');
return [{ json: { candidates, candidatesText, feedsRead: ok } }];""")

ps = by_name["Parse Selection"]["parameters"]
old = "return [{ json: { link: sel.link,"
assert ps["jsCode"].count(old) == 1
ps["jsCode"] = ps["jsCode"].replace(old,
    "const _st = $getWorkflowStaticData('global'); _st.seen5hu = [sel.link].concat(_st.seen5hu || []).slice(0, 500);\n" + old)

# ---- editor: "who's next" fashion
by_name["Select Story"]["parameters"]["messages"]["values"][0]["content"] = (
    "=You are the editor of 5HU, the channel that spots fashion's NEXT big names before everyone else - "
    "TikTok/Reels/Shorts for a young, style-obsessed global audience. Choose the SINGLE best story from the candidates for a 15-second video.\n\n"
    "5HU'S IDENTITY - pick in this order:\n"
    "1. A rising independent label or young designer (roughly the last 10 years) from a scene with buzz - Copenhagen, Stockholm, Oslo, Helsinki, "
    "London, New York, Paris, Berlin, Tokyo, Seoul, Antwerp, Milan, Lagos, Mexico City... Signals: debut show or first fashion-week slot, "
    "prize shortlist (LVMH Prize, ANDAM, Woolmark, NEWGEN, Fashion East), first store or big stockist, a celebrity or stylist picking them up, "
    "a breakout collab, a designer from a small label getting a bigger job.\n"
    "2. A cult / boutique brand doing something new (drop, collab, archive revival, new direction).\n"
    "3. A new micro-trend or scene with a clear name and concrete examples.\n"
    "4. Only if nothing above exists: the most interesting insider story from a big house (not celebrity gossip).\n"
    "Candidates tagged RISING or emerging are usually best. Freshness matters: newer beats older.\n"
    "AVOID: deaths and obituaries, body or weight talk, anything about minors' bodies, crime/lawsuits with victims, shopping roundups, "
    "sales/affiliate lists, horoscopes, sponsored posts, celebrity relationship gossip, essays without news, "
    "and anything that can't be told accurately in 15 seconds.\n\n"
    "Output ONLY valid JSON, no markdown, no code fences. Inside JSON strings use typographic quotes “ ” instead of the ASCII double quote.\n"
    "{\"link\":\"<exact LINK of the chosen story>\",\"title\":\"<its title>\",\"reason\":\"<max 12 words>\"}\n\n"
    "CANDIDATES\n{{ $json.candidatesText }}")

# ---- script writer (same schema; English; entities from en.wikipedia)
msg = by_name["Message a model"]["parameters"]["messages"]["values"][0]
article_expr = msg["content"].split("ARTICLE\n", 1)[1]
msg["content"] = (
    "=You are the scriptwriter for 5HU - the channel that spots fashion's next big names first (TikTok/Reels/Shorts). Turn ONE fashion news article into a 15-second vertical video plan.\n\n"
    "Output ONLY valid JSON matching the SCHEMA below. No markdown, no code fences, no text before or after the JSON. "
    "Inside JSON strings use typographic quotes “ ” instead of the ASCII double quote.\n\n"
    "VOICE\n"
    "- English, spoken, fast and fun: a cool, effortless insider letting you in on a secret - confident, never cringe. Write for a cool, smoky, effortless read: short weighted phrases, suspense pauses, contrast and rhythm (\"Not Paris. Not Milan. Copenhagen.\"). "
    "Short punchy sentences. Fashion vocabulary used correctly (collection, capsule, creative director, drop, silhouette). No made-up slang overload.\n"
    "- Say names exactly as they are spelled in the article.\n\n"
    "RULES\n"
    "- voiceover: 22-26 words MAX (the 5HU voice is slow, smoky and dramatic - fewer words, more weight; use \"...\" for suspense pauses). Sentence 1 is the hook: lead with the NAME and why it matters now (e.g. “Remember this name: ...”, “Copenhagen's newest obsession...”). Say WHERE the label is from when the article says it. End with a punchy line that makes people want to follow 5HU for the next big name.\n"
    "- “One to watch” is the channel's opinion: never present future success as fact, and never invent sales, followers, stockists, celebrities or prizes.\n"
    "- ACCURACY: use ONLY facts in the article. Never invent prices, dates, names, quotes, sales figures or who wore what. If it isn't in the article, don't say it.\n"
    "- No body or weight comments about anyone. Describe clothes, not bodies.\n"
    "- scenes: exactly 4. Each = 1 VO sentence + one short on_screen_text + one visual + duration_sec. Durations sum to exactly 15.\n"
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
    "- hook: max 7 words. hashtags: 4-6, e.g. #5HU #emergingdesigners #fashion plus the label/designer and city.\n\n"
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
# English fashion text: a lone capitalised word ("Dead" from "Brain Dead") is a bad brand guess that pulls a
# random Wikipedia image. Auto-spot only multi-word names and ALL-CAPS/CamelCase brands; the script's explicit entities still work.
rep("const reSingle = /(?<!\\p{L})(\\p{Lu}\\p{Ll}{2,})(?!\\p{L})/gu;\n  while ((m = reSingle.exec(vo)))",
    "const reSingle = /(?<!\\p{L})(\\p{Lu}\\p{Ll}{2,})(?!\\p{L})/gu;\n  while (false && (m = reSingle.exec(vo)))")
# "5HU" is said "Shoo" (Slavic ШУ), never "five-H-U": the voice + alignment get a phonetic copy,
# captions map the spoken word back to "5HU". Same word count, so scene timing is unchanged.
rep("return [{ json: data }];", "data.voiceover_tts = String(data.voiceover || '').replace(/5\\s*HU/gi, 'Shoo');\nreturn [{ json: data }];")
by_name["Code in JavaScript"]["parameters"]["jsCode"] = code
for _n in ("Convert text to speech",):
    _p = by_name[_n]["parameters"]
    assert _p["text"] == "={{ $('Code in JavaScript').item.json.voiceover }}"
    _p["text"] = "={{ $('Code in JavaScript').item.json.voiceover_tts }}"
for _bp in by_name["Align"]["parameters"]["bodyParameters"]["parameters"]:
    if _bp.get("name") == "text":
        assert _bp["value"] == "={{ $('Code in JavaScript').item.json.voiceover }}"
        _bp["value"] = "={{ $('Code in JavaScript').item.json.voiceover_tts }}"
_ac = by_name["Add Captions"]["parameters"]
_old = "const captions = words.map(w => ({ text: w.text.trim(),"
assert _ac["jsCode"].count(_old) == 1
_ac["jsCode"] = _ac["jsCode"].replace(_old, "const captions = words.map(w => ({ text: w.text.trim().replace(/^shoo(?=[^A-Za-z]*$)/i, '5HU'),")

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
    {"stability": 0.4, "similarity_boost": 0.85, "style": 0.45, "use_speaker_boost": True}, indent=2)

# ---- sanity
names = [n["name"] for n in w["nodes"]]
for outs in w["connections"].values():
    for branch in outs.get("main", []):
        for c in branch or []:
            assert c["node"] in names, c
blob = json.dumps(w, ensure_ascii=False)
for gone in ("lrt.lt", "15min.lt", "lrytas", "lt_img_"):
    assert gone not in blob, gone
assert 'RSS A' not in [n['name'] for n in w['nodes']]
assert all(n["id"] != o["id"] for n in w["nodes"] for o in src["nodes"])
json.dump(w, open(DST, "w"), indent=2, ensure_ascii=False)
print(f"OK -> {DST}: {len(w['nodes'])} nodes, id={w['id']}")
