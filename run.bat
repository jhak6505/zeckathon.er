@echo off
REM FINHYPE: One-Command Pipeline Runner for Windows
SETLOCAL

IF EXIST ".venv\Scripts\python.exe" (
    SET "PY_CMD=.venv\Scripts\python.exe"
) ELSE (
    SET "PY_CMD=python"
)

%PY_CMD% run_pipeline.py %*

ENDLOCAL

