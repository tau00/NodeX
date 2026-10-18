"""Real Maya callbacks through SceneSync: the board's other tests feed it made-up events."""
import os
import tempfile
import unittest
from unittest import mock

import _maya

_maya.start()

import maya.cmds as cmds  # noqa: E402

from nodex import fixture, model, sync  # noqa: E402
from nodex.bridge import ADD_NEW_VAR, Bridge  # noqa: E402


class SceneSyncTest(unittest.TestCase):
    def setUp(self):
        _maya.fresh_scene()
        self.n = fixture.build()
        self.sync = sync.SceneSync()
        self.events = []
        self.sync.flushed.connect(self.events.append)
        self.sync.start()

    def tearDown(self):
        self.sync.stop()

    def flush(self):
        self.sync.flush()        # the 30 ms timer does not run headless
        return self.events[-1]

    def test_node_made_by_script_is_reported(self):
        # The callback once raised on every node (API 2.0 has no MFileIO) and reported none.
        u = model.uuids_of([cmds.createNode("multiplyDivide")])[0]
        self.assertEqual(self.flush()["added"], [u])

    def test_rename_is_reported(self):
        cmds.rename(self.n["md"], "leg_scale_md")
        self.assertIn(model.uuids_of(["leg_scale_md"])[0], self.flush()["renamed"])

    def test_import_is_not_reported(self):
        path = os.path.join(tempfile.gettempdir(), "nodex_sync_test.ma")
        cmds.file(rename=path)
        cmds.file(save=True, type="mayaAscii", force=True)
        self.addCleanup(os.remove, path)
        self.flush()
        cmds.file(path, i=True, namespace="imp")
        self.assertEqual(self.flush()["added"], [])

    def test_callback_failure_is_reported_once(self):
        # Callbacks never raise into Maya; a silent guard once hid the MFileIO bug for good.
        sync._reported.discard("renamed")
        with mock.patch.object(sync.traceback, "print_exc") as printed:
            self.sync._on_renamed(None, "", None)     # no node: uuid_of raises
            self.sync._on_renamed(None, "", None)
        self.assertEqual(printed.call_count, 1)

    def test_script_node_reaches_the_board(self):
        saved = cmds.optionVar(q=ADD_NEW_VAR) if cmds.optionVar(exists=ADD_NEW_VAR) else None
        cmds.optionVar(remove=ADD_NEW_VAR)
        self.sync.stop()
        b = Bridge()
        try:
            b.sync.start()
            u = model.uuids_of([cmds.createNode("multiplyDivide")])[0]
            b.sync.flush()
            self.assertIn(u, b.infos)
        finally:
            b.sync.stop()
            b._flush_timer.stop()
            if saved is not None:
                cmds.optionVar(intValue=(ADD_NEW_VAR, int(saved)))


if __name__ == "__main__":
    unittest.main()
