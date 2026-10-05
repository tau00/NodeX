import unittest

import _maya

_maya.start()

import maya.cmds as cmds  # noqa: E402

from nodex import fixture, model, ops  # noqa: E402


def src(plug):
    return ops.source_of(plug)


class OpsTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()
        self.n = fixture.build()
        cmds.flushUndo()

    def P(self, key, attr):
        return self.n[key] + "." + attr

    # -------------------------------------------------------------- connect / disconnect / undo

    def test_connect_one_undo_step(self):
        err = ops.connect(self.P("db", "distance"), self.P("md", "input1Z"))
        self.assertEqual(err, "")
        self.assertEqual(src(self.P("md", "input1Z")), self.P("db", "distance"))
        cmds.undo()
        self.assertIsNone(src(self.P("md", "input1Z")))

    def test_rename_node(self):
        # one undo chunk, Maya's adjusted name comes back, errors are text.
        u = model.uuids_of([self.n["md"]])[0]
        new, err = ops.rename_node(self.n["md"], "  leg_scale_md ")
        self.assertEqual((new, err), ("leg_scale_md", ""))
        self.assertEqual(model.path_of(u), "leg_scale_md")
        cmds.undo()
        self.assertEqual(model.path_of(u), self.n["md"])
        clash, err = ops.rename_node(self.n["md"], self.n["db"])     # taken: Maya numbers it
        self.assertEqual(err, "")
        self.assertNotEqual(clash, self.n["db"])
        self.assertEqual(ops.rename_node(clash, ""), (clash, "A node name cannot be empty"))
        self.assertEqual(ops.rename_node(clash, clash), (clash, ""))
        fixed, err = ops.rename_node(clash, "1bad")                 # Maya fixes a bad name itself
        self.assertEqual(err, "")
        self.assertTrue(cmds.objExists(fixed))

    def test_connect_error_is_text(self):
        err = ops.connect(self.P("j1", "worldMatrix[0]"), self.P("md", "input1Z"))
        self.assertTrue(err)

    def test_disconnect_unit_conversion_wire(self):
        self.assertEqual(len(cmds.ls(type="unitConversion")), 1)
        cut = ops.disconnect_inputs([self.P("md", "input1Y")])
        self.assertEqual(cut, [self.P("md", "input1Y")])
        self.assertIsNone(src(self.P("md", "input1Y")))
        self.assertEqual(cmds.ls(type="unitConversion"), [])
        self.assertTrue(cmds.objExists(self.n["dm2"]))             # no cascade upstream
        cmds.undo()
        self.assertEqual(src(self.P("md", "input1Y")), self.P("dm2", "outputRotateZ"))

    def test_disconnect_many_one_chunk(self):
        ops.disconnect_inputs([self.P("pma", "input3D[0]"), self.P("pma", "input3D[1]")])
        self.assertIsNone(src(self.P("pma", "input3D[0]")))
        cmds.undo()
        self.assertEqual(src(self.P("pma", "input3D[0]")), self.P("dm1", "outputTranslate"))
        self.assertEqual(src(self.P("pma", "input3D[1]")), self.P("dm2", "outputTranslate"))

    def test_reroute(self):
        ops.reroute_input(self.P("db", "point2"), self.P("db", "point1"))
        self.assertIsNone(src(self.P("db", "point2")))
        self.assertEqual(src(self.P("db", "point1")), self.P("dm2", "outputTranslate"))

    # -------------------------------------------------------------- transfer

    def test_transfer_inputs(self):
        new = cmds.createNode("decomposeMatrix", name="dm_new")
        rep = ops.transfer(self.n["dm1"], [new], "in")
        self.assertEqual(src(new + ".inputMatrix"), self.P("j1", "worldMatrix[0]"))
        self.assertIsNone(src(self.P("dm1", "inputMatrix")))
        # outputs untouched
        self.assertEqual(src(self.P("pma", "input3D[0]")), self.P("dm1", "outputTranslate"))
        self.assertTrue(rep["moved"])
        cmds.undo()
        self.assertEqual(src(self.P("dm1", "inputMatrix")), self.P("j1", "worldMatrix[0]"))
        self.assertIsNone(src(new + ".inputMatrix"))

    def test_transfer_outputs(self):
        new = cmds.createNode("decomposeMatrix", name="dm_new")
        ops.transfer(self.n["dm1"], [new], "out")
        self.assertEqual(src(self.P("pma", "input3D[0]")), new + ".outputTranslate")
        self.assertEqual(src(self.P("db", "point1")), new + ".outputTranslate")
        self.assertEqual(src(self.P("mid", "rotate")), new + ".outputRotate")
        self.assertFalse(cmds.listConnections(self.n["dm1"], source=False, destination=True))
        self.assertEqual(src(self.P("dm1", "inputMatrix")), self.P("j1", "worldMatrix[0]"))

    def test_transfer_all_one_undo(self):
        new = cmds.createNode("decomposeMatrix", name="dm_new")
        cmds.flushUndo()
        ops.transfer(self.n["dm2"], [new], "all")
        self.assertEqual(src(new + ".inputMatrix"), self.P("j4", "worldMatrix[0]"))
        self.assertEqual(src(self.P("md", "input1Y")), new + ".outputRotateZ")
        self.assertFalse(cmds.listConnections(self.n["dm2"]))
        self.assertEqual(len(cmds.ls(type="unitConversion")), 1)   # the old one is gone, not doubled
        cmds.undo()
        self.assertEqual(src(self.P("md", "input1Y")), self.P("dm2", "outputRotateZ"))
        self.assertEqual(src(self.P("dm2", "inputMatrix")), self.P("j4", "worldMatrix[0]"))

    def test_transfer_skips_missing_attrs(self):
        grp = cmds.createNode("transform", name="grp_new")
        rep = ops.transfer(self.n["dm1"], [grp], "in")
        self.assertEqual(rep["moved"], [])
        self.assertTrue(rep["skipped"])
        self.assertEqual(src(self.P("dm1", "inputMatrix")), self.P("j1", "worldMatrix[0]"))

    # -------------------------------------------------------------- link by name / swap

    def test_link_by_name_decompose_to_transform(self):
        grp = cmds.createNode("transform", name="grp_new")
        res = ops.link_by_name(self.n["dm1"], [grp])
        self.assertEqual(src(grp + ".translate"), self.P("dm1", "outputTranslate"))
        self.assertEqual(src(grp + ".rotate"), self.P("dm1", "outputRotate"))
        self.assertEqual(src(grp + ".scale"), self.P("dm1", "outputScale"))
        self.assertEqual(src(grp + ".shear"), self.P("dm1", "outputShear"))
        self.assertEqual(len(res["made"]), 4)

    def test_link_by_name_respects_existing(self):
        res = ops.link_by_name(self.n["dm2"], [self.n["mid"]])
        # mid.translate is fed by the pma: kept without replace
        self.assertEqual(src(self.P("mid", "translate")), self.P("pma", "output3D"))
        self.assertTrue(any(d.endswith(".translate") for d, _ in res["skipped"]))
        ops.link_by_name(self.n["dm2"], [self.n["mid"]], replace=True)
        self.assertEqual(src(self.P("mid", "translate")), self.P("dm2", "outputTranslate"))

    def test_link_same_type_keyable(self):
        a = cmds.createNode("transform", name="a_grp")
        b = cmds.createNode("transform", name="b_grp")
        ops.link_by_name(a, [b])
        self.assertEqual(src(b + ".translate"), a + ".translate")
        self.assertEqual(src(b + ".visibility"), a + ".visibility")
        self.assertIsNone(src(b + ".offsetParentMatrix"))   # not keyable: never linked by name

    def test_lazy_connect_prefers_named_compound_and_undo(self):
        target = cmds.createNode('transform', name='lazy_target')
        cmds.flushUndo()
        sp, dp, error = ops.lazy_connect(self.n['dm1'], target)
        self.assertEqual((sp, dp, error), ('outputTranslate', 'translate', ''))
        self.assertEqual(src(target + '.translate'), self.P('dm1', 'outputTranslate'))
        cmds.undo()
        self.assertIsNone(src(target + '.translate'))

    def test_lazy_connect_keeps_occupied_input_and_rejects_matrix_scalar(self):
        target = cmds.createNode('transform', name='lazy_target')
        cmds.connectAttr(self.P('dm1', 'outputTranslate'), target + '.translate')
        ops.lazy_connect(self.n['dm2'], target)
        self.assertEqual(src(target + '.translate'), self.P('dm1', 'outputTranslate'))
        pairs = ops.lazy_pairs(self.n['j1'], self.n['md'])
        self.assertFalse(any('Matrix' in sp for sp, dp in pairs))
        self.assertIn('input3D[2]', dict(ops.socket_options(self.n['pma'], False)))

    def test_swap_inputs(self):
        ops.swap_inputs(self.P("db", "point1"), self.P("db", "point2"))
        self.assertEqual(src(self.P("db", "point1")), self.P("dm2", "outputTranslate"))
        self.assertEqual(src(self.P("db", "point2")), self.P("dm1", "outputTranslate"))

    def test_many_into_multi(self):
        pma = cmds.createNode("plusMinusAverage", name="pma_new")
        made = ops.connect_many_to_multi([self.P("dm1", "outputTranslate"),
                                          self.P("dm2", "outputTranslate")], pma + ".input3D")
        self.assertEqual([d for _, d in made], [pma + ".input3D[0]", pma + ".input3D[1]"])

    # -------------------------------------------------------------- names, values

    def test_copy_forms_nested_and_dag(self):
        grp = cmds.createNode("transform", name="rig_grp")
        cmds.parent(self.n["j1"], grp)
        j1 = grp + "|" + self.n["j1"]
        f = ops.copy_forms(j1 + ".translateX")
        self.assertEqual(f["attr"], "translateX")
        self.assertEqual(f["node"], self.n["j1"] + ".translateX")
        self.assertEqual(f["dag"], "|rig_grp|%s.translateX" % self.n["j1"])
        bm = cmds.createNode("blendMatrix", name="bm1")
        f = ops.copy_forms(bm + ".target[0].targetMatrix")
        self.assertEqual(f["attr"], "target[0].targetMatrix")
        self.assertEqual(f["node"], "bm1.target[0].targetMatrix")
        self.assertEqual(f["dag"], "bm1.target[0].targetMatrix")

    def test_set_value(self):
        self.assertEqual(ops.set_value(self.P("md", "input2Y"), "3.5"), "")
        self.assertAlmostEqual(cmds.getAttr(self.P("md", "input2Y")), 3.5)
        self.assertEqual(ops.set_value(self.P("md", "operation"), "Power"), "")
        self.assertEqual(cmds.getAttr(self.P("md", "operation")), 3)
        self.assertEqual(ops.set_value(self.P("j2", "rotateX"), "90"), "")
        self.assertAlmostEqual(cmds.getAttr(self.P("j2", "rotateX")), 90.0)
        self.assertEqual(ops.set_value(self.P("j2", "visibility"), "off"), "")
        self.assertFalse(cmds.getAttr(self.P("j2", "visibility")))
        self.assertTrue(ops.set_value(self.P("md", "input2Z"), "abc"))
        cmds.undo()   # the last successful set (visibility) is one step
        self.assertTrue(cmds.getAttr(self.P("j2", "visibility")))

    def test_create_node_utility(self):
        name = ops.create_node("multiplyDivide")
        self.assertEqual(cmds.nodeType(name), "multiplyDivide")


if __name__ == "__main__":
    unittest.main()
