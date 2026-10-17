"""Compile the Qt Quick shaders: nodex/qml/shaders/<name>.frag -> <name>.frag.qsb

Qt 6 reads ShaderEffect.fragmentShader as a precompiled .qsb (one file carrying the GLSL, HLSL
and MSL variants every RHI backend needs), so the sources are compiled here with the qsb.exe
that ships in Maya's devkit and the results are committed: neither users nor build.py need a
Qt SDK. stamp.json records each source's sha256 and the qsb version, which --check compares
by content (git keeps no file times, so a fresh clone must still pass).

Usage:
  python tools/build_shaders.py            compile every shader, rewrite stamp.json
  python tools/build_shaders.py --check    exit 1 if a .qsb is missing or older than its source
qsb.exe: %QSB%, else %MAYA_LOCATION%/devkit/Qt/bin/qsb.exe, else Maya 2026's default install.
"""
import glob
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
SHADERS = os.path.join(HERE, "nodex", "qml", "shaders")
STAMP = os.path.join(SHADERS, "stamp.json")
TARGETS = ["--glsl", "100 es,120,150", "--hlsl", "50", "--msl", "12"]
DEFAULT_QSB = "C:/Program Files/Autodesk/Maya2026/devkit/Qt/bin/qsb.exe"


def qsb_exe():
    if os.environ.get("QSB"):
        return os.environ["QSB"]
    if os.environ.get("MAYA_LOCATION"):
        path = os.path.join(os.environ["MAYA_LOCATION"], "devkit", "Qt", "bin", "qsb.exe")
        if os.path.isfile(path):
            return path
    return DEFAULT_QSB


def sources():
    return sorted(glob.glob(os.path.join(SHADERS, "*.frag")))


def sha256(path):
    with open(path, "rb") as f:   # line endings normalised: a checkout may turn LF into CRLF
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def read_stamp():
    try:
        with open(STAMP, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"qsb": None, "sources": {}}


def stale():
    """Names of shaders whose .qsb is missing or was not built from the current source."""
    built = read_stamp()["sources"]
    out = []
    for src in sources():
        name = os.path.basename(src)
        if not os.path.isfile(src + ".qsb") or built.get(name) != sha256(src):
            out.append(name)
    return out


def build():
    exe = qsb_exe()
    if not os.path.isfile(exe):
        sys.exit("qsb.exe not found at %s (set QSB or MAYA_LOCATION)" % exe)
    version = subprocess.run([exe, "--version"], capture_output=True, text=True,
                             check=True).stdout.strip()
    stamp = {"qsb": version, "sources": {}}
    for src in sources():
        name = os.path.basename(src)
        p = subprocess.run([exe] + TARGETS + ["-o", src + ".qsb", src],
                           capture_output=True, text=True)
        if p.returncode:
            sys.exit("%s failed:\n%s%s" % (name, p.stdout, p.stderr))
        stamp["sources"][name] = sha256(src)
        print("%s.qsb" % name)
    with open(STAMP, "w", encoding="utf-8", newline="\n") as f:
        json.dump(stamp, f, indent=2, sort_keys=True)
        f.write("\n")
    print("%d shader(s), %s" % (len(stamp["sources"]), version))


if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        bad = stale()
        for name in bad:
            print("stale: %s (run python tools/build_shaders.py)" % name)
        sys.exit(1 if bad else 0)
    build()
