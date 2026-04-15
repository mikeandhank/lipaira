import os, logging, re, requests, json, time, threading
from flask import Flask, request, jsonify
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

os.makedirs('/opt/relay/logs', exist_ok=True)

handler = RotatingFileHandler('/opt/relay/logs/relay.log', maxBytes=5*1024*1024, backupCount=3)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
log.addHandler(handler)
log.propagate = False

# ── Agent backends ────────────────────────────────────────────────────────────
AGENT_BACKENDS = {
    "robert":     "http://172.20.0.2:8100/telegram",
    "jimbojames": "http://172.19.0.2:8101/telegram",
    "bigbadinky": "http://172.18.0.2:8102/telegram",
    "patrick":    "http://172.21.0.2:8103/telegram",
    "joey":       "http://172.22.0.2:8104/telegram",
}

# ── Topic thread IDs ──────────────────────────────────────────────────────────
TOPICS = {
    "general":  None,
    "crew":     3,
    "qa":       5,
    "ops":      8,
    "research": 9,
}

# ── Patterns ─────────────────────────────────────────────────────────────────
TASK_PATTERN    = re.compile(r'^TASK\s*->\s*(\w+)',    re.IGNORECASE | re.MULTILINE)
ISSUE_PATTERN   = re.compile(r'^ISSUE\s*->\s*(\w+)',   re.IGNORECASE | re.MULTILINE)
RESULT_PATTERN  = re.compile(r'^RESULT\s*<-\s*(\w+)',  re.IGNORECASE | re.MULTILINE)
BLOCKER_PATTERN = re.compile(r'^BLOCKER\s*<-\s*(\w+)', re.IGNORECASE | re.MULTILINE)
THREAD_PATTERN  = re.compile(r'^thread:\s*(.+)$',      re.IGNORECASE | re.MULTILINE)

DAG_EXECUTOR_URL = 'http://127.0.0.1:9002'

# ── Users ─────────────────────────────────────────────────────────────────────
MICHAEL_ID    = 8643045688
GROUP_CHAT_ID = -1003995894784

RELAY_USER = {
    "id":         MICHAEL_ID,
    "first_name": "Michael",
    "username":   "mikeandhank",
    "is_bot":     False
}

# ── Dedup cache ───────────────────────────────────────────────────────────────
_seen_message_ids = {}
SEEN_TTL = 10.0

def _is_duplicate(message_id):
    now = time.time()
    expired = [k for k, v in _seen_message_ids.items() if now - v > SEEN_TTL]
    for k in expired:
        del _seen_message_ids[k]
    if message_id in _seen_message_ids:
        return True
    _seen_message_ids[message_id] = now
    return False

# ── Robert delivery ───────────────────────────────────────────────────────────
_last_robert_delivery = 0
DEDUP_WINDOW = 3.0

# ── Workflow state ────────────────────────────────────────────────────────────
WORKFLOW_FILE = "/opt/data/workflow.json"

def get_workflow_injection():
    try:
        if not os.path.exists(WORKFLOW_FILE):
            return ""
        with open(WORKFLOW_FILE) as f:
            state = json.load(f)
        if not state.get("active"):
            return ""
        waiting = [t for t in state.get("tasks", []) if t["status"] == "in_progress"]
        if not waiting:
            return ""
        lines = ["[WORKFLOW STATE]"]
        for t in waiting:
            lines.append(
                f"Waiting for RESULT from: {t['agent']} | "
                f"Task: {t['name']} | "
                f"Next: {t.get('next_agent','none')} → {t.get('next_task','')}"
            )
        lines.append("[If this message is a RESULT, fire the next task now]\n")
        return "\n".join(lines) + "\n"
    except Exception as e:
        log.warning(f"Workflow injection failed: {e}")
        return ""

def parse_thread_id(text):
    match = THREAD_PATTERN.search(text)
    if not match:
        return None
    val = match.group(1).strip()
    if val.lower() in TOPICS:
        return TOPICS[val.lower()]
    if ":" in val:
        try:
            return int(val.split(":")[-1])
        except ValueError:
            pass
    try:
        return int(val)
    except ValueError:
        return None

def build_payload(text, message_id, thread_id=None):
    msg = {
        "message_id": message_id,
        "from":       RELAY_USER,
        "chat":       {
            "id":    GROUP_CHAT_ID,
            "type":  "supergroup",
            "title": "Lipaira Dev Chat"
        },
        "date": int(time.time()),
        "text": text
    }
    if thread_id:
        msg["message_thread_id"] = thread_id
    return {"update_id": message_id, "message": msg}

def forward(agent_name, text, message_id=1, thread_id=None):
    url = AGENT_BACKENDS.get(agent_name.lower())
    if not url:
        log.warning(f"Unknown agent: {agent_name}")
        return False
    payload = build_payload(text, message_id, thread_id)
    try:
        resp = requests.post(url, json=payload, timeout=10)
        log.info(f"-> {agent_name} [thread={thread_id}]: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        log.error(f"Failed -> {agent_name}: {e}")
        return False

def deliver_to_robert(text, message_id, thread_id=None):
    global _last_robert_delivery

    def _send():
        global _last_robert_delivery
        now = time.time()
        elapsed = now - _last_robert_delivery
        if elapsed < DEDUP_WINDOW:
            wait = DEDUP_WINDOW - elapsed + 0.5
            log.info(f"Dedup wait {wait:.1f}s before delivering to Robert")
            time.sleep(wait)
        prefix = get_workflow_injection()
        full_text = prefix + text if prefix else text
        payload = build_payload(full_text, message_id, thread_id)
        try:
            resp = requests.post(AGENT_BACKENDS["robert"], json=payload, timeout=10)
            _last_robert_delivery = time.time()
            log.info(f"-> robert (delayed) [thread={thread_id}]: {resp.status_code}")
        except Exception as e:
            log.error(f"Failed -> robert: {e}")

    threading.Thread(target=_send, daemon=True).start()

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    """Receives all Telegram webhook posts — Michael's messages only."""
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"ok": True}), 200

    message_id = data["message"].get("message_id", 0)
    if _is_duplicate(message_id):
        log.info(f"Dedup drop: message_id={message_id}")
        return jsonify({"ok": True}), 200

    text      = data["message"].get("text", "")
    thread_id = parse_thread_id(text)

    # Always forward Michael's messages to Robert
    forward("robert", text, message_id, thread_id)

    # Additionally forward to target agent if TASK or ISSUE
    for pattern in [TASK_PATTERN, ISSUE_PATTERN]:
        match = pattern.search(text)
        if match:
            target = match.group(1).lower()
            if target != "robert" and target in AGENT_BACKENDS:
                forward(target, text, message_id, thread_id)
            break

    return jsonify({"ok": True}), 200


@app.route("/relay", methods=["POST"])
def receive_webhook():
    """Receives bot-to-bot messages from userbot only."""
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"ok": True}), 200

    text       = data["message"].get("text", "")
    message_id = data["message"].get("message_id", 1)
    thread_id  = parse_thread_id(text) or data["message"].get("message_thread_id")

    target        = None
    is_result    = False
    result_agent = ''

    for pattern in [TASK_PATTERN, ISSUE_PATTERN]:
        match = pattern.search(text)
        if match:
            target = match.group(1).lower()
            break

    if not target:
        for pattern in [RESULT_PATTERN, BLOCKER_PATTERN]:
            match = pattern.search(text)
            if match:
                target       = 'robert'
                is_result    = True
                result_agent = match.group(1)   # e.g. jimbojames
                break

    if target:
        if is_result:
            # Log the result event
            log.info(f'[RESULT] {result_agent} → {text[:60]}')

            # Forward to DAG executor
            try:
                dag_payload = {
                    'agent_name': result_agent,
                    'status': 'done',   # relay doesn't parse status — executor reads workflow
                    'output': text
                }
                dag_r = requests.post(
                    DAG_EXECUTOR_URL + '/result',
                    json=dag_payload,
                    timeout=5
                )
                dag_ok = dag_r.status_code == 200
                dag_resp = dag_r.json().get('ok') if dag_r.headers.get('Content-Type', '').startswith('application/json') else None
                if dag_ok and dag_resp:
                    log.info('[DAG ACK] ok')
                else:
                    log.warning(f'[DAG ERR] {dag_r.status_code}: {dag_r.text[:80]}')
            except Exception as e:
                log.error(f'[DAG ERR] POST failed: {e}')

            deliver_to_robert(text, message_id, thread_id)
        else:
            forward(target, text, message_id, thread_id)
    else:
        log.info(f"Bot message no target, dropping: {text[:60]}")

    return jsonify({"ok": True}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status":  "relay online",
        "agents":  list(AGENT_BACKENDS.keys()),
        "topics":  TOPICS,
        "version": "1.0.0-production"
    }), 200

@app.route("/workflow", methods=["GET"])
def get_workflow():
    try:
        if os.path.exists(WORKFLOW_FILE):
            with open(WORKFLOW_FILE) as f:
                return jsonify(json.load(f)), 200
        return jsonify({"active": False}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/workflow", methods=["POST"])
def update_workflow():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "No JSON"}), 400
    try:
        with open(WORKFLOW_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        log.info(f"Workflow state updated: active={data.get('active')}")
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/agents", methods=["GET"])
def list_agents():
    return jsonify({"agents": AGENT_BACKENDS}), 200

@app.route("/topics", methods=["GET"])
def list_topics():
    return jsonify({"topics": TOPICS}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)

@app.route("/github", methods=["POST"])
def github_webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "No JSON"}), 400
    try:
        ref        = data.get("ref", "")
        commits    = data.get("commits", [])
        pusher     = data.get("pusher", {}).get("name", "unknown")
        repo       = data.get("repository", {}).get("full_name", "unknown")
        compare    = data.get("compare", "")

        if not commits:
            return jsonify({"ok": True, "skipped": "no commits"}), 200

        files_changed = []
        commit_hashes = []
        for commit in commits:
            commit_hashes.append(commit.get("id", "")[:8])
            files_changed += commit.get("added", [])
            files_changed += commit.get("modified", [])
        files_changed = list(set(files_changed))

        task_text = f"""TASK -> Robert
goal: Add a QA node to the active DAG for Patrick to review a new push. Do not delegate until Patrick is available.
context: pusher={pusher} repo={repo} ref={ref} commits={", ".join(commit_hashes)} files={", ".join(files_changed) if files_changed else "see compare link"} compare={compare}
return: Confirm QA node added to DAG
thread: ops"""

        payload = build_payload(task_text, int(time.time()), TOPICS["ops"])
        resp = requests.post(AGENT_BACKENDS["robert"], json=payload, timeout=10)
        log.info(f"GitHub webhook -> Robert: {resp.status_code}")
        return jsonify({"ok": True}), 200
    except Exception as e:
        log.error(f"GitHub webhook error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
