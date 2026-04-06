"""
Model Registry - Live pricing and model info from OpenRouter
"""
import os
import time
import logging
from typing import List, Dict, Optional
import requests

logger = logging.getLogger(__name__)

# Cache models for 1 hour
MODELS_CACHE = {'models': [], 'timestamp': 0}
CACHE_TTL = 3600  # 1 hour

# Our provider API key
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')

def get_models(force_refresh: bool = False) -> List[Dict]:
    """Get models from OpenRouter, with caching."""
    global MODELS_CACHE
    
    now = time.time()
    if not force_refresh and (now - MODELS_CACHE['timestamp']) < CACHE_TTL:
        return MODELS_CACHE['models']
    
    try:
        headers = {}
        if OPENROUTER_API_KEY:
            headers['Authorization'] = f'Bearer {OPENROUTER_API_KEY}'
        
        response = requests.get(
            'https://openrouter.ai/api/v1/models',
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            models = data.get('data', [])
            
            # Process and enrich model data
            enriched = []
            for m in models:
                # Skip non-free if we only want free
                pricing = m.get('pricing', {})
                
                model_entry = {
                    'id': m.get('id'),
                    'name': m.get('name'),
                    'provider': m.get('id', '').split('/')[0] if '/' in m.get('id', '') else 'unknown',
                    'pricing': {
                        'prompt': float(pricing.get('prompt', 0)),
                        'completion': float(pricing.get('completion', 0)),
                        'image': float(pricing.get('image', 0)),
                    },
                    'context_length': m.get('context_length', 0),
                    'architecture': m.get('architecture', {}),
                    'top_provider': m.get('top_provider', {}),
                    'free': 'free' in m.get('id', '').lower() or float(pricing.get('prompt', 1)) == 0,
                }
                enriched.append(model_entry)
            
            MODELS_CACHE = {
                'models': enriched,
                'timestamp': now
            }
            
            logger.info(f"Fetched {len(enriched)} models from OpenRouter")
            return enriched
        
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
    
    # Return cached on failure
    return MODELS_CACHE.get('models', [])

def get_free_models() -> List[Dict]:
    """Get only free models."""
    all_models = get_models()
    return [m for m in all_models if m.get('free', False)]

def get_model_by_id(model_id: str) -> Optional[Dict]:
    """Get a specific model by ID."""
    models = get_models()
    for m in models:
        if m['id'] == model_id:
            return m
    return None

def get_models_by_provider(provider: str) -> List[Dict]:
    """Get all models from a specific provider."""
    models = get_models()
    return [m for m in models if m.get('provider', '').lower() == provider.lower()]

def get_model_pricing_estimate(model_id: str, input_tokens: int, output_tokens: int) -> Dict:
    """Estimate cost for a request in credits."""
    model = get_model_by_id(model_id)
    if not model:
        return {'error': 'Model not found'}
    
    pricing = model.get('pricing', {})
    
    # Prices are in USD per 1M tokens
    prompt_cost = (input_tokens / 1_000_000) * pricing.get('prompt', 0)
    completion_cost = (output_tokens / 1_000_000) * pricing.get('completion', 0)
    total_usd = prompt_cost + completion_cost
    
    # Our markup (5.5% as per pricing model)
    our_fee = total_usd * 0.055
    total_with_fee = total_usd + our_fee
    
    # Convert to credits (1 credit = $1)
    credits = total_with_fee
    
    return {
        'model': model_id,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'provider_cost_usd': round(total_usd, 6),
        'our_fee_usd': round(our_fee, 6),
        'credits_charged': round(credits, 4),
    }

# Model categories for the UI
MODEL_CATEGORIES = {
    'speed': [
        'qwen/qwen3-coder-480b:free',
        'google/gemini-2.0-flash-exp:free',
        'meta-llama/llama-3.1-8b-instruct',
    ],
    'balanced': [
        'openai/gpt-4o-mini',
        'anthropic/claude-3-haiku',
        'mistralai/mistral-7b-instruct',
    ],
    'quality': [
        'openai/gpt-4o',
        'anthropic/claude-3.5-sonnet',
        'google/gemini-pro-1.5',
    ],
    'deep': [
        'anthropic/claude-3-opus',
        'openai/gpt-4-turbo',
        'meta-llama/llama-3.3-70b-instruct',
    ]
}

def get_model_for_quality(quality: str) -> str:
    """Get recommended model for a quality setting."""
    return MODEL_CATEGORIES.get(quality, MODEL_CATEGORIES['balanced'])[0]
