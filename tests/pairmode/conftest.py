"""Pytest configuration for pairmode tests.

Adds the anchor repo root to sys.path so that ``skills.*`` packages are
importable without installing the package in editable mode.
"""

import pathlib
import sys

# Repo root is three levels above this file: tests/pairmode/conftest.py
_repo_root = pathlib.Path(__file__).parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
