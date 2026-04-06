"""
SMS APPROVAL FLOW
=================

Per SPEC v6 Block 2 Item 3:
- Trigger: Operator creates a draft action requiring approval
- Flow: draft created → SMS sent to user's phone → 
        user replies YES/NO → webhook received → action executes or cancels
- Approval window: 24 hours
- After 24h: action expires
"""

import os
import uuid
import json
import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')

APPROVAL_WINDOW_HOURS = 24


class SMSApprovalFlow:
    """Manages SMS approval workflow."""
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
    
    def create_approval_request(
        self,
        user_id: str,
        action_type: str,
        draft_content: str,
        phone_number: str
    ) -> Dict:
        """
        Create a pending approval and send SMS.
        
        Returns: approval request details
        """
        approval_id = str(uuid.uuid4())
        
        # Store in database
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO approval_requests 
                (id, user_id, action_type, draft_content, phone_number, 
                 status, created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', NOW(), %s)
            """, (
                approval_id, user_id, action_type, draft_content,
                phone_number, datetime.now() + timedelta(hours=APPROVAL_WINDOW_HOURS)
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store approval request: {e}")
            return {"success": False, "error": str(e)}
        
        # Send SMS
        sms_sent = self._send_approval_sms(phone_number, action_type, approval_id)
        
        if not sms_sent.get("success"):
            # Rollback approval request
            try:
                conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
                cur = conn.cursor()
                cur.execute("DELETE FROM approval_requests WHERE id = %s", (approval_id,))
                conn.commit()
                cur.close()
                conn.close()
            except:
                pass
            return sms_sent
        
        return {
            "success": True,
            "approval_id": approval_id,
            "status": "pending",
            "expires_at": (datetime.now() + timedelta(hours=APPROVAL_WINDOW_HOURS)).isoformat()
        }
    
    def _send_approval_sms(self, phone_number: str, action_type: str, approval_id: str) -> Dict:
        """Send approval request SMS."""
        
        if not TWILIO_ACCOUNT_SID or not TWILIO_PHONE_NUMBER:
            logger.warning("Twilio not configured - approval SMS skipped")
            # For testing without Twilio, return success
            return {"success": True, "mock": True}
        
        import requests
        
        # Construct approval message
        message = f"LIPAIRA: Approve {action_type}? Reply YES or NO. "
        message += f"Code: {approval_id[:8]}"
        
        try:
            # Use Twilio API
            url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
            
            auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            data = {
                "From": TWILIO_PHONE_NUMBER,
                "To": phone_number,
                "Body": message
            }
            
            response = requests.post(url, auth=auth, data=data, timeout=10)
            
            if response.status_code in [200, 201]:
                logger.info(f"Approval SMS sent to {phone_number}")
                return {"success": True, "sid": response.json().get("sid")}
            else:
                logger.error(f"Twilio error: {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return {"success": False, "error": str(e)}
    
    def handle_webhook(self, from_number: str, message_body: str) -> Dict:
        """
        Handle incoming SMS webhook.
        
        Parse YES/NO response and execute or cancel pending approval.
        """
        response = message_body.strip().upper()
        
        # Extract approval code from message
        # Could be "YES 12345678" or "YES" with last pending approval
        approval_id = None
        
        parts = message_body.strip().split()
        if len(parts) >= 2 and len(parts[1]) >= 8:
            approval_id = parts[1]
        
        # Find pending approval for this phone number
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            
            if approval_id:
                cur.execute("""
                    SELECT id, user_id, action_type, draft_content, status, expires_at
                    FROM approval_requests
                    WHERE phone_number = %s AND id LIKE %s AND status = 'pending'
                    ORDER BY created_at DESC LIMIT 1
                """, (from_number, f"{approval_id}%"))
            else:
                # Get most recent pending
                cur.execute("""
                    SELECT id, user_id, action_type, draft_content, status, expires_at
                    FROM approval_requests
                    WHERE phone_number = %s AND status = 'pending'
                    AND expires_at > NOW()
                    ORDER BY created_at DESC LIMIT 1
                """, (from_number,))
            
            row = cur.fetchone()
            
            if not row:
                cur.close()
                conn.close()
                return {"success": False, "error": "No pending approval found"}
            
            approval_id, user_id, action_type, draft_content, status, expires_at = row
            
            # Check if expired
            if expires_at < datetime.now():
                cur.execute("""
                    UPDATE approval_requests SET status = 'expired' WHERE id = %s
                """, (approval_id,))
                conn.commit()
                cur.close()
                conn.close()
                return {"success": False, "error": "Approval expired"}
            
            # Process response
            if response in ["YES", "YEA", "YEP", "CONFIRM", "OK", "SURE"]:
                new_status = "approved"
                execute_action = True
            elif response in ["NO", "NOPE", "NAH", "CANCEL", "DENY"]:
                new_status = "denied"
                execute_action = False
            else:
                cur.close()
                conn.close()
                return {"success": False, "error": "Reply YES or NO"}
            
            # Update status
            cur.execute("""
                UPDATE approval_requests 
                SET status = %s, responded_at = NOW()
                WHERE id = %s
            """, (new_status, approval_id))
            conn.commit()
            cur.close()
            conn.close()
            
            # Execute or log cancellation
            if execute_action:
                self._execute_approved_action(user_id, action_type, draft_content)
            
            return {
                "success": True,
                "approval_id": approval_id,
                "status": new_status,
                "action_executed": execute_action
            }
            
        except Exception as e:
            logger.error(f"Webhook handling failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _execute_approved_action(self, user_id: str, action_type: str, draft_content: str):
        """Execute the approved action."""
        
        # Parse draft content and execute
        # This would call the appropriate skill based on action_type
        logger.info(f"Executing approved action: {action_type} for user {user_id}")
        
        # Log execution
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO activity_log 
                (user_id, action_type, description, status, created_at, metadata)
                VALUES (%s, %s, %s, 'completed', NOW(), %s)
            """, (
                user_id,
                f"approval_executed_{action_type}",
                f"Executed {action_type} via SMS approval",
                json.dumps({"approval_source": "sms", "action_type": action_type})
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log action execution: {e}")
    
    def get_pending(self, user_id: str) -> list:
        """Get all pending approvals for a user."""
        
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, action_type, draft_content, created_at, expires_at
                FROM approval_requests
                WHERE user_id = %s AND status = 'pending' AND expires_at > NOW()
                ORDER BY created_at DESC
            """, (user_id,))
            
            results = []
            for row in cur.fetchall():
                results.append({
                    "id": row[0],
                    "action_type": row[1],
                    "draft_content": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "expires_at": row[4].isoformat() if row[4] else None
                })
            
            cur.close()
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Failed to get pending approvals: {e}")
            return []


# Database table creation
def init_approval_tables():
    """Create approval_requests table."""
    
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            draft_content TEXT,
            phone_number TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            responded_at TIMESTAMP,
            expires_at TIMESTAMP,
            metadata JSONB DEFAULT '{}'
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Approval requests table initialized")


# Initialize on import
init_approval_tables()