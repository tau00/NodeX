"""Shipped icons stay high-res: every nodex/icons/<type>.png and every panel toolbar icon
(nodex/icons/toolbar/<name>.png, search.png included) is at least 128 px, square, RGBA
(regenerate with tools/upscale_icons.py). Stdlib only: reads the PNG IHDR, no Maya start."""
import os
import struct
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "nodex", "icons")
MIN = 128   # 20 node units x maxZoom 2.5 x DPR 2 = 100 device px
# The toolbar draws 20 px icons at Maya's interface scale (MQtUtil.dpiScale, Qt itself unscaled):
# 30 px at 150%, 40 at 200%. 128 px art is a clean downsample at any scale and has headroom.
TOOLBAR_MIN = 128
# The 14x40 group grip is not square and stays Maya's own _200 art (native at 200%).
TOOLBAR_KEEP = {"openBar.png"}
PNG_SIG = b"\x89PNG\r\n\x1a\n"


def ihdr(path):
    """(width, height, colour type) from the PNG header."""
    with open(path, "rb") as f:
        head = f.read(26)
    if head[:8] != PNG_SIG or head[12:16] != b"IHDR":
        raise ValueError("not a PNG: %s" % path)
    w, h = struct.unpack(">II", head[16:24])
    return w, h, head[25]


class IconSizeTest(unittest.TestCase):
    def test_header_icons_are_high_res(self):
        paths = [os.path.join(ICONS, f) for f in sorted(os.listdir(ICONS)) if f.endswith(".png")]
        paths.append(os.path.join(ICONS, "toolbar", "search.png"))
        self.assertGreater(len(paths), 1)
        for p in paths:
            w, h, ctype = ihdr(p)
            name = os.path.relpath(p, ICONS)
            self.assertEqual(w, h, name)
            self.assertGreaterEqual(w, MIN, name)
            self.assertIn(ctype, (4, 6), "%s has no alpha (colour type %d)" % (name, ctype))

    def test_toolbar_icons_are_high_res(self):
        tb = os.path.join(ICONS, "toolbar")
        names = [f for f in sorted(os.listdir(tb)) if f.endswith(".png") and f not in TOOLBAR_KEEP]
        self.assertGreater(len(names), 30)
        for f in names:
            w, h, ctype = ihdr(os.path.join(tb, f))
            self.assertEqual(w, h, f)
            self.assertGreaterEqual(w, TOOLBAR_MIN, f)
            self.assertIn(ctype, (4, 6), "%s has no alpha (colour type %d)" % (f, ctype))


if __name__ == "__main__":
    unittest.main()
