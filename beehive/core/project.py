"""Project and CTO data models."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from beehive.core.architect import ArchitectRepo


class CTOMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class CTOMessage(BaseModel):
    role: CTOMessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CTOConversation(BaseModel):
    messages: list[CTOMessage] = []
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PreviewConfig(BaseModel):
    setup_command: str  # e.g. "npm run dev --port $BEEHIVE_PORT"
    teardown_command: str = ""  # optional cleanup command
    url_template: str = "http://{task_name}.localhost:{port}"
    startup_timeout: int = 30  # seconds to wait


class Project(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str = ""
    design_principles: str = ""
    engineering_principles: str = ""
    repos: list[ArchitectRepo] = []
    architect_ids: list[str] = []
    preview: Optional[PreviewConfig] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
