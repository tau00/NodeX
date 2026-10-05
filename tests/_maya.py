"""Shared headless Maya start for the NodeX tests (run with mayapy, see tests/run.bat)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT in sys.path:
    sys.path.remove(ROOT)
sys.path.insert(0, ROOT)

_started = [False]


def start():
    if _started[0]:
        return
    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as cmds
    cmds.undoInfo(state=True, infinity=True)
    try:
        cmds.loadPlugin("matrixNodes", quiet=True)
    except RuntimeError:
        pass
    _started[0] = True


def fresh_scene():
    import maya.cmds as cmds
    cmds.file(new=True, force=True)
    cmds.undoInfo(state=True, infinity=True)
    cmds.flushUndo()
