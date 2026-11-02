@echo off
REM Install dependencies once using: python -m pip install -r CrosshairGUI\requirements.txt
REM Starting the controller does not run pip or create a background service.
python "%~dp0gui.py"
exit /b %errorlevel%
