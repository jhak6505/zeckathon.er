#!/usr/bin/env bash
# FINHYPE: One-Command Pipeline Runner for Linux / macOS

if [ -f ".venv/bin/python" ]; then
    PY_CMD=".venv/bin/python"
else
    PY_CMD="python"
fi

$PY_CMD run_pipeline.py "$@"

