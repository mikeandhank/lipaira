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

from flask import Flask, request, jsonify

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [DAG] %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('/opt/relay/logs/dag_executor.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger('dag_executor')

# ── Constants ─────────────────────────────────────────────────────────────────
WORKFLOW_PATH = '/opt/data/workflow.json'
MEMORY_URL    = 'http://172.20.0.1:9001'
MEMORY_SECRET = '38467057af586e03135a309f27c62f1737b0f1f595e91713cc32f45aa310f78c'

TELEGRAM_TOKEN=os.environ.get('DAG_EXECUTOR_TELEGRAM_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN', '')
GROUP_CHAT_ID  = -1003995894784
CREW_THREAD    = 3
QA_THREAD      = 5

AGENT_WEBHOOKS = {
    'robert':     'http://172.20.0.2:8100/telegram',
    'jimbojames': 'http://172.19.0.2:8101/telegram',
    'bigbadinky': 'http://172.18.0.2:8102/telegram',
    'patrick':    'http://172.21.0.2:8103/telegram',
    'joey':       'http://172.22.0.2:8104/telegram',
}

PATROL_INTERVAL       = 10
TELEGRAM_POLL_INTERVAL = 5
RESULT_COOLDOWN       = 10

RESULT_PATTERN  = re.compile(r'^RESULT\s*<-\s*(\w+)',  re.IGNORECASE | re.MULTILINE)
BLOCKER_PATTERN = re.compile(r'^BLOCKER\s*<-\s*(\w+)', re.IGNORECASE | re.MULTILINE)

# ── Flask App ──────────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.route('/result', methods=['POST'])
def http_result():
    """
    Accept RESULT/BLOCKER from relay.
    Payload: {agent_name, node_id, status, output}
    Returns: {ok: true, node_id, agent_name} or {ok: false, error}
    """
    try:
        body = request.get_json()
        if not body:
            return jsonify({'ok': False, 'error': 'no JSON body'}), 400

        agent_name = body.get('agent_name', '').strip()
        status     = body.get('status', '').strip()
        output     = body.get('output', '').strip()
        node_id    = body.get('node_id')   # optional — if None, find running node for agent

        if not agent_name or not status:
            return jsonify({'ok': False, 'error': 'agent_name and status required'}), 400

        workflow = read_workflow()
        if not workflow.get('active'):
            return jsonify({'ok': False, 'error': 'workflow not active'}), 409

        apply_result_event(workflow, agent_name, status, output, node_id=node_id)
        write_workflow(workflow)

        # Find the node we just updated
        resolved_node_id = node_id
        if not resolved_node_id:
            for n in workflow.get('nodes', []):
                if (n.get('assigned_to') or '').lower() == agent_name.lower():
                    if n['status'] in ('done', 'failed'):
                        resolved_node_id = n['id']
                        break

        log.info('[DAG HTTP] result accepted — %s/%s -> %s', agent_name, resolved_node_id, status)
        return jsonify({'ok': True, 'agent_name': agent_name, 'node_id': resolved_node_id})

    except Exception as e:
        log.error('[DAG HTTP] /result error: %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/status', methods=['GET'])
def http_status():
    """Return workflow node counts."""
    try:
        workflow = read_workflow()
        nodes = workflow.get('nodes', [])
        statuses = {}
        for n in nodes:
            s = n.get('status', 'unknown')
            statuses[s] = statuses.get(s, 0) + 1
        return jsonify({
            'total':    len(nodes),
            'done':     statuses.get('done', 0),
            'ready':    statuses.get('ready', 0),
            'running':  statuses.get('running', 0),
            'failed':   statuses.get('failed', 0),
            'cancelled': statuses.get('cancelled', 0),
        })
    except Exception as e:
        log.error('[DAG HTTP] /status error: %s', e)
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Telegram Bot API ───────────────────────────────────────────────────────────
TG_BASE = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}' if TELEGRAM_TOKEN else None

if not TG_BASE:
    log.warning('DAG_EXECUTOR_TELEGRAM_TOKEN not set — Telegram polling disabled')


def tg_get_updates(offset=0, timeout=60):
    if not TG_BASE:
        return []
    try:
        r = requests.get(f'{TG_BASE}/getUpdates', params={
            'offset': offset,
            'timeout': timeout,
            'allowed_updates': 'message'
        }, timeout=timeout + 5)
        data = r.json()
        return data.get('result', []) if data.get('ok') else []
    except Exception as e:
        log.error('Telegram getUpdates failed: %s', e)
        return []


def tg_send_message(text, chat_id=GROUP_CHAT_ID, thread_id=None):
    if not TG_BASE:
        log.warning('TG not configured, would send: %s', text[:80])
        return
    payload = {'chat_id': chat_id, 'text': text}
    if thread_id:
        payload['message_thread_id'] = thread_id
    try:
        r = requests.post(f'{TG_BASE}/sendMessage', json=payload, timeout=10)
        resp = r.json()
        if not resp.get('ok'):
            log.error('TG send failed: %s', resp)
        else:
            log.info('TG send ok: msg_id=%s', resp.get('result', {}).get('message_id'))
    except Exception as e:
        log.error('TG send error: %s', e)


# ── Memory ─────────────────────────────────────────────────────────────────────
def memory_snapshot():
    try:
        req = Request(MEMORY_URL + '/memory/snapshot', headers={
            'X-Memory-Secret': MEMORY_SECRET
        })
        with urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        log.error('Memory snapshot failed: %s', e)
        return {'memory': {}}


def memory_write(key, value):
    try:
        body = json.dumps({'writes': [{'key': key, 'value': value}]}).encode()
        req = Request(
            MEMORY_URL + '/memory/bulk',
            data=body,
            headers={'X-Memory-Secret': MEMORY_SECRET, 'Content-Type': 'application/json'},
            method='POST'
        )
        urlopen(req, timeout=5)
    except Exception as e:
        log.error('Memory write failed (%s): %s', key, e)


# ── Agent Availability ─────────────────────────────────────────────────────────
def is_agent_available(agent_name, snapshot, workflow=None):
    """
    Returns (True, 'available') if agent can accept new work.
    
    An agent with a stale current_task in memory (from an old/abandoned DAG run)
    is treated as available if that task is not a running node in the workflow.
    
    The 5-minute heartbeat check only applies when the agent actually has a running
    node — a stale heartbeat on an idle agent is irrelevant.
    """
    mem = snapshot.get('memory', {})
    current_task_raw = (mem.get(f'agent:{agent_name}:current_task', {}) or {}).get('value')
    current_task = current_task_raw if current_task_raw else ''
    last_seen_raw = (mem.get(f'agent:{agent_name}:last_seen', {}) or {}).get('value')
    last_seen_str = last_seen_raw if last_seen_raw else ''

    # Check if agent has a live running node in the workflow
    has_running_node = False
    if workflow is not None and node_agent_busy(workflow, agent_name, snapshot):
        has_running_node = True

    # If agent has a current_task in memory, verify it's actually running
    if current_task and current_task.lower() not in ('null', 'none', ''):
        if has_running_node:
            return False, f'busy: {current_task}'
        # current_task exists in memory but not in workflow as running → stale
        log.debug('Agent %s has stale current_task=%s — treating as available', agent_name, current_task)

    # If agent has no running node in workflow, they're eligible — heartbeat age doesn't matter
    if not has_running_node:
        return True, 'available'

    # Agent has a running node — check heartbeat to confirm they're alive
    if not last_seen_str:
        return False, 'no heartbeat'

    try:
        last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
        age = datetime.now(timezone.utc) - last_seen
        if age.total_seconds() > 300:
            return False, f'stale: {age.total_seconds():.0f}s old'
    except Exception as e:
        return False, f'bad timestamp: {last_seen_str}'

    return True, 'available'


def who_is_available(snapshot, workflow=None):
    available = {}
    for name in AGENT_WEBHOOKS:
        avail, reason = is_agent_available(name, snapshot, workflow)
        available[name] = (avail, reason)
    return available


# ── Workflow ───────────────────────────────────────────────────────────────────
def read_workflow():
    try:
        with open(WORKFLOW_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {'active': False, 'nodes': []}
    except Exception as e:
        log.error('Workflow read failed: %s', e)
        return {'active': False, 'nodes': []}


def write_workflow(state):
    try:
        with open(WORKFLOW_PATH, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log.error('Workflow write failed: %s', e)


def get_node(workflow, node_id):
    for n in workflow.get('nodes', []):
        if n['id'] == node_id:
            return n
    return None


def node_status(workflow, node_id):
    n = get_node(workflow, node_id)
    return n['status'] if n else None


def all_dependencies_done(workflow, node):
    for dep_id in node.get('depends_on', []):
        if node_status(workflow, dep_id) != 'done':
            return False
    return True


def find_ready_nodes(workflow):
    ready = []
    for n in workflow.get('nodes', []):
        if n['status'] != 'pending':
            continue
        if all_dependencies_done(workflow, n):
            ready.append(n)
    log.info('find_ready: %d nodes ready — %s', len(ready), [n['id'] for n in ready])
    return ready


def find_running_nodes(workflow):
    return [n for n in workflow.get('nodes', []) if n['status'] == 'running']


def node_agent_busy(workflow, agent_name, snapshot=None):
    """Returns True if agent has a running node in workflow AND is still alive (fresh heartbeat).
    If the running node exists but the agent's last_seen is stale, the node is stuck — return False
    so the patrol loop can fire new tasks to this agent."""
    from datetime import datetime, timezone
    for n in workflow.get('nodes', []):
        if (n.get('assigned_to') or '').lower() == agent_name.lower() and n['status'] == 'running':
            # Agent has a running node — check if they're actually alive
            if snapshot:
                last_seen_str = snapshot.get('memory', {}).get(f'agent:{agent_name}:last_seen', {}).get('value', '')
                if last_seen_str:
                    try:
                        ts = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                        age = (datetime.now(timezone.utc) - ts).total_seconds()
                        if age > 300:  # stale — node is stuck, allow new tasks
                            log.debug('Agent %s has stale running node, treating as available', agent_name)
                            return False
                    except Exception:
                        pass
            return True
    return False


# ── TASK Firing ────────────────────────────────────────────────────────────────
def format_task_message(node):
    files = node.get('context', {}).get('files', [])
    notes = node.get('context', {}).get('notes', '')
    spec_ref = node.get('context', {}).get('spec_ref', '')

    lines = [
        "TASK -> " + node['assigned_to'],
        "goal: " + node['description'],
        "context: " + spec_ref,
        ("files: " + ', '.join(files)) if files else '',
        ("notes: " + notes) if notes else '',
        "return: RESULT <- " + node['assigned_to'] + ". Status: done or fail. Output: [summary]. Commit: [hash]. Thread: crew.",
        "thread: crew"
    ]
    return '\n'.join([l for l in lines if l.split(': ', 1)[-1].strip()])


def fire_task(node, workflow, thread_id=CREW_THREAD):
    """Fire a task by posting the formatted TASK message to the crew group via Telegram bot.

    Stamps node['fired_at'] before writing the workflow to disk so the timestamp
    is persisted and can be used by patrol_loop to detect stale running nodes.
    """
    # Route Patrick's QA tasks to the QA thread
    if (node.get('assigned_to') or '').lower() == 'patrick':
        thread_id = QA_THREAD
    try:
        # Stamp fired_at BEFORE writing workflow (enables patrol_loop stale-node detection)
        node['fired_at'] = datetime.now(timezone.utc).isoformat()
        node['status'] = 'running'
        write_workflow(workflow)

        message = format_task_message(node)
        tg_send_message(message, thread_id=thread_id)
        log.info('FIRE [%s] -> %s: telegram sent', node['id'], node['assigned_to'])
        return True
    except Exception as e:
        log.error('FIRE [%s] failed: %s', node['id'], e)
        return False


# ── QA Node Auto-creation ──────────────────────────────────────────────────────
def create_qa_node(commit_node, workflow):
    """
    Create a QA review node for a backend commit-type node.

    Deduplication: before creating, scans existing nodes for any node where
    (a) depends_on contains the same source_id, AND
    (b) node id contains '_qa' or '_alt'
    If found, returns None to skip creating a duplicate QA node.
    """
    src_id = commit_node['id']
    # Deduplication: skip if a QA variant for this commit already exists
    for n in workflow.get('nodes', []):
        deps = n.get('depends_on', [])
        if src_id in deps and ('_qa' in n['id'] or '_alt' in n['id']):
            log.debug('QA node for %s already exists (%s) — skipping', src_id, n['id'])
            return None

    node_id_base = commit_node['id'].replace('_c_', '_qa_')

    existing_ids = {n['id'] for n in workflow['nodes']}
    qa_id = node_id_base
    counter = 1
    while qa_id in existing_ids:
        qa_id = f'{node_id_base}_alt{counter}'
        counter += 1

    files = commit_node.get('context', {}).get('files', [])
    qa_node = {
        'id': qa_id,
        'description': 'QA review for ' + commit_node['description'],
        'agent_category': 'qa',
        'assigned_to': 'Patrick',
        'depends_on': [commit_node['id']],
        'status': 'pending',
        'context': {
            'spec_ref': commit_node.get('context', {}).get('spec_ref', ''),
            'files': files,
            'patterns': [],
            'notes': 'QA review: ' + (files[0] if files else 'unknown file') + '. Verify the docstrings are accurate and complete.'
        },
        'result': None,
        'error': None
    }
    return qa_node


# ── Result Event Processor ─────────────────────────────────────────────────────
def apply_result_event(workflow, agent_name, status, output, node_id=None):
    """
    Process a single RESULT or BLOCKER event.
    Mutates workflow in-place. Calls update_agent_task() and notify_robert_blocker().
    If node_id is None, finds the running node for agent_name.
    Returns the updated workflow.
    """
    # Find the target node
    agent_node = None
    if node_id:
        agent_node = get_node(workflow, node_id)
    else:
        for n in workflow.get('nodes', []):
            if (n.get('assigned_to') or '').lower() == agent_name.lower() and n['status'] == 'running':
                agent_node = n
                break

    if not agent_node:
        log.warning('No running node found for %s', agent_name)
        return workflow

    resolved_node_id = agent_node['id']

    if status in ('done', 'pass'):
        agent_node['status'] = 'done'
        agent_node['result'] = output
        update_agent_task(agent_name, '', 'done')

        # Auto-create QA node for backend commit-type nodes
        if agent_node.get('agent_category') == 'backend':
            qa_node = create_qa_node(agent_node, workflow)
            if qa_node is not None:
                workflow['nodes'].append(qa_node)
                log.info('Auto-created QA node: %s depending on %s', qa_node['id'], resolved_node_id)

        log.info('RESULT [%s] %s: %s', resolved_node_id, agent_name, status)

    else:  # fail / blocker
        agent_node['status'] = 'failed'
        agent_node['error'] = output
        update_agent_task(agent_name, '', 'failed')
        notify_robert_blocker(agent_name, 'Node ' + resolved_node_id + ' failed: ' + output)
        log.info('FAIL [%s] %s: %s', resolved_node_id, agent_name, output[:80])

    return workflow


# ── Result Detection (Telegram polling) ────────────────────────────────────────
_last_result_processed = {}
_last_tg_update_id = 0


def poll_telegram_results():
    """
    Poll Telegram for RESULT/BLOCKER messages from crew thread.
    Returns list of (event_type, sender, status, output) tuples.
    event_type: 'result' or 'blocker'
    """
    global _last_tg_update_id
    results = []

    if not TG_BASE:
        return results

    try:
        updates = tg_get_updates(offset=_last_tg_update_id + 1, timeout=TELEGRAM_POLL_INTERVAL)
    except Exception as e:
        log.error('Telegram poll failed: %s', e)
        return results

    for update in updates:
        msg = update.get('message', {})
        update_id = update.get('update_id', 0)
        _last_tg_update_id = max(_last_tg_update_id, update_id)

        chat = msg.get('chat', {})
        if chat.get('id') != GROUP_CHAT_ID:
            continue

        thread_id = msg.get('message_thread_id')
        if thread_id != CREW_THREAD:
            continue

        sender = msg.get('from', {})
        if sender.get('is_bot'):
            text = msg.get('text', '')
        else:
            continue

        # Detect RESULT
        r_match = RESULT_PATTERN.search(text)
        if r_match:
            sender_name = r_match.group(1).lower()
            now = time.time()
            last = _last_result_processed.get(sender_name, 0)
            if now - last < RESULT_COOLDOWN:
                log.debug('Result cooldown skip: %s', sender_name)
                continue
            _last_result_processed[sender_name] = now

            evt_status = 'done'
            if 'Status: fail' in text or 'Status: failed' in text:
                evt_status = 'fail'
            elif 'Status: pass' in text:
                evt_status = 'pass'

            output = ''
            for line in text.split('\n'):
                if line.startswith('Output:'):
                    output = line.split('Output:', 1)[1].strip()
                    break

            results.append(('result', sender_name, evt_status, output))
            continue

        # Detect BLOCKER
        b_match = BLOCKER_PATTERN.search(text)
        if b_match:
            sender_name = b_match.group(1).lower()
            blocker_msg = text
            results.append(('blocker', sender_name, blocker_msg))

    return results


# ── Blockers ───────────────────────────────────────────────────────────────────
def notify_robert_blocker(agent_name, blocker_text):
    msg = (
        'BLOCKER received from ' + agent_name + ':\n\n'
        + blocker_text + '\n\n'
        + 'Review and decide: retry, reassign, or skip the node.'
    )
    tg_send_message(msg, thread_id=CREW_THREAD)
    log.warning('BLOCKER from %s: %s', agent_name, blocker_text[:100])


# ── Memory Update Helpers ───────────────────────────────────────────────────────
def update_agent_task(agent_name, task_id, status):
    memory_write('agent:' + agent_name + ':current_task', task_id if status == 'running' else '')
    if status == 'done':
        memory_write('agent:' + agent_name + ':last_seen', datetime.now(timezone.utc).isoformat())


# ── Main Loop ─────────────────────────────────────────────────────────────────
def patrol_loop():
    """Patrol the workflow, fire ready nodes to available agents.

    Each patrol cycle:
    1. Reset any running node whose fired_at timestamp is older than TIMEOUT
       seconds (600s default). This catches agents that vanished without
       sending a RESULT, leaving their node stuck in 'running' forever.
    2. Ghost guard: scan for a second 'running' entry for the same agent and
       reset it before assigning new work.
    3. Stamp node['fired_at'] in fire_task() BEFORE write_workflow() so the
       timeout safety net can detect future stalls.
    """
    TIMEOUT = 600  # seconds before a running node is considered stale

    workflow = read_workflow()
    if not workflow.get('active'):
        log.debug('Workflow not active, skipping patrol')
        return

    snapshot = memory_snapshot()
    available = who_is_available(snapshot, workflow)
    avail_summary = {k: v[1] for k, v in available.items()}

    # ── BUG 1: Timeout safety net — reset stale running nodes ─────────────────
    now = datetime.now(timezone.utc)
    for n in workflow.get('nodes', []):
        if n['status'] == 'running' and 'fired_at' in n:
            try:
                fired_time = datetime.fromisoformat(n['fired_at'].replace('Z', '+00:00'))
                age = (now - fired_time).total_seconds()
                if age > TIMEOUT:
                    log.warning('Running node %s timed out after %ds — reset to pending', n['id'], int(age))
                    n['status'] = 'pending'
                    n['assigned_to'] = None
                    n.pop('fired_at', None)
                    update_agent_task(n.get('assigned_to', ''), '', 'pending')
            except Exception as e:
                log.debug('Could not parse fired_at for %s: %s', n['id'], e)
    write_workflow(workflow)
    # ─────────────────────────────────────────────────────────────────────────

    ready = find_ready_nodes(workflow)
    log.info('patrol: %d ready, agents avail=%s', len(ready), avail_summary)
    fired = 0

    for node in ready:
        agent = (node.get('assigned_to') or '').lower()
        if not agent:
            log.warning('Skipping %s — no assigned_to', node['id'])
            continue
        if agent not in AGENT_WEBHOOKS:
            log.warning('Unknown agent in node %s: %s', node['id'], agent)
            continue

        avail, reason = available.get(agent, (False, 'unknown'))
        if not avail:
            log.debug('Skipping %s — %s: %s', node['id'], agent, reason)
            continue

        if node_agent_busy(workflow, agent, snapshot):
            log.debug('Skipping %s — %s already running a task', node['id'], agent)
            continue

        # ── BUG 1: Ghost node guard — scan ALL running nodes for this agent ─────
        for other in workflow.get('nodes', []):
            if other['id'] != node['id'] and other.get('assigned_to', '').lower() == agent and other['status'] == 'running':
                log.warning('Ghost node %s for %s detected — resetting', other['id'], agent)
                other['status'] = 'pending'
                other['assigned_to'] = None
                other.pop('fired_at', None)
                update_agent_task(agent, '', 'pending')
        # ─────────────────────────────────────────────────────────────────────────

        update_agent_task(agent, node['id'], 'running')

        ok = fire_task(node, workflow)
        if not ok:
            node['status'] = 'pending'
            update_agent_task(agent, '', 'pending')
            write_workflow(workflow)
            log.error('Failed to fire %s to %s', node['id'], agent)
        else:
            fired += 1
            log.info('Fired %s -> %s', node['id'], agent)

    if fired:
        log.info('Patrol complete: fired %d tasks', fired)


def result_loop():
    """Poll Telegram for results and advance the DAG."""
    results = poll_telegram_results()
    if not results:
        return

    workflow = read_workflow()
    if not workflow.get('active'):
        return

    for event_type, sender, *rest in results:
        if event_type == 'blocker':
            blocker_text = rest[0]
            notify_robert_blocker(sender, blocker_text)
            continue

        # RESULT
        status = rest[0]
        output = rest[1] if len(rest) > 1 else ''

        apply_result_event(workflow, sender, status, output, node_id=None)
        write_workflow(workflow)


def run():
    log.info('dag_executor starting...')
    log.info('Workflow: %s', WORKFLOW_PATH)
    log.info('Telegram polling: %s', 'enabled' if TG_BASE else 'DISABLED')
    log.info('Patrol interval: %ds', PATROL_INTERVAL)
    log.info('HTTP endpoints: 127.0.0.1:9002')

    if not TG_BASE:
        log.warning('No Telegram token — set DAG_EXECUTOR_TELEGRAM_TOKEN env var')
        log.warning('RESULT detection will be disabled')

    wf = read_workflow()
    log.info('Workflow loaded: active=%s, nodes=%d', wf.get('active'), len(wf.get('nodes', [])))

    # Start Flask in daemon thread
    threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=9002, debug=False, use_reloader=False),
        daemon=True
    ).start()
    log.info('[HTTP] /result and /status listening on 127.0.0.1:9002')

    # Main loop
    while True:
        try:
            patrol_loop()
            result_loop()
        except Exception as e:
            import traceback
            log.error('Main loop error: %s', e)
            log.error('Trace: %s', traceback.format_exc())

        time.sleep(PATROL_INTERVAL)


if __name__ == '__main__':
    run()