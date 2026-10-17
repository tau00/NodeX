@echo off
rem NodeX tests: stdlib unittest under mayapy (no user scene touched). Run from a desktop session:
rem the shader test opens real windows and needs working Direct3D 11 and OpenGL.
rem Set MAYAPY beforehand to use another Maya (2025+ are supported).
if not defined MAYAPY set "MAYAPY=C:\Program Files\Autodesk\Maya2026\bin\mayapy.exe"
set "PYTHONPATH=%~dp0.."
cd /d "%~dp0"
"%MAYAPY%" -m unittest discover -s . -p "test_*.py" -v
