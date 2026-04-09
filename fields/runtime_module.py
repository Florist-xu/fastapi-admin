from typing import Any

from pydantic import BaseModel, Field


class RuntimeModuleConfigUpdate(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict, description="Module config payload")
