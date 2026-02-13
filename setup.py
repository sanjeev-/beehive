"""Setup file for backward compatibility with older pip versions."""

from setuptools import setup, find_packages

setup(
    name="beehive-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.0",
        "pydantic>=2.0.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "beehive=beehive.cli:cli",
        ],
    },
    python_requires=">=3.9",
)
