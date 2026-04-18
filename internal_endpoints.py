"""
Internal endpoints module — Block 4 service health + admin routes.
"""
import logging
from flask import Blueprint, jsonify, request
import psycopg2
import os

logger = logging.getLogger(__name__)

def _get_db():
    return os.environ.get('DATABASE_URL', 'postgresql://lipaira:password@localhost:5432/lipaira')


def create_internal_routes(app):
    """Register internal routes."""
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
    return app
