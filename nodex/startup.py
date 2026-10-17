"""Entry points of an installed NodeX: Windows menu item, shelf button, uninstall.

The installer (installer/install.py) copies the package into a Maya module; the module's
userSetup.py calls `run()` deferred on every Maya start. Nothing here touches the user's own
userSetup.py: removing the module's .mod file and folder removes NodeX completely.
"""
import os
import shutil

import __main__
from maya import cmds, mel

VERSION = "2.0.0"
MODULE = "NodeX"
LABEL = "NodeX Node Editor"
COMMAND = "import nodex; nodex.show()"
WIN_MENU = "mainWindowMenu"
ITEM = "nodexWindowsMenuItem"
ICON = "nodeGrapherModeAllLarge.png"
_HOOK = "_nodex_windows_menu_post"     # original postMenuCommand, kept in __main__


def run():
    """Called from the module's userSetup.py (deferred): hook the Windows menu."""
    if cmds.about(batch=True):
        return
    add_menu()


# ---------------------------------------------------------------------------- Windows menu

def add_menu():
    """Windows is filled lazily by its MEL postMenuCommand buildViewMenu (postMenuCommandOnce:
    on the first open only). Chain that command so the NodeX item follows Node Editor whenever
    Maya (re)builds the menu, and add the item now if the menu is already built."""
    if not cmds.menu(WIN_MENU, exists=True):
        return
    if not hasattr(__main__, _HOOK):
        orig = cmds.menu(WIN_MENU, q=True, postMenuCommand=True)
        setattr(__main__, _HOOK, orig if isinstance(orig, str) else "")
    cmds.menu(WIN_MENU, e=True, postMenuCommand=_post_windows_menu)
    if cmds.menu(WIN_MENU, q=True, numberOfItems=True):
        _add_item()


def _post_windows_menu(*_):
    orig = getattr(__main__, _HOOK, "")
    if orig:
        mel.eval(orig)
    _add_item()


def _add_item():
    if cmds.menuItem(ITEM, exists=True):
        return
    kw = {"insertAfter": "wmNodeEditor"} if cmds.menuItem("wmNodeEditor", exists=True) else {}
    cmds.menuItem(ITEM, parent=WIN_MENU, label=LABEL, image=ICON, command=_show,
                  annotation="Open the NodeX node editor", **kw)


def remove_menu():
    orig = getattr(__main__, _HOOK, None)
    if orig is not None and cmds.menu(WIN_MENU, exists=True):
        # Maya's command is MEL; a string handed to cmds.menu runs as Python (NameError
        # buildViewMenu on the next open), so it is put back from MEL.
        mel.eval('menu -e -postMenuCommand "%s" %s'
                 % (orig.replace("\\", "\\\\").replace('"', '\\"'), WIN_MENU))
        delattr(__main__, _HOOK)
    if cmds.menuItem(ITEM, exists=True):
        cmds.deleteUI(ITEM, menuItem=True)


def _show(*_):
    import nodex
    nodex.show()


# ---------------------------------------------------------------------------- shelf

def _shelves():
    if cmds.about(batch=True):
        return None, []
    top = mel.eval("$_nx_shelf = $gShelfTopLevel")
    if not top or not cmds.shelfTabLayout(top, exists=True):
        return None, []
    return top, cmds.shelfTabLayout(top, q=True, childArray=True) or []


def _our_buttons(shelf):
    out = []
    for b in cmds.shelfLayout(shelf, q=True, childArray=True) or []:
        if cmds.shelfButton(b, exists=True) and \
                (cmds.shelfButton(b, q=True, docTag=True) or "") == MODULE:
            out.append(b)
    return out


def add_shelf_button():
    """One NodeX button on the current shelf (none added when any shelf already has one)."""
    top, shelves = _shelves()
    if not top:
        return None
    for s in shelves:
        found = _our_buttons(s)
        if found:
            return found[0]
    shelf = cmds.shelfTabLayout(top, q=True, selectTab=True)
    btn = cmds.shelfButton(parent=shelf, label=LABEL, annotation=LABEL, docTag=MODULE,
                           image=ICON, imageOverlayLabel="NX", sourceType="python",
                           command=COMMAND)
    mel.eval("saveAllShelves $gShelfTopLevel")
    return btn


def remove_shelf_buttons():
    top, shelves = _shelves()
    n = 0
    for s in shelves:
        for b in _our_buttons(s):
            cmds.deleteUI(b)
            n += 1
    if n:
        mel.eval("saveAllShelves $gShelfTopLevel")
    return n


# ---------------------------------------------------------------------------- uninstall

def module_dir():
    return os.path.join(cmds.internalVar(userAppDir=True), "modules")


def uninstall():
    """Remove the menu item, shelf buttons, the .mod file and the module folder."""
    try:
        import nodex
        nodex.close()
    except Exception:
        pass
    remove_menu()
    removed = remove_shelf_buttons()
    mods = module_dir()
    mod_file = os.path.join(mods, MODULE + ".mod")
    if os.path.isfile(mod_file):
        os.remove(mod_file)
    shutil.rmtree(os.path.join(mods, MODULE), ignore_errors=True)
    return "NodeX removed (%d shelf button%s); restart Maya to unload it" % (
        removed, "" if removed == 1 else "s")
