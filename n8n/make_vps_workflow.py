#!/usr/bin/env python3
"""Turn the Drive-based workflow into the VPS (local disk) version.

Replaces the three Google Drive nodes with n8n "Read/Write Files from Disk"
nodes that write into /data/shared (= /root/shared on the VPS host):
  images + voice -> /data/shared/assets/
  job json       -> /data/shared/jobs/
Every other node and connection is left untouched.
"""
import json, sys, uuid

SRC = sys.argv[1] if len(sys.argv) > 1 else "n8n/workflow.json"
DST = sys.argv[2] if len(sys.argv) > 2 else "n8n/workflow_vps.json"
SHARED = "/data/shared"

w = json.load(open(SRC))
by_name = {n["name"]: n for n in w["nodes"]}


def write_node(old, new_name, path_expr):
    return {
        "parameters": {
            "operation": "write",
            "fileName": "=" + SHARED + path_expr,
            "dataPropertyName": "data",
            "options": {},
        },
        "type": "n8n-nodes-base.readWriteFile",
        "typeVersion": 1,
        "position": old["position"],
        "id": old["id"],
        "name": new_name,
    }


def rename(old, new):
    """Rename a node everywhere in the connections map."""
    con = w["connections"]
    if old in con:
        con[new] = con.pop(old)
    for outs in con.values():
        for branch in outs.get("main", []):
            for c in branch or []:
                if c["node"] == old:
                    c["node"] = new


# 1) image upload -> disk
img = by_name["Upload file"]
w["nodes"][w["nodes"].index(img)] = write_node(
    img, "Save Image", "/assets/{{ $('Split Scenes').item.json.imageFile }}")
rename("Upload file", "Save Image")

# 2) voice upload -> disk
voc = by_name["Upload file1"]
w["nodes"][w["nodes"].index(voc)] = write_node(
    voc, "Save Voice", "/assets/{{ $('Code in JavaScript').first().json.voiceFile }}")
rename("Upload file1", "Save Voice")

# 3) job file: Code node builds the binary, then a disk write node saves it
job = by_name["Create file from text"]
make_job = {
    "parameters": {
        "jsCode": (
            "const txt = $('Add Captions').first().json.job_json;\n"
            "const name = $('Code in JavaScript').first().json.jobFile;\n"
            "const bin = await this.helpers.prepareBinaryData(Buffer.from(txt, 'utf8'), name, 'application/json');\n"
            "return [{ json: { jobFile: name }, binary: { data: bin } }];"
        )
    },
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": job["position"],
    "id": job["id"],
    "name": "Make Job File",
    "executeOnce": True,
}
save_job = write_node(
    {"position": [job["position"][0] + 220, job["position"][1]], "id": str(uuid.uuid4())},
    "Save Job", "/jobs/{{ $json.jobFile }}")
w["nodes"][w["nodes"].index(job)] = make_job
w["nodes"].append(save_job)
rename("Create file from text", "Make Job File")
w["connections"]["Make Job File"] = {"main": [[{"node": "Save Job", "type": "main", "index": 0}]]}

# 3b) Combine Feeds looked up feed nodes by old names; point it at RSS A/B/C,
#     and fail loudly if no stories were collected (instead of an empty prompt)
cf = by_name["Combine Feeds"]["parameters"]
cf["jsCode"] = (cf["jsCode"]
    .replace("'RSS CoinDesk'", "'RSS A'")
    .replace("'RSS Cointelegraph'", "'RSS B'")
    .replace("'RSS Decrypt'", "'RSS C'")
    .replace("all=all.filter(x=>x.title&&x.link);",
             "all=all.filter(x=>x.title&&x.link);\n"
             "if(!all.length) throw new Error('Combine Feeds: no RSS stories collected');"))
assert "'RSS A'" in cf["jsCode"] and "no RSS stories" in cf["jsCode"]

# 4) programmatic start: lets `n8n execute --id=...` run it (CLI needs this trigger)
sched = by_name["Every Hour"]
w["nodes"].append({
    "parameters": {"inputSource": "passthrough"},
    "type": "n8n-nodes-base.executeWorkflowTrigger",
    "typeVersion": 1.1,
    "position": [sched["position"][0], sched["position"][1] + 200],
    "id": str(uuid.uuid4()),
    "name": "Run Now (CLI)",
})
w["connections"]["Run Now (CLI)"] = {"main": [[{"node": "RSS A", "type": "main", "index": 0}]]}

assert not any(n["type"].endswith("googleDrive") for n in w["nodes"]), "Drive node left"
w["name"] = "Crypto Video Pipeline"
json.dump(w, open(DST, "w"), indent=2)
print(f"OK -> {DST}: {len(w['nodes'])} nodes, no Google Drive")
