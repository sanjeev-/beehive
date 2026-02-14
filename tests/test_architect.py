"""Tests for architect feature: models, storage, planner, and CLI."""

import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from beehive.core.architect import (
    Architect,
    ArchitectRepo,
    Plan,
    Ticket,
    TicketStatus,
)
from beehive.core.architect_storage import ArchitectStorage
from beehive.core.planner import Planner


# --- Model Tests ---


class TestModels:
    def test_ticket_creation(self):
        ticket = Ticket(
            title="Add login page",
            description="Create a login page with email/password",
            repo="frontend",
        )
        assert ticket.title == "Add login page"
        assert ticket.status == TicketStatus.PENDING
        assert ticket.session_id is None
        assert ticket.pr_url is None
        assert len(ticket.ticket_id) == 8

    def test_ticket_status_enum(self):
        ticket = Ticket(
            title="Test",
            description="Test",
            repo="api",
            status=TicketStatus.ASSIGNED,
        )
        assert ticket.status == TicketStatus.ASSIGNED

    def test_plan_creation(self):
        tickets = [
            Ticket(title="Task 1", description="Do task 1", repo="api"),
            Ticket(title="Task 2", description="Do task 2", repo="frontend"),
        ]
        plan = Plan(directive="Build user auth", tickets=tickets)
        assert plan.directive == "Build user auth"
        assert len(plan.tickets) == 2
        assert len(plan.plan_id) == 8

    def test_architect_repo(self):
        repo = ArchitectRepo(
            name="api",
            path="/home/user/api",
            base_branch="develop",
            description="Backend API",
        )
        assert repo.name == "api"
        assert repo.base_branch == "develop"

    def test_architect_creation(self):
        repos = [
            ArchitectRepo(name="api", path="/tmp/api"),
            ArchitectRepo(name="web", path="/tmp/web"),
        ]
        arch = Architect(
            name="test-architect",
            principles="Keep it simple",
            repos=repos,
        )
        assert arch.name == "test-architect"
        assert len(arch.repos) == 2
        assert len(arch.plans) == 0
        assert len(arch.architect_id) == 8

    def test_model_serialization(self):
        ticket = Ticket(
            title="Test",
            description="Test desc",
            repo="api",
        )
        data = ticket.model_dump(mode="json")
        assert data["title"] == "Test"
        assert data["status"] == "pending"
        # Roundtrip
        restored = Ticket(**data)
        assert restored.ticket_id == ticket.ticket_id
        assert restored.title == ticket.title

    def test_architect_serialization(self):
        arch = Architect(
            name="test",
            principles="Be good",
            repos=[ArchitectRepo(name="api", path="/tmp/api")],
        )
        data = arch.model_dump(mode="json")
        restored = Architect(**data)
        assert restored.architect_id == arch.architect_id
        assert restored.name == arch.name
        assert len(restored.repos) == 1


# --- Storage Tests ---


class TestArchitectStorage:
    def test_storage_initialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))
            assert storage.architects_dir.exists()
            assert storage.architects_file.exists()
            assert storage.architects_file.read_text() == "[]"

    def test_save_and_load_architect(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))

            arch = Architect(
                architect_id="abc12345",
                name="test-arch",
                principles="Test principles",
                repos=[ArchitectRepo(name="api", path="/tmp/api")],
            )
            storage.save_architect(arch)

            loaded = storage.load_architect("abc12345")
            assert loaded is not None
            assert loaded.name == "test-arch"
            assert loaded.principles == "Test principles"
            assert len(loaded.repos) == 1

    def test_partial_id_matching(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))

            arch = Architect(
                architect_id="abc12345",
                name="test",
                principles="",
                repos=[ArchitectRepo(name="api", path="/tmp/api")],
            )
            storage.save_architect(arch)

            assert storage.load_architect("abc12345") is not None
            assert storage.load_architect("abc1") is not None
            assert storage.load_architect("abc") is not None
            assert storage.load_architect("zzz") is None

    def test_load_all_architects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))

            for i in range(3):
                arch = Architect(
                    architect_id=f"id{i}abcde",
                    name=f"arch{i}",
                    principles="",
                    repos=[ArchitectRepo(name="api", path="/tmp/api")],
                )
                storage.save_architect(arch)

            architects = storage.load_all_architects()
            assert len(architects) == 3

    def test_delete_architect(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))

            arch = Architect(
                architect_id="abc12345",
                name="test",
                principles="",
                repos=[ArchitectRepo(name="api", path="/tmp/api")],
            )
            storage.save_architect(arch)
            assert storage.load_architect("abc1") is not None

            storage.delete_architect("abc1")
            assert storage.load_architect("abc1") is None

    def test_save_and_load_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))

            arch = Architect(
                architect_id="abc12345",
                name="test",
                principles="",
                repos=[ArchitectRepo(name="api", path="/tmp/api")],
            )
            storage.save_architect(arch)

            plan = Plan(
                plan_id="plan1234",
                directive="Build auth",
                tickets=[
                    Ticket(
                        ticket_id="tick1234",
                        title="Add login",
                        description="Create login endpoint",
                        repo="api",
                    )
                ],
            )
            storage.save_plan("abc12345", plan)

            loaded = storage.load_plan("abc12345", "plan1234")
            assert loaded is not None
            assert loaded.directive == "Build auth"
            assert len(loaded.tickets) == 1
            assert loaded.tickets[0].title == "Add login"

    def test_find_ticket(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))

            arch = Architect(
                architect_id="abc12345",
                name="test",
                principles="",
                repos=[ArchitectRepo(name="api", path="/tmp/api")],
            )
            storage.save_architect(arch)

            plan = Plan(
                plan_id="plan1234",
                directive="Build auth",
                tickets=[
                    Ticket(
                        ticket_id="tick1234",
                        title="Add login",
                        description="Create login endpoint",
                        repo="api",
                    ),
                    Ticket(
                        ticket_id="tick5678",
                        title="Add logout",
                        description="Create logout endpoint",
                        repo="api",
                    ),
                ],
            )
            storage.save_plan("abc12345", plan)

            result = storage.find_ticket("abc12345", "tick1")
            assert result is not None
            found_plan, found_ticket = result
            assert found_ticket.title == "Add login"

            result = storage.find_ticket("abc12345", "tick5")
            assert result is not None
            _, found_ticket = result
            assert found_ticket.title == "Add logout"

            assert storage.find_ticket("abc12345", "xxxx") is None

    def test_find_ticket_globally(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))

            arch = Architect(
                architect_id="abc12345",
                name="test",
                principles="",
                repos=[ArchitectRepo(name="api", path="/tmp/api")],
            )
            storage.save_architect(arch)

            plan = Plan(
                plan_id="plan1234",
                directive="Build auth",
                tickets=[
                    Ticket(
                        ticket_id="tick1234",
                        title="Add login",
                        description="Create login endpoint",
                        repo="api",
                    ),
                ],
            )
            storage.save_plan("abc12345", plan)

            result = storage.find_ticket_globally("tick1")
            assert result is not None
            found_arch, found_plan, found_ticket = result
            assert found_arch.architect_id == "abc12345"
            assert found_ticket.title == "Add login"

    def test_update_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))

            arch = Architect(
                architect_id="abc12345",
                name="test",
                principles="",
                repos=[ArchitectRepo(name="api", path="/tmp/api")],
            )
            storage.save_architect(arch)

            plan = Plan(
                plan_id="plan1234",
                directive="Build auth",
                tickets=[
                    Ticket(
                        ticket_id="tick1234",
                        title="Add login",
                        description="Create login endpoint",
                        repo="api",
                    ),
                ],
            )
            storage.save_plan("abc12345", plan)

            # Update ticket status
            loaded = storage.load_plan("abc12345", "plan1234")
            loaded.tickets[0].status = TicketStatus.ASSIGNED
            loaded.tickets[0].session_id = "sess1234"
            storage.save_plan("abc12345", loaded)

            reloaded = storage.load_plan("abc12345", "plan1234")
            assert reloaded.tickets[0].status == TicketStatus.ASSIGNED
            assert reloaded.tickets[0].session_id == "sess1234"


# --- YAML Config Parsing Tests ---


class TestYAMLConfig:
    def test_parse_yaml_config(self):
        config_data = {
            "name": "my-architect",
            "principles": "- Keep it simple\n- Test everything",
            "repos": [
                {
                    "name": "api",
                    "path": "/tmp/api",
                    "base_branch": "main",
                    "description": "Backend API",
                },
                {
                    "name": "web",
                    "path": "/tmp/web",
                    "base_branch": "develop",
                    "description": "Frontend app",
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        with open(config_path) as f:
            parsed = yaml.safe_load(f)

        repos = [
            ArchitectRepo(
                name=r["name"],
                path=r["path"],
                base_branch=r.get("base_branch", "main"),
                description=r.get("description", ""),
            )
            for r in parsed["repos"]
        ]

        arch = Architect(
            name=parsed["name"],
            principles=parsed.get("principles", ""),
            repos=repos,
        )

        assert arch.name == "my-architect"
        assert len(arch.repos) == 2
        assert arch.repos[0].name == "api"
        assert arch.repos[1].base_branch == "develop"

        Path(config_path).unlink()

    def test_yaml_config_defaults(self):
        config_data = {
            "name": "minimal",
            "repos": [{"name": "app", "path": "/tmp/app"}],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        with open(config_path) as f:
            parsed = yaml.safe_load(f)

        repo = ArchitectRepo(
            name=parsed["repos"][0]["name"],
            path=parsed["repos"][0]["path"],
            base_branch=parsed["repos"][0].get("base_branch", "main"),
        )

        assert repo.base_branch == "main"
        assert repo.description == ""

        Path(config_path).unlink()


# --- Planner Tests ---


class TestPlanner:
    def test_build_system_prompt(self):
        arch = Architect(
            name="test",
            principles="- Keep it simple\n- Test everything",
            repos=[
                ArchitectRepo(
                    name="api",
                    path="/tmp/api",
                    base_branch="main",
                    description="Backend API",
                ),
                ArchitectRepo(
                    name="web",
                    path="/tmp/web",
                    base_branch="develop",
                    description="Frontend app",
                ),
            ],
        )

        planner = Planner(arch)
        prompt = planner._build_system_prompt()

        assert "Keep it simple" in prompt
        assert "Test everything" in prompt
        assert "api: Backend API" in prompt
        assert "web: Frontend app" in prompt
        assert "exactly ONE repository" in prompt
        assert "JSON array" in prompt

    @patch("beehive.core.planner.anthropic.Anthropic")
    def test_generate_plan(self, mock_anthropic_class):
        arch = Architect(
            name="test",
            principles="Keep it simple",
            repos=[
                ArchitectRepo(name="api", path="/tmp/api", description="Backend"),
                ArchitectRepo(name="web", path="/tmp/web", description="Frontend"),
            ],
        )

        # Mock the API response
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=json.dumps([
                    {
                        "title": "Add auth endpoint",
                        "description": "Create POST /auth/login endpoint",
                        "repo": "api",
                    },
                    {
                        "title": "Add login form",
                        "description": "Create login form component",
                        "repo": "web",
                    },
                ])
            )
        ]
        mock_client.messages.create.return_value = mock_response

        planner = Planner(arch)
        plan = planner.generate_plan("Add user authentication")

        assert plan.directive == "Add user authentication"
        assert len(plan.tickets) == 2
        assert plan.tickets[0].title == "Add auth endpoint"
        assert plan.tickets[0].repo == "api"
        assert plan.tickets[1].title == "Add login form"
        assert plan.tickets[1].repo == "web"

        # Verify API was called
        mock_client.messages.create.assert_called_once()

    @patch("beehive.core.planner.anthropic.Anthropic")
    def test_generate_plan_with_code_blocks(self, mock_anthropic_class):
        """Test parsing when Claude wraps response in markdown code blocks."""
        arch = Architect(
            name="test",
            principles="",
            repos=[ArchitectRepo(name="api", path="/tmp/api")],
        )

        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text='```json\n[{"title": "Fix bug", "description": "Fix the bug", "repo": "api"}]\n```'
            )
        ]
        mock_client.messages.create.return_value = mock_response

        planner = Planner(arch)
        plan = planner.generate_plan("Fix bugs")

        assert len(plan.tickets) == 1
        assert plan.tickets[0].title == "Fix bug"

    @patch("beehive.core.planner.anthropic.Anthropic")
    def test_generate_plan_invalid_repo(self, mock_anthropic_class):
        """Test that invalid repo names raise an error."""
        arch = Architect(
            name="test",
            principles="",
            repos=[ArchitectRepo(name="api", path="/tmp/api")],
        )

        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=json.dumps([
                    {
                        "title": "Fix bug",
                        "description": "Fix the bug",
                        "repo": "nonexistent",
                    }
                ])
            )
        ]
        mock_client.messages.create.return_value = mock_response

        planner = Planner(arch)
        with pytest.raises(ValueError, match="unknown repo 'nonexistent'"):
            planner.generate_plan("Fix bugs")


# --- Assignment Logic Tests ---


class TestAssignment:
    def test_ticket_assignment_updates(self):
        """Test that assigning a ticket updates its fields correctly."""
        ticket = Ticket(
            ticket_id="tick1234",
            title="Test task",
            description="Do something",
            repo="api",
        )

        assert ticket.status == TicketStatus.PENDING
        assert ticket.session_id is None

        # Simulate assignment
        ticket.status = TicketStatus.ASSIGNED
        ticket.session_id = "sess1234"
        ticket.updated_at = datetime.utcnow()

        assert ticket.status == TicketStatus.ASSIGNED
        assert ticket.session_id == "sess1234"

    def test_status_sync_completed(self):
        """Test that syncing from a completed session updates ticket."""
        ticket = Ticket(
            ticket_id="tick1234",
            title="Test task",
            description="Do something",
            repo="api",
            status=TicketStatus.ASSIGNED,
            session_id="sess1234",
        )

        # Simulate session completion
        mock_session_status = "completed"
        mock_pr_url = "https://github.com/test/pr/1"

        if mock_session_status == "completed":
            ticket.status = TicketStatus.COMPLETED
        if mock_pr_url:
            ticket.pr_url = mock_pr_url

        assert ticket.status == TicketStatus.COMPLETED
        assert ticket.pr_url == "https://github.com/test/pr/1"

    def test_status_sync_failed(self):
        """Test that syncing from a failed session updates ticket."""
        ticket = Ticket(
            ticket_id="tick1234",
            title="Test task",
            description="Do something",
            repo="api",
            status=TicketStatus.ASSIGNED,
            session_id="sess1234",
        )

        mock_session_status = "stopped"
        if mock_session_status in ("failed", "stopped"):
            ticket.status = TicketStatus.FAILED

        assert ticket.status == TicketStatus.FAILED

    def test_filter_pending_tickets(self):
        """Test filtering only pending tickets for assignment."""
        tickets = [
            Ticket(title="T1", description="D1", repo="api", status=TicketStatus.PENDING),
            Ticket(title="T2", description="D2", repo="api", status=TicketStatus.ASSIGNED),
            Ticket(title="T3", description="D3", repo="web", status=TicketStatus.PENDING),
            Ticket(title="T4", description="D4", repo="web", status=TicketStatus.COMPLETED),
        ]

        pending = [t for t in tickets if t.status == TicketStatus.PENDING]
        assert len(pending) == 2
        assert pending[0].title == "T1"
        assert pending[1].title == "T3"


# --- New Feature Tests: order, branch_name, MERGED, execution_mode ---


class TestNewModelFields:
    def test_ticket_order_default(self):
        """Ticket order defaults to 0 (legacy/unset)."""
        ticket = Ticket(title="T", description="D", repo="api")
        assert ticket.order == 0

    def test_ticket_order_explicit(self):
        """Ticket order can be set explicitly."""
        ticket = Ticket(title="T", description="D", repo="api", order=3)
        assert ticket.order == 3

    def test_ticket_branch_name_default(self):
        """Ticket branch_name defaults to None."""
        ticket = Ticket(title="T", description="D", repo="api")
        assert ticket.branch_name is None

    def test_ticket_branch_name_set(self):
        ticket = Ticket(title="T", description="D", repo="api", branch_name="feat/test")
        assert ticket.branch_name == "feat/test"

    def test_ticket_merged_status(self):
        """MERGED status exists and can be assigned."""
        ticket = Ticket(title="T", description="D", repo="api")
        ticket.status = TicketStatus.MERGED
        assert ticket.status == TicketStatus.MERGED

    def test_plan_execution_mode_default(self):
        """Plan execution_mode defaults to 'sequential'."""
        plan = Plan(directive="test")
        assert plan.execution_mode == "sequential"

    def test_plan_execution_mode_parallel(self):
        plan = Plan(directive="test", execution_mode="parallel")
        assert plan.execution_mode == "parallel"

    def test_backward_compat_ticket_without_order(self):
        """Ticket deserialized from JSON without 'order' defaults to 0."""
        data = {
            "ticket_id": "abc12345",
            "title": "Old ticket",
            "description": "Desc",
            "repo": "api",
            "status": "pending",
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }
        ticket = Ticket(**data)
        assert ticket.order == 0
        assert ticket.branch_name is None

    def test_backward_compat_plan_without_execution_mode(self):
        """Plan deserialized from JSON without 'execution_mode' defaults to 'sequential'."""
        data = {
            "plan_id": "plan1234",
            "directive": "Old plan",
            "tickets": [],
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }
        plan = Plan(**data)
        assert plan.execution_mode == "sequential"

    def test_model_serialization_roundtrip_new_fields(self):
        """New fields survive serialization roundtrip."""
        ticket = Ticket(
            title="T", description="D", repo="api",
            order=2, branch_name="feat/x",
            status=TicketStatus.MERGED,
        )
        data = ticket.model_dump(mode="json")
        assert data["order"] == 2
        assert data["branch_name"] == "feat/x"
        assert data["status"] == "merged"
        restored = Ticket(**data)
        assert restored.order == 2
        assert restored.branch_name == "feat/x"
        assert restored.status == TicketStatus.MERGED


class TestPlannerOrder:
    @patch("beehive.core.planner.anthropic.Anthropic")
    def test_planner_assigns_order(self, mock_anthropic_class):
        """Planner assigns order 1, 2, 3... to generated tickets."""
        arch = Architect(
            name="test",
            principles="",
            repos=[
                ArchitectRepo(name="api", path="/tmp/api", description="Backend"),
                ArchitectRepo(name="web", path="/tmp/web", description="Frontend"),
            ],
        )

        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                text=json.dumps([
                    {"title": "Task A", "description": "Do A", "repo": "api"},
                    {"title": "Task B", "description": "Do B", "repo": "web"},
                    {"title": "Task C", "description": "Do C", "repo": "api"},
                ])
            )
        ]
        mock_client.messages.create.return_value = mock_response

        planner = Planner(arch)
        plan = planner.generate_plan("Build something")

        assert len(plan.tickets) == 3
        assert plan.tickets[0].order == 1
        assert plan.tickets[1].order == 2
        assert plan.tickets[2].order == 3


class TestStorageMigration:
    def test_order_backfill_on_load(self):
        """Tickets loaded with order=0 get backfilled to idx+1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))

            arch = Architect(
                architect_id="abc12345",
                name="test",
                principles="",
                repos=[ArchitectRepo(name="api", path="/tmp/api")],
            )
            storage.save_architect(arch)

            # Write plan JSON directly with order=0 (legacy data)
            plans_file = storage._plans_file("abc12345")
            legacy_plan = {
                "plan_id": "plan1234",
                "directive": "Old plan",
                "tickets": [
                    {"ticket_id": "t1", "title": "First", "description": "D1", "repo": "api",
                     "order": 0, "status": "pending",
                     "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"},
                    {"ticket_id": "t2", "title": "Second", "description": "D2", "repo": "api",
                     "order": 0, "status": "pending",
                     "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"},
                    {"ticket_id": "t3", "title": "Third", "description": "D3", "repo": "api",
                     "order": 0, "status": "pending",
                     "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"},
                ],
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
            }
            plans_file.write_text(json.dumps([legacy_plan]))

            # Load triggers migration
            plan = storage.load_plan("abc12345", "plan1234")
            assert plan.tickets[0].order == 1
            assert plan.tickets[1].order == 2
            assert plan.tickets[2].order == 3

            # Verify migration was persisted
            plan2 = storage.load_plan("abc12345", "plan1234")
            assert plan2.tickets[0].order == 1

    def test_no_migration_when_order_set(self):
        """Tickets with order already set are not re-migrated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ArchitectStorage(Path(tmpdir))

            arch = Architect(
                architect_id="abc12345",
                name="test",
                principles="",
                repos=[ArchitectRepo(name="api", path="/tmp/api")],
            )
            storage.save_architect(arch)

            plan = Plan(
                plan_id="plan1234",
                directive="New plan",
                tickets=[
                    Ticket(ticket_id="t1", title="First", description="D1", repo="api", order=5),
                    Ticket(ticket_id="t2", title="Second", description="D2", repo="api", order=10),
                ],
            )
            storage.save_plan("abc12345", plan)

            loaded = storage.load_plan("abc12345", "plan1234")
            assert loaded.tickets[0].order == 5
            assert loaded.tickets[1].order == 10


class TestSequentialLogic:
    def test_first_pending_by_order(self):
        """Sequential mode selects first pending ticket sorted by order."""
        tickets = [
            Ticket(title="T3", description="D", repo="api", order=3, status=TicketStatus.PENDING),
            Ticket(title="T1", description="D", repo="api", order=1, status=TicketStatus.PENDING),
            Ticket(title="T2", description="D", repo="api", order=2, status=TicketStatus.ASSIGNED),
        ]
        pending = sorted(
            [t for t in tickets if t.status == TicketStatus.PENDING],
            key=lambda t: t.order,
        )
        assert pending[0].title == "T1"
        assert pending[0].order == 1

    def test_in_flight_blocks_next(self):
        """If any ticket is in-flight, no new assignment happens."""
        tickets = [
            Ticket(title="T1", description="D", repo="api", order=1, status=TicketStatus.ASSIGNED),
            Ticket(title="T2", description="D", repo="api", order=2, status=TicketStatus.PENDING),
        ]
        in_flight = [
            t for t in tickets
            if t.status in (TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.COMPLETED)
        ]
        assert len(in_flight) == 1
        # Should not assign T2 because T1 is still in-flight

    def test_merged_not_in_flight(self):
        """Merged tickets are not considered in-flight."""
        tickets = [
            Ticket(title="T1", description="D", repo="api", order=1, status=TicketStatus.MERGED),
            Ticket(title="T2", description="D", repo="api", order=2, status=TicketStatus.PENDING),
        ]
        in_flight = [
            t for t in tickets
            if t.status in (TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.COMPLETED)
        ]
        assert len(in_flight) == 0
        # T2 should be assignable


class TestCheckPrMerged:
    @patch("beehive.cli_architect.subprocess.run")
    def test_pr_merged(self, mock_run):
        """Returns True when PR state is MERGED."""
        from beehive.cli_architect import _check_pr_merged

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"state": "MERGED"}',
        )
        assert _check_pr_merged("https://github.com/test/repo/pull/1") is True
        mock_run.assert_called_once()

    @patch("beehive.cli_architect.subprocess.run")
    def test_pr_open(self, mock_run):
        """Returns False when PR state is OPEN."""
        from beehive.cli_architect import _check_pr_merged

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"state": "OPEN"}',
        )
        assert _check_pr_merged("https://github.com/test/repo/pull/1") is False

    @patch("beehive.cli_architect.subprocess.run")
    def test_pr_check_failure(self, mock_run):
        """Returns False when gh command fails."""
        from beehive.cli_architect import _check_pr_merged

        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert _check_pr_merged("https://github.com/test/repo/pull/1") is False

    @patch("beehive.cli_architect.subprocess.run")
    def test_pr_check_exception(self, mock_run):
        """Returns False when an exception occurs."""
        from beehive.cli_architect import _check_pr_merged

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=15)
        assert _check_pr_merged("https://github.com/test/repo/pull/1") is False
