"""The header fold button: a node showing rows folds to its header, a node showing none
unfolds -- an unconnected node too, which "connected" mode leaves without rows."""
import unittest
import _maya
_maya.start()
import maya.cmds as cmds
from nodex import model
from nodex.bridge import Bridge


class FoldTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()
        self.names = {k: cmds.createNode('multiplyDivide', name=k) for k in ('src', 'dst')}
        # A DAG node: "connected" shows no rows at all for it (a DG node keeps its enum fields).
        self.names['lone'] = cmds.createNode('joint', name='lone')
        self.ids = {k: model.uuids_of([n])[0] for k, n in self.names.items()}
        cmds.connectAttr(self.names['src'] + '.outputX', self.names['dst'] + '.input1X')
        cmds.flushUndo()
        self.bridge = Bridge()
        self.bridge.add_nodes(list(self.ids.values()), arrange_new=False)

    def tearDown(self):
        self.bridge._flush_timer.stop()

    def rows(self, k):
        u = self.ids[k]
        return model.describe(u, self.bridge._view_for(u), self.bridge.tab.get('mode', 'connected'),
                              self.bridge.query)['rows']

    def test_unconnected_node_unfolds(self):
        self.assertEqual(self.rows('lone'), [])
        self.bridge.toggleFold(self.ids['lone'])
        self.assertTrue(self.rows('lone'))
        self.bridge.toggleFold(self.ids['lone'])
        self.assertEqual(self.rows('lone'), [])
        self.bridge.toggleFold(self.ids['lone'])
        self.assertTrue(self.rows('lone'))

    def test_connected_node_folds_and_unfolds_to_connected(self):
        self.assertTrue(self.rows('dst'))
        self.bridge.toggleFold(self.ids['dst'])
        self.assertEqual(self.rows('dst'), [])
        self.bridge.toggleFold(self.ids['dst'])
        self.assertEqual(self.bridge._view_for(self.ids['dst']).mode, 'connected')
        self.assertTrue(self.rows('dst'))


if __name__ == '__main__':
    unittest.main()
