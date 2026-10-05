"""Bypass arbitrary Maya nodes without guessing ambiguous channels or changing unrelated branches."""
import unittest
from unittest import mock

import _maya
_maya.start()
import maya.cmds as cmds
from nodex import model, ops
from nodex.bridge import Bridge


class DeleteInbetweenTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()
        self.a, self.mid, self.b, self.c = [cmds.createNode('multiplyDivide', name=n)
                                          for n in ('source', 'ordinary_middle', 'target', 'other')]

    def link(self, src, dest):
        cmds.connectAttr(src, dest)

    def test_single_active_pair_fanout_metadata_and_native_undo_redo(self):
        self.link(self.a + '.outputX', self.mid + '.input2Y')
        for node in (self.b, self.c):
            self.link(self.mid + '.outputY', node + '.input1Z')
        meta = cmds.createNode('network')
        cmds.addAttr(meta, longName='owned', attributeType='message')
        self.link(self.mid + '.message', meta + '.owned')
        cmds.flushUndo()
        before = set(model.uuids_of(cmds.ls(long=True)))
        uid = model.uuids_of([self.mid])[0]
        undo = cmds.undoInfo(q=True, undoName=True)
        self.assertEqual(ops.delete_inbetween_plan(self.mid)['pairs'], 1)
        self.assertEqual(cmds.undoInfo(q=True, undoName=True), undo)
        plan = ops.delete_inbetween(self.mid)
        self.assertEqual(len(plan['routes']), 2)
        self.assertFalse(cmds.objExists(self.mid))
        for node in (self.b, self.c):
            self.assertEqual(ops.source_of(node + '.input1Z'), self.a + '.outputX')
        self.assertTrue(cmds.objExists(meta))
        cmds.undo()
        self.assertEqual(set(model.uuids_of(cmds.ls(long=True))), before)
        self.assertEqual(model.path_of(uid), self.mid)
        self.assertEqual(ops.source_of(self.b + '.input1Z'), self.mid + '.outputY')
        self.assertEqual(ops.source_of(meta + '.owned'), self.mid + '.message')
        cmds.redo()
        self.assertFalse(cmds.objExists(self.mid))
        self.assertEqual(ops.source_of(self.c + '.input1Z'), self.a + '.outputX')

    def test_multiple_xyz_pairs_no_channel_crossing(self):
        for axis in 'YXZ':
            self.link(self.a + '.output' + axis, self.mid + '.input1' + axis)
            self.link(self.mid + '.output' + axis, self.b + '.input1' + axis)
        self.link(self.a + '.outputX', self.c + '.input2X')
        plan = ops.delete_inbetween(self.mid)
        self.assertEqual(plan['pairs'], 3)
        for axis in 'XYZ':
            self.assertEqual(ops.source_of(self.b + '.input1' + axis), self.a + '.output' + axis)
        self.assertEqual(ops.source_of(self.c + '.input2X'), self.a + '.outputX')

    def test_compound_input_to_split_outputs(self):
        self.link(self.a + '.output', self.mid + '.input1')
        for axis in 'XY':
            self.link(self.mid + '.output' + axis, self.b + '.input1' + axis)
        # Z has no active output, so deleting would drop an unmatched active input.
        with self.assertRaises(ValueError):
            ops.delete_inbetween_plan(self.mid)
        self.link(self.mid + '.outputZ', self.b + '.input1Z')
        ops.delete_inbetween(self.mid)
        for axis in 'XYZ':
            self.assertEqual(ops.source_of(self.b + '.input1' + axis), self.a + '.output' + axis)

    def test_split_inputs_to_compound_output_and_undo_restores_parent_connection(self):
        for axis in 'XYZ':
            self.link(self.a + '.output' + axis, self.mid + '.input1' + axis)
        self.link(self.mid + '.output', self.b + '.input1')
        cmds.flushUndo()
        ops.delete_inbetween(self.mid)
        for axis in 'XYZ':
            self.assertEqual(ops.source_of(self.b + '.input1' + axis), self.a + '.output' + axis)
        cmds.undo()
        self.assertTrue(cmds.isConnected(self.mid + '.output', self.b + '.input1'))

    def test_single_compound_pair_keeps_parent_connections(self):
        self.link(self.a + '.output', self.mid + '.input1')
        self.link(self.mid + '.output', self.b + '.input1')
        ops.delete_inbetween(self.mid)
        self.assertTrue(cmds.isConnected(self.a + '.output', self.b + '.input1'))

    def test_shape_shading_membership_is_not_an_active_data_output(self):
        source, middle, target = [cmds.createNode('mesh', name=n)
                                  for n in ('shape_source', 'shape_middle', 'shape_target')]
        self.link(source + '.outMesh', middle + '.inMesh')
        self.link(middle + '.worldMesh[0]', target + '.inMesh')
        cmds.sets(middle, edit=True, forceElement='initialShadingGroup')
        group = model.uuids_of(['initialShadingGroup'])
        cmds.flushUndo()
        self.assertEqual(ops.delete_inbetween_plan(middle)['pairs'], 1)
        ops.delete_inbetween(middle)
        self.assertEqual(ops.source_of(target + '.inMesh'), source + '.outMesh')
        self.assertEqual(model.uuids_of(['initialShadingGroup']), group)
        self.assertTrue(cmds.objExists(source))
        cmds.undo()
        self.assertTrue(cmds.objExists(middle))
        self.assertEqual(ops.source_of(target + '.inMesh'), middle + '.worldMesh[0]')

    def test_array_indices_pair_without_declaration_order(self):
        middle = cmds.createNode('network', name='array_middle')
        cmds.addAttr(middle, longName='input', attributeType='double', multi=True)
        cmds.addAttr(middle, longName='output', attributeType='double', multi=True)
        for axis, index in (('X', 7), ('Y', 2)):
            self.link(self.a + '.output' + axis, middle + '.input[%d]' % index)
            self.link(middle + '.output[%d]' % index, self.b + '.input1' + axis)
        ops.delete_inbetween(middle)
        self.assertEqual(ops.source_of(self.b + '.input1X'), self.a + '.outputX')
        self.assertEqual(ops.source_of(self.b + '.input1Y'), self.a + '.outputY')

    def test_array_compound_input_matches_split_output_channels(self):
        middle = cmds.createNode('plusMinusAverage')
        self.link(self.a + '.output', middle + '.input3D[7]')
        for axis in 'XYZ':
            self.link(middle + '.output3D' + axis.lower(), self.b + '.input1' + axis)
        ops.delete_inbetween(middle)
        for axis in 'XYZ':
            self.assertEqual(ops.source_of(self.b + '.input1' + axis), self.a + '.output' + axis)

    def test_reject_ambiguous_mismatched_locked_and_unconnected_without_changes(self):
        middle = cmds.createNode('network', name='ambiguous_middle')
        for attr in ('first', 'second', 'third', 'fourth'):
            cmds.addAttr(middle, longName=attr, attributeType='double')
        for source, dest in ((self.a + '.outputX', middle + '.first'), (self.a + '.outputY', middle + '.second'),
                             (middle + '.third', self.b + '.input1X'), (middle + '.fourth', self.b + '.input1Y')):
            self.link(source, dest)
        before = set(cmds.ls(long=True))
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            ops.delete_inbetween(middle)
        with self.assertRaises(ValueError):
            ops.delete_inbetween(self.c)
        self.link(self.a + '.outputX', self.mid + '.input1X')
        self.link(self.a + '.outputY', self.mid + '.input2X')
        self.link(self.mid + '.outputX', self.c + '.input1X')
        with self.assertRaises(ValueError):
            ops.delete_inbetween(self.mid)
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.disconnectAttr(self.a + '.outputY', self.mid + '.input2X')
        cmds.setAttr(self.c + '.input1X', lock=True)
        with self.assertRaisesRegex(ValueError, 'locked'):
            ops.delete_inbetween(self.mid)
        self.assertEqual(ops.source_of(self.c + '.input1X'), self.mid + '.outputX')

    def test_conversion_helpers_and_factors_survive(self):
        angle = cmds.createNode('transform')
        self.link(angle + '.rotateX', self.mid + '.input1X')
        self.link(self.mid + '.outputX', angle + '.rotateY')
        incoming = ops.source_of(self.mid + '.input1X', skip_conversion=False)
        outgoing = ops.source_of(angle + '.rotateY', skip_conversion=False)
        conv = incoming.split('.')[0]
        cmds.setAttr(conv + '.conversionFactor', 3.25)
        cmds.flushUndo()
        ops.delete_inbetween(self.mid)
        self.assertEqual(ops.source_of(outgoing.split('.')[0] + '.input', skip_conversion=False), incoming)
        self.assertTrue(cmds.objExists(conv))
        self.assertEqual(cmds.getAttr(conv + '.conversionFactor'), 3.25)
        cmds.undo()
        self.assertEqual(ops.source_of(self.mid + '.input1X', skip_conversion=False), incoming)

    def test_failure_on_second_route_restores_entire_original_graph(self):
        for axis in 'XY':
            self.link(self.a + '.output' + axis, self.mid + '.input1' + axis)
            self.link(self.mid + '.output' + axis, self.b + '.input1' + axis)
        before = set(cmds.ls(long=True))
        native = ops.connect
        def fail(a, b):
            return 'simulated failure' if b.endswith('.input1Y') else native(a, b)
        with mock.patch.object(ops, 'connect', side_effect=fail):
            with self.assertRaises(RuntimeError):
                ops.delete_inbetween(self.mid)
        self.assertEqual(set(cmds.ls(long=True)), before)
        for axis in 'XY':
            self.assertEqual(ops.source_of(self.b + '.input1' + axis), self.mid + '.output' + axis)
            self.assertEqual(ops.source_of(self.mid + '.input1' + axis), self.a + '.output' + axis)

    def test_bridge_action_updates_graph_when_sync_is_off(self):
        self.link(self.a + '.outputX', self.mid + '.input1X')
        self.link(self.mid + '.outputX', self.b + '.input1X')
        bridge = Bridge()
        ids = model.uuids_of([self.a, self.mid, self.b])
        bridge.add_nodes(ids, arrange_new=False)
        bridge.sel = [ids[1]]
        bridge.sync_on = False
        bridge.deleteInbetween(ids[1])
        bridge._flush_ui()
        self.assertNotIn(ids[1], bridge.infos)
        self.assertEqual(bridge.sel, [])
        self.assertTrue(any(w['src'] == ids[0] and w['dst'] == ids[2] for w in bridge.wires))
        bridge._flush_timer.stop()

    def test_bridge_rewires_through_hidden_conversion_and_leaves_unrelated_rows_alone(self):
        angle = cmds.createNode('transform')
        self.link(angle + '.rotateX', self.mid + '.input1X')
        self.link(self.mid + '.outputX', self.b + '.input1X')
        bridge = Bridge()
        ids = model.uuids_of([angle, self.mid, self.b, self.c])
        bridge.add_nodes(ids, arrange_new=False)
        bridge._flush_ui()
        bridge.sync_on = False
        bridge.deleteInbetween(ids[1])
        self.assertNotIn(ids[3], bridge._pending['changed'])
        bridge._flush_ui()
        self.assertTrue(any(w['src'] == ids[0] and w['dst'] == ids[2] for w in bridge.wires))
        bridge._flush_timer.stop()

    def test_real_undo_redo_events_restore_visual_node_position_width_and_views(self):
        self.link(self.a + '.outputX', self.mid + '.input1X')
        self.link(self.mid + '.outputX', self.b + '.input1X')
        bridge = Bridge()
        ids = model.uuids_of([self.a, self.mid, self.b])
        bridge.store.set_pos(ids[1], 270, 130)
        bridge.store.set_width(ids[1], 345)
        bridge.add_nodes(ids, arrange_new=False)
        bridge._view_for(ids[1]).mode = 'full'
        bridge._view_for(ids[1]).expanded.add('input1')
        bridge.sync.start()
        bridge._flush_ui()
        cmds.flushUndo()
        try:
            bridge.deleteInbetween(ids[1])
            bridge.sync.flush()
            bridge._flush_ui()
            self.assertNotIn(ids[1], bridge.infos)
            # History reconciliation must work even with auto-add disabled and a full/locked tab.
            bridge.sync_on = False
            bridge.locked = True
            bridge.max_nodes = len(bridge.infos)
            cmds.undo()
            self.assertTrue(bridge.sync._history)
            bridge.sync.flush()
            bridge._flush_ui()
            self.assertIn(ids[1], bridge.infos)
            self.assertEqual(bridge.store.pos(ids[1]), (270, 130))
            self.assertEqual(bridge.infos[ids[1]]['width'], 345)
            self.assertEqual(bridge._view_for(ids[1]).mode, 'full')
            self.assertIn('input1', bridge._view_for(ids[1]).expanded)
            self.assertTrue(any(w['src'] == ids[1] and w['dst'] == ids[2] for w in bridge.wires))
            cmds.redo()
            bridge.sync.flush()
            bridge._flush_ui()
            self.assertNotIn(ids[1], bridge.infos)
            self.assertTrue(any(w['src'] == ids[0] and w['dst'] == ids[2] for w in bridge.wires))
        finally:
            bridge.sync.stop()
            bridge._flush_timer.stop()

    def test_native_delete_undo_revives_removed_and_dead_graph_nodes(self):
        self.link(self.a + '.outputX', self.mid + '.input1X')
        self.link(self.mid + '.outputX', self.b + '.input1X')
        ids = model.uuids_of([self.a, self.mid, self.b])
        for auto_add in (True, False):
            bridge = Bridge()
            bridge.sync_on = auto_add
            bridge.store.set_pos(ids[1], 360, 200)
            bridge.add_nodes(ids, arrange_new=False)
            bridge.sync.start()
            bridge._flush_ui()
            cmds.flushUndo()
            try:
                bridge.sel = [ids[1]]
                bridge.deleteSelected()
                bridge.sync.flush()
                bridge._flush_ui()
                if auto_add:
                    self.assertNotIn(ids[1], bridge.infos)
                else:
                    self.assertIn(ids[1], bridge.dead)
                cmds.undo()
                bridge.sync.flush()
                bridge._flush_ui()
                self.assertIn(ids[1], bridge.infos)
                self.assertNotIn(ids[1], bridge.dead)
                self.assertFalse(bridge.infos[ids[1]]['dead'])
                self.assertEqual(bridge.store.pos(ids[1]), (360, 200))
                self.assertTrue(any(w['src'] == ids[1] and w['dst'] == ids[2] for w in bridge.wires))
            finally:
                bridge.sync.stop()
                bridge._flush_timer.stop()
