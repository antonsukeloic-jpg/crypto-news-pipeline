#!/usr/bin/env python3
"""Build the "5HU Fashion News" workflow (15 s English trending-fashion news) from the LT workflow.

Input : the LT workflow JSON (output of make_lt_workflow.py) - reuses its robust parsing
        (quote repair, selection fallback), dead-feed tolerance, caption checks and channel field.
Output: a SEPARATE workflow (own id, node ids, webhook ids), English, fashion feeds,
        "channel": "5hu", files prefixed 5hu_. Started by /run 5hu via the crypto router.

usage: make_5hu_workflow.py <lt.json> <out_5hu.json>
"""
import copy, json, os, sys, uuid

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
    // photos + full text straight from the feed (many sites block server page fetches, their RSS does not)
    const images = [];
    const pushImg = (u, alt) => { u = String(u || '').replace(/&amp;/g, '&').trim(); if (/^https?:\/\//.test(u) && !/(logo|icon|avatar|pixel|feeds\.|\.gif|\.svg|gravatar|share|button)/i.test(u) && !images.some(x => x.url.split('?')[0] === u.split('?')[0])) images.push({ url: u, alt: decode(alt || '').slice(0, 140) }); };
    for (const m of b.matchAll(/<(?:media:content|media:thumbnail|enclosure)[^>]*url="([^"]+)"[^>]*>/gi)) if (!/type="(?:audio|video)/i.test(m[0])) pushImg(m[1], '');
    const raw = String(tag(b, 'content:encoded') || tag(b, 'description') || tag(b, 'content')).replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
    for (const m of raw.matchAll(/<img[^>]*>/gi)) {
      const t = m[0], at = (a) => { const q = t.match(new RegExp('\\s' + a + '\\s*=\\s*["\']([^"\']*)["\']', 'i')); return q ? q[1] : ''; };
      let src = at('src') || at('data-src'); const ss = at('srcset');
      if (ss) { let w = 0; for (const part of ss.split(',')) { const [u, d] = part.trim().split(/\s+/); const n = parseFloat(d) || 1; if (u && n >= w) { w = n; src = u; } } }
      const wd = parseInt(at('width'), 10); if (wd && wd < 300) continue;
      pushImg(src, at('alt'));
    }
    const body = decode(raw).slice(0, 6000);
    return { source, tier, title: decode(tag(b, 'title')), link: link.trim(), snippet, date, images: images.slice(0, 12), body };
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
// 5HU = the NEXT names: drop big houses, mass retail and celebrity headlines unless the item is about a new name / prize / debut
const BIG = /\b(armani|chanel|dior|louis vuitton|vuitton|gucci|prada|herm[eè]s|saint laurent|ysl|balenciaga|valentino|versace|fendi|burberry|givenchy|bottega veneta|loewe|c[eé]line|miu miu|dolce ?(&|and) ?gabbana|moncler|kering|lvmh|richemont|tiffany|cartier|rolex|ralph lauren|calvin klein|tommy hilfiger|michael kors|alexander mcqueen|zara|h&m|uniqlo|shein|kardashian|skims|beyonc[eé]|rihanna|taylor swift|hailey bieber|kylie jenner|zendaya|met gala|vogue world)\b/i;
all = all.filter(x => !BIG.test(x.title) || rising(x));
if (!all.length) throw new Error('5HU: no fresh niche stories this slot (big names filtered out)');
const used = new Set(); const take = (arr, n) => arr.filter(x => !used.has(x.link)).slice(0, n).map(x => (used.add(x.link), x));
const pool = [].concat(
  take(shuffle(all.filter(rising)), 6),
  take(shuffle(all.filter(x => x.tier === 'emerging')), 4),
  take(shuffle(all.filter(x => x.tier === 'niche')), 3),
  take(shuffle(all.filter(x => x.tier === 'main' && rising(x))), 2));
const candidates = shuffle(pool.length ? pool : all.slice(0, 12));
const candidatesText = candidates.map((x, i) => (i + 1) + '. [' + x.source + (x.tier !== 'main' ? ', ' + x.tier : '') + (rising(x) ? ', RISING' : '') + '] ' + x.title + '\n   ' + x.snippet + '\n   LINK: ' + x.link).join('\n\n');
const recentHooks = (_st.hooks5hu || []).slice(0, 12).map(h => '- ' + h).join('\n') || '(none yet)';
return [{ json: { candidates, candidatesText, feedsRead: ok, recentHooks } }];""")

ps = by_name["Parse Selection"]["parameters"]
old = "return [{ json: { link: sel.link,"
assert ps["jsCode"].count(old) == 1
ps["jsCode"] = ps["jsCode"].replace(old,
    "const _st = $getWorkflowStaticData('global'); _st.seen5hu = [sel.link].concat(_st.seen5hu || []).slice(0, 500);\n" + old)

# ---- editor: "who's next" fashion
by_name["Select Story"]["parameters"]["messages"]["values"][0]["content"] = (
    "=You are the editor of 5HU, the channel that spots fashion's NEXT big names before everyone else - "
    "TikTok/Reels/Shorts for a young, style-obsessed global audience. Choose the SINGLE best story from the candidates for a 20-30 second video.\n\n"
    "5HU'S IDENTITY - pick in this order:\n"
    "1. A rising independent label or young designer (roughly the last 10 years) from a scene with buzz - Copenhagen, Stockholm, Oslo, Helsinki, "
    "London, New York, Paris, Berlin, Tokyo, Seoul, Antwerp, Milan, Lagos, Mexico City... Signals: debut show or first fashion-week slot, "
    "prize shortlist (LVMH Prize, ANDAM, Woolmark, NEWGEN, Fashion East), first store or big stockist, a celebrity or stylist picking them up, "
    "a breakout collab, a designer from a small label getting a bigger job.\n"
    "2. A cult / boutique brand doing something new (drop, collab, archive revival, new direction).\n"
    "3. A new micro-trend or scene with a clear name and concrete examples.\n"
    "4. If nothing above exists: a smaller independent or streetwear brand story from a niche source.\n"
    "NEVER pick a big luxury house or conglomerate (Louis Vuitton, Chanel, Dior, Gucci, Armani, Prada, LVMH, Kering...), a mass retailer, or a celebrity story - 5HU is about the next names, not the established ones. A famous house is OK only when the story is really about a NEW young designer (e.g. a debut as creative director).\n"
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
    "=You are the scriptwriter for 5HU - the channel that spots fashion's next big names first (TikTok/Reels/Shorts). Turn ONE fashion news article into a 20-30 second vertical video plan.\n\n"
    "Output ONLY valid JSON matching the SCHEMA below. No markdown, no code fences, no text before or after the JSON. "
    "Inside JSON strings use typographic quotes “ ” instead of the ASCII double quote.\n\n"
    "VOICE\n"
    "- English, spoken, fast and fun: a cool, effortless insider letting you in on a secret - confident, never cringe. Write for a cool, smoky, effortless read: short weighted phrases, suspense pauses, contrast and rhythm (\"Not Paris. Not Milan. Copenhagen.\"). "
    "Short punchy sentences. Fashion vocabulary used correctly (collection, capsule, creative director, drop, silhouette). No made-up slang overload.\n"
    "- Say names exactly as they are spelled in the article.\n"
    "- SIGNATURE FLAVOUR (owner loves it): English with a little French chic. Keep fashion words, events and names in their original language with their accents so the voice says them natively - Première Vision, haute couture, prêt-à-porter, savoir-faire, atelier, aubergine, maison, défilé, je ne sais quoi, Japanese/Italian/Scandinavian names as written. One or two such words per video, woven naturally into the English, never forced or translated.\n\n"
    "RULES\n"
    "- ONE idea, told deeper - not a list of facts. Pick the single most interesting angle of the story (who they are, what is new, why it matters NOW) and build the 20-30 s around it. Never stack names, dates and numbers one after another.\n"
    "- voiceover: 32-40 words. HARD LIMIT: count the words before answering; if more than 42, rewrite shorter. 5 short sentences, one per scene, so the voice can breathe between them (the 5HU voice is slow, smoky and dramatic - fewer words, more weight; use \"...\" for suspense pauses). Sentence 1 is the hook and must be FRESH every time: NEVER open with “Remember this name”. Rotate opening styles - a bold claim, a question, a contrast (“Not Paris. Not Milan...”), a scene you can see, a striking number, a direct dare to the viewer. Do not reuse any of these recent openings or their pattern:\n{{ $('Combine Feeds').first().json.recentHooks }}\nSay WHERE the label is from when the article says it. End with a punchy closing line (the channel sign-off is added after it automatically).\n"
    "- NEVER say the channel name 5HU anywhere in the voiceover or vo_segment - the sign-off \"Follow 5HU. We find them first.\" is added automatically at the very end.\n"
    "- “One to watch” is the channel's opinion: never present future success as fact, and never invent sales, followers, stockists, celebrities or prizes.\n"
    "- ACCURACY: use ONLY facts in the article. Never invent prices, dates, names, quotes, sales figures or who wore what. If it isn't in the article, don't say it.\n"
    "- No body or weight comments about anyone. Describe clothes, not bodies.\n"
    "- scenes: exactly 5. Each = 1 VO sentence + one short on_screen_text + one visual + duration_sec. Durations sum to 25 (the video follows the voice, 20-30 s).\n"
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
rep('channel:"5hu",', 'channel:"5hu", music:"assets/"+data.musicFile, bpm:data.musicBpm,')
rep('data.voiceFile = "5hu_voice_"+ts', 'data.musicFile = "5hu_music_"+ts+".mp3";\ndata.musicBpm = [120, 122, 124, 126, 128][Math.floor(Math.random() * 5)];\ndata.voiceFile = "5hu_voice_"+ts')
rep("return (await wikiImage(title, 'lt')) || (await wikiImage(title, 'en'));", "return (await wikiImage(title, 'en')) || (await wikiImage(title, 'lt'));")
rep("return (await companyLogo(title, 'lt')) || (await companyLogo(title, 'en'));", "return (await companyLogo(title, 'en')) || (await companyLogo(title, 'lt'));")
# English fashion text: a lone capitalised word ("Dead" from "Brain Dead") is a bad brand guess that pulls a
# random Wikipedia image. Auto-spot only multi-word names and ALL-CAPS/CamelCase brands; the script's explicit entities still work.
rep("const reSingle = /(?<!\\p{L})(\\p{Lu}\\p{Ll}{2,})(?!\\p{L})/gu;\n  while ((m = reSingle.exec(vo)))",
    "const reSingle = /(?<!\\p{L})(\\p{Lu}\\p{Ll}{2,})(?!\\p{L})/gu;\n  while (false && (m = reSingle.exec(vo)))")
# "5HU" is said "Šū" (owner picked sample K: the whole 5HU sentence "[softly] [Lithuanian] … Šū. [English]"), never "five-H-U": the voice + alignment get a phonetic copy,
# captions map the spoken word back to "5HU". Same word count, so scene timing is unchanged.
# Sign-off: the body never says 5HU; the video always ends "Follow 5HU. We find them first." over the dark outro.
# SIGNOFF_TTS is what the voice reads (5HU = Lithuanian "Šū"); alignment reads the plain English copy.
# the sign-off is a fixed recorded clip (remotion/music/5hu_signoff.mp3, owner-picked take), played by the renderer
rep("return [{ json: data }];", "const _no5 = t => (String(t || '').match(/[^.!?…]+[.!?…]*/g) || []).map(x => x.trim()).filter(x => x && !/5\\s*HU|\\bShoo\\b|Šū|find them first/i.test(x)).join(' ');\n"
    "const _body = _no5(data.voiceover);\n"
    "data.voiceover = _body.trim();\n"
    "(data.scenes || []).forEach(sc => { sc.vo_segment = _no5(sc.vo_segment); });\n"
    "const _sh = $getWorkflowStaticData('global'); _sh.hooks5hu = [String(data.voiceover || '').split(/[.!?…]/)[0].trim()].concat(_sh.hooks5hu || []).slice(0, 12);\n"
    "data.voiceover_align = String(data.voiceover || '').replace(/5\\s*HU/gi, 'Shoo');\n"
    "data.voiceover_tts = (_body.match(/[^.!?…]+[.!?…]*/g) || [_body]).map(x => x.trim()).filter(Boolean).join(' [pause] ');\n"
    "try { const _j = JSON.parse(data.job_json); _j.signoff = true; _j.voiceover = data.voiceover; data.job_json = JSON.stringify(_j); } catch (e) {}\n"
    "return [{ json: data }];")
# 20-30 s videos: up to 6 scenes, 25 s script total (the render follows the voice length)
rep("const TOTAL = 15;", "const TOTAL = 25;")
rep("data.scenes.slice(0, 4)", "data.scenes.slice(0, 6)")
by_name["Code in JavaScript"]["parameters"]["jsCode"] = code
for _n in ("Convert text to speech",):
    _p = by_name[_n]["parameters"]
    assert _p["text"] == "={{ $('Code in JavaScript').item.json.voiceover }}"
    _p["text"] = "={{ $('Code in JavaScript').item.json.voiceover_tts }}"
for _bp in by_name["Align"]["parameters"]["bodyParameters"]["parameters"]:
    if _bp.get("name") == "text":
        assert _bp["value"] == "={{ $('Code in JavaScript').item.json.voiceover }}"
        _bp["value"] = "={{ $('Code in JavaScript').item.json.voiceover_align }}"
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
    'no real brand logos. Tall vertical portrait-orientation photo shot upright: the horizon and floor are horizontal, people and clothes stand upright, never rotated or sideways. Raw urban street energy: flash photography, film grain, concrete, night streets. No text, no numbers, no watermark.";') + ss["jsCode"][i1:]

# ---- voice
tts = by_name["Convert text to speech"]["parameters"]
tts["voice"] = {"__rl": True, "mode": "id", "value": VOICE_ID}
tts["additionalOptions"]["model"] = {"__rl": True, "value": MODEL, "mode": "list", "cachedResultName": "Eleven v4"}
tts["additionalOptions"]["voiceSettings"] = json.dumps(
    {"stability": 0.4, "similarity_boost": 0.85, "style": 0.45, "use_speaker_boost": True}, indent=2)

# ---- fresh techno for every video (never the same track): ElevenLabs Sound Effects, random style + BPM
MUSIC_JS = r"""
const STYLES = [
  'groovy minimal techno, rolling bassline, swung hi-hats, soft rounded kick, playful clicks',
  'groovy deep tech house, bouncy bass, shuffled hats, warm chords, light kick',
  'groovy Parisian French-touch house techno, filtered disco chords, funky bass, soft four-on-the-floor',
  'groovy melodic techno, warm arpeggio riding a funky bassline, smooth kick',
  'groovy minimal house, chopped vocal-free stabs, rubbery bass, light claps',
  'groovy electro techno, bouncy synth bass, soft claps, cheeky percussion',
  'groovy Detroit techno, mellow analog chord stabs, swung groove, steady soft kick',
  'groovy lo-fi house techno, dusty drums, warm bass, dreamy pad',
  'groovy hypnotic techno, gentle acid line in the groove, light kick, swing',
  'groovy organic techno, conga percussion, plucked synth, warm rolling bass',
];
const KEYS = ['A minor', 'F minor', 'D minor', 'G minor', 'C minor', 'E minor'];
const BPMS = [120, 122, 124, 126, 128];
const pick = (a) => a[Math.floor(Math.random() * a.length)];
const style = pick(STYLES), key = pick(KEYS);
const bpm = $('Code in JavaScript').first().json.musicBpm || pick(BPMS);
const text = style + ', ' + bpm + ' BPM, in ' + key + ', light and airy, soft kick, not aggressive, four-on-the-floor, instrumental, no vocals, no speech, chic fashion runway mood, seamless loop';
return [{ json: { text, bpm, style } }];
"""
_cx, _cy = by_name["Save Voice"]["position"]
w["nodes"] += [
    {"parameters": {"jsCode": MUSIC_JS}, "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [_cx + 220, _cy], "id": str(uuid.uuid4()), "name": "Music - Pick Style"},
    {"parameters": {
        "method": "POST", "url": "https://api.elevenlabs.io/v1/sound-generation",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ text: $json.text, duration_seconds: 30, prompt_influence: 0.6, loop: true, model_id: 'eleven_text_to_sound_v2' }) }}",
        "options": {"response": {"response": {"responseFormat": "file"}}, "timeout": 90000}},
     "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.4, "position": [_cx + 440, _cy],
     "id": str(uuid.uuid4()), "name": "Music - Generate",
     "credentials": by_name["Align"]["credentials"], "onError": "continueRegularOutput",
     "retryOnFail": True, "maxTries": 2, "waitBetweenTries": 2000},
    {"parameters": {"operation": "write",
                    "fileName": "=/data/shared/assets/{{ $('Code in JavaScript').first().json.musicFile }}",
                    "dataPropertyName": "data", "options": {}},
     "type": "n8n-nodes-base.readWriteFile", "typeVersion": 1, "position": [_cx + 660, _cy],
     "id": str(uuid.uuid4()), "name": "Save Music", "onError": "continueRegularOutput"},
]
w["connections"]["Save Voice"] = {"main": [[{"node": "Music - Pick Style", "type": "main", "index": 0}]]}
w["connections"]["Music - Pick Style"] = {"main": [[{"node": "Music - Generate", "type": "main", "index": 0}]]}
w["connections"]["Music - Generate"] = {"main": [[{"node": "Save Music", "type": "main", "index": 0}]]}
w["connections"]["Save Music"] = {"main": [[{"node": "Split Scenes", "type": "main", "index": 0}]]}

# ---- creators: the designer's / label's own accounts (Instagram, TikTok, website) for @-tags, first comment and links.
# Perplexity web search; a handle is kept only when its profile URL is in the retrieved results (n8n/js/5hu_creators.js).
_cq = ("={{ JSON.stringify({ preset: 'fast', input: 'Use web search now. This fashion story is about one or two designers / labels. '"
       " + 'Find their OFFICIAL accounts. Story: ' + $('Parse Selection').first().json.title + '. Script: ' + "
       "String((() => { try { return JSON.parse($('Add Captions').first().json.job_json).voiceover; } catch (e) { return ''; } })()).slice(0, 600) + "
       "' Reply ONLY with JSON: {\"creators\":[{\"name\":\"\",\"role\":\"designer|label\",\"instagram\":\"handle\",\"tiktok\":\"handle\",\"website\":\"https://...\"}]}. '"
       " + 'Only accounts you actually saw in the search results (the official site linking to it, or the profile page itself). If unsure, leave the field empty. Never guess.' }) }}")
_sm = by_name["Save Music"]["position"] if "Save Music" in by_name else [0, 0]
w["nodes"] += [
    {"parameters": {"method": "POST", "url": "https://api.perplexity.ai/v1/agent", "authentication": "predefinedCredentialType",
                    "nodeCredentialType": "perplexityApi", "sendBody": True, "specifyBody": "json", "jsonBody": _cq,
                    "options": {"timeout": 60000, "response": {"response": {"neverError": True}}}},
     "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [_sm[0] + 110, _sm[1] + 180], "id": str(uuid.uuid4()),
     "name": "Creator Lookup", "onError": "continueRegularOutput", "alwaysOutputData": True, "executeOnce": True,
     "credentials": {"perplexityApi": {"id": "0F59WAwddf4rDMK4", "name": "Perplexity account"}}},
    {"parameters": {"jsCode": open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "js", "5hu_creators.js")).read()},
     "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [_sm[0] + 330, _sm[1] + 180], "id": str(uuid.uuid4()),
     "name": "Creators", "onError": "continueRegularOutput", "alwaysOutputData": True},
]
w["connections"]["Save Music"] = {"main": [[{"node": "Creator Lookup", "type": "main", "index": 0}]]}
w["connections"]["Creator Lookup"] = {"main": [[{"node": "Creators", "type": "main", "index": 0}]]}
w["connections"]["Creators"] = {"main": [[{"node": "Split Scenes", "type": "main", "index": 0}]]}
# the job file carries the creators to the render watcher -> publish
by_name["Make Job File"]["parameters"]["jsCode"] = (
    "let txt = $('Add Captions').first().json.job_json;\n"
    "try { const j = JSON.parse(txt); const cr = ($('Creators').first().json.creators) || []; if (cr.length) { j.creators = cr; txt = JSON.stringify(j); } } catch (e) {}\n"
    "const name = $('Code in JavaScript').first().json.jobFile;\n"
    "const bin = await this.helpers.prepareBinaryData(Buffer.from(txt, 'utf8'), name, 'application/json');\n"
    "return [{ json: { jobFile: name }, binary: { data: bin } }];")

# ---- speed: poll Higgsfield every 3 s instead of 10 s (images are ready in ~10 s)
assert by_name["Wait"]["parameters"].get("amount") == 10
by_name["Wait"]["parameters"]["amount"] = 3

# ---- cost: Soul 2 ($0.0057/img at 1080p) instead of Soul Standard ($0.0938 at 720p)
_req = by_name["Image - Request"]["parameters"]
assert _req["url"].endswith("/higgsfield-ai/soul/standard")
_req["url"] = _req["url"].replace("/soul/standard", "/soul/v2/standard")
for _p in _req["bodyParameters"]["parameters"]:
    if _p["name"] == "resolution":
        _p["value"] = "1080p"
    if _p["name"] == "aspect_ratio":
        _p["value"] = "3:4"

# ---- REAL photos: a story about a designer must show the real designer and the real collection.
# Article Photos pulls og:image + article/figure images from the fetched page; the script assigns them to scenes
# ("photo": n); scenes without one fall back to a Soul 2 mood shot. A failed download also falls back to Soul 2.
_photos_js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "js", "5hu_article_photos.js")).read()
_h = by_name["HTML"]
w["nodes"].append({"parameters": {"jsCode": _photos_js}, "type": "n8n-nodes-base.code", "typeVersion": 2,
    "position": [_h["position"][0] + 110, _h["position"][1] + 160], "id": str(uuid.uuid4()), "name": "Article Photos"})
w["connections"]["HTML"] = {"main": [[{"node": "Article Photos", "type": "main", "index": 0}]]}
# Perplexity Agent API image_search: real designer portrait + collection looks from the whole web (~$0.005/run).
# Uses the n8n "Perplexity account" credential (key never in the repo). Failures just leave the article/RSS photos.
_pq = ("={{ JSON.stringify({ preset: 'fast', input: 'Use the image_search tool now - call it and do not answer from memory. Find: "
       "1) a portrait photo of the designer / founder / creative director (the person), 2) runway, lookbook or campaign photos of the collection or pieces, "
       "3) the label logo. Story: ' + $('Parse Selection').first().json.title + ' - ' + "
       "((($('Combine Feeds').first().json.candidates || []).find(c => c.link === $('Parse Selection').first().json.link) || {}).snippet || '').slice(0, 300) + ' Reply only with done.', "
       "tools: [{ type: 'image_search', max_results: 16, filters: { domain_filter: ['-gettyimages.com', '-shutterstock.com', '-alamy.com', '-pinterest.com', '-istockphoto.com', '-dreamstime.com'], format_filter: ['jpeg', 'png', 'webp'] } }] }) }}")
_ap = by_name["HTML"]["position"]
w["nodes"] += [
    {"parameters": {"method": "POST", "url": "https://api.perplexity.ai/v1/agent", "authentication": "predefinedCredentialType",
                    "nodeCredentialType": "perplexityApi", "sendBody": True, "specifyBody": "json", "jsonBody": _pq,
                    "options": {"timeout": 60000, "response": {"response": {"neverError": True}}}},
     "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [_ap[0] + 330, _ap[1] + 160], "id": str(uuid.uuid4()),
     "name": "Perplexity Photos", "onError": "continueRegularOutput", "alwaysOutputData": True,
     "credentials": {"perplexityApi": {"id": "0F59WAwddf4rDMK4", "name": "Perplexity account"}}},
    {"parameters": {"jsCode": open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "js", "5hu_merge_photos.js")).read()},
     "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [_ap[0] + 550, _ap[1] + 160], "id": str(uuid.uuid4()), "name": "Merge Photos"},
]
w["connections"]["Article Photos"] = {"main": [[{"node": "Perplexity Photos", "type": "main", "index": 0}]]}
w["connections"]["Perplexity Photos"] = {"main": [[{"node": "Merge Photos", "type": "main", "index": 0}]]}
w["connections"]["Merge Photos"] = {"main": [[{"node": "Message a model", "type": "main", "index": 0}]]}

_msgs = by_name["Message a model"]["parameters"]["messages"]["values"]
_n_art = 0
for _m in _msgs:
    c = _m.get("content", "")
    if "\n\nARTICLE\n{{" in c:
        c = c.replace("\n\nARTICLE\n{{", "\n\nREAL PHOTOS FROM THE ARTICLE (numbered)\n{{ $json.photosText }}\n\nARTICLE\n{{")
        _n_art += 1
    c = c.replace('"visual":{"query":"..."}', '"photo":1,"visual":{"query":"..."}')
    if '- “One to watch” is the channel' in c:
        c = c.replace('"- “One to watch” is the channel'.lstrip('"'),
            "- THE DESIGNER: one of the first two scenes MUST show the designer as a person - give it the real photo whose caption names or shows them "
            "(portrait, studio or backstage shot). If no real photo shows them, give that scene center {\"type\":\"entity\",\"kind\":\"person\",\"name\":\"<designer>\",\"wiki\":\"<designer>\"}.\n"
            "- LOGO: at least one scene MUST have center {\"type\":\"entity\",\"kind\":\"company\",\"name\":\"<label name exactly as written>\",\"wiki\":\"<Wikipedia title, or the label name>\"} for the label the story is about.\n"
            "- REAL PHOTOS: this is news about REAL designers and REAL collections - show the real person and the real pieces, never an invented collection. "
            "For each scene set \"photo\" to the number of the REAL PHOTO that best matches the sentence (the designer's portrait when you introduce them, "
            "looks / garments / campaign shots when you describe the collection). Use each photo once. Set \"photo\": 0 only when no real photo is left; "
            "then visual.query must be a mood shot (the city, a studio, fabric close-up, a rail in shadow) - never a full invented outfit or collection.\n"
            "- “One to watch” is the channel", 1)
    _m["content"] = c
assert _n_art == 1, _n_art

_code = by_name["Code in JavaScript"]["parameters"]
_anchor = 'scenes.forEach(function(s,i){ s.imageFile = '
assert _code["jsCode"].count(_anchor) == 1
_code["jsCode"] = _code["jsCode"].replace(_anchor,
    "const _ph = (() => { try { return $('Merge Photos').first().json.photos || []; } catch (e) { return []; } })();\n"
    "const _used = new Set();\n"
    "scenes.forEach(s => { const n = parseInt(s.photo, 10); if (n >= 1 && n <= _ph.length && !_used.has(n)) { _used.add(n); s.photo_url = _ph[n - 1].url; s.photo_site = _ph[n - 1].site || ''; } });\n"
    "scenes.forEach(s => { if (!s.photo_url) { const q = _ph.find(x => !_used.has(x.n)); if (q) { _used.add(q.n); s.photo_url = q.url; s.photo_site = q.site || ''; } } });\n"
    "const _src = (($('Combine Feeds').first().json.candidates || []).find(c => c.link === $('Parse Selection').first().json.link) || {}).source || '';\n"
    + _anchor)
_old = 'vo_segment: s.vo_segment || ""};'
assert _code["jsCode"].count(_old) == 1
_code["jsCode"] = _code["jsCode"].replace(_old, 'vo_segment: s.vo_segment || "", real: !!s.photo_url, credit: s.photo_url ? (s.photo_site || _src) : ""};')

_ir = by_name["Image - Request"]
for _bp in _ir["parameters"]["bodyParameters"]["parameters"]:
    if _bp["name"] == "prompt":
        _bp["value"] = "={{ $('Split Scenes').item.json.image_prompt }}"
_x, _y = _ir["position"]
w["nodes"] += [
    {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
        "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.photo_url || '' }}", "rightValue": "",
                        "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}], "combinator": "and"}, "options": {}},
     "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [_x - 220, _y], "id": str(uuid.uuid4()), "name": "Real Photo?"},
    {"parameters": {"url": "={{ $json.photo_url }}", "sendHeaders": True, "headerParameters": {"parameters": [
        {"name": "User-Agent", "value": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"},
        {"name": "Accept", "value": "image/avif,image/webp,image/png,image/jpeg,*/*"}]},
        "options": {"timeout": 20000, "response": {"response": {"responseFormat": "file"}}}},
     "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [_x, _y - 220], "id": str(uuid.uuid4()),
     "name": "Photo - Download", "onError": "continueErrorOutput"},
]
w["connections"]["Split Scenes"] = {"main": [[{"node": "Real Photo?", "type": "main", "index": 0}]]}
w["connections"]["Real Photo?"] = {"main": [[{"node": "Photo - Download", "type": "main", "index": 0}],
                                            [{"node": "Image - Request", "type": "main", "index": 0}]]}
w["connections"]["Photo - Download"] = {"main": [[{"node": "Save Image", "type": "main", "index": 0}],
                                                 [{"node": "Image - Request", "type": "main", "index": 0}]]}

# no Wikipedia logo for a niche label -> keep the card, the renderer draws the label name as a wordmark
_old = "else { _wiki_dbg.push('entDROP:' + title); _s.center = { type: 'none' }; c = _s.center; }"
assert _code["jsCode"].count(_old) == 1
_code["jsCode"] = _code["jsCode"].replace(_old, "else if (!isPerson && c.name) { _wiki_dbg.push('entWORD:' + title); } " + _old)

# network hiccups must not kill a run: a blocked article page falls back to the RSS text/photos; API calls retry
by_name["Article - Fetch"].update({"onError": "continueRegularOutput", "alwaysOutputData": True, "retryOnFail": True, "maxTries": 2, "waitBetweenTries": 2000})
by_name["Article - Fetch"]["parameters"].setdefault("options", {})["timeout"] = 20000
for _n in w["nodes"]:
    if _n["name"] in ("Select Story", "Message a model", "Perplexity Photos", "Image - Request", "Image - Get", "Music - Generate"):
        _n.update({"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 3000})

# ---- schedule (owner 2026-11-20): automatic 5HU video twice a day, 09:00 and 19:00 Vilnius time.
# The watcher then auto-posts it via Social Publish (kill switch: rm /root/stack/autopost_5hu).
_sch = by_name["Every Hour"]
_sch.pop("disabled", None)
_sch["name"] = "Every Hour"  # keep the name: connections reference it
_sch["parameters"] = {"rule": {"interval": [{"field": "cronExpression", "expression": "20 8,18 * * *"}]}}
w.setdefault("settings", {})["timezone"] = "Europe/Vilnius"

# ---- sanity
names =[n["name"] for n in w["nodes"]]
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
