"""Researcher data models for study and experiment management."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from beehive.core.architect import ArchitectRepo


class ExperimentStatus(str, Enum):
    """Status of an experiment in a study."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Experiment(BaseModel):
    """A discrete experiment targeting one repo, producing reports and assets."""

    experiment_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str  # detailed experiment description for the agent
    repo: str  # repo name (matches ArchitectRepo.name)
    status: ExperimentStatus = ExperimentStatus.PENDING
    session_id: Optional[str] = None  # linked beehive session
    output_dir: Optional[str] = None  # directory with results/artifacts
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=True)


class Study(BaseModel):
    """A set of experiments generated from a high-level research directive."""

    study_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    directive: str  # the original high-level research question
    experiments: list[Experiment] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=True)


class Researcher(BaseModel):
    """A researcher configuration with principles and repo responsibilities."""

    researcher_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    principles: str  # guiding principles for the researcher
    repos: list[ArchitectRepo]
    studies: list[Study] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=True)
