#!/usr/bin/env python3
"""
dag_executor.py — Autonomous DAG mechanical executor.
Runs as a background daemon on the relay host.
Reads /opt/data/workflow.json, fires tasks to agents, handles results,
auto-creates QA nodes, and notifies Robert on blockers.
"""

import os, json, time, re, logging, requests, threading
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DAG] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/opt/relay/logs/dag_executor.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("dag_executor")

# ── Constants ─────────────────────────────────────────────────────────────────
WORKFLOW_PATH   = "/opt/data/workflow.json"
MEMORY_URL      = "http://172.20.0.1:9001"
MEMORY_SECRET    = "38467057af586e03135a309f27c62f1737b0f1f595e91713cc32f45aa310f78c"

TELEGRAM_TOKEN   = os.environ.get("DAG_EXECUTOR_TELEGRAM_TOKEN", "")
GROUP_CHAT_ID    = -1003995894784
CREW_THREAD      = 3
QA_THREAD        = 5

AGENT_WEBHOOKS = {
    "robert":      "http://172.20.0.2:8100/telegram",
    "jimbojames":  "http://172.19.0.2:8101/telegram",
    "bigbadinky":  "http://172.18.0.2:8102/telegram",
    "patrick":     "http://172.21.0.2:8103/telegram",
    "joey":        "http://172.22.0.2:8104/telegram",
}

PATROL_INTERVAL  = 10   # seconds between workflow polls
TELEGRAM_POLL_INTERVAL = 5  # seconds between Telegram result polls
RESULT_COOLDOWN  = 10   # seconds before same sender can post another result

# Patterns (must match relay.py)
RESULT_PATTERN   = re.compile(r"^RESULT\s*<-\s*(\w+)", re.IGNORECASE | re.MULTILINE)
BLOCKER_PATTERN  = re.compile(r"^BLOCKER\s*<-\s*(\w+)", re.IGNORECASE | re.MULTILINE)

# ── Telegram Bot API ───────────────────────────────────────────────────────────
if TELEGRAM_TOKEN:
    TG_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
else:
    TG_BASE = None
    log.warning("DAG_EXECUTOR_TELEGRAM_TOKEN not set — Telegram polling disabled")


def tg_get_updates(offset=0, timeout=60):
    """Fetch updates from Telegram Bot API."""
    if not TG_BASE:
        return []
    try:
        r = requests.get(f"{TG_BASE}/getUpdates", params={
            "offset": offset,
            "timeout": timeout,
            "allowed_updates": "message"
        }, timeout=timeout + 5)
        data = r.json()
        return data.get("result", []) if data.get("ok") else []
    except Exception as e:
        log.error(f"Telegram getUpdates failed: {e}")
        return []


def tg_send_message(text, chat_id=GROUP_CHAT_ID, thread_id=None):
    """Send a message via the Telegram Bot API."""
    if not TG_BASE:
        log.warning(f"TG not configured, would send: {text[:80]}")
        return
    payload = {"chat_id": chat_id, "text": text}
    if thread_id:
        payload["message_thread_id"] = thread_id
    try:
        r = requests.post(f"{TG_BASE}/sendMessage", json=payload, timeout=10)
        if not r.json().get("ok"):
            log.error(f"TG send failed: {r.json()}")
    except Exception as e:
        log.error(f"TG send error: {e}")


# ── Memory ─────────────────────────────────────────────────────────────────────
def memory_snapshot():
    try:
        req = Request(MEMORY_URL + "/memory/snapshot", headers={
            "X-Memory-Secret": MEMORY_SECRET
        })
        with urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        log.error(f"Memory snapshot failed: {e}")
        return {"memory": {}}


def memory_write(key, value):
    try:
        body = json.dumps({"writes": [{"key": key, "value": value}]}).encode()
        req = Request(
            MEMORY_URL + "/memory/bulk",
            data=body,
            headers={"X-Memory-Secret": MEMORY_SECRET, "Content-Type": "application/json"},
            method="POST"
        )
        urlopen(req, timeout=5)
    except Exception as e:
        log.error(f"Memory write failed ({key}): {e}")


# ── Agent Availability ─────────────────────────────────────────────────────────
def is_agent_available(agent_name, snapshot):
    mem = snapshot.get("memory", {})
    current_task = mem.get(f"agent:{agent_name}:current_task", {}).get("value", "")
    last_seen_str = mem.get(f"agent:{agent_name}:last_seen", {}).get("value", "")

    if current_task and current_task.lower() not in ("null", "none", ""):
        return False, f"busy: {current_task}"

    if not last_seen_str:
        return False, "no heartbeat"

    try:
        last_seen = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - last_seen
        if age.total_seconds() > 300:
            return False, f"stale: {age.total_seconds():.0f}s old"
    except Exception:
        return False, f"bad timestamp: {last_seen_str}"

    return True, "available"


def who_is_available(snapshot):
    available = {}
    for name in AGENT_WEBHOOKS:
        avail, reason = is_agent_available(name, snapshot)
        available[name] = (avail, reason)
    return available


# ── Workflow ───────────────────────────────────────────────────────────────────
def read_workflow():
    try:
        with open(WORKFLOW_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"active": False, "nodes": []}
    except Exception as e:
        log.error(f"Workflow read failed: {e}")
        return {"active": False, "nodes": []}


def write_workflow(state):
    try:
        with open(WORKFLOW_PATH, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log.error(f"Workflow write failed: {e}")


def get_node(workflow, node_id):
    for n in workflow.get("nodes", []):
        if n["id"] == node_id:
            return n
    return None


def node_status(workflow, node_id):
    n = get_node(workflow, node_id)
    return n["status"] if n else None


def all_dependencies_done(workflow, node):
    for dep_id in node.get("depends_on", []):
        if node_status(workflow, dep_id) != "done":
            return False
    return True


def find_ready_nodes(workflow):
    """Return nodes that are pending and have all dependencies done."""
    ready = []
    for n in workflow.get("nodes", []):
        if n["status"] != "pending":
            continue
        if all_dependencies_done(workflow, n):
            ready.append(n)
    return ready


def find_running_nodes(workflow):
    return [n for n in workflow.get("nodes", []) if n["status"] == "running"]


def node_agent_busy(workflow, agent_name):
    """Check if agent already has a running node."""
    for n in workflow.get("nodes", []):
        if n.get("assigned_to", "").lower() == agent_name.lower() and n["status"] == "running":
            return True
    return False


# ── TASK Firing ────────────────────────────────────────────────────────────────
def format_task_message(node):
    """Format a TASK message for an agent from a workflow node."""
    files = node.get("context", {}).get("files", [])
    notes = node.get("context", {}).get("notes", "")
    spec_ref = node.get("context", {}).get("spec_ref", "")

    lines = [
        f"TASK -> {node['assigned_to']}",
        f"goal: {node['description']}",
        f"context: {spec_ref}",
        f"files: {', '.join(files)}" if files else "",
        f"notes: {notes}" if notes else "",
        f"return: RESULT <- {node['assigned_to']}. Status: done or fail. Output: [summary]. Commit: [hash]. Thread: crew.",
        "thread: crew"
    ]
    return "\n".join([l for l in lines if l.split(": ", 1)[-1].strip()])


def fire_task(node, thread_id=CREW_THREAD):
    """POST a TASK directly to an agent's webhook."""
    agent = node["assigned_to"].lower()
    url = AGENT_WEBHOOKS.get(agent)
    if not url:
        log.error(f"No webhook URL for agent: {agent}")
        return False

    message_id = int(time.time() * 1000)
    payload = {
        "update_id": message_id,
        "message": {
            "message_id": message_id,
            "from": {"id": 0, "first_name": "DAGExecutor", "username": "dag_executor", "is_bot": True},
            "chat": {"id": GROUP_CHAT_ID, "type": "supergroup", "title": "Lipaira Dev Chat"},
            "date": int(time.time()),
            "text": format_task_message(node),
            "message_thread_id": thread_id
        }
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        log.info(f"FIRE [{node['id']}] -> {agent}: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        log.error(f"FIRE [{node['id']}] failed: {e}")
        return False


# ── QA Node Auto-creation ─────────────────────────────────────────────────────
def create_qa_node(commit_node, workflow):
    """Create a QA node that depends on a completed commit node."""
    node_id_base = commit_node["id"].replace("_c_", "_qa_")

    # Find a unique ID
    existing_ids = {n["id"] for n in workflow["nodes"]}
    qa_id = node_id_base
    counter = 1
    while qa_id in existing_ids:
        qa_id = f"{node_id_base}_alt{counter}"
        counter += 1

    files = commit_node.get("context", {}).get("files", [])
    qa_node = {
        "id": qa_id,
        "description": f"QA review for {commit_node['description']}",
        "agent_category": "qa",
        "assigned_to": "Patrick",
        "depends_on": [commit_node["id"]],
        "status": "pending",
        "context": {
            "spec_ref": commit_node.get("context", {}).get("spec_ref", ""),
            "files": files,
            "patterns": [],
            "notes": f"QA review: {files[0] if files else 'unknown file'}. Verify the docstrings are accurate and complete."
        },
        "result": None,
        "error": None
    }
    return qa_node


# ── Result Detection ──────────────────────────────────────────────────────────
_last_result_processed = {}   # agent_name -> last result timestamp
_last_tg_update_id = 0


def poll_telegram_results():
    """
    Poll Telegram for RESULT/BLOCKER messages from crew thread.
    Returns list of (sender_agent, status, output, thread_id) tuples.
    """
    global _last_tg_update_id
    results = []

    if not TG_BASE:
        return results

    try:
        updates = tg_get_updates(offset=_last_tg_update_id + 1, timeout=TELEGRAM_POLL_INTERVAL)
    except Exception as e:
        log.error(f"Telegram poll failed: {e}")
        return results

    for update in updates:
        msg = update.get("message", {})
        update_id = update.get("update_id", 0)
        _last_tg_update_id = max(_last_tg_update_id, update_id)

        # Only look at messages in our group from the crew thread
        chat = msg.get("chat", {})
        if chat.get("id") != GROUP_CHAT_ID:
            continue

        thread_id = msg.get("message_thread_id")
        if thread_id != CREW_THREAD:
            continue

        sender = msg.get("from", {})
        if sender.get("is_bot"):
            text = msg.get("text", "")
        else:
            continue  # Only bot accounts send RESULTs

        # Detect RESULT
        r_match = RESULT_PATTERN.search(text)
        if r_match:
            sender_name = r_match.group(1).lower()
            now = time.time()
            last = _last_result_processed.get(sender_name, 0)
            if now - last < RESULT_COOLDOWN:
                log.debug(f"RESULT cooldown skip: {sender_name}")
                continue
            _last_result_processed[sender_name] = now

            # Parse status
            status = "done"
            if "Status: fail" in text or "Status: failed" in text:
                status = "fail"
            elif "Status: pass" in text:
                status = "pass"

            # Extract output
            output = ""
            for line in text.split("\n"):
                if line.startswith("Output:"):
                    output = line.split("Output:", 1)[1].strip()
                    break

            results.append(("result", sender_name, status, output, thread_id))
            continue

        # Detect BLOCKER
        b_match = BLOCKER_PATTERN.search(text)
        if b_match:
            sender_name = b_match.group(1).lower()
            blocker_msg = text
            results.append(("blocker", sender_name, blocker_msg, thread_id))
            continue

    return results


# ── Blockers ───────────────────────────────────────────────────────────────────
def notify_robert_blocker(agent_name, blocker_text):
    msg = (
        f"BLOCKER received from {agent_name}:\n\n"
        f"{blocker_text}\n\n"
        f"Review and decide: retry, reassign, or skip the node."
    )
    tg_send_message(msg, thread_id=CREW_THREAD)
    log.warning(f"BLOCKER from {agent_name}: {blocker_text[:100]}")


# ── Memory Update Helpers ───────────────────────────────────────────────────────
def update_agent_task(agent_name, task_id, status):
    memory_write(f"agent:{agent_name}:current_task", task_id if status == "running" else "")
    if status == "done":
        memory_write(f"agent:{agent_name}:last_seen", datetime.now(timezone.utc).isoformat())


# ── Main Loop ─────────────────────────────────────────────────────────────────
def patrol_loop():
    """Called every PATROL_INTERVAL seconds. Fires ready nodes."""
    workflow = read_workflow()
    if not workflow.get("active"):
        log.debug("Workflow not active, skipping patrol")
        return

    snapshot = memory_snapshot()
    available = who_is_available(snapshot)
    ready = find_ready_nodes(workflow)
    running = find_running_nodes(workflow)

    fired = 0
    for node in ready:
        agent = node["assigned_to"].lower()
        if agent not in AGENT_WEBHOOKS:
            log.warning(f"Unknown agent in node {node['id']}: {agent}")
            continue

        avail, reason = available.get(agent, (False, "unknown"))
        if not avail:
            log.debug(f"Skipping {node['id']} — {agent}: {reason}")
            continue

        if node_agent_busy(workflow, agent):
            log.debug(f"Skipping {node['id']} — {agent} already running a task")
            continue

        # Fire the task
        node["status"] = "running"
        write_workflow(workflow)

        update_agent_task(agent, node["id"], "running")

        ok = fire_task(node)
        if not ok:
            node["status"] = "pending"
            update_agent_task(agent, "", "pending")
            write_workflow(workflow)
            log.error(f"Failed to fire {node['id']} to {agent}")
        else:
            fired += 1
            log.info(f"Fired {node['id']} -> {agent}")

    if fired:
        log.info(f"Patrol complete: fired {fired} tasks")


def result_loop():
    """Poll Telegram for results and advance the DAG."""
    results = poll_telegram_results()
    if not results:
        return

    workflow = read_workflow()
    if not workflow.get("active"):
        return

    for event_type, sender, *rest in results:
        if event_type == "blocker":
            blocker_text = rest[0]
            notify_robert_blocker(sender, blocker_text)
            continue

        # RESULT
        status = rest[0]   # "done" or "pass" or "fail"
        output = rest[1] if len(rest) > 1 else ""

        # Find the running node for this agent
        agent_node = None
        for n in workflow.get("nodes", []):
            if n.get("assigned_to", "").lower() == sender.lower() and n["status"] == "running":
                agent_node = n
                break

        if not agent_node:
            log.warning(f"RESULT from {sender} but no running node found")
            continue

        node_id = agent_node["id"]

        if status in ("done", "pass"):
            agent_node["status"] = "done"
            agent_node["result"] = output
            update_agent_task(sender, "", "done")

            # Auto-create QA node for commit-type nodes (agent_category=backend)
            if agent_node.get("agent_category") == "backend":
                qa_node = create_qa_node(agent_node, workflow)
                workflow["nodes"].append(qa_node)
                log.info(f"Auto-created QA node: {qa_node['id']} depending on {node_id}")

        else:  # fail
            agent_node["status"] = "failed"
            agent_node["error"] = output
            update_agent_task(sender, "", "failed")
            notify_robert_blocker(sender, f"Node {node_id} failed: {output}")

        write_workflow(workflow)
        log.info(f"RESULT [{node_id}] {sender}: {status}")


def run():
    log.info("dag_executor starting...")
    log.info(f"Workflow: {WORKFLOW_PATH}")
    log.info(f"Telegram polling: {'enabled' if TG_BASE else 'DISABLED'}")
    log.info(f"Patrol interval: {PATROL_INTERVAL}s")

    if not TG_BASE:
        log.warning("No Telegram token — set DAG_EXECUTOR_TELEGRAM_TOKEN env var")
        log.warning("RESULT detection will be disabled")

    # Verify workflow file exists
    wf = read_workflow()
    log.info(f"Workflow loaded: active={wf.get('active')}, nodes={len(wf.get('nodes', []))}")

    # Main loop
    while True:
        try:
            patrol_loop()
            result_loop()
        except Exception as e:
            log.error(f"Main loop error: {e}")

        time.sleep(PATROL_INTERVAL)


if __name__ == "__main__":
    run()
