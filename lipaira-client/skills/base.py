from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any

class SkillResult(BaseModel):
    success: bool
    output: Any
    error: str | None = None

class BaseSkill(ABC):
    name: str
    description: str
    timeout: int = 30
    
    @abstractmethod
    def get_input_schema(self) -> dict:
        pass

    @abstractmethod
    def execute(self, input: dict) -> SkillResult:
        pass

    def to_tool_definition(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.get_input_schema()
        }
