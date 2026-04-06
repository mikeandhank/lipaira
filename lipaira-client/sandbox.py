"""
Lipaira Kernel Sandbox
======================
Process isolation using Python execution restrictions.

This provides a baseline security layer. For full kernel isolation,
deploy with gVisor or LXC on the host system.
"""

import os
import sys
import json
import time
import uuid
import subprocess
import tempfile
import traceback
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SandboxStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    TERMINATED = "terminated"
    TIMEOUT = "timeout"
    VIOLATION = "violation"
    ERROR = "error"


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution"""
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    max_execution_time_sec: int = 300
    max_processes: int = 10
    allow_network: bool = False
    allow_file_write: bool = True
    allowed_executables: List[str] = field(default_factory=list)
    block_shell: bool = True


@dataclass
class SandboxResult:
    """Result of sandbox execution"""
    status: SandboxStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    duration_ms: int = 0
    violations: List[str] = field(default_factory=list)
    error: Optional[str] = None


class LipairaSandbox:
    """
    Python sandbox with restrictions on dangerous operations.
    
    For production: Use gVisor (runsc) or LXC for kernel-level isolation.
    This provides a software fallback layer.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.config = SandboxConfig()
        self.sandboxes: Dict[str, Dict] = {}
        self._blocked_imports = {
            'os', 'subprocess', 'socket', 'requests', 'urllib',
            'http', 'ftplib', 'telnetlib', 'pty', 'tty',
            'resource', 'signal', 'multiprocessing', 'threading',
            'importlib', 'builtins', 'sys'
        }
        logger.info("Lipaira Sandbox initialized (software layer)")
    
    def create_sandbox(self, config: Optional[SandboxConfig] = None) -> str:
        sandbox_id = str(uuid.uuid4())[:8]
        cfg = config or self.config
        self.sandboxes[sandbox_id] = {
            "id": sandbox_id,
            "config": cfg,
            "status": SandboxStatus.PENDING,
            "created_at": time.time(),
        }
        return sandbox_id
    
    def execute(
        self,
        sandbox_id: str,
        code: str,
        language: str = "python",
        env: Optional[Dict[str, str]] = None
    ) -> SandboxResult:
        if sandbox_id not in self.sandboxes:
            return SandboxResult(status=SandboxStatus.ERROR, error="Sandbox not found")
        
        sandbox = self.sandboxes[sandbox_id]
        cfg = sandbox["config"]
        start_time = time.time()
        sandbox["status"] = SandboxStatus.RUNNING
        
        try:
            if language == "python":
                result = self._run_python(code, cfg)
            elif language == "javascript":
                result = self._run_js(code, cfg)
            else:
                result = SandboxResult(status=SandboxStatus.VIOLATION, violations=["Unsupported language"])
        except Exception as e:
            result = SandboxResult(status=SandboxStatus.ERROR, error=str(e), stderr=traceback.format_exc())
        
        result.duration_ms = int((time.time() - start_time) * 1000)
        sandbox["status"] = result.status
        return result
    
    def _run_python(self, code: str, config: SandboxConfig) -> SandboxResult:
        """Execute Python with restrictions"""
        
        blocked_list = list(self._blocked_imports)
        
        # Build wrapper without f-string for the inner code
        wrapper = '''
import sys
import os

# Block dangerous imports
_original_import = __builtins__.__import__
_blocked = ''' + repr(blocked_list) + '''

def _blocked_import(name, *args, **kwargs):
    if name in _blocked:
        raise ImportError("Blocked: " + name)
    return _original_import(name, *args, **kwargs)

__builtins__.__import__ = _blocked_import

# Block dangerous globals
for _dangerous in ['exit', 'quit', 'compile', 'eval', 'exec']:
    if hasattr(__builtins__, _dangerous):
        delattr(__builtins__, _dangerous)

# Restricted os.environ
class _SafeEnv:
    def __getitem__(self, k):
        if k in ('PATH', 'HOME', 'USER', 'LANG'):
            return os.environ.get(k, '')
        raise KeyError(f"Env '{k}' blocked")
    def get(self, k, d=None):
        return self[k] if k in ('PATH', 'HOME', 'USER', 'LANG') else d

os.environ = _SafeEnv()

# Execute user code
''' + code + '''
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(wrapper)
            temp_file = f.name
        
        try:
            proc = subprocess.Popen(
                ['python3', temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd='/tmp',
                env={k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'USER', 'LANG')}
            )
            
            try:
                stdout, stderr = proc.communicate(timeout=config.max_execution_time_sec)
                return SandboxResult(
                    status=SandboxStatus.TERMINATED,
                    stdout=stdout.decode('utf-8', errors='replace'),
                    stderr=stderr.decode('utf-8', errors='replace'),
                    exit_code=proc.returncode
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                return SandboxResult(status=SandboxStatus.TIMEOUT, violations=["Execution timed out"])
                
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
        
        return SandboxResult(status=SandboxStatus.TERMINATED)
    
    def _run_js(self, code: str, config: SandboxConfig) -> SandboxResult:
        """Execute JavaScript with restrictions"""
        
        wrapper = f'''
// Sandbox restrictions
delete global.require;
delete global.process;
delete global.__dirname;

// User code
{code}
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(wrapper)
            temp_file = f.name
        
        try:
            proc = subprocess.Popen(
                ['node', temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd='/tmp'
            )
            
            try:
                stdout, stderr = proc.communicate(timeout=config.max_execution_time_sec)
                return SandboxResult(
                    status=SandboxStatus.TERMINATED,
                    stdout=stdout.decode('utf-8', errors='replace'),
                    stderr=stderr.decode('utf-8', errors='replace'),
                    exit_code=proc.returncode
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                return SandboxResult(status=SandboxStatus.TIMEOUT)
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
        
        return SandboxResult(status=SandboxStatus.TERMINATED)
    
    def destroy(self, sandbox_id: str) -> bool:
        if sandbox_id in self.sandboxes:
            del self.sandboxes[sandbox_id]
            return True
        return False
    
    def list_sandboxes(self) -> List[Dict]:
        return [{"id": s["id"], "status": s["status"].value} for s in self.sandboxes.values()]


def execute_in_sandbox(code: str, language: str = "python") -> SandboxResult:
    """Quick execute in new sandbox"""
    s = LipairaSandbox()
    sid = s.create_sandbox()
    return s.execute(sid, code, language)


if __name__ == '__main__':
    s = LipairaSandbox()
    print(f"Sandbox ready: {s.get_stats()}")