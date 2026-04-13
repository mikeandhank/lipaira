"""
Lipaira Providers Package
=========================
Unified LLM provider routing for Lipaira. Replaces OpenRouter with direct
connections to OpenAI, Anthropic, Google, Mistral, Cohere, DeepSeek, Qwen,
Microsoft, Nvidia, Perplexity, ZeroOne, Minimax, Ollama, and Together.

Usage:
------
    from lipaira_providers import LipairaRouter

    router = LipairaRouter()
    response = router.chat([Message(role="user", content="Hello")], "gpt-4o")
    print(response.content)
"""

# Don't import anything at module level to avoid circular dependencies
# Use lazy imports via __getattr__

__all__ = [
    "LipairaRouter",
    "LLMResponse", 
    "Message",
    "Provider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    "OllamaProvider",
    "MistralProvider",
    "CohereProvider",
    "DeepSeekProvider",
    "QwenProvider",
    "MicrosoftProvider",
    "PerplexityProvider",
    "ZeroOneProvider",
    "MinimaxProvider",
    "TogetherProvider",
    "NvidiaProvider",
    "unified_bp",
]

__version__ = "0.1.0"

# Import hooks to handle lazy loading
_import_hooks = {
    "LipairaRouter": ("router", "LipairaRouter"),
    "LLMResponse": ("models", "LLMResponse"),
    "Message": ("models", "Message"),
    "Provider": ("models", "Provider"),
    "OpenAIProvider": ("providers", "OpenAIProvider"),
    "AnthropicProvider": ("providers", "AnthropicProvider"),
    "GoogleProvider": ("providers", "GoogleProvider"),
    "OllamaProvider": ("providers", "OllamaProvider"),
    "MistralProvider": ("providers", "MistralProvider"),
    "CohereProvider": ("providers", "CohereProvider"),
    "DeepSeekProvider": ("providers", "DeepSeekProvider"),
    "QwenProvider": ("providers", "QwenProvider"),
    "MicrosoftProvider": ("providers", "MicrosoftProvider"),
    "PerplexityProvider": ("providers", "PerplexityProvider"),
    "ZeroOneProvider": ("providers", "ZeroOneProvider"),
    "MinimaxProvider": ("providers", "MinimaxProvider"),
    "TogetherProvider": ("providers", "TogetherProvider"),
    "NvidiaProvider": ("providers", "NvidiaProvider"),
    "unified_bp": ("unified_api", "unified_bp"),
}

def __getattr__(name):
    if name in _import_hooks:
        module_name, attr_name = _import_hooks[name]
        # Import the module directly without triggering __init__ fully
        import importlib
        try:
            # First try absolute import
            module = importlib.import_module(f"lipaira_providers.{module_name}")
        except ImportError:
            # Fallback to file-based import
            import sys
            import types
            base_path = "/app/lipaira_providers"
            if module_name == "models":
                spec = importlib.util.spec_from_file_location("models", f"{base_path}/models.py")
            elif module_name == "providers":
                spec = importlib.util.spec_from_file_location("providers", f"{base_path}/providers.py")
            elif module_name == "router":
                spec = importlib.util.spec_from_file_location("router", f"{base_path}/router.py")
            elif module_name == "unified_api":
                spec = importlib.util.spec_from_file_location("unified_api", f"{base_path}/unified_api.py")
            else:
                raise ImportError(f"Unknown module: {module_name}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"lipaira_providers.{module_name}"] = module
            spec.loader.exec_module(module)
        
        return getattr(module, attr_name)
    raise AttributeError(f"module 'lipaira_providers' has no attribute '{name}'")
