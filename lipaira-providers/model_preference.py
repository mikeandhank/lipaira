"""
Model Preference Slider
========================
Users pick capability level, we pick the model
"""

from enum import Enum
from typing import List, Dict
from dataclasses import dataclass


class CapabilityLevel(Enum):
    """Slider positions from fast/cheap to smart/expensive"""
    FASTEST = 1      # gpt-4o-mini, llama3-8b
    FAST = 2         # gpt-4o, mistral-small
    BALANCED = 3     # claude-3-haiku, gemini-flash
    SMART = 4       # claude-3.5-sonnet, gpt-4
    SMARTEST = 5    # claude-3-opus, gpt-4-turbo


# Model preference tiers - auto-select based on capability level
MODEL_PREFERENCES = {
    CapabilityLevel.FASTEST: [
        {"model": "gpt-4o-mini", "provider": "openai", "score": 1, "cost_score": 1},
        {"model": "llama-3-8b", "provider": "together", "score": 2, "cost_score": 1},
        {"model": "ollama/llama3", "provider": "ollama", "score": 2, "cost_score": 0},
        {"model": "mistral-small", "provider": "mistral", "score": 3, "cost_score": 2},
        {"model": "phi3", "provider": "ollama", "score": 2, "cost_score": 0},
    ],
    CapabilityLevel.FAST: [
        {"model": "gpt-4o", "provider": "openai", "score": 4, "cost_score": 4},
        {"model": "gemini-2.0-flash-lite", "provider": "google", "score": 3, "cost_score": 1},
        {"model": "mistral-medium", "provider": "mistral", "score": 4, "cost_score": 3},
        {"model": "claude-3-haiku", "provider": "anthropic", "score": 4, "cost_score": 2},
    ],
    CapabilityLevel.BALANCED: [
        {"model": "claude-3.5-sonnet", "provider": "anthropic", "score": 5, "cost_score": 5},
        {"model": "gemini-2.0-flash", "provider": "google", "score": 4, "cost_score": 2},
        {"model": "gpt-4-turbo", "provider": "openai", "score": 5, "cost_score": 5},
    ],
    CapabilityLevel.SMART: [
        {"model": "gpt-4", "provider": "openai", "score": 6, "cost_score": 8},
        {"model": "claude-3-sonnet", "provider": "anthropic", "score": 6, "cost_score": 5},
        {"model": "gemini-2.5-pro", "provider": "google", "score": 6, "cost_score": 5},
    ],
    CapabilityLevel.SMARTEST: [
        {"model": "claude-3-opus", "provider": "anthropic", "score": 7, "cost_score": 10},
        {"model": "gpt-4-turbo", "provider": "openai", "score": 6, "cost_score": 7},
        {"model": "yi-large", "provider": "01-ai", "score": 6, "cost_score": 6},
    ],
}


@dataclass
class ModelPreference:
    level: CapabilityLevel
    label: str
    description: str
    estimated_cost: str  # "$/1M tokens"
    manual_model: str = None  # User-specified model override


MODEL_PREFERENCE_INFO = {
    CapabilityLevel.FASTEST: ModelPreference(
        level=CapabilityLevel.FASTEST,
        label="🚀 Fastest",
        description="Quick responses, lowest cost",
        estimated_cost="$0.15-0.60"
    ),
    CapabilityLevel.FAST: ModelPreference(
        level=CapabilityLevel.FAST,
        label="⚡ Fast",
        description="Good speed, moderate cost",
        estimated_cost="$1-3"
    ),
    CapabilityLevel.BALANCED: ModelPreference(
        level=CapabilityLevel.BALANCED,
        label="⚖️ Balanced",
        description="Best mix of speed and capability",
        estimated_cost="$3-6"
    ),
    CapabilityLevel.SMART: ModelPreference(
        level=CapabilityLevel.SMART,
        label="🧠 Smart",
        description="High capability, higher cost",
        estimated_cost="$6-15"
    ),
    CapabilityLevel.SMARTEST: ModelPreference(
        level=CapabilityLevel.SMARTEST,
        label="💎 Smartest",
        description="Most capable, premium cost",
        estimated_cost="$15-75"
    ),
}


class ModelPreferenceManager:
    """Manages user model preferences"""
    
    def __init__(self, db_pool=None):
        self.db = db_pool
    
    def get_user_preference(self, user_id: str) -> CapabilityLevel:
        """Get user's current model preference level"""
        # Default to SMARTEST (level 5) - Claude 3 Opus
        return CapabilityLevel.SMARTEST
    
    def set_user_preference(self, user_id: str, level: CapabilityLevel) -> bool:
        """Save user's model preference"""
        return True
    
    def get_manual_model(self, user_id: str) -> str:
        """Get user's manually specified model (overrides slider)"""
        # In production: query from database
        return None
    
    def set_manual_model(self, user_id: str, model: str) -> bool:
        """Set manual model override"""
        # In production: save to database
        return True
    
    def clear_manual_model(self, user_id: str) -> bool:
        """Clear manual model, go back to slider"""
        # In production: clear from database
        return True
    
    def get_model_for_level(self, level: CapabilityLevel, skip_provider: str = None) -> Dict:
        """Get the best model for a capability level."""
        candidates = MODEL_PREFERENCES[level]
        available = [c for c in candidates if c["provider"] != skip_provider]
        return available[0] if available else candidates[0]
    
    def resolve_model(self, user_id: str = None, level: int = None, explicit_model: str = None) -> Dict:
        """
        Resolve which model to use.
        
        Priority:
        1. Explicit model (passed in request)
        2. Manual override (set in settings)
        3. Slider preference level
        
        Returns: {model, provider, source}
        """
        # 1. Explicit model in request
        if explicit_model:
            provider = self._get_provider_for_model(explicit_model)
            return {
                "model": explicit_model,
                "provider": provider,
                "source": "explicit"  # User specified in request
            }
        
        # 2. Manual override
        manual_model = self.get_manual_model(user_id) if user_id else None
        if manual_model:
            provider = self._get_provider_for_model(manual_model)
            return {
                "model": manual_model,
                "provider": provider,
                "source": "manual"  # Set in settings
            }
        
        # 3. Slider preference
        if level is None and user_id:
            level = self.get_user_preference(user_id).value
        elif level is None:
            level = 5  # Default to SMARTEST
        
        try:
            level_enum = CapabilityLevel(level)
        except ValueError:
            level_enum = CapabilityLevel.BALANCED
        
        model_info = self.get_model_for_level(level_enum)
        return {
            "model": model_info["model"],
            "provider": model_info["provider"],
            "source": f"slider_{level}"  # From preference slider
        }
    
    def _get_provider_for_model(self, model: str) -> str:
        """Map model to provider"""
        for provider_type in Provider:
            if model.startswith(provider_type.value):
                return provider_type.value
        
        # Check MODEL_MAP patterns
        model_map = {
            "gpt-": "openai",
            "claude-": "anthropic",
            "gemini-": "google",
            "mistral-": "mistral",
            "command-": "cohere",
            "deepseek-": "deepseek",
            "qwen-": "qwen",
            "wizardlm": "microsoft",
            "nemotron": "nvidia",
            "pplx-": "perplexity",
            "yi-": "01-ai",
            "minimax": "minimax",
            "MiniMax": "minimax",
            "meta-llama/": "together",
            "ollama/": "ollama",
        }
        
        for pattern, provider in model_map.items():
            if pattern in model:
                return provider
        
        return "unknown"
    
    def get_all_preference_levels(self) -> List[Dict]:
        """Get all preference levels for UI"""
        return [
            {
                "level": level.value,
                "label": info.label,
                "description": info.description,
                "estimated_cost": info.estimated_cost,
                "recommended_model": MODEL_PREFERENCES[level][0]["model"]
            }
            for level, info in MODEL_PREFERENCE_INFO.items()
        ]


# Frontend slider values
SLIDER_CONFIG = {
    "min": 1,
    "max": 5,
    "step": 1,
    "marks": {
        1: "🚀 Fastest",
        2: "⚡ Fast", 
        3: "⚖️ Balanced",
        4: "🧠 Smart",
        5: "💎 Smartest"
    }
}


# Database migration for user preferences
USER_PREFERENCE_SQL = """
CREATE TABLE IF NOT EXISTS user_model_preferences (
    user_id UUID PRIMARY KEY,
    capability_level INTEGER DEFAULT 3,  -- 1-5 scale
    manual_model VARCHAR(255),  -- User-specified model override
    fallback_model VARCHAR(255),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Chat command history for model changes
CREATE TABLE IF NOT EXISTS user_model_commands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    agent_id UUID,
    command VARCHAR(50) NOT NULL,  -- 'use', 'switch', 'set'
    model VARCHAR(255) NOT NULL,
    executed_at TIMESTAMP DEFAULT NOW()
);
"""


# Chat commands for model switching
CHAT_COMMANDS = """
# User can change model in chat by saying:
- "use gpt-4o" 
- "switch to claude-3.5-sonnet"
- "set model to gemini-2.0-flash"
- "try the smartest model"
- "use the fastest model"

# These get parsed and applied to the request
"""

# Pattern matching for chat commands
MODEL_CHAT_PATTERNS = {
    # Explicit model names
    r"use\s+(gpt-[^\s]+)": "explicit",
    r"switch\s+to\s+([^\s]+)": "explicit", 
    r"set\s+model\s+to\s+([^\s]+)": "explicit",
    r"try\s+([^\s]+)": "explicit",
    
    # Capability levels
    r"use\s+the\s+fastest": "fastest",
    r"use\s+the\s+fast": "fast",
    r"use\s+the\s+balanced": "balanced",
    r"use\s+the\s+smart": "smart",
    r"use\s+the\s+smartest": "smartest",
    
    # Shortcuts
    r"fastest": "fastest",
    r"fast\b": "fast",
    r"balanced": "balanced",
    r"smart\b": "smart",
    r"smartest": "smartest",
}


def parse_chat_model_command(message: str) -> dict:
    """
    Parse a user's chat message for model change commands.
    
    Returns: {type: 'explicit'|'level'|'slider', value: str}
    """
    import re
    
    message_lower = message.lower().strip()
    
    # Check explicit model patterns
    for pattern, result_type in MODEL_CHAT_PATTERNS.items():
        match = re.search(pattern, message_lower)
        if match:
            if result_type == "explicit":
                return {"type": "explicit", "value": match.group(1).strip()}
            else:
                return {"type": "level", "value": result_type}
    
    return None  # No model command detected
