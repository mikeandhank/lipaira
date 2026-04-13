"""Skill registry and base skill class for Lipaira.

Defines the BaseSkill abstract class that all skills inherit from,
and the SkillRegistry for managing available skills.

Key functions/classes:
    BaseSkill: Abstract base class for all skills with execute/can_execute methods
    SkillRegistry: Registry for registering, listing, and retrieving skills
    skill_registry: Global registry instance
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseSkill(ABC):
    """Base class for all skills.
    
    Each skill is an atomic capability that can be used in workflows.
    Skills fetch their own credentials - never accept tokens from callers.
    """
    
    name: str = ""
    description: str = ""
    required_integrations: list = []
    execution_tier: str = "paid"  # "free" or "paid" - safe default is paid
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        """Check if required integrations are connected.
        
        Args:
            user_id: The user's ID
            business_id: Optional business ID
            
        Returns:
            Dict with can_run, missing, message
        """
        if not self.required_integrations:
            return {"can_run": True, "missing": [], "message": "Ready"}
        
        from skills.base import get_integration_tokens
        
        missing = []
        for provider in self.required_integrations:
            try:
                get_integration_tokens(user_id, business_id, provider)
            except ValueError:
                missing.append(provider)
        
        return {
            "can_run": len(missing) == 0,
            "missing": missing,
            "message": f"Needs: {', '.join(missing)}" if missing else "Ready"
        }
    
    @abstractmethod
    def execute(self, params: dict, user_id: str, 
                business_id: str = None) -> dict:
        """Execute the skill.
        
        Args:
            params: Skill-specific parameters
            user_id: The user's ID
            business_id: Optional business ID
            
        Returns:
            Dict with skill-specific output
        """
        raise NotImplementedError


class SkillRegistry:
    """Registry of all available skills."""
    
    def __init__(self):
        self._skills = {}
    
    def register(self, skill_class) -> None:
        """Register a skill class."""
        skill = skill_class()
        self._skills[skill.name] = skill
    
    def get(self, name: str):
        """Get a skill by name."""
        return self._skills.get(name)
    
    def list(self) -> list:
        """List all available skills."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "required_integrations": s.required_integrations,
                "can_execute": s.can_execute
            }
            for s in self._skills.values()
        ]
    
    def list_summaries(self) -> list:
        """Lightweight list of skills (without can_execute function)."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "required_integrations": s.required_integrations
            }
            for s in self._skills.values()
        ]
    
    def get_available_tools(self, user_id: str, business_id: str = None) -> list:
        """
        Return tool definitions only for skills whose integrations are connected.
        This prevents hallucination and reduces context length.
        """
        # Get user's connected integrations
        import os
        import psycopg2
        
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise RuntimeError('DATABASE_URL is required')
        
        connected_providers = set()
        try:
            conn = psycopg2.connect(db_url)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT provider FROM user_integrations
                    WHERE user_id = %s AND status = 'connected'
                """, (user_id,))
                for row in cur.fetchall():
                    connected_providers.add(row[0])
            conn.close()
        except Exception:
            pass
        
        # Also add providers that don't need integration (email, internal)
        connected_providers.add('resend')  # Lipaira's built-in email
        connected_providers.add('internal')  # Internal skills
        
        available = []
        for skill in self._skills.values():
            # Check if skill's required integrations are connected
            can_run = True
            if skill.required_integrations:
                for integ in skill.required_integrations:
                    if integ not in connected_providers:
                        can_run = False
                        break
            
            if can_run:
                schema = {}
                if hasattr(skill, 'get_input_schema'):
                    schema = skill.get_input_schema()
                
                available.append({
                    "name": skill.name,
                    "description": skill.description,
                    "input_schema": schema or {
                        "type": "object",
                        "properties": {}
                    }
                })
        
        return available


# Global registry instance
skill_registry = SkillRegistry()