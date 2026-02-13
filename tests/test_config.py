"""Tests for BeehiveConfig CLAUDE.md features."""

import tempfile
from pathlib import Path

import pytest

from beehive.core.config import BeehiveConfig, CLAUDE_MD_MARKER, CLAUDE_MD_PROJECT_MARKER


@pytest.fixture
def config(tmp_path):
    return BeehiveConfig(tmp_path)


# --- system_prompt (existing behaviour preserved) ---

def test_system_prompt_round_trip(config):
    config.set_system_prompt("Be concise.")
    assert config.get_system_prompt() == "Be concise."


def test_system_prompt_none_when_missing(config):
    assert config.get_system_prompt() is None


def test_combine_prompts_without_system_prompt(config):
    assert config.combine_prompts("Do X") == "Do X"


def test_combine_prompts_with_system_prompt(config):
    config.set_system_prompt("Be concise.")
    combined = config.combine_prompts("Do X")
    assert "Be concise." in combined
    assert "Do X" in combined


# --- get / set / path ---

def test_get_claude_md_returns_none_when_missing(config):
    assert config.get_claude_md() is None


def test_set_and_get_claude_md(config):
    config.set_claude_md("# Rules\nBe concise.")
    assert config.get_claude_md() == "# Rules\nBe concise."


def test_get_claude_md_returns_none_for_empty_file(config):
    config.claude_md_file.parent.mkdir(parents=True, exist_ok=True)
    config.claude_md_file.write_text("   \n  ")
    assert config.get_claude_md() is None


def test_get_claude_md_path(config):
    assert config.get_claude_md_path() == config.data_dir / "CLAUDE.md"


# --- inject_claude_md ---

def test_inject_noop_when_no_template(config, tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    assert config.inject_claude_md(worktree) is False
    assert not (worktree / "CLAUDE.md").exists()


def test_inject_creates_file_in_empty_worktree(config, tmp_path):
    config.set_claude_md("# Rules\nBe concise.")
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    assert config.inject_claude_md(worktree) is True
    content = (worktree / "CLAUDE.md").read_text()
    assert CLAUDE_MD_MARKER in content
    assert "# Rules\nBe concise." in content


def test_inject_prepends_to_existing_claude_md(config, tmp_path):
    config.set_claude_md("# Beehive Rules")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "CLAUDE.md").write_text("# Project-specific rules\nDo Y.")

    assert config.inject_claude_md(worktree) is True
    content = (worktree / "CLAUDE.md").read_text()
    assert CLAUDE_MD_MARKER in content
    assert CLAUDE_MD_PROJECT_MARKER in content
    assert "# Beehive Rules" in content
    assert "# Project-specific rules\nDo Y." in content
    # Beehive defaults should come first
    assert content.index(CLAUDE_MD_MARKER) < content.index(CLAUDE_MD_PROJECT_MARKER)


def test_inject_is_idempotent(config, tmp_path):
    config.set_claude_md("# Rules")
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    assert config.inject_claude_md(worktree) is True
    first_content = (worktree / "CLAUDE.md").read_text()

    # Second call should be a no-op
    assert config.inject_claude_md(worktree) is False
    assert (worktree / "CLAUDE.md").read_text() == first_content


def test_inject_idempotent_with_existing_project_file(config, tmp_path):
    config.set_claude_md("# Rules")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "CLAUDE.md").write_text("# Project")

    assert config.inject_claude_md(worktree) is True
    first_content = (worktree / "CLAUDE.md").read_text()

    # Second call should be a no-op
    assert config.inject_claude_md(worktree) is False
    assert (worktree / "CLAUDE.md").read_text() == first_content
