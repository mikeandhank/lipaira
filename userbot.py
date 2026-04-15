import asyncio
import logging
import re
import time
import requests
from telethon import TelegramClient, events

API_ID = 30418953
API_HASH = "f56e4d0a53a85d5ce0a3d481dfa3184d"
GROUP_CHAT_ID = -1003995894784
RELAY_URL = "http://172.17.0.1:9000/relay"

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler('/opt/relay/logs/userbot.log'), logging.StreamHandler()])
log = logging.getLogger(__name__)

client = TelegramClient('/opt/relay/userbot.session', API_ID, API_HASH)

TASK_PATTERN    = re.compile(r'^TASK\s*->\s*(\w+)',    re.IGNORECASE | re.MULTILINE)
ISSUE_PATTERN   = re.compile(r'^ISSUE\s*->\s*(\w+)',   re.IGNORECASE | re.MULTILINE)
RESULT_PATTERN  = re.compile(r'^RESULT\s*<-\s*(\w+)',  re.IGNORECASE | re.MULTILINE)
BLOCKER_PATTERN = re.compile(r'^BLOCKER\s*<-\s*(\w+)', re.IGNORECASE | re.MULTILINE)

KNOWN_AGENTS = {"robert", "jimbojames", "bigbadinky", "patrick", "joey", "marcus"}

_seen_message_ids = set()
_last_result_time = {}
RESULT_COOLDOWN = 10

@client.on(events.NewMessage(chats=GROUP_CHAT_ID))
async def handler(event):
    sender = await event.get_sender()
    text = event.raw_text or ""

    log.info(f"DEBUG seen: from={getattr(sender, 'username', 'unknown')} bot={getattr(sender, 'bot', False)} text={text[:60]!r}")

    if not getattr(sender, 'bot', False):
        return

    if event.id in _seen_message_ids:
        return
    _seen_message_ids.add(event.id)
    if len(_seen_message_ids) > 1000:
        _seen_message_ids.clear()

    thread_id = None
    reply_to = event.message.reply_to
    if reply_to:
        if hasattr(reply_to, 'reply_to_top_id') and reply_to.reply_to_top_id:
            thread_id = reply_to.reply_to_top_id
        elif hasattr(reply_to, 'reply_to_msg_id'):
            thread_id = reply_to.reply_to_msg_id

    target = None
    inbound = False

    for pattern in [TASK_PATTERN, ISSUE_PATTERN]:
        match = pattern.search(text)
        if match:
            target = match.group(1).lower()
            inbound = False
            break

    if not target:
        for pattern in [RESULT_PATTERN, BLOCKER_PATTERN]:
            match = pattern.search(text)
            if match:
                sender_key = (sender.username or "").lower()
                last = _last_result_time.get(sender_key, 0)
                if time.time() - last < RESULT_COOLDOWN:
                    log.info(f"Cooldown: dropping repeated RESULT from {sender.username}")
                    return
                _last_result_time[sender_key] = time.time()
                target = "robert"
                inbound = True
                break

    if not target:
        return

    if not inbound and target not in KNOWN_AGENTS:
        log.info(f"Ignoring unknown target: {target}")
        return

    if not inbound:
        sender_key = (sender.username or "").lower().replace("_bot","").replace("roflbot","")
        if sender_key == target:
            log.info(f"Skipping self-relay: {sender.username} -> {target}")
            return

    log.info(f"Relaying [{sender.username}] -> [{target}] [thread={thread_id}]: {text[:80]}")

    payload = {
        "update_id": event.id,
        "message": {
            "message_id": event.id,
            "from": {
                "id": 8643045688,
                "first_name": "Michael",
                "username": "mikeandhank",
                "is_bot": False
            },
            "chat": {
                "id": GROUP_CHAT_ID,
                "type": "supergroup",
                "title": "Lipaira Crew"
            },
            "date": int(event.date.timestamp()),
            "text": text,
            "message_thread_id": thread_id
        }
    }

    try:
        resp = requests.post(RELAY_URL, json=payload, timeout=10)
        log.info(f"Relay response: {resp.status_code}")
    except Exception as e:
        log.error(f"Relay forward failed: {e}")

async def main():
    log.info("Userbot starting...")
    await client.start()
    me = await client.get_me()
    log.info(f"Userbot running as: {me.first_name}")
    log.info(f"Watching group: {GROUP_CHAT_ID} — all threads")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
