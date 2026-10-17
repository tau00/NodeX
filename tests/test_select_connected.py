"""Select connected nodes: the nodes wired to one attribute replace the selection, off-board
ones are added first, and a locked or full board refuses as a whole."""
import unittest
import _maya
_maya.start()
import maya.cmds as cmds
from nodex import model
from nodex.bridge import Bridge


class SelectConnectedTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()
        self.names = {k: cmds.createNode('multiplyDivide', name=k) for k in ('src', 'a', 'b', 'c')}
        self.ids = {k: model.uuids_of([n])[0] for k, n in self.names.items()}
        cmds.connectAttr(self.names['src'] + '.outputX', self.names['a'] + '.input1X')
        cmds.connectAttr(self.names['src'] + '.output', self.names['b'] + '.input1')
        cmds.connectAttr(self.names['src'] + '.outputY', self.names['c'] + '.input2Y')
        cmds.flushUndo()
        self.bridge = Bridge()
        self.bridge.shapes = 'all'
        self.messages = []
        self.bridge.statusChanged.connect(self.messages.append)

    def tearDown(self):
        self.bridge._flush_timer.stop()

    def nodes(self, keys):
        return [self.ids[k] for k in keys]

    def maya_selection(self):
        return set(model.uuids_of(cmds.ls(selection=True, long=True)))

    def test_on_board_destinations_replace_selection(self):
        self.bridge.add_nodes(self.nodes(['src', 'a', 'b', 'c']), arrange_new=False)
        self.bridge.sel = [self.ids['src'], self.ids['a']]
        self.bridge.selectConnected(self.ids['src'], 'output', 'out')
        self.assertEqual(set(self.bridge.sel), set(self.nodes(['a', 'b', 'c'])))
        self.assertNotIn(self.ids['src'], self.bridge.sel)
        self.assertEqual(self.maya_selection(), set(self.nodes(['a', 'b', 'c'])))
        self.assertIn('Selected 3 nodes connected to src.output (outputs)', self.messages[-1])

    def test_input_side_and_auto_side(self):
        self.bridge.add_nodes(self.nodes(['src', 'b']), arrange_new=False)
        self.bridge.selectConnected(self.ids['b'], 'input1', 'in')
        self.assertEqual(self.bridge.sel, [self.ids['src']])
        self.bridge.sel = []
        self.bridge.selectConnected(self.ids['b'], 'input1', '')
        self.assertEqual(self.bridge.sel, [self.ids['src']])
        self.assertIn('(inputs)', self.messages[-1])

    def test_off_board_source_added_and_selected(self):
        self.bridge.store.set_pos(self.ids['a'], 400, 120)
        self.bridge.add_nodes([self.ids['a']], arrange_new=False)
        self.bridge.selectConnected(self.ids['a'], 'input1X', 'in')
        self.assertIn(self.ids['src'], self.bridge.infos)
        self.assertEqual(self.bridge.sel, [self.ids['src']])
        self.assertEqual(self.bridge.store.pos(self.ids['a']), (400, 120))
        self.assertEqual(self.maya_selection(), {self.ids['src']})

    def test_locked_and_over_limit_leave_board_and_selection(self):
        self.bridge.add_nodes([self.ids['src']], arrange_new=False)
        self.bridge.sel = [self.ids['src']]
        self.bridge.locked = True
        self.bridge.selectConnected(self.ids['src'], 'output', 'out')
        self.assertEqual(set(self.bridge.infos), {self.ids['src']})
        self.assertEqual(self.bridge.sel, [self.ids['src']])
        self.assertIn('Unlock the graph', self.messages[-1])
        self.bridge.locked = False
        self.bridge.max_nodes = 3
        self.bridge.selectConnected(self.ids['src'], 'output', 'out')
        self.assertEqual(set(self.bridge.infos), {self.ids['src']})
        self.assertEqual(self.bridge.sel, [self.ids['src']])
        self.assertIn('need 3 free slots', self.messages[-1])

    def test_locked_with_everything_on_board_still_selects(self):
        self.bridge.add_nodes(self.nodes(['src', 'a']), arrange_new=False)
        self.bridge.locked = True
        self.bridge.selectConnected(self.ids['a'], 'input1X', 'in')
        self.assertEqual(self.bridge.sel, [self.ids['src']])

    def test_default_node_skipped_and_reported(self):
        cmds.connectAttr('time1.outTime', self.names['c'] + '.input1Z')
        self.bridge.add_nodes([self.ids['c']], arrange_new=False)
        self.bridge.sel = [self.ids['c']]
        self.bridge.selectConnected(self.ids['c'], 'input1Z', 'in')
        self.assertEqual(self.bridge.sel, [self.ids['c']])
        self.assertNotIn(model.uuids_of(['time1'])[0], self.bridge.infos)
        self.assertIn('1 default node skipped', self.messages[-1])
        _, shown, skipped = self.bridge._connected(self.ids['c'], 'input1Z', 'in')
        self.assertEqual((shown, skipped), ([], 1))

    def test_expanded_conversion_selected_instead_of_source(self):
        xf = cmds.createNode('transform', name='spin')
        cmds.connectAttr(xf + '.rotateX', self.names['a'] + '.input2X')
        conv = cmds.listConnections(self.names['a'] + '.input2X', source=True, destination=False,
                                    skipConversionNodes=False)[0]
        self.assertEqual(cmds.nodeType(conv), 'unitConversion')
        xf_id, conv_id = model.uuids_of([xf, conv])
        self.bridge.add_nodes([self.ids['a']], arrange_new=False)
        self.bridge.selectConnected(self.ids['a'], 'input2X', 'in')
        self.assertEqual(self.bridge.sel, [xf_id])
        self.bridge.add_nodes([conv_id], arrange_new=False, force=True)
        self.bridge.selectConnected(self.ids['a'], 'input2X', 'in')
        self.assertEqual(self.bridge.sel, [conv_id])

    def test_no_shapes_mode_selects_transform(self):
        xf, maker = cmds.polyCube(name='box')
        xf_id, maker_id = model.uuids_of([xf, maker])
        self.bridge.shapes = 'none'
        self.bridge.add_nodes([maker_id], arrange_new=False)
        self.bridge.selectConnected(maker_id, 'output', 'out')
        self.assertEqual(self.bridge.sel, [xf_id])
        self.assertTrue(all(cmds.nodeType(model.path_of(u)) != 'mesh' for u in self.bridge.infos))

    def test_unconnected_attribute_finds_nothing(self):
        self.bridge.add_nodes([self.ids['a']], arrange_new=False)
        self.assertEqual(self.bridge._connected(self.ids['a'], 'input2Z', '')[1], [])
        self.bridge.sel = [self.ids['a']]
        self.bridge.selectConnected(self.ids['a'], 'input2Z', '')
        self.assertEqual(self.bridge.sel, [self.ids['a']])
        self.assertIn('No nodes to select', self.messages[-1])


if __name__ == '__main__':
    unittest.main()
