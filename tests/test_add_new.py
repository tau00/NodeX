"""Options > Add new nodes to tab: nodes made outside NodeX join the active tab only when it is on."""
import unittest
import _maya
_maya.start()
import maya.cmds as cmds
from nodex import catalog, model
from nodex.bridge import ADD_NEW_VAR, Bridge


def event(added=(), removed=(), history=False):
    """The flush payload of sync.SceneSync, as _on_scene_events receives it."""
    return {"added": list(added), "removed": list(removed), "renamed": [], "changed": [],
            "values": [], "selection": False, "scene": None, "history": history}


class AddNewTest(unittest.TestCase):
    def setUp(self):
        # The bridge reads the preference: start from the default, never the developer's.
        cmds.optionVar(remove=ADD_NEW_VAR)
        # create_at() records type usage in a machine optionVar: keep the developer's.
        self.usage = (cmds.optionVar(q=catalog.USAGE_VAR)
                      if cmds.optionVar(exists=catalog.USAGE_VAR) else None)
        _maya.fresh_scene()
        cmds.flushUndo()
        self.bridge = Bridge()
        self.messages = []
        self.bridge.statusChanged.connect(self.messages.append)

    def tearDown(self):
        self.bridge._flush_timer.stop()
        cmds.optionVar(remove=ADD_NEW_VAR)
        if self.usage is None:
            cmds.optionVar(remove=catalog.USAGE_VAR)
        else:
            cmds.optionVar(stringValue=(catalog.USAGE_VAR, self.usage))

    def outside_node(self):
        """A node made the way a script makes it, reported by the scene callback."""
        u = model.uuids_of([cmds.createNode('multiplyDivide')])[0]
        self.bridge._on_scene_events(event(added=[u]))
        return u

    def test_default_on_adds_outside_nodes(self):
        self.assertIs(self.bridge.add_new, True)
        u = self.outside_node()
        self.assertIn(u, self.bridge.infos)

    def test_off_skips_outside_nodes(self):
        self.bridge.set_add_new(False)
        u = self.outside_node()
        self.assertNotIn(u, self.bridge.infos)
        self.assertEqual(self.messages, [])

    def test_pref_persists(self):
        self.bridge.set_add_new(False)
        b = Bridge()
        self.assertIs(b.add_new, False)
        b._flush_timer.stop()
        self.bridge.set_add_new(True)
        b = Bridge()
        self.assertIs(b.add_new, True)
        b._flush_timer.stop()

    def test_own_create_still_lands_when_off(self):
        self.bridge.set_add_new(False)
        name = self.bridge.create_at('multiplyDivide', (0, 0))
        u = model.uuids_of([name])[0]
        self.assertIn(u, self.bridge.infos)
        self.bridge._on_scene_events(event(added=[u]))     # the callback's late flush
        self.assertIn(u, self.bridge.infos)

    def test_undo_of_delete_restores_when_off(self):
        name = cmds.createNode('multiplyDivide')
        u = model.uuids_of([name])[0]
        self.bridge.add_nodes([u], arrange_new=False)
        self.bridge.set_add_new(False)
        cmds.delete(name)
        self.bridge._on_scene_events(event(removed=[u]))
        self.assertNotIn(u, self.bridge.infos)
        self.assertIn(u, self.bridge.tab['gone'])
        cmds.undo()
        self.bridge._on_scene_events(event(history=True))
        self.assertIn(u, self.bridge.infos)

    def test_independent_of_sync(self):
        self.bridge.set_sync(False)
        u = self.outside_node()
        self.assertNotIn(u, self.bridge.infos)
        self.assertIs(self.bridge.add_new, True)
        self.bridge.set_sync(True)
        self.assertIs(self.bridge.add_new, True)
        u = self.outside_node()
        self.assertIn(u, self.bridge.infos)


if __name__ == '__main__':
    unittest.main()
