# feel free to ignore this comment
     1|"""Billing Module - Lipaira Pricing System v3 (fully metered).
     2|
     3|Fully metered billing: inference + infrastructure + agent fees.
     4|Based on pricing_spec_v3. All monetary values stored in cents (int)
     5|to avoid floating-point precision errors.
     6|
     7|Key constants:
     8|    CENTS_PER_CREDIT: 1 credit = $0.01 USD
     9|    GRACE_BUFFER_CENTS: -500 ($-5.00 grace before service pause)
    10|    INFRASTRUCTURE_PER_CALL_CENTS: 1 cent per generation
     11|    OPENROUTER_MARKUP: 1.30x markup on OpenRouter inference costs
     12|    AGENT_PRICING: Monthly/daily rates per agent type
     13|    CREDIT_PACKAGES: Pre-defined credit purchase tiers
     14|
     15|Key functions:
     16|    calculate_inference_cost(model, input_tokens, output_tokens): Compute
     17|        inference cost in credits for a model and token count.
     18|    calculate_infrastructure_cost(): Return per-call infrastructure surcharge.
     19|    can_use_service(balance_cents): Check if user is active/grace/paused.
     20|    deduct_usage(user_id, model, input_tokens, output_tokens): Deduct
     21|        inference + infra costs from user balance; record in llm_usage table.
     22|    add_credits(user_id, credits, source): Add credits and record transaction.
     23|    get_user_balance_cents(user_id): Return current balance in cents.
     24|    get_user_billing_info(user_id): Return full billing dashboard dict.
     25|    init_billing_tables(): Create credit_transactions and llm_usage tables.
     26|"""
     7|
     8|import os
     9|import logging
    10|from datetime import datetime, date, timedelta
    11|import uuid
    12|from typing import Dict, List, Optional
    13|import psycopg2
    14|from urllib.parse import urlparse
    15|from psycopg2.extras import RealDictCursor
    16|
    17|logger = logging.getLogger(__name__)
    18|
    19|# ============================================================================
    20|# CONSTANTS (from spec)
    21|# ============================================================================
    22|
    23|# Credit definition: 1 credit = $0.01 USD
    24|CENTS_PER_CREDIT = 1
    25|
    26|# Starting balance: $0 on signup (freemium - free users get responses, tools disabled)
    27|STARTING_BALANCE_CENTS = 0
    28|
    29|# Grace buffer: -$5.00
    30|GRACE_BUFFER_CENTS = -500
    31|
    32|# Infrastructure surcharge: 0.5 credits ($0.005) per generation
    33|# Rounded up to nearest cent = 1 cent
    34|INFRASTRUCTURE_PER_CALL_CENTS = 1
    35|
    36|# Markup on OpenRouter cost: 1.30 (includes 5.5% OR fee)
    37|OPENROUTER_MARKUP = 1.30
    38|
    39|# Agent pricing (monthly and daily rates)
    40|AGENT_PRICING = {
    41|    "primary": {
    42|        "monthly_cents": 3000,     # $30.00/month
    43|        "daily_cents": 100,        # $1.00/day
    44|    },
    45|    "finance": {
    46|        "monthly_cents": 1900,     # $19.00/month  
    47|        "daily_cents": 63,         # $0.633/day
    48|    },
    49|    "marketing": {
    50|        "monthly_cents": 1900,
    51|        "daily_cents": 63,
    52|    },
    53|    "operations": {
    54|        "monthly_cents": 1900,
    55|        "daily_cents": 63,
    56|    },
    57|    "sales": {
    58|        "monthly_cents": 3900,     # $39.00/month
    59|        "daily_cents": 130,        # $1.30/day
    60|    },
    61|}
    62|
    63|# Bundle discounts for specialist agents
    64|BUNDLE_DISCOUNTS = {
    65|    2: 0.10,   # 2 specialists: 10% off
    66|    3: 0.15,   # 3 specialists: 15% off
    67|    4: 0.20,   # 4+ specialists: 20% off
    68|}
    69|
    70|# Credit purchase packages
    71|CREDIT_PACKAGES = [
    72|    {"name": "Micro", "amount_cents": 1000, "credits": 1000, "discount": 0},
    73|    {"name": "Starter", "amount_cents": 5000, "credits": 5000, "discount": 0},
    74|    {"name": "Solo", "amount_cents": 14000, "credits": 15000, "discount": 0.07},
    75|    {"name": "Professional", "amount_cents": 45000, "credits": 50000, "discount": 0.10},
    76|    {"name": "Business", "amount_cents": 125000, "credits": 150000, "discount": 0.17},
    77|    {"name": "Enterprise", "amount_cents": 375000, "credits": 500000, "discount": 0.25},
    78|]
    79|
    80|# Model pricing (credits per 1M tokens - from spec)
    81|# User sees: $/1M, internal uses credits
    82|# Dynamic pricing from OpenRouter API (with 1.3x markup)
    83|_OPENROUTER_PRICING_CACHE = None
    84|_OPENROUTER_PRICING_TIMESTAMP = None
    85|PRICING_CACHE_TTL_SECONDS = 3600  # Cache for 1 hour
    86|MARKUP_MULTIPLIER = 1.30  # 30% markup on OpenRouter costs
    87|
    88|
    89|def get_openrouter_pricing() -> dict:
    90|    """Fetch live pricing from OpenRouter API with caching."""
    91|    import time
    92|    from providers import get_secret
    93|    
    94|    global _OPENROUTER_PRICING_CACHE, _OPENROUTER_PRICING_TIMESTAMP
    95|    
    96|    # Check cache
    97|    if (_OPENROUTER_PRICING_CACHE is not None and 
    98|        _OPENROUTER_PRICING_TIMESTAMP is not None and
    99|        time.time() - _OPENROUTER_PRICING_TIMESTAMP < PRICING_CACHE_TTL_SECONDS):
   100|        return _OPENROUTER_PRICING_CACHE
   101|    
   102|    try:
   103|        import requests
   104|        api_key = get_secret("OPENROUTER_API_KEY")
   105|        if not api_key:
   106|            return {}
   107|        
   108|        resp = requests.get(
   109|            "https://openrouter.ai/api/v1/models",
   110|            headers={"Authorization": f"Bearer {api_key}"},
   111|            timeout=10
   112|        )
   113|        
   114|        if resp.ok:
   115|            models = resp.json().get("data", [])
   116|            pricing = {}
   117|            for m in models:
   118|                model_id = m.get("id")
   119|                pricing_info = m.get("pricing", {})
   120|                
   121|                if pricing_info:
   122|                    # Convert from dollars per token to credits per 1M tokens
   123|                    # OpenRouter pricing is in dollars per token
   124|                    # We charge: (OpenRouter cost × 1.3 markup) / 0.01 (to get credits)
   125|                    prompt_price = float(pricing_info.get("prompt", 0))
   126|                    completion_price = float(pricing_info.get("completion", 0))
   127|                    
   128|                    if prompt_price > 0:
   129|                        # Cost per 1M tokens in dollars, then apply markup
   130|                        prompt_cost_per_1m = prompt_price * 1_000_000 * MARKUP_MULTIPLIER
   131|                        completion_cost_per_1m = completion_price * 1_000_000 * MARKUP_MULTIPLIER
   132|                        
   133|                        # Convert to credits (1 credit = $0.01)
   134|                        pricing[model_id] = {
   135|                            "input": round(prompt_cost_per_1m / 100, 2),  # credits per 1M
   136|                            "output": round(completion_cost_per_1m / 100, 2),
   137|                            "input_cost": prompt_cost_per_1m,  # raw cost for reference
   138|                            "output_cost": completion_cost_per_1m,
   139|                        }
   140|            
   141|            _OPENROUTER_PRICING_CACHE = pricing
   142|            _OPENROUTER_PRICING_TIMESTAMP = time.time()
   143|            return pricing
   144|    except Exception as e:
   145|        import logging
   146|        logging.getLogger(__name__).warning(f"Failed to fetch OpenRouter pricing: {e}")
   147|    
   148|    return {}
   149|
   150|
   151|MODEL_PRICING = {
   152|    # Anthropic
   153|    "claude-haiku-4-5": {"credits_per_1m": 197, "display_per_1m": 1.97},
   154|    "claude-sonnet-4-5": {"credits_per_1m": 741, "display_per_1m": 7.41},
   155|    "claude-opus-4-5": {"credits_per_1m": 3703, "display_per_1m": 37.03},
   156|    # OpenAI
   157|    "gpt-4o": {"credits_per_1m": 549, "display_per_1m": 5.49},
   158|    "gpt-4o-mini": {"credits_per_1m": 33, "display_per_1m": 0.33},
   159|    "gpt-5": {"credits_per_1m": 1000, "display_per_1m": 10.00},
   160|    "o1-preview": {"credits_per_1m": 2000, "display_per_1m": 20.00},
   161|    "o1-mini": {"credits_per_1m": 500, "display_per_1m": 5.00},
   162|    # MiniMax (via OpenRouter)
   163|    "minimax-m2.7": {"credits_per_1m": 50, "display_per_1m": 0.50},
   164|    "minimax-m2.5": {"credits_per_1m": 40, "display_per_1m": 0.40},
   165|    "minimax-01": {"credits_per_1m": 45, "display_per_1m": 0.45},
   166|    # Google
   167|    "gemini-2.0-flash": {"credits_per_1m": 22, "display_per_1m": 0.22},
   168|}
   169|
   170|
   171|# ============================================================================
   172|# HELPER FUNCTIONS - Prevent float precision errors
   173|# ============================================================================
   174|
   175|def dollars_to_cents(dollars: float) -> int:
   176|    """Convert dollars to cents (integer)."""
   177|    return round(float(dollars) * 100)
   178|
   179|
   180|def cents_to_dollars(cents: int) -> float:
   181|    """Convert cents to dollars."""
   182|    return cents / 100
   183|
   184|
   185|def get_db_connection():
   186|    """Get database connection - no hardcoded credentials."""
   187|    db_url = os.environ.get("DATABASE_URL", "")
   188|    if db_url:
   189|        result = urlparse(db_url)
   190|        return psycopg2.connect(
   191|            host=result.hostname,
   192|            port=result.port or 5432,
   193|            database=result.path.lstrip("/") if result.path else "nexusos",
   194|            user=result.username,
   195|            password=result.password
   196|        )
   197|    # Fallback to individual env vars
   198|    return psycopg2.connect(
   199|        host=os.environ.get("POSTGRES_HOST", "lipaira-postgres"),
   200|        database=os.environ.get("POSTGRES_DB", "lipaira"),
   201|        user=os.environ.get("POSTGRES_USER", "lipaira"),
   202|        password=os.environ.get("POSTGRES_PASSWORD")
   203|    )
   204|
   205|
   206|# ============================================================================
   207|# CORE BILLING FUNCTIONS
   208|# ============================================================================
   209|
   210|def calculate_inference_cost(model: str, input_tokens: int, output_tokens: int) -> int:
   211|    """
   212|    Calculate inference cost in credits.
   213|    
   214|    From spec: OpenRouter cost × 1.30 markup
   215|    Returns cost in credits (1 credit = $0.01)
   216|    """
   217|    pricing = MODEL_PRICING.get(model)
   218|    if not pricing:
   219|        # Default to sonnet pricing if unknown
   220|        pricing = MODEL_PRICING["claude-sonnet-4-5"]
   221|    
   222|    total_tokens = input_tokens + output_tokens
   223|    credits = (total_tokens * pricing["credits_per_1m"]) // 1_000_000
   224|    
   225|    # Minimum 1 credit
   226|    return max(credits, 1)
   227|
   228|
   229|def calculate_infrastructure_cost() -> int:
   230|    """
   231|    Calculate infrastructure surcharge.
   232|    
   233|    From spec: 0.5 credits ($0.005) per generation
   234|    Rounded up to nearest cent = 1 cent
   235|    """
   236|    return INFRASTRUCTURE_PER_CALL_CENTS
   237|
   238|
   239|def get_agent_daily_cost(agent_type: str) -> int:
   240|    """Get daily cost for an agent type (in credits)."""
   241|    return AGENT_PRICING.get(agent_type, {}).get("daily_cents", 0)
   242|
   243|
   244|def get_agent_count_discount(agent_count: int) -> float:
   245|    """Get bundle discount for number of specialist agents."""
   246|    if agent_count >= 4:
   247|        return BUNDLE_DISCOUNTS[4]
   248|    return BUNDLE_DISCOUNTS.get(agent_count, 0)
   249|
   250|
   251|def get_credit_packages() -> List[Dict]:
   252|    """Get available credit purchase packages."""
   253|    return CREDIT_PACKAGES
   254|
   255|
   256|def calculate_package_credits(amount_cents: int) -> Dict:
   257|    """Calculate credits for a given payment amount."""
   258|    # Find best package or calculate custom
   259|    for pkg in CREDIT_PACKAGES:
   260|        if amount_cents == pkg["amount_cents"]:
   261|            return {
   262|                "credits": pkg["credits"],
   263|                "discount": pkg["discount"],
   264|                "amount_paid": amount_cents,
   265|            }
   266|    
   267|    # Custom amount: linear (1 credit per cent)
   268|    return {
   269|        "credits": amount_cents,
   270|        "discount": 0,
   271|        "amount_paid": amount_cents,
   272|    }
   273|
   274|
   275|def can_use_service(balance_cents: int) -> Dict:
   276|    """
   277|    Check if user can use service based on balance.
   278|    
   279|    From spec:
   280|    - balance > 0: full access
   281|    - balance <= 0 but > -500: grace buffer (complete current, no new)
   282|    - balance <= -500: paused
   283|    """
   284|    if balance_cents > 0:
   285|        return {"allowed": True, "status": "active", "message": None}
   286|    elif balance_cents > GRACE_BUFFER_CENTS:
   287|        return {"allowed": True, "status": "grace", "message": "Balance low — add credits to continue"}
   288|    else:
   289|        return {"allowed": False, "status": "paused", "message": "Activity paused — add credits to resume"}
   290|
   291|
   292|def get_daily_burn_rate(active_agents: List[str], avg_calls_per_day: int = 100) -> int:
   293|    """
   294|    Calculate estimated daily burn rate.
   295|    
   296|    Args:
   297|        active_agents: List of active agent types (e.g., ["primary", "finance"])
   298|        avg_calls_per_day: Estimated API calls per day
   299|    """
   300|    # Agent fees
   301|    agent_cost = 0
   302|    specialist_count = 0
   303|    for agent in active_agents:
   304|        if agent == "primary":
   305|            agent_cost += AGENT_PRICING["primary"]["daily_cents"]
   306|        else:
   307|            specialist_count += 1
   308|    
   309|    # Apply bundle discount
   310|    if specialist_count > 1:
   311|        discount = get_agent_count_discount(specialist_count)
   312|        specialist_cost = sum(AGENT_PRICING.get(a, {}).get("daily_cents", 0) 
   313|                             for a in active_agents if a != "primary")
   314|        agent_cost += int(specialist_cost * (1 - discount))
   315|    
   316|    # Infrastructure
   317|    infra_cost = avg_calls_per_day * INFRASTRUCTURE_PER_CALL_CENTS
   318|    
   319|    # Assume haiku as default (cheapest)
   320|    inference_cost = avg_calls_per_day * 1  # ~1 credit per call average
   321|    
   322|    return agent_cost + infra_cost + inference_cost
   323|
   324|
   325|def get_runway_days(balance_cents: int, daily_burn: int) -> Optional[int]:
   326|    """Calculate days of runway at current burn rate."""
   327|    if daily_burn <= 0:
   328|        return None
   329|    return balance_cents // daily_burn
   330|
   331|
   332|# ============================================================================
   333|# DATABASE OPERATIONS
   334|# ============================================================================
   335|
   336|def add_credits(user_id: str, credits: int, source: str = "purchase") -> bool:
   337|    """Add credits to user account."""
   338|    conn = get_db_connection()
   339|    cur = conn.cursor()
   340|    
   341|    try:
   342|        # Get current balance
   343|        cur.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
   344|        row = cur.fetchone()
   345|        current_cents = dollars_to_cents(float(row[0])) if row else 0
   346|        
   347|        new_balance_cents = current_cents + credits
   348|        
   349|        cur.execute(
   350|            "UPDATE users SET credits = %s WHERE id = %s",
   351|            (cents_to_dollars(new_balance_cents), user_id)
   352|        )
   353|        
   354|        # Record transaction
   355|        cur.execute("""
   356|            INSERT INTO credit_transactions 
   357|            (id, user_id, amount, transaction_type, source, created_at)
   358|            VALUES (%s, %s, %s, %s, %s, %s)
   359|        """, (str(uuid.uuid4()), user_id, cents_to_dollars(credits), 
   360|              "credit_add", source, datetime.utcnow()))
   361|        
   362|        conn.commit()
   363|        return True
   364|    except Exception as e:
   365|        logger.error(f"Error adding credits: {e}")
   366|        conn.rollback()
   367|        return False
   368|    finally:
   369|        cur.close()
   370|        conn.close()
   371|
   372|
   373|def deduct_usage(user_id: str, model: str, input_tokens: int, output_tokens: int) -> Dict:
   374|    """
   375|    Deduct usage from user balance.
   376|    
   377|    Components:
   378|    1. Inference cost (per token, marked up)
   379|    2. Infrastructure surcharge (per call)
   380|    
   381|    Returns: {"success": bool, "cost": int, "balance_remaining": int}
   382|    """
   383|    # Calculate costs
   384|    inference_cost = calculate_inference_cost(model, input_tokens, output_tokens)
   385|    infra_cost = calculate_infrastructure_cost()
   386|    total_cost = inference_cost + infra_cost
   387|    
   388|    conn = get_db_connection()
   389|    cur = conn.cursor()
   390|    
   391|    try:
   392|        # Get current balance in cents
   393|        cur.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
   394|        row = cur.fetchone()
   395|        if not row:
   396|            return {"success": False, "error": "User not found"}
   397|        
   398|        balance_cents = dollars_to_cents(float(row[0]))
   399|        
   400|        # Check if can use service
   401|        can_use = can_use_service(balance_cents)
   402|        if not can_use["allowed"]:
   403|            return {
   404|                "success": False, 
   405|                "error": can_use["message"],
   406|                "status": can_use["status"]
   407|            }
   408|        
   409|        new_balance_cents = balance_cents - total_cost
   410|        
   411|        # Update balance
   412|        cur.execute(
   413|            "UPDATE users SET credits = %s WHERE id = %s",
   414|            (cents_to_dollars(new_balance_cents), user_id)
   415|        )
   416|        
   417|        # Record usage
   418|        cur.execute("""
   419|            INSERT INTO llm_usage 
   420|            (id, user_id, model, input_tokens, output_tokens, cost, created_at)
   421|            VALUES (%s, %s, %s, %s, %s, %s, %s)
   422|        """, (str(uuid.uuid4()), user_id, model, 
   423|              input_tokens, output_tokens, cents_to_dollars(total_cost), datetime.utcnow()))
   424|        
   425|        conn.commit()
   426|        
   427|        return {
   428|            "success": True,
   429|            "cost": total_cost,
   430|            "inference_cost": inference_cost,
   431|            "infrastructure_cost": infra_cost,
   432|            "balance_remaining": new_balance_cents,
   433|            "status": can_use["status"]
   434|        }
   435|        
   436|    except Exception as e:
   437|        logger.error(f"Error deducting usage: {e}")
   438|        conn.rollback()
   439|        return {"success": False, "error": str(e)}
   440|    finally:
   441|        cur.close()
   442|        conn.close()
   443|
   444|
   445|def get_user_balance_cents(user_id: str) -> int:
   446|    """Get user balance in cents."""
   447|    conn = get_db_connection()
   448|    cur = conn.cursor()
   449|    
   450|    try:
   451|        cur.execute("SELECT credits FROM users WHERE id = %s", (user_id,))
   452|        row = cur.fetchone()
   453|        if row:
   454|            return dollars_to_cents(float(row[0]))
   455|        return 0
   456|    finally:
   457|        cur.close()
   458|        conn.close()
   459|
   460|
   461|def get_user_billing_info(user_id: str) -> Dict:
   462|    """Get comprehensive billing info for user."""
   463|    balance_cents = get_user_balance_cents(user_id)
   464|    can_use = can_use_service(balance_cents)
   465|    
   466|    # Get active agents (would come from user_profiles or similar)
   467|    # For now, assume primary only
   468|    active_agents = ["primary"]
   469|    
   470|    # Calculate burn rate
   471|    daily_burn = get_daily_burn_rate(active_agents)
   472|    runway = get_runway_days(balance_cents, daily_burn)
   473|    
   474|    return {
   475|        "balance_cents": balance_cents,
   476|        "balance_display": f"${cents_to_dollars(balance_cents):.2f}",
   477|        "status": can_use["status"],
   478|        "message": can_use["message"],
   479|        "daily_burn_cents": daily_burn,
   480|        "daily_burn_display": f"${cents_to_dollars(daily_burn):.2f}/day",
   481|        "runway_days": runway,
   482|        "runway_display": f"{runway} days" if runway else "N/A",
   483|    }
   484|
   485|
   486|# ============================================================================
   487|# INITIALIZATION
   488|# ============================================================================
   489|
   490|def init_billing_tables():
   491|    """Create billing-related tables if they don't exist."""
   492|    conn = get_db_connection()
   493|    cur = conn.cursor()
   494|    
   495|    # Credit transactions table
   496|    cur.execute("""
   497|        CREATE TABLE IF NOT EXISTS credit_transactions (
   498|            id TEXT PRIMARY KEY,
   499|            user_id TEXT NOT NULL,
   500|            amount REAL NOT NULL,
   501|