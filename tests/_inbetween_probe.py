"""Exercise the real context menu, attribute chooser, acceptance and cancellation without a host."""
import json
import sys
from _qml_probe import app, make_bridge
from PySide6 import QtCore, QtWidgets
from nodex import model, ops
from nodex.inbetween import SocketDialog

wire = {'id': 'wire', 'src': 'a', 'dst': 'b', 'srcPlug': 'outputX', 'dstPlug': 'input1X'}
b = make_bridge({'nodes': [{'id': 'a'}, {'id': 'b'}], 'wires': [wire], 'sel': [], 'lead': ''})
b.locked = False
b.max_nodes = 500
b._plug = lambda uid, path: uid + '.' + path
contexts, inserts = [], []
options = [('input1.input1X', 'Numeric'), ('input2.input2X', 'Numeric')]
outputs = [('output.outputX', 'Numeric'), ('output.outputY', 'Numeric')]
from nodex import catalog as catalog_mod
class FakeCatalog:
    def inbetween(self, sc, dc, query='', src_hint='', dst_hint='', limit=120):
        contexts.append(['a.' + src_hint, 'b.' + dst_hint])
        return [('multiplyDivide', options[0][0], outputs[0][0], options, outputs)]
catalog_mod.get = lambda: FakeCatalog()
catalog_mod.Catalog.record = staticmethod(lambda t: None)
ops.type_socket_options = lambda name, output: outputs if output else options
class Plug:
    def attribute(self):
        return None
ops._mplug = lambda path: Plug()
model.attr_class = lambda attr: 'Numeric'
b._popup = lambda menu: setattr(b, '_menu', menu)
b._insert_inbetween = lambda w, name, inp, out: inserts.append([w['id'], name, inp, out])
b.wireMenu('wire')
actions = b._menu.actions()
between_action = next(a for a in actions if a.text() == 'Inbetween')
between = between_action.menu()
between_actions = between.actions()
utility_actions = [a for a in between_actions if not a.isSeparator() and a.text() != 'Search...']
labels = [a.text().split()[0] for a in utility_actions]
searches = [a.text() for a in between_actions if a.text() == 'Search...']

def answer(accept):
    dialog = next(w for w in app.topLevelWidgets() if isinstance(w, SocketDialog) and w.isVisible())
    if accept:
        dialog.input.setCurrentIndex(1)
        dialog.output.setCurrentIndex(1)
        if len(sys.argv) > 1:
            dialog.grab().save(sys.argv[1])
        dialog.accept()
    else:
        dialog.reject()

utility_actions[0].trigger()                 # plain click: the shown sockets, no dialog
direct = list(inserts)
del inserts[:]
QtCore.QTimer.singleShot(25, lambda: answer(True))
b._inbetween_pick('wire', ('multiplyDivide', 'input1.input1X', 'output.outputX'), True)
accepted = list(inserts)
QtCore.QTimer.singleShot(25, lambda: answer(False))
b._inbetween_pick('wire', ('multiplyDivide', 'input1.input1X', 'output.outputX'), True)
initial_contexts = list(contexts)
b.wires.append(dict(wire, id='wire2', srcPlug='outputY', dstPlug='input1Y'))
b.bundleMenu(['wire', 'wire2'])
group_actions = b._menu.actions()
group_action = next(a for a in group_actions if a.text() == 'Inbetween')
group = group_action.menu()
connections = group.actions()
group_first = connections[0].menu().actions()[0].text()
print('NODEX_INBETWEEN ' + json.dumps({'labels': labels, 'contexts': contexts,
    'initialContexts': initial_contexts, 'groupedConnections': [a.text() for a in connections],
    'accepted': accepted, 'afterCancel': inserts, 'direct': direct, 'searches': searches,
    'groupFirst': group_first}))

# Node context menu exposes bypass for arbitrary eligible nodes and explains refusals.
b.sel = ['a']
b.dead = set()
b.views = {}
b._view_for = lambda uid: model.NodeView()
model.path_of = lambda uid: uid
ops.delete_inbetween_plan = lambda node: {'pairs': 2}
deleted = []
b.deleteInbetween = lambda uid: deleted.append(uid)
b.nodeMenu('a')
node_actions = b._menu.actions()
bypass = next(a for a in node_actions if a.text() == 'Delete inbetween')
enabled = bypass.isEnabled()
if len(sys.argv) > 2:
    from _qml_probe import pump
    b._menu.popup(QtCore.QPoint(100, 100))
    b._menu.setActiveAction(bypass)
    pump(30)
    b._menu.grab().save(sys.argv[2])
    b._menu.hide()
bypass.trigger()
def reject(node):
    raise ValueError('Active input/output pairing is ambiguous')
ops.delete_inbetween_plan = reject
b.nodeMenu('a')
disabled_actions = b._menu.actions()
disabled = next(a for a in disabled_actions if a.text() == 'Delete inbetween')
print('NODEX_BYPASS_MENU ' + json.dumps({'enabled': enabled, 'deleted': deleted,
    'disabled': not disabled.isEnabled(), 'reason': disabled.toolTip()}))
