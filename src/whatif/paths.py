"""
src/whatif/paths.py
====================
Resolves absolute filesystem paths for the What-If Analysis module's
file-based config/model/historian storage (Data/, Results/), anchored to
the repo root rather than the process's current working directory.

This fixes the one fragile bit of the original Scripts/whatif_runner.py:
it used paths relative to os.getcwd() at call time (e.g. "..\\Data"),
which only worked because Streamlit was always launched from Scripts/.
A FastAPI process may be launched from anywhere, so every path here is
computed from this file's own location instead.
"""
from __future__ import annotations

import os

from config import settings

# src/whatif/paths.py -> src/whatif -> src -> <repo root>
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _abs(relative: str) -> str:
    return os.path.normpath(os.path.join(_REPO_ROOT, relative))


def data_dir() -> str:
    return _abs(settings.WHATIF_DATA_DIR)


def results_dir() -> str:
    return _abs(settings.WHATIF_RESULTS_DIR)


def model_dir() -> str:
    return _abs(settings.WHATIF_MODEL_DIR)


def config_file() -> str:
    return _abs(settings.WHATIF_CONFIG_FILE)


def training_workbook() -> str:
    return _abs(settings.WHATIF_TRAINING_WORKBOOK)


def historian_file() -> str:
    return _abs(settings.WHATIF_HISTORIAN_FILE)


def scripts_dir() -> str:
    return _abs("Scripts")


def whatif_train_script() -> str:
    return os.path.join(scripts_dir(), "Model_development_and_static_whatif_testing.py")


def actual_vs_estimated_file(suffix: str) -> str:
    """Per-request output filename (never the fixed original name, to avoid
    concurrent-request overwrites — see engine.py's write_actual_vs_estimated_xlsx)."""
    return os.path.join(results_dir(), f"Actual_vs_estimated_what_if_{suffix}.xlsx")
