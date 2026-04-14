"""
User Settings API - Model Preference
=====================================
GET /api/settings/model-preference - Get user's model slider
POST /api/settings/model-preference - Set user's model slider
GET /api/models/available - Get available models based on API keys
"""

from flask import Blueprint, jsonify, request
from .model_preference import (
    CapabilityLevel, 
    ModelPreferenceManager, 
    MODEL_PREFERENCES,
    SLIDER_CONFIG,
    MODEL_PREFERENCE_INFO
)
import os

settings_bp = Blueprint('settings', __name__)


# Track which API keys are configured
def get_configured_providers():
    """Check which providers have API keys configured"""
    providers = []
    
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
    if os.environ.get("GOOGLE_API_KEY"):
        providers.append("google")
    if os.environ.get("MISTRAL_API_KEY"):
        providers.append("mistral")
    if os.environ.get("COHERE_API_KEY"):
        providers.append("cohere")
    if os.environ.get("DEEPSEEK_API_KEY"):
        providers.append("deepseek")
    if os.environ.get("DASHSCOPE_API_KEY"):
        providers.append("qwen")
    if os.environ.get("AZURE_OPENAI_API_KEY"):
        providers.append("microsoft")
    if os.environ.get("NVIDIA_API_KEY"):
        providers.append("nvidia")
    if os.environ.get("PERPLEXITY_API_KEY"):
        providers.append("perplexity")
    if os.environ.get("ZEROONE_API_KEY"):
        providers.append("01-ai")
    if os.environ.get("MINIMAX_API_KEY"):
        providers.append("minimax")
    if os.environ.get("TOGETHER_API_KEY"):
        providers.append("together")
    
    # Ollama is local - always available if running
    # Would check if Ollama is actually reachable
    
    return providers


@settings_bp.route('/api/settings/model-preference', methods=['GET'])
def get_model_preference():
    """Get user's model preference"""
    user_id = request.headers.get('X-User-ID') or 'demo'
    
    # In production, query from database
    # For now, return defaults
    manager = ModelPreferenceManager()
    current_level = manager.get_user_preference(user_id)
    
    return jsonify({
        "user_id": user_id,
        "level": current_level.value,
        "label": MODEL_PREFERENCE_INFO[current_level].label,
        "description": MODEL_PREFERENCE_INFO[current_level].description,
        "slider_config": SLIDER_CONFIG,
        "available_levels": [
            {
                "level": level.value,
                "label": info.label,
                "description": info.description,
                "estimated_cost": info.estimated_cost
            }
            for level, info in MODEL_PREFERENCE_INFO.items()
        ]
    })


@settings_bp.route('/api/settings/model-preference', methods=['POST'])
def set_model_preference():
    """Set user's model preference"""
    data = request.get_json() or {}
    level = data.get('level', 3)
    
    try:
        level_enum = CapabilityLevel(level)
    except ValueError:
        return jsonify({"error": "Invalid level (1-5)"}), 400
    
    return jsonify({
        "success": True,
        "level": level_enum.value,
        "label": MODEL_PREFERENCE_INFO[level_enum].label,
        "recommended_model": MODEL_PREFERENCES[level_enum][0]["model"]
    })


@settings_bp.route('/api/settings/manual-model', methods=['GET'])
def get_manual_model():
    """Get user's manual model override"""
    user_id = request.headers.get('X-User-ID') or 'demo'
    
    manager = ModelPreferenceManager()
    manual = manager.get_manual_model(user_id)
    
    return jsonify({
        "user_id": user_id,
        "manual_model": manual,
        "mode": "manual" if manual else "slider"
    })


@settings_bp.route('/api/settings/manual-model', methods=['POST'])
def set_manual_model():
    """Set manual model override"""
    data = request.get_json() or {}
    model = data.get('model', '').strip()
    
    if not model:
        return jsonify({"error": "Model name required"}), 400
    
    manager = ModelPreferenceManager()
    success = manager.set_manual_model('demo', model)  # user_id would come from auth
    
    return jsonify({
        "success": success,
        "mode": "manual",
        "model": model,
        "provider": manager._get_provider_for_model(model)
    })


@settings_bp.route('/api/settings/manual-model', methods=['DELETE'])
def clear_manual_model():
    """Clear manual model, return to slider mode"""
    user_id = request.headers.get('X-User-ID') or 'demo'
    
    manager = ModelPreferenceManager()
    manager.clear_manual_model(user_id)
    
    return jsonify({
        "success": True,
        "mode": "slider"
    })


@settings_bp.route('/api/models/available', methods=['GET'])
def get_available_models():
    """Get models available based on configured API keys"""
    configured = get_configured_providers()
    
    # Build available models list
    available_models = []
    
    for level, models in MODEL_PREFERENCES.items():
        level_info = MODEL_PREFERENCE_INFO[level]
        
        for model_info in models:
            if model_info["provider"] in configured or model_info["provider"] == "ollama":
                # Ollama is special - available locally
                if model_info["provider"] == "ollama":
                    available_models.append({
                        "model": model_info["model"],
                        "provider": model_info["provider"],
                        "level": level.value,
                        "level_label": level_info.label,
                        "cost": level_info.estimated_cost,
                        "type": "local"
                    })
                else:
                    available_models.append({
                        "model": model_info["model"],
                        "provider": model_info["provider"],
                        "level": level.value,
                        "level_label": level_info.label,
                        "cost": level_info.estimated_cost,
                        "type": "api"
                    })
    
    return jsonify({
        "configured_providers": configured,
        "available_providers_count": len(set(m["provider"] for m in available_models)),
        "models": available_models,
        "slider_config": SLIDER_CONFIG
    })


# For use in the actual LLM calls
def resolve_model_from_preference(user_id: str = None, level: int = None, explicit_model: str = None) -> str:
    """
    Given a user preference level, return the model to use.
    
    Priority:
    1. explicit_model - passed directly in API call
    2. manual_model - user set in settings
    3. slider level - from preference slider
    
    Usage:
        model = resolve_model_from_preference(user_id="123", level=3)
        model = resolve_model_from_preference(user_id="123", explicit_model="gpt-4o")
    """
    manager = ModelPreferenceManager()
    result = manager.resolve_model(user_id=user_id, level=level, explicit_model=explicit_model)
    return result["model"]


@settings_bp.route('/api/chat/model-command', methods=['POST'])
def chat_model_command():
    """
    Parse a chat message for model change commands.
    
    Examples:
    - "use gpt-4o" → switches to gpt-4o
    - "switch to claude-3.5-sonnet" → switches model
    - "use the fastest model" → sets slider to level 1
    """
    data = request.get_json() or {}
    message = data.get('message', '')
    
    from .model_preference import parse_chat_model_command
    
    result = parse_chat_model_command(message)
    
    if not result:
        return jsonify({"has_command": False})
    
    manager = ModelPreferenceManager()
    
    if result["type"] == "explicit":
        # User specified a model
        model = result["value"]
        return jsonify({
            "has_command": True,
            "action": "switch_model",
            "model": model,
            "provider": manager._get_provider_for_model(model)
        })
    
    elif result["type"] == "level":
        # User specified capability level
        level_map = {
            "fastest": 1,
            "fast": 2,
            "balanced": 3,
            "smart": 4,
            "smartest": 5
        }
        level = level_map.get(result["value"], 3)
        
        return jsonify({
            "has_command": True,
            "action": "set_level",
            "level": level,
            "label": MODEL_PREFERENCE_INFO[CapabilityLevel(level)].label
        })
    
    return jsonify({"has_command": False})


# Example: Agent execution with model override
AGENT_MODEL_USAGE = """
# In agent execution:

@app.route('/api/agents/<agent_id>/execute', methods=['POST'])
def execute_agent(agent_id):
    data = request.json
    user_message = data.get('message', '')
    
    # 1. Check for model command in message
    cmd = parse_chat_model_command(user_message)
    
    model = None
    if cmd:
        # User wants to change model
        if cmd['type'] == 'explicit':
            model = cmd['value']
            user_message = user_message.replace(cmd['value'], '').strip()
        elif cmd['type'] == 'level':
            model = resolve_model_from_preference(
                user_id=user_id, 
                level=cmd['value']
            )
    
    # 2. Or use explicit model from request
    model = model or data.get('model')
    
    # 3. Or fall back to user preference
    if not model:
        model = resolve_model_from_preference(user_id=user_id)
    
    # Execute with resolved model
    response = router.chat(messages, model=model)
    
    return jsonify({
        "response": response.content,
        "model_used": model,
        "model_source": response.provider
    })
"""


# Frontend component code
SLIDER_COMPONENT = """
<!-- Model Preference Slider Component -->
<div class="model-preference-slider">
    <label class="slider-label">Model Preference</label>
    <div class="slider-container">
        <input 
            type="range" 
            min="1" 
            max="5" 
            step="1" 
            value="3"
            class="model-slider"
            id="modelPreferenceSlider"
        />
        <div class="slider-labels">
            <span>🚀 Fastest</span>
            <span>⚡ Fast</span>
            <span>⚖️ Balanced</span>
            <span>🧠 Smart</span>
            <span>💎 Smartest</span>
        </div>
    </div>
    <div class="slider-info" id="sliderInfo">
        <span class="current-level">⚖️ Balanced</span>
        <span class="cost-estimate">~$3-6 / 1M tokens</span>
    </div>
</div>

<style>
.model-preference-slider {
    padding: 16px;
    background: var(--bg-card);
    border-radius: 12px;
    margin: 16px 0;
}
.slider-label {
    display: block;
    font-weight: 600;
    margin-bottom: 12px;
}
.model-slider {
    width: 100%;
    height: 8px;
    -webkit-appearance: none;
    background: linear-gradient(to right, #00ff88, #00cc6a);
    border-radius: 4px;
}
.slider-labels {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--text-dim);
    margin-top: 4px;
}
.slider-info {
    display: flex;
    justify-content: space-between;
    margin-top: 12px;
    font-size: 14px;
}
.current-level {
    font-weight: 600;
}
.cost-estimate {
    color: var(--accent);
}
</style>

<script>
const slider = document.getElementById('modelPreferenceSlider');
const info = document.getElementById('sliderInfo');

slider.addEventListener('input', (e) => {
    const level = e.target.value;
    const labels = ['', '🚀 Fastest', '⚡ Fast', '⚖️ Balanced', '🧠 Smart', '💎 Smartest'];
    const costs = ['', '$0.15-0.60', '$1-3', '$3-6', '$6-15', '$15-75'];
    info.querySelector('.current-level').textContent = labels[level];
    info.querySelector('.cost-estimate').textContent = '~' + costs[level] + ' / 1M tokens';
    
    // Save preference
    fetch('/api/settings/model-preference', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({level: parseInt(level)})
    });
});
</script>
"""
