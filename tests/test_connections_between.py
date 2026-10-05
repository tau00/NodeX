"""Find all directed chains between a selected pair without adding unrelated branches."""
import unittest
import _maya
_maya.start()
import maya.cmds as cmds
from nodex import model
from nodex.bridge import Bridge


class ConnectionsBetweenTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()
        self.names = {key: cmds.createNode('multiplyDivide', name=key)
                      for key in ('a', 'b', 'first', 'second', 'alternative', 'offshoot', 'tail')}
        self.ids = {k: model.uuids_of([n])[0] for k, n in self.names.items()}
        for a, b, attr in (('a', 'first', 'input1'), ('first', 'second', 'input1'),
                           ('second', 'b', 'input1'), ('a', 'alternative', 'input1'),
                           ('alternative', 'b', 'input2'), ('first', 'offshoot', 'input1'),
                           ('b', 'tail', 'input1')):
            cmds.connectAttr(self.names[a] + '.output', self.names[b] + '.' + attr)
        cmds.flushUndo()

    def test_all_routes_both_selection_orders_exclude_unrelated_branches(self):
        expected = {self.ids[k] for k in ('a', 'b', 'first', 'second', 'alternative')}
        before = set(model.uuids_of(cmds.ls(long=True)))
        for a, b in (('a', 'b'), ('b', 'a')):
            self.assertEqual(set(model.connections_between(self.ids[a], self.ids[b])), expected)
        self.assertEqual(set(model.uuids_of(cmds.ls(long=True))), before)
        self.assertTrue(cmds.undoInfo(q=True, undoQueueEmpty=True))

    def test_direct_reverse_disconnected_and_message_connections(self):
        meta = cmds.createNode('network')
        cmds.addAttr(meta, longName='first', attributeType='message')
        cmds.addAttr(meta, longName='second', attributeType='message')
        cmds.connectAttr(self.names['offshoot'] + '.message', meta + '.first')
        cmds.connectAttr(self.names['tail'] + '.message', meta + '.second')
        self.assertEqual(model.connections_between(self.ids['offshoot'], self.ids['tail']), [])
        self.assertEqual(set(model.connections_between(self.ids['alternative'], self.ids['b'])),
                         {self.ids['alternative'], self.ids['b']})
        self.assertEqual(model.connections_between(self.ids['a'], self.ids['a']), [])

    def test_hidden_conversion_included_in_path_not_graphed(self):
        angle = cmds.createNode('transform')
        cmds.connectAttr(angle + '.rotateX', self.names['a'] + '.input1X')
        uid = model.uuids_of([angle])[0]
        found = model.connections_between(uid, self.ids['b'])
        self.assertTrue(any(cmds.nodeType(model.path_of(u)) == 'unitConversion' for u in found))
        bridge = Bridge()
        bridge.add_nodes([uid, self.ids['b']], arrange_new=False)
        bridge.sel = [uid, self.ids['b']]
        bridge.findConnectionsBetween()
        self.assertFalse(any(info['type'] == 'unitConversion' for info in bridge.infos.values()))
        bridge._flush_timer.stop()

    def test_bridge_adds_paths_and_emits_focus_after_wire_update(self):
        bridge = Bridge()
        bridge.store.set_pos(self.ids['a'], 40, 70)
        bridge.store.set_pos(self.ids['b'], 900, 120)
        endpoints = [self.ids['a'], self.ids['b']]
        bridge.add_nodes(endpoints, arrange_new=False)
        bridge.sel = endpoints
        results = []
        bridge.connectionsFound.connect(lambda nodes, wires: results.append((nodes, wires)))
        bridge.findConnectionsBetween()
        self.assertFalse(results)
        bridge._flush_ui()
        found = {self.ids[k] for k in ('a', 'b', 'first', 'second', 'alternative')}
        self.assertEqual(set(bridge.infos), found)
        self.assertEqual(bridge.sel, endpoints)
        self.assertEqual(bridge.store.pos(endpoints[0]), (40, 70))
        self.assertEqual(bridge.store.pos(endpoints[1]), (900, 120))
        self.assertEqual(set(results[0][0]), found)
        self.assertEqual(set(results[0][1]), {w['id'] for w in bridge.wires})
        bridge._flush_timer.stop()

    def test_locked_limit_and_search_cap_leave_no_partial_graph(self):
        with self.assertRaises(ValueError):
            model.connections_between(self.ids['a'], self.ids['b'], limit=2)
        bridge = Bridge()
        endpoints = [self.ids['a'], self.ids['b']]
        bridge.add_nodes(endpoints, arrange_new=False)
        bridge.sel = endpoints
        bridge.locked = True
        bridge.findConnectionsBetween()
        self.assertEqual(set(bridge.infos), set(endpoints))
        bridge.locked = False
        bridge.max_nodes = 3
        bridge.findConnectionsBetween()
        self.assertEqual(set(bridge.infos), set(endpoints))
        bridge._flush_timer.stop()
