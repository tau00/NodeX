import unittest

import _maya

_maya.start()

import maya.cmds as cmds  # noqa: E402

from nodex import fixture, model, theme  # noqa: E402


def rows_by_key(info):
    return dict((r["key"], r) for r in info["rows"])


class ModelTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()
        self.n = fixture.build()
        self.u = dict((k, model.uuids_of([v])[0]) for k, v in self.n.items())

    def test_joint_connected_mode(self):
        info = model.describe(self.u["j1"])
        rows = rows_by_key(info)
        self.assertEqual(info["type"], "joint")
        self.assertEqual(info["category"], "Joint")
        self.assertEqual(info["color"], theme.node_color("Joint"))
        wm = rows["worldMatrix[0]"]
        self.assertTrue(wm["outConn"])
        self.assertFalse(wm["inPort"])
        self.assertNotIn("shape", wm)            # every port is a filled circle, as Maya
        self.assertEqual(wm["color"], theme.attr_color("Matrix"))
        self.assertIn("more attribute", info["foot"])

    def test_math_node_rows(self):
        info = model.describe(self.u["md"])
        rows = rows_by_key(info)
        self.assertEqual(info["category"], "Utility")
        op = rows["operation"]
        self.assertEqual(op["kind"], "enum")
        self.assertEqual(op["value"], "Divide")
        self.assertEqual(info["rows"][0]["key"], "operation")   # fields first
        # input1 folded, its connected children stay visible
        self.assertIn("input1", rows)
        self.assertEqual(rows["input1"]["chev"], 1)
        self.assertTrue(rows["input1X"]["inConn"])
        self.assertTrue(rows["input1Y"]["inConn"])
        self.assertNotIn("input1Z", rows)
        self.assertEqual(rows["input1"]["cls"], "ThreeDNumericVector")

    def test_expand_shows_fields(self):
        view = model.NodeView(expanded=["input2"])
        rows = rows_by_key(model.describe(self.u["md"], view))
        self.assertEqual(rows["input2X"]["valueKind"], "num")
        self.assertEqual(rows["input2X"]["value"], "12.48")
        self.assertEqual(rows["input2Y"]["value"], "1.0")

    def test_rotation_class_and_multi(self):
        info = model.describe(self.u["dm1"])
        rows = rows_by_key(info)
        self.assertEqual(rows["outputRotate"]["cls"], "Rotation")
        pma = rows_by_key(model.describe(self.u["pma"]))
        self.assertIn("input3D[0]", pma)
        self.assertIn("input3D[1]", pma)
        self.assertEqual(pma["input3D[0]"]["label"], "Input 3D [0]")
        self.assertEqual(pma["input3D[2]"]["kind"], "slot")    # next free index to wire into

    def test_full_and_simple_modes(self):
        full = model.describe(self.u["md"], model.NodeView(mode="full"))
        conn = model.describe(self.u["md"])
        self.assertIn("input2", rows_by_key(full))
        self.assertNotIn("input2", rows_by_key(conn))
        simple = model.describe(self.u["md"], model.NodeView(mode="simple"))
        self.assertEqual(simple["rows"], [])
        self.assertEqual(simple["height"], model.HEADER_H)
        self.assertEqual(model.anchor_y(simple, "input1X"), model.HEADER_H / 2.0)

    def test_filter(self):
        info = model.describe(self.u["j1"], model.NodeView(filter_text="orient", filter_open=True))
        keys = [r["key"] for r in info["rows"]]
        self.assertEqual(keys[0], "__filter__")
        self.assertIn("jointOrient", keys)
        self.assertNotIn("worldMatrix[0]", keys)

    def test_wires_and_unit_conversion(self):
        uu = list(self.u.values())
        infos = dict((u, model.describe(u)) for u in uu)
        ws = model.wires(uu, infos)
        self.assertEqual(len(ws), len(fixture.WIRES))
        uc = [w for w in ws if w["uc"]]
        self.assertEqual(len(uc), 1)
        self.assertEqual(uc[0]["srcPlug"], "outputRotateZ")
        self.assertEqual(uc[0]["dstPlug"], "input1Y")
        self.assertEqual(uc[0]["color"], theme.attr_color("UnitConversion"))
        # dm2.outputRotateZ is folded under outputRotate: the wire meets the parent row
        dm2 = infos[self.u["dm2"]]
        self.assertEqual(uc[0]["srcY"], dm2["anchors"]["outputRotateZ"])

    def test_expanded_conversion_routes_through_it(self):
        uu = list(self.u.values())
        uc = [w for w in model.wires(uu) if w["uc"]][0]
        self.assertTrue(uc["conv"])
        conv = model.describe(uc["conv"], model.NodeView(pinned=["conversionFactor"]))
        self.assertTrue(conv["conv"])
        self.assertEqual(rows_by_key(conv)["conversionFactor"]["valueKind"], "num")
        ws = model.wires(uu + [uc["conv"]])
        self.assertFalse([w for w in ws if w["uc"]])
        into = [w for w in ws if w["dst"] == uc["conv"]][0]
        out = [w for w in ws if w["src"] == uc["conv"]][0]
        self.assertEqual((into["src"], into["srcPlug"]), (self.u["dm2"], "outputRotateZ"))
        self.assertEqual((out["dst"], out["dstPlug"]), (self.u["md"], "input1Y"))

    def test_wires_touching_matches_full_rebuild(self):
        uu = list(self.u.values())
        uc = [w for w in model.wires(uu) if w["uc"]][0]["conv"]
        for board in (uu, uu + [uc]):          # also with the unitConversion on the board
            infos = dict((u, model.describe(u)) for u in board)
            full = model.wires(board, infos)
            for touched in ([self.u["dm2"]], [self.u["md"], self.u["j1"]], [uc], board):
                t = set(touched)
                want = sorted(w["id"] for w in full if w["src"] in t or w["dst"] in t)
                got = model.wires_touching(touched, board, infos)
                self.assertEqual(sorted(w["id"] for w in got), want)
                byid = dict((w["id"], w) for w in full)
                for w in got:
                    self.assertEqual(w, byid[w["id"]])

    def _tops(self, node, mode):
        info = model.describe(model.uuids_of([node])[0], model.NodeView(mode=mode))
        return list(dict.fromkeys(model._top_of(r["key"]) for r in info["rows"] if r["depth"] == 0))

    def test_full_mode_is_mayas_rule_on_a_transform(self):
        # Maya's own Full on the user's Head_Chains_Grp: TRS + visibility,
        # outputs (message when connected) by name, dynamic by case-sensitive name, connected.
        t = cmds.createNode("transform", name="chains_grp")
        other = cmds.createNode("transform", name="other_grp")
        cmds.addAttr(t, ln="ik_fk_blender", at="double")
        cmds.addAttr(t, ln="zero_xforms", at="bool")
        cmds.addAttr(t, ln="HeadSupport", at="message")
        cmds.connectAttr(other + ".message", t + ".HeadSupport")
        cmds.connectAttr(other + ".translateX", t + ".ik_fk_blender")
        cmds.addAttr(other, ln="back", at="message")
        cmds.connectAttr(t + ".message", other + ".back")
        cmds.connectAttr(other + ".translate", t + ".rotatePivot")          # in only
        cmds.connectAttr(t + ".rotateOrder", other + ".rotateOrder")        # out only
        cmds.connectAttr(other + ".rotate", t + ".scalePivot")              # both ways
        cmds.connectAttr(t + ".scalePivot", other + ".scalePivot")
        # Groups by port side, as Maya draws them (clavicle_l: Rotate Order among the
        # outputs, Inverse Scale among the two-sided rows, Rotate Pivot last).
        self.assertEqual(self._tops(t, "full"), [
            "translate", "rotate", "scale", "visibility",
            "boundingBox", "center", "dagLocalInverseMatrix", "dagLocalMatrix", "inverseMatrix",
            "matrix", "message", "objectColorRGB", "parentInverseMatrix", "parentMatrix",
            "rotateOrder", "selectHandle", "transMinusRotatePivot", "worldInverseMatrix",
            "worldMatrix", "xformMatrix",
            "HeadSupport", "ik_fk_blender", "scalePivot", "zero_xforms",
            "rotatePivot"])
        # message only when connected
        self.assertNotIn("message", self._tops(self.n["mid"], "full"))

    def test_full_mode_is_mayas_rule_on_a_compute_node(self):
        # Maya's own Full on the user's Chest_Pivot_adjuster: Message, Output, Spine Support,
        # Auto Pivotbase, Input 1, Input 2 -- and no `operation` field.
        md = self.n["md"]
        cmds.addAttr(md, ln="auto_pivotbase", dt="string")
        cmds.addAttr(md, ln="SpineSupport", at="message", multi=True)
        cmds.connectAttr(self.n["mid"] + ".message", md + ".SpineSupport[0]")
        cmds.addAttr(self.n["db"], ln="back", at="message")
        cmds.connectAttr(md + ".message", self.n["db"] + ".back")
        self.assertEqual(self._tops(md, "full"),
                         ["message", "output", "SpineSupport", "auto_pivotbase", "input1", "input2"])

    def test_full_mode_reaches_hidden_connected_attrs(self):
        info = model.describe(self.u["md"], model.NodeView(mode="full"))
        self.assertNotIn("operation", rows_by_key(info))
        self.assertIn("more attribute", info["foot"])

    def test_show_all_attributes(self):
        full = model.describe(self.u["md"], model.NodeView(mode="full"))
        every = model.describe(self.u["md"], model.NodeView(mode=model.ALL))
        self.assertGreater(len(every["rows"]), len(full["rows"]))
        self.assertIn("operation", rows_by_key(every))
        self.assertEqual(every["foot"], "Show fewer attributes")
        # also from a board in full mode (the foot is no longer hidden there)
        board_full = model.describe(self.u["md"], None, "full")
        self.assertIn("more attribute", board_full["foot"])

    def test_custom_mode_is_maya_template_plus_connected(self):
        # NEtransformTemplate.xml: matrix, rotate, scale, translate; then connected attrs.
        keys = self._tops(self.n["mid"], "custom")
        self.assertEqual(keys[:4], ["matrix", "rotate", "scale", "translate"])
        self.assertNotIn("visibility", keys)
        md = self._tops(self.n["md"], "custom")
        self.assertEqual(md, ["output", "input1", "input2"])
        # no template (joint) -> Full
        self.assertEqual(self._tops(self.n["j1"], "custom"), self._tops(self.n["j1"], "full"))

    def test_custom_mode_node_specific_template_wins(self):
        import os
        import tempfile
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "NEmultiplyDivide.%sTemplate.xml" % self.n["md"]), "w") as f:
            f.write("<templates><view name='NEDefault' template='x'>"
                    "<group name='g'><property name='input2'/></group>"
                    "<property name='operation'/></view></templates>")
        old = os.environ.get("MAYA_CUSTOM_TEMPLATE_PATH", "")
        os.environ["MAYA_CUSTOM_TEMPLATE_PATH"] = d + os.pathsep + old
        model._templates.clear()
        try:
            keys = self._tops(self.n["md"], "custom")
        finally:
            os.environ["MAYA_CUSTOM_TEMPLATE_PATH"] = old
            model._templates.clear()
        # template order, then connected ones (input1 via input1X, output via outputX)
        self.assertEqual(keys, ["input2", "operation", "input1", "output"])

    def test_find_reveals_matching_rows(self):
        info = model.describe(self.u["md"], None, "connected", "input2")
        rows = rows_by_key(info)
        self.assertIn("input2", rows)
        self.assertEqual(rows["input2"]["hit"], "<u>Input 2</u>")
        self.assertEqual(rows["input2X"]["hit"], "<u>Input 2X</u>")   # matched by the long name
        self.assertEqual(rows_by_key(model.describe(self.u["md"], None, "connected", "2x"))["input2X"]["hit"], "Input <u>2X</u>")
        self.assertIn("input1X", rows)          # the connected rows stay
        self.assertEqual(rows["input1X"]["hit"], "")
        simple = model.describe(self.u["md"], model.NodeView(mode="simple"), "connected", "input2z")
        self.assertEqual([r["key"] for r in simple["rows"]], ["input2", "input2Z"])
        self.assertIn("input 2z", simple["search"])
        none = model.describe(self.u["md"], None, "connected", "nosuchattr")
        self.assertEqual(none["rows"], model.describe(self.u["md"])["rows"])

    def _blendshape(self):
        base = cmds.polyCube(name="face")[0]
        jaw = cmds.polyCube(name="jaw_open")[0]
        brow = cmds.polyCube(name="brow_up")[0]
        bs = cmds.blendShape(jaw, brow, base, name="face_bs")[0]
        cmds.connectAttr(self.n["db"] + ".distance", bs + ".weight[1]")
        return bs

    def test_multi_elements_show_their_alias(self):
        # blendShape rows name their targets, not "Weight [1]"; any aliased plug does.
        bs = self._blendshape()
        rows = rows_by_key(model.describe(model.uuids_of([bs])[0]))
        self.assertEqual(rows["weight[1]"]["label"], "brow_up")
        every = rows_by_key(model.describe(model.uuids_of([bs])[0], model.NodeView(mode=model.ALL)))
        self.assertEqual(every["weight[0]"]["label"], "jaw_open")
        self.assertEqual(model.plug_info(model.uuids_of([bs])[0], "weight[1]")["nice"], "brow_up")

    def test_labels_are_mayas_nice_names(self):
        t = self.n["mid"]
        cmds.addAttr(t, ln="ik_fk_blender", at="double", k=True)
        cmds.addAttr(t, ln="_worldW2", at="double", k=True)
        cmds.addAttr(t, ln="stretchy", nn="Stretch Amount", at="double", k=True)
        rows = rows_by_key(model.describe(model.uuids_of([t])[0], model.NodeView(mode="full")))
        self.assertEqual(rows["ik_fk_blender"]["label"], "Ik Fk Blender")
        self.assertEqual(rows["_worldW2"]["label"], "World W2")
        self.assertEqual(rows["stretchy"]["label"], "Stretch Amount")

    def test_find_reaches_every_attribute(self):
        # the find field indexes all attributes of a node -- hidden, short names,
        # dynamic ones of this node only, aliases -- and reveals the matching row.
        md = self.u["md"]
        rows = rows_by_key(model.describe(md, None, "connected", "message"))       # hidden
        self.assertIn("message", rows)
        self.assertIn("i2x", model.describe(md)["search"])                         # short name
        cmds.addAttr(self.n["mid"], ln="pole_twist", at="double")
        self.assertIn("pole_twist", model.describe(self.u["mid"])["search"])
        other = cmds.createNode("transform", name="other_grp")
        self.assertNotIn("pole_twist", model.describe(model.uuids_of([other])[0])["search"])
        bs = model.uuids_of([self._blendshape()])[0]
        found = rows_by_key(model.describe(bs, None, "connected", "jaw_open"))      # unconnected alias
        self.assertEqual(found["weight[0]"]["hit"], "<u>jaw_open</u>")

    def test_filter_finds_hidden_attributes(self):
        info = model.describe(self.u["md"], model.NodeView(filter_text="message", filter_open=True))
        self.assertIn("message", rows_by_key(info))

    def test_anchor_climbs_to_parent(self):
        info = model.describe(self.u["mid"])
        self.assertIn("translate", info["anchors"])
        self.assertEqual(model.anchor_y(info, "translate"), info["anchors"]["translate"])

    def test_nested_multi_compound(self):
        bm = cmds.createNode("blendMatrix")
        cmds.connectAttr(self.n["j1"] + ".worldMatrix[0]", bm + ".target[0].targetMatrix")
        info = model.describe(model.uuids_of([bm])[0])
        rows = rows_by_key(info)
        self.assertIn("target[0].targetMatrix", rows)
        self.assertTrue(rows["target[0].targetMatrix"]["inConn"])
        self.assertEqual(rows["target[0].targetMatrix"]["depth"], 1)

    def test_traverse(self):
        up = model.traverse([self.u["md"]], "up", 1)
        self.assertEqual(set(up), {self.u["md"], self.u["db"], self.u["dm2"]})
        allup = model.traverse([self.u["md"]], "up", None)
        self.assertIn(self.u["j1"], allup)
        self.assertIn(self.u["j4"], allup)

    def test_traverse_limit_keeps_the_nearest(self):
        allup = model.traverse([self.u["md"]], "up", None, limit=None)
        near = set(model.traverse([self.u["md"]], "up", 1, limit=None))
        cut = model.traverse([self.u["md"]], "up", None, limit=len(near))
        self.assertGreater(len(allup), len(near))
        self.assertEqual(set(cut), near)          # breadth-first: hop 1 fills the limit first

    def test_plug_info(self):
        info = model.plug_info(self.u["md"], "input1Y")
        self.assertEqual(info["io"], "input")
        self.assertTrue(info["source"].endswith(".outputRotateZ"))
        self.assertEqual(info["via"], "unitConversion")
        self.assertEqual(model.plug_info(self.u["md"], "input2X")["value"], "12.48")

    def test_nice_name(self):
        self.assertEqual(model.nice_name("input3D"), "Input 3D")
        self.assertEqual(model.nice_name("outputTranslateX"), "Output Translate X")
        self.assertEqual(model.nice_name("inMatrix1"), "In Matrix 1")


if __name__ == "__main__":
    unittest.main()
