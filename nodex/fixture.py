"""The demo rig (a small transform/joint graph) as a real scene: used by tests and live checks."""
import maya.cmds as cmds

NAMES = {
    "j1": "leg_back_01_l_int",
    "j4": "leg_back_04_l_int",
    "dm1": "decomposeMatrix1",
    "dm2": "decomposeMatrix2",
    "pma": "leg_mid_pma",
    "db": "leg_length_dist",
    "md": "leg_stretch_md",
    "mid": "leg_mid_grp",
    "j2": "leg_back_02_l_int",
}

WIRES = [
    ("j1", "worldMatrix[0]", "dm1", "inputMatrix"),
    ("j4", "worldMatrix[0]", "dm2", "inputMatrix"),
    ("dm1", "outputTranslate", "pma", "input3D[0]"),
    ("dm2", "outputTranslate", "pma", "input3D[1]"),
    ("dm1", "outputTranslate", "db", "point1"),
    ("dm2", "outputTranslate", "db", "point2"),
    ("db", "distance", "md", "input1X"),
    ("pma", "output3D", "mid", "translate"),
    ("md", "outputX", "j2", "scaleX"),
    ("dm1", "outputRotate", "mid", "rotate"),
    ("dm2", "outputRotateZ", "md", "input1Y"),   # angle -> double: Maya inserts unitConversion
]


def build(prefix=""):
    """Create the fixture rig; returns {key: node name}."""
    if not cmds.pluginInfo("matrixNodes", q=True, loaded=True):
        try:
            cmds.loadPlugin("matrixNodes", quiet=True)
        except RuntimeError:
            pass
    n = {}
    cmds.select(clear=True)
    n["j1"] = cmds.joint(name=prefix + NAMES["j1"], position=(0, 10, 0))
    cmds.select(clear=True)
    n["j4"] = cmds.joint(name=prefix + NAMES["j4"], position=(2, 1, 4))
    cmds.select(clear=True)
    n["j2"] = cmds.joint(name=prefix + NAMES["j2"], position=(1, 5, 2))
    cmds.select(clear=True)
    n["mid"] = cmds.createNode("transform", name=prefix + NAMES["mid"])
    n["dm1"] = cmds.createNode("decomposeMatrix", name=prefix + NAMES["dm1"])
    n["dm2"] = cmds.createNode("decomposeMatrix", name=prefix + NAMES["dm2"])
    n["pma"] = cmds.createNode("plusMinusAverage", name=prefix + NAMES["pma"])
    n["db"] = cmds.createNode("distanceBetween", name=prefix + NAMES["db"])
    n["md"] = cmds.createNode("multiplyDivide", name=prefix + NAMES["md"])
    cmds.setAttr(n["pma"] + ".operation", 3)
    cmds.setAttr(n["md"] + ".operation", 2)
    cmds.setAttr(n["md"] + ".input2X", 12.48)
    for a, pa, b, pb in WIRES:
        cmds.connectAttr(n[a] + "." + pa, n[b] + "." + pb, force=True)
    return n


def cleanup(prefix=""):
    for key, name in NAMES.items():
        for hit in cmds.ls(prefix + name) or []:
            if cmds.objExists(hit):
                cmds.delete(hit)
