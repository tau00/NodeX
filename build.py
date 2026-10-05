"""Build the NodeX install archive: dist/NodeX-<version>.zip

    python build.py

Archive layout (unpack anywhere, drag install.py into Maya):

    NodeX-<version>/install.py, README.txt, HOTKEYS.md
    NodeX-<version>/NodeX/scripts/userSetup.py
    NodeX-<version>/NodeX/scripts/nodex/...   (package + palette.json, no tests helpers)
"""
import os
import re
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
SKIP_FILES = {"fixture.py"}                       # test rig only


def version():
    with open(os.path.join(ROOT, "nodex", "startup.py"), encoding="utf-8") as f:
        return re.search(r'^VERSION = "([^"]+)"', f.read(), re.M).group(1)


def _ignore(folder, names):
    return [n for n in names if n == "__pycache__" or n.endswith(".pyc") or n in SKIP_FILES]


def build():
    ver = version()
    name = "NodeX-%s" % ver
    stage = os.path.join(DIST, name)
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    scripts = os.path.join(stage, "NodeX", "scripts")
    shutil.copytree(os.path.join(ROOT, "nodex"), os.path.join(scripts, "nodex"), ignore=_ignore)
    shutil.copy2(os.path.join(ROOT, "palette.json"), os.path.join(scripts, "nodex", "palette.json"))
    shutil.copy2(os.path.join(ROOT, "installer", "userSetup.py"), scripts)
    for f in ("install.py", "README.txt"):
        shutil.copy2(os.path.join(ROOT, "installer", f), stage)
    shutil.copy2(os.path.join(ROOT, "HOTKEYS.md"), stage)

    archive = os.path.join(DIST, name + ".zip")
    if os.path.isfile(archive):
        os.remove(archive)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(stage):
            for f in sorted(files):
                full = os.path.join(base, f)
                z.write(full, os.path.relpath(full, DIST))
    return archive, stage


if __name__ == "__main__":
    path, stage = build()
    n = sum(len(f) for _, _, f in os.walk(stage))
    print("%s (%d files, %.0f KB)" % (path, n, os.path.getsize(path) / 1024.0))
    sys.exit(0)
