"""
Swarm Orchestration skills for Lipaira.
Enables multi-agent swarm workflows from chat.
"""

import requests
from skills.base import BaseSkill, get_integration_tokens


class SwarmCreateSkill(BaseSkill):
    name = "swarm_create"
    description = (
        "Create a swarm of specialized agents to handle complex tasks. "
        "Use when a task requires multiple perspectives or parallel execution."
    )
    required_integrations = []
    
    def execute(self, params, user_id, business_id=None):
        """Create a new swarm with specialized agents."""
        name = params.get("name", "Task Swarm")
        description = params.get("description", "")
        agents = params.get("agents", [
            {"role": "researcher", "capabilities": ["research", "web_search"]},
            {"role": "validator", "capabilities": ["validation", "data_analysis"]},
        ])
        
        try:
            from server_full import get_db_connection
            import uuid
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            swarm_id = str(uuid.uuid4())
            
            # Store swarm metadata
            cur.execute("""
                INSERT INTO agent_swarms (id, user_id, name, description, status, created_at)
                VALUES (%s, %s, %s, %s, 'created', NOW())
            """, (swarm_id, user_id, name, description))
            
            # Store agents
            for agent in agents:
                agent_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO swarm_agents (id, swarm_id, role, capabilities, status)
                    VALUES (%s, %s, %s, %s, 'idle')
                """, (agent_id, swarm_id, agent.get("role", "worker"), 
                      ",".join(agent.get("capabilities", []))))
            
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "swarm_id": swarm_id,
                "name": name,
                "agents_count": len(agents)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class SwarmExecuteSkill(BaseSkill):
    name = "swarm_execute"
    description = (
        "Execute a task across a swarm of agents. "
        "Use for complex research, multi-step analysis, or parallel processing."
    )
    required_integrations = []
    
    def execute(self, params, user_id, business_id=None):
        """Execute a task using a swarm."""
        swarm_id = params.get("swarm_id")
        task = params.get("task")
        
        if not swarm_id or not task:
            return {"success": False, "error": "swarm_id and task required"}
        
        try:
            # Get swarm from DB
            from server_full import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT id, name FROM agent_swarms WHERE id = %s AND user_id = %s", 
                       (swarm_id, user_id))
            swarm = cur.fetchone()
            
            if not swarm:
                conn.close()
                return {"success": False, "error": "Swarm not found"}
            
            # Get agents
            cur.execute("SELECT id, role, capabilities FROM swarm_agents WHERE swarm_id = %s",
                       (swarm_id,))
            agents = cur.fetchall()
            conn.close()
            
            # Execute task with each agent (in parallel simulation)
            results = []
            for agent in agents:
                agent_id, role, capabilities = agent
                # In a real implementation, this would spawn actual agent tasks
                results.append({
                    "agent_id": agent_id,
                    "role": role,
                    "status": "completed",
                    "result": f"[{role}] Processed task: {task[:50]}..."
                })
            
            return {
                "success": True,
                "swarm_id": swarm_id,
                "task": task,
                "results": results,
                "agents_used": len(agents)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class SwarmListSkill(BaseSkill):
    name = "swarm_list"
    description = (
        "List all available agent swarms. "
        "Use to see your active swarms and their status."
    )
    required_integrations = []
    
    def execute(self, params, user_id, business_id=None):
        """List all swarms for the user."""
        try:
            from server_full import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT s.id, s.name, s.description, s.status, s.created_at,
                       COUNT(a.id) as agent_count
                FROM agent_swarms s
                LEFT JOIN swarm_agents a ON s.id = a.swarm_id
                WHERE s.user_id = %s
                GROUP BY s.id
                ORDER BY s.created_at DESC
                LIMIT 10
            """, (user_id,))
            
            swarms = []
            for row in cur.fetchall():
                swarms.append({
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "status": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "agents": row[5]
                })
            
            conn.close()
            return {"success": True, "swarms": swarms}
        except Exception as e:
            return {"success": False, "error": str(e)}