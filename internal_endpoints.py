"""
Internal endpoints module - Federated Intelligence opt-in/out endpoints
"""
import os
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)

def create_internal_routes(app):
    """Register internal routes including federated intelligence endpoints."""
    
    # Import here to avoid circular imports
    from federated_intelligence import get_federated

    @app.route('/api/internal/federated/opt-in', methods=['POST'])
    def federated_opt_in():
        """Opt a user into federated intelligence.
        
        Request body: {"user_id": "user123"}
        """
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({'error': 'user_id is required'}), 400
            
            fed = get_federated()
            success = fed.opt_in_user(user_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'user_id': user_id,
                    'opted_in': True
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to opt in user'
                }), 500
                
        except Exception as e:
            logger.error(f"Error in federated_opt_in: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/internal/federated/opt-out', methods=['POST'])
    def federated_opt_out():
        """Opt a user out of federated intelligence.
        
        Request body: {"user_id": "user123"}
        """
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({'error': 'user_id is required'}), 400
            
            fed = get_federated()
            success = fed.opt_out_user(user_id)
            
            if success:
                return jsonify({
                    'success': True,
                    'user_id': user_id,
                    'opted_in': False
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to opt out user'
                }), 500
                
        except Exception as e:
            logger.error(f"Error in federated_opt_out: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/internal/federated/status', methods=['GET'])
    def federated_status():
        """Get federated intelligence status for a user.
        
        Query params: user_id
        """
        try:
            user_id = request.args.get('user_id')
            
            if not user_id:
                return jsonify({'error': 'user_id is required'}), 400
            
            from federated_intelligence import get_federated, PRIVACY_GUARD_ENABLED, MIN_COHORT_SIZE
            
            fed = get_federated()
            cohort_count = fed._get_opted_in_user_count()
            
            # Get user's opt-in status
            conn = None
            user_opted_in = False
            try:
                import psycopg2
                from urllib.parse import urlparse
                db_url = os.environ.get('DATABASE_URL')
                if db_url:
                    result = urlparse(db_url)
                    conn = psycopg2.connect(
                        host=result.hostname,
                        port=result.port or 5432,
                        database=result.path[1:],
                        user=result.username,
                        password=result.password
                    )
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT federated_opt_in FROM user_profiles WHERE user_id = %s",
                        (user_id,)
                    )
                    row = cursor.fetchone()
                    user_opted_in = row[0] if row else False
                    conn.close()
            except Exception as e:
                logger.warning(f"Error getting user opt-in status: {e}")
            
            return jsonify({
                'user_id': user_id,
                'opted_in': user_opted_in,
                'cohort_size': cohort_count,
                'min_cohort_required': MIN_COHORT_SIZE,
                'is_enabled': fed.is_enabled(),
                'privacy_guard_enabled': PRIVACY_GUARD_ENABLED
            })
            
        except Exception as e:
            logger.error(f"Error in federated_status: {e}")
            return jsonify({'error': str(e)}), 500

    logger.info("Federated intelligence endpoints registered")
