"""Bind the redesign's colours to Maya's own colour prefs file.

Reads the Node Editor entries of userRGBColors2.mel, derives the styled value for each
(same hue, lightness and saturation pulled into a band that reads on the dark node plate,
relative lightness preserved so Maya's light/dark pairs stay distinguishable), then rewrites
palette.json (read by nodex/theme.py).

Usage:
  python tools/build_palette.py [path/to/userRGBColors2.mel]
Default path: %USERPROFILE%/Documents/maya/2024/prefs/userRGBColors2.mel
"""
import colorsys
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
DEFAULT_SRC = os.path.join(os.path.expanduser("~"), "Documents", "maya", "2024", "prefs", "userRGBColors2.mel")


def hexv(rgb):
    return "#%02X%02X%02X" % tuple(int(round(c * 255)) for c in rgb)


def style_port(rgb):
    h, l, s = colorsys.rgb_to_hls(*rgb)
    if s < 0.08:  # greys (and Maya's black "ambiguous") become a readable neutral
        return hexv(colorsys.hls_to_rgb(h, min(max(0.35 + 0.6 * l, 0.55), 0.82), s))
    l = min(max(0.35 + 0.6 * l, 0.50), 0.80)
    s = min(max(s, 0.25), 0.60)
    return hexv(colorsys.hls_to_rgb(h, l, s))


def style_node(rgb):
    h, l, s = colorsys.rgb_to_hls(*rgb)
    l = min(max(l, 0.25), 0.34)  # keeps white title text readable on every header
    return hexv(colorsys.hls_to_rgb(h, l, s * 0.85))


def parse(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    pat = r"displayRGBColor -c nodeEditor(\w+) ([\d.]+) ([\d.]+) ([\d.]+)"
    home = os.path.expanduser("~").replace("\\", "/")
    out = {"source": path.replace("\\", "/").replace(home, "~"), "attr": {}, "node": {}, "canvas": {}}
    for m in re.finditer(pat, text):
        key, rgb = m.group(1), tuple(float(v) for v in m.groups()[1:])
        if key.endswith("Attribute"):
            out["attr"][key[:-9]] = {"maya": hexv(rgb), "styled": style_port(rgb)}
        elif key.endswith("Node"):
            out["node"][key[:-4]] = {"maya": hexv(rgb), "styled": style_node(rgb)}
        else:
            out["canvas"][key] = {"maya": hexv(rgb)}
    if not out["attr"]:
        sys.exit("no nodeEditor*Attribute entries in %s" % path)
    out["sel"] = parse_selection(os.path.dirname(path), text)
    return out


def parse_selection(prefs, rgb_text):
    """Lead = the last selected object (displayRGBColor lead); active = the rest of the selection,
    an index colour (displayColor -active active N in userColors.mel, resolved via paletteColors.mel)."""
    sel = {}
    m = re.search(r"displayRGBColor -c lead ([\d.]+) ([\d.]+) ([\d.]+)", rgb_text)
    if m:
        c = hexv(tuple(float(v) for v in m.groups()))
        sel["lead"] = {"maya": c, "styled": c}
    try:
        idx = re.search(r"displayColor -c -active active (\d+)",
                        open(os.path.join(prefs, "userColors.mel"), encoding="utf-8", errors="replace").read()).group(1)
        m = re.search(r"colorIndex %s ([\d.]+) ([\d.]+) ([\d.]+)" % idx,
                      open(os.path.join(prefs, "paletteColors.mel"), encoding="utf-8", errors="replace").read())
        c = hexv(tuple(float(v) for v in m.groups()))
        sel["active"] = {"maya": c, "styled": c, "index": int(idx)}
    except (OSError, AttributeError):
        pass
    # Maya defaults when a prefs file lacks the entry
    sel.setdefault("lead", {"maya": "#43FFA3", "styled": "#43FFA3"})
    sel.setdefault("active", {"maya": "#FFFFFF", "styled": "#FFFFFF", "index": 16})
    return sel


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    pal = parse(src)
    json.dump(pal, open(os.path.join(HERE, "palette.json"), "w", encoding="utf-8"), indent=2)
    print("palette: %d attribute types, %d node categories from %s" % (len(pal["attr"]), len(pal["node"]), src))


if __name__ == "__main__":
    main()
