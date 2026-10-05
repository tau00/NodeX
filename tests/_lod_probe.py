"""LOD probe: Board.qml on the column graph of _perf_probe.py, in its own mayapy.

Saves a frame at a far zoom (greek bars) and a near one (text), and times the zoom that
crosses `far` (detail built through the board's build queue): the frame of the crossing and
the time until the queue is drained. Prints one NODEX_LOD json line.

    set QT_QPA_PLATFORM=windows & mayapy _lod_probe.py [nodes] [out_prefix]
"""
import json
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv, _argv = sys.argv[:1], sys.argv     # _perf_probe parses argv when it runs main()
_src = open(os.path.join(HERE, "_perf_probe.py")).read().replace("\nmain()\n", "\n")
exec(compile(_src, "_perf_probe.py", "exec"))   # column(), _probe, app, panel ...
sys.argv = _argv

from PySide2 import QtCore, QtQuickWidgets  # noqa: E402


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    prefix = sys.argv[2] if len(sys.argv) > 2 else None
    snap = column(n)
    b = _probe.make_bridge(snap)
    q = QtQuickWidgets.QQuickWidget()
    q.setResizeMode(QtQuickWidgets.QQuickWidget.SizeRootObjectToView)
    q.engine().addImportPath(panel.maya_qml_dir())
    warnings = []
    q.engine().warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    q.rootContext().setContextProperty("bridge", b)
    q.resize(1274, 1000)
    q.setSource(QtCore.QUrl.fromLocalFile(os.path.join(panel.QML_DIR, "Board.qml")))
    r = q.rootObject()
    q.show()
    res = {"nodes": n}

    def view(z):
        r.setProperty("zoom", z)
        r.setProperty("panX", 40.0)
        r.setProperty("panY", 60.0 - 6 * 330 * z)

    view(0.35)
    _probe.pump(400)
    if prefix:
        q.grabFramebuffer().save(prefix + "_far.png")
    t = time.perf_counter()
    view(0.6)
    q.grabFramebuffer()
    res["cross_frame_ms"] = round((time.perf_counter() - t) * 1000, 1)
    from PySide2 import QtQml

    def ev(expr):
        v = QtQml.QQmlExpression(q.rootContext(), r, expr).evaluate()
        return v[0] if isinstance(v, tuple) else v

    t = time.perf_counter()
    while ev("buildQueue.length") and time.perf_counter() - t < 10:
        app.processEvents(QtCore.QEventLoop.AllEvents, 5)
    res["drain_ms"] = round((time.perf_counter() - t) * 1000, 1)
    res["queue_left"] = ev("buildQueue.length")
    res["built"] = ev("var n = 0; for (var k in nodeItems) if (nodeItems[k].built) n++; n")
    res["visible"] = ev("var n = 0; for (var k in nodeItems) if (nodeItems[k].visible) n++; n")
    res["shift_mutates"] = ev("var a = buildQueue, n = a.length; a.shift(); [n, buildQueue.length].join('>')")
    res["head"] = ev("var it = buildQueue[0]; JSON.stringify([!!it, it ? it.nid : null, "
                     "it ? nodeItems[it.nid] === it : null, it ? it.built : null, far, it ? it.visible : null])")
    _probe.pump(200)
    if prefix:
        q.grabFramebuffer().save(prefix + "_near.png")
    t = time.perf_counter()
    view(0.35)
    q.grabFramebuffer()
    res["back_far_ms"] = round((time.perf_counter() - t) * 1000, 1)
    res["warnings"] = [w for w in warnings if "qrc:/" not in w][:10]
    sys.stdout.write("NODEX_LOD " + json.dumps(res) + "\n")


main()
