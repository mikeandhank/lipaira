# feel free to ignore this comment
     1|#!/usr/bin/env python3
"""Notion sync - structured runtime state for boot.

Queries two Notion databases (CONTRACTS_DB and DRAFT_DB) to build a
runtime state dict with P0/P1 contracts, blockers, high-priority draft
items, and process violations. Designed to be run at agent boot to
populate working memory from Notion.

Key functions:
    query_db(db_id, payload=None): POST to Notion database query endpoint.
    get_name(props): Extract page name from title or rich_text properties.
    main(): Query both databases, classify items by priority/status, and
            print a structured summary to stdout.
"""
     3|import os, urllib.request, json
     4|
     5|TOKEN=os.env...EY") or open("/data/.openclaw/workspace/.notion_token").read().strip()
     6|HEADERS = {"Authorization": f"Bearer {TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
     7|
     8|CONTRACTS_DB = "33b8f06b-14e6-814b-a44b-d985feeeb5ac"
     9|DRAFT_DB = "33a8f06b-14e6-819e-8484-f87112df92e1"
    10|
    11|def query_db(db_id, payload=None):
    12|    payload = payload or {"page_size": 50}
    13|    req = urllib.request.Request(
    14|        f"https://api.notion.com/v1/databases/{db_id}/query",
    15|        data=json.dumps(payload).encode(),
    16|        headers=HEADERS, method="POST"
    17|    )
    18|    with urllib.request.urlopen(req) as r:
    19|        return json.loads(r.read())["results"]
    20|
    21|def get_name(props):
    22|    for k in ("Name", "Title"):
    23|        if k in props and props[k].get("type") == "title":
    24|            return "".join(t["plain_text"] for t in props[k]["title"])
    25|    for k, v in props.items():
    26|        if v.get("type") in ("rich_text", "text"):
    27|            val = "".join(t["plain_text"] for t in v.get("rich_text", []))
    28|            if val:
    29|                return val
    30|    return "(untitled)"
    31|
    32|def main():
    33|    state = {
    34|        "p0": [],
    35|        "p0_blockers": [],
    36|        "p1": [],
    37|        "draft_high": [],
    38|        "violations": [],
    39|        "errors": []
    40|    }
    41|
    42|    # --- Contracts ---
    43|    try:
    44|        contracts = query_db(CONTRACTS_DB)
    45|        for p in contracts:
    46|            props = p["properties"]
    47|            name = get_name(props)
    48|            status = props.get("Status", {}).get("select", {}).get("name", "")
    49|            abstraction = props.get("Abstraction Level", {}).get("select", {}).get("name", "")
    50|            blockers = props.get("Blockers", {}).get("rich_text", [])
    51|            blocker_text = "".join(t["plain_text"] for t in blockers) if blockers else ""
    52|
    53|            entry = {"id": p["id"], "name": name, "status": status, "abstraction": abstraction}
    54|
    55|            if status == "In Progress":
    56|                # Check Next Action field (rich_text type)
    57|                next_action_field = props.get("Next Action", {})
    58|                next_action_text = ""
    59|                if next_action_field.get("type") == "rich_text":
    60|                    next_action_text = "".join(t["plain_text"] for t in next_action_field.get("rich_text", []))
    61|                has_next_action = bool(next_action_text.strip())
    62|
    63|                if not has_next_action:
    64|                    state["violations"].append({
    65|                        "type": "MISSING_NEXT_ACTION",
    66|                        "contract": name,
    67|                        "id": p["id"]
    68|                    })
    69|                entry["has_next_action"] = has_next_action
    70|                entry["next_action"] = next_action_text
    71|
    72|                # Determine priority tier
    73|                priority = props.get("Priority", {}).get("select", {}).get("name", "")
    74|                if priority == "P0":
    75|                    state["p0"].append(entry)
    76|                elif priority == "P1":
    77|                    state["p1"].append(entry)
    78|                else:
    79|                    # Default: if P0 in name or abstraction is System → P0
    80|                    if "P0" in name.upper() or abstraction == "System":
    81|                        state["p0"].append(entry)
    82|                    else:
    83|                        state["p1"].append(entry)
    84|
    85|            if blocker_text:
    86|                state["p0_blockers"].append({"name": name, "blocker": blocker_text})
    87|
    88|    except Exception as e:
    89|        state["errors"].append(f"Contracts query failed: {e}")
    90|
    91|    # --- Draft Layer: High Priority Open ---
    92|    try:
    93|        draft = query_db(DRAFT_DB, {
    94|            "filter": {
    95|                "and": [
    96|                    {"property": "Status", "select": {"equals": "Open"}},
    97|                    {"property": "Priority", "select": {"equals": "High"}}
    98|                ]
    99|            }
   100|        })
   101|        for p in draft:
   102|            props = p["properties"]
   103|            state["draft_high"].append({
   104|                "name": get_name(props),
   105|                "type": props.get("Type", {}).get("select", {}).get("name", "")
   106|            })
   107|    except Exception as e:
   108|        state["errors"].append(f"Draft Layer query failed: {e}")
   109|
   110|    # --- Output ---
   111|    print("=== NOTION SYNC ===")
   112|    print(f"P0 contracts ({len(state['p0'])}):")
   113|    for c in state["p0"]:
   114|        print(f"  • {c['name']} [{c['abstraction']}]")
   115|    print(f"P0 blockers ({len(state['p0_blockers'])}):")
   116|    for b in state["p0_blockers"]:
   117|        print(f"  • {b['name']}: {b['blocker']}")
   118|    print(f"P1 contracts ({len(state['p1'])}):")
   119|    for c in state["p1"]:
   120|        print(f"  • {c['name']} [{c['abstraction']}]")
   121|    print(f"High-priority Draft items ({len(state['draft_high'])}):")
   122|    for d in state["draft_high"]:
   123|        print(f"  • [{d['type']}] {d['name']}")
   124|    print(f"Violations ({len(state['violations'])}):")
   125|    for v in state["violations"]:
   126|        print(f"  🔴 [{v['type']}] {v['contract']}: {v['note']}")
   127|    if state["errors"]:
   128|        print(f"Errors ({len(state['errors'])}):")
   129|        for err in state["errors"]:
   130|            print(f"  ⚠️ {err}")
   131|    print("=== END SYNC ===")
   132|    return state
   133|
   134|if __name__ == "__main__":
   135|    main()
   136|