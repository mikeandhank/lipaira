"""
Automation Templates Library - Pre-built Workflows
"""

import uuid
import json
import re
from datetime import datetime
from flask import jsonify, request

# Template registry
AUTOMATION_TEMPLATES = {
    'crm_sync': {
        'id': 'crm_sync',
        'name': 'CRM Data Sync',
        'description': 'Automatically sync contacts and deals between systems',
        'triggers': ['new_lead', 'deal_updated', 'contact_created'],
        'actions': ['create_contact', 'update_deal', 'send_notification'],
        'category': 'sales',
        'config_schema': {
            'source_crm': {'type': 'string', 'enum': ['hubspot', 'salesforce', 'pipedrive']},
            'target_system': {'type': 'string'},
            'sync_interval': {'type': 'integer', 'default': 15}
        }
    },
    'email_parser': {
        'id': 'email_parser',
        'name': 'Email Intake Parser',
        'description': 'Parse incoming emails, extract info, route to appropriate handler',
        'triggers': ['email_received'],
        'actions': ['extract_data', 'create_task', 'auto_reply'],
        'category': 'operations',
        'config_schema': {
            'email_folder': {'type': 'string', 'default': 'inbox'},
            'extract_fields': {'type': 'array', 'items': ['name', 'email', 'phone', 'company']},
            'auto_reply_template': {'type': 'string'}
        }
    },
    'support_triage': {
        'id': 'support_triage',
        'name': 'Support Ticket Triage',
        'description': 'AI-powered ticket classification and routing',
        'triggers': ['new_ticket'],
        'actions': ['classify', 'prioritize', 'route_to_queue', 'auto_respond'],
        'category': 'support',
        'config_schema': {
            'priority_keywords': {'type': 'object'},
            'routing_rules': {'type': 'array'},
            'sla_respond_minutes': {'type': 'integer', 'default': 60}
        }
    },
    'invoice_processor': {
        'id': 'invoice_processor',
        'name': 'Invoice Processing',
        'description': 'Extract data from invoices, validate, process payments',
        'triggers': ['invoice_received'],
        'actions': ['extract_data', 'validate', 'approve', 'schedule_payment'],
        'category': 'finance',
        'config_schema': {
            'approval_threshold': {'type': 'number', 'default': 1000},
            'auto_approve_under': {'type': 'number', 'default': 100}
        }
    },
    'content_publish': {
        'id': 'content_publish',
        'name': 'Content Publishing Workflow',
        'description': 'Draft → Review → Schedule → Publish across platforms',
        'triggers': ['content_approved', 'schedule_time'],
        'actions': ['format_for_platform', 'upload_media', 'publish', 'notify'],
        'category': 'marketing',
        'config_schema': {
            'platforms': {'type': 'array', 'items': ['twitter', 'linkedin', 'blog']},
            'approval_required': {'type': 'boolean', 'default': True}
        }
    },
    'onboarding_flow': {
        'id': 'onboarding',
        'name': 'Customer Onboarding',
        'description': 'Automated new customer welcome and setup sequence',
        'triggers': ['customer_created'],
        'actions': ['send_welcome', 'create_accounts', 'setup_profile', 'schedule_checkin'],
        'category': 'sales',
        'config_schema': {
            'welcome_email_template': {'type': 'string'},
            'days_to_checkin': {'type': 'integer', 'default': 7}
        }
    }
}

# Active automations (user-instantiated)
ACTIVE_AUTOMATIONS = {}

def sanitize_input(text, max_length=1000):
    """Sanitize string input."""
    if not text:
        return ''
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(text))[:max_length]

def validate_automation_config(template_id, config):
    """Validate config against template schema."""
    if template_id not in AUTOMATION_TEMPLATES:
        return {'valid': False, 'error': 'Template not found'}
    
    template = AUTOMATION_TEMPLATES[template_id]
    schema = template.get('config_schema', {})
    
    errors = []
    for key, value in config.items():
        if key not in schema:
            errors.append(f'Unknown config key: {key}')
            continue
        
        expected_type = schema[key].get('type')
        
        # Type validation
        if expected_type == 'integer' and not isinstance(value, int):
            try:
                config[key] = int(value)
            except (ValueError, TypeError):
                errors.append(f'{key} must be an integer')
        
        elif expected_type == 'number' and not isinstance(value, (int, float)):
            try:
                config[key] = float(value)
            except (ValueError, TypeError):
                errors.append(f'{key} must be a number')
        
        elif expected_type == 'boolean' and not isinstance(value, bool):
            errors.append(f'{key} must be a boolean')
        
        elif expected_type == 'string' and not isinstance(value, str):
            errors.append(f'{key} must be a string')
        
        elif expected_type == 'array' and not isinstance(value, list):
            errors.append(f'{key} must be an array')
        
        elif expected_type == 'object' and not isinstance(value, dict):
            errors.append(f'{key} must be an object')
    
    # Check for required fields with 'required' in schema
    # (could be added to template definitions)
    
    return {'valid': len(errors) == 0, 'errors': errors}

def create_automation_routes(app, require_auth):
    """Register automation template routes"""
    
    @app.route('/api/automations/templates', methods=['GET'])
    @require_auth
    def list_templates():
        """List all automation templates"""
        return jsonify({
            'templates': list(AUTOMATION_TEMPLATES.values())
        })
    
    @app.route('/api/automations/templates/<template_id>', methods=['GET'])
    @require_auth
    def get_template(template_id):
        """Get template details"""
        template_id = sanitize_input(template_id, 50)
        if template_id not in AUTOMATION_TEMPLATES:
            return jsonify({'error': 'Template not found'}), 404
        return jsonify(AUTOMATION_TEMPLATES[template_id])
    
    @app.route('/api/automations', methods=['POST'])
    @require_auth
    def activate_automation():
        """Activate an automation from a template"""
        data = request.get_json() or {}
        template_id = sanitize_input(data.get('template_id', ''), 50)
        
        if template_id not in AUTOMATION_TEMPLATES:
            return jsonify({'error': 'Template not found'}), 400
        
        config = data.get('config', {})
        
        # Validate config against schema
        validation = validate_automation_config(template_id, config)
        if not validation['valid']:
            return jsonify({'error': 'Invalid config', 'details': validation['errors']}), 400
        
        automation_id = str(uuid.uuid4())
        automation = {
            'id': automation_id,
            'template_id': template_id,
            'name': AUTOMATION_TEMPLATES[template_id]['name'],
            'config': config,
            'status': 'active',
            'owner_id': g.user_id,
            'trigger_count': 0,
            'last_triggered': None,
            'created_at': datetime.utcnow().isoformat()
        }
        
        ACTIVE_AUTOMATIONS[automation_id] = automation
        
        return jsonify({
            'automation': automation,
            'message': f'Automation "{automation["name"]}" activated'
        })
    
    @app.route('/api/automations', methods=['GET'])
    @require_auth
    def list_automations():
        """List user's active automations"""
        user_autos = [a for a in ACTIVE_AUTOMATIONS.values() if a.get('owner_id') == g.user_id]
        return jsonify({
            'automations': user_autos
        })
    
    @app.route('/api/automations/<automation_id>/trigger', methods=['POST'])
    @require_auth
    def trigger_automation(automation_id):
        """Manually trigger an automation"""
        automation_id_param = sanitize_input(automation_id, 50)
        
        if automation_id_param not in ACTIVE_AUTOMATIONS:
            return jsonify({'error': 'Automation not found'}), 404
        
        automation = ACTIVE_AUTOMATIONS[automation_id_param]
        
        # Verify ownership
        if automation.get('owner_id') != g.user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        trigger_data = request.get_json() or {}
        
        # Validate trigger data structure
        if not isinstance(trigger_data, dict):
            return jsonify({'error': 'Trigger data must be an object'}), 400
        
        # Simulate automation execution
        template = AUTOMATION_TEMPLATES.get(automation['template_id'])
        
        automation['trigger_count'] += 1
        automation['last_triggered'] = datetime.utcnow().isoformat()
        
        return jsonify({
            'status': 'executed',
            'automation_id': automation_id,
            'actions_executed': template['actions'] if template else [],
            'trigger_data_keys': list(trigger_data.keys()),
            'executed_at': automation['last_triggered']
        })
    
    @app.route('/api/automations/<automation_id>', methods=['DELETE'])
    @require_auth
    def deactivate_automation(automation_id):
        """Deactivate an automation"""
        automation_id_param = sanitize_input(automation_id, 50)
        
        if automation_id_param not in ACTIVE_AUTOMATIONS:
            return jsonify({'error': 'Automation not found'}), 404
        
        automation = ACTIVE_AUTOMATIONS[automation_id_param]
        
        # Verify ownership
        if automation.get('owner_id') != g.user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        del ACTIVE_AUTOMATIONS[automation_id_param]
        return jsonify({'message': 'Automation deactivated'})
    
    @app.route('/api/automations/<automation_id>', methods=['PUT'])
    @require_auth
    def update_automation(automation_id):
        """Update automation config"""
        automation_id_param = sanitize_input(automation_id, 50)
        
        if automation_id_param not in ACTIVE_AUTOMATIONS:
            return jsonify({'error': 'Automation not found'}), 404
        
        automation = ACTIVE_AUTOMATIONS[automation_id_param]
        
        # Verify ownership
        if automation.get('owner_id') != g.user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json() or {}
        new_config = data.get('config', {})
        
        # Validate new config
        validation = validate_automation_config(automation['template_id'], new_config)
        if not validation['valid']:
            return jsonify({'error': 'Invalid config', 'details': validation['errors']}), 400
        
        ACTIVE_AUTOMATIONS[automation_id_param]['config'].update(new_config)
        
        return jsonify({
            'automation': ACTIVE_AUTOMATIONS[automation_id_param]
        })
    
    return app
