"""Drive real QML keyboard/mouse events without a Maya scene."""
import json
import os
import sys

from _qml_probe import app, capture_messages, make_bridge, pump
from PySide6 import QtCore, QtGui, QtQml, QtQuickWidgets, QtWidgets
from nodex import panel

with open(sys.argv[1]) as stream:
    snap = json.load(stream)
messages = capture_messages()
b = make_bridge(snap)
calls = []
b.copyFragment = lambda: calls.append(['copy'])
b.pasteFragment = lambda x, y: calls.append(['paste', round(x, 1), round(y, 1)])
b.duplicateFragment = lambda: calls.append(['duplicate'])
b.linkByName = lambda replace: calls.append(['link', replace])
b.lazyConnect = lambda source, target, choose: calls.append(['lazy', source, target, choose])
b.distributeWire = lambda source, plug, targets: calls.append(['fanout', source, plug,
    targets.toVariant() if hasattr(targets, 'toVariant') else targets])
b.dead = set()
b.views = {}
b._typing = False
owner = panel.NodeXPanel.__new__(panel.NodeXPanel)
QtWidgets.QWidget.__init__(owner)
q = QtQuickWidgets.QQuickWidget(owner)
owner.quick = q
owner.bridge = b
q.installEventFilter(owner)
q.quickWindow().installEventFilter(owner)
q.setResizeMode(QtQuickWidgets.QQuickWidget.SizeRootObjectToView)
panel.add_maya_qml_dir(q.engine())
warnings = []
q.engine().warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
q.rootContext().setContextProperty('bridge', b)
q.resize(1400, 1000)
q.setSource(QtCore.QUrl.fromLocalFile(os.path.join(panel.QML_DIR, 'Board.qml')))
owner.resize(1400, 1000)
owner.show()
q.setFocus()
pump(150)
root = q.rootObject()

def js(source):
    expr = QtQml.QQmlExpression(q.rootContext(), root, source)
    result = expr.evaluate()
    if expr.hasError():
        raise RuntimeError(expr.error().toString())
    return result[0] if isinstance(result, tuple) else result

js('forceActiveFocus(); panX = 0; panY = 0; zoom = 1; mouseWorld = Qt.point(700, 450)')
host_calls = []
shortcut = QtGui.QShortcut(QtGui.QKeySequence('Ctrl+C'), owner)
shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
shortcut.activated.connect(lambda: host_calls.append('copy'))

def key(k, modifiers=QtCore.Qt.NoModifier):
    for kind in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
        QtWidgets.QApplication.sendEvent(q, QtGui.QKeyEvent(kind, k, modifiers))
    pump(5)

ctrl, shift, alt = QtCore.Qt.ControlModifier, QtCore.Qt.ShiftModifier, QtCore.Qt.AltModifier
key(QtCore.Qt.Key_C, ctrl)
key(QtCore.Qt.Key_V, ctrl)
key(QtCore.Qt.Key_D, shift)
key(QtCore.Qt.Key_K)
key(QtCore.Qt.Key_K, shift)
key(QtCore.Qt.Key_K, ctrl)  # unsupported modifier must not invoke link
keyboard = list(calls)
calls.clear()

def mouse(kind, x, y, button, buttons, modifiers):
    p = QtCore.QPointF(x, y)
    QtWidgets.QApplication.sendEvent(q, QtGui.QMouseEvent(
        kind, p, QtCore.QPointF(q.mapToGlobal(p.toPoint())), button, buttons, modifiers))

a, z = snap['nodes'][:2]
start, end = (a['x'] + 12, a['y'] + 12), (z['x'] + 12, z['y'] + 12)
right = QtCore.Qt.RightButton
for modifiers in (alt, alt | shift):
    mouse(QtCore.QEvent.MouseButtonPress, *start, right, right, modifiers)
    mouse(QtCore.QEvent.MouseMove, *end, QtCore.Qt.NoButton, right, modifiers)
    if modifiers == alt and len(sys.argv) > 2:
        pump(30)
        q.grabFramebuffer().save(sys.argv[2])
    mouse(QtCore.QEvent.MouseButtonRelease, *end, right, QtCore.Qt.NoButton, modifiers)
    pump(5)
gestures = list(calls)
calls.clear()
mouse(QtCore.QEvent.MouseButtonPress, *start, right, right, alt)
key(QtCore.Qt.Key_Escape)
mouse(QtCore.QEvent.MouseButtonRelease, *end, right, QtCore.Qt.NoButton, alt)
cancelled = list(calls)
calls.clear()

# Sweep three real socket centers, cross a socket in one fast move, revisit it, then
# release over empty canvas. Capture targets from the actual rendered delegates.
ports = json.loads(js('JSON.stringify((function() { var result = []; '
    'for (var id in nodeItems) { var it = nodeItems[id]; '
    'for (var i = 0; i < it.info.rows.length; ++i) { var r = it.info.rows[i]; '
    'if (!r.compound && r.cls === "Numeric") { '
    'var p = portPt(id, anchorOf(id, r.key), r.outPort && !r.inPort); '
    'result.push({nid:id, key:r.key, x:p.x, y:p.y, input:r.inPort, output:r.outPort}); } } } '
    'return result; })())'))
source = next(p for p in ports if p['output'] and not p['input'])
targets = [p for p in ports if p['input'] and p['nid'] != source['nid']][:3]
left = QtCore.Qt.LeftButton
mouse(QtCore.QEvent.MouseButtonPress, source['x'], source['y'], left, left, alt)
fanout_started = bool(js('drag !== null && drag.fanout'))
for p in targets:
    mouse(QtCore.QEvent.MouseMove, p['x'], p['y'] - 16, QtCore.Qt.NoButton, left, alt)
    mouse(QtCore.QEvent.MouseMove, p['x'], p['y'] + 16, QtCore.Qt.NoButton, left, alt)
mouse(QtCore.QEvent.MouseMove, targets[0]['x'], targets[0]['y'], QtCore.Qt.NoButton, left, alt)
preview = json.loads(js('JSON.stringify(drag ? drag.targets : [])'))
pump(10)
if len(sys.argv) > 3:
    q.grabFramebuffer().save(sys.argv[3])
mouse(QtCore.QEvent.MouseButtonRelease, targets[0]['x'] - 30, targets[0]['y'], left, QtCore.Qt.NoButton, alt)
fanout_calls = list(calls)
calls.clear()
mouse(QtCore.QEvent.MouseButtonPress, source['x'], source['y'], left, left, alt)
mouse(QtCore.QEvent.MouseMove, targets[0]['x'], targets[0]['y'], QtCore.Qt.NoButton, left, alt)
key(QtCore.Qt.Key_Escape, alt)
mouse(QtCore.QEvent.MouseButtonRelease, targets[0]['x'], targets[0]['y'], left, QtCore.Qt.NoButton, alt)
fanout_cancelled = list(calls)
calls.clear()

# TextInput keeps normal editing shortcuts; NodeX must not copy/delete the graph here.
js('startRename("%s")' % a['id'])
pump(10)
typing = owner._typing()
key(QtCore.Qt.Key_C, ctrl)
key(QtCore.Qt.Key_V, ctrl)
key(QtCore.Qt.Key_D, shift)
typing_calls = list(calls)
sys.stdout.write('NODEX_KEYS ' + json.dumps({
    'keyboard': keyboard, 'host': host_calls, 'gestures': gestures,
    'cancelled': cancelled, 'typing': typing, 'typingCalls': typing_calls,
    'fanoutStarted': fanout_started, 'fanout': fanout_calls, 'fanoutCancelled': fanout_cancelled,
    'fanoutPreview': preview, 'fanoutExpected': targets, 'fanoutSource': source,
    'warnings': [w for w in warnings if 'Cannot open: qrc:/' not in w],
    'qtMessages': messages,
}) + '\n')
sys.stdout.flush()
