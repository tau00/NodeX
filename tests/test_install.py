"""installer/install.py: the version-gated NodeX.mod, so Maya 2022-2024 never load 2.0.0."""
import importlib.util
import os
import unittest

import _maya
_maya.start()

_spec = importlib.util.spec_from_file_location(
    "nodex_install", os.path.join(_maya.ROOT, "installer", "install.py"))
install = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install)

DEST = "C:/Users/u/Documents/maya/modules/NodeX"


def line(year, version="2.0.0", dest=DEST):
    return "+ MAYAVERSION:%d NodeX %s %s\n" % (year, version, dest)


class ModTextTest(unittest.TestCase):
    def test_fresh_install_from_2026(self):
        self.assertEqual(install.mod_text(None, 2026, "2.0.0", DEST), line(2025) + line(2026))

    def test_reinstall_from_2026_keeps_a_newer_year(self):
        old = line(2025) + line(2026) + line(2027, "2.0.0", "C:/old/NodeX")
        self.assertEqual(install.mod_text(old, 2026, "2.0.0", DEST),
                         line(2025) + line(2026) + line(2027))

    def test_upgrade_drops_the_ungated_1_0_0_line(self):
        old = "+ NodeX 1.0.0 C:/Users/u/Documents/maya/modules/NodeX\n"
        self.assertEqual(install.mod_text(old, 2026, "2.0.0", DEST), line(2025) + line(2026))

    def test_install_from_2027(self):
        self.assertEqual(install.mod_text("", 2027, "2.0.0", DEST),
                         line(2025) + line(2026) + line(2027))

    def test_years_before_2025_are_never_listed(self):
        old = "+ MAYAVERSION:2024 NodeX 1.0.0 C:/x\n" + line(2026)
        self.assertEqual(install.mod_text(old, 2025, "2.0.0", DEST), line(2025) + line(2026))


if __name__ == "__main__":
    unittest.main()
