"""
Enhanced Preferences API - Per Task Type
====================================
GET/POST/PUT /api/settings/preferences - Get/set all task preferences
GET/POST/PUT /api/settings/preferences/{task_type} - Get/set specific task preference
GET /api/settings/preferences/schema - Get UI schema
"""

from flask import Blueprint, jsonify, request
from .enhanced_preferences import (
    PreferenceManager,
    TaskType,
    get_preferences_schema,
    AVAILABLE_MODELS,
    TASK_INFO,
    DEFAULT_TASK_MODELS,
    SLIDER_LABELS
)
import json

preferences_bp = Blueprint('preferences', __name__)


def get_user_id():
    """Get user ID from request"""
    return request.headers.get('X-User-ID') or request.args.get('user_id') or 'demo'


@preferences_bp.route('/api/settings/preferences/schema', methods=['GET'])
def get_schema():
    """Get schema for preferences UI"""
    return jsonify(get_preferences_schema())


@preferences_bp.route('/api/settings/preferences', methods=['GET'])
def get_all_preferences():
    """Get all user preferences"""
    user_id = get_user_id()
    prefs = PreferenceManager.get_all_preferences(user_id)
    return jsonify(prefs)


@preferences_bp.route('/api/settings/preferences', methods=['POST', 'PUT'])
def update_all_preferences():
    """Bulk update preferences"""
    user_id = get_user_id()
    data = request.get_json() or {}
    
    for task_str, task_data in data.get("preferences", {}).items():
        try:
            task = TaskType(task_str)
            model = task_data.get("current")
            if model:
                PreferenceManager.set_task_model(user_id, task, model)
        except ValueError:
            pass
    
    return jsonify(PreferenceManager.get_all_preferences(user_id))


@preferences_bp.route('/api/settings/preferences/<task_type>', methods=['GET'])
def get_task_preference(task_type):
    """Get preference for specific task"""
    user_id = get_user_id()
    
    try:
        task = TaskType(task_type)
    except ValueError:
        return jsonify({"error": f"Invalid task type: {task_type}"}), 400
    
    model = PreferenceManager.get_model_for_task(user_id, task)
    prefs = PreferenceManager.get_all_preferences(user_id)
    
    task_prefs = prefs["preferences"].get(task_type, {})
    
    return jsonify({
        "task_type": task_type,
        "current_model": model,
        "available_models": AVAILABLE_MODELS[task],
        "info": TASK_INFO[task],
        "default": DEFAULT_TASK_MODELS[task]
    })


@preferences_bp.route('/api/settings/preferences/slider', methods=['POST', 'PUT'])
def set_slider_level():
    """Set slider level - updates all task defaults"""
    user_id = get_user_id()
    data = request.get_json() or {}
    level = data.get('level', 5)
    
    PreferenceManager.set_slider_level(user_id, level)
    
    return jsonify({
        "success": True,
        "level": level,
        "label": SLIDER_LABELS.get(level, "Smartest"),
        "preferences": PreferenceManager.get_all_preferences(user_id)
    })
@preferences_bp.route("/api/settings/preferences/<task_type>", methods=["POST", "PUT"])
def set_task_preference(task_type):
    """Set model for specific task"""
    user_id = get_user_id()
    data = request.get_json() or {}
    model = data.get("model", "").strip()
    
    try:
        task = TaskType(task_type)
    except ValueError:
        return jsonify({"error": f"Invalid task type: {task_type}"}), 400
    
    if not model:
        return jsonify({"error": "Model required"}), 400
    
    PreferenceManager.set_task_model(user_id, task, model)
    
    return jsonify({
        "success": True,
        "task_type": task_type,
        "model": model
    })


@preferences_bp.route('/api/settings/preferences/<task_type>', methods=['DELETE'])
def clear_task_preference(task_type):
    """Clear custom model, revert to default"""
    user_id = get_user_id()
    
    try:
        task = TaskType(task_type)
    except ValueError:
        return jsonify({"error": f"Invalid task type: {task_type}"}), 400
    
    PreferenceManager.clear_task_model(user_id, task)
    
    return jsonify({
        "success": True,
        "task_type": task_type,
        "model": DEFAULT_TASK_MODELS[task]
    })


# Frontend UI Component
PREFERENCES_COMPONENT = """
<!-- Model Preferences by Task Type -->
<div class="preferences-panel" id="preferencesPanel">
    <h3>🤖 Model Preferences</h3>
    <p class="prefs-description">Choose the best model for each task type</p>
    
    <div class="task-prefs" id="taskPrefs">
        <!-- Populated by JS -->
    </div>
</div>

<style>
.preferences-panel {
    padding: 20px;
    background: var(--bg-card);
    border-radius: 12px;
}
.prefs-description {
    color: var(--text-dim);
    font-size: 14px;
    margin-bottom: 20px;
}
.task-pref {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px;
    margin-bottom: 8px;
    background: var(--bg-input);
    border-radius: 8px;
}
.task-info {
    display: flex;
    align-items: center;
    gap: 10px;
}
.task-icon { font-size: 20px; }
.task-name { font-weight: 600; }
.task-desc { font-size: 12px; color: var(--text-dim); }
.model-select {
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-main);
    color: var(--text-main);
    font-size: 14px;
    min-width: 180px;
}
</style>

<script>
async function loadPreferences() {
    const schemaRes = await fetch('/api/settings/preferences/schema');
    const prefsRes = await fetch('/api/settings/preferences');
    const schema = await schemaRes.json();
    const prefs = await prefsRes.json();
    
    const container = document.getElementById('taskPrefs');
    container.innerHTML = '';
    
    for (const taskType of schema.task_types) {
        const current = prefs.preferences[taskType.type]?.current || taskType.default_model;
        
        const div = document.createElement('div');
        div.className = 'task-pref';
        div.innerHTML = `
            <div class="task-info">
                <span class="task-icon">${taskType.icon}</span>
                <div>
                    <div class="task-name">${taskType.name}</div>
                    <div class="task-desc">${taskType.description}</div>
                </div>
            </div>
            <select class="model-select" onchange="setPreference('${taskType.type}', this.value)">
                ${taskType.available_models.map(m => 
                    `<option value="${m.id}" ${m.id === current ? 'selected' : ''}>${m.name}</option>`
                ).join('')}
            </select>
        `;
        container.appendChild(div);
    }
}

async function setPreference(taskType, model) {
    await fetch(\`/api/settings/preferences/\${taskType}\`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({model})
    });
    showToast('Preference saved!');
}

loadPreferences();
</script>
"""
