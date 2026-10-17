"""NodeX installer.

Drag this file into a Maya viewport, or run it in the Script Editor (Python tab:
File > Source Script). It installs NodeX as a Maya module for the current user:

    <maya app dir>/modules/NodeX.mod
    <maya app dir>/modules/NodeX/scripts/nodex/...       the editor
    <maya app dir>/modules/NodeX/scripts/userSetup.py    adds Windows > NodeX Node Editor

and puts a NodeX button on the current shelf. Your own userSetup.py is not touched.
Installing again replaces the previous version. To remove NodeX:

    import nodex.startup; print(nodex.startup.uninstall())
"""
import os
import re
import shutil
import sys

from maya import cmds

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "NodeX")
NAME = "NodeX"
FIRST = 2025        # oldest Maya with PySide6; 2022-2024 stay on NodeX 1.0.0
TESTED = 2026       # newest Maya this release was tested on; newer ones get a warning


def _version():
    with open(os.path.join(SOURCE, "scripts", "nodex", "startup.py"), encoding="utf-8") as f:
        m = re.search(r'^VERSION = "([^"]+)"', f.read(), re.M)
    return m.group(1) if m else "1.0.0"


def _unload():
    """Close a running NodeX and forget its modules, so the new copy is the one imported."""
    if "nodex" in sys.modules:
        try:
            sys.modules["nodex"].close()
        except Exception:
            pass
    for name in list(sys.modules):
        if name == "nodex" or name.startswith("nodex."):
            del sys.modules[name]


def mod_text(existing, major, version, dest):
    """NodeX.mod text gated to Maya 2025+: one line per year from FIRST to the running `major`,
    plus any 2025+ year an earlier install (e.g. from a newer Maya) already listed. Ungated
    lines of the 1.0.0 format are dropped, so Maya 2022-2024 never load the PySide6 code."""
    years = set(range(FIRST, major + 1))
    for m in re.finditer(r"^\+\s+MAYAVERSION:(\d{4})\s+%s\b" % NAME, existing or "", re.M):
        if int(m.group(1)) >= FIRST:
            years.add(int(m.group(1)))
    return "".join("+ MAYAVERSION:%d %s %s %s\n" % (y, NAME, version, dest) for y in sorted(years))


def install():
    api = int(cmds.about(apiVersion=True))
    if api < FIRST * 10000:
        raise RuntimeError("This NodeX needs Maya %d or newer (PySide6); this is Maya %s. "
                           "For Maya 2022-2024 use NodeX 1.0.0." % (FIRST, cmds.about(version=True)))
    major = api // 10000
    if not os.path.isdir(os.path.join(SOURCE, "scripts", "nodex")):
        raise RuntimeError("NodeX folder not found next to install.py: unpack the whole archive")
    version = _version()
    modules = os.path.join(cmds.internalVar(userAppDir=True), "modules")
    dest = os.path.join(modules, NAME).replace("\\", "/")
    _unload()
    if not os.path.isdir(modules):
        os.makedirs(modules)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    shutil.copytree(SOURCE, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    mod_file = os.path.join(modules, NAME + ".mod")
    existing = None
    if os.path.isfile(mod_file):
        with open(mod_file, encoding="utf-8", errors="replace") as f:
            existing = f.read()
    with open(mod_file, "w", encoding="utf-8") as f:
        f.write(mod_text(existing, major, version, dest))

    # This session: the module path is read at startup only, so add it by hand once.
    scripts = os.path.join(dest, "scripts")
    sys.path[:] = [p for p in sys.path if os.path.normcase(os.path.normpath(p)) !=
                   os.path.normcase(os.path.normpath(scripts))]
    sys.path.insert(0, scripts)
    import nodex.startup
    nodex.startup.run()
    nodex.startup.add_shelf_button()
    msg = ("NodeX %s installed to %s. Open it from the shelf button or Windows > NodeX Node "
           "Editor; Help > Keys lists the shortcuts." % (version, dest))
    if major > TESTED:
        msg += ("\n\nWarning: this is Maya %s, which NodeX %s has not been tested on (tested on "
                "Maya %d). Please report anything that does not work."
                % (cmds.about(version=True), version, TESTED))
    print(msg)
    try:
        cmds.confirmDialog(title="NodeX", message=msg, button=["OK"])
    except RuntimeError:
        pass
    return dest


def onMayaDroppedPythonFile(*_):
    install()


if __name__ == "__main__":
    install()
