"""Extract Maya's built-in icons from its Qt resources.

Node icons (:/out_<type>.png) go to ./icons, the Node Editor toolbar icons (the set built by
nodeEdCreateToolbar in scripts/others/nodeEditorPanel.mel) go to ./icons/toolbar.
The HiDPI variant (<name>_200.png, 2x) is preferred when it exists.

Run with mayapy: "C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe" tools/extract_icons.py
Toolbar icons only resolve inside the Maya GUI: exec this file from the Script Editor or commandPort.
"""
import os
import sys

from PySide6 import QtGui, QtWidgets

# Inside the Maya GUI a QApplication already exists and every icon library is loaded; the
# Node Editor toolbar icons are only available there. Under mayapy, start standalone first.
if QtWidgets.QApplication.instance() is None:
    import maya.standalone
    maya.standalone.initialize(name="python")
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

NODE_TYPES = [
    "joint", "transform", "decomposeMatrix", "composeMatrix", "multMatrix", "blendMatrix",
    "plusMinusAverage", "multiplyDivide", "distanceBetween", "condition", "reverse",
    "clamp", "remapValue", "blendColors",
]
TOOLBAR = [
    "createNode", "openBar", "syncOn", "syncOff",
    "hsUpStreamCon", "hsUpDownStreamCon", "hsDownStreamCon",
    "hsClearView", "nodeGrapherAddNodes", "nodeGrapherRemoveNodes", "hsRearrange",
    "nodeGrapherModeSimpleLarge", "nodeGrapherModeConnectedLarge", "nodeGrapherModeAllLarge",
    "nodeGrapherModeCustomLarge", "search", "nodeGrapherSwatchToggle",
    "addBookmark", "editBookmark", "SP_FileDialogBack", "SP_FileDialogForward",
    "nodeGrapherDisplayAll", "nodeGrapherDisplayAllExcept", "nodeGrapherDisplayNone",
    "nodeGrapherUnlocked", "nodeGrapherLocked",
    "zeroDepth", "reduceDepth", "increaseDepth", "unlimitedDepth",
    "nodeGridDisplay", "snapGrid",
]
# Output goes to <repo>/icons. Exec'd inside Maya there is no __file__: set NODEX_ROOT instead.
if "__file__" in globals():
    HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
else:
    HERE = os.environ.get("NODEX_ROOT", os.getcwd())


def extract(names, out_dir, patterns):
    os.makedirs(out_dir, exist_ok=True)
    for n in names:
        for pat in patterns:
            res = pat % n
            img = QtGui.QImage(res)
            if not img.isNull():
                img.save(os.path.join(out_dir, n + ".png"))
                print("OK   %-30s %s %dx%d" % (n, res, img.width(), img.height()))
                break
        else:
            print("MISS %s" % n)


extract(NODE_TYPES, os.path.join(HERE, "icons"), (":/out_%s_200.png", ":/out_%s_150.png", ":/out_%s.png"))
extract(TOOLBAR, os.path.join(HERE, "icons", "toolbar"), (":/%s_200.png", ":/%s_150.png", ":/%s.png", ":/%s.svg"))
