"""Shader half of test_qml.py: Board.qml on the REAL `windows` platform, so the RHI actually
compiles and runs its ShaderEffects (offscreen never does). The backend is whatever
QSG_RHI_BACKEND (d3d11 | opengl) in this process's environment asks for.

A broken ShaderEffect never reaches QQuickWidget.errors() or QQmlEngine.warnings -- it just
draws nothing -- so this reports the three signals that do see it: each effect's `status`
(+ `log`), the Qt messages about shaders / pipelines, and whether hiding the effect changes
the frame at all.

    mayapy _shader_probe.py snapshot.json
"""
import json
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "windows"

from _qml_probe import app, capture_messages, make_bridge, pump  # noqa: E402
from PySide6 import QtCore, QtQml, QtQuickWidgets  # noqa: E402
from nodex import panel  # noqa: E402

NAMES = ("gridShader", "greekShader")


def effects(item, out):
    if item.objectName() in NAMES:
        out.append(item)
    for child in item.childItems():
        effects(child, out)
    return out


def status_name(ctx, obj):
    # PySide has no converter for QQuickShaderEffect::Status; read it as an int through QML.
    mo = obj.metaObject()
    value = QtQml.QQmlExpression(ctx, obj, "status").evaluate()
    value = value[0] if isinstance(value, tuple) else value
    return mo.property(mo.indexOfProperty("status")).enumerator().valueToKey(int(value))


def main():
    with open(sys.argv[1]) as f:
        snap = json.load(f)
    messages = capture_messages()
    b = make_bridge(snap)
    q = QtQuickWidgets.QQuickWidget()
    q.setResizeMode(QtQuickWidgets.QQuickWidget.SizeRootObjectToView)
    panel.add_maya_qml_dir(q.engine())
    q.rootContext().setContextProperty("bridge", b)
    q.resize(900, 600)
    q.setSource(QtCore.QUrl.fromLocalFile(os.path.join(panel.QML_DIR, "Board.qml")))
    res = {"errors": [e.toString() for e in q.errors()]}
    root = q.rootObject()
    if root is not None:
        q.show()
        pump(150)
        # Below the far threshold (Board.qml: zoom < 0.42) every node draws its greek bars.
        root.setProperty("showGrid", True)
        root.setProperty("panX", 20.0)
        root.setProperty("panY", 20.0)
        root.setProperty("zoom", 0.3)
        pump(400)
        frame = q.grabFramebuffer()
        found = effects(root, [])
        res["status"] = {}
        res["draws"] = {}
        for name in NAMES:
            items = [e for e in found if e.objectName() == name]
            res["status"][name] = [{"status": status_name(q.rootContext(), e), "log": e.property("log") or ""}
                                   for e in items]
            # Hiding the effects must change the frame, or they were drawing nothing.
            for e in items:
                e.setProperty("visible", False)
            pump(100)
            res["draws"][name] = bool(items) and q.grabFramebuffer() != frame
            for e in items:
                e.setProperty("visible", True)
            pump(100)
    api = q.quickWindow().rendererInterface().graphicsApi()
    res["api"] = getattr(api, "name", str(api))
    res["qtMessages"] = [m for m in messages
                         if "shader" in m.lower() or "pipeline" in m.lower()]
    sys.stdout.write("NODEX_SHADERS " + json.dumps(res) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
