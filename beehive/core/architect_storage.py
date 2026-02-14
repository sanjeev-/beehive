"""Architect persistence with file locking."""

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from beehive.core.architect import Architect, Plan, Ticket


class ArchitectStorage:
    """Handles persistence of architect configs and plans."""

    def __init__(self, data_dir: Path):
        """Initialize storage with data directory."""
        self.data_dir = Path(data_dir)
        self.architects_dir = self.data_dir / "architects"
        self.architects_file = self.architects_dir / "architects.json"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create storage directories if they don't exist."""
        self.architects_dir.mkdir(parents=True, exist_ok=True)
        if not self.architects_file.exists():
            self.architects_file.write_text("[]")

    def _architect_dir(self, architect_id: str) -> Path:
        """Get directory for a specific architect's data."""
        return self.architects_dir / architect_id

    def _plans_file(self, architect_id: str) -> Path:
        """Get plans file path for an architect."""
        return self._architect_dir(architect_id) / "plans.json"

    @contextmanager
    def _lock_file(self, filepath: Path):
        """File locking for concurrent access safety."""
        with open(filepath, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield f
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    # --- Architect CRUD ---

    def save_architect(self, architect: Architect) -> None:
        """Save or update an architect atomically."""
        # Ensure architect directory exists
        self._architect_dir(architect.architect_id).mkdir(parents=True, exist_ok=True)

        # Initialize plans file if needed
        plans_file = self._plans_file(architect.architect_id)
        if not plans_file.exists():
            plans_file.write_text("[]")

        # Save architect metadata (without plans — plans are stored separately)
        with self._lock_file(self.architects_file) as f:
            f.seek(0)
            content = f.read()
            architects = json.loads(content) if content.strip() else []

            # Serialize without plans (plans stored in separate file)
            arch_data = architect.model_dump(mode="json")
            arch_data.pop("plans", None)

            # Update or append
            updated = False
            for i, a in enumerate(architects):
                if a["architect_id"] == architect.architect_id:
                    architects[i] = arch_data
                    updated = True
                    break

            if not updated:
                architects.append(arch_data)

            f.seek(0)
            f.truncate()
            json.dump(architects, f, indent=2, default=str)

    def load_architect(self, architect_id: str) -> Optional[Architect]:
        """Load architect by ID (supports partial match)."""
        architects = self.load_all_architects()
        for a in architects:
            if a.architect_id.startswith(architect_id):
                return a
        return None

    def load_all_architects(self) -> list[Architect]:
        """Load all architects with their plans."""
        try:
            with open(self.architects_file) as f:
                content = f.read()
                data = json.loads(content) if content.strip() else []

            architects = []
            for arch_data in data:
                # Load plans from separate file
                plans = self._load_plans(arch_data["architect_id"])
                arch_data["plans"] = [p.model_dump(mode="json") for p in plans]
                architects.append(Architect(**arch_data))
            return architects
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def delete_architect(self, architect_id: str) -> None:
        """Remove architect from storage."""
        # Find full ID first
        architect = self.load_architect(architect_id)
        if not architect:
            return

        full_id = architect.architect_id

        # Remove from architects.json
        with self._lock_file(self.architects_file) as f:
            f.seek(0)
            content = f.read()
            architects = json.loads(content) if content.strip() else []
            architects = [a for a in architects if a["architect_id"] != full_id]
            f.seek(0)
            f.truncate()
            json.dump(architects, f, indent=2, default=str)

        # Remove architect directory
        import shutil

        arch_dir = self._architect_dir(full_id)
        if arch_dir.exists():
            shutil.rmtree(arch_dir)

    # --- Plan CRUD ---

    def save_plan(self, architect_id: str, plan: Plan) -> None:
        """Save or update a plan for an architect."""
        plans_file = self._plans_file(architect_id)
        if not plans_file.exists():
            self._architect_dir(architect_id).mkdir(parents=True, exist_ok=True)
            plans_file.write_text("[]")

        with self._lock_file(plans_file) as f:
            f.seek(0)
            content = f.read()
            plans = json.loads(content) if content.strip() else []

            plan_data = plan.model_dump(mode="json")

            # Update or append
            updated = False
            for i, p in enumerate(plans):
                if p["plan_id"] == plan.plan_id:
                    plans[i] = plan_data
                    updated = True
                    break

            if not updated:
                plans.append(plan_data)

            f.seek(0)
            f.truncate()
            json.dump(plans, f, indent=2, default=str)

    def _load_plans(self, architect_id: str) -> list[Plan]:
        """Load all plans for an architect, backfilling ticket order if needed."""
        plans_file = self._plans_file(architect_id)
        try:
            with open(plans_file) as f:
                content = f.read()
                data = json.loads(content) if content.strip() else []
                plans = [Plan(**p) for p in data]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

        # Migrate: backfill order for tickets with order == 0
        migrated = False
        for plan in plans:
            for idx, ticket in enumerate(plan.tickets):
                if ticket.order == 0:
                    ticket.order = idx + 1
                    migrated = True

        if migrated:
            self._save_plans_list(architect_id, plans)

        return plans

    def _save_plans_list(self, architect_id: str, plans: list[Plan]) -> None:
        """Bulk-write all plans for an architect (used by migration)."""
        plans_file = self._plans_file(architect_id)
        if not plans_file.exists():
            self._architect_dir(architect_id).mkdir(parents=True, exist_ok=True)
            plans_file.write_text("[]")

        with self._lock_file(plans_file) as f:
            f.seek(0)
            f.truncate()
            plans_data = [p.model_dump(mode="json") for p in plans]
            json.dump(plans_data, f, indent=2, default=str)

    def load_plan(self, architect_id: str, plan_id: str) -> Optional[Plan]:
        """Load a specific plan by ID (supports partial match)."""
        plans = self._load_plans(architect_id)
        for p in plans:
            if p.plan_id.startswith(plan_id):
                return p
        return None

    def find_ticket(self, architect_id: str, ticket_id: str) -> Optional[tuple[Plan, Ticket]]:
        """Find a ticket by partial ID across all plans. Returns (plan, ticket) or None."""
        plans = self._load_plans(architect_id)
        for plan in plans:
            for ticket in plan.tickets:
                if ticket.ticket_id.startswith(ticket_id):
                    return (plan, ticket)
        return None

    def find_ticket_globally(self, ticket_id: str) -> Optional[tuple[Architect, Plan, Ticket]]:
        """Find a ticket by partial ID across all architects and plans."""
        architects = self.load_all_architects()
        for architect in architects:
            for plan in architect.plans:
                for ticket in plan.tickets:
                    if ticket.ticket_id.startswith(ticket_id):
                        return (architect, plan, ticket)
        return None
