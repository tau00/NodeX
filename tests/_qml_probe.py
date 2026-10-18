"""QML half of test_qml.py -- runs in its OWN mayapy process, never under maya.standalone.

maya.standalone installs a bare QGuiApplication, after which any QtWidgets object segfaults
(global leaf mayapy-headless-test-harness), so Board.qml is loaded here in a clean process with
a QApplication, and the result goes back to the test as one JSON line on stdout.

The Bridge is the real class from nodex/bridge.py (its signal and slot declarations are what
is under test), created WITHOUT its __init__ so no Maya scene or callback is touched.

    mayapy _qml_probe.py [snapshot.json [frame.png]]
"""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # "windows" for real fonts in a frame
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6 import QtCore, QtQml, QtQuickWidgets, QtWidgets  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

from nodex import bridge, panel  # noqa: E402


class _Store(object):
    tab = {}


def make_bridge(snapshot):
    b = bridge.Bridge.__new__(bridge.Bridge)
    QtCore.QObject.__init__(b)
    b.store = _Store()
    b.infos = dict((n["id"], n) for n in snapshot["nodes"])
    b.wires = snapshot["wires"]
    b.sel = list(snapshot["sel"])
    b.cursor = None
    b._ignore_selection = 0
    b._select_in_maya = lambda: None
    b._mark_modified = lambda: None     # the one Maya call at the end of moveNodes
    b._connection_result = None
    return b


def signals():
    mo = bridge.Bridge.staticMetaObject
    out = []
    for i in range(mo.methodOffset(), mo.methodCount()):
        m = mo.method(i)
        if m.methodType() == QtCore.QMetaMethod.Signal:
            out.append({"name": bytes(m.name()).decode(),
                        "types": [bytes(t).decode() for t in m.parameterTypes()],
                        "names": [bytes(n).decode() for n in m.parameterNames()]})
    return out


def capture_messages():
    """Collect every Qt message (qWarning and friends) into the returned list. Shader and
    deprecation messages go to the message handler, never to QQmlEngine.warnings."""
    messages = []

    def handler(kind, context, text):
        messages.append(text)
    QtCore.qInstallMessageHandler(handler)
    return messages


def pump(ms):
    t = QtCore.QElapsedTimer()
    t.start()
    while t.elapsed() < ms:
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)


def find_items(item, name):
    """Every visual descendant of `item` with this objectName (Loader content included)."""
    out = []
    for child in item.childItems():
        if child.objectName() == name:
            out.append(child)
        out.extend(find_items(child, name))
    return out


def type_icon(root):
    """The header icon of a built node whose type ships a local 128 px copy in nodex/icons:
    status, and the loaded pixmap size. implicitWidth, not sourceSize -- sourceSize reads back
    whatever was requested even when a smaller file loaded."""
    shipped = set(f[:-4] for f in os.listdir(os.path.join(ROOT, "nodex", "icons")) if f.endswith(".png"))
    t = QtCore.QElapsedTimer()
    t.start()
    while t.elapsed() < 3000:
        for it in find_items(root, "typeIcon"):
            # Image.Status has no Python converter; read it through QML.
            e = QtQml.QQmlExpression(QtQml.QQmlEngine.contextForObject(it), it,
                'JSON.stringify({type: type, status: status, w: implicitWidth, h: implicitHeight})')
            v = e.evaluate()
            r = json.loads(v[0] if isinstance(v, tuple) else v)
            if r["type"] in shipped and r["status"] != 2:   # 2: Image.Loading
                return r
        pump(50)
    return None


def main():
    snap = {"nodes": [], "wires": [], "sel": [], "lead": ""}
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            snap = json.load(f)
    res = {"signals": signals()}
    messages = capture_messages()
    b = make_bridge(snap)
    q = QtQuickWidgets.QQuickWidget()
    q.setResizeMode(QtQuickWidgets.QQuickWidget.SizeRootObjectToView)
    panel.add_maya_qml_dir(q.engine())
    warnings = []
    q.engine().warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    q.rootContext().setContextProperty("bridge", b)
    q.resize(900, 600)
    q.setSource(QtCore.QUrl.fromLocalFile(os.path.join(panel.QML_DIR, "Board.qml")))
    res["status"] = str(q.status())
    res["errors"] = [e.toString() for e in q.errors()]
    root = q.rootObject()
    if root is not None:
        q.show()
        pump(150)
        res["nodeItems"] = root.property("nodesVersion")
        res["typeIcon"] = type_icon(root)
        # Every QML-bound signal must reach its handler with its arguments intact.
        b.viewRequested.emit(11.0, 22.0, 1.5)
        b.wiresChanged.emit(json.dumps(snap["wires"][:1]))
        b.selectionChanged.emit(snap["sel"][:1], snap["lead"])
        pump(50)
        res["view"] = [root.property("panX"), root.property("panY"), root.property("zoom")]
        wl = root.property("wireList")      # a `var` property arrives as QJSValue
        res["wireCount"] = len(wl.toVariant() if hasattr(wl, "toVariant") else wl)
        res["lead"] = root.property("lead")
        # JS arrays/objects reach "QVariant" slots as QJSValue; a slot that iterates the raw
        # value raises, and the exception aborts the calling QML handler (stuck marquee).
        # Ids that are not on the board keep these calls away from Maya.
        calls = {}
        for name, expr in (("disconnectWires", 'bridge.disconnectWires(["nope"])'),
                           ("moveNodes", 'bridge.moveNodes({"nope": [1, 2]})'),
                           ("bundleTip", 'bridge.bundleTip(["nope"])')):
            e = QtQml.QQmlExpression(q.rootContext(), root, expr + '; "ok"')
            v = e.evaluate()
            calls[name] = e.error().toString() if e.hasError() else (v[0] if isinstance(v, tuple) else v)
        res["jsCalls"] = calls
        # A middle-drag pan while the smooth zoom is still easing must carry the zoom's view
        # on: the pan used to be absolute from the press and threw the view back (teleport).
        from PySide6 import QtGui

        def mmb(kind, x, button, buttons):
            p = QtCore.QPointF(x, 300)
            QtWidgets.QApplication.sendEvent(q, QtGui.QMouseEvent(
                kind, p, QtCore.QPointF(q.mapToGlobal(p.toPoint())), button, buttons, QtCore.Qt.NoModifier))
        mid = QtCore.Qt.MiddleButton
        mmb(QtCore.QEvent.MouseButtonPress, 450, mid, mid)
        mmb(QtCore.QEvent.MouseMove, 460, QtCore.Qt.NoButton, mid)
        QtQml.QQmlExpression(q.rootContext(), root, "zoomSmooth(2.0, 450, 300)").evaluate()
        pump(400)
        px = root.property("panX")
        mmb(QtCore.QEvent.MouseMove, 470, QtCore.Qt.NoButton, mid)
        mmb(QtCore.QEvent.MouseButtonRelease, 470, mid, QtCore.Qt.NoButton)
        res["panJump"] = round(root.property("panX") - (px + 10), 3)
        res["zoomAfterPan"] = round(root.property("zoom"), 3)
        focus_nodes = [n['id'] for n in snap['nodes'][:2]]
        focus_wires = [w['id'] for w in snap['wires'][:1]]
        b.connectionsFound.emit(focus_nodes, focus_wires)
        pump(50)
        e = QtQml.QQmlExpression(q.rootContext(), root,
            'JSON.stringify({nodes:Object.keys(connectionFocus.nodes), '
            'wires:Object.keys(connectionFocus.wires)})')
        value = e.evaluate()
        res['connectionFocus'] = json.loads(value[0] if isinstance(value, tuple) else value)
        QtWidgets.QApplication.sendEvent(q, QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier))
        pump(10)
        res['focusCleared'] = root.property('connectionFocus') is None
        img = q.grabFramebuffer()
        if len(sys.argv) > 2:
            img.save(sys.argv[2])
        res["frame"] = [img.width(), img.height()]
    res["warnings"] = warnings
    res["qtMessages"] = messages
    sys.stdout.write("NODEX_PROBE " + json.dumps(res) + "\n")
    sys.stdout.flush()


if __name__ == '__main__':
    main()
