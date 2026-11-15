#!/usr/bin/env python3
"""Build the "Vikops Ad Pipeline" workflow (15 s Lithuanian ad for vikops.lt) from the LT workflow.

Input : the LT workflow JSON (output of make_lt_workflow.py) - reuses its Lithuanian voice,
        quote-safe JSON parsing, captions and image loop.
Output: a SEPARATE workflow (own id, node ids, webhook ids). The news part (RSS -> pick story ->
        fetch article) is replaced by "Pick Topic": an ad angle built only from vikops.lt facts,
        or the free-text topic sent with `/run vikops <tema>`.

usage: make_vikops_workflow.py <lt.json> <out_vikops.json>
"""
import copy, json, re, sys, uuid

SRC = sys.argv[1] if len(sys.argv) > 1 else "n8n/workflow_lt.json"
DST = sys.argv[2] if len(sys.argv) > 2 else "n8n/workflow_vikops.json"
VIKOPS_WORKFLOW_ID = "VikopsAdPipeln01"   # fixed 16-char id
SITE, PHONE = "vikops.lt", "+370 664 88588"

# Everything the script may claim. Source: vikops.lt (read 2026-11-15). Edit here when prices change.
FACTS = """MB „Vikops“ - natūralaus kalkakmenio grindų plytelės ir jų klojimas.
- Seashell: šviesus kalkakmenis su tikrais jūrinių kriauklių fragmentais. Kaina nuo 63 €/m² su PVM.
- Highland Grey: pilkas kalkakmenis su fosilijų fragmentais.
- Formatai: 900×600, 850×600, 800×600, 750×600, 700×600, 650×600 ir 600×600 mm. Storis nuo 13 mm, gludintas (honed) paviršius.
- „Opus French“ mozaikos komplektai. Klojimo schemos: „Regular“ (vienodo formato) ir „Opus“ (skirtingų ilgių plokštės).
- Klojimas nuo 35 €/m²; klijai ir fuga apie 10 €/m². Impregnavimas ir priežiūros instrukcijos.
- Architektams, dizaineriams ir rangovams 5-15 % nuolaida.
- Minimalaus užsakymo nėra - galima pasiimti ir vieną dėžę. Didesnius kiekius pristato.
- 2 200 m² sandėlis Magūnuose, Vilniaus rajone, 15 min nuo Vilniaus. Apžiūra pagal susitarimą, ir savaitgaliais.
- Šūkiai: „Grindys iš jūros dugno.“ „Kiekviena plytelė - mažas muziejus, kurį galima paliesti.“
- Kontaktai: vikops.lt, +370 664 88588."""

ANGLES = [
    "Grindys iš jūros dugno: Seashell kalkakmenyje matosi tikros kriauklės.",
    "Kiekviena plytelė - mažas muziejus: fosilijos Highland Grey akmenyje.",
    "Opus klojimas: skirtingų ilgių plokštės sukuria gyvą, natūralų raštą.",
    "Natūralus kalkakmenis prieinamesnis nei manai: Seashell nuo 63 €/m², klojimas nuo 35 €/m².",
    "Nėra minimalaus užsakymo: gali pasiimti net vieną dėžę, sandėlis 15 min nuo Vilniaus.",
    "Architektams, dizaineriams ir rangovams 5-15 % nuolaida.",
    "Viskas vienoje vietoje: plytelės, klojimas, impregnavimas ir priežiūros patarimai.",
    "Pamatyk akmenį gyvai: 2 200 m² sandėlis Magūnuose, apžiūra ir savaitgaliais.",
]

src = json.load(open(SRC))
assert src.get("id") != VIKOPS_WORKFLOW_ID
w = copy.deepcopy(src)
w["name"] = "Vikops Ad Pipeline"
w["id"] = VIKOPS_WORKFLOW_ID
for k in ("versionId", "staticData", "pinData", "tags", "meta"):
    w.pop(k, None)

# ---- 1) drop the news chain
DROP = {"RSS A", "RSS B", "RSS C", "Combine Feeds", "Select Story", "Parse Selection", "Article - Fetch", "HTML"}
w["nodes"] = [n for n in w["nodes"] if n["name"] not in DROP]
for d in DROP:
    w["connections"].pop(d, None)
for n in w["nodes"]:
    n["id"] = str(uuid.uuid4())
    if "webhookId" in n:
        n["webhookId"] = str(uuid.uuid4())
by_name = {n["name"]: n for n in w["nodes"]}
by_name["Every Hour"]["disabled"] = True

# ---- 2) Pick Topic: /run vikops <tema> -> that topic, otherwise a random angle
pick_js = (
    "const FACTS = " + json.dumps(FACTS, ensure_ascii=False) + ";\n"
    "const ANGLES = " + json.dumps(ANGLES, ensure_ascii=False) + ";\n"
    "const inp = ($input.first() && $input.first().json) || {};\n"
    "const topic = String(inp.topic || '').trim().slice(0, 300);\n"
    "const angle = topic ? ('Užsakovo tema: ' + topic) : ANGLES[Math.floor(Math.random() * ANGLES.length)];\n"
    "return [{ json: { angle, topic_in: topic, brief: 'ANGLE: ' + angle + '\\n\\nFACTS (the ONLY facts you may state):\\n' + FACTS } }];"
)
mx, my = by_name["Message a model"]["position"]
w["nodes"].append({"parameters": {"jsCode": pick_js}, "type": "n8n-nodes-base.code", "typeVersion": 2,
                   "position": [mx - 260, my], "id": str(uuid.uuid4()), "name": "Pick Topic"})
w["connections"]["Run Now (CLI)"] = {"main": [[{"node": "Pick Topic", "type": "main", "index": 0}]]}
w["connections"]["Every Hour"] = {"main": [[{"node": "Pick Topic", "type": "main", "index": 0}]]}
w["connections"]["Pick Topic"] = {"main": [[{"node": "Message a model", "type": "main", "index": 0}]]}

# ---- 3) ad script prompt (same JSON schema; 5 scenes x 3 s)
by_name["Message a model"]["parameters"]["messages"]["values"][0]["content"] = (
    "=You write 15-second vertical video ADS (TikTok/Reels/Facebook) in Lithuanian for MB „Vikops“ (vikops.lt), "
    "a company that sells and installs natural limestone floor tiles near Vilnius.\n\n"
    "Output ONLY valid JSON matching the SCHEMA below. No markdown, no code fences, no text before or after the JSON. "
    "Inside JSON strings never use the ASCII double quote character: write Lithuanian quotes as „ and “ instead.\n\n"
    "LANGUAGE\n"
    "- voiceover, every vo_segment, on_screen_text, hook, meta.title, center.label and hashtags are in NATURAL SPOKEN LITHUANIAN: "
    "warm, confident, premium but friendly - like a good interior designer talking to a homeowner. Correct grammar, cases and diacritics "
    "(ą č ę ė į š ų ū ž). Short sentences. No anglicisms (product names Seashell, Highland Grey, Opus stay as they are), no bureaucratic phrasing.\n"
    "- Write prices so they are read correctly aloud: \"šešiasdešimt trys eurai už kvadratinį metrą\".\n"
    "- Do NOT spell the web address or phone in the voiceover: an end card shows vikops.lt and the phone. "
    "End the voiceover with a short call to action that names Vikops (e.g. „Užsuk į Vikops.“ / „Rinkis Vikops.“).\n"
    "- visual.query stays in ENGLISH.\n\n"
    "RULES\n"
    "- Build the ad around the ANGLE. Sentence 1 is a scroll-stopping hook (a surprising image or benefit, not the company name).\n"
    "- ACCURACY: state ONLY facts from FACTS. Never invent prices, discounts, guarantees, stock, delivery times, awards or reviews. "
    "No superlatives you cannot back up (\"geriausias Lietuvoje\").\n"
    "- voiceover: ~30-35 words total (~15 s).\n"
    "- scenes: exactly 5 (not 4, not 6). Each = one short VO phrase (max 8 words) + one short on_screen_text + one visual + duration_sec 3. Durations sum to exactly 15.\n"
    "- The scenes' vo_segment values, joined in order with spaces, MUST equal the voiceover.\n"
    "- on_screen_text: max ~4 words, Lithuanian. The last scene's on_screen_text is the call to action (e.g. „Apžiūrėk gyvai“).\n"
    "- center: {\"type\":\"stat\",\"value\":\"63\",\"prefix\":\"\",\"suffix\":\"€/m²\",\"label\":\"Seashell kaina nuo\"} ONLY for a number that is in FACTS "
    "(prefix/suffix short units like €, €/m², %, m²; no color), at most 1 scene; otherwise {\"type\":\"none\"}. Never use \"entity\".\n"
    "- hook: max 7 words. hashtags: 4-6 Lithuanian/relevant hashtags, no spaces (e.g. #kalkakmenis #interjeras #grindys #vikops).\n\n"
    "VISUAL RULES (for every visual.query, in English)\n"
    "- Show the PRODUCT: honed natural limestone floor tiles. Seashell = light cream/beige limestone with visible small sea-shell fragments; "
    "Highland Grey = grey limestone with fossil fragments. Large thin rectangular TILES (60 cm wide, 60-90 cm long, 13 mm thick) with perfectly straight sawn edges and a flat honed surface - NEVER rough, broken, chunky or irregular stone pieces, never natural rock boulders or flagstone.\n"
    "- Mix: macro close-ups of shells/fossils in the stone; bright modern Scandinavian living rooms, kitchens, bathrooms and terraces with the limestone floor; "
    "an Opus pattern floor of mixed-length rectangular slabs; hands of a tiler setting a large slab; a calm stone warehouse with neat pallets of slabs. "
    "Each scene a clearly different shot that matches its sentence.\n"
    "- Photoreal, premium interior-magazine look. No readable text, numbers, logos or watermarks. No faces in close-up. "
    "Do not show other stone types (marble veining, travertine holes, slate) or glossy polished finish.\n"
    "- Vertical 9:16, main subject in the lower-middle, calmer darker space in the top third.\n\n"
    "SCHEMA\n"
    "{\"meta\":{\"title\":\"...\"},\"hook\":\"...\",\"hashtags\":[\"#...\"],\"voiceover\":\"...\","
    "\"scenes\":[{\"id\":1,\"vo_segment\":\"...\",\"on_screen_text\":\"...\",\"visual\":{\"query\":\"...\"},\"center\":{\"type\":\"none\"},\"duration_sec\":3}]}\n\n"
    "BRIEF\n{{ $json.brief }}")

# ---- 4) Code in JavaScript: vikops_ files, channel + CTA, no Wikipedia entities
code = by_name["Code in JavaScript"]["parameters"]["jsCode"]


def rep(old, new, count=1):
    global code
    assert code.count(old) == count, (old, code.count(old))
    code = code.replace(old, new)


for kind in ("img", "voice", "video", "job"):
    rep('"lt_%s_"+ts' % kind, '"vikops_%s_"+ts' % kind)
rep('"Lietuvos naujienos"', '"natural limestone floor tiles in a bright modern home"', 2)
rep('channel:"lt",',
    'channel:"vikops", cta:{url:"%s", phone:"%s"}, angle: ($(\'Pick Topic\').first().json.angle || ""),' % (SITE, PHONE))
# only real-number stats in the middle; never Wikipedia look-ups for an ad
code, k = re.subn(r"for \(const _s of scenes\) \{\s*let c = _s\.center;",
                  "for (const _s of scenes) {\n  let c = _s.center;\n  if (c && c.type && c.type !== 'stat') { _s.center = { type: 'none' }; c = _s.center; }", code)
assert k == 1
rep("if (c.type === 'none') {\n    const cands = extractEntities", "if (false && c.type === 'none') {\n    const cands = extractEntities")
assert "cta:{url" in code and "vikops_video_" in code
by_name["Code in JavaScript"]["parameters"]["jsCode"] = code

# ---- 5) image style: interior / product photography
ss = by_name["Split Scenes"]["parameters"]
i0 = ss["jsCode"].index('const STYLE="')
i1 = ss["jsCode"].index('";', i0) + 2
ss["jsCode"] = ss["jsCode"][:i0] + (
    'const STYLE=" Style: high-end interior and architectural photography, photorealistic natural honed limestone texture with visible '
    'shell and fossil details, thin rectangular tiles with straight sawn edges (never rough or irregular stone), soft natural daylight, warm neutral palette, calm premium editorial look, high detail. Vertical 9:16. '
    'No text, no numbers, no logos, no watermark.";') + ss["jsCode"][i1:]

# ---- 6) sanity
names = [n["name"] for n in w["nodes"]]
for outs in w["connections"].values():
    for branch in outs.get("main", []):
        for c in branch or []:
            assert c["node"] in names, c
blob = json.dumps(w, ensure_ascii=False)
for gone in ("Combine Feeds", "Parse Selection", "lrt.lt", "15min.lt"):
    assert gone not in blob, gone
assert all(n["id"] != o["id"] for n in w["nodes"] for o in src["nodes"])
json.dump(w, open(DST, "w"), indent=2, ensure_ascii=False)
print(f"OK -> {DST}: {len(w['nodes'])} nodes, id={w['id']}")
