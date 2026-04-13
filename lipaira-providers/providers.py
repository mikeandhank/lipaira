"""
Additional LLM Provider Integrations for Lipaira
================================================
Direct provider clients beyond the core set: Mistral, Cohere, DeepSeek, Qwen,
Microsoft (Azure), Nvidia NIM, Perplexity, ZeroOne (01-ai), Minimax, and Together.
Each provider implements BaseProvider and provides pricing, API key management,
and chat completion methods.
"""
import os
import requests
import time
from typing import List, Dict
from lipaira_providers.models import BaseProvider, LLMResponse, Message, Provider


class MistralProvider(BaseProvider):
    """Mistral AI integration"""
    
    def get_base_url(self) -> str:
        return "https://api.mistral.ai/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("MISTRAL_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "mistral-large": {"input": 2.00, "output": 6.00},
            "mistral-medium": {"input": 1.40, "output": 4.60},
            "mistral-small": {"input": 0.60, "output": 2.00},
            "mistral-7b": {"input": 0.20, "output": 0.20},
        }
    
    def chat(self, messages: List[Message], model: str = "mistral-small", **kwargs) -> LLMResponse:
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="Mistral API key not configured")
        
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
                return LLMResponse(success=False, error=f"Mistral error: {response.status_code}")
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="mistral",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=self.calculate_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class CohereProvider(BaseProvider):
    """Cohere AI integration"""
    
    def get_base_url(self) -> str:
        return "https://api.cohere.ai/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("COHERE_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "command-r-plus": {"input": 3.00, "output": 15.00},
            "command-r": {"input": 0.50, "output": 1.50},
            "command": {"input": 0.30, "output": 0.60},
        }
    
    def chat(self, messages: List[Message], model: str = "command-r", **kwargs) -> LLMResponse:
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="Cohere API key not configured")
        
        try:
            # Cohere uses 'message' instead of 'messages'
            prompt = "\n".join([f"{m.role}: {m.content}" for m in messages])
            
            response = requests.post(
                f"{self.base_url}/generate",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "prompt": prompt,
                    "max_tokens": kwargs.get("max_tokens", 4000),
                    "temperature": kwargs.get("temperature", 0.7),
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(success=False, error=f"Cohere error: {response.status_code}")
            
            data = response.json()
            
            return LLMResponse(
                success=True,
                content=data.get("generations", [{}])[0].get("text", ""),
                model=model,
                provider="cohere",
                input_tokens=data.get("prompt_tokens", 0),
                output_tokens=data.get("tokens_generated", 0),
                total_tokens=data.get("prompt_tokens", 0) + data.get("tokens_generated", 0),
                cost=self.calculate_cost(data.get("prompt_tokens", 0), data.get("tokens_generated", 0)),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class DeepSeekProvider(BaseProvider):
    """DeepSeek integration"""
    
    def get_base_url(self) -> str:
        return "https://api.deepseek.com/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("DEEPSEEK_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "deepseek-chat": {"input": 0.14, "output": 0.28},
            "deepseek-coder": {"input": 0.14, "output": 0.28},
        }
    
    def chat(self, messages: List[Message], model: str = "deepseek-chat", **kwargs) -> LLMResponse:
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="DeepSeek API key not configured")
        
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
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(success=False, error=f"DeepSeek error: {response.status_code}")
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="deepseek",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=self.calculate_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class QwenProvider(BaseProvider):
    """Qwen (Alibaba) integration via DashScope"""
    
    def get_base_url(self) -> str:
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("DASHSCOPE_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "qwen-2-72b": {"input": 0.90, "output": 1.00},
            "qwen-2-7b": {"input": 0.20, "output": 0.20},
            "qwen-plus": {"input": 2.00, "output": 6.00},
            "qwen-turbo": {"input": 0.40, "output": 1.20},
        }
    
    def chat(self, messages: List[Message], model: str = "qwen-2-7b", **kwargs) -> LLMResponse:
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="DashScope API key not configured")
        
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
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(success=False, error=f"Qwen error: {response.status_code}")
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="qwen",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=self.calculate_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class MicrosoftProvider(BaseProvider):
    """Microsoft Azure OpenAI integration"""
    
    def get_base_url(self) -> str:
        return os.environ.get("AZURE_OPENAI_ENDPOINT", "https://api.openai.com/v1")
    
    def _get_api_key(self) -> str:
        return os.environ.get("AZURE_OPENAI_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "wizardlm-2-8x22b": {"input": 1.20, "output": 1.20},
            "wizardlm-2-7b": {"input": 0.20, "output": 0.20},
        }
    
    def chat(self, messages: List[Message], model: str = "wizardlm-2-7b", **kwargs) -> LLMResponse:
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="Azure API key not configured")
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "api-key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                    "max_tokens": kwargs.get("max_tokens", 4000),
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(success=False, error=f"Azure error: {response.status_code}")
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="microsoft",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=self.calculate_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class PerplexityProvider(BaseProvider):
    """Perplexity AI integration"""
    
    def get_base_url(self) -> str:
        return "https://api.perplexity.ai"
    
    def _get_api_key(self) -> str:
        return os.environ.get("PERPLEXITY_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "pplx-7b-online": {"input": 10.00, "output": 10.00},
            "pplx-70b-online": {"input": 10.00, "output": 10.00},
            "llama-3-sonar-small-online": {"input": 1.00, "output": 1.00},
            "llama-3-sonar-large-online": {"input": 3.00, "output": 3.00},
        }
    
    def chat(self, messages: List[Message], model: str = "llama-3-sonar-small-online", **kwargs) -> LLMResponse:
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="Perplexity API key not configured")
        
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
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(success=False, error=f"Perplexity error: {response.status_code}")
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="perplexity",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=self.calculate_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class ZeroOneProvider(BaseProvider):
    """01.AI (Yi) integration"""
    
    def get_base_url(self) -> str:
        return "https://api.01.ai/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("ZEROONE_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "yi-large": {"input": 3.00, "output": 15.00},
            "yi-medium": {"input": 1.00, "output": 3.00},
            "yi-spark": {"input": 0.20, "output": 0.40},
        }
    
    def chat(self, messages: List[Message], model: str = "yi-medium", **kwargs) -> LLMResponse:
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="01.AI API key not configured")
        
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
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(success=False, error=f"01.AI error: {response.status_code}")
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="01-ai",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=self.calculate_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class MinimaxProvider(BaseProvider):
    """MiniMax integration"""
    
    def get_base_url(self) -> str:
        return "https://api.minimax.chat/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("MINIMAX_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "MiniMax-M2.7": {"input": 0.30, "output": 1.20},
            "MiniMax-M2.7-highspeed": {"input": 0.60, "output": 2.40},
            "MiniMax-M2.5": {"input": 0.30, "output": 1.20},
            "MiniMax-M2.5-highspeed": {"input": 0.60, "output": 2.40},
            "MiniMax-M2.1": {"input": 0.30, "output": 1.20},
        }
    
    def chat(self, messages: List[Message], model: str = "MiniMax-M2.5", **kwargs) -> LLMResponse:
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="MiniMax API key not configured")
        
        try:
            response = requests.post(
                f"{self.base_url}/text/chatcompletion_v2",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                    "max_tokens": kwargs.get("max_tokens", 4000),
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(success=False, error=f"MiniMax error: {response.status_code}")
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="minimax",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=self.calculate_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class TogetherProvider(BaseProvider):
    """Together AI - hosts Meta and other open models"""
    
    def get_base_url(self) -> str:
        return "https://api.together.xyz/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("TOGETHER_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "meta-llama/Llama-3.1-70B-Instruct": {"input": 0.88, "output": 0.88},
            "meta-llama/Llama-3.1-8B-Instruct": {"input": 0.22, "output": 0.22},
            "meta-llama/Llama-3-70B": {"input": 0.80, "output": 0.80},
            "meta-llama/Llama-3-8B": {"input": 0.20, "output": 0.20},
        }
    
    def chat(self, messages: List[Message], model: str = "meta-llama/Llama-3.1-8B-Instruct", **kwargs) -> LLMResponse:
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="Together API key not configured")
        
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
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(success=False, error=f"Together error: {response.status_code}")
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="together",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=self.calculate_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))


class NvidiaProvider(BaseProvider):
    """Nvidia NIM integration"""
    
    def get_base_url(self) -> str:
        return "https://integrate.api.nvidia.com/v1"
    
    def _get_api_key(self) -> str:
        return os.environ.get("NVIDIA_API_KEY", "")
    
    def get_pricing(self) -> Dict[str, float]:
        return {
            "nemotron-70b": {"input": 0.40, "output": 0.40},
            "nvidia/llama-3.1-nemotron-70b-instruct": {"input": 0.40, "output": 0.40},
        }
    
    def chat(self, messages: List[Message], model: str = "nemotron-70b", **kwargs) -> LLMResponse:
        start = time.time()
        
        if not self.api_key:
            return LLMResponse(success=False, error="Nvidia API key not configured")
        
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
                },
                timeout=60
            )
            
            if response.status_code != 200:
                return LLMResponse(success=False, error=f"Nvidia error: {response.status_code}")
            
            data = response.json()
            usage = data.get("usage", {})
            
            return LLMResponse(
                success=True,
                content=data["choices"][0]["message"]["content"],
                model=model,
                provider="nvidia",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=self.calculate_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
                latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))
