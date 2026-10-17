"""A traversal depth change re-runs the tab's last Graph command from the nodes it started at."""
import unittest
import _maya
_maya.start()
import maya.cmds as cmds
from nodex import model, store
from nodex.bridge import Bridge, DEPTH_VAR


class TraversalDepthTest(unittest.TestCase):
    def setUp(self):
        # The bridge reads the depth preference: start from the default, never the developer's.
        cmds.optionVar(remove=DEPTH_VAR)
        _maya.fresh_scene()
        self.names = {k: cmds.createNode('multiplyDivide', name=k) for k in 'abcd'}
        self.ids = {k: model.uuids_of([n])[0] for k, n in self.names.items()}
        for a, b in (('a', 'b'), ('b', 'c'), ('c', 'd')):
            cmds.connectAttr(self.names[a] + '.output', self.names[b] + '.input1')
        cmds.flushUndo()
        self.bridge = Bridge()
        self.messages = []
        self.bridge.statusChanged.connect(self.messages.append)

    def tearDown(self):
        self.bridge._flush_timer.stop()
        cmds.optionVar(remove=DEPTH_VAR)

    def board(self):
        return set(self.bridge.infos)

    def nodes(self, keys):
        return {self.ids[k] for k in keys}

    def graph_up_from_d(self):
        cmds.select(self.names['d'])
        self.bridge.graphConnections('up')
        self.assertEqual(self.board(), self.nodes('cd'))

    def test_depth_regraphs_from_remembered_seeds(self):
        self.assertEqual(self.bridge.depth, 1)
        self.graph_up_from_d()
        cmds.select(self.names['c'])            # clicking a board node moves Maya's selection
        self.bridge.set_depth(2)
        self.assertEqual(self.board(), self.nodes('bcd'))
        self.bridge.set_depth(None)
        self.assertEqual(self.board(), self.nodes('abcd'))
        self.bridge.set_depth(0)
        self.assertEqual(self.board(), self.nodes('d'))

    def test_same_depth_does_not_regraph(self):
        self.graph_up_from_d()
        self.bridge.remove_nodes([self.ids['c']], remember=False)
        self.bridge.set_depth(1)
        self.assertEqual(self.board(), self.nodes('d'))

    def test_locked_changes_depth_not_board(self):
        self.graph_up_from_d()
        self.bridge.locked = True
        self.bridge.set_depth(3)
        self.assertEqual(self.bridge.depth, 3)
        self.assertEqual(self.board(), self.nodes('cd'))

    def test_clear_graph_forgets_it(self):
        self.graph_up_from_d()
        self.bridge.clearGraph()
        self.assertIsNone(self.bridge.tab['graph'])
        self.bridge.set_depth(2)
        self.assertEqual(self.board(), set())

    def test_deleted_seeds_report_and_leave_board(self):
        self.graph_up_from_d()
        cmds.delete(self.names['d'])
        before = self.board()
        del self.messages[:]
        self.bridge.set_depth(2)
        self.assertEqual(self.board(), before)
        self.assertEqual(self.messages, ["The graphed nodes are gone; graph again"])

    def test_graph_saved_with_scene_and_depth_preference_written(self):
        self.graph_up_from_d()
        self.bridge.store.save()
        loaded = store.Store().load()
        graph = loaded['tabs'][0]['graph']
        self.assertEqual((graph['direction'], graph['seeds']), ('up', [self.ids['d']]))
        self.assertEqual(set(graph['nodes']), self.nodes('cd'))
        self.bridge.set_depth(None)
        self.assertEqual(cmds.optionVar(q=DEPTH_VAR), -1)
        self.bridge.set_depth(4)
        self.assertEqual(cmds.optionVar(q=DEPTH_VAR), 4)
        b = Bridge()
        self.assertEqual(b.depth, 4)
        b._flush_timer.stop()

    def test_board_edited_after_graph_is_not_replaced(self):
        self.graph_up_from_d()
        self.bridge.add_nodes([self.ids['a']], arrange_new=False)     # added by hand
        del self.messages[:]
        self.bridge.set_depth(2)
        self.assertEqual(self.board(), self.nodes('acd'))
        self.assertIsNone(self.bridge.tab['graph'])
        self.assertIn('graph again', self.messages[-1])
        self.bridge.set_depth(3)                                       # forgotten, not retried
        self.assertEqual(self.board(), self.nodes('acd'))

    def test_board_with_node_removed_after_graph_is_not_replaced(self):
        self.graph_up_from_d()
        self.bridge.remove_nodes([self.ids['c']], remember=False)
        self.bridge.set_depth(2)
        self.assertEqual(self.board(), self.nodes('d'))

    def test_display_mode_change_keeps_depth_working(self):
        self.graph_up_from_d()
        self.bridge.set_shapes('none')
        self.bridge.set_depth(2)
        self.assertEqual(self.board(), self.nodes('bcd'))

    def test_malformed_saved_values_fall_back(self):
        cmds.optionVar(stringValue=(DEPTH_VAR, 'deep'))
        b = Bridge()
        self.assertEqual(b.depth, 1)
        b._flush_timer.stop()
        for bad in ({'direction': 'up'}, {'direction': 'sideways', 'seeds': []}, ['up'], 'x'):
            tab = store.new_tab('Odd')
            tab['graph'] = bad
            self.assertIsNone(store._normalise({'tabs': [tab]})['tabs'][0]['graph'])

    def test_old_tab_without_graph_key_normalises_to_none(self):
        tab = store.new_tab('Old')
        del tab['graph']
        out = store._normalise({'tabs': [tab]})
        self.assertIsNone(out['tabs'][0]['graph'])


if __name__ == '__main__':
    unittest.main()
