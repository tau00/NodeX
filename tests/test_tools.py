"""2026-10-04 batch: name-rule bulk connect, arrange variants, node search ranking, shape
display filter, slide parameters, JSON presets, frames in the tab store."""
import os
import tempfile
import unittest

import _maya
_maya.start()
import maya.cmds as cmds
from nodex import catalog, layout, model, naming, ops, presets, store


class NamingTest(unittest.TestCase):
    def test_rules(self):
        cases = [("skin_spine1", "drv_spine1", "skin_spine2", "drv_spine2"),
                 ("jnt1", "jnt1_ctrl", "jnt2", "jnt2_ctrl"),
                 ("L_arm_jnt", "L_arm_ctrl", "L_hand_jnt", "L_hand_ctrl"),
                 ("arm_L_jnt", "arm_R_jnt", "Leg_L_jnt", "Leg_R_jnt"),
                 ("rigA:hand", "rigB:hand", "rigA:foot", "rigB:foot"),
                 ("|grp|a_src", "|grp|a_dst", "b_src", "b_dst")]
        for a, b, x, y in cases:
            self.assertEqual(naming.apply(x, naming.rule(a, b)), y, (a, b, x))

    def test_pairs_need_a_selected_partner_once(self):
        sel = ["skin_a", "drv_a", "skin_b", "drv_b", "skin_c", "other"]
        self.assertEqual(naming.pairs("skin_a", "drv_a", sel), [("skin_b", "drv_b")])
        self.assertEqual(naming.pairs("a", "a", ["a", "b"]), [])


class ArrangeTest(unittest.TestCase):
    sizes = {"a": (100, 50), "b": (100, 80), "c": (100, 50)}
    pos = {"a": (0, 0), "b": (300, 200), "c": (300, 10)}

    def test_row_and_column(self):
        row = layout.align_row(list(self.sizes), self.sizes, self.pos)
        self.assertEqual(len(set(p[1] for p in row.values())), 1)
        self.assertEqual([k for k, _ in sorted(row.items(), key=lambda kv: kv[1][0])], ["a", "b", "c"])
        col = layout.align_column(list(self.sizes), self.sizes, self.pos)
        self.assertEqual(len(set(p[0] for p in col.values())), 1)

    def test_straighten_aligns_main_wire_without_overlap(self):
        out = layout.straighten(list(self.sizes), self.sizes, self.pos, [("a", 30, "c", 40), ("a", 30, "b", 40)])
        self.assertEqual(out["a"], (0, 0))
        tops = sorted([out["b"][1], out["c"][1]])
        self.assertEqual(tops[0], -10)                      # one of them runs straight off a
        self.assertGreaterEqual(tops[1] - tops[0], 50 + layout.GAP_Y)

    def test_grid_sorted(self):
        g = layout.grid(["c", "a", "b"], self.sizes, lambda i: i, (0, 0), aspect=10)
        self.assertEqual(sorted(g, key=lambda i: (g[i][1], g[i][0])), ["a", "b", "c"])


class CatalogTest(unittest.TestCase):
    def test_text_ranking(self):
        cat = catalog.Catalog()
        self.assertEqual(cat.search("decomposeMatrix")[0], "decomposeMatrix")
        self.assertEqual(cat.search("dm")[0], "decomposeMatrix")
        self.assertIn("plusMinusAverage", cat.search("add")[:8])

    def test_context(self):
        cat = catalog.Catalog()
        ib = cat.inbetween("Matrix", "Matrix")
        self.assertIn("multMatrix", [r[0] for r in ib[:6]])
        self.assertTrue(all(c == "Matrix" for r in ib[:10] for _, c in r[3][:1]))
        lt = cat.link_targets("Matrix", True, hint="worldMatrix[0]")
        self.assertEqual(lt[0][2], "Matrix")
        self.assertIn("decomposeMatrix", [t for t, _, _ in lt[:5]])
        self.assertTrue(cat.link_targets("Matrix", True, query="mult.matrixin"))


class ShapeAndValueTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()

    def test_shape_filter(self):
        t = cmds.polyCube(name="box")[0]
        shape = cmds.listRelatives(t, shapes=True, fullPath=True)[0]
        tu, su = model.uuids_of([t, shape])
        self.assertEqual(model.apply_shape_filter([tu], "all"), [tu, su])
        self.assertEqual(model.apply_shape_filter([su], "none"), [tu])
        sg = model.uuids_of(["initialShadingGroup"])[0]
        self.assertNotIn(sg, model.apply_shape_filter([tu, sg], "except"))
        self.assertIn(sg, model.apply_shape_filter([tu, sg], "except", keep=[sg]))
        self.assertTrue(model.is_matrix_type("multMatrix"))
        self.assertEqual(model.category("multMatrix", False), "Matrix")

    def test_slide_meta(self):
        n = cmds.createNode("transform")
        m = ops.slide_meta(ops._mplug(n + ".rotateX"))
        self.assertEqual((m["step"], m["coarse"]), (0.5, 5.0))
        r = cmds.createNode("remapValue")
        m = ops.slide_meta(ops._mplug(r + ".inputMin"))
        self.assertFalse(m["isInt"])


class PresetTest(unittest.TestCase):
    def test_roundtrip_and_bare_snapshot(self):
        snap = {"version": 1, "selected": ["u1"], "layout": {}}
        d = tempfile.mkdtemp()
        path = presets.write(snap, "my preset", os.path.join(d, "p.json"))
        self.assertEqual(presets.read(path), {"name": "my preset", "snapshot": snap})
        bad = os.path.join(d, "bad.json")
        with open(bad, "w") as fh:
            fh.write('{"version": 2}')
        with self.assertRaises(ValueError):
            presets.read(bad)

    def test_tabs_carry_frames(self):
        self.assertEqual(store.new_tab("x")["frames"], [])
        data = store._normalise({"tabs": [{"name": "a", "frames": [{"id": "f1"}]}]})
        self.assertEqual(data["tabs"][0]["frames"], [{"id": "f1"}])


if __name__ == "__main__":
    unittest.main()
