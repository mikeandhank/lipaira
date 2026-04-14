import subprocess
from .base import BaseSkill, SkillResult

BLOCKED_PATTERNS = [
    "import os", "import sys", "import subprocess", "import socket",
    "**import**", "eval(", "exec(", "open(", "os.system",
]

class CodeRunSkill(BaseSkill):
    name = "code_run"
    description = "Execute Python code for calculations, data processing, and analysis."
    timeout = 15
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"}
            },
            "required": ["code"]
        }

    def execute(self, input: dict) -> SkillResult:
        code = input.get("code", "")
        for pattern in BLOCKED_PATTERNS:
            if pattern in code:
                return SkillResult(success=False, output=None,
                    error=f"Restricted operation: {pattern}")
        try:
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True, text=True,
                timeout=self.timeout,
                cwd="/app/data",
                env={"PATH": "/usr/bin:/bin"}
            )
            output = result.stdout if result.returncode == 0 else result.stderr
            return SkillResult(success=result.returncode == 0, output=output)
        except subprocess.TimeoutExpired:
            return SkillResult(success=False, output=None, error="Execution timed out (15s)")
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))

class EmailDraftSkill(BaseSkill):
    name = "email_draft"
    description = "Draft a professional email. Returns a draft for user review — does not send."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "intent": {"type": "string", "description": "What the email should accomplish"},
                "tone": {"type": "string", "enum": ["professional", "friendly", "formal"],
                    "default": "professional"}
            },
            "required": ["to", "intent"]
        }

    def execute(self, input: dict) -> SkillResult:
        return SkillResult(success=True, output={
            "to": input.get("to"),
            "subject": input.get("subject", "(subject needed)"),
            "intent": input.get("intent"),
            "tone": input.get("tone", "professional"),
            "note": "Draft only — review and send manually"
        })
