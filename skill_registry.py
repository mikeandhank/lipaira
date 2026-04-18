"""
Skill Registry - Central registry for all skills with hot reload support.
"""

import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SkillManifest:
    """Metadata about a registered skill."""
    name: str
    version: str
    description: str
    author: str = "unknown"
    source: str = "local"  # 'local', 'marketplace'
    file_path: str = ""
    dependencies: List[str] = field(default_factory=list)
    skill_class: Optional[type] = None  # The actual skill class reference


class SkillRegistry:
    """Global skill registry with hot reload capabilities."""
    
    def __init__(self):
        self._skills: Dict[str, SkillManifest] = {}
        self._instances: Dict[str, Any] = {}
        self.hot_reload_enabled: bool = False
    
    def register(self, name: str, skill_class: type, manifest: Optional[SkillManifest] = None) -> None:
        """Register a skill class."""
        try:
            instance = skill_class()
            self._instances[name] = instance
            
            if manifest is None:
                manifest = SkillManifest(
                    name=name,
                    version=getattr(skill_class, 'SKILL_VERSION', '1.0.0'),
                    description=getattr(skill_class, 'SKILL_DESCRIPTION', ''),
                    author=getattr(skill_class, 'SKILL_AUTHOR', 'unknown'),
                    file_path=getattr(skill_class, '__file__', ''),
                    skill_class=skill_class
                )
            else:
                manifest.skill_class = skill_class
            
            self._skills[name] = manifest
            logger.info(f"Registered skill: {name} v{manifest.version}")
        except Exception as e:
            logger.error(f"Failed to register skill {name}: {e}")
            raise
    
    def unregister(self, name: str) -> bool:
        """Unregister a skill by name."""
        if name in self._skills:
            del self._skills[name]
        if name in self._instances:
            del self._instances[name]
        logger.info(f"Unregistered skill: {name}")
        return True
    
    def get(self, name: str) -> Optional[Any]:
        """Get a skill instance by name."""
        return self._instances.get(name)
    
    def list_skills(self) -> List[str]:
        """List all registered skill names."""
        return list(self._skills.keys())
    
    def list_manifests(self) -> List[SkillManifest]:
        """List all skill manifests."""
        return list(self._skills.values())
    
    def reload_skills(self) -> Dict[str, Any]:
        """Reload all skills from their registered sources."""
        results = {}
        for name, manifest in list(self._skills.items()):
            if manifest.file_path:
                try:
                    # Re-import the module to pick up changes
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(name, manifest.file_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        if hasattr(module, 'load_skill'):
                            skill_class = module.load_skill()
                            self.register(name, type(skill_class), manifest)
                            results[name] = "reloaded"
                except Exception as e:
                    logger.error(f"Failed to reload skill {name}: {e}")
                    results[name] = f"error: {e}"
            else:
                results[name] = "no_file_path"
        return results
    
    def get_skill_info(self, name: str) -> Optional[Dict]:
        """Get skill info as dict."""
        manifest = self._skills.get(name)
        if not manifest:
            return None
        instance = self._instances.get(name)
        return {
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "author": manifest.author,
            "source": manifest.source,
            "file_path": manifest.file_path,
            "dependencies": manifest.dependencies,
            "has_execute": hasattr(instance, 'execute') if instance else False
        }


# Global registry instance
skill_registry = SkillRegistry()
