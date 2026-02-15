"""Tests for project feature: models, storage, conversation, and CTO."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from beehive.core.architect import ArchitectRepo
from beehive.core.project import (
    CTOConversation,
    CTOMessage,
    CTOMessageRole,
    Project,
)
from beehive.core.project_storage import ProjectStorage


# --- Model Tests ---


class TestProjectModels:
    def test_project_creation(self):
        proj = Project(name="bitbook", description="A social platform")
        assert proj.name == "bitbook"
        assert proj.description == "A social platform"
        assert len(proj.project_id) == 8
        assert proj.repos == []
        assert proj.architect_ids == []
        assert proj.design_principles == ""
        assert proj.engineering_principles == ""

    def test_project_with_repos(self):
        repos = [
            ArchitectRepo(name="braid", path="/tmp/braid", description="Backend"),
            ArchitectRepo(name="fabric", path="/tmp/fabric", description="Frontend"),
        ]
        proj = Project(name="bitbook", repos=repos)
        assert len(proj.repos) == 2
        assert proj.repos[0].name == "braid"
        assert proj.repos[1].name == "fabric"

    def test_project_serialization(self):
        proj = Project(
            name="test",
            description="desc",
            design_principles="Mobile first",
            engineering_principles="Ship small PRs",
            repos=[ArchitectRepo(name="api", path="/tmp/api")],
            architect_ids=["abc12345"],
        )
        data = proj.model_dump(mode="json")
        assert data["name"] == "test"
        assert data["design_principles"] == "Mobile first"
        assert len(data["repos"]) == 1
        assert data["architect_ids"] == ["abc12345"]

        # Roundtrip
        restored = Project(**data)
        assert restored.project_id == proj.project_id
        assert restored.name == proj.name
        assert restored.design_principles == proj.design_principles

    def test_cto_message(self):
        msg = CTOMessage(role=CTOMessageRole.USER, content="Hello CTO")
        assert msg.role == CTOMessageRole.USER
        assert msg.content == "Hello CTO"
        assert isinstance(msg.timestamp, datetime)

    def test_cto_conversation(self):
        conv = CTOConversation(
            messages=[
                CTOMessage(role=CTOMessageRole.USER, content="Hi"),
                CTOMessage(role=CTOMessageRole.ASSISTANT, content="Hello!"),
            ]
        )
        assert len(conv.messages) == 2
        assert conv.messages[0].role == CTOMessageRole.USER
        assert conv.messages[1].role == CTOMessageRole.ASSISTANT

    def test_cto_message_serialization(self):
        msg = CTOMessage(role=CTOMessageRole.USER, content="Test")
        data = msg.model_dump(mode="json")
        restored = CTOMessage(**data)
        assert restored.role == CTOMessageRole.USER
        assert restored.content == "Test"


# --- Storage Tests ---


class TestProjectStorage:
    def test_storage_initialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ProjectStorage(Path(tmpdir))
            assert storage.projects_dir.exists()
            assert storage.projects_file.exists()
            assert storage.projects_file.read_text() == "[]"

    def test_save_and_load_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ProjectStorage(Path(tmpdir))

            proj = Project(
                project_id="proj1234",
                name="test-project",
                description="A test project",
                repos=[ArchitectRepo(name="api", path="/tmp/api")],
            )
            storage.save_project(proj)

            loaded = storage.load_project("proj1234")
            assert loaded is not None
            assert loaded.name == "test-project"
            assert loaded.description == "A test project"
            assert len(loaded.repos) == 1

    def test_partial_id_matching(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ProjectStorage(Path(tmpdir))

            proj = Project(
                project_id="proj1234",
                name="test",
            )
            storage.save_project(proj)

            assert storage.load_project("proj1234") is not None
            assert storage.load_project("proj1") is not None
            assert storage.load_project("proj") is not None
            assert storage.load_project("zzz") is None

    def test_load_all_projects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ProjectStorage(Path(tmpdir))

            for i in range(3):
                proj = Project(
                    project_id=f"id{i}abcde",
                    name=f"project{i}",
                )
                storage.save_project(proj)

            projects = storage.load_all_projects()
            assert len(projects) == 3

    def test_delete_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ProjectStorage(Path(tmpdir))

            proj = Project(project_id="proj1234", name="test")
            storage.save_project(proj)
            assert storage.load_project("proj1") is not None

            storage.delete_project("proj1")
            assert storage.load_project("proj1") is None

    def test_update_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ProjectStorage(Path(tmpdir))

            proj = Project(project_id="proj1234", name="test")
            storage.save_project(proj)

            # Update
            proj.description = "Updated description"
            proj.architect_ids.append("arch1234")
            storage.save_project(proj)

            loaded = storage.load_project("proj1234")
            assert loaded.description == "Updated description"
            assert loaded.architect_ids == ["arch1234"]


# --- Conversation Tests ---


class TestConversation:
    def test_save_and_load_conversation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ProjectStorage(Path(tmpdir))

            proj = Project(project_id="proj1234", name="test")
            storage.save_project(proj)

            conv = CTOConversation(
                messages=[
                    CTOMessage(role=CTOMessageRole.USER, content="Hello"),
                    CTOMessage(role=CTOMessageRole.ASSISTANT, content="Hi there!"),
                ]
            )
            storage.save_conversation("proj1234", conv)

            loaded = storage.load_conversation("proj1234")
            assert len(loaded.messages) == 2
            assert loaded.messages[0].content == "Hello"
            assert loaded.messages[1].content == "Hi there!"

    def test_append_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ProjectStorage(Path(tmpdir))

            proj = Project(project_id="proj1234", name="test")
            storage.save_project(proj)

            storage.append_message("proj1234", CTOMessageRole.USER, "First message")
            storage.append_message("proj1234", CTOMessageRole.ASSISTANT, "Response")
            storage.append_message("proj1234", CTOMessageRole.USER, "Follow-up")

            conv = storage.load_conversation("proj1234")
            assert len(conv.messages) == 3
            assert conv.messages[0].content == "First message"
            assert conv.messages[1].content == "Response"
            assert conv.messages[2].content == "Follow-up"

    def test_clear_conversation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ProjectStorage(Path(tmpdir))

            proj = Project(project_id="proj1234", name="test")
            storage.save_project(proj)

            storage.append_message("proj1234", CTOMessageRole.USER, "Hello")
            storage.append_message("proj1234", CTOMessageRole.ASSISTANT, "Hi")

            storage.clear_conversation("proj1234")

            conv = storage.load_conversation("proj1234")
            assert len(conv.messages) == 0

    def test_load_empty_conversation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ProjectStorage(Path(tmpdir))

            proj = Project(project_id="proj1234", name="test")
            storage.save_project(proj)

            conv = storage.load_conversation("proj1234")
            assert len(conv.messages) == 0


# --- CTO Tests ---


class TestCTO:
    def test_build_system_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from beehive.core.architect_storage import ArchitectStorage
            from beehive.core.cto import CTO
            from beehive.core.session import SessionManager

            proj = Project(
                name="bitbook",
                description="Social platform for book lovers",
                design_principles="Mobile-first",
                engineering_principles="Ship small PRs",
                repos=[
                    ArchitectRepo(name="braid", path="/tmp/braid", description="Backend"),
                    ArchitectRepo(name="fabric", path="/tmp/fabric", description="Frontend"),
                ],
            )

            project_storage = ProjectStorage(Path(tmpdir))
            architect_storage = ArchitectStorage(Path(tmpdir))
            session_manager = SessionManager(Path(tmpdir))

            cto = CTO(proj, project_storage, architect_storage, session_manager)
            prompt = cto._build_system_prompt()

            assert "bitbook" in prompt
            assert "Mobile-first" in prompt
            assert "Ship small PRs" in prompt
            assert "advise" in prompt.lower() or "Advise" in prompt

    def test_build_project_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from beehive.core.architect_storage import ArchitectStorage
            from beehive.core.cto import CTO
            from beehive.core.session import SessionManager

            proj = Project(
                name="bitbook",
                repos=[
                    ArchitectRepo(name="braid", path="/tmp/braid", description="Backend"),
                ],
            )

            project_storage = ProjectStorage(Path(tmpdir))
            architect_storage = ArchitectStorage(Path(tmpdir))
            session_manager = SessionManager(Path(tmpdir))

            cto = CTO(proj, project_storage, architect_storage, session_manager)
            context = cto._build_project_context()

            assert "bitbook" in context
            assert "braid" in context
            assert "Repositories" in context

    def test_chat(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from beehive.core.architect_storage import ArchitectStorage
            from beehive.core.cto import CTO
            from beehive.core.session import SessionManager

            proj = Project(project_id="proj1234", name="bitbook")

            project_storage = ProjectStorage(Path(tmpdir))
            project_storage.save_project(proj)
            architect_storage = ArchitectStorage(Path(tmpdir))
            session_manager = SessionManager(Path(tmpdir))

            # Mock anthropic module
            mock_anthropic = MagicMock()
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client

            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="I recommend focusing on the API first.")]
            mock_client.messages.create.return_value = mock_response

            cto = CTO(proj, project_storage, architect_storage, session_manager)

            with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
                response = cto.chat("What should we work on next?")

            assert response == "I recommend focusing on the API first."
            mock_client.messages.create.assert_called_once()

            # Check conversation was saved
            conv = project_storage.load_conversation("proj1234")
            assert len(conv.messages) == 2
            assert conv.messages[0].role == CTOMessageRole.USER
            assert conv.messages[1].role == CTOMessageRole.ASSISTANT

    def test_brief(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from beehive.core.architect_storage import ArchitectStorage
            from beehive.core.cto import CTO
            from beehive.core.session import SessionManager

            proj = Project(project_id="proj1234", name="bitbook")

            project_storage = ProjectStorage(Path(tmpdir))
            project_storage.save_project(proj)
            architect_storage = ArchitectStorage(Path(tmpdir))
            session_manager = SessionManager(Path(tmpdir))

            mock_anthropic = MagicMock()
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client

            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Project is on track.")]
            mock_client.messages.create.return_value = mock_response

            cto = CTO(proj, project_storage, architect_storage, session_manager)

            with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
                raw_data, ai_summary = cto.brief()

            assert "bitbook" in raw_data
            assert ai_summary == "Project is on track."
