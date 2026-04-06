#!/usr/bin/env python3
"""Notion sync — structured runtime state for boot."""
import os, urllib.request, json

TOKEN = os.environ.get("NOTION_API_KEY") or open("/data/.openclaw/workspace/.notion_token").read().strip()
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}

CONTRACTS_DB = "33a8f06b-14e6-8145-8d82-f07062e5981a"
DRAFT_DB = "33a8f06b-14e6-819e-8484-f87112df92e1"

def query_db(db_id, payload=None):
    payload = payload or {"page_size": 50}
    req = urllib.request.Request(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        data=json.dumps(payload).encode(),
        headers=HEADERS, method="POST"
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["results"]

def get_name(props):
    for k in ("Name", "Title"):
        if k in props and props[k].get("type") == "title":
            return "".join(t["plain_text"] for t in props[k]["title"])
    for k, v in props.items():
        if v.get("type") in ("rich_text", "text"):
            val = "".join(t["plain_text"] for t in v.get("rich_text", []))
            if val:
                return val
    return "(untitled)"

def main():
    state = {
        "p0": [],
        "p0_blockers": [],
        "p1": [],
        "draft_high": [],
        "violations": [],
        "errors": []
    }

    # --- Contracts ---
    try:
        contracts = query_db(CONTRACTS_DB)
        for p in contracts:
            props = p["properties"]
            name = get_name(props)
            status = props.get("Status", {}).get("select", {}).get("name", "")
            abstraction = props.get("Abstraction Level", {}).get("select", {}).get("name", "")
            blockers = props.get("Blockers", {}).get("rich_text", [])
            blocker_text = "".join(t["plain_text"] for t in blockers) if blockers else ""

            entry = {"id": p["id"], "name": name, "status": status, "abstraction": abstraction}

            if status == "In Progress":
                # Check Next Action field (rich_text type)
                next_action_field = props.get("Next Action", {})
                next_action_text = ""
                if next_action_field.get("type") == "rich_text":
                    next_action_text = "".join(t["plain_text"] for t in next_action_field.get("rich_text", []))
                has_next_action = bool(next_action_text.strip())

                if not has_next_action:
                    state["violations"].append({
                        "type": "MISSING_NEXT_ACTION",
                        "contract": name,
                        "id": p["id"]
                    })
                entry["has_next_action"] = has_next_action
                entry["next_action"] = next_action_text

                # Determine priority tier
                priority = props.get("Priority", {}).get("select", {}).get("name", "")
                if priority == "P0":
                    state["p0"].append(entry)
                elif priority == "P1":
                    state["p1"].append(entry)
                else:
                    # Default: if P0 in name or abstraction is System → P0
                    if "P0" in name.upper() or abstraction == "System":
                        state["p0"].append(entry)
                    else:
                        state["p1"].append(entry)

            if blocker_text:
                state["p0_blockers"].append({"name": name, "blocker": blocker_text})

    except Exception as e:
        state["errors"].append(f"Contracts query failed: {e}")

    # --- Draft Layer: High Priority Open ---
    try:
        draft = query_db(DRAFT_DB, {
            "filter": {
                "and": [
                    {"property": "Status", "select": {"equals": "Open"}},
                    {"property": "Priority", "select": {"equals": "High"}}
                ]
            }
        })
        for p in draft:
            props = p["properties"]
            state["draft_high"].append({
                "name": get_name(props),
                "type": props.get("Type", {}).get("select", {}).get("name", "")
            })
    except Exception as e:
        state["errors"].append(f"Draft Layer query failed: {e}")

    # --- Output ---
    print("=== NOTION SYNC ===")
    print(f"P0 contracts ({len(state['p0'])}):")
    for c in state["p0"]:
        print(f"  • {c['name']} [{c['abstraction']}]")
    print(f"P0 blockers ({len(state['p0_blockers'])}):")
    for b in state["p0_blockers"]:
        print(f"  • {b['name']}: {b['blocker']}")
    print(f"P1 contracts ({len(state['p1'])}):")
    for c in state["p1"]:
        print(f"  • {c['name']} [{c['abstraction']}]")
    print(f"High-priority Draft items ({len(state['draft_high'])}):")
    for d in state["draft_high"]:
        print(f"  • [{d['type']}] {d['name']}")
    print(f"Violations ({len(state['violations'])}):")
    for v in state["violations"]:
        print(f"  🔴 [{v['type']}] {v['contract']}: {v['note']}")
    if state["errors"]:
        print(f"Errors ({len(state['errors'])}):")
        for err in state["errors"]:
            print(f"  ⚠️ {err}")
    print("=== END SYNC ===")
    return state

if __name__ == "__main__":
    main()
