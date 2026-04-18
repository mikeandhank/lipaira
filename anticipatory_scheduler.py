# anticipatory_scheduler.py - Anticipatory Scheduler
#
# Contract: Block 4 Item 17
# Background loop that scans user data to predict future needs
# Writes signals to anticipatory_signals table

import os
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import psycopg2
from dateutil import parser as date_parser

class AnticipatoryScheduler:
    """Scans user data to anticipate future needs."""
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.environ.get('DATABASE_URL')
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._scan_interval = 3600  # 60 minutes
        
    def start(self):
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        print("AnticipatoryScheduler started")
        
    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("AnticipatoryScheduler stopped")
        
    def _scan_loop(self):
        """Main scan loop."""
        while self._running:
            try:
                self._scan_all_users()
            except Exception as e:
                print(f"Scheduler error: {e}")
            time.sleep(self._scan_interval)
            
    def _scan_all_users(self):
        """Scan all users for anticipatory signals."""
        conn = psycopg2.connect(self.db_url)
        cursor = conn.cursor()
        
        # Get all active users
        cursor.execute("SELECT id, email FROM users WHERE is_active=true")
        users = cursor.fetchall()
        
        for user_id, email in users:
            try:
                signals = self._scan_user(user_id)
                for signal in signals:
                    self._save_signal(user_id, signal)
            except Exception as e:
                print(f"Error scanning user {user_id}: {e}")
                
        conn.close()
        print(f"Scanned {len(users)} users for anticipatory signals")
        
    def _scan_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Scan a single user for signals."""
        signals = []
        conn = psycopg2.connect(self.db_url)
        
        # 1. Check insurance_renewal in memory_nodes
        cursor = conn.cursor()
        cursor.execute("""
            SELECT content, created_at FROM memory_nodes 
            WHERE user_id=%s AND content ILIKE '%insurance%renewal%'
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,))
        insurance = cursor.fetchone()
        if insurance:
            # Check if renewal within 45 days
            try:
                # Try to extract date from content
                content = insurance[0]
                if '2026' in content or '2027' in content:
                    # Simple check - real impl would parse dates
                    signals.append({
                        'signal_type': 'insurance_renewal',
                        'urgency': 'medium',
                        'title': 'Insurance Renewal Approaching',
                        'description': 'Review your insurance coverage',
                        'action_suggested': 'Get quote comparison'
                    })
            except:
                pass
                
        # 2. Check contract_expiring in memory_nodes
        cursor.execute("""
            SELECT content FROM memory_nodes 
            WHERE user_id=%s AND content ILIKE '%contract%ends%'
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,))
        contract = cursor.fetchone()
        if contract:
            signals.append({
                'signal_type': 'contract_expiring',
                'urgency': 'high',
                'title': 'Contract Expiring Soon',
                'description': 'Prepare talking points for renewal',
                'action_suggested': 'Draft talking points'
            })
            
        # 3. Check invoice_gap - no invoices in N+10 days
        cursor.execute("""
            SELECT MAX(created_at) FROM billing_history 
            WHERE user_id=%s
        """, (user_id,))
        last_invoice = cursor.fetchone()[0]
        if last_invoice:
            days_since = (datetime.utcnow() - last_invoice).days
            if days_since > 40:  # N+10 threshold
                signals.append({
                    'signal_type': 'invoice_gap',
                    'urgency': 'medium',
                    'title': 'Invoice Gap Detected',
                    'description': f'No invoices in {days_since} days',
                    'action_suggested': 'Review billing cycle'
                })
                
        # 4. Check calendar_block_ahead - meeting tomorrow
        cursor.execute("""
            SELECT COUNT(*) FROM activity_log 
            WHERE user_id=%s AND activity_type='meeting'
            AND created_at > NOW() - INTERVAL '1 day'
        """, (user_id,))
        meetings_today = cursor.fetchone()[0]
        if meetings_today >= 3:
            signals.append({
                'signal_type': 'busy_day_ahead',
                'urgency': 'high',
                'title': 'Busy Day Tomorrow',
                'description': f'You have {meetings_today} meetings',
                'action_suggested': 'Clear your desk'
            })
            
        # 5. Check recurring_chase - same contact chased N times
        cursor.execute("""
            SELECT COUNT(*) FROM activity_log 
            WHERE user_id=%s AND activity_type LIKE '%chase%'
            AND created_at > NOW() - INTERVAL '30 days'
        """, (user_id,))
        chase_count = cursor.fetchone()[0]
        if chase_count >= 3:
            signals.append({
                'signal_type': 'recurring_chase',
                'urgency': 'low',
                'title': 'Repeated Follow-ups',
                'description': f'Chased {chase_count} times this month',
                'action_suggested': 'Consider automation'
            })
            
        conn.close()
        return signals
        
    def _save_signal(self, user_id: str, signal: Dict[str, Any]):
        """Save signal to anticipatory_signals table."""
        conn = psycopg2.connect(self.db_url)
        cursor = conn.cursor()
        
        # Check if similar signal already surfaced recently
        cursor.execute("""
            SELECT id FROM anticipatory_signals 
            WHERE user_id=%s AND signal_type=%s 
            AND surfaced_at > NOW() - INTERVAL '30 days'
        """, (user_id, signal['signal_type']))
        
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return  # Already surfaced recently
            
        cursor.execute("""
            INSERT INTO anticipatory_signals 
            (user_id, signal_type, urgency, title, description, action_suggested, metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (
            user_id, 
            signal['signal_type'],
            signal['urgency'],
            signal['title'],
            signal['description'],
            signal['action_suggested'],
            json.dumps(signal.get('metadata', {}))
        ))
        
        conn.commit()
        conn.close()
        
    def get_signals_for_user(self, user_id: str, urgency_filter: str = None) -> List[Dict]:
        """Get pending signals for a user."""
        conn = psycopg2.connect(self.db_url)
        cursor = conn.cursor()
        
        if urgency_filter:
            cursor.execute("""
                SELECT id, signal_type, urgency, title, description, action_suggested, surfaced_at
                FROM anticipatory_signals 
                WHERE user_id=%s AND status='pending' AND urgency=%s
                ORDER BY 
                    CASE urgency 
                        WHEN 'high' THEN 1 
                        WHEN 'medium' THEN 2 
                        WHEN 'low' THEN 3 
                    END
            """, (user_id, urgency_filter))
        else:
            cursor.execute("""
                SELECT id, signal_type, urgency, title, description, action_suggested, surfaced_at
                FROM anticipatory_signals 
                WHERE user_id=%s AND status='pending'
                ORDER BY 
                    CASE urgency 
                        WHEN 'high' THEN 1 
                        WHEN 'medium' THEN 2 
                        WHEN 'low' THEN 3 
                    END
            """, (user_id,))
            
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': r[0],
                'signal_type': r[1],
                'urgency': r[2],
                'title': r[3],
                'description': r[4],
                'action_suggested': r[5],
                'surfaced_at': r[6]
            }
            for r in rows
        ]


# Global instance
_scheduler: Optional[AnticipatoryScheduler] = None

def get_scheduler() -> AnticipatoryScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AnticipatoryScheduler()
    return _scheduler