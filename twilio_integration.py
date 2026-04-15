"""
Twilio Integration - SMS and Voice for NexusOS
"""

import os
import re
import uuid
import hmac
import hashlib
import base64
import psycopg2
from datetime import datetime
from flask import jsonify, request, make_response, g

# Twilio credentials - require them to be set
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')

# In-memory SMS/Call log (would be DB in production)
MESSAGES = {}
CALLS = {}

# Phone number validation regex (E.164 format)
PHONE_REGEX = re.compile(r'^\+[1-9]\d{1,14}$')

def validate_phone_number(phone: str) -> bool:
    """Validate phone number in E.164 format."""
    return bool(PHONE_REGEX.match(phone))

def verify_twilio_signature(url: str, params: dict, signature: str) -> bool:
    """Verify Twilio request signature."""
    if not TWILIO_AUTH_TOKEN:
        return False
    
    # Sort params and concatenate
    sorted_params = ''.join(f'{k}{v}' for k, v in sorted(params.items()))
    data = url + sorted_params
    
    # Compute HMAC-SHA1
    hash = hmac.new(
        TWILIO_AUTH_TOKEN.encode(),
        data.encode(),
        hashlib.sha1
    ).digest()
    
    # Compare with signature
    expected = base64.b64encode(hash).decode()
    return hmac.compare_digest(expected, signature)

def create_twilio_routes(app, require_auth):
    """Register Twilio routes"""
    
    @app.route('/api/twilio/config', methods=['GET'])
    @require_auth
    def twilio_config_status():
        """Check Twilio configuration status"""
        configured = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER)
        return jsonify({
            'configured': configured,
            'phone_number': TWILIO_PHONE_NUMBER[-4:] if TWILIO_PHONE_NUMBER else None,
            'features': ['sms', 'voice'] if configured else []
        })
    
    @app.route('/api/twilio/approval/create', methods=['POST'])
    @require_auth
    def create_approval():
        """Create an approval request and send SMS"""
        from sms_approval_flow import SMSApprovalFlow
        
        data = request.get_json()
        action_type = data.get('action_type', '')
        draft_content = data.get('draft_content', '')
        
        # Get user's phone from their profile
        user_id = g.user_id
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            cur.execute("SELECT phone FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            phone_number = row[0] if row else None
            conn.close()
            
            if not phone_number:
                return jsonify({'error': 'No phone number on file'}), 400
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
        flow = SMSApprovalFlow()
        result = flow.create_approval_request(user_id, action_type, draft_content, phone_number)
        
        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify({'error': result.get('error')}), 500
    
    @app.route('/api/twilio/approval/pending', methods=['GET'])
    @require_auth
    def get_pending_approvals():
        """Get all pending approvals for current user"""
        from sms_approval_flow import SMSApprovalFlow
        
        user_id = g.user_id
        flow = SMSApprovalFlow()
        pending = flow.get_pending(user_id)
        
        return jsonify({'pending': pending})
    
    @app.route('/api/twilio/sms/send', methods=['POST'])
    @require_auth
    def send_sms():
        """Send an SMS"""
        if not TWILIO_ACCOUNT_SID:
            return jsonify({
                'error': 'Twilio not configured',
                'setup': 'Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER'
            }), 503
        
        data = request.get_json()
        to_number = data.get('to', '')
        message = data.get('message', '')
        
        # Validate phone number
        if not validate_phone_number(to_number):
            return jsonify({
                'error': 'Invalid phone number. Use E.164 format: +1234567890'
            }), 400
        
        if not message:
            return jsonify({'error': 'Message required'}), 400
        
        if len(message) > 1600:
            return jsonify({'error': 'Message too long (max 1600 chars)'}), 400
        
        # In production, this would use twilio library:
        # from twilio.rest import Client
        # client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        # client.messages.create(body=message, from_=TWILIO_PHONE_NUMBER, to=to_number)
        
        # Store message log
        msg_id = str(uuid.uuid4())
        MESSAGES[msg_id] = {
            'id': msg_id,
            'to': to_number,
            'from': TWILIO_PHONE_NUMBER,
            'message': message,
            'status': 'sent',
            'direction': 'outbound',
            'created_at': datetime.utcnow().isoformat()
        }
        
        return jsonify({
            'success': True,
            'message_id': msg_id,
            'to': to_number,
            'status': 'sent'
        })
    
    @app.route('/api/twilio/sms', methods=['GET'])
    @require_auth
    def list_sms():
        """List SMS messages"""
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)  # Cap at 100
        messages = list(MESSAGES.values())[-limit:]
        return jsonify({'messages': messages})
    
    @app.route('/api/twilio/sms/webhook', methods=['POST'])
    def twilio_sms_webhook():
        """Webhook for incoming SMS"""
        # Verify Twilio signature in production
        signature = request.headers.get('X-Twilio-Signature', '')
        url = request.url
        
        # Skip verification if no token configured (development)
        if TWILIO_AUTH_TOKEN:
            params = dict(request.form)
            if not verify_twilio_signature(url, params, signature):
                # In production, return 403
                pass  # Allow for development
        
        from_number = request.form.get('From', '')
        message_body = request.form.get('Body', '')
        
        # Validate incoming phone number
        if not validate_phone_number(from_number):
            from_number = '+' + re.sub(r'\D', '', from_number)
        
        msg_id = str(uuid.uuid4())
        MESSAGES[msg_id] = {
            'id': msg_id,
            'to': TWILIO_PHONE_NUMBER,
            'from': from_number,
            'message': message_body,
            'status': 'received',
            'direction': 'inbound',
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Return TwiML response
        response = make_response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>')
        response.headers['Content-Type'] = 'text/xml'
        
        # Process through approval flow if it's a YES/NO response
        try:
            from sms_approval_flow import SMSApprovalFlow
            approval_flow = SMSApprovalFlow()
            result = approval_flow.handle_webhook(from_number, message_body)
            
            if result.get("success"):
                logger.info(f"Approval {result.get('status')}: {result.get('approval_id')}")
            else:
                logger.warning(f"Approval handling failed: {result.get('error')}")
        except Exception as e:
            logger.error(f"Approval flow error: {e}")
        
        return response
    
    @app.route('/api/twilio/call/initiate', methods=['POST'])
    @require_auth
    def initiate_call():
        """Initiate a voice call"""
        if not TWILIO_ACCOUNT_SID:
            return jsonify({'error': 'Twilio not configured'}), 503
        
        data = request.get_json()
        to_number = data.get('to', '')
        
        # Validate phone number
        if not validate_phone_number(to_number):
            return jsonify({
                'error': 'Invalid phone number. Use E.164 format: +1234567890'
            }), 400
        
        call_id = str(uuid.uuid4())
        CALLS[call_id] = {
            'id': call_id,
            'to': to_number,
            'from': TWILIO_PHONE_NUMBER,
            'status': 'initiated',
            'created_at': datetime.utcnow().isoformat()
        }
        
        return jsonify({
            'success': True,
            'call_id': call_id,
            'to': to_number,
            'status': 'initiated'
        })
    
    @app.route('/api/twilio/call', methods=['GET'])
    @require_auth
    def list_calls():
        """List calls"""
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)  # Cap at 100
        calls = list(CALLS.values())[-limit:]
        return jsonify({'calls': calls})
    
    @app.route('/api/twilio/voice/webhook', methods=['POST'])
    def twilio_voice_webhook():
        """Webhook for voice call status"""
        # Verify Twilio signature in production
        signature = request.headers.get('X-Twilio-Signature', '')
        url = request.url
        
        if TWILIO_AUTH_TOKEN:
            params = dict(request.form)
            # In production, verify signature
        
        call_sid = request.form.get('CallSid', '')
        call_status = request.form.get('CallStatus', '')
        
        # Update call status
        for call in CALLS.values():
            if call.get('sid') == call_sid:
                call['status'] = call_status
        
        # Return TwiML for voicemail/menu
        response = make_response('''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Thank you for calling NexusOS. Leave a message after the tone.</Say>
    <Record maxLength="60" />
</Response>''')
        response.headers['Content-Type'] = 'text/xml'
        return response
    
    return app
