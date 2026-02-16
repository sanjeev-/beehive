"""Architect data models for plan and ticket management."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TicketStatus(str, Enum):
    """Status of a ticket in a plan."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    MERGED = "merged"


class ArchitectRepo(BaseModel):
    """A repository managed by an architect."""

    name: str  # e.g. "fabric"
    path: str  # absolute path on host
    base_branch: str = "main"
    description: str = ""  # what this repo is for


class Ticket(BaseModel):
    """A discrete unit of work targeting one repo and one PR."""

    ticket_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str  # detailed work description for the agent
    repo: str  # repo name (matches ArchitectRepo.name)
    order: int = 0  # 1-indexed execution order; 0 = legacy/unset
    status: TicketStatus = TicketStatus.PENDING
    session_id: Optional[str] = None  # linked beehive session
    branch_name: Optional[str] = None
    pr_url: Optional[str] = None
    is_feedback: bool = False  # True for ad-hoc feedback tickets from PR comments
    source_comment_id: Optional[int] = None  # GitHub comment ID that spawned this
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=True)


class Plan(BaseModel):
    """A set of tickets generated from a high-level directive."""

    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    directive: str  # the original high-level request
    execution_mode: str = "sequential"  # "sequential" or "parallel"
    auto_merge: bool = False  # agents auto-merge PRs into feature branch
    base_branch: Optional[str] = None  # plan's feature branch name
    feature_pr_url: Optional[str] = None  # PR from feature branch → main
    preview_url: Optional[str] = None  # preview env for the feature branch
    processed_comment_ids: list[int] = []  # GitHub comment IDs already handled
    tickets: list[Ticket] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=True)


class Architect(BaseModel):
    """An architect configuration with principles and repo responsibilities."""

    architect_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    principles: str  # guiding principles for the architect
    repos: list[ArchitectRepo]
    plans: list[Plan] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=True)
