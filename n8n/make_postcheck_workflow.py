#!/usr/bin/env python3
"""5HU Post Check - every 30 min: did Metricool really publish our posts? (autopilot safety net, owner 2026-11-25)

Metricool accepts a post right away but publishes it later, so a failure (Instagram refusing a collab invite, an expired
connection, a media error) would otherwise go unnoticed in quiet mode. This workflow lists the 5HU posts of the last 6 hours,
and for every network that ended in ERROR (each one once):
  - an Instagram Reel that carried a collab invite is posted again WITHOUT the invite (the invite is the likely cause);
  - a short Telegram message goes to the owner (errors are the only messages he gets).

    python3 n8n/make_postcheck_workflow.py <metricool_credential_id> out.json
"""
import json, sys, uuid

CID = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/wf_postcheck.json"
BLOG, USER = "8237757", "6373812"
WF_ID = "FiveHuPostChk01"
MC_CRED = {"httpHeaderAuth": {"id": CID, "name": "Metricool"}}
TG_CRED = {"telegramApi": {"id": "MsHdBVyurDnoXcyo", "name": "Telegram account"}}

FIND_JS = r"""
const st = $getWorkflowStaticData('global'); st.seen = st.seen || {};
for (const k of Object.keys(st.seen)) if (Date.now() - st.seen[k] > 4 * 864e5) delete st.seen[k];
const d = $input.first().json || {};
const list = Array.isArray(d.data) ? d.data : (Array.isArray(d) ? d : []);
const out = [];
for (const p of list) for (const pr of (p.providers || [])) {
  if (String(pr.status || '').toUpperCase() !== 'ERROR') continue;
  const key = String(p.id) + ':' + pr.network; if (st.seen[key]) continue; st.seen[key] = Date.now();
  const why = String(pr.detailedStatus || pr.error || pr.errorMessage || 'unknown error').replace(/\s+/g, ' ').slice(0, 200);
  const ig = p.instagramData || {};
  const hadCollab = pr.network === 'instagram' && Array.isArray(ig.collaborators) && ig.collaborators.length > 0;
  // "published with some warnings" = it IS live (it has a public URL): never post it again
  const live = !!(pr.publicUrl || /^https?:/.test(String(pr.id || '')));
  const restricted = /restrict/i.test(why);
  if (restricted) st.restrictedAt = Date.now();
  let rescue = null;
  if (hadCollab && !live) {
    const when = new Date(Date.now() + 3 * 60 * 1000).toLocaleString('sv-SE', { timeZone: 'Europe/Vilnius' }).replace(' ', 'T').slice(0, 19);
    const igData = Object.assign({}, ig); delete igData.collaborators;
    rescue = { publicationDate: { dateTime: when, timezone: 'Europe/Vilnius' }, autoPublish: true, draft: false, descendants: [],
      text: p.text || '', firstCommentText: p.firstCommentText || '', hasNotReadNotes: false, media: p.media || [], mediaAltText: [],
      shortener: false, smartLinkData: { ids: [] }, providers: [{ network: 'instagram' }], instagramData: igData };
    if (p.videoThumbnailUrl) rescue.videoThumbnailUrl = p.videoThumbnailUrl;
  }
  const what = (ig.type === 'POST' || (p.media || []).length > 1) ? 'post' : 'Reel';
  out.push({ json: { network: pr.network, why, restricted, rescue: rescue ? JSON.stringify(rescue) : '',
    alert: '⚠️ 5HU: ' + pr.network + ' ' + what + (live ? ' is live, but ' + pr.network + ' warned: ' : ' failed to publish: ') + why.replace(/\.?$/, '.')
      + (rescue ? ' Reposting it without the collab invite.' : '')
      + (restricted ? ' Instagram careful mode for 14 days: no tags, collab invites, first comments or carousels there; Reels keep posting.' : '') } });
}
return out;
"""

HEALTH_JS = r"""
const st = $getWorkflowStaticData('global');
if (!$input.all().some(i => i.json.restricted)) return [];
const body = JSON.stringify({ lastRestrictedAt: new Date(st.restrictedAt || Date.now()).toISOString(), carefulDays: 14 });
return [{ json: {}, binary: { data: await this.helpers.prepareBinaryData(Buffer.from(body, 'utf8'), '5hu_ig_health.json', 'application/json') } }];
"""

RANGE = {
    "start": "={{ $now.minus({hours: 6}).setZone('Europe/Vilnius').toFormat(\"yyyy-MM-dd'T'HH:mm:ss\") }}",
    "end": "={{ $now.plus({minutes: 10}).setZone('Europe/Vilnius').toFormat(\"yyyy-MM-dd'T'HH:mm:ss\") }}",
}


def node(name, typ, ver, params, pos, **extra):
    n = {"parameters": params, "type": typ, "typeVersion": ver, "position": pos, "id": str(uuid.uuid4()), "name": name}
    n.update(extra)
    return n


nodes = [
    node("Every 30 min", "n8n-nodes-base.scheduleTrigger", 1.2,
         {"rule": {"interval": [{"field": "cronExpression", "expression": "7,37 * * * *"}]}}, [0, 0]),
    node("Run Now (CLI)", "n8n-nodes-base.executeWorkflowTrigger", 1.1, {"inputSource": "passthrough"}, [0, 200]),
    node("Our Posts", "n8n-nodes-base.httpRequest", 4.2, {
        "url": "https://app.metricool.com/api/v2/scheduler/posts",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendQuery": True, "queryParameters": {"parameters": [
            {"name": "blogId", "value": BLOG}, {"name": "userId", "value": USER}, {"name": "timezone", "value": "Europe/Vilnius"},
            {"name": "extendedRange", "value": "false"}, {"name": "start", "value": RANGE["start"]}, {"name": "end", "value": RANGE["end"]}]},
        "options": {"timeout": 60000}}, [220, 0], credentials=MC_CRED, onError="stopWorkflow", retryOnFail=True, maxTries=2, waitBetweenTries=10000),
    node("Find Problems", "n8n-nodes-base.code", 2, {"jsCode": FIND_JS}, [440, 0]),
    node("Rescue?", "n8n-nodes-base.if", 2.2,
         {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                         "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.rescue }}", "rightValue": "",
                                         "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}], "combinator": "and"}, "options": {}},
         [660, -120]),
    node("Repost Without Collab", "n8n-nodes-base.httpRequest", 4.2, {
        "method": "POST", "url": f"https://app.metricool.com/api/v2/scheduler/posts?blogId={BLOG}&userId={USER}",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json", "jsonBody": "={{ $json.rescue }}", "options": {"timeout": 60000}},
         [880, -120], credentials=MC_CRED, onError="continueRegularOutput", retryOnFail=True, maxTries=2, waitBetweenTries=5000),
    node("Health File", "n8n-nodes-base.code", 2, {"jsCode": HEALTH_JS}, [660, 320]),
    node("Write Health", "n8n-nodes-base.readWriteFile", 1,
         {"operation": "write", "fileName": "/data/shared/5hu_ig_health.json", "dataPropertyName": "data", "options": {}}, [880, 320],
         onError="continueRegularOutput"),
    node("Tell Owner", "n8n-nodes-base.telegram", 1.2,
         {"chatId": "694708370", "text": "={{ $json.alert }}", "additionalFields": {"appendAttribution": False}},
         [660, 120], credentials=TG_CRED, onError="continueRegularOutput", retryOnFail=True, maxTries=3, waitBetweenTries=20000),
]
conn = {
    "Every 30 min": {"main": [[{"node": "Our Posts", "type": "main", "index": 0}]]},
    "Run Now (CLI)": {"main": [[{"node": "Our Posts", "type": "main", "index": 0}]]},
    "Our Posts": {"main": [[{"node": "Find Problems", "type": "main", "index": 0}]]},
    "Find Problems": {"main": [[{"node": "Rescue?", "type": "main", "index": 0}, {"node": "Tell Owner", "type": "main", "index": 0},
                                {"node": "Health File", "type": "main", "index": 0}]]},
    "Health File": {"main": [[{"node": "Write Health", "type": "main", "index": 0}]]},
    "Rescue?": {"main": [[{"node": "Repost Without Collab", "type": "main", "index": 0}], []]},
}
wf = {"id": WF_ID, "name": "5HU Post Check", "nodes": nodes, "connections": conn,
      "settings": {"executionOrder": "v1", "timezone": "Europe/Vilnius", "saveDataSuccessExecution": "none"}, "active": False, "pinData": {}}
json.dump(wf, open(OUT, "w"), ensure_ascii=False, indent=1)
print("OK ->", OUT)
