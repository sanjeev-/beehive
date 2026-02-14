"""Researcher persistence with file locking."""

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from beehive.core.researcher import Experiment, Researcher, Study


class ResearcherStorage:
    """Handles persistence of researcher configs and studies."""

    def __init__(self, data_dir: Path):
        """Initialize storage with data directory."""
        self.data_dir = Path(data_dir)
        self.researchers_dir = self.data_dir / "researchers"
        self.researchers_file = self.researchers_dir / "researchers.json"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create storage directories if they don't exist."""
        self.researchers_dir.mkdir(parents=True, exist_ok=True)
        if not self.researchers_file.exists():
            self.researchers_file.write_text("[]")

    def _researcher_dir(self, researcher_id: str) -> Path:
        """Get directory for a specific researcher's data."""
        return self.researchers_dir / researcher_id

    def _studies_file(self, researcher_id: str) -> Path:
        """Get studies file path for a researcher."""
        return self._researcher_dir(researcher_id) / "studies.json"

    @contextmanager
    def _lock_file(self, filepath: Path):
        """File locking for concurrent access safety."""
        with open(filepath, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield f
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    # --- Researcher CRUD ---

    def save_researcher(self, researcher: Researcher) -> None:
        """Save or update a researcher atomically."""
        # Ensure researcher directory exists
        self._researcher_dir(researcher.researcher_id).mkdir(parents=True, exist_ok=True)

        # Initialize studies file if needed
        studies_file = self._studies_file(researcher.researcher_id)
        if not studies_file.exists():
            studies_file.write_text("[]")

        # Save researcher metadata (without studies — studies are stored separately)
        with self._lock_file(self.researchers_file) as f:
            f.seek(0)
            content = f.read()
            researchers = json.loads(content) if content.strip() else []

            # Serialize without studies (studies stored in separate file)
            res_data = researcher.model_dump(mode="json")
            res_data.pop("studies", None)

            # Update or append
            updated = False
            for i, r in enumerate(researchers):
                if r["researcher_id"] == researcher.researcher_id:
                    researchers[i] = res_data
                    updated = True
                    break

            if not updated:
                researchers.append(res_data)

            f.seek(0)
            f.truncate()
            json.dump(researchers, f, indent=2, default=str)

    def load_researcher(self, researcher_id: str) -> Optional[Researcher]:
        """Load researcher by ID (supports partial match)."""
        researchers = self.load_all_researchers()
        for r in researchers:
            if r.researcher_id.startswith(researcher_id):
                return r
        return None

    def load_all_researchers(self) -> list[Researcher]:
        """Load all researchers with their studies."""
        try:
            with open(self.researchers_file) as f:
                content = f.read()
                data = json.loads(content) if content.strip() else []

            researchers = []
            for res_data in data:
                # Load studies from separate file
                studies = self._load_studies(res_data["researcher_id"])
                res_data["studies"] = [s.model_dump(mode="json") for s in studies]
                researchers.append(Researcher(**res_data))
            return researchers
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def delete_researcher(self, researcher_id: str) -> None:
        """Remove researcher from storage."""
        # Find full ID first
        researcher = self.load_researcher(researcher_id)
        if not researcher:
            return

        full_id = researcher.researcher_id

        # Remove from researchers.json
        with self._lock_file(self.researchers_file) as f:
            f.seek(0)
            content = f.read()
            researchers = json.loads(content) if content.strip() else []
            researchers = [r for r in researchers if r["researcher_id"] != full_id]
            f.seek(0)
            f.truncate()
            json.dump(researchers, f, indent=2, default=str)

        # Remove researcher directory
        import shutil

        res_dir = self._researcher_dir(full_id)
        if res_dir.exists():
            shutil.rmtree(res_dir)

    # --- Study CRUD ---

    def save_study(self, researcher_id: str, study: Study) -> None:
        """Save or update a study for a researcher."""
        studies_file = self._studies_file(researcher_id)
        if not studies_file.exists():
            self._researcher_dir(researcher_id).mkdir(parents=True, exist_ok=True)
            studies_file.write_text("[]")

        with self._lock_file(studies_file) as f:
            f.seek(0)
            content = f.read()
            studies = json.loads(content) if content.strip() else []

            study_data = study.model_dump(mode="json")

            # Update or append
            updated = False
            for i, s in enumerate(studies):
                if s["study_id"] == study.study_id:
                    studies[i] = study_data
                    updated = True
                    break

            if not updated:
                studies.append(study_data)

            f.seek(0)
            f.truncate()
            json.dump(studies, f, indent=2, default=str)

    def _load_studies(self, researcher_id: str) -> list[Study]:
        """Load all studies for a researcher."""
        studies_file = self._studies_file(researcher_id)
        try:
            with open(studies_file) as f:
                content = f.read()
                data = json.loads(content) if content.strip() else []
                return [Study(**s) for s in data]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def load_study(self, researcher_id: str, study_id: str) -> Optional[Study]:
        """Load a specific study by ID (supports partial match)."""
        studies = self._load_studies(researcher_id)
        for s in studies:
            if s.study_id.startswith(study_id):
                return s
        return None

    def find_experiment(self, researcher_id: str, experiment_id: str) -> Optional[tuple[Study, Experiment]]:
        """Find an experiment by partial ID across all studies. Returns (study, experiment) or None."""
        studies = self._load_studies(researcher_id)
        for study in studies:
            for experiment in study.experiments:
                if experiment.experiment_id.startswith(experiment_id):
                    return (study, experiment)
        return None

    def find_experiment_globally(self, experiment_id: str) -> Optional[tuple[Researcher, Study, Experiment]]:
        """Find an experiment by partial ID across all researchers and studies."""
        researchers = self.load_all_researchers()
        for researcher in researchers:
            for study in researcher.studies:
                for experiment in study.experiments:
                    if experiment.experiment_id.startswith(experiment_id):
                        return (researcher, study, experiment)
        return None
