"""Frame-time probe for big boards -- Board.qml on a synthetic graph, in its own mayapy.

Shaped like a real rig that was slow (591 nodes, 7533 wires, 12.5k rows): joints feeding
parentConstraints feeding joints. Uses the real Bridge class without its __init__ (like
_probe.py), so nothing touches a Maya scene. Prints one JSON line of timings.

    set QT_QPA_PLATFORM=windows & mayapy _perf_probe.py [pairs | column:N | fan:N] [frame.png]
"""
import json
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6 import QtCore, QtQuickWidgets, QtWidgets  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

from nodex import bridge, panel  # noqa: E402


class _Store(object):
    tab = {}


class _probe(object):
    """The two helpers of _probe.py (that module runs its main() on import)."""

    @staticmethod
    def make_bridge(snapshot):
        b = bridge.Bridge.__new__(bridge.Bridge)
        QtCore.QObject.__init__(b)
        b.store = _Store()
        b.infos = dict((n["id"], n) for n in snapshot["nodes"])
        b.wires = snapshot["wires"]
        b.sel = list(snapshot["sel"])
        b.cursor = None
        b._mark_modified = lambda: None
        return b

    @staticmethod
    def pump(ms):
        t = QtCore.QElapsedTimer()
        t.start()
        while t.elapsed() < ms:
            app.processEvents(QtCore.QEventLoop.AllEvents, 20)


def rows_for(n, conn_in, conn_out, y0=32):
    rows, anchors, parents, y = [], {}, {}, y0
    for i in range(n):
        key = "attr%d" % i
        r = {"kind": "port", "key": key, "label": "Attribute %d" % i, "depth": 0, "h": 20,
             "inPort": True, "outPort": True, "inConn": i < conn_in, "outConn": i < conn_out,
             "cls": "Numeric" if i % 3 else "Matrix", "compound": False,
             "color": "#8fbf6f" if i % 3 else "#e0a45c",
             "chev": 0, "valueKind": "num" if i >= conn_in else "", "value": "1.0", "more": 0,
             "hit": "", "y": y}
        rows.append(r)
        anchors[key] = y + 10
        parents[key] = ""
        y += 20
    return rows, anchors, parents, y + 3


def node(uid, name, typ, x, y, n_rows, cin, cout):
    rows, anchors, parents, h = rows_for(n_rows, cin, cout)
    return {"id": uid, "name": name, "path": name, "type": typ, "category": "Joint",
            "color": "#2f6f5f", "mode": "connected", "filterOpen": False, "filterText": "",
            "dead": False, "conv": False, "hasIn": True, "hasOut": True, "rows": rows,
            "foot": "", "height": h, "anchors": anchors, "parents": parents, "width": 220,
            "search": name.lower() + " " + typ.lower(), "x": x, "y": y}


def _wire(src, sk, dst, dk, color="#8fbf6f"):
    return {"id": "%s|attr%d>%s|attr%d" % (src, sk, dst, dk), "src": src, "srcPlug": "attr%d" % sk,
            "dst": dst, "dstPlug": "attr%d" % dk, "uc": False, "conv": "", "cls": "Numeric",
            "compound": False, "color": color, "srcY": 42 + sk * 20, "dstY": 42 + dk * 20}


def synthetic(pairs):
    """Joint -> parentConstraint pairs side by side: short wires only (the run 3 probe)."""
    nodes, wires = [], []
    for i in range(pairs):
        j, c = "j%d" % i, "c%d" % i
        nodes.append(node(j, "joint_%03d" % i, "joint", 60, 60 + i * 480, 16, 3, 10))
        nodes.append(node(c, "joint_%03d_parentConstraint1" % i, "parentConstraint", 420, 60 + i * 480, 26, 20, 3))
    for i in range(pairs):
        j, c, nxt = "j%d" % i, "c%d" % i, "j%d" % ((i + 1) % pairs)
        for k in range(10):
            wires.append(_wire(j, k, c, k, "#8fbf6f" if k % 3 else "#e0a45c"))
        for k in range(3):
            wires.append(_wire(c, k, nxt, k))
    return {"nodes": nodes, "wires": wires, "sel": [], "lead": ""}


def column(n):
    """A real rig as Graph lays it out: one tall column (n nodes, ~330 px apart) with 8 short
    wires to the next node and 4 long cross links each (~12 n wires), so most wires that touch
    the view run thousands of px beyond it -- the shape that made a live 59-node board paint
    at 2 fps."""
    nodes, wires = [], []
    for i in range(n):
        nodes.append(node("n%d" % i, "node_%03d" % i, "joint", 60 + (i % 2) * 420, 60 + i * 330, 12, 8, 8))
    for i in range(n):
        for k in range(8):
            wires.append(_wire("n%d" % i, k, "n%d" % ((i + 1) % n), k, "#8fbf6f" if k % 3 else "#e0a45c"))
        for k in range(4):
            far = (i + 20 + (i * 13 + k * 37) % 160) % n
            wires.append(_wire("n%d" % i, 8 + k, "n%d" % far, 8 + k, "#6fa8dc"))
    return {"nodes": nodes, "wires": wires, "sel": [], "lead": ""}


def fan(n):
    """The live zoom-2.5 lag (run 6): one source node at the middle wired to n targets spread
    10-40k px away at zoom 2.5. Hover it (NODEX_PROBE_JS="hoverNode = 's'") and its wires go
    wide, the case that rasterized 280 ms a repaint on the user's board."""
    nodes, wires = [], []
    rows = n // 5 + 1
    for i in range(n):
        nodes.append(node("t%d" % i, "target_%03d" % i, "joint", 2600 + (i % 5) * 2000, (i // 5) * 1200, 12, 8, 0))
    nodes.append(node("s", "source", "joint", 60, (rows // 2) * 1200, 12, 0, 6))
    for i in range(n):
        for k in range(6):
            wires.append(_wire("s", k, "t%d" % i, k, "#8fbf6f" if k % 3 else "#e0a45c"))
    return {"nodes": nodes, "wires": wires, "sel": [], "lead": ""}


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "295"
    if arg.startswith("column:"):
        snap = column(int(arg.split(":")[1]))
    elif arg.startswith("fan:"):
        snap = fan(int(arg.split(":")[1]))
    else:
        snap = synthetic(int(arg))
    ys = sorted(n["y"] for n in snap["nodes"])
    mid_y = ys[len(ys) // 2]
    b = _probe.make_bridge(snap)
    q = QtQuickWidgets.QQuickWidget()
    q.setResizeMode(QtQuickWidgets.QQuickWidget.SizeRootObjectToView)
    panel.add_maya_qml_dir(q.engine())
    warnings = []
    q.engine().warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    q.rootContext().setContextProperty("bridge", b)
    q.resize(1280, 811)
    t = time.perf_counter()
    q.setSource(QtCore.QUrl.fromLocalFile(os.path.join(panel.QML_DIR, "Board.qml")))
    r = q.rootObject()
    for kv in filter(None, os.environ.get("NODEX_PROBE_SET", "").split(",")):
        k_, v_ = kv.split("=")
        r.setProperty(k_, {"true": True, "false": False}.get(v_, int(v_) if v_.isdigit() else v_))
    q.show()
    _probe.pump(200)
    res = {"nodes": len(snap["nodes"]), "wires": len(snap["wires"]),
           "load_ms": round((time.perf_counter() - t) * 1000), "errors": [e.toString() for e in q.errors()]}
    from PySide6 import QtQml
    for label, expr in (("snapshot_ms", "bridge.snapshot().nodes.length"), ("reset_ms", "reset()")):
        e = QtQml.QQmlExpression(q.rootContext(), r, expr)
        t = time.perf_counter()
        e.evaluate()
        res[label] = round((time.perf_counter() - t) * 1000)
    # env NODEX_PROBE_JS: a board expression run after reset() (which clears hover / isolation),
    # e.g. "hoverNode = 'n30'" -- the focus node's wires go hot (wide), the live slow case
    if os.environ.get("NODEX_PROBE_JS"):
        QtQml.QQmlExpression(q.rootContext(), r, os.environ["NODEX_PROBE_JS"]).evaluate()
    _probe.pump(100)
    canvas = [k for k in r.childItems() if k.metaObject().className().startswith("QQuickCanvasItem")][0]

    def frame_ms(fn, n=6):
        t0 = time.perf_counter()
        for _ in range(n):
            fn()
            q.grabFramebuffer()
        return round((time.perf_counter() - t0) * 1000 / n, 1)

    k = [0]

    def measure(label, zoom, links):
        b.setLinks("on" if links else "off")
        r.setProperty("zoom", zoom)
        r.setProperty("panX", 40.0)
        r.setProperty("panY", 400.0 - mid_y * zoom)
        _probe.pump(250)
        px = r.property("panX")

        def pan():
            k[0] += 1
            r.setProperty("panX", px + (k[0] % 2) * 3)
        pan_ms = frame_ms(pan)
        _probe.pump(150)
        t0 = time.perf_counter()
        QtCore.QMetaObject.invokeMethod(canvas, "requestPaint")
        q.grabFramebuffer()
        rep_ms = round((time.perf_counter() - t0) * 1000, 1)
        ps = r.property("paintStats")
        ps = ps.toVariant() if hasattr(ps, "toVariant") else ps
        res[label] = {"pan": pan_ms, "repaint": rep_ms, "js": ps.get("ms"), "curves": ps.get("curves"),
                      "groups": ps.get("groups"), "far": r.property("far")}

    measure("close_detail", 2.5, False)
    measure("live_detail", 0.84, False)
    if os.environ.get("NODEX_PROBE_QUICK"):
        sys.stdout.write("NODEX_PERF " + json.dumps(res) + "\n")
        return
    measure("far_links", 0.3, True)
    measure("near_links", 0.9, True)
    measure("far_detail", 0.3, False)
    measure("near_detail", 0.9, False)
    measure("tiny_links", 0.07, True)
    measure("tiny_detail", 0.07, False)
    if len(sys.argv) > 2:
        b.setLinks("on")
        r.setProperty("zoom", 0.9)
        _probe.pump(300)
        q.grabFramebuffer().save(sys.argv[2])
    res["warnings"] = warnings[:10]
    sys.stdout.write("NODEX_PERF " + json.dumps(res) + "\n")
    sys.stdout.flush()


main()
