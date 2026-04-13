"""
Unified Request API for Lipaira LLM interactions.
Single Flask blueprint entry point for all LLM requests:
  POST /api/unified/chat   - route to appropriate model
  GET  /api/unified/models - list available models
Design principles: single endpoint, auto task detection, honor user preferences.
"""
from flask import Blueprint, request, jsonify
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from enum import Enum
import time

# Import our routing system
from lipaira_providers.enhanced_preferences import PreferenceManager, TaskType
from lipaira_providers.task_detection import detect_task_type, resolve_model_with_task
from lipaira_providers.router import LipairaRouter, Message
from lipaira_providers.encryption import get_public_key, decrypt_request, encrypt_response

# Create the unified API
unified_bp = Blueprint('unified', __name__)


# ============================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================

@dataclass
class UnifiedRequest:
    """Standardized request format"""
    # Required
    message: str                    # User message
    
    # Optional overrides
    model: Optional[str] = None     # Explicit model
    task_type: Optional[str] = None # Force specific task type
    stream: bool = False            # Streaming response
    temperature: float = 0.7        # LLM temperature
    max_tokens: int = 4000          # Max tokens to generate
    
    # Context
    system_prompt: Optional[str] = None
    history: Optional[List[Dict]] = None  # Chat history
    
    # User preferences
    user_id: str = "demo"


@dataclass
class UnifiedResponse:
    """Standardized response format"""
    # Response
    content: str
    model: str
    provider: str
    
    # Task info (what triggered this model)
    task_type: str
    task_icon: str
    model_source: str  # explicit, task, preference
    
    # Usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_estimate: str = ""
    latency_ms: int = 0
    
    # Metadata
    success: bool = True
    error: Optional[str] = None


# ============================================================
# UNIFIED ENDPOINT
# ============================================================

@unified_bp.route('/v1/chat', methods=['POST'])
@unified_bp.route('/api/chat', methods=['POST'])
def chat():
    """
    Unified chat endpoint - single API for all requests
    
    Supports BOTH plaintext and encrypted requests automatically:
    
    Plaintext:
    {
        "message": "Hello, write me a function",
        "user_id": "user123"
    }
    
    Encrypted:
    {
        "encrypted": "base64_encrypted_json_payload"
    }
    
    Response (always encrypted if request was encrypted):
    {
        "content": "Here's a Python function...",
        "model": "claude-3-opus",
        "success": true
    }
    """
    start_time = time.time()
    
    # Parse request
    data = request.get_json() or {}
    
    # AUTO-DETECT: Check for encrypted payload
    encrypted = data.get('encrypted', '')
    if encrypted:
        try:
            data = decrypt_request(encrypted)
        except ValueError as e:
            return jsonify({"error": f"Decryption failed: {e}"}), 400
    
    # Extract message (from plaintext or decrypted)
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({"error": "message is required"}), 400
    
    # Get user preferences
    user_id = data.get('user_id', 'demo')
    prefs = PreferenceManager.get_preferences(user_id)
    slider_level = prefs.slider_level
    
    # Detect or use forced task type
    task_type_str = data.get('task_type')
    if task_type_str:
        try:
            task_type = TaskType(task_type_str)
        except ValueError:
            task_type = detect_task_type(user_message)
    else:
        task_type = detect_task_type(user_message)
    
    # Resolve model to use
    explicit_model = data.get('model')
    
    # Get model from preferences
    model = explicit_model or prefs.get_model(task_type)
    
    # Build messages
    messages = []
    
    # System prompt
    system_prompt = data.get('system_prompt')
    if system_prompt:
        messages.append(Message(role="system", content=system_prompt))
    
    # Chat history
    history = data.get('history', [])
    for msg in history:
        messages.append(Message(
            role=msg.get('role', 'user'),
            content=msg.get('content', '')
        ))
    
    # Current message
    messages.append(Message(role='user', content=user_message))
    
    # Make the request
    router = LipairaRouter()
    response = router.chat(
        messages=messages,
        model=model,
        temperature=data.get('temperature', 0.7),
        max_tokens=data.get('max_tokens', 4000)
    )
    
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Build response
    result = UnifiedResponse(
        content=response.content or "",
        model=response.model or model,
        provider=response.provider or "unknown",
        task_type=task_type.value,
        task_icon=task_type.value.icon if hasattr(task_type, 'icon') else "💬",
        model_source="explicit" if explicit_model else f"task_{task_type.value}",
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        total_tokens=response.total_tokens,
        cost_estimate=f"${response.cost:.4f}" if response.cost else "$0.00",
        latency_ms=latency_ms + response.latency_ms,
        success=response.success,
        error=response.error
    )
    
    response_data = asdict(result)
    
    # If request was encrypted, encrypt response too
    if encrypted:
        return jsonify({"encrypted": encrypt_response(response_data)})
    
    return jsonify(response_data)


# ============================================================
# ENCRYPTED ENDPOINTS
# ============================================================

@unified_bp.route('/v1/encryption/key', methods=['GET'])
@unified_bp.route('/api/encryption/key', methods=['GET'])
def get_encryption_key():
    """Get public key for client-side encryption"""
    return jsonify({"public_key": get_public_key()})


@unified_bp.route('/v1/chat/encrypted', methods=['POST'])
@unified_bp.route('/api/chat/encrypted', methods=['POST'])
def chat_encrypted():
    """End-to-end encrypted chat - server never sees plaintext"""
    start_time = time.time()
    data = request.get_json() or {}
    encrypted = data.get('encrypted', '')
    
    if not encrypted:
        return jsonify({"error": "No encrypted payload", "hint": "Send {encrypted: base64}"}), 400
    
    try:
        plaintext = decrypt_request(encrypted)
    except ValueError as e:
        return jsonify({"error": f"Decryption failed: {e}"}), 400
    
    user_message = plaintext.get('message', '').strip()
    if not user_message:
        return jsonify({"error": "message required"}), 400
    
    user_id = plaintext.get('user_id', 'demo')
    prefs = PreferenceManager.get_preferences(user_id)
    task_type = detect_task_type(user_message)
    model = prefs.get_model(task_type)
    
    messages = []
    if plaintext.get('system_prompt'):
        messages.append(Message(role="system", content=plaintext['system_prompt']))
    for msg in plaintext.get('history', []):
        messages.append(Message(role=msg.get('role', 'user'), content=msg.get('content', '')))
    messages.append(Message(role='user', content=user_message))
    
    router = LipairaRouter()
    response = router.chat(messages, model=model, temperature=plaintext.get('temperature', 0.7), max_tokens=plaintext.get('max_tokens', 4000))
    
    result = {
        "content": response.content or "",
        "model": response.model or model,
        "provider": response.provider or "unknown",
        "task_type": task_type.value,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "total_tokens": response.total_tokens,
        "cost_estimate": f"${response.cost:.4f}" if response.cost else "$0.00",
        "latency_ms": int((time.time() - start_time) * 1000) + response.latency_ms,
        "success": response.success,
        "error": response.error
    }
    
    return jsonify({"encrypted": encrypt_response(result)})


# ============================================================
# HELPER ENDPOINTS
# ============================================================

@unified_bp.route('/v1/models', methods=['GET'])
@unified_bp.route('/api/models', methods=['GET'])
def list_models():
    """List all available models"""
    return jsonify({
        "models": [
            {"id": "gpt-4o-mini", "provider": "OpenAI", "context": 128000},
            {"id": "gpt-4o", "provider": "OpenAI", "context": 128000},
            {"id": "gpt-4", "provider": "OpenAI", "context": 128000},
            {"id": "gpt-4-turbo", "provider": "OpenAI", "context": 128000},
            {"id": "claude-3-haiku", "provider": "Anthropic", "context": 200000},
            {"id": "claude-3.5-sonnet", "provider": "Anthropic", "context": 200000},
            {"id": "claude-3-opus", "provider": "Anthropic", "context": 200000},
            {"id": "gemini-2.0-flash", "provider": "Google", "context": 1000000},
            {"id": "gemini-2.5-pro", "provider": "Google", "context": 2000000},
            {"id": "mistral-small", "provider": "Mistral", "context": 128000},
            {"id": "mistral-medium", "provider": "Mistral", "context": 128000},
            {"id": "deepseek-coder", "provider": "DeepSeek", "context": 64000},
            {"id": "qwen-2-7b", "provider": "Qwen", "context": 32768},
            {"id": "qwen-2-72b", "provider": "Qwen", "context": 32768},
        ]
    })


@unified_bp.route('/v1/detect-task', methods=['POST'])
@unified_bp.route('/api/detect-task', methods=['POST'])
def detect_task():
    """Detect task type from message"""
    data = request.get_json() or {}
    message = data.get('message', '')
    
    task = detect_task_type(message)
    
    return jsonify({
        "task_type": task.value,
        "confidence": "high"  # Could add confidence scoring
    })


# ============================================================
# STREAMLING (optional)
# ============================================================

@unified_bp.route('/v1/chat/stream', methods=['POST'])
def chat_stream():
    """
    Streaming chat endpoint
    Uses server-sent events for real-time responses
    """
    from flask import Response
    import json
    
    data = request.get_json() or {}
    message = data.get('message', '')
    user_id = data.get('user_id', 'demo')
    
    # Get model
    task_type = detect_task_type(message)
    prefs = PreferenceManager.get_preferences(user_id)
    model = prefs.get_model(task_type)
    
    def generate():
        router = LipairaRouter()
        messages = [Message(role='user', content=message)]
        
        # For streaming, yield chunks as they come
        # (Implementation depends on provider support)
        response = router.chat(messages, model=model, stream=True)
        
        for chunk in response:
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return Response(generate(), mimetype='text/event-stream')
