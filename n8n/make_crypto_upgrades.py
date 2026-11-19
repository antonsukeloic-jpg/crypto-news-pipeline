#!/usr/bin/env python3
"""Crypto-only upgrades, applied AFTER make_vps_workflow.py (LT / Vikops / 5HU are built from the un-upgraded base,
so they are not affected).

    python3 make_crypto_upgrades.py <crypto_wf_in.json> <crypto_wf_out.json>

What it adds (lessons from 5HU, 2026-11-19):
  1. Images: Higgsfield Soul 2 at 1080p, 3:4 (Soul Standard 720p cost ~16x more; 9:16 sometimes renders sideways).
  2. Retries on every paid API call; a failed article fetch falls back to the RSS text.
  3. RSS items carry their full text + images (many news sites block server page fetches).
  4. Perplexity fact-check (Agent API + web_search) of every name / number / date in the script before the voice.
  5. Perplexity image_search + article/RSS photos: real people / company / logo photos where the script asks for them;
     everything else stays an AI image.
  (Loudness -14 LUFS is done in remotion/render_vps.sh.)
"""
import json, os, sys, uuid

src, dst = sys.argv[1], sys.argv[2]
w = json.load(open(src))
by_name = {n["name"]: n for n in w["nodes"]}
HERE = os.path.dirname(os.path.abspath(__file__))
PPLX_CRED = {"perplexityApi": {"id": "0F59WAwddf4rDMK4", "name": "Perplexity account"}}


def node(name, ntype, params, pos, ver=2, **extra):
    n = {"parameters": params, "type": ntype, "typeVersion": ver, "position": pos, "id": str(uuid.uuid4()), "name": name}
    n.update(extra)
    w["nodes"].append(n)
    by_name[name] = n
    return n


def link(a, b, out=0):
    w["connections"].setdefault(a, {"main": []})
    m = w["connections"][a]["main"]
    while len(m) <= out:
        m.append([])
    m[out] = [{"node": b, "type": "main", "index": 0}]


# ---- 1. Soul 2, 1080p, 3:4
req = by_name["Image - Request"]["parameters"]
assert req["url"].endswith("/higgsfield-ai/soul/standard"), req["url"]
req["url"] = req["url"].replace("/soul/standard", "/soul/v2/standard")
for p in req["bodyParameters"]["parameters"]:
    if p["name"] == "resolution":
        p["value"] = "1080p"
    if p["name"] == "aspect_ratio":
        p["value"] = "3:4"
    if p["name"] == "prompt":
        p["value"] = "={{ $('Split Scenes').item.json.image_prompt }}"
ss = by_name["Split Scenes"]["parameters"]
assert "Vertical 9:16." in ss["jsCode"]
ss["jsCode"] = ss["jsCode"].replace("Vertical 9:16.", "Tall vertical portrait-orientation photo shot upright: horizon and floor horizontal, never rotated or sideways.")

# ---- 2. retries
for n in w["nodes"]:
    if n["name"] in ("Select Story", "Message a model", "Image - Request", "Image - Get", "Image - Download", "Convert text to speech"):
        n.update({"retryOnFail": True, "maxTries": 3, "waitBetweenTries": 3000})
by_name["Article - Fetch"].update({"onError": "continueRegularOutput", "alwaysOutputData": True})
by_name["Article - Fetch"]["parameters"].setdefault("options", {})["timeout"] = 20000

# ---- 3. RSS full text + images
cf = by_name["Combine Feeds"]["parameters"]
old = "date:it.isoDate||it.pubDate||''}); }); }"
assert cf["jsCode"].count(old) == 1
cf["jsCode"] = cf["jsCode"].replace(old, (
    "date:it.isoDate||it.pubDate||'', body:(it['content:encoded']||it.content||'').toString().replace(/<[^>]+>/g,' ').replace(/\\s+/g,' ').trim().slice(0,6000), "
    "images:(function(){ const out=[]; const add=(u,alt)=>{ u=String(u||'').replace(/&amp;/g,'&'); if(/^https?:\\/\\//.test(u) && !/(logo|icon|avatar|pixel|\\.gif|\\.svg|gravatar)/i.test(u) && !out.some(x=>x.url.split('?')[0]===u.split('?')[0])) out.push({url:u,alt:String(alt||'').slice(0,140)}); }; "
    "if(it.enclosure&&it.enclosure.url&&!/audio|video/.test(it.enclosure.type||'')) add(it.enclosure.url,''); "
    "for(const m of String(it['content:encoded']||it.content||'').matchAll(/<img[^>]*>/gi)){ const t=m[0]; const s=(t.match(/\\ssrc=[\"']([^\"']+)/i)||[])[1]; const a=(t.match(/\\salt=[\"']([^\"']*)/i)||[])[1]; add(s,a); } "
    "return out.slice(0,8); })()}); }); }"))

msg = by_name["Message a model"]["parameters"]["messages"]["values"][-1]
old_art = "('HEADLINE: ' + $('Parse Selection').first().json.title + '\\nSUMMARY: ' + (($('Combine Feeds').first().json.candidates || []).find(c => c.link === $('Parse Selection').first().json.link) || {}).snippet)"
assert msg["content"].count(old_art) == 1
msg["content"] = msg["content"].replace(old_art,
    "((($('Combine Feeds').first().json.candidates || []).find(c => c.link === $('Parse Selection').first().json.link) || {}).body || "
    "('HEADLINE: ' + $('Parse Selection').first().json.title + '\\nSUMMARY: ' + (($('Combine Feeds').first().json.candidates || []).find(c => c.link === $('Parse Selection').first().json.link) || {}).snippet))")

# ---- 5a. photos: Article Photos (page + RSS) -> Perplexity image_search -> Merge Photos -> script
assert msg["content"].count("\n\nARTICLE\n{{") == 1
msg["content"] = msg["content"].replace("\n\nARTICLE\n{{",
    "\n\nREAL PHOTOS (numbered - real photos found for this story)\n{{ $json.photosText }}\n\nARTICLE\n{{")
msg["content"] = msg["content"].replace('"visual":{"query":"..."}', '"photo":0,"visual":{"query":"..."}')
RULE = ("- photo: per scene, the number of a REAL PHOTO only when it clearly shows the exact person, company, building, product or logo that "
        "sentence is about (e.g. the CEO named, the exchange's logo). Use each photo once. Otherwise 0 - then visual.query makes an AI image. "
        "Never pick a generic stock photo of coins or charts.\n")
anchor = "- center: per scene"
assert msg["content"].count(anchor) == 1
msg["content"] = msg["content"].replace(anchor, RULE + anchor)

hx, hy = by_name["HTML"]["position"]
node("Article Photos", "n8n-nodes-base.code", {"jsCode": open(os.path.join(HERE, "js", "5hu_article_photos.js")).read()}, [hx + 110, hy + 160])
PQ = ("={{ JSON.stringify({ preset: 'fast', input: 'Use the image_search tool now - call it and do not answer from memory. Find real photos for this crypto news story: "
      "portraits of the people named (CEOs, founders, officials), the companies / exchanges / projects involved and their logos. No generic stock coins. Story: ' + "
      "$('Parse Selection').first().json.title + ' - ' + ((($('Combine Feeds').first().json.candidates || []).find(c => c.link === $('Parse Selection').first().json.link) || {}).snippet || '').slice(0, 300) + ' Reply only with done.', "
      "tools: [{ type: 'image_search', max_results: 12, filters: { domain_filter: ['-gettyimages.com', '-shutterstock.com', '-alamy.com', '-pinterest.com', '-istockphoto.com', '-dreamstime.com', '-freepik.com'], format_filter: ['jpeg', 'png', 'webp'] } }] }) }}")
node("Perplexity Photos", "n8n-nodes-base.httpRequest",
     {"method": "POST", "url": "https://api.perplexity.ai/v1/agent", "authentication": "predefinedCredentialType", "nodeCredentialType": "perplexityApi",
      "sendBody": True, "specifyBody": "json", "jsonBody": PQ, "options": {"timeout": 60000, "response": {"response": {"neverError": True}}}},
     [hx + 330, hy + 160], ver=4.2, onError="continueRegularOutput", alwaysOutputData=True, retryOnFail=True, maxTries=2, waitBetweenTries=3000, credentials=PPLX_CRED)
node("Merge Photos", "n8n-nodes-base.code", {"jsCode": open(os.path.join(HERE, "js", "5hu_merge_photos.js")).read()}, [hx + 550, hy + 160])
link("HTML", "Article Photos"); link("Article Photos", "Perplexity Photos"); link("Perplexity Photos", "Merge Photos")

# ---- 4. Perplexity fact-check between the script and everything downstream (fail-safe: original script on any problem)
mx, my = by_name["Message a model"]["position"]
FQ = ("={{ JSON.stringify({ preset: 'fast', input: 'You are a fact-checker for a crypto news video. Use web search to verify every name, number, price, percentage, "
      "date and claim in the SCRIPT against the ARTICLE and current reliable sources. Fix ONLY facts that are wrong (keep the wording, length and JSON structure "
      "exactly; change nothing else; if a claim cannot be verified but is in the article, keep it). Reply with ONLY this JSON, no markdown: "
      "{\"ok\": true|false, \"fixes\": [{\"wrong\": \"exact text in script\", \"right\": \"replacement\", \"why\": \"short reason\"}]}. "
      "ARTICLE: ' + String($('Merge Photos').first().json.articleText || '').slice(0, 3500) + ' SCRIPT: ' + $json.content[0].text }) }}")
node("Fact Check", "n8n-nodes-base.httpRequest",
     {"method": "POST", "url": "https://api.perplexity.ai/v1/agent", "authentication": "predefinedCredentialType", "nodeCredentialType": "perplexityApi",
      "sendBody": True, "specifyBody": "json", "jsonBody": FQ, "options": {"timeout": 90000, "response": {"response": {"neverError": True}}}},
     [mx + 200, my + 200], ver=4.2, onError="continueRegularOutput", alwaysOutputData=True, retryOnFail=True, maxTries=2, waitBetweenTries=3000, credentials=PPLX_CRED)
node("Apply Fact Check", "n8n-nodes-base.code", {"jsCode": open(os.path.join(HERE, "js", "crypto_apply_factcheck.js")).read()}, [mx + 420, my + 200])
link("Merge Photos", "Message a model")
link("Message a model", "Fact Check"); link("Fact Check", "Apply Fact Check"); link("Apply Fact Check", "Code in JavaScript")

# ---- 5b. scenes with a real photo download it instead of generating; download failure -> AI image
code = by_name["Code in JavaScript"]["parameters"]
a = "scenes.forEach(function(s,i){ s.imageFile = "
assert code["jsCode"].count(a) == 1
code["jsCode"] = code["jsCode"].replace(a,
    "const _ph = (() => { try { return $('Merge Photos').first().json.photos || []; } catch (e) { return []; } })();\n"
    "const _used = new Set();\n"
    "scenes.forEach(s => { const n = parseInt(s.photo, 10); if (n >= 1 && n <= _ph.length && !_used.has(n)) { _used.add(n); s.photo_url = _ph[n - 1].url; } });\n" + a)
ix, iy = by_name["Image - Request"]["position"]
node("Real Photo?", "n8n-nodes-base.if",
     {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                     "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.photo_url || '' }}", "rightValue": "",
                                     "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}], "combinator": "and"}, "options": {}},
     [ix - 220, iy], ver=2.2)
node("Photo - Download", "n8n-nodes-base.httpRequest",
     {"url": "={{ $json.photo_url }}", "sendHeaders": True, "headerParameters": {"parameters": [
         {"name": "User-Agent", "value": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"},
         {"name": "Accept", "value": "image/avif,image/webp,image/png,image/jpeg,*/*"}]},
      "options": {"timeout": 20000, "response": {"response": {"responseFormat": "file"}}}},
     [ix, iy - 220], ver=4.2, onError="continueErrorOutput")
link("Split Scenes", "Real Photo?")
link("Real Photo?", "Image - Request", 1); link("Real Photo?", "Photo - Download", 0)
link("Photo - Download", "Save Image", 0); link("Photo - Download", "Image - Request", 1)

# ---- sanity
names = [n["name"] for n in w["nodes"]]
assert len(names) == len(set(names)), "duplicate node names"
for k, v in w["connections"].items():
    assert k in by_name, k
    for outs in v["main"]:
        for c in outs or []:
            assert c["node"] in by_name, c["node"]
json.dump(w, open(dst, "w"), indent=1)
print(f"OK -> {dst}: {len(w['nodes'])} nodes, id={w.get('id')}")
