@echo off
rem ===========================================================================
rem  Recover-NX-Images.bat - launcher for nx_recover.py
rem  NX Image Recovery. Copyright (c) 2026 cimply.
rem
rem  1. Copy the NX cache files loose into the "input" folder next to this file.
rem  2. Double-click this file.
rem  3. Recovered images appear in the "output" folder.
rem
rem  This file only: finds Python, installs numpy + pillow if they're missing,
rem  and runs nx_recover.py. It does not touch any other files or settings.
rem ===========================================================================
setlocal
title Agfa NX image recovery
cd /d "%~dp0"

rem ---------------------------------------------------------------------------
rem  STEP 1 - Find Python 3 (the "py" launcher first, then "python").
rem  Nothing is installed or changed here; it only checks what exists.
rem ---------------------------------------------------------------------------
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    where python >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo Python 3 was not found.
    echo Install it from https://www.python.org/downloads/ ^(tick "Add to PATH"^), then run this again.
    pause
    exit /b 1
)

rem ---------------------------------------------------------------------------
rem  STEP 2 - Make sure numpy and pillow are available.
rem  If they're already installed, nothing happens. If not, they're
rem  downloaded from PyPI (the standard Python package site) into the current
rem  user's Python only (--user, no admin rights). This is the ONLY step that
rem  uses the internet.
rem ---------------------------------------------------------------------------
%PY% -c "import numpy, PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing numpy and pillow for this user...
    %PY% -m pip install --user --quiet --disable-pip-version-check numpy pillow
    if errorlevel 1 (
        echo Could not install numpy/pillow. Check internet access and try again.
        pause
        exit /b 1
    )
)

rem ---------------------------------------------------------------------------
rem  STEP 3 - Run the converter on the "input" folder, saving to "output".
rem  Both folders sit next to this file and are created if missing.
rem  Optional extras (e.g. --from 2026-10-21) can be added after the .bat name
rem  when run from a command prompt; they're passed straight through.
rem ---------------------------------------------------------------------------
if not exist "%~dp0input" mkdir "%~dp0input"
if not exist "%~dp0output" mkdir "%~dp0output"
%PY% "%~dp0nx_recover.py" %*
echo.
pause
