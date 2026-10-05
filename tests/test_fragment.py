"""Real Maya fragment snapshots: boundary links, values, conversion semantics and undo."""
import unittest

import _maya
_maya.start()
import maya.cmds as cmds
from nodex import fixture, fragment, model, ops
from nodex.bridge import Bridge


class FragmentTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()
        self.n = fixture.build()
        cmds.flushUndo()

    def paste(self, keys):
        names = [self.n[k] for k in keys]
        snapshot = fragment.capture(names)
        mapping = fragment.paste(snapshot)
        return {k: model.path_of(mapping[u]) for k, u in zip(keys, snapshot['selected'])}

    def test_internal_links_only_and_values(self):
        cmds.addAttr(self.n['md'], longName='note', dataType='string')
        cmds.setAttr(self.n['md'] + '.note', 'quoted "hello"; // comment\nnext line', type='string')
        old_nodes = set(cmds.ls(long=True))
        new = self.paste(['dm1', 'dm2', 'pma', 'md'])
        self.assertEqual(ops.source_of(new['pma'] + '.input3D[0]'), new['dm1'] + '.outputTranslate')
        self.assertEqual(ops.source_of(new['pma'] + '.input3D[1]'), new['dm2'] + '.outputTranslate')
        self.assertIsNone(ops.source_of(new['dm1'] + '.inputMatrix'))
        self.assertIsNone(ops.source_of(new['md'] + '.input1X'))
        self.assertEqual(cmds.getAttr(new['md'] + '.operation'), cmds.getAttr(self.n['md'] + '.operation'))
        self.assertEqual(cmds.getAttr(new['md'] + '.note'), cmds.getAttr(self.n['md'] + '.note'))
        self.assertEqual(ops.source_of(self.n['mid'] + '.translate'), self.n['pma'] + '.output3D')
        self.assertEqual(len(set(cmds.ls(long=True)) - old_nodes), 5)  # four explicit + internal conversion
        self.assertFalse(cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) and
                         any('nodexPaste_' in n for n in cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)))
        self.assertFalse(any(a.startswith('_nodexFragment_') for node in new.values()
                             for a in (cmds.listAttr(node, userDefined=True) or [])))

    def test_hidden_conversion_factor_and_undo_redo(self):
        conv = cmds.ls(type='unitConversion')[0]
        cmds.setAttr(conv + '.conversionFactor', 3.25)
        cmds.flushUndo()
        before = set(cmds.ls(long=True))
        new = self.paste(['dm2', 'md'])
        self.assertEqual(ops.source_of(new['md'] + '.input1Y'), new['dm2'] + '.outputRotateZ')
        copied_conv = ops.source_of(new['md'] + '.input1Y', skip_conversion=False).split('.')[0]
        self.assertEqual(cmds.getAttr(copied_conv + '.conversionFactor'), 3.25)
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.redo()
        self.assertEqual(ops.source_of(new['md'] + '.input1Y'), new['dm2'] + '.outputRotateZ')

    def test_copy_is_snapshot_after_source_deleted_repeated_paste(self):
        snapshot = fragment.capture([self.n['dm1'], self.n['pma']])
        cmds.delete(self.n['dm1'], self.n['pma'])
        a, b = fragment.paste(snapshot), fragment.paste(snapshot)
        self.assertTrue(set(a.values()).isdisjoint(b.values()))
        for mapping in (a, b):
            dm, pma = [model.path_of(mapping[u]) for u in snapshot['selected']]
            self.assertEqual(ops.source_of(pma + '.input3D[0]'), dm + '.outputTranslate')
            self.assertIsNone(ops.source_of(pma + '.input3D[1]'))

    def test_copy_preserves_selection_undo_and_scene_globals(self):
        cmds.select(self.n['mid'])
        cmds.setAttr(self.n['md'] + '.input2Z', 5)
        undo = cmds.undoInfo(q=True, undoName=True)
        before = set(cmds.ls(long=True))
        cmds.currentTime(17)
        snapshot = fragment.capture([self.n['dm1'], self.n['pma']])
        self.assertEqual(cmds.ls(sl=True), [self.n['mid']])
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertEqual(cmds.undoInfo(q=True, undoName=True), undo)
        cmds.setAttr('defaultResolution.width', 1923)
        fragment.paste(snapshot)
        self.assertEqual(cmds.getAttr('defaultResolution.width'), 1923)
        self.assertEqual(cmds.currentTime(q=True), 17)
        self.assertEqual(cmds.ls(sl=True), [self.n['mid']])

    def test_dag_selection_excludes_unselected_parent_and_children(self):
        parent = cmds.createNode('transform', name='outside')
        root = cmds.createNode('transform', name='inside', parent=parent)
        child = cmds.createNode('transform', name='child', parent=root)
        cmds.createNode('transform', name='outsideChild', parent=child)
        before = set(cmds.ls(long=True))
        snap = fragment.capture([root, child])
        mapping = fragment.paste(snap)
        new = [model.path_of(mapping[u]) for u in snap['selected']]
        self.assertEqual(len(set(cmds.ls(long=True)) - before), 2)
        self.assertFalse(cmds.listRelatives(new[0], parent=True))
        self.assertEqual(model.uuids_of(cmds.listRelatives(new[1], parent=True)), [mapping[snap['selected'][0]]])

    def test_namespaced_nodes_and_unicode_values(self):
        cmds.namespace(add='rig')
        a = cmds.createNode('multiplyDivide', name='rig:math')
        cmds.addAttr(a, longName='label', dataType='string')
        cmds.setAttr(a + '.label', '\u041f\u0440\u0438\u0432\u0435\u0442', type='string')
        original = cmds.getAttr(a + '.label')
        snap = fragment.capture([a])
        self.assertEqual(cmds.getAttr(a + '.label'), original)
        copied = model.path_of(fragment.paste(snap)[snap['selected'][0]])
        self.assertEqual(cmds.getAttr(a + '.label'), original)
        self.assertEqual([ord(c) for c in cmds.getAttr(copied + '.label')], [ord(c) for c in original])

    def test_bridge_layout_display_selection_and_single_undo(self):
        b = Bridge()
        ids = model.uuids_of([self.n['dm1'], self.n['pma']])
        b.store.set_pos(ids[0], -100, 40)
        b.store.set_pos(ids[1], 180, 260)
        b.add_nodes(ids, arrange_new=False)
        b.sel = ids
        b._view_for(ids[0]).mode = 'full'
        b._view_for(ids[0]).expanded.add('outputTranslate')
        b.store.set_width(ids[0], 370)
        b.max_nodes = len(ids)  # refusal must not create a partial graph
        snap = b._capture_fragment()
        before = set(cmds.ls(long=True))
        b._paste_fragment(snap, 1000, -200)
        self.assertEqual(set(cmds.ls(long=True)), before)
        b.max_nodes = 500
        cmds.flushUndo()
        b._paste_fragment(snap, 1000, -200)
        copied = list(b.sel)
        self.assertEqual([b.store.pos(u) for u in copied], [(1000, -200), (1280, 20)])
        self.assertEqual(b._view_for(copied[0]).mode, 'full')
        self.assertEqual(b.store.width(copied[0]), 370)
        self.assertIn('outputTranslate', b._view_for(copied[0]).expanded)
        self.assertEqual(model.uuids_of(cmds.ls(sl=True)), copied)
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.redo()
        self.assertTrue(all(model.path_of(u) for u in copied))
        b._flush_timer.stop()

    def test_dag_undo_redo_and_cross_scene_units(self):
        root = cmds.createNode('transform', name='fragment_root')
        child = cmds.createNode('transform', name='fragment_child', parent=root)
        cmds.setAttr(root + '.rotateX', 30)
        snap = fragment.capture([root, child])
        _maya.fresh_scene()
        cmds.currentUnit(angle='radian', linear='meter')
        before = set(cmds.ls(long=True))
        mapping = fragment.paste(snap)
        copied = [model.path_of(mapping[u]) for u in snap['selected']]
        self.assertAlmostEqual(cmds.getAttr(copied[0] + '.rotateX'), 0.5235987756)
        self.assertEqual(cmds.currentUnit(q=True, angle=True), 'rad')
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.redo()
        self.assertTrue(all(model.path_of(u) for u in mapping.values()))

    def test_shape_only_paste_excludes_original_parent_and_undo(self):
        mesh = cmds.createNode('mesh', name='fragment_mesh')
        parent = cmds.listRelatives(mesh, parent=True)[0]
        snap = fragment.capture([mesh])
        before = set(cmds.ls(long=True))
        mapping = fragment.paste(snap)
        shape = model.path_of(mapping[snap['selected'][0]])
        self.assertNotIn(parent, cmds.listRelatives(shape, parent=True) or [])
        cmds.undo()
        self.assertEqual(set(cmds.ls(long=True)), before)
        cmds.redo()
        self.assertTrue(model.path_of(mapping[snap['selected'][0]]))

    def test_transform_copy_includes_geometry_all_shapes_and_no_history(self):
        cube, history = cmds.polyCube(name='copy_cube', width=3, height=5, depth=7)
        mesh = cmds.listRelatives(cube, shapes=True, fullPath=True)[0]
        points = cmds.xform(mesh + '.vtx[*]', q=True, objectSpace=True, translation=True)
        curve = cmds.circle(name='extra_shape')[0]
        curve_shape = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]
        curve_shape = cmds.parent(curve_shape, cube, shape=True, relative=True)[0]
        cmds.setAttr(curve_shape + '.intermediateObject', True)
        snap = fragment.capture([cube])
        self.assertEqual(len(snap['selected']), 1)
        cmds.delete(cube)
        before = set(cmds.ls(uuid=True))
        copy = model.path_of(fragment.paste(snap)[snap['selected'][0]])
        shapes = cmds.listRelatives(copy, shapes=True, fullPath=True)
        self.assertEqual(len(shapes), 2)
        copied_mesh = next(s for s in shapes if cmds.nodeType(s) == 'mesh')
        self.assertEqual(cmds.xform(copied_mesh + '.vtx[*]', q=True,
                                   objectSpace=True, translation=True), points)
        self.assertIsNone(ops.source_of(copied_mesh + '.inMesh'))
        copied_curve = next(s for s in shapes if cmds.nodeType(s) == 'nurbsCurve')
        self.assertTrue(cmds.getAttr(copied_curve + '.intermediateObject'))
        self.assertEqual(len(set(cmds.ls(uuid=True)) - before), 3)
        cmds.undo()
        self.assertEqual(set(cmds.ls(uuid=True)), before)
        cmds.redo()
        self.assertEqual(cmds.polyEvaluate(copied_mesh, vertex=True), 8)

    def test_explicit_shape_and_transform_copy_shape_once(self):
        cube = cmds.polyCube()[0]
        shape = cmds.listRelatives(cube, shapes=True, fullPath=True)[0]
        snap = fragment.capture([cube, shape])
        mapping = fragment.paste(snap)
        copied = model.path_of(mapping[snap['selected'][0]])
        self.assertEqual(model.uuids_of(cmds.listRelatives(copied, shapes=True)),
                         [mapping[snap['selected'][1]]])
        self.assertEqual(cmds.polyEvaluate(copied, vertex=True), 8)

    def test_shift_d_native_parent_hierarchy_shapes_and_single_undo(self):
        outside = cmds.createNode('transform', name='duplicate_parent')
        cube = cmds.polyCube(name='duplicate_cube')[0]
        cube = cmds.parent(cube, outside)[0]
        child = cmds.polySphere(name='duplicate_child')[0]
        child = cmds.parent(child, cube)[0]
        child = cmds.ls(child, long=True)[0]
        cmds.setAttr(cube + '.translateX', 12)
        b = Bridge()
        source = model.uuids_of([cube])[0]
        b.store.set_pos(source, 20, 30)
        b.add_nodes([source], arrange_new=False)
        b.sel = [source]
        b.store.set_width(source, 340)
        b._capture_fragment = lambda: self.fail('Duplicate must use native Maya duplication')
        before = set(cmds.ls(uuid=True))
        cmds.flushUndo()
        b.duplicateFragment()
        self.assertNotEqual(b.sel, [source])
        copied = model.path_of(b.sel[0])
        self.assertEqual(model.uuids_of(cmds.listRelatives(copied, parent=True)),
                         model.uuids_of([outside]))
        self.assertEqual(cmds.getAttr(copied + '.translateX'), 12)
        self.assertEqual(cmds.polyEvaluate(copied, vertex=True), 8)
        children = cmds.listRelatives(copied, children=True, type='transform', fullPath=True)
        self.assertEqual(len(children), 1)
        self.assertEqual(cmds.polyEvaluate(children[0], vertex=True), cmds.polyEvaluate(child, vertex=True))
        self.assertEqual(b.store.pos(b.sel[0]), (64, 74))
        self.assertEqual(b.store.width(b.sel[0]), 340)
        cmds.undo()
        self.assertEqual(set(cmds.ls(uuid=True)), before)
        cmds.redo()
        self.assertEqual(cmds.polyEvaluate(copied, vertex=True), 8)
        b._flush_timer.stop()

    def test_shape_only_shift_d_copies_object_and_selected_child_not_twice(self):
        cube = cmds.polyCube()[0]
        shape = cmds.listRelatives(cube, shapes=True, fullPath=True)[0]
        b = Bridge()
        ids = model.uuids_of([shape, cube])
        b.add_nodes(ids, arrange_new=False)
        b.sel = ids[:1]
        b.duplicateFragment()
        copied = model.path_of(b.sel[0])
        self.assertEqual(cmds.nodeType(copied), 'transform')
        self.assertEqual(cmds.polyEvaluate(copied, vertex=True), 8)
        b.sel = ids
        b.duplicateFragment()
        self.assertEqual(len(b.sel), 1)
        self.assertEqual(len(cmds.listRelatives(model.path_of(b.sel[0]), shapes=True)), 1)
        b._flush_timer.stop()

    def test_distribute_wire_connections_replacement_and_one_undo(self):
        b = Bridge()
        source, a, c, outside = [self.n[k] for k in ('dm1', 'md', 'pma', 'dm2')]
        cmds.connectAttr(outside + '.outputTranslateX', a + '.input2X')
        previous = ops.source_of(a + '.input2X')
        cmds.flushUndo()
        su, au, cu = model.uuids_of([source, a, c])
        targets = [{'nid': au, 'key': 'input2X'}, {'nid': cu, 'key': 'input3D[2].input3Dx'},
                   {'nid': au, 'key': 'input2X'}]
        b.distributeWire(su, 'outputTranslateX', targets)
        self.assertEqual(ops.source_of(a + '.input2X'), source + '.outputTranslateX')
        self.assertEqual(ops.source_of(c + '.input3D[2].input3Dx'), source + '.outputTranslateX')
        cmds.undo()
        self.assertEqual(ops.source_of(a + '.input2X'), previous)
        self.assertIsNone(ops.source_of(c + '.input3D[2].input3Dx'))
        cmds.redo()
        self.assertEqual(ops.source_of(a + '.input2X'), source + '.outputTranslateX')
        b._flush_timer.stop()


if __name__ == '__main__':
    unittest.main()
