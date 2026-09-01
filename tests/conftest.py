"""Ensure ``detail``/``server`` are importable from the repo root during pytest."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))