# feel free to ignore this comment
     1|"""
     2|Automation Templates Library - Pre-built Workflows
     3|"""
     4|
     5|import uuid
     6|import json
     7|import re
     8|from datetime import datetime
     9|from flask import jsonify, request
    10|
    11|# Template registry
    12|AUTOMATION_TEMPLATES = {
    13|    'crm_sync': {
    14|        'id': 'crm_sync',
    15|        'name': 'CRM Data Sync',
    16|        'description': 'Automatically sync contacts and deals between systems',
    17|        'triggers': ['new_lead', 'deal_updated', 'contact_created'],
    18|        'actions': ['create_contact', 'update_deal', 'send_notification'],
    19|        'category': 'sales',
    20|        'config_schema': {
    21|            'source_crm': {'type': 'string', 'enum': ['hubspot', 'salesforce', 'pipedrive']},
    22|            'target_system': {'type': 'string'},
    23|            'sync_interval': {'type': 'integer', 'default': 15}
    24|        }
    25|    },
    26|    'email_parser': {
    27|        'id': 'email_parser',
    28|        'name': 'Email Intake Parser',
    29|        'description': 'Parse incoming emails, extract info, route to appropriate handler',
    30|        'triggers': ['email_received'],
    31|        'actions': ['extract_data', 'create_task', 'auto_reply'],
    32|        'category': 'operations',
    33|        'config_schema': {
    34|            'email_folder': {'type': 'string', 'default': 'inbox'},
    35|            'extract_fields': {'type': 'array', 'items': ['name', 'email', 'phone', 'company']},
    36|            'auto_reply_template': {'type': 'string'}
    37|        }
    38|    },
    39|    'support_triage': {
    40|        'id': 'support_triage',
    41|        'name': 'Support Ticket Triage',
    42|        'description': 'AI-powered ticket classification and routing',
    43|        'triggers': ['new_ticket'],
    44|        'actions': ['classify', 'prioritize', 'route_to_queue', 'auto_respond'],
    45|        'category': 'support',
    46|        'config_schema': {
    47|            'priority_keywords': {'type': 'object'},
    48|            'routing_rules': {'type': 'array'},
    49|            'sla_respond_minutes': {'type': 'integer', 'default': 60}
    50|        }
    51|    },
    52|    'invoice_processor': {
    53|        'id': 'invoice_processor',
    54|        'name': 'Invoice Processing',
    55|        'description': 'Extract data from invoices, validate, process payments',
    56|        'triggers': ['invoice_received'],
    57|        'actions': ['extract_data', 'validate', 'approve', 'schedule_payment'],
    58|        'category': 'finance',
    59|        'config_schema': {
    60|            'approval_threshold': {'type': 'number', 'default': 1000},
    61|            'auto_approve_under': {'type': 'number', 'default': 100}
    62|        }
    63|    },
    64|    'content_publish': {
    65|        'id': 'content_publish',
    66|        'name': 'Content Publishing Workflow',
    67|        'description': 'Draft → Review → Schedule → Publish across platforms',
    68|        'triggers': ['content_approved', 'schedule_time'],
    69|        'actions': ['format_for_platform', 'upload_media', 'publish', 'notify'],
    70|        'category': 'marketing',
    71|        'config_schema': {
    72|            'platforms': {'type': 'array', 'items': ['twitter', 'linkedin', 'blog']},
    73|            'approval_required': {'type': 'boolean', 'default': True}
    74|        }
    75|    },
    76|    'onboarding_flow': {
    77|        'id': 'onboarding',
    78|        'name': 'Customer Onboarding',
    79|        'description': 'Automated new customer welcome and setup sequence',
    80|        'triggers': ['customer_created'],
    81|        'actions': ['send_welcome', 'create_accounts', 'setup_profile', 'schedule_checkin'],
    82|        'category': 'sales',
    83|        'config_schema': {
    84|            'welcome_email_template': {'type': 'string'},
    85|            'days_to_checkin': {'type': 'integer', 'default': 7}
    86|        }
    87|    }
    88|}
    89|
    90|# Active automations (user-instantiated)
    91|ACTIVE_AUTOMATIONS = {}
    92|
    93|def sanitize_input(text, max_length=1000):
    94|    """Sanitize string input."""
    95|    if not text:
    96|        return ''
    97|    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(text))[:max_length]
    98|
    99|def validate_automation_config(template_id, config):
   100|    """Validate config against template schema."""
   101|    if template_id not in AUTOMATION_TEMPLATES:
   102|        return {'valid': False, 'error': 'Template not found'}
   103|    
   104|    template = AUTOMATION_TEMPLATES[template_id]
   105|    schema = template.get('config_schema', {})
   106|    
   107|    errors = []
   108|    for key, value in config.items():
   109|        if key not in schema:
   110|            errors.append(f'Unknown config key: {key}')
   111|            continue
   112|        
   113|        expected_type = schema[key].get('type')
   114|        
   115|        # Type validation
   116|        if expected_type == 'integer' and not isinstance(value, int):
   117|            try:
   118|                config[key] = int(value)
   119|            except (ValueError, TypeError):
   120|                errors.append(f'{key} must be an integer')
   121|        
   122|        elif expected_type == 'number' and not isinstance(value, (int, float)):
   123|            try:
   124|                config[key] = float(value)
   125|            except (ValueError, TypeError):
   126|                errors.append(f'{key} must be a number')
   127|        
   128|        elif expected_type == 'boolean' and not isinstance(value, bool):
   129|            errors.append(f'{key} must be a boolean')
   130|        
   131|        elif expected_type == 'string' and not isinstance(value, str):
   132|            errors.append(f'{key} must be a string')
   133|        
   134|        elif expected_type == 'array' and not isinstance(value, list):
   135|            errors.append(f'{key} must be an array')
   136|        
   137|        elif expected_type == 'object' and not isinstance(value, dict):
   138|            errors.append(f'{key} must be an object')
   139|    
   140|    # Check for required fields with 'required' in schema
   141|    # (could be added to template definitions)
   142|    
   143|    return {'valid': len(errors) == 0, 'errors': errors}
   144|
   145|def create_automation_routes(app, require_auth):
   146|    """Register automation template routes"""
   147|    
   148|    @app.route('/api/automations/templates', methods=['GET'])
   149|    @require_auth
   150|    def list_templates():
   151|        """List all automation templates"""
   152|        return jsonify({
   153|            'templates': list(AUTOMATION_TEMPLATES.values())
   154|        })
   155|    
   156|    @app.route('/api/automations/templates/<template_id>', methods=['GET'])
   157|    @require_auth
   158|    def get_template(template_id):
   159|        """Get template details"""
   160|        template_id = sanitize_input(template_id, 50)
   161|        if template_id not in AUTOMATION_TEMPLATES:
   162|            return jsonify({'error': 'Template not found'}), 404
   163|        return jsonify(AUTOMATION_TEMPLATES[template_id])
   164|    
   165|    @app.route('/api/automations', methods=['POST'])
   166|    @require_auth
   167|    def activate_automation():
   168|        """Activate an automation from a template"""
   169|        data = request.get_json() or {}
   170|        template_id = sanitize_input(data.get('template_id', ''), 50)
   171|        
   172|        if template_id not in AUTOMATION_TEMPLATES:
   173|            return jsonify({'error': 'Template not found'}), 400
   174|        
   175|        config = data.get('config', {})
   176|        
   177|        # Validate config against schema
   178|        validation = validate_automation_config(template_id, config)
   179|        if not validation['valid']:
   180|            return jsonify({'error': 'Invalid config', 'details': validation['errors']}), 400
   181|        
   182|        automation_id = str(uuid.uuid4())
   183|        automation = {
   184|            'id': automation_id,
   185|            'template_id': template_id,
   186|            'name': AUTOMATION_TEMPLATES[template_id]['name'],
   187|            'config': config,
   188|            'status': 'active',
   189|            'owner_id': g.user_id,
   190|            'trigger_count': 0,
   191|            'last_triggered': None,
   192|            'created_at': datetime.utcnow().isoformat()
   193|        }
   194|        
   195|        ACTIVE_AUTOMATIONS[automation_id] = automation
   196|        
   197|        return jsonify({
   198|            'automation': automation,
   199|            'message': f'Automation "{automation["name"]}" activated'
   200|        })
   201|    
   202|    @app.route('/api/automations', methods=['GET'])
   203|    @require_auth
   204|    def list_automations():
   205|        """List user's active automations"""
   206|        user_autos = [a for a in ACTIVE_AUTOMATIONS.values() if a.get('owner_id') == g.user_id]
   207|        return jsonify({
   208|            'automations': user_autos
   209|        })
   210|    
   211|    @app.route('/api/automations/<automation_id>/trigger', methods=['POST'])
   212|    @require_auth
   213|    def trigger_automation(automation_id):
   214|        """Manually trigger an automation"""
   215|        automation_id_param = sanitize_input(automation_id, 50)
   216|        
   217|        if automation_id_param not in ACTIVE_AUTOMATIONS:
   218|            return jsonify({'error': 'Automation not found'}), 404
   219|        
   220|        automation = ACTIVE_AUTOMATIONS[automation_id_param]
   221|        
   222|        # Verify ownership
   223|        if automation.get('owner_id') != g.user_id:
   224|            return jsonify({'error': 'Access denied'}), 403
   225|        
   226|        trigger_data = request.get_json() or {}
   227|        
   228|        # Validate trigger data structure
   229|        if not isinstance(trigger_data, dict):
   230|            return jsonify({'error': 'Trigger data must be an object'}), 400
   231|        
   232|        # Simulate automation execution
   233|        template = AUTOMATION_TEMPLATES.get(automation['template_id'])
   234|        
   235|        automation['trigger_count'] += 1
   236|        automation['last_triggered'] = datetime.utcnow().isoformat()
   237|        
   238|        return jsonify({
   239|            'status': 'executed',
   240|            'automation_id': automation_id,
   241|            'actions_executed': template['actions'] if template else [],
   242|            'trigger_data_keys': list(trigger_data.keys()),
   243|            'executed_at': automation['last_triggered']
   244|        })
   245|    
   246|    @app.route('/api/automations/<automation_id>', methods=['DELETE'])
   247|    @require_auth
   248|    def deactivate_automation(automation_id):
   249|        """Deactivate an automation"""
   250|        automation_id_param = sanitize_input(automation_id, 50)
   251|        
   252|        if automation_id_param not in ACTIVE_AUTOMATIONS:
   253|            return jsonify({'error': 'Automation not found'}), 404
   254|        
   255|        automation = ACTIVE_AUTOMATIONS[automation_id_param]
   256|        
   257|        # Verify ownership
   258|        if automation.get('owner_id') != g.user_id:
   259|            return jsonify({'error': 'Access denied'}), 403
   260|        
   261|        del ACTIVE_AUTOMATIONS[automation_id_param]
   262|        return jsonify({'message': 'Automation deactivated'})
   263|    
   264|    @app.route('/api/automations/<automation_id>', methods=['PUT'])
   265|    @require_auth
   266|    def update_automation(automation_id):
   267|        """Update automation config"""
   268|        automation_id_param = sanitize_input(automation_id, 50)
   269|        
   270|        if automation_id_param not in ACTIVE_AUTOMATIONS:
   271|            return jsonify({'error': 'Automation not found'}), 404
   272|        
   273|        automation = ACTIVE_AUTOMATIONS[automation_id_param]
   274|        
   275|        # Verify ownership
   276|        if automation.get('owner_id') != g.user_id:
   277|            return jsonify({'error': 'Access denied'}), 403
   278|        
   279|        data = request.get_json() or {}
   280|        new_config = data.get('config', {})
   281|        
   282|        # Validate new config
   283|        validation = validate_automation_config(automation['template_id'], new_config)
   284|        if not validation['valid']:
   285|            return jsonify({'error': 'Invalid config', 'details': validation['errors']}), 400
   286|        
   287|        ACTIVE_AUTOMATIONS[automation_id_param]['config'].update(new_config)
   288|        
   289|        return jsonify({
   290|            'automation': ACTIVE_AUTOMATIONS[automation_id_param]
   291|        })
   292|    
   293|    return app
   294|