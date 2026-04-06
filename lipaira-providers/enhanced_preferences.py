"""
Enhanced Model Preferences - Per Task Type
=========================================
Users can set preferred model for EACH task type independently
"""

from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import json


class TaskType(Enum):
    """Categories of tasks"""
    GENERAL = "general"
    CODING = "coding"
    REASONING = "reasoning"
    VISION = "vision"
    FAST = "fast"
    LONG_CONTEXT = "long_context"
    CREATIVE = "creative"
    TRANSLATION = "translation"
    FUNCTION_CALLING = "function_calling"


# Default models per task type AT EACH SLIDER LEVEL
# Slider 1 = cheapest, 5 = most expensive (opus)
# Now includes Mistral, Cohere, DeepSeek, Qwen, Google, Meta
TASK_DEFAULT_BY_LEVEL = {
    TaskType.GENERAL: {
        1: {"model": "gpt-4o-mini", "cost": "$0.15-0.60"},
        2: {"model": "mistral-small", "cost": "$0.60-2.00"},
        3: {"model": "claude-3.5-sonnet", "cost": "$3-15"},
        4: {"model": "gpt-4", "cost": "$15-60"},
        5: {"model": "claude-3-opus", "cost": "$15-75"},
    },
    TaskType.CODING: {
        1: {"model": "gpt-4o-mini", "cost": "$0.15-0.60"},
        2: {"model": "mistral-small", "cost": "$0.60-2.00"},
        3: {"model": "deepseek-coder", "cost": "$0.14-0.28"},
        4: {"model": "claude-3.5-sonnet", "cost": "$3-15"},
        5: {"model": "claude-3-opus", "cost": "$15-75"},
    },
    TaskType.REASONING: {
        1: {"model": "gpt-4o-mini", "cost": "$0.15-0.60"},
        2: {"model": "qwen-2-7b", "cost": "$0.20-0.20"},
        3: {"model": "claude-3.5-sonnet", "cost": "$3-15"},
        4: {"model": "gpt-4", "cost": "$15-60"},
        5: {"model": "claude-3-opus", "cost": "$15-75"},
    },
    TaskType.VISION: {
        1: {"model": "gpt-4o-mini", "cost": "$0.15-0.60"},
        2: {"model": "gemini-2.0-flash", "cost": "$0.10-0.40"},
        3: {"model": "gemini-2.5-pro", "cost": "$1.25-10"},
        4: {"model": "claude-3.5-sonnet", "cost": "$3-15"},
        5: {"model": "gpt-4o", "cost": "$2.50-10"},
    },
    TaskType.FAST: {
        1: {"model": "gpt-4o-mini", "cost": "$0.15-0.60"},
        2: {"model": "mistral-small", "cost": "$0.60-2.00"},
        3: {"model": "gpt-4o", "cost": "$2.50-10"},
        4: {"model": "gemini-2.0-flash", "cost": "$0.10-0.40"},
        5: {"model": "claude-3.5-sonnet", "cost": "$3-15"},
    },
    TaskType.LONG_CONTEXT: {
        1: {"model": "gpt-4o-mini", "cost": "$0.15-0.60"},
        2: {"model": "qwen-2-72b", "cost": "$0.90-1.00"},
        3: {"model": "gpt-4-turbo", "cost": "$5-15"},
        4: {"model": "claude-3-opus", "cost": "$15-75"},
        5: {"model": "claude-3-opus", "cost": "$15-75"},
    },
    TaskType.CREATIVE: {
        1: {"model": "gpt-4o-mini", "cost": "$0.15-0.60"},
        2: {"model": "mistral-medium", "cost": "$1.40-4.60"},
        3: {"model": "claude-3.5-sonnet", "cost": "$3-15"},
        4: {"model": "gpt-4", "cost": "$15-60"},
        5: {"model": "claude-3-opus", "cost": "$15-75"},
    },
    TaskType.TRANSLATION: {
        1: {"model": "gpt-4o-mini", "cost": "$0.15-0.60"},
        2: {"model": "nllb-200", "cost": "free"},  # Meta NLLB
        3: {"model": "claude-3.5-sonnet", "cost": "$3-15"},
        4: {"model": "gpt-4", "cost": "$15-60"},
        5: {"model": "claude-3-opus", "cost": "$15-75"},
    },
    TaskType.FUNCTION_CALLING: {
        1: {"model": "gpt-4o-mini", "cost": "$0.15-0.60"},
        2: {"model": "mistral-small", "cost": "$0.60-2.00"},
        3: {"model": "gpt-4o", "cost": "$2.50-10"},
        4: {"model": "gpt-4-turbo", "cost": "$5-15"},
        5: {"model": "claude-3-opus", "cost": "$15-75"},
    },
}


# Default models per task type (level 5 - smartest)
DEFAULT_TASK_MODELS = {task: TASK_DEFAULT_BY_LEVEL[task][5]["model"] for task in TaskType}


# Display names and icons
TASK_INFO = {
    TaskType.GENERAL: {"icon": "💬", "name": "General Chat", "description": "Conversation and Q&A"},
    TaskType.CODING: {"icon": "💻", "name": "Coding", "description": "Code generation, debugging"},
    TaskType.REASONING: {"icon": "🧠", "name": "Reasoning", "description": "Math, logic, analysis"},
    TaskType.VISION: {"icon": "👁️", "name": "Vision", "description": "Image analysis, OCR"},
    TaskType.FAST: {"icon": "⚡", "name": "Fast", "description": "Quick, simple responses"},
    TaskType.LONG_CONTEXT: {"icon": "📄", "name": "Long Context", "description": "Documents, large texts"},
    TaskType.CREATIVE: {"icon": "🎨", "name": "Creative", "description": "Writing, storytelling"},
    TaskType.TRANSLATION: {"icon": "🌍", "name": "Translation", "description": "Language translation"},
    TaskType.FUNCTION_CALLING: {"icon": "🔧", "name": "Tools", "description": "Using functions, API calls"},
}


SLIDER_LABELS = {
    1: "🚀 Fastest",
    2: "⚡ Fast",
    3: "⚖️ Balanced",
    4: "🧠 Smart",
    5: "💎 Smartest",
}


# Available models per task type
AVAILABLE_MODELS = {
    TaskType.GENERAL: [
        {"id": "claude-3-opus", "name": "Claude 3 Opus", "provider": "Anthropic"},
        {"id": "gpt-4", "name": "GPT-4", "provider": "OpenAI"},
        {"id": "claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
        {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "Google"},
    ],
    TaskType.CODING: [
        {"id": "claude-3-opus", "name": "Claude 3 Opus", "provider": "Anthropic"},
        {"id": "gpt-4", "name": "GPT-4", "provider": "OpenAI"},
        {"id": "deepseek-coder", "name": "DeepSeek Coder", "provider": "DeepSeek"},
        {"id": "claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
        {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
    ],
    TaskType.REASONING: [
        {"id": "claude-3-opus", "name": "Claude 3 Opus", "provider": "Anthropic"},
        {"id": "gpt-4", "name": "GPT-4", "provider": "OpenAI"},
        {"id": "claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
    ],
    TaskType.VISION: [
        {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
        {"id": "claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "Google"},
    ],
    TaskType.FAST: [
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
        {"id": "llama-3-8b", "name": "Llama 3 8B", "provider": "Together"},
        {"id": "ollama/llama3", "name": "Llama 3 (Local)", "provider": "Ollama"},
    ],
    TaskType.LONG_CONTEXT: [
        {"id": "claude-3-opus", "name": "Claude 3 Opus (200K)", "provider": "Anthropic"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo (128K)", "provider": "OpenAI"},
        {"id": "claude-3.5-sonnet", "name": "Claude 3.5 Sonnet (200K)", "provider": "Anthropic"},
    ],
    TaskType.CREATIVE: [
        {"id": "claude-3-opus", "name": "Claude 3 Opus", "provider": "Anthropic"},
        {"id": "gpt-4", "name": "GPT-4", "provider": "OpenAI"},
        {"id": "claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
    ],
    TaskType.TRANSLATION: [
        {"id": "claude-3-opus", "name": "Claude 3 Opus", "provider": "Anthropic"},
        {"id": "gpt-4", "name": "GPT-4", "provider": "OpenAI"},
        {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
    ],
    TaskType.FUNCTION_CALLING: [
        {"id": "claude-3-opus", "name": "Claude 3 Opus", "provider": "Anthropic"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "OpenAI"},
        {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
    ],
}


@dataclass
class TaskPreference:
    """User's preference for a specific task type"""
    task_type: TaskType
    model: str = None  # None = use default
    custom_model: str = None  # User's override
    
    @property
    def effective_model(self) -> str:
        return self.custom_model or self.model or DEFAULT_TASK_MODELS[self.task_type]


@dataclass
class UserPreferences:
    """All of a user's model preferences"""
    user_id: str
    task_preferences: Dict[TaskType, TaskPreference] = field(default_factory=dict)
    use_smart_defaults: bool = True  # Use AI-suggested defaults
    slider_level: int = 5  # Current slider level (1-5)
    
    def __post_init__(self):
        # Initialize defaults based on slider level
        self._apply_slider_defaults()
    
    def _apply_slider_defaults(self):
        """Apply slider level to set defaults for all tasks"""
        for task in TaskType:
            if task not in self.task_preferences:
                default = TASK_DEFAULT_BY_LEVEL[task].get(self.slider_level, TASK_DEFAULT_BY_LEVEL[task][5])
                self.task_preferences[task] = TaskPreference(
                    task_type=task,
                    model=default["model"]
                )
    
    def set_slider_level(self, level: int):
        """Update slider level and recalculate all defaults"""
        self.slider_level = max(1, min(5, level))
        # Clear custom models when slider changes
        for task in self.task_preferences:
            self.task_preferences[task].custom_model = None
        self._apply_slider_defaults()
    
    def get_model(self, task: TaskType) -> str:
        """Get effective model for a task"""
        pref = self.task_preferences.get(task, TaskPreference(task, DEFAULT_TASK_MODELS[task]))
        return pref.effective_model
    
    def set_model(self, task: TaskType, model: str):
        """Set custom model for a task"""
        if task not in self.task_preferences:
            self.task_preferences[task] = TaskPreference(task)
        self.task_preferences[task].custom_model = model
    
    def clear_model(self, task: TaskType):
        """Clear custom model, revert to default"""
        if task in self.task_preferences:
            self.task_preferences[task].custom_model = None
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "slider_level": self.slider_level,
            "slider_label": SLIDER_LABELS[self.slider_level],
            "use_smart_defaults": self.use_smart_defaults,
            "preferences": {
                task.value: {
                    "current": pref.effective_model,
                    "custom": pref.custom_model,
                    "default": pref.model,
                    "cost": TASK_DEFAULT_BY_LEVEL[task].get(self.slider_level, {}).get("cost", ""),
                    "info": TASK_INFO[task]
                }
                for task, pref in self.task_preferences.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "UserPreferences":
        prefs = cls(user_id=data.get("user_id", ""))
        prefs.use_smart_defaults = data.get("use_smart_defaults", True)
        
        for task_str, task_data in data.get("preferences", {}).items():
            try:
                task = TaskType(task_str)
                pref = TaskPreference(
                    task_type=task,
                    model=task_data.get("default"),
                    custom_model=task_data.get("custom")
                )
                prefs.task_preferences[task] = pref
            except ValueError:
                pass
        
        return prefs


# In-memory storage (would be database in production)
_USER_PREFS: Dict[str, UserPreferences] = {}


class PreferenceManager:
    """Manages user preferences"""
    
    @staticmethod
    def get_preferences(user_id: str) -> UserPreferences:
        """Get user's preferences, create if not exists"""
        if user_id not in _USER_PREFS:
            _USER_PREFS[user_id] = UserPreferences(user_id=user_id)
        return _USER_PREFS[user_id]
    
    @staticmethod
    def set_slider_level(user_id: str, level: int) -> bool:
        """Set slider level and update all task defaults"""
        prefs = PreferenceManager.get_preferences(user_id)
        prefs.set_slider_level(level)
        return True
    
    @staticmethod
    def set_task_model(user_id: str, task: TaskType, model: str) -> bool:
        """Set model for a specific task"""
        prefs = PreferenceManager.get_preferences(user_id)
        prefs.set_model(task, model)
        return True
    
    @staticmethod
    def clear_task_model(user_id: str, task: TaskType) -> bool:
        """Clear custom model for task"""
        prefs = PreferenceManager.get_preferences(user_id)
        prefs.clear_model(task)
        return True
    
    @staticmethod
    def get_model_for_task(user_id: str, task: TaskType) -> str:
        """Get the effective model for a task"""
        prefs = PreferenceManager.get_preferences(user_id)
        return prefs.get_model(task)
    
    @staticmethod
    def get_all_preferences(user_id: str) -> Dict:
        """Get all preferences as dict"""
        prefs = PreferenceManager.get_preferences(user_id)
        return prefs.to_dict()


# API Models
def get_preferences_schema():
    """Get the full preferences schema for UI"""
    return {
        "task_types": [
            {
                "type": task.value,
                "icon": info["icon"],
                "name": info["name"],
                "description": info["description"],
                "available_models": AVAILABLE_MODELS[task],
                "default_model": DEFAULT_TASK_MODELS[task]
            }
            for task, info in TASK_INFO.items()
        ]
    }
