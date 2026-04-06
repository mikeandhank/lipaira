"""
Billing Module - Lipaira Pricing System v3
==========================================
Fully metered billing: inference + infrastructure + agent fees
Based on pricing_spec_v3
"""

import os
import logging
from datetime import datetime, date, timedelta
import uuid
from typing import Dict, List, Optional
import psycopg2
from urllib.parse import urlparse
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS (from spec)
# ============================================================================

# Credit definition: 1 credit = $0.01 USD
CENTS_PER_CREDIT = 1

# Starting balance: $0 on signup (freemium - free users get responses, tools disabled)
STARTING_BALANCE_CENTS = 0

# Grace buffer: -$5.00
GRACE_BUFFER_CENTS = -500

# Infrastructure surcharge: 0.5 credits ($0.005) per generation
# Rounded up to nearest cent = 1 cent
INFRASTRUCTURE_PER_CALL_CENTS = 1

# Markup on OpenRouter cost: 1.30 (includes 5.5% OR fee)
OPENROUTER_MARKUP = 1.30

# Agent pricing (monthly and daily rates)
AGENT_PRICING = {
    "primary": {
        "monthly_cents": 3000,     # $30.00/month
        "daily_cents": 100,        # $1.00/day
    },
    "finance": {
        "monthly_cents": 1900,     # $19.00/month  
        "daily_cents": 63,         # $0.633/day
    },
    "marketing": {
        "monthly_cents": 1900,
        "daily_cents": 63,
    },
    "operations": {
        "monthly_cents": 1900,
        "daily_cents": 63,
    },
    "sales": {
        "monthly_cents": 3900,     # $39.00/month
        "daily_cents": 130,        # $1.30/day
    },
}

# Bundle discounts for specialist agents
BUNDLE_DISCOUNTS = {
    2: 0.10,   # 2 specialists: 10% off
    3: 0.15,   # 3 specialists: 15% off
    4: 0.20,   # 4+ specialists: 20% off
}

# Credit purchase packages
CREDIT_PACKAGES = [
    {"name": "Micro", "amount_cents": 1000, "credits": 1000, "discount": 0},
    {"name": "Starter", "amount_cents": 5000, "credits": 5000, "discount": 0},
    {"name": "Solo", "amount_cents": 14000, "credits": 15000, "discount": 0.07},
    {"name": "Professional", "amount_cents": 45000, "credits": 50000, "discount": 0.10},
    {"name": "Business", "amount_cents": 125000, "credits": 150000, "discount": 0.17},
    {"name": "Enterprise", "amount_cents": 375000, "credits": 500000, "discount": 0.25},
]

# Model pricing (credits per 1M tokens - from spec)
# User sees: $/1M, internal uses credits
# Dynamic pricing from OpenRouter API (with 1.3x markup)
_OPENROUTER_PRICING_CACHE = None
_OPENROUTER_PRICING_TIMESTAMP = None
PRICING_CACHE_TTL_SECONDS = 3600  # Cache for 1 hour
MARKUP_MULTIPLIER = 1.30  # 30% markup on OpenRouter costs


def get_openrouter_pricing() -> dict:
    """Fetch live pricing from OpenRouter API with caching."""
    import time
    from providers import get_secret
    
    global _OPENROUTER_PRICING_CACHE, _OPENROUTER_PRICING_TIMESTAMP
    
    # Check cache
    if (_OPENROUTER_PRICING_CACHE is not None and 
        _OPENROUTER_PRICING_TIMESTAMP is not None and
        time.time() - _OPENROUTER_PRICING_TIMESTAMP < PRICING_CACHE_TTL_SECONDS):
        return _OPENROUTER_PRICING_CACHE
    
    try:
        import requests
        api_key = get_secret("OPENROUTER_API_KEY")
        if not api_key:
            return {}
        
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10
        )
        
        if resp.ok:
            models = resp.json().get("data", [])
            pricing = {}
            for m in models:
                model_id = m.get("id")
                pricing_info = m.get("pricing", {})
                
                if pricing_info:
                    # Convert from dollars per token to credits per 1M tokens
                    # OpenRouter pricing is in dollars per token
                    # We charge: (OpenRouter cost × 1.3 markup) / 0.01 (to get credits)
                    prompt_price = float(pricing_info.get("prompt", 0))
                    completion_price = float(pricing_info.get("completion", 0))
                    
                    if prompt_price > 0:
                        # Cost per 1M tokens in dollars, then apply markup
                        prompt_cost_per_1m = prompt_price * 1_000_000 * MARKUP_MULTIPLIER
                        completion_cost_per_1m = completion_price * 1_000_000 * MARKUP_MULTIPLIER
                        
                        # Convert to credits (1 credit = $0.01)
                        pricing[model_id] = {
                            "input": round(prompt_cost_per_1m / 100, 2),  # credits per 1M
                            "output": round(completion_cost_per_1m / 100, 2),
                            "input_cost": prompt_cost_per_1m,  # raw cost for reference
                            "output_cost": completion_cost_per_1m,
                        }
            
            _OPENROUTER_PRICING_CACHE = pricing
            _OPENROUTER_PRICING_TIMESTAMP = time.time()
            return pricing
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to fetch OpenRouter pricing: {e}")
    
    return {}


MODEL_PRICING = {
    # Anthropic
    "claude-haiku-4-5": {"credits_per_1m": 197, "display_per_1m": 1.97},
    "claude-sonnet-4-5": {"credits_per_1m": 741, "display_per_1m": 7.41},
    "claude-opus-4-5": {"credits_per_1m": 3703, "display_per_1m": 37.03},
    # OpenAI
    "gpt-4o": {"credits_per_1m": 549, "display_per_1m": 5.49},
    "gpt-4o-mini": {"credits_per_1m": 33, "display_per_1m": 0.33},
    "gpt-5": {"credits_per_1m": 1000, "display_per_1m": 10.00},
    "o1-preview": {"credits_per_1m": 2000, "display_per_1m": 20.00},
    "o1-mini": {"credits_per_1m": 500, "display_per_1m": 5.00},
    # MiniMax (via OpenRouter)
    "minimax-m2.7": {"credits_per_1m": 50, "display_per_1m": 0.50},
    "minimax-m2.5": {"credits_per_1m": 40, "display_per_1m": 0.40},
    "minimax-01": {"credits_per_1m": 45, "display_per_1m": 0.45},
    # Google
    "gemini-2.0-flash": {"credits_per_1m": 22, "display_per_1m": 0.22},
}


# ============================================================================
# HELPER FUNCTIONS - Prevent float precision errors
# ============================================================================

def dollars_to_cents(dollars: float) -> int:
    """Convert dollars to cents (integer)."""
    return round(float(dollars) * 100)


def cents_to_dollars(cents: int) -> float:
    """Convert cents to dollars."""
    return cents / 100


def get_db_connection():
    """Get database connection - no hardcoded credentials."""
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        result = urlparse(db_url)
        return psycopg2.connect(
            host=result.hostname,
            port=result.port or 5432,
            database=result.path.lstrip("/") if result.path else "nexusos",
            user=result.username,
            password=result.password
        )
    # Fallback to individual env vars
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "lipaira-postgres"),
        database=os.environ.get("POSTGRES_DB", "lipaira"),
        user=os.environ.get("POSTGRES_USER", "lipaira"),
        password=os.environ.get("POSTGRES_PASSWORD")
    )


# ============================================================================
# CORE BILLING FUNCTIONS
# ============================================================================

def calculate_inference_cost(model: str, input_tokens: int, output_tokens: int) -> int:
    """
    Calculate inference cost in credits.
    
    From spec: OpenRouter cost × 1.30 markup
    Returns cost in credits (1 credit = $0.01)
    """
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        # Default to sonnet pricing if unknown
        pricing = MODEL_PRICING["claude-sonnet-4-5"]
    
    total_tokens = input_tokens + output_tokens
    credits = (total_tokens * pricing["credits_per_1m"]) // 1_000_000
    
    # Minimum 1 credit
    return max(credits, 1)


def calculate_infrastructure_cost() -> int:
    """
    Calculate infrastructure surcharge.
    
    From spec: 0.5 credits ($0.005) per generation
    Rounded up to nearest cent = 1 cent
    """
    return INFRASTRUCTURE_PER_CALL_CENTS


def get_agent_daily_cost(agent_type: str) -> int:
    """Get daily cost for an agent type (in credits)."""
    return AGENT_PRICING.get(agent_type, {}).get("daily_cents", 0)


def get_agent_count_discount(agent_count: int) -> float:
    """Get bundle discount for number of specialist agents."""
    if agent_count >= 4:
        return BUNDLE_DISCOUNTS[4]
    return BUNDLE_DISCOUNTS.get(agent_count, 0)


def get_credit_packages() -> List[Dict]:
    """Get available credit purchase packages."""
    return CREDIT_PACKAGES


def calculate_package_credits(amount_cents: int) -> Dict:
    """Calculate credits for a given payment amount."""
    # Find best package or calculate custom
    for pkg in CREDIT_PACKAGES:
        if amount_cents == pkg["amount_cents"]:
            return {
                "credits": pkg["credits"],
                "discount": pkg["discount"],
                "amount_paid": amount_cents,
            }
    
    # Custom amount: linear (1 credit per cent)
    return {
        "credits": amount_cents,
        "discount": 0,
        "amount_paid": amount_cents,
    }


def can_use_service(balance_cents: int) -> Dict:
    """
    Check if user can use service based on balance.
    
    From spec:
    - balance > 0: full access
    - balance <= 0 but > -500: grace buffer (complete current, no new)
    - balance <= -500: paused
    """
    if balance_cents > 0:
        return {"allowed": True, "status": "active", "message": None}
    elif balance_cents > GRACE_BUFFER_CENTS:
        return {"allowed": True, "status": "grace", "message": "Balance low — add credits to continue"}
    else:
        return {"allowed": False, "status": "paused", "message": "Activity paused — add credits to resume"}


def get_daily_burn_rate(active_agents: List[str], avg_calls_per_day: int = 100) -> int:
    """
    Calculate estimated daily burn rate.
    
    Args:
        active_agents: List of active agent types (e.g., ["primary", "finance"])
        avg_calls_per_day: Estimated API calls per day
    """
    # Agent fees
    agent_cost = 0
    specialist_count = 0
    for agent in active_agents:
        if agent == "primary":
            agent_cost += AGENT_PRICING["primary"]["daily_cents"]
        else:
            specialist_count += 1
    
    # Apply bundle discount
    if specialist_count > 1:
        discount = get_agent_count_discount(specialist_count)
        specialist_cost = sum(AGENT_PRICING.get(a, {}).get("daily_cents", 0) 
                             for a in active_agents if a != "primary")
        agent_cost += int(specialist_cost * (1 - discount))
    
    # Infrastructure
    infra_cost = avg_calls_per_day * INFRASTRUCTURE_PER_CALL_CENTS
    
    # Assume haiku as default (cheapest)
    inference_cost = avg_calls_per_day * 1  # ~1 credit per call average
    
    return agent_cost + infra_cost + inference_cost


def get_runway_days(balance_cents: int, daily_burn: int) -> Optional[int]:
    """Calculate days of runway at current burn rate."""
    if daily_burn <= 0:
        return None
    return balance_cents // daily_burn


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def add_credits(user_id: str, credits: int, source: str = "purchase") -> bool:
    """Add credits to user account."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get current balance
        cur.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        current_cents = dollars_to_cents(float(row[0])) if row else 0
        
        new_balance_cents = current_cents + credits
        
        cur.execute(
            "UPDATE users SET credits = %s WHERE id = %s",
            (cents_to_dollars(new_balance_cents), user_id)
        )
        
        # Record transaction
        cur.execute("""
            INSERT INTO credit_transactions 
            (id, user_id, amount, transaction_type, source, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), user_id, cents_to_dollars(credits), 
              "credit_add", source, datetime.utcnow()))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error adding credits: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def deduct_usage(user_id: str, model: str, input_tokens: int, output_tokens: int) -> Dict:
    """
    Deduct usage from user balance.
    
    Components:
    1. Inference cost (per token, marked up)
    2. Infrastructure surcharge (per call)
    
    Returns: {"success": bool, "cost": int, "balance_remaining": int}
    """
    # Calculate costs
    inference_cost = calculate_inference_cost(model, input_tokens, output_tokens)
    infra_cost = calculate_infrastructure_cost()
    total_cost = inference_cost + infra_cost
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get current balance in cents
        cur.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": "User not found"}
        
        balance_cents = dollars_to_cents(float(row[0]))
        
        # Check if can use service
        can_use = can_use_service(balance_cents)
        if not can_use["allowed"]:
            return {
                "success": False, 
                "error": can_use["message"],
                "status": can_use["status"]
            }
        
        new_balance_cents = balance_cents - total_cost
        
        # Update balance
        cur.execute(
            "UPDATE users SET credits = %s WHERE id = %s",
            (cents_to_dollars(new_balance_cents), user_id)
        )
        
        # Record usage
        cur.execute("""
            INSERT INTO llm_usage 
            (id, user_id, model, input_tokens, output_tokens, cost, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), user_id, model, 
              input_tokens, output_tokens, cents_to_dollars(total_cost), datetime.utcnow()))
        
        conn.commit()
        
        return {
            "success": True,
            "cost": total_cost,
            "inference_cost": inference_cost,
            "infrastructure_cost": infra_cost,
            "balance_remaining": new_balance_cents,
            "status": can_use["status"]
        }
        
    except Exception as e:
        logger.error(f"Error deducting usage: {e}")
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        cur.close()
        conn.close()


def get_user_balance_cents(user_id: str) -> int:
    """Get user balance in cents."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if row:
            return dollars_to_cents(float(row[0]))
        return 0
    finally:
        cur.close()
        conn.close()


def get_user_billing_info(user_id: str) -> Dict:
    """Get comprehensive billing info for user."""
    balance_cents = get_user_balance_cents(user_id)
    can_use = can_use_service(balance_cents)
    
    # Get active agents (would come from user_profiles or similar)
    # For now, assume primary only
    active_agents = ["primary"]
    
    # Calculate burn rate
    daily_burn = get_daily_burn_rate(active_agents)
    runway = get_runway_days(balance_cents, daily_burn)
    
    return {
        "balance_cents": balance_cents,
        "balance_display": f"${cents_to_dollars(balance_cents):.2f}",
        "status": can_use["status"],
        "message": can_use["message"],
        "daily_burn_cents": daily_burn,
        "daily_burn_display": f"${cents_to_dollars(daily_burn):.2f}/day",
        "runway_days": runway,
        "runway_display": f"{runway} days" if runway else "N/A",
    }


# ============================================================================
# INITIALIZATION
# ============================================================================

def init_billing_tables():
    """Create billing-related tables if they don't exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Credit transactions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS credit_transactions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            amount REAL NOT NULL,
            transaction_type TEXT NOT NULL,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Agent subscriptions table (with all required columns)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_subscriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            agent_type TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            daily_rate_cents INTEGER NOT NULL,
            hired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fired_at TIMESTAMP
        )
    """)
    
    # Auto-refill settings table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS auto_refill_settings (
            id SERIAL PRIMARY KEY,
            user_id TEXT UNIQUE NOT NULL,
            enabled BOOLEAN DEFAULT FALSE,
            threshold_cents INTEGER DEFAULT 1000,
            package_cents INTEGER DEFAULT 5000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Billing tables initialized")


# ============================================================================
# DAILY SWEEP - Charge agent base fees
# ============================================================================

def run_daily_sweep(sweep_date=None) -> Dict:
    """
    Charge prorated daily base fee for every active agent.
    Runs at midnight UTC.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    charged = 0
    skipped = 0
    errors = 0
    
    if sweep_date is None:
        sweep_date = datetime.utcnow().date()
    
    try:
        # Get all active agent subscriptions
        cur.execute("""
            SELECT user_id, agent_type, daily_rate_cents, id
            FROM agent_subscriptions
            WHERE status = 'active'
            AND (fired_at IS NULL OR fired_at > NOW())
        """)
        active = cur.fetchall()
        
        for sub in active:
            try:
                # Get current balance
                cur2 = conn.cursor()
                cur2.execute(
                    "SELECT credits FROM users WHERE id = %s",
                    (sub['user_id'],)
                )
                row = cur2.fetchone()
                if not row:
                    errors += 1
                    continue
                
                balance_cents = dollars_to_cents(float(row[0]))
                fee = sub['daily_rate_cents']
                new_balance_cents = balance_cents - fee
                
                # Check grace buffer
                if new_balance_cents < GRACE_BUFFER_CENTS:
                    logger.warning(f"Skipping fee for {sub['user_id']}: "
                                  f"would exceed grace buffer")
                    skipped += 1
                    continue
                
                # Deduct fee
                cur2.execute(
                    "UPDATE users SET credits = %s WHERE id = %s",
                    (cents_to_dollars(new_balance_cents), sub['user_id'])
                )
                
                # Log to credit_transactions
                cur2.execute("""
                    INSERT INTO credit_transactions
                    (id, user_id, amount, transaction_type,
                     source, created_at)
                    VALUES (%s, %s, %s, 'debit', %s, NOW())
                """, (
                    f"sweep_{sub['user_id']}_{sweep_date}_{sub['agent_type']}",
                    sub['user_id'],
                    cents_to_dollars(fee),
                    f"agent_base_fee:{sub['agent_type']}"
                ))
                
                conn.commit()
                charged += 1
                
            except Exception as e:
                logger.error(f"Sweep error for {sub['user_id']}: {e}")
                conn.rollback()
                errors += 1
            finally:
                if 'cur2' in locals():
                    cur2.close()
        
    finally:
        cur.close()
        conn.close()
    
    logger.info(f"Daily sweep: {charged} charged, {skipped} skipped, {errors} errors")
    return {
        "status": "completed",
        "charged": charged,
        "skipped": skipped,
        "errors": errors,
        "date": str(sweep_date)
    }


# ============================================================================
# API COMPATIBILITY FUNCTIONS
# ============================================================================

def calculate_credits_and_fee(user_payment: float) -> Dict[str, float]:
    """
    Calculate credits and fee from user payment amount.
    From spec: credits = payment, 5.5% fee absorbed in markup.
    """
    # Simple: user pays $X, gets $X in credits
    # The 5.5% fee and markup are handled in the cost calculation
    return {
        "credits": int(user_payment * 100),  # in cents
        "fee": 0,  # handled in markup
        "total_charged": int(user_payment * 100),
    }


def get_pricing_tiers() -> List[Dict]:
    """Get all pricing tiers (for API)."""
    return [
        {"model_id": k, "model_name": k.replace("-", " ").title(), 
         "our_input_cost": v["credits_per_1m"] / 100, 
         "our_output_cost": v["credits_per_1m"] / 100}
        for k, v in MODEL_PRICING.items()
    ]


# ============================================================================
# PHASE 2: MEMORY SWEEPS - Extract context from integrations
# ============================================================================

def get_user_integrations(user_id: str) -> List[Dict]:
    """Get user's connected integrations for memory extraction."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check if status column exists
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'user_integrations' AND column_name = 'status'
    """)
    has_status = cur.fetchone() is not None
    
    if has_status:
        cur.execute("""
            SELECT provider, access_token, refresh_token, expires_at
            FROM user_integrations
            WHERE user_id = %s AND status = 'connected'
        """, (user_id,))
    else:
        # Fallback: get all (assuming if record exists, it's connected)
        cur.execute("""
            SELECT provider, access_token, refresh_token, expires_at
            FROM user_integrations
            WHERE user_id = %s
        """, (user_id,))
    
    integrations = cur.fetchall()
    conn.close()
    return [dict(i) for i in integrations]


def extract_quickbooks_context(user_id: str) -> Dict:
    """
    Extract relevant context from QuickBooks for agent memory.
    Called when Finance agent needs to answer QB-related questions.
    """
    integrations = get_user_integrations(user_id)
    qb = next((i for i in integrations if i['provider'] == 'quickbooks'), None)
    
    if not qb:
        return {"connected": False, "data": None}
    
    # In production, this would call QuickBooks API
    # For now, return structure
    return {
        "connected": True,
        "last_sync": None,
        "data": {
            "customers": [],
            "invoices": [],
            "expenses": []
        }
    }


def extract_google_context(user_id: str) -> Dict:
    """
    Extract relevant context from Google (Gmail, Calendar, Drive).
    """
    integrations = get_user_integrations(user_id)
    google = next((i for i in integrations if i['provider'] == 'google'), None)
    
    if not google:
        return {"connected": False, "gmail": False, "calendar": False, "drive": False}
    
    return {
        "connected": True,
        "gmail": True,
        "calendar": True,
        "drive": True,
        "last_sync": None
    }


def run_memory_sweep(user_id: str) -> Dict:
    """
    Run periodic memory sweep - extract and update agent context.
    Called by background task or on-demand.
    """
    result = {
        "user_id": user_id,
        "integrations_found": 0,
        "context_updated": False,
        "errors": []
    }
    
    try:
        integrations = get_user_integrations(user_id)
        result["integrations_found"] = len(integrations)
        
        for int_app in integrations:
            try:
                if int_app['provider'] == 'quickbooks':
                    extract_quickbooks_context(user_id)
                elif int_app['provider'] == 'google':
                    extract_google_context(user_id)
            except Exception as e:
                result["errors"].append(f"{int_app['provider']}: {str(e)}")
        
        if not result["errors"]:
            result["context_updated"] = True
            
    except Exception as e:
        result["errors"].append(str(e))
    
    return result
