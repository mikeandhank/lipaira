# event_bus.py - Ambient Event Queue
#
# Contract: Block 4 Item 16
# Handles external webhooks, internal skill completions, scheduled triggers
# Events persisted to DB, processed within 5 seconds

import os
import json
import threading
import time
from datetime import datetime, timedelta
from queue import Queue, Empty
from typing import Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, Future
import psycopg2
from urllib.parse import urlparse

# Configuration
MAX_CONCURRENT_HANDLERS = 10
RETRY_ATTEMPTS = 3
DEAD_LETTER_THRESHOLD = 3

class EventBus:
    """Central event bus for Lipaira."""
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.environ.get('DATABASE_URL')
        self._handlers: Dict[str, Callable] = {}
        self._queue: Queue = Queue()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._running = False
        
    def register_handler(self, event_type: str, handler: Callable):
        """Register a handler for a specific event type."""
        self._handlers[event_type] = handler
        print(f"Registered handler for event type: {event_type}")
        
    def emit(self, event_type: str, user_id: str, payload: Dict[str, Any]) -> bool:
        """Emit an event to the queue."""
        event = {
            'event_type': event_type,
            'user_id': user_id,
            'payload': payload,
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Persist to DB
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (event_type, payload, user_id, created_at)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (event_type, json.dumps(payload), user_id, event['created_at']))
            event['id'] = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            print(f"Event persisted: {event_type} (id: {event['id']})")
        except Exception as e:
            print(f"Failed to persist event: {e}")
            return False
            
        # Add to queue for async processing
        self._queue.put(event)
        return True
        
    def start(self):
        """Start the thread pool executor."""
        if self._running:
            return
        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_HANDLERS, thread_name_prefix='event_worker')
        # Start the queue consumer
        self._consumer_thread = threading.Thread(target=self._consumer, daemon=True)
        self._consumer_thread.start()
        print(f"EventBus started with ThreadPoolExecutor(max_workers={MAX_CONCURRENT_HANDLERS})")
        
    def stop(self):
        """Stop the event bus."""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=True)
        if hasattr(self, '_consumer_thread'):
            self._consumer_thread.join(timeout=5)
        print("EventBus stopped")
        
    def _consumer(self):
        """Consumer thread that pulls events from queue and dispatches to thread pool."""
        while self._running:
            try:
                event = self._queue.get(timeout=1)
                if self._executor:
                    self._executor.submit(self._process_event, event)
            except Empty:
                continue
            except Exception as e:
                print(f"Consumer error: {e}")
                
    def _process_event(self, event: Dict[str, Any]):
        """Process a single event (runs in thread pool)."""
        event_type = event.get('event_type')
        user_id = event.get('user_id')
        payload = event.get('payload', {})
        event_id = event.get('id')
        
        handler = self._handlers.get(event_type)
        if not handler:
            print(f"No handler for event type: {event_type}")
            self._update_status(event_id, 'no_handler')
            return
            
        try:
            handler(user_id, payload)
            self._update_status(event_id, 'processed')
            print(f"Event processed: {event_type}")
        except Exception as e:
            print(f"Handler failed for {event_type}: {e}")
            self._increment_failure(event_id)
            
    def _update_status(self, event_id: int, status: str):
        """Update event status in DB."""
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute("UPDATE events SET status=%s WHERE id=%s", (status, event_id))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to update status: {e}")
            
    def _increment_failure(self, event_id: int):
        """Increment failure count, move to dead letter if threshold reached."""
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE events 
                SET failure_count = COALESCE(failure_count, 0) + 1,
                    status = CASE 
                        WHEN COALESCE(failure_count, 0) + 1 >= %s THEN 'failed'
                        ELSE 'pending'
                    END
                WHERE id=%s
            """, (DEAD_LETTER_THRESHOLD, event_id))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to increment failure: {e}")
            
    def replay_pending(self):
        """Replay pending events on service restart."""
        try:
            cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, event_type, payload, user_id 
                FROM events 
                WHERE status='pending' AND created_at < %s
            """, (cutoff,))
            pending = cursor.fetchall()
            conn.close()
            
            for event in pending:
                self._queue.put({
                    'id': event[0],
                    'event_type': event[1],
                    'payload': event[2],
                    'user_id': event[3]
                })
            print(f"Replayed {len(pending)} pending events")
        except Exception as e:
            print(f"Failed to replay pending events: {e}")


# Global instance
_event_bus: Optional[EventBus] = None

def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
        _event_bus.start()
        # Register default handler stubs for each event type
        _register_default_handlers(_event_bus)
        # Replay pending events on startup
        _event_bus.replay_pending()
    return _event_bus

def _register_default_handlers(bus: EventBus):
    """Register empty handler stubs for all defined event types."""
    event_types = [
        'invoice_overdue',
        'invoice_paid', 
        'email_received',
        'calendar_conflict',
        'deal_quiet',
        'payment_received',
        'contract_expiring',
        'pattern_threshold_hit'
    ]
    for evt_type in event_types:
        bus.register_handler(evt_type, _make_stub_handler(evt_type))

def _make_stub_handler(event_type: str):
    """Create a stub handler that logs the event."""
    def stub_handler(user_id: str, payload: Dict[str, Any]):
        print(f"Handler called for {event_type} (user_id={user_id})")
    return stub_handler

def emit_event(event_type: str, user_id: str, payload: Dict[str, Any]) -> bool:
    """Convenience function to emit events."""
    return get_event_bus().emit(event_type, user_id, payload)
