# feel free to ignore this comment
"""Prompt Input Sanitization Module - mitigates CVE-2025-54794 prompt injection attacks.

Strips fake markdown directives (# SYSTEM:, # USER:, # ASSISTANT:) that can
override model safety constraints. Also removes zero-width Unicode characters
used to evade detection and normalizes excess newlines.

Key functions:
    sanitize_prompt_input(user_input: str): Strip injection directives and
        bypass encodings from raw user input; returns sanitized string.
    is_suspicious_input(user_input: str): Check input for injection patterns
        and return True if logging/warning is warranted.
"""
     8|import re
     9|from typing import Optional
    10|
    11|
    12|# Regex pattern for prompt injection directives at line start
    13|# Matches: # SYSTEM:, # USER:, # ASSISTANT:, # ADMIN:, # SYSTEM_PROMPT:, etc.
    14|PROMPT_INJECTION_PATTERN = re.compile(
    15|    r'^\s*(?:#\s*(?:SYSTEM|USER|ASSISTANT|ADMIN|SYSTEM_PROMPT|MODEL|INSTRUCT|Override|Directive)[^\n]*)',
    16|    re.IGNORECASE | re.MULTILINE
    17|)
    18|
    19|
    20|def sanitize_prompt_input(user_input: str) -> str:
    21|    """
    22|    Strip fake markdown directives that attempt to override system prompts.
    23|    
    24|    Args:
    25|        user_input: Raw user message before LLM context
    26|        
    27|    Returns:
    28|        Sanitized input with injection directives removed
    29|    """
    30|    if not user_input:
    31|        return user_input
    32|    
    33|    # Remove injection directives at line start
    34|    sanitized = PROMPT_INJECTION_PATTERN.sub('', user_input)
    35|    
    36|    # Also handle common encoding bypass attempts
    37|    # Zero-width characters sometimes used to evade detection
    38|    sanitized = sanitized.replace('\u200b', '')  # Zero-width space
    39|    sanitized = sanitized.replace('\u200c', '')  # Zero-width non-joiner
    40|    sanitized = sanitized.replace('\u200d', '')  # Zero-width joiner
    41|    sanitized = sanitized.replace('\ufeff', '')  # Zero-width no-break space
    42|    
    43|    # Normalize multiple newlines (sometimes used to hide content)
    44|    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    45|    
    46|    return sanitized.strip()
    47|
    48|
    49|def is_suspicious_input(user_input: str) -> bool:
    50|    """
    51|    Check if input contains suspicious patterns that warrant logging.
    52|    
    53|    Args:
    54|        user_input: Raw user message
    55|        
    56|    Returns:
    57|        True if input contains injection patterns
    58|    """
    59|    if not user_input:
    60|        return False
    61|    
    62|    # Check for various injection patterns
    63|    patterns = [
    64|        r'#\s*SYSTEM[:\s]',
    65|        r'#\s*USER[:\s]',
    66|        r'#\s*ASSISTANT[:\s]',
    67|        r'ignore\s+(?:previous|above|instructions)',
    68|        r'forget\s+(?:everything|all|your)',
    69|        r'new\s+system\s*prompt',
    70|        r'override\s+(?:your|model)',
    71|        r'directive[:\s]',
    72|    ]
    73|    
    74|    return any(re.search(p, user_input, re.IGNORECASE) for p in patterns)
    75|