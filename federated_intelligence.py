# federated_intelligence.py - Federated User Intelligence
#
# Contract: Block 4 Item 18
# Anonymized benchmarking for users - disabled until 5+ users opt-in
# Requires: user_profiles with business_type, location, federated_opt_in

import os
import json
from typing import Dict, Any, Optional, List
import psycopg2

MIN_COHORT_SIZE = 5  # Minimum users required
PRIVACY_GUARD_ENABLED = False  # Must be True after privacy review before enabling before surfacing any aggregates

class FederatedIntelligence:
    """Privacy-preserving federated intelligence for benchmarking."""
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.environ.get('DATABASE_URL')
        self._enabled = False  # Disabled by default until sufficient users
        
    def is_enabled(self) -> bool:
        """Check if federated intelligence is enabled.
        
        Returns False unless:
        1. PRIVACY_GUARD_ENABLED is True (privacy review completed)
        2. Manual _enabled flag is True
        3. Minimum cohort size (5) is met
        """
        if not self._enabled:
            return False
        
        # Privacy guard - must be enabled after review
        if not PRIVACY_GUARD_ENABLED:
            return False
            
        # Check minimum cohort size
        count = self._get_opted_in_user_count()
        if count < MIN_COHORT_SIZE:
            return False
        return True
        
    def _get_opted_in_user_count(self) -> int:
        """Get count of users who have opted into federated intelligence."""
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM user_profiles 
                WHERE federated_opt_in = true 
                AND business_type IS NOT NULL
                AND location IS NOT NULL
            """)
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            print(f"Error checking opt-in count: {e}")
            return 0
            
    def enable(self):
        """Manually enable (admin only).
        
        Raises NotImplementedError if privacy review has not been completed.
        """
        if not PRIVACY_GUARD_ENABLED:
            raise NotImplementedError(
                'Privacy review required before enabling federated intelligence. '
                'Set PRIVACY_GUARD_ENABLED = True after completing privacy review.'
            )
        self._enabled = True
        
    def disable(self):
        """Manually disable."""
        self._enabled = False
        
    def opt_in_user(self, user_id: str) -> bool:
        """Opt a user into federated intelligence."""
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_profiles 
                SET federated_opt_in = true 
                WHERE user_id = %s
            """, (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error opting in user: {e}")
            return False
            
    def opt_out_user(self, user_id: str) -> bool:
        """Opt a user out of federated intelligence."""
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_profiles 
                SET federated_opt_in = false 
                WHERE user_id = %s
            """, (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error opting out user: {e}")
            return False
            
    def benchmark(self, user_id: str, query_type: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Query anonymized aggregates for benchmarking.
        
        query_type: 'hourly_rate', 'payment_terms', 'service_type', etc.
        filters: {'business_type': 'plumber', 'location': 'Columbus'}
        
        Returns anonymized aggregate - never exposes individual data.
        """
        # Check if enabled
        if not self.is_enabled():
            return {
                'available': False,
                'reason': f'Not enough users to enable benchmarking. Need {MIN_COHORT_SIZE}+, have {self._get_opted_in_user_count()}.'
            }
            
        # Build query based on type
        if query_type == 'hourly_rate':
            return self._benchmark_hourly_rate(user_id, filters)
        elif query_type == 'payment_terms':
            return self._benchmark_payment_terms(user_id, filters)
        else:
            return {'error': f'Unknown query_type: {query_type}'}
            
    def _benchmark_hourly_rate(self, user_id: str, filters: Optional[Dict]) -> Dict[str, Any]:
        """Benchmark hourly rates - anonymized."""
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            # Get user's own rate (excluded from aggregate)
            cursor.execute("""
                SELECT context->>'hourly_rate' as rate 
                FROM user_profiles 
                WHERE user_id = %s
            """, (user_id,))
            user_row = cursor.fetchone()
            user_rate = float(user_row[0]) if user_row and user_row[0] else None
            
            # Build cohort query (excluding user)
            sql = """
                SELECT 
                    COUNT(*) as cohort_size,
                    MIN((context->>'hourly_rate')::numeric) as min_rate,
                    MAX((context->>'hourly_rate')::numeric) as max_rate,
                    AVG((context->>'hourly_rate')::numeric) as avg_rate,
                    PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY (context->>'hourly_rate')::numeric) as median_rate
                FROM user_profiles
                WHERE federated_opt_in = true
                AND context->>'hourly_rate' IS NOT NULL
                AND user_id != %s
            """
            params = [user_id]
            
            if filters:
                if 'business_type' in filters:
                    sql += " AND business_type = %s"
                    params.append(filters['business_type'])
                if 'location' in filters:
                    sql += " AND location = %s"
                    params.append(filters['location'])
                    
            cursor.execute(sql, params)
            row = cursor.fetchone()
            conn.close()
            
            if not row or row[0] < MIN_COHORT_SIZE:
                return {
                    'available': False,
                    'cohort_size': row[0] if row else 0,
                    'reason': f'Not enough users in cohort (need {MIN_COHORT_SIZE})'
                }
                
            # Return anonymized aggregate (no individual data)
            return {
                'available': True,
                'cohort_size': row[0],
                'rate_range': f'${int(row[1])}-${int(row[2])}/hr',
                'median_rate': f'${int(row[4])}/hr' if row[4] else None,
                'your_rate': f'${int(user_rate)}/hr' if user_rate else 'Not set',
                'your_position': self._calculate_position(user_rate, row[1], row[2]) if user_rate else 'N/A'
            }
            
        except Exception as e:
            return {'error': str(e)}
            
    def _benchmark_payment_terms(self, user_id: str, filters: Optional[Dict]) -> Dict[str, Any]:
        """Benchmark payment terms - anonymized."""
        # Similar structure to hourly_rate
        # Would query billing_history for payment patterns
        return {'available': False, 'reason': 'Not implemented yet'}
        
    def _calculate_position(self, user_value: float, min_val: float, max_val: float) -> str:
        """Calculate user's position in the cohort."""
        if max_val == min_val:
            return 'Average'
        position = (user_value - min_val) / (max_val - min_val)
        if position < 0.33:
            return 'Below average'
        elif position > 0.66:
            return 'Above average'
        return 'Average'
        
    def log_query(self, user_id: str, query_type: str, result_available: bool):
        """Log all queries for SOC 2 audit trail."""
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs (user_id, action, details, created_at)
                VALUES (%s, 'federated_query', %s, NOW())
            """, (user_id, json.dumps({'query_type': query_type, 'result_available': result_available})))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to log federated query: {e}")


# Global instance
_federated: Optional[FederatedIntelligence] = None

def get_federated() -> FederatedIntelligence:
    """Get the global federated intelligence instance."""
    global _federated
    if _federated is None:
        _federated = FederatedIntelligence()
    return _federated