"""
Skill Hot Loader - Runtime skill loading with watchdog file system monitoring.

Drop a new skill file into skills/ directory → it appears in registry within 30 seconds.
Invalid skills are rejected with specific errors without crashing the server.
"""

import os
import sys
import time
import logging
import importlib.util
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from threading import Thread, Event
from queue import Queue, Empty

logger = logging.getLogger(__name__)

# Configuration
SKILLS_DIR = os.environ.get('SKILLS_DIR', '/paperclip/lipaira/lipaira-client/skills')
SANDBOX_TIMEOUT = 3  # seconds
WATCH_INTERVAL = 1  # polling interval in seconds

# Skill interface requirements
REQUIRED_ATTRS = ['SKILL_NAME', 'SKILL_VERSION']


@dataclass
class SkillValidationResult:
    """Result of skill validation."""
    valid: bool
    skill_name: str = ""
    version: str = ""
    description: str = ""
    author: str = "unknown"
    error: str = ""
    skill_class: Optional[type] = None


class SkillSandboxValidator:
    """Validates skill files in an isolated subprocess."""
    
    SANDBOX_TEMPLATE = '''
import sys
import traceback

try:
    # Try to load the module
    import importlib.util
    spec = importlib.util.spec_from_file_location("sandbox_skill", "{filepath}")
    if spec is None or spec.loader is None:
        print("ERROR: Cannot load file spec")
        sys.exit(1)
    
    module = importlib.util.module_from_spec(spec)
    sys.modules["sandbox_skill"] = module
    spec.loader.exec_module(module)
    
    # Check required attributes
    if not hasattr(module, "SKILL_NAME"):
        print("ERROR: Missing SKILL_NAME attribute")
        sys.exit(2)
    if not hasattr(module, "SKILL_VERSION"):
        print("ERROR: Missing SKILL_VERSION attribute")
        sys.exit(3)
    
    # Check for Skill class or load_skill function
    has_skill_class = hasattr(module, "Skill") and hasattr(module.Skill, "execute")
    has_load_skill = hasattr(module, "load_skill")
    
    if not has_skill_class and not has_load_skill:
        print("ERROR: Missing Skill class with execute() method or load_skill() function")
        sys.exit(4)
    
    # Try to instantiate if we have a Skill class
    skill_instance = None
    if has_skill_class:
        skill_class = getattr(module, "Skill")
        skill_instance = skill_class()
    elif has_load_skill:
        skill_instance = module.load_skill()
    
    # Verify execute method exists
    if skill_instance and not hasattr(skill_instance, "execute"):
        print("ERROR: Skill instance missing execute() method")
        sys.exit(5)
    
    # Output success info
    print(f"OK:{module.SKILL_NAME}:{module.SKILL_VERSION}")
    if hasattr(module, "SKILL_DESCRIPTION"):
        print(f"DESC:{module.SKILL_DESCRIPTION}")
    if hasattr(module, "SKILL_AUTHOR"):
        print(f"AUTH:{module.SKILL_AUTHOR}")
    
    sys.exit(0)

except Exception as e:
    print(f"ERROR: Import failed: {{str(e)}}")
    traceback.print_exc()
    sys.exit(10)
'''

    @classmethod
    def validate(cls, skill_filepath: str) -> SkillValidationResult:
        """Run skill file in subprocess sandbox to validate.
        
        Returns SkillValidationResult with valid=True if successful,
        or valid=False with specific error message.
        """
        if not os.path.exists(skill_filepath):
            return SkillValidationResult(valid=False, error=f"File not found: {skill_filepath}")
        
        if not skill_filepath.endswith('.py'):
            return SkillValidationResult(valid=False, error=f"Not a Python file: {skill_filepath}")
        
        # Create temp sandbox script
        import tempfile
        sandbox_code = cls.SANDBOX_TEMPLATE.format(filepath=skill_filepath.replace('"', '\\"'))
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(sandbox_code)
            sandbox_script = f.name
        
        try:
            result = subprocess.run(
                [sys.executable, sandbox_script],
                capture_output=True,
                text=True,
                timeout=SANDBOX_TIMEOUT
            )
            
            output = result.stdout.strip()
            stderr = result.stderr.strip()
            
            if result.returncode != 0:
                # Parse error from output
                error_msg = "Validation failed"
                for line in output.split('\n'):
                    if line.startswith('ERROR:'):
                        error_msg = line.replace('ERROR:', '').strip()
                        break
                return SkillValidationResult(valid=False, error=error_msg)
            
            # Parse success output
            lines = output.split('\n')
            skill_name = ""
            version = ""
            description = ""
            author = "unknown"
            
            for line in lines:
                if line.startswith('OK:'):
                    parts = line.split(':', 2)
                    skill_name = parts[1]
                    version = parts[2] if len(parts) > 2 else "1.0.0"
                elif line.startswith('DESC:'):
                    description = line.replace('DESC:', '').strip()
                elif line.startswith('AUTH:'):
                    author = line.replace('AUTH:', '').strip()
            
            if not skill_name:
                return SkillValidationResult(valid=False, error="Could not parse skill name from output")
            
            return SkillValidationResult(
                valid=True,
                skill_name=skill_name,
                version=version,
                description=description,
                author=author
            )
            
        except subprocess.TimeoutExpired:
            return SkillValidationResult(valid=False, error=f"Sandbox timeout after {SANDBOX_TIMEOUT}s")
        except Exception as e:
            return SkillValidationResult(valid=False, error=f"Sandbox error: {str(e)}")
        finally:
            try:
                os.unlink(sandbox_script)
            except:
                pass


class SkillFileLoader:
    """Loads skill from file and returns class instance."""
    
    @classmethod
    def load(cls, skill_filepath: str) -> Tuple[bool, Any, str]:
        """Load skill class from file.
        
        Returns (success, skill_instance_or_class, error_message)
        """
        try:
            spec = importlib.util.spec_from_file_location("skill", skill_filepath)
            if spec is None or spec.loader is None:
                return False, None, "Cannot load file spec"
            
            module = importlib.util.module_from_spec(spec)
            sys.modules["skill"] = module
            spec.loader.exec_module(module)
            
            # Prefer load_skill function, fallback to Skill class
            if hasattr(module, 'load_skill'):
                skill_instance = module.load_skill()
                return True, type(skill_instance), ""
            elif hasattr(module, 'Skill'):
                return True, module.Skill, ""
            else:
                return False, None, "No Skill class or load_skill() function found"
                
        except Exception as e:
            return False, None, f"Load error: {str(e)}"


class SkillHotLoader:
    """Hot loader for skills using file system monitoring."""
    
    def __init__(self, skills_dir: str = None, registry = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self.registry = registry
        
        self._watcher_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._event_queue: Queue = Queue()
        
        # Try to use watchdog, fall back to polling
        self._use_watchdog = False
        try:
            from watchdog import Observer
            self._use_watchdog = True
            self._observer = None
        except ImportError:
            logger.warning("watchdog not available, using polling fallback")
    
    def _get_python_files(self) -> list:
        """Get all .py files in skills directory."""
        path = Path(self.skills_dir)
        if not path.exists():
            return []
        return [str(f) for f in path.glob("*.py") if f.name not in ('__init__.py', '__pycache__')]
    
    def _process_file_event(self, filepath: str, event: str) -> None:
        """Process a file add/modify/remove event."""
        if filepath.endswith('.py') and not filepath.endswith('__init__.py'):
            logger.info(f"Skill file event: {event} - {filepath}")
            
            if event in ('added', 'modified'):
                self._register_or_update_skill(filepath)
            elif event == 'removed':
                self._unregister_skill(filepath)
    
    def _register_or_update_skill(self, filepath: str) -> None:
        """Register or update a skill from file."""
        # Validate in sandbox first
        validation = SkillSandboxValidator.validate(filepath)
        
        if not validation.valid:
            logger.error(f"Skill validation failed for {filepath}: {validation.error}")
            return
        
        # Load the actual skill
        success, skill_class, error = SkillFileLoader.load(filepath)
        
        if not success:
            logger.error(f"Skill load failed for {filepath}: {error}")
            return
        
        # Create manifest
        from skill_registry import SkillManifest
        manifest = SkillManifest(
            name=validation.skill_name,
            version=validation.version,
            description=validation.description,
            author=validation.author,
            source="local",
            file_path=filepath,
            skill_class=skill_class
        )
        
        # Register with global registry
        from skill_registry import skill_registry as global_registry
        registry = self.registry or global_registry
        
        # Unregister existing first (to handle updates)
        if validation.skill_name in registry.list_skills():
            registry.unregister(validation.skill_name)
        
        registry.register(validation.skill_name, skill_class, manifest)
        logger.info(f"Hot-loaded skill: {validation.skill_name} v{validation.version}")
    
    def _unregister_skill(self, filepath: str) -> None:
        """Unregister a skill by file path."""
        from skill_registry import skill_registry as global_registry
        registry = self.registry or global_registry
        
        # Find skill by file path and unregister
        for manifest in registry.list_manifests():
            if manifest.file_path == filepath:
                registry.unregister(manifest.name)
                logger.info(f"Unregistered skill: {manifest.name}")
                break
    
    def _watch_with_watchdog(self) -> None:
        """Watch using watchdog Observer."""
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        
        class SkillEventHandler(FileSystemEventHandler):
            def __init__(hotloader, queue):
                self.queue = queue
            
            def on_created(self, event):
                if not event.is_directory:
                    self.queue.put(('added', event.src_path))
            
            def on_modified(self, event):
                if not event.is_directory:
                    self.queue.put(('modified', event.src_path))
            
            def on_deleted(self, event):
                if not event.is_directory:
                    self.queue.put(('removed', event.src_path))
        
        handler = SkillEventHandler(self._event_queue)
        self._observer = Observer()
        self._observer.schedule(handler, self.skills_dir, recursive=False)
        self._observer.start()
        
        try:
            while not self._stop_event.is_set():
                try:
                    event, path = self._event_queue.get(timeout=WATCH_INTERVAL)
                    self._process_file_event(path, event)
                except Empty:
                    pass
        finally:
            self._observer.stop()
            self._observer.join()
    
    def _watch_with_polling(self) -> None:
        """Fallback: watch using polling."""
        known_files = set(self._get_python_files())
        
        while not self._stop_event.is_set():
            time.sleep(WATCH_INTERVAL)
            
            current_files = set(self._get_python_files())
            
            # Added files
            for f in current_files - known_files:
                self._process_file_event(f, 'added')
            
            # Removed files
            for f in known_files - current_files:
                self._process_file_event(f, 'removed')
            
            # Modified files (re-check all)
            for f in known_files & current_files:
                self._process_file_event(f, 'modified')
            
            known_files = current_files
    
    def start_watcher(self) -> None:
        """Start watching the skills directory."""
        if self._watcher_thread is not None and self._watcher_thread.is_alive():
            logger.warning("Watcher already running")
            return
        
        self._stop_event.clear()
        self._watcher_thread = Thread(
            target=self._watch_with_watchdog if self._use_watchdog else self._watch_with_polling,
            name="SkillHotLoader",
            daemon=True
        )
        self._watcher_thread.start()
        logger.info(f"Skill hot loader started (watching {self.skills_dir})")
    
    def stop_watcher(self) -> None:
        """Stop watching the skills directory."""
        self._stop_event.set()
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5)
            self._watcher_thread = None
        if self._observer:
            self._observer.stop()
            self._observer = None
        logger.info("Skill hot loader stopped")
    
    def load_existing_skills(self) -> None:
        """Load all existing skills from directory on startup."""
        logger.info(f"Loading existing skills from {self.skills_dir}")
        for filepath in self._get_python_files():
            self._register_or_update_skill(filepath)


# Singleton instance for server integration
_hot_loader_instance: Optional[SkillHotLoader] = None


def start_hot_loader(skills_dir: str = None, registry = None) -> SkillHotLoader:
    """Start the hot loader singleton."""
    global _hot_loader_instance
    if _hot_loader_instance is None:
        _hot_loader_instance = SkillHotLoader(skills_dir=skills_dir, registry=registry)
        _hot_loader_instance.start_watcher()
    return _hot_loader_instance


def stop_hot_loader() -> None:
    """Stop the hot loader singleton."""
    global _hot_loader_instance
    if _hot_loader_instance is not None:
        _hot_loader_instance.stop_watcher()
        _hot_loader_instance = None
