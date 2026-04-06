"""
MORNING BRIEFING ENGINE
========================

Per SPEC v6 Block 2 Item 5:
- Schedule: 7:00 AM user's local timezone, daily
- Delivery: email to user's primary address
- Content: today's calendar events, overdue invoices, pending approvals,
           top memory surface, one proactive suggestion
- No hardcoded content - every briefing is live data
"""

import os
import json
import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)


class MorningBriefingEngine:
    """Generates daily morning briefings for users."""
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
    
    def generate_briefing(self, user_id: str) -> Dict:
        """Generate morning briefing for user."""
        
        briefing = {
            "generated_at": datetime.now().isoformat(),
            "sections": {}
        }
        
        # 1. Today's calendar events
        try:
            from skills.google.calendar import CalendarReadSkill
            cal = CalendarReadSkill()
            events_result = cal.execute({"days": 1}, user_id)
            briefing["sections"]["calendar"] = events_result.get("events", [])[:5]
        except Exception as e:
            logger.warning(f"Calendar fetch failed: {e}")
            briefing["sections"]["calendar"] = []
        
        # 2. Overdue invoices
        try:
            from skills.quickbooks.get_invoices import GetInvoicesSkill
            qb = GetInvoicesSkill()
            invoices_result = qb.execute({"days_overdue": 1, "limit": 10}, user_id)
            overdue = [i for i in invoices_result.get("invoices", []) if i.get("days_overdue", 0) > 0]
            total_overdue = sum(i.get("amount", 0) for i in overdue)
            briefing["sections"]["overdue_invoices"] = {
                "count": len(overdue),
                "total": total_overdue,
                "details": overdue[:5]
            }
        except Exception as e:
            logger.warning(f"QB fetch failed: {e}")
            briefing["sections"]["overdue_invoices"] = {"count": 0, "total": 0}
        
        # 3. Pending approvals
        try:
            from sms_approval_flow import SMSApprovalFlow
            flow = SMSApprovalFlow()
            pending = flow.get_pending(user_id)
            briefing["sections"]["pending_approvals"] = pending
        except Exception as e:
            logger.warning(f"Pending approvals fetch failed: {e}")
            briefing["sections"]["pending_approvals"] = []
        
        # 4. Top memory surface (what needs attention today)
        try:
            graph = get_memory_graph(user_id)
            # Get high-priority memories
            memories = graph.recall_semantic("what do I need to do today", limit=5)
            briefing["sections"]["memory_surface"] = [
                node.content for node, score in memories if score > 0.5
            ]
        except Exception as e:
            logger.warning(f"Memory fetch failed: {e}")
            briefing["sections"]["memory_surface"] = []
        
        # 5. Proactive suggestion (based on patterns)
        suggestion = self._generate_proactive_suggestion(user_id)
        briefing["sections"]["proactive_suggestion"] = suggestion
        
        return briefing
    
    def _generate_proactive_suggestion(self, user_id: str) -> str:
        """Generate one proactive suggestion based on patterns."""
        
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            
            # Check recent activity
            cur.execute("""
                SELECT COUNT(*) FROM activity_log
                WHERE user_id = %s AND created_at > NOW() - INTERVAL '7 days'
            """, (user_id,))
            week_activity = cur.fetchone()[0] or 0
            
            # Check pending items
            cur.execute("""
                SELECT COUNT(*) FROM approval_requests
                WHERE user_id = %s AND status = 'pending' AND expires_at > NOW()
            """, (user_id,))
            pending_count = cur.fetchone()[0] or 0
            
            conn.close()
            
            if pending_count > 0:
                return f"You have {pending_count} pending approval(s). Review them to keep things moving."
            elif week_activity < 5:
                return "It's been a quiet week. Consider reaching out to your top clients."
            else:
                return "Everything looks clear for today!"
                
        except Exception as e:
            logger.error(f"Suggestion generation failed: {e}")
            return "Have a great day!"
    
    def format_email(self, briefing: Dict, user_name: str = None) -> Dict:
        """Format briefing as email content."""
        
        user_greeting = f"Hi{', ' + user_name if user_name else ''}," if user_name else "Hi,"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>🌅 Your Morning Briefing</h2>
            <p>{user_greeting}</p>
            
            <h3>📅 Today's Calendar</h3>
            {self._format_calendar(briefing['sections'].get('calendar', []))}
            
            <h3>💰 Overdue Invoices</h3>
            {self._format_overdue(briefing['sections'].get('overdue_invoices', {}))}
            
            <h3>✋ Pending Approvals</h3>
            {self._format_approvals(briefing['sections'].get('pending_approvals', []))}
            
            <h3>🧠 What You Need to Know</h3>
            {self._format_memory(briefing['sections'].get('memory_surface', []))}
            
            <h3>💡 Proactive Suggestion</h3>
            <p>{briefing['sections'].get('proactive_suggestion', '')}</p>
            
            <hr>
            <p style="color: #666; font-size: 12px;">
                Generated by Lipaira at {briefing['generated_at']}
            </p>
        </body>
        </html>
        """
        
        return {
            "subject": "🌅 Your Daily Morning Briefing",
            "html": html,
            "text": self._format_text(briefing)
        }
    
    def _format_calendar(self, events: List) -> str:
        if not events:
            return "<p>No events scheduled for today.</p>"
        
        html = "<ul>"
        for e in events[:5]:
            time = e.get('start_time', 'TBD')
            title = e.get('title', 'Untitled')
            html += f"<li><strong>{time}:</strong> {title}</li>"
        html += "</ul>"
        return html
    
    def _format_overdue(self, data: Dict) -> str:
        count = data.get('count', 0)
        total = data.get('total', 0)
        if count == 0:
            return "<p>✅ No overdue invoices!</p>"
        return f"<p>⚠️ {count} overdue invoices totaling ${total:.2f}</p>"
    
    def _format_approvals(self, pending: List) -> str:
        if not pending:
            return "<p>✅ No pending approvals.</p>"
        
        html = "<ul>"
        for p in pending:
            html += f"<li>{p.get('action_type', 'Action')}: {p.get('draft_content', '')[:50]}...</li>"
        html += "</ul>"
        return html
    
    def _format_memory(self, memories: List) -> str:
        if not memories:
            return "<p>No key memories to surface.</p>"
        
        html = "<ul>"
        for m in memories[:3]:
            html += f"<li>{m}</li>"
        html += "</ul>"
        return html
    
    def _format_text(self, briefing: Dict) -> str:
        # Plain text version
        lines = ["Your Morning Briefing", ""]
        
        cal = briefing['sections'].get('calendar', [])
        if cal:
            lines.append("Today's Calendar:")
            for e in cal[:5]:
                lines.append(f"  - {e.get('start_time', 'TBD')}: {e.get('title', '')}")
        
        overdue = briefing['sections'].get('overdue_invoices', {})
        if overdue.get('count', 0) > 0:
            lines.append(f"\nOverdue: {overdue['count']} invoices, ${overdue['total']:.2f}")
        
        return "\n".join(lines)


def get_memory_graph(user_id):
    """Import and get memory graph."""
    from operator_context import get_memory_graph
    return get_memory_graph(user_id)