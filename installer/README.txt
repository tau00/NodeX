NodeX -- a node editor for Maya
================================

Requirements: Windows, Maya 2025 or newer (PySide6), tested on Maya 2026.
Maya 2022-2024: use NodeX 1.0.0. Installing 2.0.0 removes NodeX from those versions
on the same machine (the module is only loaded by Maya 2025+). The two releases share one
install, so only one can be installed per user: running the 1.0.0 installer afterwards
replaces 2.0.0 for every Maya version.

Install
-------
1. Unpack the whole archive anywhere (keep install.py next to the NodeX folder).
2. Drag install.py into a Maya viewport.
   (Or: Script Editor > File > Source Script... > install.py.)
3. Done: a NodeX button appears on the current shelf, and Windows > NodeX Node Editor.

The editor is installed as a Maya module for the current user:
    Documents/maya/modules/NodeX.mod
    Documents/maya/modules/NodeX/
Your own userSetup.py is not changed. Installing again replaces the old version.
NodeX.mod enables the module only for Maya 2025 up to the Maya you installed from: after
installing a newer Maya, drag install.py into it once.

Maya may ask once whether to allow the module's userSetup.py at the next start
(Security preferences). Allow it, otherwise the Windows menu item is missing; the shelf
button works either way.

Open from Python
----------------
    import nodex; nodex.show()

Keys
----
Help > Keys inside the editor, or HOTKEYS.md in this archive.

Uninstall
---------
    import nodex.startup; print(nodex.startup.uninstall())
then restart Maya.

Data
----
Graph tabs, positions and frames are saved in the scene (network node nodexBoard).
Presets: Documents/maya/nodex_presets/*.json -- copy this folder to move presets between machines.
