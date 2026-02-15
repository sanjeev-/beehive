#!/usr/bin/env python3
"""
Generate a Homebrew formula for beehive-cli.

This script reads dependencies from pyproject.toml, fetches metadata from PyPI,
and generates a valid Homebrew formula with all required resources.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Dict, Set, List, Tuple


def read_pyproject() -> Tuple[str, List[str]]:
    """Read version and dependencies from pyproject.toml."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject_path.read_text()

    # Extract version
    version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if not version_match:
        raise ValueError("Could not find version in pyproject.toml")
    version = version_match.group(1)

    # Extract dependencies
    deps_section = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if not deps_section:
        raise ValueError("Could not find dependencies in pyproject.toml")

    deps_text = deps_section.group(1)
    dependencies = []
    for line in deps_text.split('\n'):
        line = line.strip().strip(',').strip('"').strip("'")
        if line and not line.startswith('#'):
            # Extract package name (before >= or ==)
            pkg_name = re.split(r'[><=!]', line)[0].strip()
            if pkg_name:
                dependencies.append(pkg_name)

    return version, dependencies


def fetch_pypi_metadata(package: str) -> Dict:
    """Fetch package metadata from PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"Error fetching metadata for {package}: {e}", file=sys.stderr)
        raise


def normalize_package_name(package: str) -> str:
    """Normalize package name by removing version specifiers and special chars."""
    # Remove version specifiers like ~=, >=, etc.
    pkg = re.split(r'[><=!~\[\s]', package)[0].strip()
    # Convert underscores to hyphens (PyPI naming convention)
    pkg = pkg.replace('_', '-')
    return pkg


def get_transitive_dependencies(package: str, visited: Set[str] = None) -> Set[str]:
    """Recursively fetch all transitive dependencies of a package."""
    if visited is None:
        visited = set()

    # Normalize package name
    package = normalize_package_name(package)

    if package in visited:
        return visited

    visited.add(package)

    try:
        metadata = fetch_pypi_metadata(package)
        info = metadata.get('info', {})
        requires_dist = info.get('requires_dist', [])

        if requires_dist:
            for req in requires_dist:
                # Skip optional dependencies (those with semicolon conditions)
                if ';' in req:
                    # Only include if it's a basic Python version requirement
                    if 'extra ==' in req or 'platform_' in req:
                        continue

                # Extract package name (before any version specifier)
                dep_name = normalize_package_name(req)
                if dep_name and dep_name not in visited:
                    get_transitive_dependencies(dep_name, visited)
    except Exception as e:
        print(f"Warning: Could not fetch dependencies for {package}: {e}", file=sys.stderr)

    return visited


def get_sdist_info(package: str) -> Tuple[str, str]:
    """Get the sdist URL and SHA256 for the latest version of a package."""
    metadata = fetch_pypi_metadata(package)

    # Get URLs from the latest version
    urls = metadata.get('urls', [])

    # Find the sdist (source distribution)
    for url_info in urls:
        if url_info.get('packagetype') == 'sdist':
            return url_info['url'], url_info['digests']['sha256']

    raise ValueError(f"No sdist found for package {package}")


def generate_formula(version: str, dependencies: List[str]) -> str:
    """Generate the Homebrew formula Ruby code."""

    # Collect all dependencies (direct + transitive)
    all_deps = set()
    for dep in dependencies:
        print(f"Collecting dependencies for {dep}...", file=sys.stderr)
        deps = get_transitive_dependencies(dep)
        all_deps.update(deps)

    # Sort dependencies for consistent output
    sorted_deps = sorted(all_deps)

    print(f"\nTotal dependencies (including transitive): {len(sorted_deps)}", file=sys.stderr)
    print(f"Dependencies: {', '.join(sorted_deps)}\n", file=sys.stderr)

    # Generate resource blocks
    resources = []
    for dep in sorted_deps:
        print(f"Fetching sdist info for {dep}...", file=sys.stderr)
        try:
            url, sha256 = get_sdist_info(dep)
            resources.append(f'''  resource "{dep}" do
    url "{url}"
    sha256 "{sha256}"
  end''')
        except Exception as e:
            print(f"Error getting sdist for {dep}: {e}", file=sys.stderr)
            continue

    resources_block = '\n\n'.join(resources)

    # Generate the formula
    formula = f'''# Homebrew formula for beehive-cli
# Generated by scripts/generate_formula.py

class Beehive < Formula
  include Language::Python::Virtualenv

  desc "Manage multiple Claude Code agent sessions"
  homepage "https://github.com/sanjeev-/beehive"
  url "https://github.com/sanjeev-/beehive/archive/refs/tags/v{version}.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"

  depends_on "python@3.12"
  depends_on "tmux"
  depends_on "gh"

{resources_block}

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"beehive", "--version"
  end
end
'''

    return formula


def main():
    """Main entry point."""
    print("Reading pyproject.toml...", file=sys.stderr)
    version, dependencies = read_pyproject()

    print(f"Version: {version}", file=sys.stderr)
    print(f"Direct dependencies: {', '.join(dependencies)}", file=sys.stderr)

    print("\nGenerating Homebrew formula...", file=sys.stderr)
    formula = generate_formula(version, dependencies)

    # Write to Formula/beehive.rb
    output_path = Path(__file__).parent.parent / "Formula" / "beehive.rb"
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(formula)

    print(f"\n✓ Formula written to {output_path}", file=sys.stderr)
    print(f"✓ Generated formula with {len(formula.splitlines())} lines", file=sys.stderr)


if __name__ == "__main__":
    main()
