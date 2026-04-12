# feel free to ignore this comment
     1|"""
     2|Background Tasks - Scheduled maintenance jobs
     3|==============================================
     4|Runs as daemon threads when the server starts.
     5|"""
     6|
     7|import os
     8|import logging
     9|import threading
    10|import time
    11|from datetime import datetime, timezone, timedelta
    12|from typing import Dict
    13|
    14|logger = logging.getLogger(__name__)
    15|
    16|# Import billing for sweep function
    17|try:
    18|    import billing
    19|except ImportError:
    20|    billing = None
    21|
    22|
    23|def _run_billing_sweep_loop():
    24|    """Run billing sweep daily at midnight UTC."""
    25|    while True:
    26|        now = datetime.now(timezone.utc)
    27|        next_midnight = now.replace(
    28|            hour=0, minute=0, second=0, microsecond=0
    29|        )
    30|        if next_midnight <= now:
    31|            next_midnight += timedelta(days=1)
    32|
    33|        sleep_seconds = (next_midnight - now).total_seconds()
    34|        logger.info(f"Next billing sweep in {sleep_seconds/3600:.1f} hours")
    35|        time.sleep(sleep_seconds)
    36|
    37|        try:
    38|            # Call our own API endpoint
    39|            # Container calls itself via internal network
    40|            base_url = os.environ.get(
    41|                'INTERNAL_API_URL', 'http://localhost:8080'
    42|            )
    43|            import requests
    44|            resp = requests.post(
    45|                f"{base_url}/api/billing/sweep",
    46|                headers={
    47|                    'X-Internal-Key': os.environ.get('INTERNAL_KEY'),
    48|                    'Content-Type': 'application/json'
    49|                },
    50|                json={},
    51|                timeout=60
    52|            )
    53|            if resp.ok:
    54|                logger.info(f"Billing sweep complete: {resp.json()}")
    55|            else:
    56|                logger.error(f"Billing sweep failed: {resp.status_code}")
    57|        except Exception as e:
    58|            logger.error(f"Billing sweep error: {e}")
    59|
    60|
    61|def _run_memory_sweep_loop():
    62|    """Run memory sweep daily at 6am UTC."""
    63|    while True:
    64|        now = datetime.now(timezone.utc)
    65|        next_6am = now.replace(hour=6, minute=0, second=0, microsecond=0)
    66|        if next_6am <= now:
    67|            next_6am += timedelta(days=1)
    68|
    69|        sleep_seconds = (next_6am - now).total_seconds()
    70|        logger.info(f"Next memory sweep in {sleep_seconds/3600:.1f} hours")
    71|        time.sleep(sleep_seconds)
    72|
    73|        try:
    74|            base_url = os.environ.get(
    75|                'INTERNAL_API_URL', 'http://localhost:8080'
    76|            )
    77|            import requests
    78|            # Get all users and run memory sweep for each
    79|            # For now, just log that we'd do this
    80|            logger.info("Memory sweep: would process all users")
    81|        except Exception as e:
    82|            logger.error(f"Memory sweep error: {e}")
    83|
    84|
    85|def _run_workflow_scheduler_loop():
    86|    """Check for and run scheduled workflows - optimized version."""
    87|    import requests
    88|    
    89|    # Import croniter for cron parsing
    90|    try:
    91|        from croniter import croniter
    92|    except ImportError:
    93|        logger.warning("croniter not installed, workflow scheduler disabled")
    94|        return
    95|    
    96|    # Cache of workflow next_run times (refresh every 5 minutes)
    97|    workflow_cache = []
    98|    cache_refreshed = 0
    99|    CACHE_TTL = 300  # 5 minutes
   100|    
   101|    while True:
   102|        try:
   103|            now = datetime.now()
   104|            
   105|            # Refresh cache periodically
   106|            if not workflow_cache or (now.timestamp() - cache_refreshed) > CACHE_TTL:
   107|                import psycopg2
   108|                import os
   109|                db_url = os.environ.get('DATABASE_URL')
   110|                if not db_url:
   111|                    raise RuntimeError('DATABASE_URL is required')
   112|                conn = psycopg2.connect(db_url)
   113|                
   114|                with conn:
   115|                    with conn.cursor() as cur:
   116|                        cur.execute("""
   117|                            SELECT w.id, w.user_id, w.name, w.trigger_config, 
   118|                                   w.steps, w.next_run_at, w.enabled
   119|                            FROM workflows w
   120|                            WHERE w.trigger_type = 'scheduled' 
   121|                            AND w.enabled = true
   122|                            AND w.next_run_at IS NOT NULL
   123|                        """)
   124|                        workflow_cache = cur.fetchall()
   125|                
   126|                cache_refreshed = now.timestamp()
   127|                logger.info(f"Workflow cache refreshed: {len(workflow_cache)} scheduled workflows")
   128|            
   129|            # Only check workflows due to run now
   130|            for wf in workflow_cache:
   131|                workflow_id, user_id, name, trigger_config, steps, next_run, enabled = wf
   132|                
   133|                if not enabled or not next_run:
   134|                    continue
   135|                
   136|                # Check if it's time to run (within 60 seconds)
   137|                if isinstance(next_run, str):
   138|                    next_run = datetime.fromisoformat(next_run)
   139|                
   140|                time_diff = (next_run - now).total_seconds()
   141|                
   142|                if 0 <= time_diff <= 60:
   143|                    logger.info(f"Running scheduled workflow: {name}")
   144|                    
   145|                    # Execute via DB (no API call needed)
   146|                    try:
   147|                        import psycopg2
   148|                        import os
   149|                        db_url = os.environ.get('DATABASE_URL')
   150|                        if not db_url:
   151|                            raise RuntimeError('DATABASE_URL is required')
   152|                        conn = psycopg2.connect(db_url)
   153|                        
   154|                        # Get user API key
   155|                        with conn:
   156|                            with conn.cursor() as cur:
   157|                                cur.execute("""
   158|                                    SELECT api_key FROM api_keys 
   159|                                    WHERE user_id = %s AND active = true
   160|                                    LIMIT 1
   161|                                """, (user_id,))
   162|                                key_row = cur.fetchone()
   163|                        
   164|                        if key_row:
   165|                            api_key = key_row[0]
   166|                            
   167|                            # Execute workflow directly (inline, no API call)
   168|                            result = _execute_workflow_inline(workflow_id, steps, user_id)
   169|                            
   170|                            # Update next_run and run_count
   171|                            # Parse cron for next run time
   172|                            cron_expr = trigger_config.get('cron') if isinstance(trigger_config, dict) else None
   173|                            if cron_expr:
   174|                                try:
   175|                                    cron = croniter(cron_expr, now)
   176|                                    new_next = cron.get_next(datetime)
   177|                                    
   178|                                    with get_user_conn() as conn:
   179|                                        with conn.cursor() as cur:
   180|                                            cur.execute("""
   181|                                                UPDATE workflows 
   182|                                                SET last_run_at = NOW(),
   183|                                                    run_count = run_count + 1,
   184|                                                    next_run_at = %s,
   185|                                                    updated_at = NOW()
   186|                                                WHERE id = %s
   187|                                            """, (new_next, workflow_id))
   188|                                            conn.commit()
   189|                                except Exception as e:
   190|                                    logger.error(f"Failed to update next_run for {name}: {e}")
   191|                            
   192|                            logger.info(f"Workflow {name} executed: {result.get('success', False)}")
   193|                        else:
   194|                            logger.warning(f"No API key for user {user_id}")
   195|                    
   196|                    except Exception as e:
   197|                        logger.error(f"Error executing workflow {name}: {e}")
   198|                    
   199|                    # Remove from cache so we don't run again this cycle
   200|                    workflow_cache = [w for w in workflow_cache if w[0] != workflow_id]
   201|                    
   202|        except Exception as e:
   203|            logger.error(f"Workflow scheduler error: {e}")
   204|        
   205|        # Check every 30 seconds (not every minute)
   206|        time.sleep(30)
   207|
   208|
   209|def _execute_workflow_inline(workflow_id, steps, user_id):
   210|    """Execute workflow directly without API call - saves tokens."""
   211|    import asyncio
   212|    
   213|    from operator_layer.workflow_engine import WorkflowExecutor, WorkflowStep, StepType
   214|    
   215|    # Parse steps
   216|    step_objects = []
   217|    for step_data in (steps if isinstance(steps, list) else []):
   218|        step = WorkflowStep(
   219|            id=step_data.get('id', f'step_{len(step_objects)}'),
   220|            type=StepType(step_data.get('type', 'action')),
   221|            description=step_data.get('description', ''),
   222|            integration=step_data.get('integration'),
   223|            operation=step_data.get('operation'),
   224|            params=step_data.get('params', {})
   225|        )
   226|        step_objects.append(step)
   227|    
   228|    # Set up executors
   229|    executors = {}
   230|    
   231|    # Resend email
   232|    def send_email(**params):
   233|        from lipaira_client.skills.email_send_skill import EmailSendSkill
   234|        skill = EmailSendSkill()
   235|        result = skill.execute({
   236|            'to': params.get('to'),
   237|            'subject': params.get('subject'),
   238|            'body': params.get('body'),
   239|            'from_name': params.get('from_name', 'Lipaira')
   240|        })
   241|        return result.output if result.output else {'success': result.success}
   242|    
   243|    executors['resend'] = send_email
   244|    
   245|    # QuickBooks
   246|    try:
   247|        from lipaira_client.skills.quickbooks_client import qb_query
   248|        executors['quickbooks'] = qb_query
   249|    except:
   250|        pass
   251|    
   252|    executor = WorkflowExecutor(user_id, executors)
   253|    
   254|    try:
   255|        loop = asyncio.get_event_loop()
   256|    except:
   257|        loop = asyncio.new_event_loop()
   258|        asyncio.set_event_loop(loop)
   259|    
   260|    return loop.run_until_complete(
   261|        executor.execute_workflow(step_objects, {})
   262|    )
   263|
   264|
   265|def start_background_tasks():
   266|    """Start all background maintenance threads."""
   267|    # Start billing sweep
   268|    threading.Thread(
   269|        target=_run_billing_sweep_loop,
   270|        name="billing-sweep",
   271|        daemon=True
   272|    ).start()
   273|
   274|    # Start memory sweep
   275|    threading.Thread(
   276|        target=_run_memory_sweep_loop,
   277|        name="memory-sweep",
   278|        daemon=True
   279|    ).start()
   280|
   281|    # Start workflow scheduler
   282|    threading.Thread(
   283|        target=_run_workflow_scheduler_loop,
   284|        name="workflow-scheduler",
   285|        daemon=True
   286|    ).start()
   287|
   288|    logger.info("Background tasks started")
   289|
   290|
   291|if __name__ == "__main__":
   292|    # For testing: run once
   293|    logging.basicConfig(level=logging.INFO)
   294|    _run_billing_sweep_loop()