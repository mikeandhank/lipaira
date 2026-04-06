"""
Task-Based Model Selection
==========================
Automatically select best model based on task type detected from message
"""

from enum import Enum
from typing import List, Dict, Optional
import re


class TaskType(Enum):
    """Categories of tasks"""
    GENERAL = "general"           # Default chat
    CODING = "coding"           # Code generation, debugging
    REASONING = "reasoning"     # Math, logic
    VISION = "vision"           # Image analysis
    FAST = "fast"               # Quick simple tasks
    LONG_CONTEXT = "long_context" # Documents
    CREATIVE = "creative"       # Writing, storytelling
    TRANSLATION = "translation"  # Language translation
    FUNCTION_CALLING = "function_calling"  # Tool use


# Task detection keywords/patterns
TASK_PATTERNS = {
    TaskType.CODING: [
        r'\b(code|function|class|def|import|debug|bug|fix|script|api|algorithm)\b',
        r'\b(write.*code|generate.*code|create.*function|build.*app)\b',
        r'\b(python|javascript|typescript|java|go|rust|c\+\+)\b',
        r'\b(debug|error|exception|stack.*trace)\b',
        r'\b(sql|query|database|schema)\b',
        r'\b(regex|test|unit.*test)\b',
    ],
    TaskType.REASONING: [
        r'\b(proof|prove|calculate|compute|solve)\b',
        r'\b(math|equation|formula|algebra|calculus)\b',
        r'\b(logic|puzzle|reason|analyze.*this)\b',
        r'\b(why.*because|explain.*reason)\b',
    ],
    TaskType.VISION: [
        r'\b(image|photo|picture|visual|see|look.*at)\b',
        r'\b(describe.*image|what.*in.*image|analyze.*image)\b',
        r'\b(ocr|extract.*text.*from)\b',
        r'\b(chart|graph|diagram|screenshot)\b',
    ],
    TaskType.FAST: [
        r'\b(quick|simple|short|fast)\b',
        r'\b(what.*is|who.*is|when.*did|where.*is)\b',
        r'\b(one.*word|yes|no|ok|thanks)\b',
    ],
    TaskType.LONG_CONTEXT: [
        r'\b(document|article|paper|book|report)\b',
        r'\b(summarize|summary|extract)\b',
        r'\b(long.*text|entire|full)\b',
        r'\b(pdf|docx|word.*doc)\b',
    ],
    TaskType.CREATIVE: [
        r'\b(write.*story|storytelling|creative)\b',
        r'\b(marketing|blog|article|post)\b',
        r'\b(joke|funny|humor)\b',
        r'\b(poem|lyrics|script)\b',
    ],
    TaskType.TRANSLATION: [
        r'\b(translate|translation)\b',
        r'\b(convert.*to|from.*to)\b',
        r'\b(spanish|french|german|chinese|japanese|korean)\b',
    ],
    TaskType.FUNCTION_CALLING: [
        r'\b(use.*tool|call.*function|execute.*tool)\b',
        r'\b(search.*web|get.*info|fetch.*data)\b',
    ],
}


# Best models for each task type
# Best models for each task type at each slider level
# Best models for each task type at each slider level
# Now includes Mistral, Cohere, DeepSeek, Qwen, etc.
TASK_MODEL_PREFERENCES = {
    TaskType.CODING: {
        1: "gpt-4o-mini",
        2: "mistral-small",      # Mistral - cheap coding
        3: "claude-3.5-sonnet",
        4: "deepseek-coder",     # DeepSeek - specialized for code
        5: "claude-3-opus",
    },
    TaskType.REASONING: {
        1: "gpt-4o-mini",
        2: "qwen-2-7b",          # Qwen - good reasoning cheap
        3: "claude-3.5-sonnet",
        4: "gpt-4",
        5: "claude-3-opus",
    },
    TaskType.VISION: {
        1: "gpt-4o-mini",
        2: "gpt-4o",
        3: "gemini-2.0-flash",   # Google - good vision
        4: "claude-3.5-sonnet",
        5: "gpt-4o",
    },
    TaskType.FAST: {
        1: "gpt-4o-mini",
        2: "mistral-small",
        3: "gpt-4o",
        4: "claude-3.5-sonnet",
        5: "claude-3-opus",
    },
    TaskType.LONG_CONTEXT: {
        1: "gpt-4o-mini",
        2: "gpt-4-turbo",
        3: "qwen-2-72b",         # Qwen - 128k context cheap
        4: "claude-3-opus",
        5: "claude-3-opus",
    },
    TaskType.CREATIVE: {
        1: "gpt-4o-mini",
        2: "mistral-medium",
        3: "claude-3.5-sonnet",
        4: "gpt-4",
        5: "claude-3-opus",
    },
    TaskType.TRANSLATION: {
        1: "gpt-4o-mini",
        2: "nllb-200",           # Meta NLLB - dedicated translation
        3: "claude-3.5-sonnet",
        4: "gpt-4",
        5: "claude-3-opus",
    },
    TaskType.FUNCTION_CALLING: {
        1: "gpt-4o-mini",
        2: "mistral-small",
        3: "gpt-4o",
        4: "gpt-4-turbo",
        5: "claude-3-opus",
    },
    TaskType.GENERAL: {
        1: "gpt-4o-mini",
        2: "mistral-medium",     # Mix it up
        3: "claude-3.5-sonnet",
        4: "gpt-4",
        5: "claude-3-opus",
    },
}


def detect_task_type(message: str) -> TaskType:
    """
    Detect the task type from the user's message.
    
    Returns TaskType based on keywords/patterns found.
    """
    message_lower = message.lower()
    
    # Score each task type
    scores = {task: 0 for task in TaskType}
    
    for task, patterns in TASK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                scores[task] += 1
    
    # Get highest scoring task
    max_score = max(scores.values())
    
    if max_score == 0:
        return TaskType.GENERAL
    
    for task, score in scores.items():
        if score == max_score:
            return task
    
    return TaskType.GENERAL


def get_model_for_task(
    task: TaskType, 
    capability_level: int = 5,
    preferred_provider: str = None
) -> str:
    """
    Get the best model for a task type at the given capability level.
    
    Args:
        task: The detected task type
        capability_level: User's slider level (1-5)
        preferred_provider: Skip this provider if API key missing
    
    Returns:
        Model name to use
    """
    model = TASK_MODEL_PREFERENCES[task].get(capability_level, "gpt-4o-mini")
    
    # Could add logic here to check if provider is available
    # and fall back to another model if needed
    
    return model


def get_task_info(task: TaskType) -> Dict:
    """Get display info for a task type"""
    info = {
        TaskType.GENERAL: {"icon": "💬", "name": "General Chat", "description": "Conversation and Q&A"},
        TaskType.CODING: {"icon": "💻", "name": "Coding", "description": "Code generation and debugging"},
        TaskType.REASONING: {"icon": "🧠", "name": "Reasoning", "description": "Math, logic, analysis"},
        TaskType.VISION: {"icon": "👁️", "name": "Vision", "description": "Image analysis and OCR"},
        TaskType.FAST: {"icon": "⚡", "name": "Fast", "description": "Quick, simple responses"},
        TaskType.LONG_CONTEXT: {"icon": "📄", "name": "Long Context", "description": "Documents and large texts"},
        TaskType.CREATIVE: {"icon": "🎨", "name": "Creative", "description": "Writing and storytelling"},
        TaskType.TRANSLATION: {"icon": "🌍", "name": "Translation", "description": "Language translation"},
        TaskType.FUNCTION_CALLING: {"icon": "🔧", "name": "Tools", "description": "Using functions and tools"},
    }
    return info.get(task, info[TaskType.GENERAL])


# Integration with model preference system
def resolve_model_with_task(
    message: str = None,
    user_id: str = None,
    explicit_model: str = None,
    capability_level: int = 5
) -> Dict:
    """
    Full model resolution including task detection.
    
    Priority:
    1. explicit_model - user specified in request
    2. Task detection - from message content
    3. User preference slider
    """
    from .model_preference import ModelPreferenceManager
    
    # 1. Explicit model wins
    if explicit_model:
        return {
            "model": explicit_model,
            "source": "explicit",
            "task": None
        }
    
    # 2. Detect task from message
    task = TaskType.GENERAL
    if message:
        task = detect_task_type(message)
    
    # 3. Get model for task + capability level
    model = get_model_for_task(task, capability_level)
    
    return {
        "model": model,
        "source": f"task_{task.value}",
        "task": task.value,
        "task_info": get_task_info(task)
    }
