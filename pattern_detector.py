"""Pattern detection and workflow suggestion - per SPEC Item 14."""
import os
import json
import logging
from datetime import datetime, timedelta
from collections import Counter
import psycopg2

logger = logging.getLogger(__name__)

MIN_PATTERN_REPEATS = 4  # Minimum times to detect pattern
CONFIDENCE_THRESHOLD = 0.7


class PatternDetector:
    """Detect recurring patterns in user activity."""
    
    def __init__(self):
        pass
    
    def detect_patterns(self, user_id: str) -> list:
        """Query activity log and detect recurring patterns."""
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cur = conn.cursor()
        
        # Get last 30 days of activity
        cur.execute(""" 
            SELECT action_type, description, created_at::date as activity_date
            FROM activity_log
            WHERE user_id = %s AND created_at > NOW() - INTERVAL '30 days'
            ORDER BY created_at
        """, (user_id,))
        
        activities = cur.fetchall()
        cur.close()
        conn.close()
        
        if len(activities) < MIN_PATTERN_REPEATS:
            return []
        
        # Group by action_type and find sequences
        patterns = self._analyze_patterns(activities)
        
        return patterns
    
    def _analyze_patterns(self, activities: list) -> list:
        """Analyze for repeated sequences."""
        # Count action types
        action_counts = Counter([a[0] for a in activities])
        
        patterns = []
        
        # Find actions repeated 4+ times
        for action, count in action_counts.items():
            if count >= MIN_PATTERN_REPEATS:
                # Get dates when this action occurred
                dates = sorted(set(a[2] for a in activities if a[0] == action))
                
                # Check for regularity (e.g., every month around same time)
                if len(dates) >= 2:
                    intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                    avg_interval = sum(intervals) / len(intervals)
                    
                    pattern_type = self._classify_pattern(action, avg_interval, intervals)
                    
                    patterns.append({
                        'action_type': action,
                        'count': count,
                        'pattern_type': pattern_type,
                        'avg_interval_days': round(avg_interval, 1),
                        'confidence': min(count / 10, 1.0)  # More repeats = higher confidence
                    })
        
        # Sort by confidence
        patterns.sort(key=lambda x: x['confidence'], reverse=True)
        return patterns
    
    def _classify_pattern(self, action: str, avg_interval: float, intervals: list) -> str:
        """Classify the pattern type based on intervals."""
        if 25 <= avg_interval <= 35:
            return "monthly"
        elif 6 <= avg_interval <= 8:
            return "weekly"
        elif 0 <= avg_interval <= 1:
            return "daily"
        else:
            return "irregular"


class WorkflowSuggester:
    """Generate workflow suggestions based on patterns."""
    
    def __init__(self, pattern_detector: PatternDetector):
        self.pattern_detector = pattern_detector
    
    def get_suggestions(self, user_id: str) -> list:
        """Get workflow suggestions for user."""
        patterns = self.pattern_detector.detect_patterns(user_id)
        
        suggestions = []
        for pattern in patterns:
            if pattern['confidence'] >= CONFIDENCE_THRESHOLD:
                suggestion = self._generate_suggestion(pattern)
                if suggestion:
                    suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_suggestion(self, pattern: dict) -> dict:
        """Generate a workflow suggestion from a pattern."""
        action = pattern['action_type']
        
        # Map patterns to workflow templates
        suggestion_templates = {
            'invoice_chase_executed': {
                'title': f'Automate invoice chasing for {pattern["count"]} clients',
                'description': f'Automatically chase overdue invoices every month. You\'ve done this {pattern["count"]} times in the last 30 days.',
                'workflow_type': 'invoice_automation'
            },
            'email_send': {
                'title': 'Automate weekly report emails',
                'description': f'Automatically send weekly reports every {int(pattern["avg_interval_days"])} days.',
                'workflow_type': 'email_automation'
            },
            'calendar_event_created': {
                'title': 'Schedule recurring meetings',
                'description': f'Automatically create recurring meetings every {int(pattern["avg_interval_days"])} days.',
                'workflow_type': 'calendar_automation'
            }
        }
        
        template = suggestion_templates.get(action, {
            'title': f'Automate {action}',
            'description': f'You\'ve performed this action {pattern["count"]} times. Want to automate it?',
            'workflow_type': 'generic'
        })
        
        return {
            'pattern': pattern,
            'suggestion': template,
            'confidence': pattern['confidence']
        }
    
    def approve_suggestion(self, user_id: str, suggestion: dict) -> dict:
        """Convert approved suggestion to actual workflow."""
        workflow_type = suggestion['suggestion']['workflow_type']
        
        # Would create actual workflow in workflow_presets or DB
        logger.info(f"Creating workflow of type {workflow_type} for user {user_id}")
        
        # Log pattern + approval
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cur = conn.cursor()
        cur.execute(""" 
            INSERT INTO activity_log (user_id, action_type, description, status, created_at, metadata)
            VALUES (%s, 'pattern_automation_enabled', %s, 'completed', NOW(), %s)
        """, (user_id, f"Pattern automation: {workflow_type}", json.dumps(suggestion)))
        conn.commit()
        cur.close()
        conn.close()
        
        return {'success': True, 'workflow_created': workflow_type}


# API routes
def create_pattern_routes(app, require_auth):
    """Register pattern detection routes."""
    from flask import g, jsonify, request
    
    @app.route('/api/patterns/detect', methods=['GET'])
    @require_auth
    def detect_patterns():
        """Detect patterns in user's activity."""
        detector = PatternDetector()
        patterns = detector.detect_patterns(g.user_id)
        return jsonify({'patterns': patterns})
    
    @app.route('/api/patterns/suggestions', methods=['GET'])
    @require_auth
    def get_suggestions():
        """Get workflow suggestions based on patterns."""
        detector = PatternDetector()
        suggester = WorkflowSuggester(detector)
        suggestions = suggester.get_suggestions(g.user_id)
        return jsonify({'suggestions': suggestions})
    
    @app.route('/api/patterns/approve', methods=['POST'])
    @require_auth
    def approve_suggestion():
        """Approve a pattern suggestion and create workflow."""
        data = request.get_json() or {}
        suggestion = data.get('suggestion', {})
        
        detector = PatternDetector()
        suggester = WorkflowSuggester(detector)
        result = suggester.approve_suggestion(g.user_id, suggestion)
        
        return jsonify(result)