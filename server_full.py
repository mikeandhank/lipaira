# Repo renamed to lipaira — https://github.com/mikeandhank/lipaira
"""
Nexus Server - Full Implementation
Complete server with: Auth, LLM Routing, Cost/Quality Slider, Billing, Usage
"""

import os
import random
import threading
import billing
from api.prompt_sanitizer import sanitize_prompt_input, is_suspicious_input
from billing import (
    deduct_usage,
    get_user_billing_info,
    add_credits,
    can_use_service,
    get_user_balance_cents,
    STARTING_BALANCE_CENTS,
    cents_to_dollars,
    dollars_to_cents
)
import sys
import json
import uuid
import secrets
import hashlib
import logging
import bcrypt
from typing import List, Dict
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from psycopg2.extras import RealDictCursor
from functools import wraps
from flask import Flask, request, jsonify, g, redirect, session
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
CORS(app, origins=['https://lipaira.ai', 'https://api.lipaira.ai', 
                   'http://localhost:3000', 'http://localhost:5173'], 
     supports_credentials=True)
import requests
import redis
import docker
import stripe
from stripe.checkout import Session as CheckoutSession
from urllib.parse import urlencode

# Memory graph - imported lazily in get_memory_graph()

# Docker client - initialize lazily to avoid container startup errors
docker_client = None
try:
    docker_client = docker.from_env()
except Exception:
    pass  # Docker not available (expected in containers)

# Import our modules
from swarm_orchestration import create_swarm_routes
from internal_endpoints import create_internal_routes
from google_oauth import create_google_routes  # Not available
from automation_templates import create_automation_routes
from twilio_integration import create_twilio_routes
from pattern_detector import create_pattern_routes
from integrations.routes import integrations_bp

# Register swarm routes after app is fully initialized (after require_auth is defined)
# This happens later in the file, near the end
from operator_layer.routes import operator_bp
from lipaira_client.webhooks import webhooks_bp
from encryption import get_encryption_key, hash_key_for_storage, verify_key_hash
from audit_log import log_audit, AuditLogError
from model_registry import (
    get_models, get_free_models, get_model_by_id, 
    get_models_by_provider, get_model_pricing_estimate,
    get_model_for_quality, MODEL_CATEGORIES
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Memory graph - standalone module (no legacy dependencies)
_memory_graphs = {}

def get_memory_graph(user_id: str):
    if user_id not in _memory_graphs:
        from memory_graph import CumulativeMemoryGraph
        
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise RuntimeError("DATABASE_URL environment variable is required")
        _memory_graphs[user_id] = CumulativeMemoryGraph(
            user_id=user_id,
            db_url=db_url
        )
    return _memory_graphs[user_id]

# Load API keys from AWS Secrets Manager on startup
from providers import load_secrets
from user_provisioner import provision_user
load_secrets()

# Register all skills at startup
try:
    import skills  # triggers skills/__init__.py → populates skill_registry
    from skills.registry import skill_registry as _sr
    logger.info(f"Skill registry loaded: {len(_sr.list())} skills registered")
except Exception as e:
    logger.error(f"CRITICAL: Skill registry failed to load: {e}")

# Import quickbooks after secrets are loaded
from lipaira_client.quickbooks_oauth import quickbooks_bp
from google_oauth import google_bp
from lipaira_client.microsoft_oauth import microsoft_bp
from webhook_sync import webhook_bp
from push_notifications import create_push_routes

# Start background tasks (billing sweep, memory sweep)
try:
    from background_tasks import start_background_tasks
    start_background_tasks()
except Exception as e:
    logging.warning(f"Failed to start background tasks: {e}")

# Initialize skill hot loader (Block 5 Item 16)
try:
    import atexit
    from skill_registry import skill_registry
    from skill_hot_loader import start_hot_loader, stop_hot_loader
    _hot_loader = start_hot_loader(registry=skill_registry)
    atexit.register(stop_hot_loader)
    logging.info("SkillHotLoader initialized")
except Exception as e:
    logging.warning(f"Failed to start SkillHotLoader: {e}")

# Register integration routes
# Commented out - using server_full.py endpoint instead
app.register_blueprint(integrations_bp)

# Register operator routes
app.register_blueprint(operator_bp)

# Register webhook routes
app.register_blueprint(webhooks_bp)

# Register QuickBooks OAuth routes
app.register_blueprint(quickbooks_bp)
app.register_blueprint(google_bp)
app.register_blueprint(microsoft_bp)
# webhook_bp already registered above (Item 15)

# lipaira-providers — only register if imports succeed
try:
    from lipaira_providers.user_settings import settings_bp
    app.register_blueprint(settings_bp)
except Exception as e:
    logger.warning(f"settings_bp not registered: {e}")

try:
    from lipaira_providers.enhanced_preferences_api import preferences_bp
    app.register_blueprint(preferences_bp)
except Exception as e:
    logger.warning(f"preferences_bp not registered: {e}")

try:
    from lipaira_providers.unified_api import unified_bp
    app.register_blueprint(unified_bp)
except Exception as e:
    logger.warning(f"unified_bp not registered: {e}")

# lipaira-client — only register if imports succeed
try:
    from lipaira_client.crm_routes import crm_bp
    app.register_blueprint(crm_bp)
except Exception as e:
    logger.warning(f"crm_bp not registered: {e}")

# create_push_routes moved after require_auth is defined

# ============================================================================
# SECURITY: HTTPS Enforcement & Headers
# ============================================================================

@app.before_request
def enforce_https():
    """Redirect HTTP to HTTPS in production."""
    if os.environ.get('NEXUSOS_ENV') == 'production':
        if request.headers.get('X-Forwarded-Proto', 'http') != 'https':
            return jsonify({'error': 'HTTPS required'}), 301

@app.after_request
def add_security_headers(response):
    """Add security headers."""
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


# ============================================================================
# API KEY ENCRYPTION
# ============================================================================

def encrypt_api_key(key: str, user_id: str) -> str:
    """Encrypt an API key before storage using per-user salt."""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(get_encryption_key(user_id).encode())
        return f.encrypt(key.encode()).decode()
    except Exception as e:
        logger.warning(f"Encryption failed, storing hash instead: {e}")
        return hash_key_for_storage(key)

def decrypt_api_key(encrypted_key: str, user_id: str) -> str:
    """Decrypt an API key using per-user salt."""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(get_encryption_key(user_id).encode())
        return f.decrypt(encrypted_key.encode()).decode()
    except Exception:
        # Not encrypted, might be a hash
        return None


# ============================================================================
# RATE LIMITING (Credit-Based - More Credits = Higher Limits)
# ============================================================================

import time
RATE_LIMIT_STORE = {}

def get_rate_limit(credits: float) -> int:
    """Calculate rate limit based on account balance."""
    # High cap - we WANT users to spend their credits!
    # This is mainly to prevent infinite loops and system overload
    if credits < 100:
        return 100    # Minimum to prevent complete lockout
    elif credits < 1000:
        return 1000   
    elif credits < 10000:
        return 2500   
    elif credits < 100000:
        return 5000   
    else:
        return 10000  # High roller cap

def check_rate_limit(user_id: str, credits: float = 0) -> bool:
    """Check if user has exceeded rate limit based on their credit balance."""
    now = time.time()
    window = 60  # 1 minute window
    
    # Get limit based on credits
    limit = get_rate_limit(credits)
    
    key = f"{user_id}:{int(now // window)}"
    count = RATE_LIMIT_STORE.get(key, 0)
    
    if count >= limit:
        return False
    
    RATE_LIMIT_STORE[key] = count + 1
    
    # Cleanup old entries
    for k in list(RATE_LIMIT_STORE.keys()):
        if int(k.split(':')[1]) < int(now // window) - 2:
            del RATE_LIMIT_STORE[k]
    
    return True


# ============================================================================
# COST/QUALITY SLIDER - MODEL MAPPING
# ============================================================================

class QualityLevel:
    """Cost/Quality slider levels."""
    SPEED = 'speed'          # Cheapest, fastest
    BALANCED = 'balanced'    # Default
    QUALITY = 'quality'      # Premium
    DEEP = 'deep'           # Most expensive, best for hard problems


# ============================================================================
# PASSWORD HELPERS - Using bcrypt
# ============================================================================

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


# Model configuration by quality level
QUALITY_MODELS = {
    QualityLevel.SPEED: {
        'provider': 'openai',
        'model': 'gpt-4o-mini',
        'cost_per_1m': 0.15,  # sh.15 per 1M tokens
        'context': 128000,
        'description': 'Fast, cheap - good for simple tasks'
    },
    QualityLevel.BALANCED: {
        'provider': 'anthropic',
        'model': 'claude-sonnet-4-20250514',
        'cost_per_1m': 3.00,
        'context': 200000,
        'description': 'Best overall - great reasoning, good speed'
    },
    QualityLevel.QUALITY: {
        'provider': 'openai',
        'model': 'gpt-4o',
        'cost_per_1m': 2.50,
        'context': 128000,
        'description': 'High quality responses'
    },
    QualityLevel.DEEP: {
        'provider': 'openai',
        'model': 'o1-preview',
        'cost_per_1m': 15.00,
        'context': 200000,
        'description': 'Complex reasoning, hard problems'
    }
}

# Fallback chains per level
QUALITY_FALLBACKS = {
    QualityLevel.SPEED: ['gpt-4o-mini', 'llama3', 'phi3'],
    QualityLevel.BALANCED: ['claude-sonnet-4-20250514', 'gpt-4o-mini', 'llama3'],
    QualityLevel.QUALITY: ['gpt-4o', 'claude-sonnet-4-20250514', 'gpt-4o-mini'],
    QualityLevel.DEEP: ['o1-preview', 'claude-opus-4-20250514', 'gpt-4o']
}

# Provider API endpoints
PROVIDER_ENDPOINTS = {
    'openai': 'https://api.openai.com/v1/chat/completions',
    'anthropic': 'https://api.anthropic.com/v1/messages',
    'google': 'https://generativelanguage.googleapis.com/v1/models'
}

# ============================================================================
# DATABASE HELPERS
# ============================================================================

def get_db_connection():
    """Get PostgreSQL connection."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from urllib.parse import urlparse
    
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    result = urlparse(db_url)
    
    conn = psycopg2.connect(
        host=result.hostname,
        port=result.port or 5432,
        database=result.path[1:],
        user=result.username,
        password=result.password
    )
    return conn


def extract_memory_nodes(user_id: str, message: str, response: str, model: str = "claude-haiku-4-5-20251001") -> list:
    """Extract semantic memories from conversation and store in memory_nodes.
    
    Uses lightweight LLM to extract 1-3 key facts/preferences from each exchange.
    """
    import json
    import requests
    
    extraction_prompt = f"""Extract 0-3 key facts, preferences, or contextual information from this conversation.
Return ONLY a JSON array of objects, each with:
- "type": one of: fact, preference, context, entity
- "content": the factual information (short, specific)
- "confidence": 0.7-1.0 (how certain this is a useful memory)

Rules:
- Only extract if there's genuinely useful info to remember
- Keep content under 50 words
- Focus on preferences, facts about user, project context
- Return [] if nothing worth remembering

Conversation:
User: {message[:500]}
Assistant: {response[:500]}

JSON:"""
    
    try:
        # Use OpenRouter for extraction (cheap, fast)
        api_key = os.environ.get('OPENROUTER_API_KEY')
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY environment variable is required")
        resp = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://lipaira.ai',
                'X-Title': 'Lipaira'
            },
            json={
                'model': 'anthropic/claude-haiku-4.5',
                'messages': [
                    {'role': 'system', 'content': 'You extract structured memories from conversations. Return ONLY valid JSON, no explanation.'},
                    {'role': 'user', 'content': extraction_prompt}
                ],
                'max_tokens': 500,
                'temperature': 0.3
            },
            timeout=15
        )
        
        if resp.status_code != 200:
            logger.warning(f"Memory extraction failed: {resp.status_code}")
            return []
        
        result = resp.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '[]')
        
        # Parse JSON from response
        try:
            memories = json.loads(content)
        except:
            # Try to extract JSON from text
            import re
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                memories = json.loads(match.group())
            else:
                memories = []
        
        if not isinstance(memories, list):
            memories = []
        
        # Store in database
        import uuid
        conn = get_db_connection()
        cur = conn.cursor()
        # Collect node IDs for embedding generation
        stored_nodes = []
        
        for mem in memories:
            if not isinstance(mem, dict):
                continue
            node_type = mem.get('type', 'fact')
            mem_content = mem.get('content', '')
            confidence = min(1.0, max(0.5, mem.get('confidence', 0.8)))
            
            if mem_content and len(mem_content) < 500:
                node_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO memory_nodes (id, user_id, node_type, content, confidence, source, created_at)
                    VALUES (%s, %s, %s, %s, %s, 'conversation', NOW())
                """, (node_id, user_id, node_type, mem_content, confidence))
                stored_nodes.append((node_id, mem_content))
                stored += 1

        conn.commit()
        cur.close()
        conn.close()

        # Generate embeddings after commit (we're already in a background thread)
        if stored_nodes:
            try:
                from memory_embeddings import store_embedding
                embed_conn = get_db_connection()
                for node_id, content in stored_nodes:
                    store_embedding(node_id, user_id, content, embed_conn)
                embed_conn.close()
            except Exception as e:
                logger.warning(f"[extract_memory_nodes] embedding generation failed: {e}")

        if stored > 0:
            logger.warning(f"Stored {stored} memory nodes for user {user_id}")
        
        return memories
        
    except Exception as e:
        logger.warning(f"Memory extraction error: {e}")
        return []


def row_to_dict(cursor, row):
    """Convert row to dict."""
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


# ============================================================================
# PROVIDER KEY MANAGEMENT
# ============================================================================

class ProviderKeyManager:
    """Manages encrypted provider API keys."""
    
    # Master keys (encrypted in DB, decrypted at request time)
    MASTER_KEYS = {}  # In production: load from encrypted DB
    
    @classmethod
    def get_key(cls, provider: str) -> str:
        """Get decrypted provider key."""
        env_var_name = f'{provider.upper()}_API_KEY'
        # Check environment first (for testing)
        env_key = os.environ.get(env_var_name)
        logger.info(f"get_key({provider}): checking env {env_var_name} = {repr(env_key)[:50]}")
        if env_key:
            logger.info(f"get_key({provider}): found in env")
            return env_key
        
        # Check in-memory cache
        if provider in cls.MASTER_KEYS:
            logger.info(f"get_key({provider}): found in MASTER_KEYS")
            return cls.MASTER_KEYS[provider]
        
        # Check database
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT encrypted_key FROM provider_keys WHERE provider = %s AND is_default = true",
                (provider,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                logger.info(f"get_key({provider}): found in DB")
                # In production: decrypt here using pgcrypto
                return row[0]  # Would be decrypted
        except Exception as e:
            logger.error(f"Error fetching provider key: {e}")
        
        # Check AWS Secrets Manager as fallback
        try:
            from providers import get_secret
            # Map provider names to environment variable names
            # These match the keys in SECRET_MAP in providers.py
            secret_map = {
                'minimax': 'OPENROUTER_API_KEY',
                'openrouter': 'OPENROUTER_API_KEY',
                'anthropic': 'OPENROUTER_API_KEY',
                'openai': 'OPENROUTER_API_KEY',  # Can use OpenRouter for any model
                'google': 'GOOGLE_API_KEY',
            }
            secret_name = secret_map.get(provider, f"{provider.upper()}_API_KEY")
            key = get_secret(secret_name)
            if key:
                logger.info(f"get_key({provider}): found in ASM as {secret_name}")
                return key
            else:
                logger.warning(f"get_key({provider}): secret {secret_name} not found in ASM")
        except Exception as e:
            logger.warning(f"ASM key lookup failed for {provider}: {e}")
        
        logger.warning(f"get_key({provider}): no key found")
        return None
    
    @classmethod
    def set_key(cls, provider: str, api_key: str, label: str = 'primary'):
        """Store encrypted provider key."""
        # In production: encrypt before storing
        cls.MASTER_KEYS[provider] = api_key
        logger.info(f"Provider key set for: {provider}")


# ============================================================================
# UNIFIED LLM PROVIDER ADAPTERS
# ============================================================================

import json

class ProviderAdapter:
    """Base adapter for LLM providers."""
    @staticmethod
    def get_headers(api_key: str) -> dict: raise NotImplementedError
    @staticmethod
    def build_request(provider: str, model: str, messages: list, tools: list = None, system: str = None, max_tokens: int = 4000) -> dict: raise NotImplementedError
    @staticmethod
    def parse_response(response_data: dict) -> dict: raise NotImplementedError

class AnthropicAdapter(ProviderAdapter):
    @staticmethod
    def get_headers(api_key: str) -> dict: return {'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'}
    @staticmethod
    def build_request(provider: str, model: str, messages: list, tools: list = None, system: str = None, max_tokens: int = 4000) -> dict:
        system_content = system or ""
        msgs = [msg for msg in messages if msg['role'] != 'system']
        for msg in messages:
            if msg['role'] == 'system' and not system_content: system_content = msg['content']
        data = {'model': model, 'messages': msgs, 'max_tokens': max_tokens}
        if system_content: data['system'] = system_content
        if tools: data['tools'] = tools
        return data
    @staticmethod
    def parse_response(response_data: dict) -> dict:
        blocks = response_data.get('content', [])
        text = ' '.join(b.get('text', '') for b in blocks if b.get('type') == 'text')
        return {'content': text, 'stop_reason': response_data.get('stop_reason', 'end_turn'), 'raw_content': blocks,
                'input_tokens': response_data.get('usage', {}).get('input_tokens', 0),
                'output_tokens': response_data.get('usage', {}).get('output_tokens', 0)}

class OpenAIAdapter(ProviderAdapter):
    @staticmethod
    def get_headers(api_key: str) -> dict: return {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    @staticmethod
    def build_request(provider: str, model: str, messages: list, tools: list = None, system: str = None, max_tokens: int = 4000) -> dict:
        system_content = system or ""
        msgs = [msg for msg in messages if msg['role'] != 'system']
        for msg in messages:
            if msg['role'] == 'system' and not system_content: system_content = msg['content']
        if system_content: msgs = [{'role': 'system', 'content': system_content}] + msgs
        data = {'model': model, 'messages': msgs, 'max_tokens': max_tokens}
        if tools: data['functions'] = tools; data['function_call'] = 'auto'
        return data
    @staticmethod
    def parse_response(response_data: dict) -> dict:
        msg = response_data.get('choices', [{}])[0].get('message', {})
        fc = msg.get('function_call')
        blocks = []
        if fc: blocks.append({'type': 'function_call', 'name': fc.get('name'), 'input': json.loads(fc.get('arguments', '{}')), 'id': fc.get('call_id')})
        text = msg.get('content', '')
        if text: blocks.append({'type': 'text', 'text': text})
        return {'content': text, 'stop_reason': 'tool_use' if fc else 'end_turn', 'raw_content': blocks,
                'input_tokens': response_data.get('usage', {}).get('prompt_tokens', 0),
                'output_tokens': response_data.get('usage', {}).get('completion_tokens', 0)}

class GoogleAdapter(ProviderAdapter):
    @staticmethod
    def get_headers(api_key: str) -> dict: return {'Content-Type': 'application/json'}
    @staticmethod
    def build_request(provider: str, model: str, messages: list, tools: list = None, system: str = None, max_tokens: int = 4000) -> dict:
        contents = [{'role': msg['role'], 'parts': [{'text': msg['content']}]} for msg in messages if msg['role'] != 'system']
        data = {'contents': contents, 'generationConfig': {'maxOutputTokens': max_tokens}}
        if system: data['systemInstruction'] = {'parts': [{'text': system}]}
        if tools: data['tools'] = tools
        return data
    @staticmethod
    def parse_response(response_data: dict) -> dict:
        cand = response_data.get('candidates', [{}])[0]
        parts = cand.get('content', {}).get('parts', [])
        text = ' '.join(p.get('text', '') for p in parts)
        return {'content': text, 'stop_reason': 'end_turn', 'raw_content': [{'type': 'text', 'text': text}],
                'input_tokens': response_data.get('usageMetadata', {}).get('promptTokenCount', 0),
                'output_tokens': response_data.get('usageMetadata', {}).get('candidatesTokenCount', 0)}


class MiniMaxAdapter(ProviderAdapter):
    """MiniMax API adapter - routes through OpenRouter."""
    @staticmethod
    def get_headers(api_key: str) -> dict: return {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json', 'HTTP-Referer': 'https://lipaira.ai', 'X-Title': 'Lipaira'}
    @staticmethod
    def build_request(provider: str, model: str, messages: list, tools: list = None, system: str = None, max_tokens: int = 4000) -> dict:
        # Route through OpenRouter
        msgs = []
        if system:
            msgs.append({'role': 'system', 'content': system})
        msgs.extend([{'role': msg['role'], 'content': msg['content']} for msg in messages if msg['role'] != 'system'])
        # OpenRouter model format: provider/model
        data = {'model': f'minimax/{model}', 'messages': msgs, 'max_tokens': max_tokens}
        return data
    @staticmethod
    def parse_response(response_data: dict) -> dict:
        choice = response_data.get('choices', [{}])[0]
        msg = choice.get('message', {})
        content = msg.get('content', '')
        usage = response_data.get('usage', {})
        return {
            'content': content,
            'stop_reason': choice.get('finish_reason', 'end_turn'),
            'raw_content': [{'type': 'text', 'text': content}],
            'input_tokens': usage.get('prompt_tokens', 0),
            'output_tokens': usage.get('completion_tokens', 0)
        }


# OpenRouter adapter - routes ALL models through OpenRouter
class OpenRouterAdapter(ProviderAdapter):
    """OpenRouter adapter - allows any OpenRouter-supported model."""
    @staticmethod
    def get_headers(api_key: str) -> dict: return {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json', 'HTTP-Referer': 'https://lipaira.ai', 'X-Title': 'Lipaira'}
    @staticmethod
    def build_request(provider: str, model: str, messages: list, tools: list = None, system: str = None, max_tokens: int = 4000) -> dict:
        msgs = []
        if system:
            msgs.append({'role': 'system', 'content': system})
        
        # Preserve all message fields including tool_calls and tool_call_id
        for msg in messages:
            if msg['role'] == 'system':
                continue
            new_msg = {'role': msg['role'], 'content': msg.get('content')}
            # Preserve tool_calls for assistant messages
            if msg.get('tool_calls'):
                new_msg['tool_calls'] = msg['tool_calls']
            # Preserve tool_call_id for tool messages
            if msg.get('tool_call_id'):
                new_msg['tool_call_id'] = msg['tool_call_id']
            # Preserve name for tool messages if present
            if msg.get('name'):
                new_msg['name'] = msg['name']
            msgs.append(new_msg)
        
        # Map common model names to OpenRouter format
        model_map = {
            # Claude models
            'claude-sonnet-4-20250514': 'anthropic/claude-sonnet-4.6',
            'claude-haiku-4-5-20251001': 'anthropic/claude-haiku-4.5',
            'claude-opus-4-20250514': 'anthropic/claude-opus-4.6',
            # OpenAI models
            'gpt-4o': 'openai/gpt-4o',
            'gpt-4o-mini': 'openai/gpt-4o-mini',
            'gpt-5': 'openai/gpt-5',
            # MiniMax models
            'minimax-01': 'minimax/minimax-m2.7',
            'minimax-m2.5': 'minimax/minimax-m2.5',
            'minimax-m2.7': 'minimax/minimax-m2.7',
            # Other models
            'o1-preview': 'openai/o1-preview',
            'o1-mini': 'openai/o1-mini',
        }
        or_model = model_map.get(model, model)  # Use as-is if not in map
        
        data = {'model': or_model, 'messages': msgs, 'max_tokens': max_tokens}
        
        # Pass tools to OpenRouter for Anthropic models
        if tools:
            data['tools'] = tools
        
        return data
    @staticmethod
    def parse_response(response_data: dict) -> dict:
        choice = response_data.get('choices', [{}])[0]
        msg = choice.get('message', {})
        content = msg.get('content', '')
        usage = response_data.get('usage', {})
        
        # Check if response contains tool_use blocks
        tool_use = msg.get('tool_calls', [])
        raw_content = []
        
        if tool_use:
            # Has tool_use blocks
            for tc in tool_use:
                raw_content.append({
                    'type': 'tool_use',
                    'id': tc.get('id', ''),
                    'name': tc.get('function', {}).get('name', ''),
                    'input': tc.get('function', {}).get('arguments', {})
                })
            # Also add any text content
            if content:
                raw_content.append({'type': 'text', 'text': content})
        else:
            # No tool_use - just text
            raw_content = [{'type': 'text', 'text': content}]
        
        stop_reason = choice.get('finish_reason', 'end_turn')
        if tool_use:
            stop_reason = 'tool_use'
        
        return {
            'content': content,
            'stop_reason': stop_reason,
            'raw_content': raw_content,
            'input_tokens': usage.get('prompt_tokens', 0),
            'output_tokens': usage.get('completion_tokens', 0)
        }


ADAPTERS = {'anthropic': AnthropicAdapter(), 'openai': OpenAIAdapter(), 'google': GoogleAdapter(), 'minimax': OpenRouterAdapter(), 'openrouter': OpenRouterAdapter()}
ENDPOINTS = {'anthropic': 'https://api.anthropic.com/v1/messages', 'openai': 'https://api.openai.com/v1/chat/completions', 'google': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', 'minimax': 'https://openrouter.ai/api/v1/chat/completions', 'openrouter': 'https://openrouter.ai/api/v1/chat/completions'}

def call_provider(provider: str, model: str, messages: list, tools: list = None, system: str = None, max_tokens: int = 4000) -> dict:
    """Unified LLM call - works with all providers."""
    if provider not in ADAPTERS: return {'success': False, 'error': f'Unknown provider: {provider}'}
    adapter = ADAPTERS[provider]
    # For minimax through OpenRouter, use the minimax key
    api_key = ProviderKeyManager.get_key(provider)
    if not api_key: return {'success': False, 'error': f'No API key for: {provider}'}
    try:
        request = adapter.build_request(provider, model, messages, tools, system, max_tokens)
        endpoint = ENDPOINTS[provider].format(model=model)
        if provider == 'google': endpoint += f'?key={api_key}'
        headers = adapter.get_headers(api_key)
        
        response = requests.post(endpoint, headers=headers, json=request, timeout=60)
        if response.status_code != 200: return {'success': False, 'error': f'{provider} error: {response.text}'}
        parsed = adapter.parse_response(response.json())
        return {'success': True, 'content': parsed['content'], 'stop_reason': parsed['stop_reason'], 'raw_content': parsed['raw_content'],
                'model': model, 'provider': provider, 'input_tokens': parsed['input_tokens'], 'output_tokens': parsed['output_tokens'],
                'total_tokens': parsed['input_tokens'] + parsed['output_tokens']}
    except Exception as e:
        logger.error(f"Provider call error: {e}")
        return {'success': False, 'error': str(e)}

# Legacy compatibility
class LLMRouter:
    def __init__(self): self.usage_tracker = None
    def get_model_for_quality(self, quality, user_tier='free'): return {'model': 'claude-haiku-4-5-20251001', 'provider': 'anthropic'}
    def detect_task_complexity(self, messages): return 'balanced'
    def route(self, messages, quality=None, model=None, user_id=None, user_tier='free'): return self.get_model_for_quality(quality or 'balanced', user_tier)
    def call_provider(self, provider, model, messages, max_tokens=4000, tools=None, system=None):
        return call_provider(provider, model, messages, tools, system, max_tokens)

llm_router = LLMRouter()


# ============================================================================
# USAGE TRACKING
# ============================================================================

class UsageTracker:
    """Track and bill usage."""
    
    # Map OpenRouter model slugs to our pricing IDs
    MODEL_MAP = {
        # Anthropic (direct)
        'claude-haiku-4-5-20251001': 'claude-haiku-4-5',
        'claude-sonnet-4-5-20251001': 'claude-sonnet-4-5',
        'claude-opus-4-5-20251001': 'claude-opus-4-5',
        # Anthropic via OpenRouter
        'anthropic/claude-haiku-4.5': 'claude-haiku-4-5',
        'anthropic/claude-sonnet-4.6': 'claude-sonnet-4-5',
        'anthropic/claude-opus-4.6': 'claude-opus-4-5',
        # OpenAI (direct)
        'openai/gpt-4o-2024-08-06': 'gpt-4o',
        'openai/gpt-4o-mini-2024-07-18': 'gpt-4o-mini',
        # OpenAI via OpenRouter
        'openai/gpt-4o': 'gpt-4o',
        'openai/gpt-4o-mini': 'gpt-4o-mini',
        'openai/gpt-5': 'gpt-5',
        'openai/o1-preview': 'o1-preview',
        'openai/o1-mini': 'o1-mini',
        # MiniMax via OpenRouter
        'minimax/minimax-m2.7': 'minimax-m2.7',
        'minimax/minimax-m2.5': 'minimax-m2.5',
        'minimax/minimax-01': 'minimax-01',
        # Google
        'google/gemini-2.5-flash-lite': 'gemini-2.0-flash',
        'google/gemini-1.5-flash-8b-exp': 'gemini-2.0-flash',
    }
    
    # Fallback costs (if database not available) - per 1M tokens in dollars
    # These are our cost + markup
    FALLBACK_COSTS = {
        'claude-haiku-4-5': {'input': 1.04, 'output': 5.20},
        'claude-sonnet-4-5': {'input': 3.90, 'output': 19.50},
        'claude-opus-4-5': {'input': 15.00, 'output': 75.00},
        'gpt-4o': {'input': 3.25, 'output': 13.00},
        'gpt-4o-mini': {'input': 0.20, 'output': 0.78},
        'gpt-5': {'input': 10.00, 'output': 30.00},
        'o1-preview': {'input': 15.00, 'output': 60.00},
        'o1-mini': {'input': 3.00, 'output': 12.00},
        'minimax-m2.7': {'input': 0.30, 'output': 1.50},
        'minimax-m2.5': {'input': 0.20, 'output': 1.00},
        'minimax-01': {'input': 0.25, 'output': 1.25},
    }
    
    @classmethod
    def get_pricing(cls, model: str) -> dict:
        """Get pricing - try dynamic from OpenRouter first, then database, then fallback."""
        # First, try to get dynamic pricing from OpenRouter
        try:
            from billing import get_openrouter_pricing
            or_pricing = get_openrouter_pricing()
            if model in or_pricing:
                p = or_pricing[model]
                return {'input': p.get('input', 0.1), 'output': p.get('output', 0.1)}
            
            # Also check mapped model
            pricing_id = cls.MODEL_MAP.get(model, model)
            if pricing_id in or_pricing:
                p = or_pricing[pricing_id]
                return {'input': p.get('input', 0.1), 'output': p.get('output', 0.1)}
        except Exception as e:
            logger.warning(f"Dynamic pricing lookup failed: {e}")
        
        # Fallback to database or static costs
        pricing_id = cls.MODEL_MAP.get(model, model)
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                "SELECT our_input_cost, our_output_cost FROM pricing_tiers WHERE model_id = %s AND is_active = TRUE",
                (pricing_id,)
            )
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if row:
                return {'input': float(row['our_input_cost']), 'output': float(row['our_output_cost'])}
        except Exception as e:
            logger.warning(f"DB pricing lookup failed: {e}")
        
        # Fallback
        return cls.FALLBACK_COSTS.get(pricing_id, {'input': 3.00, 'output': 15.00})
    
    @classmethod
    def calculate_cost(cls, provider: str, model: str, input_tokens: int, output_tokens: int = 0) -> float:
        """Calculate cost for input + output tokens using database pricing."""
        pricing = cls.get_pricing(model)
        input_cost = (input_tokens / 1_000_000) * pricing['input']
        output_cost = (output_tokens / 1_000_000) * pricing['output']
        return input_cost + output_cost
    
    @classmethod
    def record_usage(cls, user_id: str, provider: str, model: str, 
                    input_tokens: int, output_tokens: int) -> dict:
        """Record usage and deduct credits.
        
        Note: Fee is collected at credit purchase (POS), not per-call.
        Credits are deducted 1:1 against our provider cost.
        """
        total_tokens = input_tokens + output_tokens
        cost = cls.calculate_cost(provider, model, input_tokens, output_tokens)
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Atomic check-and-deduct: only deduct if balance sufficient
            cursor.execute("""
                UPDATE users 
                SET credits = credits - %s 
                WHERE id = %s AND credits >= %s
                RETURNING credits
            """, (cost, user_id, cost))
            
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return {'success': False, 'error': 'Insufficient credits'}
            
            # Record usage only if deduction succeeded
            cursor.execute("""
                INSERT INTO llm_usage 
                (id, user_id, provider, model, input_tokens, output_tokens, 
                 provider_cost, mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'we_bill')
            """, (str(uuid.uuid4()), user_id, provider, model, input_tokens,
                   output_tokens, cost))
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'cost': cost,
                'deducted': cost
            }
        except Exception as e:
            logger.error(f"Usage recording error: {e}")
            return {'success': False, 'error': str(e)}


# ============================================================================
# API KEY AUTHENTICATION
# ============================================================================

def require_auth(f):
    """Decorator for API Key authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Support both X-Lipaira-Key, Authorization: Bearer, and query param 'key'
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            api_key = auth_header[7:]
        else:
            api_key = request.headers.get('X-Lipaira-Key') or request.args.get('api_key') or request.args.get('key')
        
        if not api_key:
            return jsonify({'error': 'Missing API key (use X-Lipaira-Key or Authorization: Bearer)'}), 401
        
        # Validate key
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Support both hashed and unhashed keys for backward compatibility
            # Try both: hash of full key, hash of key without prefix, and raw key
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            key_part = api_key.replace('sk-nexus-', '').replace('lp-', '')
            key_hash_part = hashlib.sha256(key_part.encode()).hexdigest()
            
            cursor.execute("""
                SELECT ak.user_id, u.email, u.credits, u.subscription_tier, u.role
                FROM api_keys ak
                JOIN users u ON u.id = ak.user_id
                WHERE (ak.key_hash = %s OR ak.key_hash = %s OR ak.key_hash = %s OR ak.key_hash = %s) AND ak.is_active = true
            """, (key_hash, key_hash_part, api_key, key_part))
            
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return jsonify({'error': 'Invalid API key'}), 401
            
            # Update last used - match any of the possible key formats
            cursor.execute(
                "UPDATE api_keys SET last_used = %s WHERE (key_hash = %s OR key_hash = %s OR key_hash = %s OR key_hash = %s)",
                (datetime.now().isoformat(), key_hash, key_hash_part, api_key, key_part)
            )
            conn.commit()
            conn.close()
            
            g.user_id = row[0]
            g.user_email = row[1]
            g.user_credits = float(row[2])
            g.user_tier = row[3]
            g.user_role = row[4] or 'user'
            
            # Check rate limit based on credit balance
            current_limit = get_rate_limit(g.user_credits)
            if not check_rate_limit(g.user_id, g.user_credits):
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'your_limit': current_limit,
                    'your_credits': g.user_credits,
                    'purchase_credits': 'Add credits for higher limits'
                }), 429
            
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return jsonify({'error': 'Authentication failed'}), 401
        
        return f(*args, **kwargs)
    
    return decorated


def require_admin(f):
    """
    Decorator for admin-only endpoints.
    Requires @require_auth to be applied first.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'user_role') or g.user_role != 'admin':
            return jsonify({'error': 'Insufficient privileges'}), 403
        return f(*args, **kwargs)
    return decorated


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

def _generate_verification_code():
    """Generate 6-digit numeric code."""
    return str(random.randint(100000, 999999))

def _send_verification_email(email: str, code: str):
    """Send verification code via Resend."""
    import requests
    from providers import get_secret
    
    resend_key = get_secret("RESEND_API_KEY")
    if not resend_key:
        logger.warning("RESEND_API_KEY not set, skipping verification email")
        return False
    
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": "Lipaira <noreply@lipaira.ai>",
                "to": [email],
                "subject": "Verify your Lipaira account",
                "html": f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 500px; margin: 0 auto;">
                    <h1>Welcome to Lipaira!</h1>
                    <p>Your verification code is:</p>
                    <div style="background: #f3f4f6; padding: 20px; text-align: center; font-size: 32px; letter-spacing: 8px; font-weight: bold; border-radius: 8px;">
                        {code}
                    </div>
                    <p>This code expires in 10 minutes.</p>
                    <p>If you didn't create this account, please ignore this email.</p>
                </div>
                """
            },
            timeout=30
        )
        return response.ok
    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")
        return False


# Register supplementary routes individually (after require_auth is defined)
try:
    create_swarm_routes(app, require_auth)
except Exception as e:
    logger.warning(f"Swarm routes registration failed: {e}")

try:
    create_internal_routes(app)
except Exception as e:
    logger.warning(f"Internal routes registration failed: {e}")

try:
    create_automation_routes(app, require_auth)
except Exception as e:
    logger.warning(f"Automation routes registration failed: {e}")

try:
    create_twilio_routes(app, require_auth)
except Exception as e:
    logger.warning(f"Twilio routes registration failed: {e}")

try:
    create_push_routes(app, require_auth)  # Push notifications
except Exception as e:
    logger.warning(f"Push routes registration failed: {e}")

try:
    create_pattern_routes(app, require_auth)  # Pattern detection
except Exception as e:
    logger.warning(f"Pattern routes registration failed: {e}")

logger.info("Supplementary route registration complete")


@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register new user - requires email + phone verification."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    password = data.get('password', '')
    name = data.get('name', email.split('@')[0]) if email else 'User'
    
    # Validate required fields
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    if not phone:
        return jsonify({'error': 'Phone number is required'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    
    # Basic email validation
    import re
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Phone validation (basic - allow digits, +, spaces, -, parentheses)
    phone_clean = re.sub(r'[^\d+]', '', phone)
    if len(phone_clean) < 10:
        return jsonify({'error': 'Invalid phone number'}), 400
    
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check existing email
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Email already registered'}), 400
        
        # Check existing phone
        cursor.execute("SELECT id FROM users WHERE phone = %s", (phone,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Phone number already registered'}), 400
        
        # Generate verification code
        verification_code = _generate_verification_code()
        from datetime import datetime, timedelta
        verification_expires = datetime.now() + timedelta(minutes=10)
        
        # Create user (not verified yet)
        user_id = str(uuid.uuid4())
        password_hash = hash_password(password)
        
        cursor.execute("""
            INSERT INTO users (id, email, phone, password_hash, name, 
                             credits, subscription_tier, email_verified, 
                             verification_code, verification_expires, is_active)
            VALUES (%s, %s, %s, %s, %s, 0, 'free', false, %s, %s, true)
        """, (user_id, email, phone, password_hash, name, 
              verification_code, verification_expires))
        
        # Generate API key but don't return it yet (needs verification)
        api_key = f"lp-{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        cursor.execute("""
            INSERT INTO api_keys (id, user_id, key_hash, name, active)
            VALUES (%s, %s, %s, %s, false)
        """, (str(uuid.uuid4()), user_id, key_hash, 'Default Key'))
        
        # Create default LLM config
        cursor.execute("""
            INSERT INTO user_llm_config (id, user_id, provider, model, quality_preference, auto_route)
            VALUES (%s, %s, %s, %s, %s, true)
        """, (str(uuid.uuid4()), user_id, 'openrouter', 'minimax/minimax-m2.7', 'balanced'))
        
        conn.commit()
        
        # Provision user's database isolation (async, non-blocking)
        # Free tier: schema isolation; Paid tier: dedicated container
        threading.Thread(
            target=provision_user,
            args=(user_id, 'free'),
            daemon=True
        ).start()
        
        # Send verification email
        _send_verification_email(email, verification_code)
        
        # Critical audit log — reject registration if this fails
        try:
            log_audit(user_id, "register", {"email": email}, success=True)
        except Exception as audit_err:
            logger.error(f"CRITICAL audit failure on register: {audit_err}")
            raise AuditLogError(f"Audit log failed for register: {audit_err}")
        
        conn.close()
        
        return jsonify({
            'user_id': user_id,
            'email': email,
            'verification_required': True,
            'next_step': '/verify-email',
            'message': 'Verification code sent to your email'
        }), 201
        
    except AuditLogError:
        raise  # Already handled
    except Exception as e:
        err_str = str(e).lower()
        if any(x in err_str for x in ['could not translate', 'connection refused', 'pgcode', 'psycopg2', 'operationalerror']):
            logger.error(f"CRITICAL: DB unavailable for register audit: {e}")
            try:
                log_audit("unknown", "register", {"email": email}, success=False, error=str(e))
            except:
                pass
            return jsonify({'error': 'Service temporarily unavailable'}), 503
        logger.error(f"Register error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login and get API key - requires verified email."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    # Rate limit check: 5 failed attempts per email per 15 minutes
    # Redis unavailable fallback: in-memory counter (max 10, cleared on restart)
    login._attempt_counts = getattr(login, '_attempt_counts', {})
    
    try:
        import redis
        redis_url = os.environ.get('REDIS_URL', 'redis://lipaira-redis:6379')
        r = redis.from_url(redis_url)
        attempts_key = f"login_attempts:{email}"
        attempts = r.get(attempts_key)
        if attempts and int(attempts) >= 5:
            ttl = r.ttl(attempts_key)
            if ttl > 0:
                return jsonify({'error': 'Too many login attempts. Please wait 15 minutes.'}), 429
    except Exception as e:
        logger.warning(f"Rate limit Redis unavailable: {e}")
        # Fallback: in-memory counter (max 10, cleared on restart)
        if login._attempt_counts.get(email, 0) >= 10:
            return jsonify({'error': 'Too many login attempts. Please wait 15 minutes.'}), 429
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch user by email
        cursor.execute("""
            SELECT id, email, name, credits, subscription_tier, password_hash, 
                   email_verified, phone_verified, is_active, role
            FROM users WHERE email = %s
        """, (email,))
        
        row = cursor.fetchone()
        
        if not row or not verify_password(password, row[5]):
            # Increment failed attempt counter
            try:
                import redis
                r = redis.from_url(os.environ.get('REDIS_URL', 'redis://lipaira-redis:6379'))
                r.incr(attempts_key)
                r.expire(attempts_key, 900)  # 15 minutes
            except:
                login._attempt_counts[email] = login._attempt_counts.get(email, 0) + 1
            
            conn.close()
            return jsonify({'error': 'Invalid credentials'}), 401
        
        user_id, user_email, name, credits, tier, _, email_verified, phone_verified, is_active, role = row
        role = role or 'user'
        
        # Clear failed attempts on successful login
        try:
            import redis
            r = redis.from_url(os.environ.get('REDIS_URL', 'redis://lipaira-redis:6379'))
            r.delete(attempts_key)
        except:
            if email in login._attempt_counts:
                del login._attempt_counts[email]
        
        # Check if account is active
        if not is_active:
            conn.close()
            return jsonify({'error': 'Account is disabled'}), 403
        
        # Check email verification
        if not email_verified:
            conn.close()
            return jsonify({
                'user_id': user_id,
                'email_verified': False,
                'next_step': '/verify-email',
                'message': 'Please verify your email'
            }), 403
        
        user = {
            'id': user_id,
            'email': user_email,
            'name': name,
            'credits': float(credits),
            'subscription_tier': tier,
            'role': role
        }
        
        # Get or create active API key
        cursor.execute("""
            SELECT key_hash FROM api_keys 
            WHERE user_id = %s AND active = true LIMIT 1
        """, (user_id,))
        
        key_row = cursor.fetchone()
        
        if key_row:
            # Reconstruct full API key - need to store differently or fetch prefix
            cursor.execute("""
                SELECT id FROM api_keys 
                WHERE user_id = %s AND active = true LIMIT 1
            """, (user_id,))
            key_id_row = cursor.fetchone()
            api_key = f"lp-{secrets.token_urlsafe(32)}"
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            cursor.execute("""
                UPDATE api_keys SET key_hash = %s, active = true WHERE id = %s
            """, (key_hash, key_id_row[0]))
        else:
            api_key = f"lp-{secrets.token_urlsafe(32)}"
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            cursor.execute("""
                INSERT INTO api_keys (id, user_id, key_hash, name, active)
                VALUES (%s, %s, %s, %s, true)
            """, (str(uuid.uuid4()), user_id, key_hash, 'Default Key'))
        
        conn.commit()
        
        # Critical audit log — reject login if this fails
        try:
            log_audit(user_id, "login", {"email": email}, success=True)
        except Exception as audit_err:
            logger.error(f"CRITICAL audit failure on login: {audit_err}")
            raise AuditLogError(f"Audit log failed for login: {audit_err}")
        
        conn.close()
        
        return jsonify({
            'user': user, 
            'api_key': api_key,
            'email_verified': True,
            'role': role
        })
        
    except AuditLogError:
        raise  # Already handled
    except Exception as e:
        # DB unavailable = critical audit failure for login
        err_str = str(e).lower()
        if any(x in err_str for x in ['could not translate', 'connection refused', 'pgcode', 'psycopg2', 'operationalerror']):
            logger.error(f"CRITICAL: DB unavailable for login audit: {e}")
            try:
                log_audit("unknown", "login", {"email": email}, success=False, error=str(e))
            except:
                pass
            return jsonify({'error': 'Service temporarily unavailable'}), 503
        logger.error(f"Login error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/verify-email', methods=['POST'])
def verify_email():
    """Verify email with code."""
    data = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    code = data.get('code', '').strip()
    
    if not user_id or not code:
        return jsonify({'error': 'User ID and code required'}), 400
    
    if len(code) != 6 or not code.isdigit():
        return jsonify({'error': 'Invalid code format'}), 400
    
    try:
        from datetime import datetime
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user and verification code
        cursor.execute("""
            SELECT id, email, verification_code, verification_expires, email_verified
            FROM users WHERE id = %s
        """, (user_id,))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        db_user_id, email, stored_code, expires_at, already_verified = row
        
        if already_verified:
            conn.close()
            return jsonify({'message': 'Email already verified', 'verified': True})
        
        # Check if code matches
        if stored_code != code:
            conn.close()
            return jsonify({'error': 'Invalid verification code'}), 400
        
        # Check if expired
        if expires_at and datetime.now() > expires_at:
            conn.close()
            return jsonify({'error': 'Verification code expired'}), 400
        
        # Mark as verified
        cursor.execute("""
            UPDATE users SET email_verified = true, verification_code = NULL, 
                           verification_expires = NULL
            WHERE id = %s
        """, (user_id,))
        
        # Activate API key
        cursor.execute("""
            UPDATE api_keys SET active = true WHERE user_id = %s AND active = false
        """, (user_id,))
        
        # Get API key to return
        cursor.execute("""
            SELECT key_hash FROM api_keys WHERE user_id = %s AND active = true LIMIT 1
        """, (user_id,))
        key_row = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        # Return API key so user can proceed
        api_key = f"lp-{secrets.token_urlsafe(32)}"
        
        # Critical audit log — reject if this fails
        try:
            log_audit(user_id, "verify_email", {"email": email}, success=True)
        except Exception as audit_err:
            logger.error(f"CRITICAL audit failure on verify_email: {audit_err}")
            raise AuditLogError(f"Audit log failed for verify_email: {audit_err}")
        
        return jsonify({
            'verified': True,
            'message': 'Email verified successfully',
            'user_id': user_id,
            'api_key': api_key
        })
        
    except AuditLogError:
        raise  # Already handled
    except Exception as e:
        err_str = str(e).lower()
        if any(x in err_str for x in ['could not translate', 'connection refused', 'pgcode', 'psycopg2', 'operationalerror']):
            logger.error(f"CRITICAL: DB unavailable for verify_email audit: {e}")
            try:
                log_audit(user_id, "verify_email", {}, success=False, error=str(e))
            except:
                pass
            return jsonify({'error': 'Service temporarily unavailable'}), 503
        logger.error(f"Verify error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/resend-code', methods=['POST'])
def resend_code():
    """Resend verification code."""
    data = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    
    try:
        from datetime import datetime, timedelta
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user
        cursor.execute("""
            SELECT email, verification_expires FROM users WHERE id = %s
        """, (user_id,))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        email, expires_at = row
        
        # Check rate limit (can only resend once per 30 seconds)
        if expires_at and datetime.now() < expires_at - timedelta(seconds=600):
            # Already requested recently
            conn.close()
            return jsonify({'error': 'Please wait before requesting another code'}), 429
        
        # Generate new code
        new_code = _generate_verification_code()
        new_expires = datetime.now() + timedelta(minutes=10)
        
        cursor.execute("""
            UPDATE users SET verification_code = %s, verification_expires = %s
            WHERE id = %s
        """, (new_code, new_expires, user_id))
        
        conn.commit()
        conn.close()
        
        # Send new code
        _send_verification_email(email, new_code)
        
        return jsonify({'success': True, 'message': 'Verification code resent'})
        
    except Exception as e:
        logger.error(f"Resend error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# LOGOUT
# ============================================================================

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """
    Logout current session by revoking the presented API key.
    
    Note: This invalidates ONLY the presented API key (single session).
    If the user has multiple API keys (multiple devices/sessions),
    other sessions remain active. This is intentional — users may want
    to log out of one device without losing their session elsewhere.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing Authorization header'}), 401
    
    api_key = auth_header[7:]
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    key_part = api_key.replace('sk-nexus-', '').replace('lp-', '')
    key_hash_part = hashlib.sha256(key_part.encode()).hexdigest()
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Revoke only active keys (prevents double-revoke info leak)
        cursor.execute("""
            UPDATE api_keys 
            SET is_active = false, last_used = %s
            WHERE key_hash IN (%s, %s, %s, %s) AND is_active = true
            RETURNING id, user_id
        """, (datetime.now().isoformat(), key_hash, key_hash_part, api_key, key_part))
        
        revoked_row = cursor.fetchone()
        
        if revoked_row:
            revoked_id, audit_user_id = revoked_row
            
            # Critical audit log — reject if this fails
            try:
                log_audit(audit_user_id, "logout", {"key_id": revoked_id}, success=True)
            except Exception as audit_err:
                logger.error(f"CRITICAL audit failure on logout: {audit_err}")
                raise AuditLogError(f"Audit log failed for logout: {audit_err}")
        
        conn.commit()
        conn.close()
        
        if revoked_row:
            return jsonify({'message': 'Session revoked'}), 200
        else:
            return jsonify({'error': 'Invalid or already-revoked API key'}), 401
            
    except AuditLogError:
        raise  # Already handled
    except Exception as e:
        err_str = str(e).lower()
        if any(x in err_str for x in ['could not translate', 'connection refused', 'pgcode', 'psycopg2', 'operationalerror']):
            logger.error(f"CRITICAL: DB unavailable for logout: {e}")
            try:
                log_audit("unknown", "logout", {}, success=False, error=str(e))
            except:
                pass
            return jsonify({'error': 'Service temporarily unavailable'}), 503
        logger.error(f"Logout error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# DATA DELETION (GDPR/CCPA / HIPAA Right to Delete)
# ============================================================================

@app.route('/api/users/<user_id>', methods=['DELETE'])
@require_auth
def delete_user(user_id):
    """
    Delete all data for a user (GDPR Article 17 / CCPA / HIPAA right to delete).
    
    Logic:
    - User deletes own account → 200 (self-deletion allowed)
    - User deletes someone else's account → 403
    - Admin deletes any account → 200
    
    Deletes: users row, api_keys, user_integrations, memory_nodes,
      billing_history, operator_audit_log entries
    """
    calling_user_id = g.user_id
    calling_user_role = getattr(g, 'user_role', 'user')
    
    # Self-deletion allowed; admin can delete any; otherwise 403
    if calling_user_id != user_id and calling_user_role != 'admin':
        try:
            log_audit(calling_user_id, "delete_user_unauthorized", 
                     {"target_user_id": user_id}, success=False)
        except:
            pass
        return jsonify({'error': 'Forbidden — can only delete your own account'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify user exists
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Delete in order: audit log → api keys → integrations → billing → memory → users
        tables_order = [
            ("operator_audit_log", "user_id"),
            ("api_keys", "user_id"),
            ("user_integrations", "user_id"),
            ("billing_history", "user_id"),
            ("memory_nodes", "user_id"),
            ("users", "id"),
        ]
        
        deleted_counts = {}
        for table, col in tables_order:
            # Try to delete; ignore if table doesn't exist (idempotent)
            try:
                cursor.execute(f"DELETE FROM {table} WHERE {col} = %s", (user_id,))
                deleted_counts[table] = cursor.rowcount
            except Exception as del_err:
                # Table may not exist — continue
                deleted_counts[table] = 0
        
        conn.commit()
        conn.close()
        
        # Log the successful deletion
        try:
            log_audit(calling_user_id, "delete_user", 
                     {"deleted_user_id": user_id, "tables": deleted_counts}, success=True)
        except Exception:
            pass  # Don't fail the deletion request if audit fails
        
        return jsonify({
            'message': f'User {user_id} and all associated data deleted',
            'deleted': {
                'operator_audit_log': deleted_counts.get('operator_audit_log', 0),
                'api_keys': deleted_counts.get('api_keys', 0),
                'user_integrations': deleted_counts.get('user_integrations', 0),
                'billing_history': deleted_counts.get('billing_history', 0),
                'memory_nodes': deleted_counts.get('memory_nodes', 0),
                'users': deleted_counts.get('users', 0),
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Delete user error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ONBOARDING
# ============================================================================

@app.route('/api/onboarding', methods=['POST'])
@require_auth
def onboarding():
    """Complete onboarding - set user's name and get started."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'name is required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users SET name = %s, updated_at = NOW()
            WHERE id = %s
        """, (name, g.user_id))
        conn.commit()
        
        # Get updated user
        cursor.execute("""
            SELECT id, email, name, credits, subscription_tier
            FROM users WHERE id = %s
        """, (g.user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'id': row[0],
                'email': row[1],
                'name': row[2],
                'credits': row[3],
                'tier': row[4]
            },
            'message': f'Welcome, {name}! You are now in the chat.'
        })
        
    except Exception as e:
        logger.error(f"Onboarding error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/onboarding/status', methods=['GET'])
@require_auth
def onboarding_status():
    """Check if user has completed onboarding."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT onboarded, display_name 
            FROM user_profiles 
            WHERE user_id = %s
        """, (g.user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            return jsonify({
                'completed': True,
                'display_name': row[1]
            })
        return jsonify({'completed': False})
        
    except Exception as e:
        logger.error(f"Onboarding status error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/onboarding/complete', methods=['POST'])
@require_auth
def onboarding_complete():
    """Complete onboarding - save display name."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'name is required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_profiles (user_id, display_name, onboarded, onboarded_at, updated_at)
            VALUES (%s, %s, true, NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                onboarded = true,
                onboarded_at = NOW(),
                updated_at = NOW()
        """, (g.user_id, name))
        
        # Also update users table name
        cursor.execute("""
            UPDATE users SET name = %s, updated_at = NOW()
            WHERE id = %s
        """, (name, g.user_id))
        
        conn.commit()
        conn.close()
        
        # Save to memory graph
        try:
            graph = get_memory_graph(g.user_id)
            graph.add_memory(
                content=f"User's name is {name}",
                memory_type="fact",
                confidence=1.0,
                source="onboarding"
            )
        except Exception as e:
            logger.warning(f"Memory save failed for {g.user_id}: {e}")
        
        return jsonify({
            'status': 'complete',
            'display_name': name
        })
        
    except Exception as e:
        logger.error(f"Onboarding complete error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# CONFIG ENDPOINTS
# ============================================================================

@app.route('/api/config', methods=['GET'])
@require_auth
def get_config():
    """Get user's LLM configuration."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT provider, model, quality_preference, auto_route,
                   fallback_provider, fallback_model
            FROM user_llm_config WHERE user_id = %s
        """, (g.user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            config = {
                'provider': row[0],
                'model': row[1],
                'quality_preference': row[2] or 'balanced',
                'auto_route': row[3],
                'fallback_provider': row[4],
                'fallback_model': row[5]
            }
        else:
            config = {
                'provider': 'openai',
                'model': 'gpt-4o-mini',
                'quality_preference': 'balanced',
                'auto_route': True,
                'fallback_provider': None,
                'fallback_model': None
            }
        
        return jsonify(config)
        
    except Exception as e:
        logger.error(f"Get config error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['PUT'])
@require_auth
def update_config():
    """Update user's LLM configuration."""
    data = request.get_json() or {}
    
    provider = data.get('provider', 'openai')
    model = data.get('model', 'gpt-4o-mini')
    quality = data.get('quality_preference', 'balanced')
    auto_route = data.get('auto_route', True)
    fallback_provider = data.get('fallback_provider')
    fallback_model = data.get('fallback_model')
    
    # Validate quality
    if quality not in QUALITY_MODELS:
        quality = 'balanced'
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_llm_config (id, user_id, provider, model, 
                                         quality_preference, auto_route,
                                         fallback_provider, fallback_model)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(user_id) DO UPDATE SET
                provider = excluded.provider,
                model = excluded.model,
                quality_preference = excluded.quality_preference,
                auto_route = excluded.auto_route,
                fallback_provider = excluded.fallback_provider,
                fallback_model = excluded.fallback_model,
                updated_at = CURRENT_TIMESTAMP
        """, (str(uuid.uuid4()), g.user_id, provider, model, quality,
               auto_route, fallback_provider, fallback_model))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Configuration updated', 'quality': quality})
        
    except Exception as e:
        logger.error(f"Update config error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/models', methods=['GET'])
@require_auth
def get_models():
    """Get available models."""
    # Return all available models
    models = {
        QualityLevel.SPEED: {
            'name': 'Speed',
            'models': ['gpt-4o-mini', 'minimax-01', 'llama3', 'phi3'],
            'description': 'Fast, cheap - for simple tasks'
        },
        QualityLevel.BALANCED: {
            'name': 'Balanced', 
            'models': ['minimax-01', 'claude-sonnet-4-20250514', 'gpt-4o-mini'],
            'description': 'Best overall - great reasoning'
        },
        QualityLevel.QUALITY: {
            'name': 'Quality',
            'models': ['gpt-4o', 'claude-sonnet-4-20250514'],
            'description': 'High quality responses'
        },
        QualityLevel.DEEP: {
            'name': 'Deep Thinking',
            'models': ['o1-preview', 'claude-opus-4-20250514'],
            'description': 'Complex reasoning'
        }
    }
    
    return jsonify({
        'tier': g.user_tier,
        'models': models,
        'current_quality': 'balanced',
        'default': 'claude-sonnet-4-20250514'
    })


# ============================================================================
# BILLING ENDPOINTS
# ============================================================================

@app.route('/api/credits', methods=['GET'])
@require_auth
def get_credits():
    """Get credit balance."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT credits FROM users WHERE id = %s", (g.user_id,))
        row = cursor.fetchone()
        conn.close()
        
        credits = float(row[0]) if row else 0
        
        return jsonify({
            'credits': credits,
            'user_id': g.user_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/billing/status', methods=['GET'])
@require_auth
def billing_status():
    """Get billing status - credit balance and plan info."""
    info = get_user_billing_info(g.user_id)
    return jsonify({
        "balance_usd": info["balance_cents"] / 100,
        "balance_display": info["balance_display"],
        "status": info["status"],
        "daily_burn_usd": info["daily_burn_cents"] / 100,
        "runway_days": info["runway_days"],
        "credits": info["balance_cents"] / 100,
        "credits_remaining": info["balance_cents"] / 100,
    })


# ============================================================================
# MEMORY API
# ============================================================================

@app.route('/api/memories', methods=['GET'])
@require_auth
def get_memories():
    """Get user's stored memories."""
    try:
        from memory_graph import get_memory_graph
        graph = get_memory_graph(g.user_id)
        memories = graph.recall_semantic('', limit=50)
        return jsonify([{
            'content': node.content,
            'type': node.node_type,
            'confidence': node.confidence,
            'created_at': str(node.created_at)
        } for node, score in memories])
    except Exception as e:
        return jsonify([])


# ============================================================================
# STRIPE CREDIT PURCHASE
# ============================================================================

@app.route('/api/billing/credits/purchase', methods=['POST'])
@require_auth
def purchase_credits_checkout():
    """Create Stripe checkout for credit purchase."""
    from providers import get_secret
    import stripe
    
    data = request.get_json() or {}
    amount = float(data.get('amount', 25))  # Dollar amount
    
    if amount < 5:
        return jsonify({'error': 'Minimum purchase is $5'}), 400
    
    # Get Stripe key
    stripe_key = get_secret('STRIPE_SECRET_KEY')
    if not stripe_key:
        return jsonify({'error': 'Payment not configured'}), 503
    
    stripe.api_key = stripe_key
    
    # Calculate credits (user gets: amount - 5.5% fee, then $1/credit)
    # Example: $25 → $23.63 after fee → ~23.63 credits
    fee = max(amount * 0.055, 0.80)
    credits_value = amount - fee  # Amount available for credits
    
    try:
        # Create checkout session
        session = CheckoutSession.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Lipaira Credits (${credits_value:.2f} value)',
                        'description': f'{credits_value:.2f} credits for AI agent conversations'
                    },
                    'unit_amount': int(amount * 100),  # Stripe uses cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'https://lipaira.ai/chat?payment=success&session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'https://lipaira.ai/chat?payment=cancelled',
            metadata={
                'user_id': g.user_id,
                'credits_value': str(credits_value),
                'amount_paid': str(amount),
                'fee': str(fee)
            }
        )
        
        return jsonify({
            'checkout_url': session.url
        })
        
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        return jsonify({'error': 'Failed to create checkout'}), 500


@app.route('/api/billing/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks."""
    from providers import get_secret
    import stripe
    import hmac
    import hashlib
    
    stripe_key = get_secret('STRIPE_SECRET_KEY')
    if not stripe_key:
        return jsonify({'error': 'Webhook not configured'}), 503
    
    stripe.api_key = stripe_key
    
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = get_secret('STRIPE_WEBHOOK_SECRET')
    
    try:
        if webhook_secret and sig_header:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # For testing without webhook secret
            event = json.loads(payload)
    except Exception as e:
        logger.error(f"Webhook verify failed: {e}")
        return jsonify({'error': 'Invalid webhook'}), 400
    
    # Handle events
    try:
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            user_id = session.get('metadata', {}).get('user_id')
            credits_value = float(session.get('metadata', {}).get('credits_value', 0))
            amount_paid = float(session.get('metadata', {}).get('amount_paid', 0))
            fee = float(session.get('metadata', {}).get('fee', 0))
            
            if user_id and credits_value > 0:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Add credits
                cursor.execute(
                    "UPDATE users SET credits = credits + %s WHERE id = %s",
                    (credits_value, user_id)
                )
                
                # Record purchase
                cursor.execute("""
                    INSERT INTO credit_purchases (id, user_id, amount_paid, credits_added, our_fee, provider, status)
                    VALUES (%s, %s, %s, %s, %s, 'stripe', 'completed')
                """, (str(uuid.uuid4()), user_id, amount_paid, credits_value, fee))
                
                conn.commit()
                conn.close()
                
                logger.info(f"Credit purchase completed: {user_id} +{credits_value}")
        
        elif event['type'] == 'invoice.payment_failed':
            # Mark subscription as past_due
            logger.warning(f"Payment failed: {event['data']['object']}")
        
        elif event['type'] == 'customer.subscription.deleted':
            # Handle subscription cancellation
            logger.info(f"Subscription cancelled: {event['data']['object']}")
        
    except Exception as e:
        logger.error(f"Webhook handling error: {e}")
    
    return jsonify({'status': 'ok'})


# ============================================================================
# DAILY SWEEP - Charge agent base fees (Phase 4)
# ============================================================================

@app.route('/api/billing/sweep', methods=['POST'])
def daily_sweep():
    """
    Run daily fee sweep - charge base fees for active agents.
    Normally runs via cron at midnight UTC.
    Can be triggered manually for testing.

    Internal calls allowed with X-Internal-Key header.
    """
    # Allow internal calls or admin auth
    internal_key = request.headers.get('X-Internal-Key')
    expected_key = os.environ.get('INTERNAL_KEY')
    if not expected_key:
        raise RuntimeError("INTERNAL_KEY environment variable is required")
    if internal_key != expected_key:
        # Fall back to normal auth for manual calls
        if not hasattr(g, 'user_id') or not g.user_id:
            return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    sweep_date = data.get('date')  # Optional: YYYY-MM-DD

    if sweep_date:
        from datetime import datetime
        try:
            sweep_date = datetime.strptime(sweep_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    try:
        result = billing.run_daily_sweep(sweep_date=sweep_date)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Daily sweep failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/billing/sweep/status', methods=['GET'])
def sweep_status():
    """Get last sweep status."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT COUNT(*) as total, 
               SUM(CASE WHEN transaction_type = 'debit' THEN 1 ELSE 0 END) as debits
        FROM credit_transactions 
        WHERE source LIKE 'agent_base_fee%'
        AND created_at > NOW() - INTERVAL '24 hours'
    """)
    row = cur.fetchone()
    conn.close()
    
    return jsonify({
        'sweeps_24h': row[0] or 0,
        'agent_fees_24h': row[1] or 0
    })


# ============================================================================
# INTEGRATIONS
# ============================================================================

@app.route('/api/integrations/list', methods=['GET'])
@require_auth
def list_integrations():
    """List user's connected integrations. Requires valid API key."""
    user_id = g.user_id
    
    # Get all integrations for this user
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT provider, status, extra, created_at
        FROM user_integrations
        WHERE user_id = %s
    """, (user_id,))
    
    rows = cur.fetchall()
    conn.close()
    
    integrations = []
    provider_details = {
        'google': {'label': 'Google', 'status_key': 'google_access_token'},
        'microsoft': {'label': 'Microsoft', 'status_key': 'microsoft_access_token'},
        'quickbooks': {'label': 'QuickBooks', 'status_key': 'quickbooks_access_token'},
        'notion': {'label': 'Notion', 'status_key': 'notion_access_token'},
        'slack': {'label': 'Slack', 'status_key': 'slack_access_token'},
        'square': {'label': 'Square', 'status_key': 'square_access_token'},
        'hubspot': {'label': 'HubSpot', 'status_key': 'hubspot_access_token'},
        'pipedrive': {'label': 'Pipedrive', 'status_key': 'pipedrive_access_token'},
        'salesforce': {'label': 'Salesforce', 'status_key': 'salesforce_access_token'},
        'zoho': {'label': 'Zoho', 'status_key': 'zoho_access_token'},
    }
    
    for row in rows:
        provider, status, extra, created_at = row
        info = provider_details.get(provider, {'label': provider.title(), 'status_key': f'{provider}_access_token'})
        integrations.append({
            'provider': provider,
            'label': info['label'],
            'status': 'green' if status == 'connected' else 'gray',
            'detail': extra.get('email') if extra else None,
            'connected': status == 'connected'
        })
    
    return jsonify(integrations)


# ============================================================================
# AGENTS - Hire/Fire (Phase 3)
# ============================================================================

@app.route('/api/agents/hire', methods=['POST'])
@require_auth
def hire_agent():
    """Hire an agent."""
    data = request.get_json() or {}
    agent_type = data.get('agent_type', '').lower()
    
    if not agent_type:
        return jsonify({'error': 'agent_type required'}), 400
    
    # Validate agent type
    valid_agents = list(billing.AGENT_PRICING.keys())
    if agent_type not in valid_agents:
        return jsonify({
            'error': f'Invalid agent_type. Valid: {valid_agents}'
        }), 400
    
    user_id = g.user_id
    
    # Check if already hired
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM agent_subscriptions 
        WHERE user_id = %s AND agent_type = %s AND status = 'active'
    """, (user_id, agent_type))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({'error': f'Already have active {agent_type} agent'}), 400
    
    # Check balance (need enough for 1 day + buffer)
    balance_cents = billing.get_user_balance_cents(user_id)
    daily_rate = billing.get_agent_daily_cost(agent_type)
    min_balance = daily_rate + billing.GRACE_BUFFER_CENTS
    
    if balance_cents < min_balance:
        cur.close()
        conn.close()
        return jsonify({
            'error': f'Insufficient balance. Need {cents_to_dollars(min_balance):.2f} for {agent_type} agent',
            'balance': cents_to_dollars(balance_cents),
            'required': cents_to_dollars(min_balance)
        }), 402
    
    # Hire the agent
    import uuid
    agent_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO agent_subscriptions 
        (id, user_id, agent_type, status, daily_rate_cents, hired_at)
        VALUES (%s, %s, %s, 'active', %s, NOW())
    """, (agent_id, user_id, agent_type, daily_rate))
    
    conn.commit()
    cur.close()
    conn.close()
    
    # Calculate bundle discount if any
    active_count = len(get_active_agents(user_id))
    discount = billing.get_agent_count_discount(active_count)
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'agent_type': agent_type,
        'daily_rate_cents': daily_rate,
        'active_agents': active_count,
        'bundle_discount': f'{discount*100:.0f}%',
        'message': f'{agent_type.title()} agent hired successfully'
    })


@app.route('/api/agents/fire', methods=['POST'])
@require_auth
def fire_agent():
    """Fire an agent."""
    data = request.get_json() or {}
    agent_type = data.get('agent_type', '').lower()
    agent_id = data.get('agent_id', '')
    
    user_id = g.user_id
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Find the agent to fire
    if agent_id:
        cur.execute("""
            SELECT id FROM agent_subscriptions 
            WHERE id = %s AND user_id = %s AND status = 'active'
        """, (agent_id, user_id))
    elif agent_type:
        cur.execute("""
            SELECT id FROM agent_subscriptions 
            WHERE user_id = %s AND agent_type = %s AND status = 'active'
            ORDER BY hired_at DESC LIMIT 1
        """, (user_id, agent_type))
    else:
        return jsonify({'error': 'agent_type or agent_id required'}), 400
    
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({'error': 'Agent not found'}), 404
    
    # Fire the agent
    cur.execute("""
        UPDATE agent_subscriptions 
        SET status = 'fired', fired_at = NOW()
        WHERE id = %s
    """, (row[0],))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'{agent_type.title() if agent_type else "Agent"} fired successfully'
    })


@app.route('/api/agents', methods=['GET'])
@require_auth
def list_agents():
    """List user's hired agents."""
    user_id = g.user_id
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT id, agent_type, status, daily_rate_cents, hired_at, fired_at
        FROM agent_subscriptions
        WHERE user_id = %s
        ORDER BY hired_at DESC
    """, (user_id,))
    
    agents = cur.fetchall()
    conn.close()
    
    # Calculate totals
    active = [a for a in agents if a['status'] == 'active']
    total_daily = sum(a['daily_rate_cents'] for a in active)
    
    return jsonify({
        'agents': [
            {
                'id': a['id'],
                'type': a['agent_type'],
                'status': a['status'],
                'daily_rate': cents_to_dollars(a['daily_rate_cents']),
                'hired_at': a['hired_at'].isoformat() if a['hired_at'] else None,
                'fired_at': a['fired_at'].isoformat() if a['fired_at'] else None
            }
            for a in agents
        ],
        'active_count': len(active),
        'total_daily_cents': total_daily,
        'total_daily': cents_to_dollars(total_daily)
    })


# Helper to get active agents
def get_active_agents(user_id: str) -> List[Dict]:
    """Get all active agents for a user."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT agent_type, daily_rate_cents
        FROM agent_subscriptions
        WHERE user_id = %s AND status = 'active'
    """, (user_id,))
    agents = cur.fetchall()
    conn.close()
    return [dict(a) for a in agents]


@app.route('/api/credits/purchase', methods=['POST'])
@require_auth
def purchase_credits():
    """Purchase credits."""
    data = request.get_json() or {}
    amount = data.get('amount', 10.0)
    
    if amount < 5:
        return jsonify({'error': 'Minimum purchase is '}), 400
    
    # Calculate credits (OpenRouter-style: 5.5% fee)
    fee = max(amount * 0.055, 0.80)
    credits = (amount - fee) * 1.058  # Rough conversion
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add credits
        cursor.execute(
            "UPDATE users SET credits = credits + %s WHERE id = %s",
            (credits, g.user_id)
        )
        
        # Record purchase
        cursor.execute("""
            INSERT INTO credit_purchases (id, user_id, amount_paid, credits_added, our_fee, provider, status)
            VALUES (%s, %s, %s, %s, %s, 'stripe', 'completed')
        """, (str(uuid.uuid4()), g.user_id, amount, credits, fee))
        
        conn.commit()
        
        # Get new balance
        cursor.execute("SELECT credits FROM users WHERE id = %s", (g.user_id,))
        new_balance = float(cursor.fetchone()[0])
        
        conn.close()
        
        return jsonify({
            'credits_added': credits,
            'amount_paid': amount,
            'our_fee': fee,
            'new_balance': new_balance
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# AUTO-REFILL SETTINGS
# ============================================================================

@app.route('/api/billing/auto-refill', methods=['GET'])
@require_auth
def get_auto_refill():
    """Get auto-refill settings."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT enabled, threshold_cents, package_cents, created_at, updated_at
        FROM auto_refill_settings
        WHERE user_id = %s
    """, (g.user_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return jsonify({
            'enabled': False,
            'threshold_cents': 1000,
            'package_cents': 5000
        })
    
    return jsonify({
        'enabled': row['enabled'],
        'threshold_cents': row['threshold_cents'],
        'threshold_display': f"${row['threshold_cents'] / 100:.2f}",
        'package_cents': row['package_cents'],
        'package_display': f"${row['package_cents'] / 100:.2f}",
        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
    })


@app.route('/api/billing/auto-refill', methods=['POST'])
@require_auth
def set_auto_refill():
    """Update auto-refill settings."""
    data = request.get_json() or {}
    
    enabled = data.get('enabled', False)
    threshold_cents = int(data.get('threshold', 10) * 100)  # Convert USD to cents
    package_cents = int(data.get('package', 50) * 100)  # Convert USD to cents
    
    # Validate
    if threshold_cents < 100:
        return jsonify({'error': 'Threshold must be at least $1.00'}), 400
    if package_cents < 500:
        return jsonify({'error': 'Package must be at least $5.00'}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Upsert settings
    cur.execute("""
        INSERT INTO auto_refill_settings (user_id, enabled, threshold_cents, package_cents, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            enabled = EXCLUDED.enabled,
            threshold_cents = EXCLUDED.threshold_cents,
            package_cents = EXCLUDED.package_cents,
            updated_at = NOW()
    """, (g.user_id, enabled, threshold_cents, package_cents))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'enabled': enabled,
        'threshold_cents': threshold_cents,
        'package_cents': package_cents,
        'message': f"Auto-refill {'enabled' if enabled else 'disabled'}"
    })


@app.route('/api/billing/auto-refill', methods=['DELETE'])
@require_auth
def disable_auto_refill():
    """Disable auto-refill."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE auto_refill_settings 
        SET enabled = FALSE, updated_at = NOW()
        WHERE user_id = %s
    """, (g.user_id,))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Auto-refill disabled'})


# ============================================================================
# MEMORY SWEEPS - Extract context from integrations (Phase 2)
# ============================================================================

@app.route('/api/memory/sweep', methods=['POST'])
@require_auth
def run_memory_sweep_endpoint():
    """Run memory sweep to extract context from integrations."""
    try:
        result = billing.run_memory_sweep(g.user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Memory sweep failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/memory/sweep/status', methods=['GET'])
@require_auth
def memory_sweep_status():
    """Get integration status for memory."""
    try:
        integrations = billing.get_user_integrations(g.user_id)
        return jsonify({
            'integrations': [
                {
                    'provider': i['provider'],
                    'connected': True,
                    'last_sync': i.get('last_sync')
                }
                for i in integrations
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/usage', methods=['GET'])
@require_auth
def get_usage():
    """Get usage history."""
    days = request.args.get('days', 30, type=int)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT provider, model, input_tokens, output_tokens, 
                   provider_cost, our_fee, credits_deducted, created_at
            FROM llm_usage 
            WHERE user_id = %s AND created_at > NOW() - INTERVAL '1 day' * %s
            ORDER BY created_at DESC
            LIMIT 100
        """, (g.user_id, days))
        
        rows = cursor.fetchall()
        conn.close()
        
        usage = []
        for row in rows:
            usage.append({
                'provider': row[0],
                'model': row[1],
                'input_tokens': row[2],
                'output_tokens': row[3],
                'cost': float(row[4]) if row[4] else 0,
                'fee': float(row[5]) if row[5] else 0,
                'deducted': float(row[6]) if row[6] else 0,
                'created_at': row[7].isoformat() if row[7] else None
            })
        
        return jsonify({'usage': usage})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/usage/summary', methods=['GET'])
@require_auth
def get_usage_summary():
    """Get usage summary."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_requests,
                COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                COALESCE(SUM(cost), 0) as total_cost
            FROM llm_usage 
            WHERE user_id = %s AND created_at > NOW() - INTERVAL '30 days'
        """, (g.user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'period_days': 30,
            'total_requests': row[0],
            'total_tokens': int(row[1]) if row[1] else 0,
            'total_cost': float(row[2]) if row[2] else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# HEALTH
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'lipaira'})


@app.route('/version', methods=['GET'])
def version():
    """Test endpoint for CI/CD verification."""
    return jsonify({'version': '2026.04.07-test', 'deployed': 'success'})


# ============================================================================
# DASHBOARD (Static HTML)
# ============================================================================

@app.route('/dashboard', methods=['GET'])
@app.route('/ui', methods=['GET'])
@app.route('/app', methods=['GET'])
def serve_dashboard():
    """Serve the dashboard."""
    try:
        with open('dashboard.html', 'r') as f:
            from flask import make_response
            response = make_response(f.read())
            response.headers['Content-Type'] = 'text/html'
            return response
    except FileNotFoundError:
        return jsonify({'error': 'Dashboard not found'}), 404


# ============================================================================
# LANDING PAGE (Static HTML)
# ============================================================================

@app.route('/', methods=['GET'])
def serve_landing_page():
    """Serve the landing page at root."""
    try:
        with open('index.html', 'r') as f:
            from flask import make_response
            response = make_response(f.read())
            response.headers['Content-Type'] = 'text/html'
            return response
    except FileNotFoundError:
        return jsonify({'error': 'Landing page not found'}), 404
    return jsonify({'status': 'ok', 'service': 'lipaira'})


# ============================================================================
# MODEL REGISTRY - OpenRouter Integration
# ============================================================================

@app.route('/api/models', methods=['GET'])
@require_auth
def list_models():
    """List all available models with pricing."""
    try:
        models = get_models()
        free_only = request.args.get('free', 'false').lower() == 'true'
        provider = request.args.get('provider')
        
        result = models
        if free_only:
            result = [m for m in result if m.get('free')]
        if provider:
            result = [m for m in result if m.get('provider', '').lower() == provider.lower()]
        
        return jsonify({
            'models': result[:100],  # Limit for response size
            'total': len(result),
            'free_count': len([m for m in models if m.get('free')]),
            'categories': list(MODEL_CATEGORIES.keys())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/models/free', methods=['GET'])
@require_auth
def list_free_models():
    """List only free models."""
    try:
        models = get_free_models()
        return jsonify({
            'models': models,
            'count': len(models)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/models/<path:model_id>', methods=['GET'])
@require_auth
def get_model(model_id):
    """Get details for a specific model."""
    model = get_model_by_id(model_id)
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    # Add pricing estimate examples
    model['pricing_examples'] = {
        '1k_input_1k_output': get_model_pricing_estimate(model_id, 1000, 1000),
        '10k_input_5k_output': get_model_pricing_estimate(model_id, 10000, 5000),
    }
    
    return jsonify(model)


@app.route('/api/models/estimate', methods=['POST'])
@require_auth
def estimate_cost():
    """Estimate cost for a request before making it."""
    data = request.get_json()
    model_id = data.get('model')
    input_tokens = data.get('input_tokens', 0)
    output_tokens = data.get('output_tokens', 0)
    
    if not model_id:
        return jsonify({'error': 'model required'}), 400
    
    estimate = get_model_pricing_estimate(model_id, input_tokens, output_tokens)
    return jsonify(estimate)


@app.route('/api/models/by-quality/<quality>', methods=['GET'])
@require_auth
def get_model_by_quality(quality):
    """Get recommended model for a quality setting."""
    if quality not in MODEL_CATEGORIES:
        return jsonify({
            'error': 'Invalid quality',
            'valid': list(MODEL_CATEGORIES.keys())
        }), 400
    
    model_id = get_model_for_quality(quality)
    model = get_model_by_id(model_id)
    
    return jsonify({
        'quality': quality,
        'model': model_id,
        'model_info': model,
        'alternatives': MODEL_CATEGORIES[quality]
    })


# ============================================================================
# CONVERSATION HISTORY
# ============================================================================

@app.route('/api/conversation/history', methods=['GET'])
@require_auth
def conversation_history():
    """Get last 50 messages for the user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT role, content, created_at 
            FROM conversation_messages 
            WHERE user_id = %s 
            ORDER BY created_at ASC 
            LIMIT 50
        """, (g.user_id,))
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                'role': row[0],
                'content': row[1],
                'created_at': row[2].isoformat() if row[2] else None
            })
        
        conn.close()
        return jsonify(messages)
        
    except Exception as e:
        logger.error(f"History error: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# LIPAIRA UNIFIED CHAT API - Multi-provider LLM endpoint with memory
# =============================================================================
def run_agentic_loop(user_id, messages, system_prompt, model, provider, max_rounds=5, business_id=None, user_credits=0):
    """Agentic loop with tool use."""
    import sys
    import os
    import json
    
    os.environ['USER_ID'] = user_id
    os.environ['GATEWAY_URL'] = 'http://localhost:8080'
    
    # Use the provider passed from the chat endpoint, or default to openrouter
    if not provider:
        provider = 'openrouter'
    
    # Get tools from skill registry
    tools = []
    SKILLS = {}
    try:
        from skills.registry import skill_registry
        all_skills = skill_registry.get_available_tools(user_id, business_id)
        logger.warning(f"SKILL_REGISTRY_COUNT: {len(all_skills)}")
        
        # Build SKILLS dict and tools list — must be in the try block, not except
        for skill_info in all_skills:
            skill_obj = skill_registry.get(skill_info['name'])
            if skill_obj:
                SKILLS[skill_info['name']] = skill_obj
        
        for skill in all_skills:
            input_schema = {}
            skill_obj = skill_registry.get(skill['name'])
            if skill_obj and hasattr(skill_obj, 'get_input_schema'):
                try:
                    input_schema = skill_obj.get_input_schema()
                except:
                    pass
            tools.append({
                "type": "function",
                "function": {
                    "name": skill["name"],
                    "description": skill["description"],
                    "parameters": input_schema if input_schema else {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            })
    except Exception as e:
        logger.warning(f"Skill filter failed, showing all skills: {e}")
        try:
            all_skills = skill_registry.list()
            logger.warning(f"SKILL_REGISTRY_COUNT: {len(all_skills)} (fallback)")
            for skill_info in all_skills:
                skill_obj = skill_registry.get(skill_info['name'])
                if skill_obj:
                    SKILLS[skill_info['name']] = skill_obj
            for skill in all_skills:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": skill["name"],
                        "description": skill["description"],
                        "parameters": {"type": "object", "properties": {}, "required": []}
                    }
                })
        except Exception as e2:
            logger.error(f"Complete skill loading failure: {e2}")
    
    for round_num in range(1, max_rounds + 1):
        logger.warning(f"TOOLS_BEING_SENT: {len(tools)} tools - {[t.get('function', {}).get('name') for t in tools]}")
        
        result = llm_router.call_provider(provider=provider, model=model, messages=messages, system=system_prompt, tools=tools, max_tokens=4096)
        if not result.get('success'):
            return result
        
        # Deduct credits for this LLM call (skip for free tier)
        try:
            input_tokens = result.get('input_tokens', 0)
            output_tokens = result.get('output_tokens', 0)
            if input_tokens > 0 or output_tokens > 0:
                # Only deduct if user has credits (paid tier)
                if user_credits > 0:
                    deduction = UsageTracker.record_usage(
                        user_id=user_id,
                        provider=provider,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens
                    )
                    if not deduction.get('success'):
                        return {'success': False, 'error': f'Insufficient credits. Need {deduction.get("cost", 0):.4f}'}
                else:
                    # Free tier - no credit deduction
                    logger.warning(f"Free tier call: {input_tokens} input, {output_tokens} output tokens (no charge)")
        except Exception as e:
            logger.warning(f"Credit deduction failed: {e}")
        
        stop_reason = result.get('stop_reason', 'end_turn')
        content, raw_content = result.get('content', ''), result.get('raw_content', [])
        
        logger.warning(f"LOOP_DEBUG: round={round_num}, stop_reason={stop_reason}, has_raw_content={bool(raw_content)}, content_preview={content[:100] if content else 'empty'}")
        
        # Check if there's tool_use content regardless of stop_reason
        tool_use_blocks = [b for b in raw_content if b.get('type') == 'tool_use'] if raw_content else []
        has_tool_use = len(tool_use_blocks) > 0
        
        logger.warning(f"RAW_CONTENT: {raw_content}")
        
        if tool_use_blocks:
            logger.warning(f"TOOL_USE_BLOCKS found: {tool_use_blocks}")
        
        if stop_reason == 'end_turn' and not has_tool_use:
            return {'success': True, 'content': content, 'rounds': round_num}
        
        if stop_reason == 'tool_use' or has_tool_use:
            logger.warning(f"TOOL_USE_BLOCK: stop_reason={stop_reason}, raw_content={raw_content[:1] if raw_content else 'empty'}")
            messages.append({'role': 'assistant', 'content': raw_content})
            tool_results = []
            for block in raw_content:
                if block.get('type') != 'tool_use':
                    continue
                skill_name = block.get('name')
                skill = SKILLS.get(skill_name)
                logger.warning(f"TOOL_CALL: skill={skill_name}, input={block.get('input', {})}")
                
                # Check credits for tool execution (free tier = no paid-tier tools)
                if user_credits <= 0:
                    # Get execution_tier from skill, default to "paid" (safe)
                    skill_tier = getattr(skill, 'execution_tier', 'paid') if skill else 'paid'
                    if skill_tier == 'paid':
                        output = json.dumps({
                            "error": "credits_required",
                            "message": f"Connect credits to take this action. Free tier can read but not act."
                        })
                        logger.warning(f"TOOL_BLOCKED: free tier user {user_id} tried to use paid skill {skill_name}")
                    else:
                        # Free tier skill - allow execution
                        logger.warning(f"TOOL_ALLOWED: free tier using free skill {skill_name}")
                        try:
                            result = skill.execute(block.get('input', {}), user_id)
                            output = json.dumps(result)
                            logger.warning(f"TOOL_RESULT: {output[:200]}")
                        except Exception as e:
                            output = f"Error: {str(e)}"
                            logger.warning(f"TOOL_ERROR: {e}")
                elif skill:
                    try:
                        result = skill.execute(block.get('input', {}), user_id)
                        output = json.dumps(result)
                        logger.warning(f"TOOL_RESULT: {output[:200]}")
                    except Exception as e:
                        output = f"Error: {str(e)}"
                        logger.warning(f"TOOL_ERROR: {e}")
                else:
                    output = f"Unknown skill: {skill_name}"
                tool_results.append({'type': 'tool_result', 'tool_use_id': block.get('id'), 'content': output})
            
            logger.warning(f"TOOL_RESULTS_COUNT: {len(tool_results)}")
            if tool_results:
                logger.warning(f"FIRST_TOOL_RESULT: {tool_results[0]}")
            
            # Format tool results in OpenRouter's proper format
            # Step 1: Echo back assistant's tool_calls (content: null)
            tc_list = []
            for block in raw_content:
                if block.get('type') == 'tool_use':
                    args = block.get('input', {})
                    if isinstance(args, str):
                        args_json = args
                    else:
                        args_json = json.dumps(args)
                    tc_list.append({
                        "id": block.get('id'),
                        "type": "function",
                        "function": {
                            "name": block.get('name'),
                            "arguments": args_json
                        }
                    })
            
            if tc_list:
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tc_list
                })
            
            # Step 2: Send tool results as "tool" role (no name field!)
            for tr in tool_results:
                content = tr.get('content', '')
                if not isinstance(content, str):
                    content = json.dumps(content)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr.get('tool_use_id'),
                    "content": content
                })
            
            continue
        
        return {'success': True, 'content': content, 'rounds': round_num}
    
    return {'success': True, 'content': 'Max rounds reached.', 'rounds': max_rounds}

@app.route("/api/chat", methods=["POST"])
@require_auth
def chat():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    message = sanitize_prompt_input(message)  # C8: prompt injection sanitize
    user_id = g.user_id
    
    # ── TIER ROUTING: Select model based on credits ────────────
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    user_credits = row[0] if row else 0
    conn.close()
    
    # TIER ROUTING: Select model based on credits (Contract V1d)
    # Free tier (credits = 0): use free Google model
    # Locked decision: Gemini Flash-Lite via Google AI directly
    if user_credits <= 0:
        provider = "openrouter"
        model = "google/gemini-2.5-flash-lite"
    else:
        # Paid tier — read from user_llm_config
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT provider, model FROM user_llm_config 
                WHERE user_id = %s LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            if row and row[0] and row[1]:
                provider = row[0]
                model = row[1]
                # Handle provider prefixes
                if provider == 'openrouter':
                    model = model  # Already in "minimax/..." format
                else:
                    model = f"{provider}/{model}"
            else:
                # No config — fallback to openrouter/minimax
                provider = "openrouter"
                model = "minimax/minimax-m2.7"
            conn.close()
        except Exception as e:
            logger.warning(f"Model config lookup failed: {e}")
            # Fallback on error
            provider = "openrouter"
            model = "minimax/minimax-m2.7"

    if not message:
        return jsonify({"error": "message required"}), 400

    # ── 1. RECALL: Get relevant memories ─────────────────────────
    memory_context = ""
    
    # Also check user profile for name
    user_name = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT display_name FROM user_profiles 
            WHERE user_id = %s AND display_name IS NOT NULL
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            user_name = row[0]
        conn.close()
    except Exception as e:
        logger.warning(f"Profile lookup failed: {e}")
    
    try:
        graph = get_memory_graph(user_id)
        
        # Check for name-related queries
        name_query = message.lower().replace('?', '').strip()
        if user_name:
            memory_context = f"WHAT YOU KNOW ABOUT THIS USER:\n- The user's name is {user_name}"
        else:
            # Regular memory recall
            memories = graph.recall_semantic(message, limit=10)
            if memories:
                lines = [
                    f"- {node.content}"
                    for node, score in memories
                    if score > 0.3
                ]
                if lines:
                    memory_context = (
                        "WHAT YOU KNOW ABOUT THIS USER:\n" +
                        '\n'.join(lines)
                    )
    except Exception as e:
        logger.warning(f"Memory recall failed for {user_id}: {e}")

    # ── 2. GET CONVERSATION HISTORY ─────────────────────────────
    # Get recent conversation history for context
    recent_history = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content 
            FROM conversation_messages
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        # Reverse so oldest is first (correct order for LLM)
        recent_history = [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except Exception as e:
        logger.warning(f"History fetch failed for {user_id}: {e}")

    # ── 3. BUILD: Inject memory + history into messages ──────────
    # Use layered system prompt (Soul + Context)
    try:
        from operator_context import build_system_prompt
        system_prompt = build_system_prompt(
            user_id=user_id,
            business_id=data.get('business_id'),
            first_message=message
        )
    except Exception as e:
        logger.warning(f"build_system_prompt failed: {e}, using fallback")
        # Fallback to simple memory injection
        system_prompt = (
            "IMPORTANT: You have PERSISTENT MEMORY. Everything the user tells you "
            "is saved to a memory database and WILL be remembered in future conversations. "
            "When they ask about their name, location, business, or preferences — "
            "you KNOW the answer from your memory.\n\n"
            "You are connected to the user's external accounts through integrations "
            "they have set up. You can read emails, calendar events, create invoices, "
            "and more depending on which integrations are connected.\n\n"
        )
        if memory_context:
            system_prompt += memory_context
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history (if any)
    for msg in recent_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current message
    messages.append({"role": "user", "content": message})

    # ── 3. CALL: LLM via router ──────────────────────────────────
    # Route model to provider
    # All models go through openrouter for consistency (except direct API calls)
    if model.startswith('minimax') or 'minimax' in model:
        provider = 'openrouter'
    elif model.startswith('qwen') or 'qwen' in model:
        provider = 'openrouter'
    elif model.startswith('gpt') or model.startswith('o1'):
        provider = 'openai'
    elif model.startswith('claude') or model.startswith('anthropic'):
        provider = 'anthropic'
    elif (model.startswith('gemini') or model.startswith('google')) and not model.startswith('google/'):
        provider = 'google'
    else:
        provider = 'openrouter'  # default to openrouter
    
    import time
    start_time = time.time()

    # Check balance BEFORE LLM call (synchronous)
    balance_cents = get_user_balance_cents(user_id)
    can_use = can_use_service(balance_cents)
    if not can_use["allowed"]:
        return jsonify({
            "error": can_use["message"],
            "status": "insufficient_credits",
            "action": "add_credits",
            "balance": balance_cents / 100
        }), 402

    # Run agentic loop with tools
    loop_result = run_agentic_loop(user_id=user_id, messages=messages, system_prompt=system_prompt, model=model, provider=provider, max_rounds=5, business_id=data.get("business_id"), user_credits=user_credits)
    if not loop_result.get('success'):
        return jsonify({'error': loop_result.get('error', 'Agent error')}), 500
    content = loop_result.get('content', '')
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Deduct AFTER LLM call (asynchronous, non-blocking)
    input_tokens = loop_result.get('input_tokens', 0)
    output_tokens = loop_result.get('output_tokens', 0)
    
    def _deduct_billing():
        try:
            deduct_usage(
                user_id=user_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
        except Exception as e:
            logger.warning(f"Billing error for {user_id}: {e}")
    
    threading.Thread(target=_deduct_billing, daemon=True).start()
    
    # ── 4. SAVE: Persist conversation to database ─────────────────
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Save user message
        cur.execute("""
            INSERT INTO conversation_messages (user_id, role, content, model, created_at)
            VALUES (%s, 'user', %s, %s, NOW())
        """, (user_id, message, model))
        # Save assistant response
        cur.execute("""
            INSERT INTO conversation_messages (user_id, role, content, model, created_at)
            VALUES (%s, 'assistant', %s, %s, NOW())
        """, (user_id, content, model))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to save conversation history: {e}")
    
    # ── 5. EXTRACT: Save semantic memories ───────────────────────
    try:
        threading.Thread(target=extract_memory_nodes, args=(user_id, message, content, model), daemon=True).start()
    except Exception as e:
        logger.warning(f"Memory extraction failed: {e}")
    
    # Return the response
    return jsonify({
        'success': True,
        'content': content,
        'latency_ms': latency_ms,
        'model': model
    })
def public_email_send():
    """Send email via Resend API."""
    from providers import get_secret
    import requests
    
    data = request.get_json()
    to_email = data.get('to')
    subject = data.get('subject', 'Email from Lipaira')
    body = data.get('body', '')
    
    if not to_email:
        return jsonify({'error': 'Missing "to" email address'}), 400
    
    api_key = get_secret('RESEND_API_KEY')
    if not api_key:
        return jsonify({'error': 'Resend not configured'}), 500
    
    # Send via Resend
    resp = requests.post(
        'https://api.resend.com/emails',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'from': 'Lipaira AI <onboarding@resend.dev>',  # Use verified domain in prod
            'to': [to_email],
            'subject': subject,
            'html': body.replace('\n', '<br>')
        }
    )
    
    if resp.ok:
        return jsonify({'success': True, 'id': resp.json().get('id')})
    else:
        return jsonify({'error': resp.text}), resp.status_code

# ============================================================================
# SLACK OAuth
# ============================================================================

@app.route('/api/auth/slack/connect')
def slack_connect():
    from urllib.parse import urlencode
    import secrets
    
    from providers import get_secret
    client_id = get_secret('SLACK_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Slack OAuth not configured'}), 503
    
    import base64
    state = base64.b64encode(f"{request.args.get('user_id', '')}:{secrets.token_urlsafe(16)}".encode()).decode()
    
    scopes = 'chat:write,channels:read,channels:history,users:read,im:read,im:history'
    
    params = urlencode({
        'client_id': client_id,
        'redirect_uri': 'https://lipaira.ai/api/auth/slack/callback',
        'scope': scopes,
        'state': state,
    })
    
    return redirect(f'https://slack.com/oauth/v2/authorize?{params}')


@app.route('/api/auth/slack/callback')
def slack_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        import base64
        user_id = base64.b64decode(state).decode().split(':')[0]
    except:
        return redirect('/chat?error=oauth_invalid_state')
    
    from providers import get_secret
    client_id = get_secret('SLACK_CLIENT_ID')
    client_secret = get_secret('SLACK_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return jsonify({'error': 'Slack OAuth not configured'}), 503
    
    import requests
    resp = requests.post('https://slack.com/api/oauth.v2.access', data={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': 'https://lipaira.ai/api/auth/slack/callback',
    })
    
    tokens = resp.json()
    if not tokens.get('ok'):
        return redirect('/chat?error=slack_denied')
    
    access_token = tokens.get('access_token')
    team_id = tokens.get('team', {}).get('id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS slack_access_token TEXT,
            ADD COLUMN IF NOT EXISTS slack_team_id TEXT
        """)
    except:
        pass
    
    cursor.execute("""
        UPDATE users SET slack_access_token = %s, slack_team_id = %s WHERE id = %s
    """, (access_token, team_id, user_id))
    conn.commit()
    conn.close()
    
    return redirect('/chat?connected=slack')


@app.route('/api/auth/slack/status')
@require_auth
def slack_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT slack_access_token IS NOT NULL FROM users WHERE id = %s", (g.user_id,))
    connected = cursor.fetchone()[0]
    conn.close()
    return jsonify({'connected': connected})


@app.route('/api/auth/slack/disconnect', methods=['POST'])
@require_auth
def slack_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET slack_access_token = NULL, slack_team_id = NULL WHERE id = %s", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============================================================================
# NOTION OAuth
# ============================================================================

@app.route('/api/auth/notion/connect')
def notion_connect():
    from urllib.parse import urlencode
    import secrets
    
    from providers import get_secret
    client_id = get_secret('NOTION_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Notion OAuth not configured'}), 503
    
    # Get user_id from query param (not from g.user_id since no @require_auth)
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id parameter required'}), 400
    
    import base64
    state = base64.b64encode(f"{user_id}:{secrets.token_urlsafe(16)}".encode()).decode()
    
    params = urlencode({
        'client_id': client_id,
        'redirect_uri': 'https://lipaira.ai/api/auth/notion/callback',
        'response_type': 'code',
        'owner': 'user',
        'state': state,
    })
    
    return redirect(f'https://api.notion.com/v1/oauth/authorize?{params}')


@app.route('/api/auth/notion/callback')
def notion_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        import base64
        user_id = base64.b64decode(state).decode().split(':')[0]
    except:
        return redirect('/chat?error=oauth_invalid_state')
    
    from providers import get_secret
    client_id = get_secret('NOTION_CLIENT_ID')
    client_secret = get_secret('NOTION_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return jsonify({'error': 'Notion OAuth not configured'}), 503
    
    import requests
    import base64
    
    # Notion requires HTTP Basic Auth with credentials
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    resp = requests.post('https://api.notion.com/v1/oauth/token', 
        json={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': 'https://lipaira.ai/api/auth/notion/callback',
        },
        headers={
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    )
    
    tokens = resp.json()
    
    access_token = tokens.get('access_token')
    workspace_id = tokens.get('workspace_id')
    workspace_name = tokens.get('workspace_name')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS notion_access_token TEXT,
            ADD COLUMN IF NOT EXISTS notion_workspace_id TEXT,
            ADD COLUMN IF NOT EXISTS notion_workspace_name TEXT
        """)
    except:
        pass
    
    cursor.execute("""
        UPDATE users SET notion_access_token = %s, notion_workspace_id = %s, notion_workspace_name = %s WHERE id = %s
    """, (access_token, workspace_id, workspace_name, user_id))
    
    import json
    
    # Also save to user_integrations for consistency
    extra_data = json.dumps({"workspace_id": workspace_id, "workspace_name": workspace_name})
    cursor.execute("""
        INSERT INTO user_integrations (user_id, provider, access_token, status, extra, created_at)
        VALUES (%s, 'notion', %s, 'connected', %s::jsonb, NOW())
        ON CONFLICT (user_id, provider) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            status = 'connected',
            extra = EXCLUDED.extra,
            updated_at = NOW()
    """, (user_id, access_token, extra_data))
    
    conn.commit()
    conn.close()
    
    return redirect('/dashboard?connected=notion')


@app.route('/api/auth/notion/status')
@require_auth
def notion_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT notion_access_token IS NOT NULL FROM users WHERE id = %s", (g.user_id,))
    connected = cursor.fetchone()[0]
    conn.close()
    return jsonify({'connected': connected})


@app.route('/api/auth/notion/disconnect', methods=['POST'])
@require_auth
def notion_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET notion_access_token = NULL, notion_workspace_id = NULL WHERE id = %s", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============================================================================
# SQUARE OAuth
# ============================================================================

@app.route('/api/auth/square/connect')
def square_connect():
    from urllib.parse import urlencode
    import secrets
    
    from providers import get_secret
    client_id = get_secret('SQUARE_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Square OAuth not configured'}), 503
    
    import base64
    state = base64.b64encode(f"{request.args.get('user_id', '')}:{secrets.token_urlsafe(16)}".encode()).decode()
    
    params = urlencode({
        'client_id': client_id,
        'redirect_uri': 'https://lipaira.ai/api/auth/square/callback',
        'scope': 'ITEMS_READ ITEMS_WRITE ORDERS_READ ORDERS_WRITE CUSTOMERS_READ CUSTOMERS_WRITE',
        'state': state,
        'session': 'false',
    })
    
    return redirect(f'https://connect.squareup.com/oauth2/authorize?{params}')


@app.route('/api/auth/square/callback')
def square_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        import base64
        user_id = base64.b64decode(state).decode().split(':')[0]
    except:
        return redirect('/chat?error=oauth_invalid_state')
    
    from providers import get_secret
    client_id = get_secret('SQUARE_CLIENT_ID')
    client_secret = get_secret('SQUARE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return jsonify({'error': 'Square OAuth not configured'}), 503
    
    import requests
    resp = requests.post('https://connect.squareup.com/oauth2/token', data={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': 'https://lipaira.ai/api/auth/square/callback',
        'grant_type': 'authorization_code',
    })
    
    tokens = resp.json()
    if 'access_token' not in tokens:
        return redirect('/chat?error=square_denied')
    
    access_token = tokens.get('access_token')
    merchant_id = tokens.get('merchant_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS square_access_token TEXT,
            ADD COLUMN IF NOT EXISTS square_merchant_id TEXT
        """)
    except:
        pass
    
    cursor.execute("""
        UPDATE users SET square_access_token = %s, square_merchant_id = %s WHERE id = %s
    """, (access_token, merchant_id, user_id))
    conn.commit()
    conn.close()
    
    return redirect('/chat?connected=square')


@app.route('/api/auth/square/status')
@require_auth
def square_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT square_access_token IS NOT NULL FROM users WHERE id = %s", (g.user_id,))
    connected = cursor.fetchone()[0]
    conn.close()
    return jsonify({'connected': connected})


@app.route('/api/auth/square/disconnect', methods=['POST'])
@require_auth
def square_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET square_access_token = NULL, square_merchant_id = NULL WHERE id = %s", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============================================================================
# HUBSPOT OAuth
# ============================================================================

@app.route('/api/auth/hubspot/connect')
def hubspot_connect():
    from urllib.parse import urlencode
    import secrets
    
    from providers import get_secret
    client_id = get_secret('HUBSPOT_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'HubSpot OAuth not configured'}), 503
    
    import base64
    state = base64.b64encode(f"{request.args.get('user_id', '')}:{secrets.token_urlsafe(16)}".encode()).decode()
    
    scopes = 'crm.objects.contacts.read crm.objects.contacts.write crm.objects.deals.read crm.objects.deals.write'
    
    params = urlencode({
        'client_id': client_id,
        'redirect_uri': 'https://lipaira.ai/api/auth/hubspot/callback',
        'scope': scopes,
        'state': state,
    })
    
    return redirect(f'https://app.hubspot.com/oauth/authorize?{params}')


@app.route('/api/auth/hubspot/callback')
def hubspot_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        import base64
        user_id = base64.b64decode(state).decode().split(':')[0]
    except:
        return redirect('/chat?error=oauth_invalid_state')
    
    from providers import get_secret
    client_id = get_secret('HUBSPOT_CLIENT_ID')
    client_secret = get_secret('HUBSPOT_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return jsonify({'error': 'HubSpot OAuth not configured'}), 503
    
    import requests
    resp = requests.post('https://api.hubapi.com/oauth/v1/token', data={
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': 'https://lipaira.ai/api/auth/hubspot/callback',
        'code': code,
    })
    
    tokens = resp.json()
    if 'access_token' not in tokens:
        return redirect('/chat?error=hubspot_denied')
    
    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS hubspot_access_token TEXT,
            ADD COLUMN IF NOT EXISTS hubspot_refresh_token TEXT
        """)
    except:
        pass
    
    cursor.execute("""
        UPDATE users SET hubspot_access_token = %s, hubspot_refresh_token = %s WHERE id = %s
    """, (access_token, refresh_token, user_id))
    conn.commit()
    conn.close()
    
    return redirect('/chat?connected=hubspot')


@app.route('/api/auth/hubspot/status')
@require_auth
def hubspot_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hubspot_access_token IS NOT NULL FROM users WHERE id = %s", (g.user_id,))
    connected = cursor.fetchone()[0]
    conn.close()
    return jsonify({'connected': connected})


@app.route('/api/auth/hubspot/disconnect', methods=['POST'])
@require_auth
def hubspot_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET hubspot_access_token = NULL, hubspot_refresh_token = NULL WHERE id = %s", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============================================================================
# PIPEDRIVE OAuth
# ============================================================================

@app.route('/api/auth/pipedrive/connect')
def pipedrive_connect():
    from urllib.parse import urlencode
    import secrets
    
    from providers import get_secret
    client_id = get_secret('PIPEDRIVE_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Pipedrive OAuth not configured'}), 503
    
    import base64
    state = base64.b64encode(f"{request.args.get('user_id', '')}:{secrets.token_urlsafe(16)}".encode()).decode()
    
    params = urlencode({
        'client_id': client_id,
        'redirect_uri': 'https://lipaira.ai/api/auth/pipedrive/callback',
        'scope': 'contacts:full deals:full users:read',
        'state': state,
    })
    
    return redirect(f'https://oauth.pipedrive.com/oauth/authorize?{params}')


@app.route('/api/auth/pipedrive/callback')
def pipedrive_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        import base64
        user_id = base64.b64decode(state).decode().split(':')[0]
    except:
        return redirect('/chat?error=oauth_invalid_state')
    
    from providers import get_secret
    client_id = get_secret('PIPEDRIVE_CLIENT_ID')
    client_secret = get_secret('PIPEDRIVE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return jsonify({'error': 'Pipedrive OAuth not configured'}), 503
    
    import requests
    resp = requests.post('https://oauth.pipedrive.com/oauth/token', data={
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': 'https://lipaira.ai/api/auth/pipedrive/callback',
        'code': code,
    })
    
    tokens = resp.json()
    if 'access_token' not in tokens:
        return redirect('/chat?error=pipedrive_denied')
    
    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS pipedrive_access_token TEXT,
            ADD COLUMN IF NOT EXISTS pipedrive_refresh_token TEXT
        """)
    except:
        pass
    
    cursor.execute("""
        UPDATE users SET pipedrive_access_token = %s, pipedrive_refresh_token = %s WHERE id = %s
    """, (access_token, refresh_token, user_id))
    conn.commit()
    conn.close()
    
    return redirect('/chat?connected=pipedrive')


@app.route('/api/auth/pipedrive/status')
@require_auth
def pipedrive_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pipedrive_access_token IS NOT NULL FROM users WHERE id = %s", (g.user_id,))
    connected = cursor.fetchone()[0]
    conn.close()
    return jsonify({'connected': connected})


@app.route('/api/auth/pipedrive/disconnect', methods=['POST'])
@require_auth
def pipedrive_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET pipedrive_access_token = NULL, pipedrive_refresh_token = NULL WHERE id = %s", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============================================================================
# SALESFORCE OAuth
# ============================================================================

@app.route('/api/auth/salesforce/connect')
def salesforce_connect():
    from urllib.parse import urlencode
    import secrets
    
    from providers import get_secret
    client_id = get_secret('SALESFORCE_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Salesforce OAuth not configured'}), 503
    
    import base64
    state = base64.b64encode(f"{request.args.get('user_id', '')}:{secrets.token_urlsafe(16)}".encode()).decode()
    
    scopes = 'api refresh_token'
    
    params = urlencode({
        'client_id': client_id,
        'redirect_uri': 'https://lipaira.ai/api/auth/salesforce/callback',
        'response_type': 'code',
        'scope': scopes,
        'state': state,
    })
    
    return redirect(f'https://login.salesforce.com/services/oauth2/authorize?{params}')


@app.route('/api/auth/salesforce/callback')
def salesforce_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        import base64
        user_id = base64.b64decode(state).decode().split(':')[0]
    except:
        return redirect('/chat?error=oauth_invalid_state')
    
    from providers import get_secret
    client_id = get_secret('SALESFORCE_CLIENT_ID')
    client_secret = get_secret('SALESFORCE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return jsonify({'error': 'Salesforce OAuth not configured'}), 503
    
    import requests
    resp = requests.post('https://login.salesforce.com/services/oauth2/token', data={
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': 'https://lipaira.ai/api/auth/salesforce/callback',
        'code': code,
    })
    
    tokens = resp.json()
    if 'access_token' not in tokens:
        return redirect('/chat?error=salesforce_denied')
    
    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')
    instance_url = tokens.get('instance_url')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS salesforce_access_token TEXT,
            ADD COLUMN IF NOT EXISTS salesforce_refresh_token TEXT,
            ADD COLUMN IF NOT EXISTS salesforce_instance_url TEXT
        """)
    except:
        pass
    
    cursor.execute("""
        UPDATE users SET salesforce_access_token = %s, salesforce_refresh_token = %s, salesforce_instance_url = %s WHERE id = %s
    """, (access_token, refresh_token, instance_url, user_id))
    conn.commit()
    conn.close()
    
    return redirect('/chat?connected=salesforce')


@app.route('/api/auth/salesforce/status')
@require_auth
def salesforce_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT salesforce_access_token IS NOT NULL FROM users WHERE id = %s", (g.user_id,))
    connected = cursor.fetchone()[0]
    conn.close()
    return jsonify({'connected': connected})


@app.route('/api/auth/salesforce/disconnect', methods=['POST'])
@require_auth
def salesforce_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET salesforce_access_token = NULL, salesforce_refresh_token = NULL, salesforce_instance_url = NULL WHERE id = %s", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============================================================================
# ZOHO OAuth
# ============================================================================

@app.route('/api/auth/zoho/connect')
def zoho_connect():
    """Start Zoho OAuth flow."""
    import secrets
    import base64
    from urllib.parse import urlencode
    
    from providers import get_secret
    client_id = get_secret('ZOHO_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Zoho OAuth not configured'}), 503
    
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({'error': 'user_id parameter required'}), 400
    
    state = base64.b64encode(f"{user_id}:{secrets.token_urlsafe(16)}".encode()).decode()
    
    params = urlencode({
        'client_id': client_id,
        'response_type': 'code',
        'scope': 'ZohoCRM.modules.all,ZohoCRM.settings.all',
        'redirect_uri': 'https://lipaira.ai/api/auth/zoho/callback',
        'state': state,
        'access_type': 'offline'
    })
    
    return redirect(f'https://accounts.zoho.com/oauth/v2/auth?{params}')


@app.route('/api/auth/zoho/callback')
def zoho_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        import base64
        user_id = base64.b64decode(state).decode().split(':')[0]
    except:
        return redirect('/dashboard?error=oauth_invalid_state')
    
    from providers import get_secret
    client_id = get_secret('ZOHO_CLIENT_ID')
    client_secret = get_secret('ZOHO_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return jsonify({'error': 'Zoho OAuth not configured'}), 503
    
    import requests
    import base64
    
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    resp = requests.post(
        'https://accounts.zoho.com/oauth/v2/token',
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': 'https://lipaira.ai/api/auth/zoho/callback',
        },
        headers={
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    )
    
    tokens = resp.json()
    
    if 'access_token' not in tokens:
        print(f"Zoho OAuth error: {tokens}")
        return redirect('/dashboard?error=zoho_denied')
    
    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Save to user_integrations
    import json
    extra_data = json.dumps({"api_domain": tokens.get('api_domain')})
    cursor.execute("""
        INSERT INTO user_integrations (user_id, provider, access_token, refresh_token, status, extra, created_at)
        VALUES (%s, 'zoho', %s, %s, 'connected', %s::jsonb, NOW())
        ON CONFLICT (user_id, provider) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            status = 'connected',
            extra = EXCLUDED.extra,
            updated_at = NOW()
    """, (user_id, access_token, refresh_token, extra_data))
    
    conn.commit()
    conn.close()
    
    return redirect('/dashboard?connected=zoho')


@app.route('/api/auth/zoho/status')
@require_auth
def zoho_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT access_token IS NOT NULL FROM user_integrations WHERE user_id = %s AND provider = 'zoho'", (g.user_id,))
    connected = cursor.fetchone()[0] if cursor.fetchone() else False
    conn.close()
    return jsonify({'connected': bool(connected)})


@app.route('/api/auth/zoho/disconnect', methods=['POST'])
@require_auth
def zoho_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_integrations WHERE user_id = %s AND provider = 'zoho'", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============================================================================
# NEW OAUTH PROVIDERS (from INTEGRATIONS.md spec)
# ============================================================================

@app.route('/api/auth/zoom/connect')
def zoom_connect():
    """Connect Zoom OAuth."""
    key = request.args.get('key') or request.headers.get('X-Lipaira-Key')
    user = get_user_by_key(key)
    if not user:
        return jsonify({'error': 'Invalid key'}), 401

    import secrets
    state = f"{user.id}:{secrets.token_urlsafe(16)}"

    from providers import get_secret
    client_id = get_secret('ZOOM_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Zoom OAuth not configured'}), 503

    auth_url = (
        f"https://zoom.us/oauth/authorize?"
        f"response_type=code&client_id={client_id}"
        f"&redirect_uri=https://lipaira.ai/api/auth/zoom/callback"
        f"&state={state}"
    )
    return redirect(auth_url)


@app.route('/api/auth/zoom/callback')
def zoom_callback():
    """Zoom OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')

    if not code:
        return redirect('/dashboard?error=zoom_denied')

    user_id = state.split(':')[0] if state else None

    from providers import get_secret
    client_id = get_secret('ZOOM_CLIENT_ID')
    client_secret = get_secret('ZOOM_CLIENT_SECRET')

    if not client_id or not client_secret:
        return jsonify({'error': 'Zoom OAuth not configured'}), 503

    import requests

    resp = requests.post(
        'https://zoom.us/oauth/token',
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': 'https://lipaira.ai/api/auth/zoom/callback',
        },
        auth=(client_id, client_secret)
    )

    tokens = resp.json()

    if 'access_token' not in tokens:
        return redirect('/dashboard?error=zoom_denied')

    conn = get_db_connection()
    cursor = conn.cursor()
    import json
    cursor.execute("""
        INSERT INTO user_integrations (user_id, provider, access_token, refresh_token, status, extra, created_at)
        VALUES (%s, 'zoom', %s, %s, 'connected', '{}'::jsonb, NOW())
        ON CONFLICT (user_id, provider) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            status = 'connected',
            extra = EXCLUDED.extra,
            updated_at = NOW()
    """, (user_id, tokens.get('access_token'), tokens.get('refresh_token')))
    conn.commit()
    conn.close()

    return redirect('/dashboard?connected=zoom')


@app.route('/api/auth/zoom/status')
@require_auth
def zoom_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM user_integrations WHERE user_id = %s AND provider = 'zoom'", (g.user_id,))
    row = cursor.fetchone()
    conn.close()
    return jsonify({'connected': row is not None and row[0] == 'connected'})


@app.route('/api/auth/zoom/disconnect', methods=['POST'])
@require_auth
def zoom_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_integrations WHERE user_id = %s AND provider = 'zoom'", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Calendly OAuth
# ---------------------------------------------------------------------------

@app.route('/api/auth/calendly/connect')
def calendly_connect():
    """Connect Calendly OAuth."""
    key = request.args.get('key') or request.headers.get('X-Lipaira-Key')
    user = get_user_by_key(key)
    if not user:
        return jsonify({'error': 'Invalid key'}), 401

    import secrets
    state = f"{user.id}:{secrets.token_urlsafe(16)}"

    from providers import get_secret
    client_id = get_secret('CALENDLY_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Calendly OAuth not configured'}), 503

    auth_url = (
        f"https://auth.calendly.com/oauth/authorize?"
        f"response_type=code&client_id={client_id}"
        f"&redirect_uri=https://lipaira.ai/api/auth/calendly/callback"
        f"&state={state}"
    )
    return redirect(auth_url)


@app.route('/api/auth/calendly/callback')
def calendly_callback():
    """Calendly OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')

    if not code:
        return redirect('/dashboard?error=calendly_denied')

    user_id = state.split(':')[0] if state else None

    from providers import get_secret
    client_id = get_secret('CALENDLY_CLIENT_ID')
    client_secret = get_secret('CALENDLY_CLIENT_SECRET')

    if not client_id or not client_secret:
        return jsonify({'error': 'Calendly OAuth not configured'}), 503

    import requests

    resp = requests.post(
        'https://auth.calendly.com/oauth/token',
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': 'https://lipaira.ai/api/auth/calendly/callback',
            'client_id': client_id,
            'client_secret': client_secret
        }
    )

    tokens = resp.json()

    if 'access_token' not in tokens:
        return redirect('/dashboard?error=calendly_denied')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_integrations (user_id, provider, access_token, refresh_token, status, extra, created_at)
        VALUES (%s, 'calendly', %s, %s, 'connected', '{}'::jsonb, NOW())
        ON CONFLICT (user_id, provider) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            status = 'connected',
            updated_at = NOW()
    """, (user_id, tokens.get('access_token'), tokens.get('refresh_token')))
    conn.commit()
    conn.close()

    return redirect('/dashboard?connected=calendly')


@app.route('/api/auth/calendly/status')
@require_auth
def calendly_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM user_integrations WHERE user_id = %s AND provider = 'calendly'", (g.user_id,))
    row = cursor.fetchone()
    conn.close()
    return jsonify({'connected': row is not None and row[0] == 'connected'})


@app.route('/api/auth/calendly/disconnect', methods=['POST'])
@require_auth
def calendly_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_integrations WHERE user_id = %s AND provider = 'calendly'", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Meta Ads OAuth
# ---------------------------------------------------------------------------

@app.route('/api/auth/meta_ads/connect')
def meta_ads_connect():
    """Connect Meta Ads OAuth."""
    key = request.args.get('key') or request.headers.get('X-Lipaira-Key')
    user = get_user_by_key(key)
    if not user:
        return jsonify({'error': 'Invalid key'}), 401

    import secrets
    state = f"{user.id}:{secrets.token_urlsafe(16)}"

    from providers import get_secret
    client_id = get_secret('META_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Meta Ads OAuth not configured'}), 503

    auth_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth?"
        f"client_id={client_id}"
        f"&redirect_uri=https://lipaira.ai/api/auth/meta_ads/callback"
        f"&state={state}"
        f"&scope=ads_management,ads_read,business_management"
    )
    return redirect(auth_url)


@app.route('/api/auth/meta_ads/callback')
def meta_ads_callback():
    """Meta Ads OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')

    if not code:
        return redirect('/dashboard?error=meta_denied')

    user_id = state.split(':')[0] if state else None

    from providers import get_secret
    client_id = get_secret('META_CLIENT_ID')
    client_secret = get_secret('META_CLIENT_SECRET')

    if not client_id or not client_secret:
        return jsonify({'error': 'Meta Ads OAuth not configured'}), 503

    import requests

    resp = requests.get(
        'https://graph.facebook.com/v18.0/oauth/access_token',
        params={
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': 'https://lipaira.ai/api/auth/meta_ads/callback',
            'code': code
        }
    )

    tokens = resp.json()

    if 'access_token' not in tokens:
        return redirect('/dashboard?error=meta_denied')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_integrations (user_id, provider, access_token, refresh_token, status, extra, created_at)
        VALUES (%s, 'meta_ads', %s, %s, 'connected', '{}'::jsonb, NOW())
        ON CONFLICT (user_id, provider) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            status = 'connected',
            updated_at = NOW()
    """, (user_id, tokens.get('access_token'), tokens.get('refresh_token')))
    conn.commit()
    conn.close()

    return redirect('/dashboard?connected=meta_ads')


@app.route('/api/auth/meta_ads/status')
@require_auth
def meta_ads_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM user_integrations WHERE user_id = %s AND provider = 'meta_ads'", (g.user_id,))
    row = cursor.fetchone()
    conn.close()
    return jsonify({'connected': row is not None and row[0] == 'connected'})


@app.route('/api/auth/meta_ads/disconnect', methods=['POST'])
@require_auth
def meta_ads_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_integrations WHERE user_id = %s AND provider = 'meta_ads'", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Canva OAuth
# ---------------------------------------------------------------------------

@app.route('/api/auth/canva/connect')
def canva_connect():
    """Connect Canva OAuth."""
    key = request.args.get('key') or request.headers.get('X-Lipaira-Key')
    user = get_user_by_key(key)
    if not user:
        return jsonify({'error': 'Invalid key'}), 401

    import secrets
    state = f"{user.id}:{secrets.token_urlsafe(16)}"

    from providers import get_secret
    client_id = get_secret('CANVA_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Canva OAuth not configured'}), 503

    auth_url = (
        f"https://www.canva.com/api/oauth/authorize?"
        f"response_type=code&client_id={client_id}"
        f"&redirect_uri=https://lipaira.ai/api/auth/canva/callback"
        f"&state={state}"
        f"&scope=design:content:read,design:content:write,design:meta:read"
    )
    return redirect(auth_url)


@app.route('/api/auth/canva/callback')
def canva_callback():
    """Canva OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')

    if not code:
        return redirect('/dashboard?error=canva_denied')

    user_id = state.split(':')[0] if state else None

    from providers import get_secret
    client_id = get_secret('CANVA_CLIENT_ID')
    client_secret = get_secret('CANVA_CLIENT_SECRET')

    if not client_id or not client_secret:
        return jsonify({'error': 'Canva OAuth not configured'}), 503

    import requests
    import base64

    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    resp = requests.post(
        'https://api.canva.com/rest/v1/oauth/token',
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': 'https://lipaira.ai/api/auth/canva/callback',
        },
        headers={'Authorization': f'Basic {auth}'}
    )

    tokens = resp.json()

    if 'access_token' not in tokens:
        return redirect('/dashboard?error=canva_denied')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_integrations (user_id, provider, access_token, refresh_token, status, extra, created_at)
        VALUES (%s, 'canva', %s, %s, 'connected', '{}'::jsonb, NOW())
        ON CONFLICT (user_id, provider) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            status = 'connected',
            updated_at = NOW()
    """, (user_id, tokens.get('access_token'), tokens.get('refresh_token')))
    conn.commit()
    conn.close()

    return redirect('/dashboard?connected=canva')


@app.route('/api/auth/canva/status')
@require_auth
def canva_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM user_integrations WHERE user_id = %s AND provider = 'canva'", (g.user_id,))
    row = cursor.fetchone()
    conn.close()
    return jsonify({'connected': row is not None and row[0] == 'connected'})


@app.route('/api/auth/canva/disconnect', methods=['POST'])
@require_auth
def canva_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_integrations WHERE user_id = %s AND provider = 'canva'", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Asana OAuth
# ---------------------------------------------------------------------------

@app.route('/api/auth/asana/connect')
def asana_connect():
    """Connect Asana OAuth."""
    key = request.args.get('key') or request.headers.get('X-Lipaira-Key')
    user = get_user_by_key(key)
    if not user:
        return jsonify({'error': 'Invalid key'}), 401

    import secrets
    state = f"{user.id}:{secrets.token_urlsafe(16)}"

    from providers import get_secret
    client_id = get_secret('ASANA_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'Asana OAuth not configured'}), 503

    auth_url = (
        f"https://app.asana.com/-/oauth_authorize?"
        f"client_id={client_id}"
        f"&redirect_uri=https://lipaira.ai/api/auth/asana/callback"
        f"&state={state}"
        f"&response_type=code"
    )
    return redirect(auth_url)


@app.route('/api/auth/asana/callback')
def asana_callback():
    """Asana OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')

    if not code:
        return redirect('/dashboard?error=asana_denied')

    user_id = state.split(':')[0] if state else None

    from providers import get_secret
    client_id = get_secret('ASANA_CLIENT_ID')
    client_secret = get_secret('ASANA_CLIENT_SECRET')

    if not client_id or not client_secret:
        return jsonify({'error': 'Asana OAuth not configured'}), 503

    import requests

    resp = requests.post(
        'https://app.asana.com/-/oauth_token',
        data={
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': 'https://lipaira.ai/api/auth/asana/callback',
            'code': code
        }
    )

    tokens = resp.json()

    if 'access_token' not in tokens:
        return redirect('/dashboard?error=asana_denied')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_integrations (user_id, provider, access_token, refresh_token, status, extra, created_at)
        VALUES (%s, 'asana', %s, %s, 'connected', '{}'::jsonb, NOW())
        ON CONFLICT (user_id, provider) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            status = 'connected',
            updated_at = NOW()
    """, (user_id, tokens.get('access_token'), tokens.get('refresh_token')))
    conn.commit()
    conn.close()

    return redirect('/dashboard?connected=asana')


@app.route('/api/auth/asana/status')
@require_auth
def asana_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM user_integrations WHERE user_id = %s AND provider = 'asana'", (g.user_id,))
    row = cursor.fetchone()
    conn.close()
    return jsonify({'connected': row is not None and row[0] == 'connected'})


@app.route('/api/auth/asana/disconnect', methods=['POST'])
@require_auth
def asana_disconnect():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_integrations WHERE user_id = %s AND provider = 'asana'", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============================================================================
# TRELLO OAUTH (OAuth 1.0a)
# ============================================================================

@app.route('/api/auth/trello/connect')
def trello_connect():
    """Start Trello OAuth 1.0a flow - get request token."""
    user_id = request.args.get('user_id')
    if not user_id:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            api_key = auth_header[7:]
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM api_keys WHERE key_prefix = %s AND active = true", (api_key[:20],))
            row = cur.fetchone()
            if row:
                user_id = row[0]
            conn.close()
    
    if not user_id:
        return redirect('/login?error=no_user')
    
    # Get Trello API key from secrets
    from providers import get_secret
    api_key = get_secret("TRELLO_API_KEY")
    api_secret = get_secret("TRELLO_API_SECRET")
    
    if not api_key or not api_secret:
        return redirect('/dashboard?error=trello_not_configured')
    
    # OAuth 1.0a - Step 1: Get request token
    import uuid
    oauth_token = str(uuid.uuid4())
    oauth_secret = str(uuid.uuid4())
    
    # Store in session/cache for callback
    from datetime import datetime, timedelta
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO oauth_states (state, user_id, provider, created_at)
        VALUES (%s, %s, 'trello', NOW())
        ON CONFLICT (state) DO UPDATE SET user_id = %s, created_at = NOW()
    """, (oauth_token, user_id, user_id))
    conn.commit()
    
    # Build authorization URL
    callback_url = "https://lipaira.ai/api/auth/trello/callback"
    auth_url = (
        f"https://trello.com/1/OAuthAuthorizeToken?"
        f"oauth_token={api_key}&"
        f"name=Lipaira&"
        f"expiration=never&"
        f"scope=read,write&"
        f"response_type=token"
    )
    
    # Store the API key/secret temporarily (not ideal but needed for OAuth 1.0a)
    cur.execute("""
        INSERT INTO oauth_states (state, user_id, provider, created_at, extra)
        VALUES (%s, %s, 'trello', NOW(), %s)
    """, (f"{oauth_token}_secret", user_id, json.dumps({"api_key": api_key, "api_secret": api_secret, "oauth_token": oauth_token, "oauth_secret": oauth_secret})))
    conn.commit()
    conn.close()
    
    # For Trello, the API key becomes the request token in the authorization URL
    # This is simplified - normally you'd use a proper OAuth library
    trello_auth_url = f"https://trello.com/1/OAuthAuthorizeToken?name=Lipaira&expiration=never&scope=read,write&response_type=token&return_url={callback_url}?oauth_token={api_key}"
    
    return redirect(trello_auth_url)


@app.route('/api/auth/trello/callback')
def trello_callback():
    """Trello OAuth callback - exchange token."""
    oauth_token = request.args.get('oauth_token', '')
    api_key = request.args.get('oauth_token', '')  # Same in Trello's flow
    
    if not api_key:
        return redirect('/dashboard?error=trello_failed')
    
    # Find the user from the stored state
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, extra FROM oauth_states 
        WHERE provider = 'trello' AND extra::text LIKE %s
        ORDER BY created_at DESC LIMIT 1
    """, (f"%{api_key}%",))
    row = cur.fetchone()
    
    if not row:
        conn.close()
        return redirect('/dashboard?error=trello_failed')
    
    user_id = row[0]
    
    # Store the token
    cur.execute("""
        INSERT INTO user_integrations (user_id, provider, access_token, status, extra, connected, created_at)
        VALUES (%s, 'trello', %s, 'connected', %s, true, NOW())
        ON CONFLICT (user_id, provider) DO UPDATE SET
            access_token = %s,
            extra = %s,
            connected = true,
            status = 'connected'
    """, (user_id, oauth_token, json.dumps({"api_key": api_key}), oauth_token, json.dumps({"api_key": api_key})))
    conn.commit()
    conn.close()
    
    # Trigger sweep
    try:
        from memory_sweep import trigger_sweep
        trigger_sweep(user_id, 'trello')
    except:
        pass
    
    return redirect('/dashboard?connected=trello')


@app.route('/api/auth/trello/status')
@require_auth
def trello_status():
    """Check Trello connection status."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT connected, status, created_at FROM user_integrations
        WHERE user_id = %s AND provider = 'trello'
    """, (g.user_id,))
    row = cur.fetchone()
    conn.close()
    
    if row:
        return jsonify({
            'connected': row[0],
            'status': row[1],
            'connected_at': row[2].isoformat() if row[2] else None
        })
    return jsonify({'connected': False})


@app.route('/api/auth/trello/disconnect', methods=['POST'])
@require_auth
def trello_disconnect():
    """Disconnect Trello."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_integrations WHERE user_id = %s AND provider = 'trello'", (g.user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ============================================================================
# BILLING API ENDPOINTS
# ============================================================================

@app.route('/api/billing/calculate', methods=['POST'])
def billing_calculate():
    """Calculate credits and fee for a payment amount."""
    data = request.get_json()
    amount = float(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    result = billing.calculate_credits_and_fee(amount)
    return jsonify(result)


@app.route('/api/billing/pricing', methods=['GET'])
def billing_pricing():
    """Get all pricing tiers."""
    tiers = billing.get_pricing_tiers()
    return jsonify({'tiers': tiers})


@app.route('/api/billing/sweep', methods=['POST'])
@require_auth
def billing_sweep():
    """Trigger daily revenue sweep (admin only)."""
    # Check if admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE id = %s", (g.user_id,))
    row = cursor.fetchone()
    
    if not row or row[0] != 'admin':
        cursor.close()
        conn.close()
        return jsonify({'error': 'Admin only'}), 403
    
    data = request.get_json() or {}
    sweep_date = data.get('date')
    
    if sweep_date:
        from datetime import datetime
        sweep_date = datetime.strptime(sweep_date, '%Y-%m-%d').date()
    
    result = billing.run_daily_sweep(sweep_date)
    cursor.close()
    conn.close()
    return jsonify(result)


@app.route('/api/billing/usage', methods=['GET'])
@require_auth
def billing_usage():
    """Get user's usage history."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT model, input_tokens, output_tokens, cost, created_at
        FROM llm_usage
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 50
    """, (g.user_id,))
    
    usage = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    
    return jsonify({'usage': usage})


# ============================================================================
# INVOICE CHASE WORKFLOW (Block 2 Item 4)
# ============================================================================

@app.route('/api/invoice/chase/draft', methods=['POST'])
@require_auth
def draft_invoice_chase():
    """
    Draft a chase email for an overdue invoice.
    Returns draft content for approval flow.
    """
    from invoice_chase_workflow import InvoiceChaseWorkflow
    
    data = request.get_json() or {}
    client_name = data.get('client_name', '')
    invoice_number = data.get('invoice_number', '')
    amount_due = float(data.get('amount_due', 0))
    days_overdue = int(data.get('days_overdue', 7))
    
    workflow = InvoiceChaseWorkflow()
    draft = workflow.draft_chase_email(
        g.user_id, client_name, invoice_number, amount_due, days_overdue
    )
    
    return jsonify(draft)


@app.route('/api/invoice/chase/submit', methods=['POST'])
@require_auth
def submit_chase_for_approval():
    """
    Submit a drafted chase for SMS approval.
    Creates approval request and sends SMS to user.
    """
    from invoice_chase_workflow import InvoiceChaseWorkflow
    from sms_approval_flow import SMSApprovalFlow
    
    data = request.get_json() or {}
    draft_content = data.get('draft_content', '')
    client_name = data.get('client_name', '')
    
    workflow = InvoiceChaseWorkflow()
    approval_flow = SMSApprovalFlow()
    
    # Get user's phone
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM users WHERE id = %s", (g.user_id,))
    row = cursor.fetchone()
    phone = row[0] if row else None
    conn.close()
    
    if not phone:
        return jsonify({'error': 'No phone number on file'}), 400
    
    # Create approval request
    result = approval_flow.create_approval_request(
        g.user_id, 'invoice_chase', draft_content, phone
    )
    
    return jsonify(result)


@app.route('/api/invoice/overdue', methods=['GET'])
@require_auth
def get_overdue_invoices():
    """Get list of overdue invoices from QuickBooks."""
    from invoice_chase_workflow import InvoiceChaseWorkflow
    
    days = request.args.get('days', 7, type=int)
    
    workflow = InvoiceChaseWorkflow()
    invoices = workflow.get_overdue_invoices(g.user_id, days)
    
    return jsonify({'overdue': invoices})


# ============================================================================
# MORNING BRIEFING (Block 2 Item 5)
# ============================================================================

@app.route('/api/briefing/generate', methods=['GET'])
@require_auth
def generate_briefing():
    """Generate morning briefing for current user."""
    from morning_briefing import MorningBriefingEngine
    
    engine = MorningBriefingEngine()
    briefing = engine.generate_briefing(g.user_id)
    
    return jsonify(briefing)


@app.route('/api/briefing/email', methods=['GET'])
@require_auth
def get_briefing_email():
    """Get formatted email for morning briefing."""
    from morning_briefing import MorningBriefingEngine
    
    engine = MorningBriefingEngine()
    briefing = engine.generate_briefing(g.user_id)
    
    # Get user name
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT display_name FROM user_profiles WHERE user_id = %s", (g.user_id,))
    row = cursor.fetchone()
    user_name = row[0] if row else None
    conn.close()
    
    email = engine.format_email(briefing, user_name)
    
    return jsonify(email)


@app.route('/api/briefing/schedule', methods=['POST'])
@require_auth
def schedule_briefing():
    """Schedule morning briefing delivery time."""
    data = request.get_json() or {}
    hour = data.get('hour', 7)  # Default 7 AM
    
    # Store preference
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_preferences (user_id, preference_key, preference_value)
        VALUES (%s, 'briefing_hour', %s)
        ON CONFLICT (user_id, preference_key) 
        DO UPDATE SET preference_value = %s
    """, (g.user_id, str(hour), str(hour)))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'success': True, 'scheduled_hour': hour})


# ============================================================================
# ACTIVITY LOG (Block 2 Item 6)
# ============================================================================

@app.route('/api/activity', methods=['GET'])
@require_auth
def get_activity_log():
    """Get user's activity log (last 50 entries)."""
    limit = request.args.get('limit', 50, type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT id, action_type, description, status, created_at, metadata
        FROM activity_log
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, (g.user_id, limit))
    
    results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    
    return jsonify({'activity': results})


@app.route('/api/activity', methods=['POST'])
@require_auth
def log_activity():
    """Log a new activity entry."""
    data = request.get_json() or {}
    action_type = data.get('action_type', '')
    description = data.get('description', '')
    status = data.get('status', 'completed')
    metadata = data.get('metadata', {})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO activity_log (user_id, action_type, description, status, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (g.user_id, action_type, description, status, json.dumps(metadata)))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'success': True})

