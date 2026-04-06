"""
Swarm Orchestration - Multi-Agent Federated System
"""

import uuid
import re
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify, g

# In-memory swarm registry (would be DB in production)
SWARMS = {}

# Allowed roles and capabilities (whitelist)
ALLOWED_ROLES = {'researcher', 'synthesizer', 'validator', 'executor', 'worker', 'coordinator'}
ALLOWED_CAPABILITIES = {'web_search', 'web_fetch', 'data_analysis', 'code generation', 
                        'writing', 'research', 'validation', 'execution', 'api_calls'}

class SwarmAgent:
    def __init__(self, agent_id, role, capabilities):
        self.id = agent_id
        self.role = role if role in ALLOWED_ROLES else 'worker'  # Default to worker
        # Filter capabilities to whitelist
        self.capabilities = [c for c in capabilities if c in ALLOWED_CAPABILITIES]
        self.status = 'idle'

class Swarm:
    def __init__(self, name, description, owner_id):
        self.id = str(uuid.uuid4())
        self.name = name[:100] if name else 'Unnamed Swarm'  # Limit length
        self.description = description[:500] if description else ''  # Limit length
        self.owner_id = owner_id  # Track ownership
        self.agents = []
        self.created_at = datetime.utcnow()
        self.status = 'created'
    
    def add_agent(self, agent):
        self.agents.append(agent)
    
    def to_dict(self, include_sensitive=False):
        result = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'agents': [{'id': a.id, 'role': a.role, 'capabilities': a.capabilities} for a in self.agents],
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }
        if include_sensitive:
            result['owner_id'] = self.owner_id
        return result

def sanitize_input(text, max_length=500):
    """Sanitize string input - remove dangerous characters."""
    if not text:
        return ''
    # Remove null bytes and control characters
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(text))
    return sanitized[:max_length]

def create_swarm_routes(app, require_auth):
    """Register swarm routes with Flask app"""
    
    @app.route('/api/swarm/create', methods=['POST'])
    @require_auth
    def create_swarm():
        """Create a new swarm of agents"""
        data = request.get_json() or {}
        
        # Validate and sanitize inputs
        name = sanitize_input(data.get('name', ''), 100)
        description = sanitize_input(data.get('description', ''), 500)
        
        if not name:
            return jsonify({'error': 'Swarm name required'}), 400
        
        swarm = Swarm(
            name=name,
            description=description,
            owner_id=g.user_id  # Track who created it
        )
        
        # Add agents to swarm with validation
        agents = data.get('agents', [])
        if len(agents) > 20:
            return jsonify({'error': 'Maximum 20 agents per swarm'}), 400
        
        for agent_spec in agents:
            agent_id = sanitize_input(agent_spec.get('id', str(uuid.uuid4())), 100)
            role = sanitize_input(agent_spec.get('role', 'worker'), 50)
            capabilities = agent_spec.get('capabilities', [])
            
            agent = SwarmAgent(agent_id, role, capabilities)
            swarm.add_agent(agent)
        
        SWARMS[swarm.id] = swarm
        
        return jsonify({
            'swarm': swarm.to_dict(),
            'message': f'Swarm "{swarm.name}" created with {len(swarm.agents)} agents'
        })
    
    @app.route('/api/swarm/<swarm_id>/execute', methods=['POST'])
    @require_auth
    def swarm_execute(swarm_id):
        """Execute task across swarm - parallel execution with result aggregation"""
        if swarm_id not in SWARMS:
            return jsonify({'error': 'Swarm not found'}), 404
        
        swarm = SWARMS[swarm_id]
        
        # Verify ownership
        if swarm.owner_id != g.user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json() or {}
        task = sanitize_input(data.get('task', ''), 10000)
        
        if not task:
            return jsonify({'error': 'Task required'}), 400
        
        # Execute each agent in parallel (simulated)
        results = []
        for agent in swarm.agents:
            # In real implementation, this calls each agent's executor
            results.append({
                'agent_id': agent.id,
                'role': agent.role,
                'status': 'completed',
                'output': f'[Simulated] {agent.role} processed: {task[:50]}...'
            })
        
        # Synthesize results
        synthesis = {
            'swarm_id': swarm_id,
            'task': task[:200] + '...' if len(task) > 200 else task,  # Truncate for response
            'agent_results': results,
            'synthesized': f'Aggregated {len(results)} agent outputs',
            'executed_at': datetime.utcnow().isoformat()
        }
        
        return jsonify(synthesis)
    
    @app.route('/api/swarm/<swarm_id>/handoff', methods=['POST'])
    @require_auth
    def swarm_handoff(swarm_id):
        """Hand off from one agent to another in the swarm"""
        if swarm_id not in SWARMS:
            return jsonify({'error': 'Swarm not found'}), 404
        
        swarm = SWARMS[swarm_id]
        
        # Verify ownership
        if swarm.owner_id != g.user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json() or {}
        from_agent = sanitize_input(data.get('from_agent', ''), 100)
        to_agent = sanitize_input(data.get('to_agent', ''), 100)
        payload = data.get('payload', {})
        
        # Validate agents exist
        agent_ids = {a.id for a in swarm.agents}
        if from_agent not in agent_ids or to_agent not in agent_ids:
            return jsonify({'error': 'Invalid agent ID'}), 400
        
        return jsonify({
            'status': 'handed_off',
            'from': from_agent,
            'to': to_agent,
            'payload_size': len(str(payload)),
            'message': f'Results handed from {from_agent} to {to_agent}'
        })
    
    @app.route('/api/swarm', methods=['GET'])
    @require_auth
    def list_swarms():
        """List user's swarms only"""
        user_swarms = [s.to_dict() for s in SWARMS.values() if s.owner_id == g.user_id]
        return jsonify({
            'swarms': user_swarms
        })
    
    @app.route('/api/swarm/<swarm_id>', methods=['GET'])
    @require_auth
    def get_swarm(swarm_id):
        """Get swarm details"""
        if swarm_id not in SWARMS:
            return jsonify({'error': 'Swarm not found'}), 404
        
        swarm = SWARMS[swarm_id]
        
        # Verify ownership
        if swarm.owner_id != g.user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify(swarm.to_dict())
    
    @app.route('/api/swarm/<swarm_id>', methods=['DELETE'])
    @require_auth
    def delete_swarm(swarm_id):
        """Delete a swarm"""
        if swarm_id not in SWARMS:
            return jsonify({'error': 'Swarm not found'}), 404
        
        swarm = SWARMS[swarm_id]
        
        # Verify ownership
        if swarm.owner_id != g.user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        del SWARMS[swarm_id]
        return jsonify({'message': 'Swarm deleted'})
    
    return app
