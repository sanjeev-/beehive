#!/usr/bin/env python3
"""
Generate a Homebrew formula for beehive from pyproject.toml.
"""
import json
import re
import tomllib
from pathlib import Path
from urllib.request import urlopen


def fetch_pypi_metadata(package_name: str, version: str = None) -> dict:
    """Fetch package metadata from PyPI JSON API."""
    if version:
        url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    else:
        url = f"https://pypi.org/pypi/{package_name}/json"

    with urlopen(url) as response:
        return json.loads(response.read())


def get_sdist_info(package_name: str, version: str = None) -> tuple[str, str]:
    """Get the sdist URL and SHA256 for a package."""
    metadata = fetch_pypi_metadata(package_name, version)

    # Find the sdist in the URLs
    for url_info in metadata['urls']:
        if url_info['packagetype'] == 'sdist':
            return url_info['url'], url_info['digests']['sha256']

    raise ValueError(f"No sdist found for {package_name}")


def parse_version_spec(spec: str) -> str:
    """Extract version from a dependency specification like 'package>=1.0.0'."""
    # Remove version constraints, just get the package name
    match = re.match(r'^([a-zA-Z0-9_-]+)', spec)
    if match:
        return match.group(1)
    return spec


def get_all_dependencies(dependencies: list[str]) -> dict[str, tuple[str, str]]:
    """
    Resolve all dependencies (including transitive) and get their sdist info.
    Returns a dict of package_name -> (url, sha256)
    """
    result = {}
    to_process = list(dependencies)
    processed = set()

    while to_process:
        dep_spec = to_process.pop(0)
        package_name = parse_version_spec(dep_spec)

        if package_name in processed:
            continue

        processed.add(package_name)
        print(f"Fetching metadata for {package_name}...")

        try:
            url, sha256 = get_sdist_info(package_name)
            result[package_name] = (url, sha256)

            # Get transitive dependencies
            metadata = fetch_pypi_metadata(package_name)
            info = metadata.get('info', {})
            requires_dist = info.get('requires_dist', [])

            if requires_dist:
                for req in requires_dist:
                    # Skip optional dependencies (with extras or markers)
                    if ';' in req or 'extra ==' in req:
                        continue
                    req_name = parse_version_spec(req)
                    if req_name not in processed:
                        to_process.append(req)

        except Exception as e:
            print(f"Warning: Could not fetch {package_name}: {e}")
            continue

    return result


def generate_formula(version: str, dependencies: dict[str, tuple[str, str]]) -> str:
    """Generate the Homebrew formula Ruby code."""

    # Sort dependencies alphabetically
    sorted_deps = sorted(dependencies.items())

    # Generate resource blocks
    resource_blocks = []
    for package_name, (url, sha256) in sorted_deps:
        resource_blocks.append(f'''  resource "{package_name}" do
    url "{url}"
    sha256 "{sha256}"
  end''')

    resources_section = '\n\n'.join(resource_blocks)

    formula = f'''class Beehive < Formula
  include Language::Python::Virtualenv

  desc "Manage multiple Claude Code agent sessions"
  homepage "https://github.com/sanjeev-/beehive"
  url "https://github.com/sanjeev-/beehive/archive/refs/tags/v{version}.tar.gz"
  sha256 "PLACEHOLDER_SHA256_UPDATE_AFTER_RELEASE"
  license "MIT"

  depends_on "python@3.12"
  depends_on "tmux"
  depends_on "gh"

{resources_section}

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "beehive", shell_output("#{{bin}}/beehive --help")
  end
end
'''

    return formula


def main():
    # Read pyproject.toml
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    version = pyproject['project']['version']
    dependencies = pyproject['project']['dependencies']

    print(f"Beehive version: {version}")
    print(f"Base dependencies: {dependencies}")
    print("\nResolving all dependencies (including transitive)...\n")

    # Get all dependencies with their sdist info
    all_deps = get_all_dependencies(dependencies)

    print(f"\nTotal dependencies resolved: {len(all_deps)}")

    # Generate formula
    formula_content = generate_formula(version, all_deps)

    # Write to Formula/beehive.rb
    formula_path = Path(__file__).parent.parent / "Formula" / "beehive.rb"
    formula_path.parent.mkdir(exist_ok=True)
    with open(formula_path, "w") as f:
        f.write(formula_content)

    print(f"\nFormula written to {formula_path}")


if __name__ == "__main__":
    main()
