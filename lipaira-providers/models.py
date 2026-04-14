"""
Shared models for Lipaira providers
===================================
Base classes and data structures used across all provider modules
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import os
import logging

logger = logging.getLogger(__name__)


class Provider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    MISTRAL = "mistral"
    COHERE = "cohere"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    MICROSOFT = "microsoft"
    NVIDIA = "nvidia"
    PERPLEXITY = "perplexity"
    ZEROONE = "01-ai"
    MINIMAX = "minimax"
    OLLAMA = "ollama"
    TOGETHER = "together"


@dataclass
class LLMResponse:
    success: bool
    content: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    error: Optional[str] = None
    latency_ms: int = 0


@dataclass
class Message:
    role: str
    content: str


class BaseProvider(ABC):
    """Base class for all LLM providers"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or self._get_api_key()
        self.base_url = self.get_base_url()
        self.pricing = self.get_pricing()
    
    @abstractmethod
    def get_base_url(self) -> str:
        pass
    
    @abstractmethod
    def _get_api_key(self) -> str:
        pass
    
    @abstractmethod
    def get_pricing(self) -> Dict[str, float]:
        """Returns {input_cost_per_1m, output_cost_per_1m}"""
        pass
    
    @abstractmethod
    def chat(self, messages: List[Message], model: str, **kwargs) -> LLMResponse:
        pass
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens / 1_000_000 * self.pricing.get('input', 0) + 
                output_tokens / 1_000_000 * self.pricing.get('output', 0))