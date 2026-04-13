"""
LLM Provider Router for Lipaira
================================
Unified interface for multiple LLM providers. Replaces OpenRouter with direct
connections. Provides LipairaRouter class with chat(), chat_with_function_call(),
and embedding() methods. Routes to the correct provider based on model name.
"""
import os
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from enum import Enum
import logging

# Import all providers
from lipaira_providers.providers import (
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    OllamaProvider,
    MistralProvider,
    CohereProvider,
    DeepSeekProvider,
    QwenProvider,
    MicrosoftProvider,
    PerplexityProvider,
    ZeroOneProvider,
    MinimaxProvider,
    TogetherProvider,
    NvidiaProvider,
)

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
    TOGETHER = "together"  # For Meta models
    OPENROUTER = "openrouter"  # All models route through OpenRouter


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


class OpenAIProvider(BaseProvider):
    """OpenAI API integration"""
    
    def get_base_url(self) -> str:
        return "https://api.openai.com/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("OPENAI_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4-turbo": {"input": 5.00, "output": 15.00},
            "gpt-4": {"input": 15.00, "output": 60.00},
            "gpt-3.5-turbo": {"input": 0.50, "output": 2.00},
        }
    
    def chat(self, messages: List[Message], model: str = "gpt-4o", **kwargs) -> LLMResponse:
        import time
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="OpenAI API key not configured")
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                    "max_tokens": kwargs.get("max_tokens", 4000),
                    "temperature": kwargs.get("temperature", 0.7),
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    success=False,
                    error=f"OpenAI error: {response.status_code} - {response.text}"
                )
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="openai",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=self.calculate_cost(
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0)
                ),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API integration"""
    
    def get_base_url(self) -> str:
        return "https://api.anthropic.com/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("ANTHROPIC_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
            "claude-3-opus": {"input": 15.00, "output": 75.00},
            "claude-3-sonnet": {"input": 3.00, "output": 15.00},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
        }
    
    def chat(self, messages: List[Message], model: str = "claude-3.5-sonnet", **kwargs) -> LLMResponse:
        import time
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="Anthropic API key not configured")
        
        # Convert messages to Anthropic format
        anthropic_messages = []
        system_prompt = ""
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                anthropic_messages.append({"role": m.role, "content": m.content})
        
        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": anthropic_messages,
                    "max_tokens": kwargs.get("max_tokens", 4000),
                    "system": system_prompt if system_prompt else None,
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    success=False,
                    error=f"Anthropic error: {response.status_code} - {response.text}"
                )
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["content"][0]["text"],
                model=model,
                provider="anthropic",
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                cost=self.calculate_cost(
                    usage.get("input_tokens", 0),
                    usage.get("output_tokens", 0)
                ),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class GoogleProvider(BaseProvider):
    """Google Gemini API integration"""
    
    def get_base_url(self) -> str:
        return "https://generativelanguage.googleapis.com/v1beta"
    
    def _get_api_key(self) -> str:
        return os.environ.get("GOOGLE_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
            "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
            "gemini-2.0-flash-lite": {"input": 0.07, "output": 0.30},
        }
    
    def chat(self, messages: List[Message], model: str = "gemini-2.0-flash", **kwargs) -> LLMResponse:
        import time
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="Google API key not configured")
        
        try:
            # Convert messages to Gemini format
            contents = []
            for m in messages:
                if m.role != "system":
                    contents.append({"role": m.role, "parts": [{"text": m.content}]})
            
            response = requests.post(
                f"{self.base_url}/models/{model}:generateContent",
                params={"key": self.api_key},
                json={
                    "contents": contents,
                    "generationConfig": {
                        "maxOutputTokens": kwargs.get("max_tokens", 4000),
                        "temperature": kwargs.get("temperature", 0.7),
                    }
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    success=False,
                    error=f"Google error: {response.status_code} - {response.text}"
                )
            
            data = response.json()
            
            return LLMResponse(
                success=True,
                content=data["candidates"][0]["content"]["parts"][0]["text"],
                model=model,
                provider="google",
                # Note: Google doesn't return token counts in standard response
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0.0,  # Would need to calculate from usage quota
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class OllamaProvider(BaseProvider):
    """Ollama local models - free"""
    
    def get_base_url(self) -> str:
        return os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/v1"
    
    def _get_api_key(self) -> str:
        return ""  # No API key needed for local
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "llama3": {"input": 0, "output": 0},
            "llama3.1": {"input": 0, "output": 0},
            "codellama": {"input": 0, "output": 0},
            "mistral": {"input": 0, "output": 0},
            "phi3": {"input": 0, "output": 0},
        }
    
    def chat(self, messages: List[Message], model: str = "llama3", **kwargs) -> LLMResponse:
        import time
        start = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                    "max_tokens": kwargs.get("max_tokens", 4000),
                },
                timeout=120
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    success=False,
                    error=f"Ollama error: {response.status_code}"
                )
            
            data = response.json()
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="ollama",
                cost=0.0,
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


# Provider registry
PROVIDERS = {
    Provider.OPENAI: OpenAIProvider,
    Provider.ANTHROPIC: AnthropicProvider,
    Provider.GOOGLE: GoogleProvider,
    Provider.OLLAMA: OllamaProvider,
    Provider.MISTRAL: MistralProvider,
    Provider.CHERE: CohereProvider,
    Provider.DEEPSEEK: DeepSeekProvider,
    Provider.QWEN: QwenProvider,
    Provider.MICROSOFT: MicrosoftProvider,
    Provider.NVIDIA: NvidiaProvider,
    Provider.PERPLEXITY: PerplexityProvider,
    Provider.ZEROONE: ZeroOneProvider,
    Provider.MINIMAX: MinimaxProvider,
    Provider.TOGETHER: TogetherProvider,
    Provider.OPENROUTER: OpenRouterProvider,  # Routes all models through OpenRouter
}


class LipairaRouter:
    """
    Unified LLM router - replaces OpenRouter
    Routes to appropriate provider based on model
    """
    
    # Model to provider mapping - ALL route through OpenRouter
    MODEL_MAP = {
        # All models now route through OpenRouter
        "claude-": Provider.OPENROUTER,
        "gpt-": Provider.OPENROUTER,
        "gemini-": Provider.OPENROUTER,
        "llama-": Provider.OPENROUTER,
        "mistral-": Provider.OPENROUTER,
        "command-": Provider.OPENROUTER,
        "deepseek-": Provider.OPENROUTER,
        "qwen-": Provider.OPENROUTER,
        "wizardlm": Provider.OPENROUTER,
        "nemotron": Provider.OPENROUTER,
        "pplx-": Provider.OPENROUTER,
        "yi-": Provider.OPENROUTER,
        "meta-": Provider.OPENROUTER,
        
        # Ollama (local) - still direct
        "ollama/": Provider.OLLAMA,
    }
    
    def __init__(self):
        self.providers: Dict[Provider, BaseProvider] = {}
        self._init_providers()
    
    def _init_providers(self):
        """Initialize all available providers"""
        for provider_type, provider_class in PROVIDERS.items():
            try:
                self.providers[provider_type] = provider_class()
                logger.info(f"Initialized provider: {provider_type.value}")
            except Exception as e:
                logger.warning(f"Failed to initialize {provider_type.value}: {e}")
    
    def get_provider(self, model: str) -> Optional[BaseProvider]:
        """Get the appropriate provider for a model"""
        # Check if model starts with any provider prefix (prefix matching)
        for provider_type in Provider:
            if model.startswith(provider_type.value):
                return self.providers.get(provider_type)
        
        # Check model map for exact or partial matches
        for model_pattern, provider_type in self.MODEL_MAP.items():
            if model_pattern in model:
                return self.providers.get(provider_type)
        
        return None
    
    def chat(self, messages: List[Message], model: str, **kwargs) -> LLMResponse:
        """Route chat request to appropriate provider"""
        provider = self.get_provider(model)
        
        if not provider:
            return LLMResponse(
                success=False,
                error=f"No provider found for model: {model}"
            )
        
        return provider.chat(messages, model, **kwargs)
    
    def get_available_models(self) -> List[Dict]:
        """Get list of all available models"""
        models = []
        for provider_type, provider in self.providers.items():
            if provider.api_key:  # Only include configured providers
                pricing = provider.get_pricing()
                for model_name in pricing.keys():
                    models.append({
                        "id": model_name,
                        "provider": provider_type.value,
                        "input_cost": pricing[model_name]["input"],
                        "output_cost": pricing[model_name]["output"],
                    })
        return models


# Usage example
if __name__ == "__main__":
    router = LipairaRouter()
    
    # Test with a message
    messages = [Message(role="user", content="Hello!")]
    
    # Try OpenAI if available
    response = router.chat(messages, "gpt-4o-mini")
    print(f"Response: {response.content}")
    print(f"Cost: ${response.cost:.4f}")
    print(f"Provider: {response.provider}")


# ============================================================================
# OPENROUTER PROVIDER - All models route through OpenRouter
# ============================================================================

class OpenRouterProvider(BaseProvider):
    """OpenRouter API integration - routes to 100+ models"""
    
    MODEL_MAP = {
        "claude-haiku-4-5": "anthropic/claude-haiku-4-5-20251001",
        "claude-sonnet-4-5": "anthropic/claude-sonnet-4-5-20251001",
        "claude-opus-4-5": "anthropic/claude-opus-4-5-20251001",
        "claude-3.5-sonnet": "anthropic/claude-sonnet-4-20240219",
        "claude-3-haiku": "anthropic/claude-3-haiku-20240307",
        "gpt-4o": "openai/gpt-4o-2024-08-06",
        "gpt-4o-mini": "openai/gpt-4o-mini-2024-07-18",
        "gemini-2.0-flash": "google/gemini-2.0-flash-exp",
        "gemini-1.5-flash": "google/gemini-1.5-flash-8b-exp",
    }
    
    # Our pricing (OR cost * 1.30 markup)
    PRICING = {
        "claude-haiku-4-5": {"input": 1.04, "output": 5.20},
        "claude-sonnet-4-5": {"input": 3.90, "output": 19.50},
        "claude-opus-4-5": {"input": 19.50, "output": 97.50},
        "gpt-4o": {"input": 3.25, "output": 13.00},
        "gpt-4o-mini": {"input": 0.20, "output": 0.78},
        "gemini-2.0-flash": {"input": 0.13, "output": 0.52},
    }
    
    def get_base_url(self) -> str:
        return "https://openrouter.ai/api/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("OPENROUTER_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return self.PRICING
    
    def _get_openrouter_model(self, model: str) -> str:
        return self.MODEL_MAP.get(model, model)
    
    def chat(self, messages: List[Message], model: str = "claude-haiku-4-5", **kwargs) -> LLMResponse:
        import time
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="OpenRouter API key not configured")
        
        or_model = self._get_openrouter_model(model)
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://lipaira.ai",
                    "X-Title": "Lipaira"
                },
                json={
                    "model": or_model,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                    "max_tokens": kwargs.get("max_tokens", 4000),
                    "temperature": kwargs.get("temperature", 0.7),
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    success=False,
                    error=f"OpenRouter error: {response.status_code}"
                )
            
            data = response.json()
            usage = data.get("usage", {})
            input_tok = usage.get("prompt_tokens", 0)
            output_tok = usage.get("completion_tokens", 0)
            pricing = self.PRICING.get(model, {"input": 1.0, "output": 5.0})
            our_cost = (
                (input_tok / 1_000_000 * pricing["input"]) +
                (output_tok / 1_000_000 * pricing["output"])
            )
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="openrouter",
                input_tokens=input_tok,
                output_tokens=output_tok,
                total_tokens=usage.get("total_tokens", 0),
                cost=our_cost,
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))
