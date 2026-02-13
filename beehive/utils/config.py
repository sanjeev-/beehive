"""Configuration management for Beehive."""

from pathlib import Path


class Config:
    """Configuration for Beehive."""

    DEFAULT_DATA_DIR = Path.home() / ".beehive"
    DEFAULT_BASE_BRANCH = "main"

    @classmethod
    def get_data_dir(cls) -> Path:
        """Get the data directory, creating it if needed."""
        data_dir = cls.DEFAULT_DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
