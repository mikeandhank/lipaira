"""
Prompt Input Sanitization Module
C8: Mitigates CVE-2025-54794 prompt injection attacks

Strips fake markdown directives (# SYSTEM:, # USER:, # ASSISTANT:) 
that can override model safety constraints.
"""
import re
from typing import Optional


# Regex pattern for prompt injection directives at line start
# Matches: # SYSTEM:, # USER:, # ASSISTANT:, # ADMIN:, # SYSTEM_PROMPT:, etc.
PROMPT_INJECTION_PATTERN = re.compile(
    r'^\s*(?:#\s*(?:SYSTEM|USER|ASSISTANT|ADMIN|SYSTEM_PROMPT|MODEL|INSTRUCT|Override|Directive)[^\n]*)',
    re.IGNORECASE | re.MULTILINE
)


def sanitize_prompt_input(user_input: str) -> str:
    """
    Strip fake markdown directives that attempt to override system prompts.
    
    Args:
        user_input: Raw user message before LLM context
        
    Returns:
        Sanitized input with injection directives removed
    """
    if not user_input:
        return user_input
    
    # Remove injection directives at line start
    sanitized = PROMPT_INJECTION_PATTERN.sub('', user_input)
    
    # Also handle common encoding bypass attempts
    # Zero-width characters sometimes used to evade detection
    sanitized = sanitized.replace('\u200b', '')  # Zero-width space
    sanitized = sanitized.replace('\u200c', '')  # Zero-width non-joiner
    sanitized = sanitized.replace('\u200d', '')  # Zero-width joiner
    sanitized = sanitized.replace('\ufeff', '')  # Zero-width no-break space
    
    # Normalize multiple newlines (sometimes used to hide content)
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    
    return sanitized.strip()


def is_suspicious_input(user_input: str) -> bool:
    """
    Check if input contains suspicious patterns that warrant logging.
    
    Args:
        user_input: Raw user message
        
    Returns:
        True if input contains injection patterns
    """
    if not user_input:
        return False
    
    # Check for various injection patterns
    patterns = [
        r'#\s*SYSTEM[:\s]',
        r'#\s*USER[:\s]',
        r'#\s*ASSISTANT[:\s]',
        r'ignore\s+(?:previous|above|instructions)',
        r'forget\s+(?:everything|all|your)',
        r'new\s+system\s*prompt',
        r'override\s+(?:your|model)',
        r'directive[:\s]',
    ]
    
    return any(re.search(p, user_input, re.IGNORECASE) for p in patterns)
