# feel free to ignore this comment
"""
Federated User Intelligence
===========================
Anonymized benchmarking for users - disabled until 5+ users opt-in.
Requires: user_profiles with business_type, location, federated_opt_in.

Contract: Block 4 Item 18
"""

# federated_intelligence.py - Federated User Intelligence
     6|
     7|import os
     8|import json
     9|from typing import Dict, Any, Optional, List
    10|import psycopg2
    11|
    12|MIN_COHORT_SIZE = 5  # Minimum users required before surfacing any aggregates
    13|
    14|class FederatedIntelligence:
    15|    """Privacy-preserving federated intelligence for benchmarking."""
    16|    
    17|    def __init__(self, db_url: str = None):
    18|        self.db_url = db_url or os.environ.get('DATABASE_URL')
    19|        self._enabled = False  # Disabled by default until sufficient users
    20|        
    21|    def is_enabled(self) -> bool:
    22|        """Check if federated intelligence is enabled."""
    23|        if not self._enabled:
    24|            return False
    25|            
    26|        # Check minimum cohort size
    27|        count = self._get_opted_in_user_count()
    28|        if count < MIN_COHORT_SIZE:
    29|            return False
    30|        return True
    31|        
    32|    def _get_opted_in_user_count(self) -> int:
    33|        """Get count of users who have opted into federated intelligence."""
    34|        try:
    35|            conn = psycopg2.connect(self.db_url)
    36|            cursor = conn.cursor()
    37|            cursor.execute("""
    38|                SELECT COUNT(*) FROM user_profiles 
    39|                WHERE federated_opt_in = true 
    40|                AND business_type IS NOT NULL
    41|                AND location IS NOT NULL
    42|            """)
    43|            count = cursor.fetchone()[0]
    44|            conn.close()
    45|            return count
    46|        except Exception as e:
    47|            print(f"Error checking opt-in count: {e}")
    48|            return 0
    49|            
    50|    def enable(self):
    51|        """Manually enable (admin only)."""
    52|        self._enabled = True
    53|        
    54|    def disable(self):
    55|        """Manually disable."""
    56|        self._enabled = False
    57|        
    58|    def opt_in_user(self, user_id: str) -> bool:
    59|        """Opt a user into federated intelligence."""
    60|        try:
    61|            conn = psycopg2.connect(self.db_url)
    62|            cursor = conn.cursor()
    63|            cursor.execute("""
    64|                UPDATE user_profiles 
    65|                SET federated_opt_in = true 
    66|                WHERE user_id = %s
    67|            """, (user_id,))
    68|            conn.commit()
    69|            conn.close()
    70|            return True
    71|        except Exception as e:
    72|            print(f"Error opting in user: {e}")
    73|            return False
    74|            
    75|    def opt_out_user(self, user_id: str) -> bool:
    76|        """Opt a user out of federated intelligence."""
    77|        try:
    78|            conn = psycopg2.connect(self.db_url)
    79|            cursor = conn.cursor()
    80|            cursor.execute("""
    81|                UPDATE user_profiles 
    82|                SET federated_opt_in = false 
    83|                WHERE user_id = %s
    84|            """, (user_id,))
    85|            conn.commit()
    86|            conn.close()
    87|            return True
    88|        except Exception as e:
    89|            print(f"Error opting out user: {e}")
    90|            return False
    91|            
    92|    def benchmark(self, user_id: str, query_type: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
    93|        """
    94|        Query anonymized aggregates for benchmarking.
    95|        
    96|        query_type: 'hourly_rate', 'payment_terms', 'service_type', etc.
    97|        filters: {'business_type': 'plumber', 'location': 'Columbus'}
    98|        
    99|        Returns anonymized aggregate - never exposes individual data.
   100|        """
   101|        # Check if enabled
   102|        if not self.is_enabled():
   103|            return {
   104|                'available': False,
   105|                'reason': f'Not enough users to enable benchmarking. Need {MIN_COHORT_SIZE}+, have {self._get_opted_in_user_count()}.'
   106|            }
   107|            
   108|        # Build query based on type
   109|        if query_type == 'hourly_rate':
   110|            return self._benchmark_hourly_rate(user_id, filters)
   111|        elif query_type == 'payment_terms':
   112|            return self._benchmark_payment_terms(user_id, filters)
   113|        else:
   114|            return {'error': f'Unknown query_type: {query_type}'}
   115|            
   116|    def _benchmark_hourly_rate(self, user_id: str, filters: Optional[Dict]) -> Dict[str, Any]:
   117|        """Benchmark hourly rates - anonymized."""
   118|        try:
   119|            conn = psycopg2.connect(self.db_url)
   120|            cursor = conn.cursor()
   121|            
   122|            # Get user's own rate (excluded from aggregate)
   123|            cursor.execute("""
   124|                SELECT context->>'hourly_rate' as rate 
   125|                FROM user_profiles 
   126|                WHERE user_id = %s
   127|            """, (user_id,))
   128|            user_row = cursor.fetchone()
   129|            user_rate = float(user_row[0]) if user_row and user_row[0] else None
   130|            
   131|            # Build cohort query (excluding user)
   132|            sql = """
   133|                SELECT 
   134|                    COUNT(*) as cohort_size,
   135|                    MIN((context->>'hourly_rate')::numeric) as min_rate,
   136|                    MAX((context->>'hourly_rate')::numeric) as max_rate,
   137|                    AVG((context->>'hourly_rate')::numeric) as avg_rate,
   138|                    PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY (context->>'hourly_rate')::numeric) as median_rate
   139|                FROM user_profiles
   140|                WHERE federated_opt_in = true
   141|                AND context->>'hourly_rate' IS NOT NULL
   142|                AND user_id != %s
   143|            """
   144|            params = [user_id]
   145|            
   146|            if filters:
   147|                if 'business_type' in filters:
   148|                    sql += " AND business_type = %s"
   149|                    params.append(filters['business_type'])
   150|                if 'location' in filters:
   151|                    sql += " AND location = %s"
   152|                    params.append(filters['location'])
   153|                    
   154|            cursor.execute(sql, params)
   155|            row = cursor.fetchone()
   156|            conn.close()
   157|            
   158|            if not row or row[0] < MIN_COHORT_SIZE:
   159|                return {
   160|                    'available': False,
   161|                    'cohort_size': row[0] if row else 0,
   162|                    'reason': f'Not enough users in cohort (need {MIN_COHORT_SIZE})'
   163|                }
   164|                
   165|            # Return anonymized aggregate (no individual data)
   166|            return {
   167|                'available': True,
   168|                'cohort_size': row[0],
   169|                'rate_range': f'${int(row[1])}-${int(row[2])}/hr',
   170|                'median_rate': f'${int(row[4])}/hr' if row[4] else None,
   171|                'your_rate': f'${int(user_rate)}/hr' if user_rate else 'Not set',
   172|                'your_position': self._calculate_position(user_rate, row[1], row[2]) if user_rate else 'N/A'
   173|            }
   174|            
   175|        except Exception as e:
   176|            return {'error': str(e)}
   177|            
   178|    def _benchmark_payment_terms(self, user_id: str, filters: Optional[Dict]) -> Dict[str, Any]:
   179|        """Benchmark payment terms - anonymized."""
   180|        # Similar structure to hourly_rate
   181|        # Would query billing_history for payment patterns
   182|        return {'available': False, 'reason': 'Not implemented yet'}
   183|        
   184|    def _calculate_position(self, user_value: float, min_val: float, max_val: float) -> str:
   185|        """Calculate user's position in the cohort."""
   186|        if max_val == min_val:
   187|            return 'Average'
   188|        position = (user_value - min_val) / (max_val - min_val)
   189|        if position < 0.33:
   190|            return 'Below average'
   191|        elif position > 0.66:
   192|            return 'Above average'
   193|        return 'Average'
   194|        
   195|    def log_query(self, user_id: str, query_type: str, result_available: bool):
   196|        """Log all queries for SOC 2 audit trail."""
   197|        try:
   198|            conn = psycopg2.connect(self.db_url)
   199|            cursor = conn.cursor()
   200|            cursor.execute("""
   201|                INSERT INTO audit_logs (user_id, action, details, created_at)
   202|                VALUES (%s, 'federated_query', %s, NOW())
   203|            """, (user_id, json.dumps({'query_type': query_type, 'result_available': result_available})))
   204|            conn.commit()
   205|            conn.close()
   206|        except Exception as e:
   207|            print(f"Failed to log federated query: {e}")
   208|
   209|
   210|# Global instance
   211|_federated: Optional[FederatedIntelligence] = None
   212|
   213|def get_federated() -> FederatedIntelligence:
   214|    """Get the global federated intelligence instance."""
   215|    global _federated
   216|    if _federated is None:
   217|        _federated = FederatedIntelligence()
   218|    return _federated