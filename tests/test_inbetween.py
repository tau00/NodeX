"""Context filtering and transactional Utility insertion in a real Maya DG."""
import unittest
from unittest import mock

import _maya
_maya.start()
import maya.cmds as cmds
from nodex import fixture, model, ops
from nodex.bridge import Bridge


class InbetweenTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()
        self.n = fixture.build()
        cmds.flushUndo()

    def test_context_filters_both_ends_and_does_not_create_nodes(self):
        before = set(cmds.ls(long=True))
        undo = cmds.undoInfo(q=True, undoName=True)
        numeric = ops.utility_options(self.n['db'] + '.distance', self.n['md'] + '.input1X')
        matrix = ops.utility_options(self.n['j1'] + '.worldMatrix[0]', self.n['dm1'] + '.inputMatrix')
        self.assertIn('multiplyDivide', numeric)
        self.assertNotIn('multiplyDivide', matrix)
        self.assertIn('multMatrix', matrix)
        self.assertNotIn('multMatrix', numeric)
        self.assertIn('input1.input1X', dict(numeric['multiplyDivide'][0]))
        self.assertIn('output.outputX', dict(numeric['multiplyDivide'][1]))
        self.assertTrue(all(ops.compatible_sockets('Numeric', c)
                            for ins, outs in numeric.values() for p, c in ins + outs))
        self.assertTrue(all(c == 'Matrix' for ins, outs in matrix.values() for p, c in ins + outs))
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertEqual(cmds.undoInfo(q=True, undoName=True), undo)

    def test_multi_and_vector_socket_options(self):
        inputs = dict(ops.type_socket_options('plusMinusAverage', False))
        self.assertEqual(inputs['input3D[0]'], 'ThreeDNumericVector')
        self.assertEqual(inputs['input3D[0].input3Dx'], 'Numeric')
        mixed = ops.utility_options(self.n['j1'] + '.worldMatrix[0]', self.n['md'] + '.input1')
        self.assertIn('decomposeMatrix', mixed)
        self.assertNotIn('multMatrix', mixed)

    def test_native_insert_preserves_other_edges_and_single_undo(self):
        source = self.n['dm1'] + '.outputTranslate'
        dest = self.n['pma'] + '.input3D[0]'
        other = ops.source_of(self.n['pma'] + '.input3D[1]')
        before = set(cmds.ls(long=True))
        node = ops.insert_utility(source, dest, 'multiplyDivide', 'input1', 'output')
        self.assertEqual(ops.source_of(node + '.input1'), source)
        self.assertEqual(ops.source_of(dest), node + '.output')
        self.assertEqual(ops.source_of(self.n['pma'] + '.input3D[1]'), other)
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertEqual(ops.source_of(dest), source)
        cmds.redo()
        self.assertEqual(ops.source_of(dest), node + '.output')

    def test_existing_conversion_factor_kept_before_insert(self):
        source = self.n['dm2'] + '.outputRotateZ'
        dest = self.n['md'] + '.input1Y'
        raw = ops.source_of(dest, skip_conversion=False)
        conv = raw.split('.')[0]
        cmds.setAttr(conv + '.conversionFactor', 3.25)
        cmds.flushUndo()
        node = ops.insert_utility(source, dest, 'multiplyDivide', 'input1.input1X', 'output.outputX')
        self.assertEqual(ops.source_of(node + '.input1X', skip_conversion=False), raw)
        self.assertEqual(cmds.getAttr(conv + '.conversionFactor'), 3.25)
        cmds.undo()
        self.assertEqual(ops.source_of(dest, skip_conversion=False), raw)
        self.assertEqual(cmds.getAttr(conv + '.conversionFactor'), 3.25)

    def test_reject_stale_locked_and_invalid_attributes_before_creation(self):
        source, dest = self.n['dm1'] + '.outputTranslate', self.n['pma'] + '.input3D[0]'
        before = set(cmds.ls(long=True))
        for src, inp, out in ((self.n['dm2'] + '.outputTranslate', 'input1', 'output'),
                              (source, 'bad', 'output'), (source, 'input1', 'output.outputX')):
            with self.assertRaises(ValueError):
                ops.insert_utility(src, dest, 'multiplyDivide', inp, out)
        cmds.setAttr(dest, lock=True)
        with self.assertRaises(ValueError):
            ops.insert_utility(source, dest, 'multiplyDivide', 'input1', 'output')
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertEqual(ops.source_of(dest), source)

    def test_failed_second_connection_rolls_back_first_and_new_node(self):
        source, dest = self.n['dm1'] + '.outputTranslate', self.n['pma'] + '.input3D[0]'
        before = set(cmds.ls(long=True))
        connect = ops.connect
        def fail_output(a, b):
            return 'simulated connection failure' if b == dest else connect(a, b)
        with mock.patch.object(ops, 'connect', side_effect=fail_output):
            with self.assertRaises(RuntimeError):
                ops.insert_utility(source, dest, 'multiplyDivide', 'input1', 'output')
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertEqual(ops.source_of(dest), source)

    def test_bridge_insertion_adds_selects_and_undoes_in_one_step(self):
        b = Bridge()
        ids = model.uuids_of([self.n['dm1'], self.n['pma']])
        b.add_nodes(ids, arrange_new=False)
        b._flush_ui()
        wire = next(w for w in b.wires if w['src'] == ids[0] and w['dst'] == ids[1])
        before = set(cmds.ls(long=True))
        cmds.flushUndo()
        node = b._insert_inbetween(wire, 'multiplyDivide', 'input1', 'output')
        uid = model.uuids_of([node])[0]
        self.assertEqual(b.sel, [uid])
        self.assertIn(uid, b.infos)
        self.assertEqual(model.uuids_of(cmds.ls(sl=True)), [uid])
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertEqual(ops.source_of(self.n['pma'] + '.input3D[0]'), self.n['dm1'] + '.outputTranslate')
        b._flush_timer.stop()
