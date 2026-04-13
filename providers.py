"""
Provider configuration loader for Lipaira.
Maps integration secret names (QuickBooks, Shopify, Slack, etc.) to environment
variables by loading credentials from AWS Secrets Manager at startup. Falls back to
environment variables when Secrets Manager is unavailable.
"""

import os
import json
import boto3
from botocore.exceptions import ClientError

# AWS Secrets Manager secret name mapping
SECRET_MAP = {
    # LLM Providers
    "lipaira/anthropic-api-key": "ANTHROPIC_API_KEY",
    "lipaira/OpenAI_API_Key": "OPENAI_API_KEY",
    "lipaira/Google_API_Key": "GOOGLE_API_KEY",
    "lipaira/Mistral_API_Key": "MISTRAL_API_KEY",
    "lipaira/Cohere_API_Key": "COHERE_API_KEY",
    "lipaira/Deepseek_API_Key": "DEEPSEEK_API_KEY",
    "lipaira/xAI_API_Key": "XAI_API_KEY",
    "lipaira/Minimax_API_Key": "MINIMAX_API_KEY",
    "lipaira/StepFun_API_Key": "STEPFUN_API_KEY",
    "lipaira/OpenRouter_API_Key": "OPENROUTER_API_KEY",
    # OAuth Providers
    "lipaira/Google_OAuth_Client_ID": "GOOGLE_CLIENT_ID",
    "lipaira/Google_OAuth_Client_Secret": "GOOGLE_CLIENT_SECRET",
    "lipaira/MICROSOFT_CLIENT_ID": "MICROSOFT_CLIENT_ID",
    "lipaira/MICROSOFT_CLIENT_SECRET": "MICROSOFT_CLIENT_SECRET",
    "lipaira/QuickBooks_Client_ID": "QUICKBOOKS_CLIENT_ID",
    "lipaira/QuickBooks_Client_SECRET": "QUICKBOOKS_CLIENT_SECRET",
    "lipaira/Zoho_Client_ID": "ZOHO_CLIENT_ID",
    "lipaira/Zoho_Client_Secret": "ZOHO_CLIENT_SECRET",
    "lipaira/Slack_Client_ID": "SLACK_CLIENT_ID",
    "lipaira/Slack_Client_Secret": "SLACK_CLIENT_SECRET",
    "lipaira/Notion_Client_ID": "NOTION_CLIENT_ID",
    "lipaira/Notion_Client_Secret": "NOTION_CLIENT_SECRET",
    "lipaira/Square_Client_ID": "SQUARE_CLIENT_ID",
    "lipaira/Square_Client_Secret": "SQUARE_CLIENT_SECRET",
    "lipaira/Salesforce_Client_ID": "SALESFORCE_CLIENT_ID",
    "lipaira/Salesforce_Client_Secret": "SALESFORCE_CLIENT_SECRET",
    "lipaira/HubSpot_Client_ID": "HUBSPOT_CLIENT_ID",
    "lipaira/HubSpot_Client_Secret": "HUBSPOT_CLIENT_SECRET",
    "lipaira/Pipedrive_Client_ID": "PIPEDRIVE_CLIENT_ID",
    "lipaira/Pipedrive_Client_Secret": "PIPEDRIVE_CLIENT_SECRET",
    # New OAuth Providers (from INTEGRATIONS.md spec)
    "lipaira/Zoom_Client_ID": "ZOOM_CLIENT_ID",
    "lipaira/Zoom_Client_Secret": "ZOOM_CLIENT_SECRET",
    "lipaira/Calendly_Client_ID": "CALENDLY_CLIENT_ID",
    "lipaira/Calendly_Client_Secret": "CALENDLY_CLIENT_SECRET",
    "lipaira/Meta_Client_ID": "META_CLIENT_ID",
    "lipaira/Meta_Client_Secret": "META_CLIENT_SECRET",
    "lipaira/Canva_Client_ID": "CANVA_CLIENT_ID",
    "lipaira/Canva_Client_Secret": "CANVA_CLIENT_SECRET",
    "lipaira/Trello_API_Key": "TRELLO_API_KEY",
    "lipaira/Trello_API_Secret": "TRELLO_API_SECRET",
    "lipaira/Asana_Client_ID": "ASANA_CLIENT_ID",
    "lipaira/Asana_Client_Secret": "ASANA_CLIENT_SECRET",
    "lipaira/Google_Ads_Developer_Token": "GOOGLE_ADS_DEVELOPER_TOKEN",
    # Resend
    "lipaira/Resend_API_Key": "RESEND_API_KEY",
    "lipaira/Brave_Search_API_Key": "BRAVE_SEARCH_API_KEY",
    # Stripe
    "lipaira/STRIPE_SECRET_KEY": "STRIPE_SECRET_KEY",
    "lipaira/STRIPE_PRICE_PERSONAL": "STRIPE_PRICE_PERSONAL",
    "lipaira/STRIPE_PRICE_PROFESSIONAL": "STRIPE_PRICE_PROFESSIONAL",
    "lipaira/STRIPE_PRICE_TEAM": "STRIPE_PRICE_TEAM",
    "lipaira/STRIPE_PRICE_USAGE": "STRIPE_PRICE_USAGE",
    # Infrastructure
    "lipaira/Token_Encryption_Key": "TOKEN_ENCRYPTION_KEY",
}

# Key field mapping within each secret
KEY_FIELD_MAP = {
    # LLM Providers
    "ANTHROPIC_API_KEY": "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY": "OpenAI_API_Key",
    "GOOGLE_API_KEY": "Google_API_Key",
    "MISTRAL_API_KEY": "Mistral_API_Key",
    "COHERE_API_KEY": "Cohere_API_Key",
    "DEEPSEEK_API_KEY": "Deepseek_API_Key",
    "XAI_API_KEY": "xAI_API_Key",
    "MINIMAX_API_KEY": "Minimax_API_Key",
    "OPENROUTER_API_KEY": "OpenRouter_API_Key",
    "STEPFUN_API_KEY": "StepFun_API_Key",
    # OAuth Providers
    "GOOGLE_CLIENT_ID": "Google_OAuth_Client_ID",
    "GOOGLE_CLIENT_SECRET": "Google_OAuth_Client_Secret",
    "MICROSOFT_CLIENT_ID": "MICROSOFT_CLIENT_ID",
    "MICROSOFT_CLIENT_SECRET": "MICROSOFT_CLIENT_SECRET",
    "QUICKBOOKS_CLIENT_ID": "QuickBooks_Client_ID",
    "QUICKBOOKS_CLIENT_SECRET": "QuickBooks_Client_SECRET",
    "ZOHO_CLIENT_ID": "Zoho_Client_ID",
    "ZOHO_CLIENT_SECRET": "Zoho_Client_Secret",
    "SALESFORCE_CLIENT_ID": "Salesforce_Client_ID",
    "SALESFORCE_CLIENT_SECRET": "Salesforce_Client_Secret",
    "HUBSPOT_CLIENT_ID": "HubSpot_Client_ID",
    "HUBSPOT_CLIENT_SECRET": "HubSpot_Client_Secret",
    "PIPEDRIVE_CLIENT_ID": "Pipedrive_Client_ID",
    "PIPEDRIVE_CLIENT_SECRET": "Pipedrive_Client_Secret",
    # Notion
    "NOTION_CLIENT_ID": "Notion_Client_ID",
    "NOTION_CLIENT_SECRET": "Notion_Client_Secret",
    # Slack
    "SLACK_CLIENT_ID": "Slack_Client_ID",
    "SLACK_CLIENT_SECRET": "Slack_Client_Secret",
    # Square
    "SQUARE_CLIENT_ID": "Square_Client_ID",
    "SQUARE_CLIENT_SECRET": "Square_Client_Secret",
    # New OAuth Providers (from INTEGRATIONS.md spec)
    "ZOOM_CLIENT_ID": "Zoom_Client_ID",
    "ZOOM_CLIENT_SECRET": "Zoom_Client_Secret",
    "CALENDLY_CLIENT_ID": "Calendly_Client_ID",
    "CALENDLY_CLIENT_SECRET": "Calendly_Client_Secret",
    "META_CLIENT_ID": "Meta_Client_ID",
    "META_CLIENT_SECRET": "Meta_Client_Secret",
    "CANVA_CLIENT_ID": "Canva_Client_ID",
    "CANVA_CLIENT_SECRET": "Canva_Client_Secret",
    "TRELLO_API_KEY": "Trello_API_Key",
    "TRELLO_API_SECRET": "Trello_API_Secret",
    "ASANA_CLIENT_ID": "Asana_Client_ID",
    "ASANA_CLIENT_SECRET": "Asana_Client_Secret",
    "GOOGLE_ADS_DEVELOPER_TOKEN": "Google_Ads_Developer_Token",
    # Other APIs
    "RESEND_API_KEY": "Resend_API_Key",
    "BRAVE_SEARCH_API_KEY": "Brave_Search_API_Key",
    # Stripe
    "STRIPE_SECRET_KEY": "STRIPE_SECRET_KEY",
    "STRIPE_PRICE_PERSONAL": "STRIPE_PRICE_PERSONAL",
    "STRIPE_PRICE_PROFESSIONAL": "STRIPE_PRICE_PROFESSIONAL",
    "STRIPE_PRICE_TEAM": "STRIPE_PRICE_TEAM",
    "STRIPE_PRICE_USAGE": "STRIPE_PRICE_USAGE",
    # Infrastructure
    "TOKEN_ENCRYPTION_KEY": "Token_Encryption_Key",
}

# Cache for loaded secrets
_SECRETS_CACHE = {}

def load_secrets():
    """Load API keys from AWS Secrets Manager."""
    client = boto3.client(
        'secretsmanager',
        region_name=os.environ.get('AWS_REGION', 'us-east-2')
    )
    
    loaded = []
    failed = []
    
    for secret_name, env_var in SECRET_MAP.items():
        if env_var in _SECRETS_CACHE:
            loaded.append(secret_name)
            continue
            
        try:
            response = client.get_secret_value(SecretId=secret_name)
            secret_dict = json.loads(response['SecretString'])
            
            key_field = KEY_FIELD_MAP.get(env_var, env_var)
            api_key = secret_dict.get(key_field)
            
            if api_key:
                _SECRETS_CACHE[env_var] = api_key
                os.environ[env_var] = api_key
                loaded.append(secret_name)
            else:
                failed.append(f"{secret_name}: key '{key_field}' not found")
        except ClientError as e:
            failed.append(f"{secret_name}: {e.response['Error']['Code']}")
        except Exception as e:
            failed.append(f"{secret_name}: {str(e)}")
    
    print(f"✅ Loaded {len(loaded)} provider secrets from ASM")
    if failed:
        print(f"⚠️ Failed to load {len(failed)} secrets")
    return loaded

def get_api_key(provider: str) -> str:
    """Get API key for a provider, loading from ASM if needed."""
    env_var = f"{provider.upper()}_API_KEY"
    
    if env_var in _SECRETS_CACHE:
        return _SECRETS_CACHE[env_var]
    
    if os.environ.get(env_var):
        return os.environ.get(env_var)
    
    if not _SECRETS_CACHE:
        load_secrets()
    
    return _SECRETS_CACHE.get(env_var)


def get_secret(env_var: str) -> str:
    """Get a secret by environment variable name, loading from ASM if needed."""
    if env_var in _SECRETS_CACHE:
        return _SECRETS_CACHE[env_var]
    
    if os.environ.get(env_var):
        return os.environ.get(env_var)
    
    if not _SECRETS_CACHE:
        load_secrets()
    
    return _SECRETS_CACHE.get(env_var)

# Environment variable -> provider name mapping
ENV_MAP = {
    "ANTHROPIC_API_KEY": "anthropic",
    "OPENAI_API_KEY": "openai",
    "GOOGLE_API_KEY": "google",
    "MISTRAL_API_KEY": "mistral",
    "COHERE_API_KEY": "cohere",
    "DEEPSEEK_API_KEY": "deepseek",
    "XAI_API_KEY": "xai",
    "MINIMAX_API_KEY": "minimax",
    "OPENROUTER_API_KEY": "openrouter",
    "STEPFUN_API_KEY": "stepfun",
}

def get_loaded_providers():
    """Return list of providers with valid API keys."""
    if not _SECRETS_CACHE:
        load_secrets()
    return list(_SECRETS_CACHE.keys())

# Provider endpoints and models
PROVIDER_ENDPOINTS = {
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"]
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o1-mini"]
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"]
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "models": ["mistral-large-latest", "mistral-small-latest", "mistral-nemo", "codestral-latest"]
    },
    "cohere": {
        "base_url": "https://api.cohere.ai/v1",
        "models": ["command-r-plus", "command-r", "command-light"]
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"]
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "models": ["grok-3", "grok-3-mini", "grok-2"]
    },
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "models": ["minimax-01", "abab6.5s-chat"]
    },
    "stepfun": {
        "base_url": "https://api.stepfun.com/v1",
        "models": ["step-2-16k", "step-1-8k"]
    },
    "ollama": {
        "base_url": "http://ollama:11434/v1",
        "models": ["mistral", "phi3"]
    },
}

# Pricing per million tokens (USD)
PROVIDER_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 2.50, "output": 10.00},
    "o1-mini": {"input": 1.10, "output": 4.40},
    "o1": {"input": 15.00, "output": 60.00},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "mistral-nemo": {"input": 0.15, "output": 0.15},
    "mistral-small-latest": {"input": 0.20, "output": 0.60},
    "mistral-large-latest": {"input": 2.00, "output": 6.00},
    "codestral-latest": {"input": 0.20, "output": 0.60},
    "command-light": {"input": 0.30, "output": 0.60},
    "command-r": {"input": 0.15, "output": 0.60},
    "command-r-plus": {"input": 2.50, "output": 10.00},
    "deepseek-chat": {"input": 0.07, "output": 1.10},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "grok-2": {"input": 2.00, "output": 10.00},
    "grok-3-mini": {"input": 0.30, "output": 0.50},
    "grok-3": {"input": 3.00, "output": 15.00},
    "minimax-01": {"input": 0.20, "output": 1.10},
    "abab6.5s-chat": {"input": 0.10, "output": 0.50},
    "step-2-16k": {"input": 0.38, "output": 1.50},
    "step-1-8k": {"input": 0.20, "output": 1.00},
    "mistral": {"input": 0.08, "output": 0.40},
    "phi3": {"input": 0.04, "output": 0.20},
}

DEFAULT_PRICING = {"input": 0.20, "output": 1.00}
CREDITS_PER_DOLLAR = 100
PLATFORM_FEE = 0.055

def calculate_credits(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate credits used for a request."""
    pricing = PROVIDER_PRICING.get(model, DEFAULT_PRICING)
    cost_usd = (
        (input_tokens / 1_000_000) * pricing["input"] +
        (output_tokens / 1_000_000) * pricing["output"]
    ) * (1 + PLATFORM_FEE)
    credits_used = cost_usd * CREDITS_PER_DOLLAR
    return max(0.001, round(credits_used, 4))