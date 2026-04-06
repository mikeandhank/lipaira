import os
from .base import BaseSkill, SkillResult

DATA_DIR = "/app/data"

def safe_path(relative: str) -> str | None:
    path = os.path.realpath(os.path.join(DATA_DIR, relative))
    return path if path.startswith(DATA_DIR) else None

class FileReadSkill(BaseSkill):
    name = "file_read"
    description = "Read a file from the user's storage."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to user storage"}
            },
            "required": ["path"]
        }

    def execute(self, input: dict) -> SkillResult:
        path = safe_path(input.get("path", ""))
        if not path:
            return SkillResult(success=False, output=None, error="Path not permitted")
        try:
            with open(path, "r") as f:
                return SkillResult(success=True, output=f.read())
        except FileNotFoundError:
            return SkillResult(success=False, output=None, error="File not found")
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))

class FileWriteSkill(BaseSkill):
    name = "file_write"
    description = "Write or append content to a file in the user's storage."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["write", "append"], "default": "write"}
            },
            "required": ["path", "content"]
        }

    def execute(self, input: dict) -> SkillResult:
        path = safe_path(input.get("path", ""))
        if not path:
            return SkillResult(success=False, output=None, error="Path not permitted")
        mode = "a" if input.get("mode") == "append" else "w"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, mode) as f:
                f.write(input.get("content", ""))
            return SkillResult(success=True, output=f"Written to {input['path']}")
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))

class FileListSkill(BaseSkill):
    name = "file_list"
    description = "List files in the user's storage directory."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."}
            }
        }

    def execute(self, input: dict) -> SkillResult:
        path = safe_path(input.get("path", "."))
        if not path:
            return SkillResult(success=False, output=None, error="Path not permitted")
        try:
            files = []
            for f in os.listdir(path):
                full = os.path.join(path, f)
                files.append({
                    "name": f,
                    "type": "dir" if os.path.isdir(full) else "file",
                    "size": os.path.getsize(full) if os.path.isfile(full) else 0
                })
            return SkillResult(success=True, output=files)
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
