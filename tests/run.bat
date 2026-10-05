@echo off
rem NodeX headless tests: stdlib unittest under mayapy (no GUI, no user scene touched).
rem Set MAYAPY beforehand to use another Maya (2022-2024 are supported).
if not defined MAYAPY set "MAYAPY=C:\Program Files\Autodesk\Maya2024\bin\mayapy.exe"
set "PYTHONPATH=%~dp0.."
cd /d "%~dp0"
"%MAYAPY%" -m unittest discover -s . -p "test_*.py" -v
