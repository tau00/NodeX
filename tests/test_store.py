import os
import tempfile
import unittest

import _maya

_maya.start()

import maya.cmds as cmds  # noqa: E402

from nodex import fixture, layout, model, store  # noqa: E402


class StoreTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()
        self.n = fixture.build()
        self.u = dict((k, model.uuids_of([v])[0]) for k, v in self.n.items())

    def test_roundtrip_through_file(self):
        s = store.Store()
        s.load()
        s.set_pos(self.u["j1"], 40, 90)
        s.set_pos(self.u["md"], 890.25, 320)
        s.tab["views"][self.u["md"]] = {"mode": "full", "expanded": ["input2"], "pinned": []}
        s.add_tab("ik_leg_l")
        s.set_pos(self.u["j4"], 10, 20)
        s.save()
        path = os.path.join(tempfile.gettempdir(), "nodex_store_test.ma")
        cmds.file(rename=path)
        cmds.file(save=True, type="mayaAscii", force=True)
        cmds.file(new=True, force=True)
        self.assertIsNone(store.store_node())
        cmds.file(path, open=True, force=True)
        s2 = store.Store()
        s2.load()
        self.assertEqual([t["name"] for t in s2.tabs], ["Graph 1", "ik_leg_l"])
        self.assertEqual(s2.active, 1)
        self.assertEqual(s2.pos(self.u["j4"]), (10.0, 20.0))
        t0 = s2.tabs[0]
        self.assertEqual(s2.pos(self.u["j1"], t0), (40.0, 90.0))
        self.assertEqual(s2.pos(self.u["md"], t0), (890.2, 320.0))   # rounded to 0.1
        self.assertEqual(t0["views"][self.u["md"]]["expanded"], ["input2"])
        # UUIDs survive the save/open, so positions still find their nodes
        self.assertEqual(model.path_of(self.u["md"]), self.n["md"])
        os.remove(path)

    def test_store_writes_do_not_touch_undo(self):
        cmds.flushUndo()
        cmds.setAttr(self.n["md"] + ".input2Y", 4.0)
        before = cmds.undoInfo(q=True, undoName=True)
        s = store.Store()
        s.set_pos(self.u["j1"], 1, 2)
        s.save()
        s.set_pos(self.u["j1"], 3, 4)
        s.save()
        self.assertEqual(cmds.undoInfo(q=True, undoName=True), before)
        cmds.undo()
        self.assertEqual(cmds.getAttr(self.n["md"] + ".input2Y"), 1.0)
        self.assertIsNotNone(store.store_node())

    def test_close_and_restore_tab(self):
        s = store.Store()
        s.add_tab("A")
        s.add_tab("B")
        s.set_pos(self.u["j1"], 5, 6)            # on B
        s.set_active(1)
        s.close_tab(2)
        self.assertEqual([t["name"] for t in s.tabs], ["Graph 1", "A"])
        self.assertEqual(s.recent[0]["tab"]["name"], "B")
        s.close_tab(0)
        self.assertEqual([t["name"] for t in s.tabs], ["A"])
        tab = s.restore_recent(1)                # B came back at index 2 -> clamped to the end
        self.assertEqual(tab["name"], "B")
        self.assertEqual([t["name"] for t in s.tabs], ["A", "B"])
        self.assertEqual(s.pos(self.u["j1"]), (5.0, 6.0))
        s.restore_recent(0)                      # Graph 1 back at index 0
        self.assertEqual([t["name"] for t in s.tabs], ["Graph 1", "A", "B"])
        self.assertEqual(s.tab["name"], "Graph 1")

    def test_closing_last_tab_keeps_one(self):
        s = store.Store()
        s.close_tab(0)
        self.assertEqual(len(s.tabs), 1)
        self.assertEqual(len(s.recent), 1)

    def test_recent_survives_save(self):
        s = store.Store()
        s.add_tab("keep")
        s.close_tab(1)
        s.save()
        s2 = store.Store()
        s2.load()
        self.assertEqual(s2.recent[0]["tab"]["name"], "keep")

    def test_node_width_set_by_hand(self):
        # a dragged width lives on the tab, survives a save, 0 goes back to the computed one.
        s = store.Store()
        s.set_pos(self.u["md"], 1, 2)
        self.assertIsNone(s.width(self.u["md"]))
        s.set_width(self.u["md"], 412.34)
        s.save()
        s2 = store.Store()
        s2.load()
        self.assertEqual(s2.width(self.u["md"]), 412.3)
        s2.set_width(self.u["md"], 0)
        self.assertIsNone(s2.width(self.u["md"]))
        s2.set_width(self.u["md"], 300)
        s2.remove(self.u["md"], remember=False)
        self.assertIsNone(s2.width(self.u["md"]))
        # a tab saved before widths existed (e.g. one in "Recently closed")
        old = store.new_tab("old")
        del old["widths"]
        self.assertIsNone(s2.width(self.u["md"], old))
        s2.set_width(self.u["md"], 250, old)
        self.assertEqual(s2.width(self.u["md"], old), 250.0)

    def test_gone_and_prune(self):
        s = store.Store()
        s.set_pos(self.u["md"], 7, 8)
        s.remove(self.u["md"])
        self.assertIsNone(s.pos(self.u["md"]))
        self.assertEqual(s.tab["gone"][self.u["md"]], [7.0, 8.0])
        s.prune([self.u["md"]])
        self.assertIn(self.u["md"], s.tab["gone"])
        s.prune([])
        self.assertNotIn(self.u["md"], s.tab["gone"])


class LayoutTest(unittest.TestCase):
    def test_place_never_overlaps_and_never_moves(self):
        rects = [(0, 0, 200, 120), (0, 200, 200, 120), (300, 0, 200, 300)]
        before = list(rects)
        x, y = layout.place((200, 100), rects, cursor=(100, 60))
        self.assertFalse(layout._overlaps((x, y, 200, 100), rects))
        self.assertEqual(rects, before)

    def test_place_beside_upstream(self):
        rects = [(0, 0, 200, 120)]
        x, y = layout.place((200, 100), rects, upstream=[rects[0]])
        self.assertEqual((x, y), (200 + layout.GAP_X, 0))

    def test_layered_columns(self):
        sizes = dict((k, (200, 100)) for k in "abcd")
        pos = layout.layered("abcd", sizes, [("a", "b"), ("b", "c"), ("a", "c"), ("d", "c")])
        self.assertEqual(pos["a"][0], pos["d"][0])
        self.assertLess(pos["a"][0], pos["b"][0])
        self.assertLess(pos["b"][0], pos["c"][0])

    def test_layered_cycle_safe(self):
        sizes = dict((k, (200, 100)) for k in "ab")
        pos = layout.layered("ab", sizes, [("a", "b"), ("b", "a")])
        self.assertEqual(len(pos), 2)

    def test_columns_long_chain_no_recursion_limit(self):
        ids = ["n%d" % i for i in range(5000)]
        edges = [(ids[i], ids[i + 1]) for i in range(4999)]
        col, _ups = layout.columns(ids, edges)
        self.assertEqual(col["n0"], 0)
        self.assertEqual(col["n4999"], 4999)
        col, _ups = layout.columns(ids, edges + [(ids[-1], ids[0])])   # one long cycle
        self.assertEqual(sorted(col.values()), list(range(1, 5001)))

    def _aspect(self, pos, sizes):
        x0, y0, x1, y1 = layout._bbox(pos, sizes)
        return (x1 - x0) / float(y1 - y0)

    def _no_overlap(self, pos, sizes):
        ids = list(pos)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                ra = (pos[a][0], pos[a][1], sizes[a][0], sizes[a][1])
                rb = (pos[b][0], pos[b][1], sizes[b][0], sizes[b][1])
                self.assertFalse(ra[0] < rb[0] + rb[2] and rb[0] < ra[0] + ra[2] and
                                 ra[1] < rb[1] + rb[3] and rb[1] < ra[1] + ra[3]), (a, b)

    def test_wrap_tall_column_to_view_aspect(self):
        # 200 sources feeding 200 sinks: two columns ~28000 px tall before wrapping
        ids = ["s%d" % i for i in range(200)] + ["t%d" % i for i in range(200)]
        sizes = dict((i, (200, 100)) for i in ids)
        edges = [("s%d" % i, "t%d" % i) for i in range(200)]
        pos = layout.layered(ids, sizes, edges, origin=(0.0, 0.0))
        self.assertLess(self._aspect(pos, sizes), 0.1)
        out = layout.wrap(pos, sizes, aspect=1.6)
        self.assertGreater(self._aspect(out, sizes), 1.6 / 1.8)
        self.assertLess(self._aspect(out, sizes), 1.6 * 1.8)
        self._no_overlap(out, sizes)
        # a source and its sink stay side by side
        self.assertEqual(out["s7"][1], out["t7"][1])
        self.assertLess(out["s7"][0], out["t7"][0])

    def test_wrap_long_chain_and_small_graphs(self):
        ids = ["n%d" % i for i in range(60)]
        sizes = dict((i, (200, 100)) for i in ids)
        pos = layout.layered(ids, sizes, [(ids[i], ids[i + 1]) for i in range(59)], origin=(0.0, 0.0))
        out = layout.wrap(pos, sizes, aspect=1.6)
        self.assertLess(self._aspect(out, sizes), 1.6 * 1.8)
        self._no_overlap(out, sizes)
        small = layout.layered("ab", dict((k, (200, 100)) for k in "ab"), [("a", "b")])
        self.assertEqual(layout.wrap(small, dict((k, (200, 100)) for k in "ab")), small)


if __name__ == "__main__":
    unittest.main()
