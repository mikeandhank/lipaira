"""
Operator Layer — natural language command execution across integrations.
Exports IntentParser, RateLimitedExecutor, AuditLogger, and the operator_bp
Flask blueprint. Coordinates intent parsing → capability resolution →
rate-limited execution → audit logging for all operator actions.
"""
from .intent import (
    IntentParser,
    OperatorIntent,
    ActionType,
    RiskLevel,
    get_intent_parser
)

from .executor import (
    RateLimitedExecutor,
    PlatformAction,
    ExecutionResult,
    CapabilityResolver,
    get_executor
)

from .audit import (
    AuditLogger,
    AuditEntry,
    get_audit_logger,
    compute_intent_hash
)

from .routes import operator_bp

__all__ = [
    'IntentParser',
    'OperatorIntent', 
    'ActionType',
    'RiskLevel',
    'get_intent_parser',
    'RateLimitedExecutor',
    'PlatformAction',
    'ExecutionResult',
    'CapabilityResolver',
    'get_executor',
    'AuditLogger',
    'AuditEntry',
    'get_audit_logger',
    'compute_intent_hash',
    'operator_bp',
]