"""Tests for git operations."""

from beehive.core.git_ops import generate_branch_name


def test_generate_branch_name():
    """Test branch name generation."""
    # Normal name
    name = generate_branch_name("fix-bug", "a1b2c3d4")
    assert name == "beehive/fix-bug-a1b2c3d4"

    # Name with spaces
    name = generate_branch_name("Fix Bug", "a1b2")
    assert name == "beehive/fix-bug-a1b2"

    # Name with special characters
    name = generate_branch_name("Fix: Auth Bug!", "a1b2")
    assert name == "beehive/fix-auth-bug-a1b2"

    # Multiple consecutive dashes
    name = generate_branch_name("fix---bug", "a1b2")
    assert name == "beehive/fix-bug-a1b2"

    # Leading/trailing dashes
    name = generate_branch_name("-fix-bug-", "a1b2")
    assert name == "beehive/fix-bug-a1b2"

    # Very long name
    long_name = "a" * 100
    name = generate_branch_name(long_name, "a1b2")
    assert len(name.split("/")[-1].replace("-a1b2", "")) <= 50
