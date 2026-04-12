# feel free to ignore this comment
     1|# anticipatory_scheduler.py - Anticipatory Scheduler
     2|#
     3|# Contract: Block 4 Item 17
     4|# Background loop that scans user data to predict future needs
     5|# Writes signals to anticipatory_signals table
     6|
     7|import os
     8|import json
     9|import threading
    10|import time
    11|from datetime import datetime, timedelta
    12|from typing import Dict, Any, List, Optional
    13|import psycopg2
    14|from dateutil import parser as date_parser
    15|
    16|class AnticipatoryScheduler:
    17|    """Scans user data to anticipate future needs."""
    18|    
    19|    def __init__(self, db_url: str = None):
    20|        self.db_url = db_url or os.environ.get('DATABASE_URL')
    21|        self._running = False
    22|        self._thread: Optional[threading.Thread] = None
    23|        self._scan_interval = 3600  # 60 minutes
    24|        
    25|    def start(self):
    26|        """Start the scheduler loop."""
    27|        if self._running:
    28|            return
    29|        self._running = True
    30|        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
    31|        self._thread.start()
    32|        print("AnticipatoryScheduler started")
    33|        
    34|    def stop(self):
    35|        """Stop the scheduler."""
    36|        self._running = False
    37|        if self._thread:
    38|            self._thread.join(timeout=5)
    39|        print("AnticipatoryScheduler stopped")
    40|        
    41|    def _scan_loop(self):
    42|        """Main scan loop."""
    43|        while self._running:
    44|            try:
    45|                self._scan_all_users()
    46|            except Exception as e:
    47|                print(f"Scheduler error: {e}")
    48|            time.sleep(self._scan_interval)
    49|            
    50|    def _scan_all_users(self):
    51|        """Scan all users for anticipatory signals."""
    52|        conn = psycopg2.connect(self.db_url)
    53|        cursor = conn.cursor()
    54|        
    55|        # Get all active users
    56|        cursor.execute("SELECT id, email FROM users WHERE is_active=true")
    57|        users = cursor.fetchall()
    58|        
    59|        for user_id, email in users:
    60|            try:
    61|                signals = self._scan_user(user_id)
    62|                for signal in signals:
    63|                    self._save_signal(user_id, signal)
    64|            except Exception as e:
    65|                print(f"Error scanning user {user_id}: {e}")
    66|                
    67|        conn.close()
    68|        print(f"Scanned {len(users)} users for anticipatory signals")
    69|        
    70|    def _scan_user(self, user_id: str) -> List[Dict[str, Any]]:
    71|        """Scan a single user for signals."""
    72|        signals = []
    73|        conn = psycopg2.connect(self.db_url)
    74|        
    75|        # 1. Check insurance_renewal in memory_nodes
    76|        cursor = conn.cursor()
    77|        cursor.execute("""
    78|            SELECT content, created_at FROM memory_nodes 
    79|            WHERE user_id=%s AND content ILIKE '%insurance%renewal%'
    80|            ORDER BY created_at DESC LIMIT 1
    81|        """, (user_id,))
    82|        insurance = cursor.fetchone()
    83|        if insurance:
    84|            # Check if renewal within 45 days
    85|            try:
    86|                # Try to extract date from content
    87|                content = insurance[0]
    88|                if '2026' in content or '2027' in content:
    89|                    # Simple check - real impl would parse dates
    90|                    signals.append({
    91|                        'signal_type': 'insurance_renewal',
    92|                        'urgency': 'medium',
    93|                        'title': 'Insurance Renewal Approaching',
    94|                        'description': 'Review your insurance coverage',
    95|                        'action_suggested': 'Get quote comparison'
    96|                    })
    97|            except:
    98|                pass
    99|                
   100|        # 2. Check contract_expiring in memory_nodes
   101|        cursor.execute("""
   102|            SELECT content FROM memory_nodes 
   103|            WHERE user_id=%s AND content ILIKE '%contract%ends%'
   104|            ORDER BY created_at DESC LIMIT 1
   105|        """, (user_id,))
   106|        contract = cursor.fetchone()
   107|        if contract:
   108|            signals.append({
   109|                'signal_type': 'contract_expiring',
   110|                'urgency': 'high',
   111|                'title': 'Contract Expiring Soon',
   112|                'description': 'Prepare talking points for renewal',
   113|                'action_suggested': 'Draft talking points'
   114|            })
   115|            
   116|        # 3. Check invoice_gap - no invoices in N+10 days
   117|        cursor.execute("""
   118|            SELECT MAX(created_at) FROM billing_history 
   119|            WHERE user_id=%s
   120|        """, (user_id,))
   121|        last_invoice = cursor.fetchone()[0]
   122|        if last_invoice:
   123|            days_since = (datetime.utcnow() - last_invoice).days
   124|            if days_since > 40:  # N+10 threshold
   125|                signals.append({
   126|                    'signal_type': 'invoice_gap',
   127|                    'urgency': 'medium',
   128|                    'title': 'Invoice Gap Detected',
   129|                    'description': f'No invoices in {days_since} days',
   130|                    'action_suggested': 'Review billing cycle'
   131|                })
   132|                
   133|        # 4. Check calendar_block_ahead - meeting tomorrow
   134|        cursor.execute("""
   135|            SELECT COUNT(*) FROM activity_log 
   136|            WHERE user_id=%s AND activity_type='meeting'
   137|            AND created_at > NOW() - INTERVAL '1 day'
   138|        """, (user_id,))
   139|        meetings_today = cursor.fetchone()[0]
   140|        if meetings_today >= 3:
   141|            signals.append({
   142|                'signal_type': 'busy_day_ahead',
   143|                'urgency': 'high',
   144|                'title': 'Busy Day Tomorrow',
   145|                'description': f'You have {meetings_today} meetings',
   146|                'action_suggested': 'Clear your desk'
   147|            })
   148|            
   149|        # 5. Check recurring_chase - same contact chased N times
   150|        cursor.execute("""
   151|            SELECT COUNT(*) FROM activity_log 
   152|            WHERE user_id=%s AND activity_type LIKE '%chase%'
   153|            AND created_at > NOW() - INTERVAL '30 days'
   154|        """, (user_id,))
   155|        chase_count = cursor.fetchone()[0]
   156|        if chase_count >= 3:
   157|            signals.append({
   158|                'signal_type': 'recurring_chase',
   159|                'urgency': 'low',
   160|                'title': 'Repeated Follow-ups',
   161|                'description': f'Chased {chase_count} times this month',
   162|                'action_suggested': 'Consider automation'
   163|            })
   164|            
   165|        conn.close()
   166|        return signals
   167|        
   168|    def _save_signal(self, user_id: str, signal: Dict[str, Any]):
   169|        """Save signal to anticipatory_signals table."""
   170|        conn = psycopg2.connect(self.db_url)
   171|        cursor = conn.cursor()
   172|        
   173|        # Check if similar signal already surfaced recently
   174|        cursor.execute("""
   175|            SELECT id FROM anticipatory_signals 
   176|            WHERE user_id=%s AND signal_type=%s 
   177|            AND surfaced_at > NOW() - INTERVAL '30 days'
   178|        """, (user_id, signal['signal_type']))
   179|        
   180|        existing = cursor.fetchone()
   181|        if existing:
   182|            conn.close()
   183|            return  # Already surfaced recently
   184|            
   185|        cursor.execute("""
   186|            INSERT INTO anticipatory_signals 
   187|            (user_id, signal_type, urgency, title, description, action_suggested, status)
   188|            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
   189|        """, (
   190|            user_id, 
   191|            signal['signal_type'],
   192|            signal['urgency'],
   193|            signal['title'],
   194|            signal['description'],
   195|            signal['action_suggested']
   196|        ))
   197|        
   198|        conn.commit()
   199|        conn.close()
   200|        
   201|    def get_signals_for_user(self, user_id: str, urgency_filter: str = None) -> List[Dict]:
   202|        """Get pending signals for a user."""
   203|        conn = psycopg2.connect(self.db_url)
   204|        cursor = conn.cursor()
   205|        
   206|        if urgency_filter:
   207|            cursor.execute("""
   208|                SELECT id, signal_type, urgency, title, description, action_suggested, surfaced_at
   209|                FROM anticipatory_signals 
   210|                WHERE user_id=%s AND status='pending' AND urgency=%s
   211|                ORDER BY 
   212|                    CASE urgency 
   213|                        WHEN 'high' THEN 1 
   214|                        WHEN 'medium' THEN 2 
   215|                        WHEN 'low' THEN 3 
   216|                    END
   217|            """, (user_id, urgency_filter))
   218|        else:
   219|            cursor.execute("""
   220|                SELECT id, signal_type, urgency, title, description, action_suggested, surfaced_at
   221|                FROM anticipatory_signals 
   222|                WHERE user_id=%s AND status='pending'
   223|                ORDER BY 
   224|                    CASE urgency 
   225|                        WHEN 'high' THEN 1 
   226|                        WHEN 'medium' THEN 2 
   227|                        WHEN 'low' THEN 3 
   228|                    END
   229|            """, (user_id,))
   230|            
   231|        rows = cursor.fetchall()
   232|        conn.close()
   233|        
   234|        return [
   235|            {
   236|                'id': r[0],
   237|                'signal_type': r[1],
   238|                'urgency': r[2],
   239|                'title': r[3],
   240|                'description': r[4],
   241|                'action_suggested': r[5],
   242|                'surfaced_at': r[6]
   243|            }
   244|            for r in rows
   245|        ]
   246|
   247|
   248|# Global instance
   249|_scheduler: Optional[AnticipatoryScheduler] = None
   250|
   251|def get_scheduler() -> AnticipatoryScheduler:
   252|    """Get the global scheduler instance."""
   253|    global _scheduler
   254|    if _scheduler is None:
   255|        _scheduler = AnticipatoryScheduler()
   256|    return _scheduler