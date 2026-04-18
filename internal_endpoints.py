"""
Internal endpoints module — Block 4 service health + admin routes.
"""
import os
import logging
from flask import Blueprint, jsonify, request
import psycopg2

logger = logging.getLogger(__name__)


def _get_db():
    return os.environ.get('DATABASE_URL', 'postgresql://lipaira:***@localhost:5432/lipaira')


def create_internal_routes(app):
    """Register internal routes including admin health + federated intelligence endpoints."""

    # ── Admin services health endpoint ──────────────────────────────────
    admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

    @admin_bp.route('/services', methods=['GET'])
    def services_status():
        """
        Health check for Block 4 background services.
        Returns status of Event Bus (events table), Anticipatory Scheduler
        (anticipatory_signals table), and Federated Intelligence (opt-in count).
        """
        db_url = _get_db()
        status = {
            'event_bus': 'unknown',
            'anticipatory_scheduler': 'unknown',
            'federated_intelligence': 'unknown'
        }

        try:
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()

            # Event Bus — check events table exists and is writable
            try:
                cursor.execute("""
                    INSERT INTO events (event_type, payload, user_id, created_at, status)
                    VALUES ('regression_test', '{}', 'regression_test', NOW(), 'pending')
                    RETURNING id
                """)
                event_id = cursor.fetchone()[0]
                cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
                conn.commit()
                status['event_bus'] = 'ok'
            except Exception as e:
                status['event_bus'] = f'error: {e}'
                conn.rollback()

            # Anticipatory Scheduler — check anticipatory_signals table exists
            try:
                cursor.execute("SELECT 1 FROM anticipatory_signals LIMIT 1")
                cursor.execute("SELECT COUNT(*) FROM anticipatory_signals")
                count = cursor.fetchone()[0]
                status['anticipatory_scheduler'] = f'ok ({count} signals)'
            except Exception as e:
                status['anticipatory_scheduler'] = f'error: {e}'

            # Federated Intelligence — check opt-in flag readable
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = 'users'
                    AND column_name = 'federated_intel_opt_in'
                """)
                has_col = cursor.fetchone()[0] > 0
                if has_col:
                    cursor.execute("SELECT COUNT(*) FROM users WHERE federated_intel_opt_in = TRUE")
                    optins = cursor.fetchone()[0]
                    status['federated_intelligence'] = f'ok ({optins} opted in)'
                else:
                    status['federated_intelligence'] = 'column_missing (migration needed)'
            except Exception as e:
                status['federated_intelligence'] = f'error: {e}'

            cursor.close()
            conn.close()
        except Exception as e:
            return jsonify({'error': str(e), 'status': status}), 503

        return jsonify(status), 200

    app.register_blueprint(admin_bp)
    logger.info("Admin services endpoint registered: /api/admin/services")

    # ── Federated intelligence opt-in/opt-out endpoints ────────────────
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

    return app
