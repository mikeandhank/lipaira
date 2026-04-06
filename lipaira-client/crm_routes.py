"""
CRM Sync module - Handles CRM connections and sync.
"""
import os
import json
import requests
from flask import Blueprint, request, jsonify
from psycopg2.extras import RealDictCursor

crm_bp = Blueprint('crm', __name__)


def get_db():
    import psycopg2
    db_url = os.environ.get('DATABASE_URL', 'postgresql://nexusos:ChangeMe123!@postgres:5432/nexusos')
    return psycopg2.connect(db_url)


# ── CRM Contact endpoints ─────────────────────────────────────────────────

@crm_bp.route('/api/crm/contacts/search')
def crm_contacts_search():
    user_id = request.headers.get('X-User-ID')
    name = request.args.get('name', '')
    email = request.args.get('email', '')
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM crm_contacts
                WHERE user_id = %s AND (name ILIKE %s OR email ILIKE %s)
                LIMIT 10
            """, (user_id, f'%{name}%', f'%{email}%'))
            return jsonify([dict(c) for c in cur.fetchall()])


@crm_bp.route('/api/crm/contacts', methods=['POST'])
def crm_contacts_create():
    user_id = request.headers.get('X-User-ID')
    data = request.get_json()
    import uuid
    contact_id = str(uuid.uuid4())
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO crm_contacts (id, user_id, name, email, phone, company, address)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (contact_id, user_id, data.get('name'), data.get('email'), data.get('phone'), data.get('company'), data.get('address')))
            conn.commit()
    
    return jsonify({'id': contact_id})


# ── CRM Deal endpoints ───────────────────────────────────────────────────

@crm_bp.route('/api/crm/deals')
def crm_deals_list():
    user_id = request.headers.get('X-User-ID')
    stage = request.args.get('stage', 'all')
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if stage == 'all':
                cur.execute("SELECT * FROM crm_deals WHERE user_id = %s ORDER BY created_at DESC LIMIT 20", (user_id,))
            else:
                cur.execute("SELECT * FROM crm_deals WHERE user_id = %s AND stage = %s ORDER BY created_at DESC LIMIT 20", (user_id, stage))
            return jsonify([dict(d) for d in cur.fetchall()])


@crm_bp.route('/api/crm/deals', methods=['POST'])
def crm_deals_create():
    user_id = request.headers.get('X-User-ID')
    data = request.get_json()
    import uuid
    deal_id = str(uuid.uuid4())
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO crm_deals (id, user_id, title, value, stage, close_date, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (deal_id, user_id, data.get('title'), data.get('value', 0), data.get('stage', 'new'), data.get('close_date'), data.get('notes')))
            conn.commit()
    
    return jsonify({'id': deal_id})


# ── Pipeline summary ─────────────────────────────────────────────────────

@crm_bp.route('/api/crm/pipeline/summary')
def crm_pipeline_summary():
    user_id = request.headers.get('X-User-ID')
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT stage, COUNT(*) as count, COALESCE(SUM(value), 0) as total_value
                FROM crm_deals WHERE user_id = %s
                GROUP BY stage
            """, (user_id,))
            stages = cur.fetchall()
            
            cur.execute("""
                SELECT COALESCE(SUM(value), 0) as pipeline_value
                FROM crm_deals WHERE user_id = %s AND stage NOT IN ('won', 'lost')
            """, (user_id,))
            total = cur.fetchone()
    
    return jsonify({
        'stages': [dict(s) for s in stages],
        'pipeline_value': float(total['pipeline_value']) if total else 0
    })


def create_crm_routes(app):
    app.register_blueprint(crm_bp)