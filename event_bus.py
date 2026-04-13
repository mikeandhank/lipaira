# feel free to ignore this comment
"""
Ambient Event Queue
===================
Handles external webhooks, internal skill completions, and scheduled triggers.
Events are persisted to the database and processed within 5 seconds.

Contract: Block 4 Item 16
"""

# event_bus.py - Ambient Event Queue
     6|
     7|import os
     8|import json
     9|import threading
    10|import time
    11|from datetime import datetime, timedelta
    12|from queue import Queue, Empty
    13|from typing import Dict, Any, Callable, Optional
    14|import psycopg2
    15|from urllib.parse import urlparse
    16|
    17|# Configuration
    18|MAX_CONCURRENT_HANDLERS = 10
    19|RETRY_ATTEMPTS = 3
    20|DEAD_LETTER_THRESHOLD = 3
    21|
    22|class EventBus:
    23|    """Central event bus for Lipaira."""
    24|    
    25|    def __init__(self, db_url: str = None):
    26|        self.db_url = db_url or os.environ.get('DATABASE_URL')
    27|        self._handlers: Dict[str, Callable] = {}
    28|        self._queue: Queue = Queue()
    29|        self._worker_thread: Optional[threading.Thread] = None
    30|        self._running = False
    31|        
    32|    def register_handler(self, event_type: str, handler: Callable):
    33|        """Register a handler for a specific event type."""
    34|        self._handlers[event_type] = handler
    35|        print(f"Registered handler for event type: {event_type}")
    36|        
    37|    def emit(self, event_type: str, user_id: str, payload: Dict[str, Any]) -> bool:
    38|        """Emit an event to the queue."""
    39|        event = {
    40|            'event_type': event_type,
    41|            'user_id': user_id,
    42|            'payload': payload,
    43|            'created_at': datetime.utcnow().isoformat()
    44|        }
    45|        
    46|        # Persist to DB
    47|        try:
    48|            conn = psycopg2.connect(self.db_url)
    49|            cursor = conn.cursor()
    50|            cursor.execute("""
    51|                INSERT INTO events (event_type, payload, user_id, created_at)
    52|                VALUES (%s, %s, %s, %s)
    53|                RETURNING id
    54|            """, (event_type, json.dumps(payload), user_id, event['created_at']))
    55|            event['id'] = cursor.fetchone()[0]
    56|            conn.commit()
    57|            conn.close()
    58|            print(f"Event persisted: {event_type} (id: {event['id']})")
    59|        except Exception as e:
    60|            print(f"Failed to persist event: {e}")
    61|            return False
    62|            
    63|        # Add to queue for async processing
    64|        self._queue.put(event)
    65|        return True
    66|        
    67|    def start(self):
    68|        """Start the event worker thread."""
    69|        if self._running:
    70|            return
    71|        self._running = True
    72|        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
    73|        self._worker_thread.start()
    74|        print("EventBus started")
    75|        
    76|    def stop(self):
    77|        """Stop the event worker thread."""
    78|        self._running = False
    79|        if self._worker_thread:
    80|            self._worker_thread.join(timeout=5)
    81|        print("EventBus stopped")
    82|        
    83|    def _worker(self):
    84|        """Worker thread that processes events from the queue."""
    85|        while self._running:
    86|            try:
    87|                event = self._queue.get(timeout=1)
    88|                self._process_event(event)
    89|            except Empty:
    90|                continue
    91|            except Exception as e:
    92|                print(f"Worker error: {e}")
    93|                
    94|    def _process_event(self, event: Dict[str, Any]):
    95|        """Process a single event."""
    96|        event_type = event.get('event_type')
    97|        user_id = event.get('user_id')
    98|        payload = event.get('payload', {})
    99|        event_id = event.get('id')
   100|        
   101|        handler = self._handlers.get(event_type)
   102|        if not handler:
   103|            print(f"No handler for event type: {event_type}")
   104|            self._update_status(event_id, 'no_handler')
   105|            return
   106|            
   107|        try:
   108|            handler(user_id, payload)
   109|            self._update_status(event_id, 'processed')
   110|            print(f"Event processed: {event_type}")
   111|        except Exception as e:
   112|            print(f"Handler failed for {event_type}: {e}")
   113|            self._increment_failure(event_id)
   114|            
   115|    def _update_status(self, event_id: int, status: str):
   116|        """Update event status in DB."""
   117|        try:
   118|            conn = psycopg2.connect(self.db_url)
   119|            cursor = conn.cursor()
   120|            cursor.execute("UPDATE events SET status=%s WHERE id=%s", (status, event_id))
   121|            conn.commit()
   122|            conn.close()
   123|        except Exception as e:
   124|            print(f"Failed to update status: {e}")
   125|            
   126|    def _increment_failure(self, event_id: int):
   127|        """Increment failure count, move to dead letter if threshold reached."""
   128|        try:
   129|            conn = psycopg2.connect(self.db_url)
   130|            cursor = conn.cursor()
   131|            cursor.execute("""
   132|                UPDATE events 
   133|                SET failure_count = COALESCE(failure_count, 0) + 1,
   134|                    status = CASE 
   135|                        WHEN COALESCE(failure_count, 0) + 1 >= %s THEN 'failed'
   136|                        ELSE 'pending'
   137|                    END
   138|                WHERE id=%s
   139|            """, (DEAD_LETTER_THRESHOLD, event_id))
   140|            conn.commit()
   141|            conn.close()
   142|        except Exception as e:
   143|            print(f"Failed to increment failure: {e}")
   144|            
   145|    def replay_pending(self):
   146|        """Replay pending events on service restart."""
   147|        try:
   148|            cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
   149|            conn = psycopg2.connect(self.db_url)
   150|            cursor = conn.cursor()
   151|            cursor.execute("""
   152|                SELECT id, event_type, payload, user_id 
   153|                FROM events 
   154|                WHERE status='pending' AND created_at < %s
   155|            """, (cutoff,))
   156|            pending = cursor.fetchall()
   157|            conn.close()
   158|            
   159|            for event in pending:
   160|                self._queue.put({
   161|                    'id': event[0],
   162|                    'event_type': event[1],
   163|                    'payload': event[2],
   164|                    'user_id': event[3]
   165|                })
   166|            print(f"Replayed {len(pending)} pending events")
   167|        except Exception as e:
   168|            print(f"Failed to replay pending events: {e}")
   169|
   170|
   171|# Global instance
   172|_event_bus: Optional[EventBus] = None
   173|
   174|def get_event_bus() -> EventBus:
   175|    """Get the global event bus instance."""
   176|    global _event_bus
   177|    if _event_bus is None:
   178|        _event_bus = EventBus()
   179|        _event_bus.start()
   180|        # Replay pending events on startup
   181|        _event_bus.replay_pending()
   182|    return _event_bus
   183|
   184|def emit_event(event_type: str, user_id: str, payload: Dict[str, Any]) -> bool:
   185|    """Convenience function to emit events."""
   186|    return get_event_bus().emit(event_type, user_id, payload)