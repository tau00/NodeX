"""Board.qml loads and binds to the real Bridge (the crash of the first live nodex.show()).

Root cause, found by bisecting headless loads: a PySide 5.15 signal with 3+ UNNAMED parameters
(any types) crashes QQmlBoundSignalExpression while `Connections { function onX(a, b, c) }` is
bound -- ACCESS_VIOLATION inside QQuickWidget.setSource in ~25% of loads. Named parameters
(`Signal(..., arguments=[...])`) fix it. The name check below is the deterministic guard;
the repeated loads catch the random crash itself.

The scene half (fixture -> node infos, wires) runs here under maya.standalone; the QML half
runs in separate mayapy processes (_qml_probe.py) because a QApplication cannot live in a
process where maya.standalone has started (global leaf mayapy-headless-test-harness).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

import _maya

_maya.start()

from PySide6 import QtCore  # noqa: E402

from nodex import bridge, fixture, model  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "_qml_probe.py")
LOADS = 6


def _snapshot():
    _maya.fresh_scene()
    names = fixture.build()
    uuids = model.uuids_of(list(names.values()))
    infos = {}
    for i, u in enumerate(uuids):
        info = model.describe(u, model.NodeView(), "connected")
        info["x"], info["y"] = 60.0 + 260.0 * (i % 4), 60.0 + 220.0 * (i // 4)
        infos[u] = info
    return {"nodes": [infos[u] for u in uuids], "wires": model.wires(uuids, infos),
            "sel": [uuids[0]], "lead": uuids[0]}


INJECTION = "Injection of parameters into signal handlers is deprecated"
# Qt messages a probe may log and still pass:
QT_NOISE = (
    "QFontDatabase: Cannot find font directory",   # offscreen platform: Maya ships no lib/fonts
    "Cannot open: qrc:/",                          # Maya's :/ icons exist only in the GUI (see below)
)


def _qt_noise(messages):
    """The probe's Qt messages minus the allowed noise; a parameter-injection deprecation
    always stays (a handler reading `mouse` / `event` without declaring it)."""
    return [m for m in messages if INJECTION in m or not any(n in m for n in QT_NOISE)]


def _probe(path):
    env = dict(os.environ)
    env.pop("QT_QPA_PLATFORM", None)
    p = subprocess.run([sys.executable, PROBE, path], env=env, capture_output=True,
                       text=True, timeout=120)
    for line in p.stdout.splitlines():
        if line.startswith("NODEX_PROBE "):
            return json.loads(line[len("NODEX_PROBE "):])
    return {"crash": p.returncode, "tail": (p.stdout + p.stderr)[-2000:]}


class QmlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = _snapshot()
        fd, cls.path = tempfile.mkstemp(prefix="nodex_snap_", suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(cls.snap, f)
        with ThreadPoolExecutor(LOADS) as ex:
            cls.runs = list(ex.map(_probe, [cls.path] * LOADS))

    @classmethod
    def tearDownClass(cls):
        os.remove(cls.path)

    def test_signals_name_their_parameters(self):
        mo = bridge.Bridge.staticMetaObject
        for i in range(mo.methodOffset(), mo.methodCount()):
            m = mo.method(i)
            if m.methodType() != QtCore.QMetaMethod.MethodType.Signal:
                continue
            names = [bytes(n).decode() for n in m.parameterNames()]
            self.assertTrue(all(names), "Bridge.%s has unnamed parameters %s"
                            % (bytes(m.name()).decode(), names))

    def test_variant_slots_unwrap_js_values(self):
        # A JS array/object reaches a "QVariant" slot as QJSValue; iterating it raises, and the
        # exception aborts the calling QML function half-way (a value drag whose valueFinish never
        # ran froze its node's rows). Every such slot must pass it through _js(), itself or in a
        # helper it calls.
        import inspect
        import re
        mo = bridge.Bridge.staticMetaObject

        def unwraps(fn, depth=0):
            src = inspect.getsource(fn)
            if "_js(" in src:
                return True
            if depth > 1:
                return False
            for h in set(re.findall(r"self\.(_\w+)\(", src)):
                f = getattr(bridge.Bridge, h, None)
                if callable(f) and unwraps(f, depth + 1):
                    return True
            return False
        checked = []
        for i in range(mo.methodOffset(), mo.methodCount()):
            m = mo.method(i)
            if m.methodType() != QtCore.QMetaMethod.MethodType.Slot:
                continue
            if b"QVariant" not in [bytes(t) for t in m.parameterTypes()]:
                continue
            name = bytes(m.name()).decode()
            checked.append(name)
            self.assertTrue(unwraps(getattr(bridge.Bridge, name)),
                            "Bridge.%s takes a QVariant without _js()" % name)
        self.assertIn("commitValues", checked)

    def test_help_keys_match_hotkeys_md(self):
        # Help > Keys is rendered from nodex/keys.py; HOTKEYS.md must carry every row.
        from nodex import keys
        with open(os.path.join(HERE, "..", "HOTKEYS.md"), encoding="utf-8") as f:
            md = f.read()
        for title, rows in keys.SECTIONS:
            self.assertIn("## " + title, md)
            for k, action in rows:
                self.assertIn("| %s | %s |" % (k, action), md)
        from nodex import theme
        self.assertIn("Ctrl+J", keys.html(theme.CHROME))

    def test_board_loads_every_time(self):
        for r in self.runs:
            self.assertNotIn("crash", r, r.get("tail"))
            self.assertTrue(r["status"].endswith("Ready"), r)
            self.assertEqual(r["errors"], [])
            # Maya's :/ icon resources are registered only by the GUI; a type without a local
            # copy in nodex/icons is expected to miss here and nowhere else.
            noise = [w for w in r["warnings"] if "Cannot open: qrc:/" not in w]
            self.assertEqual(noise, [])
            self.assertEqual(_qt_noise(r["qtMessages"]), [])

    def test_real_nodes_become_delegates(self):
        r = self.runs[0]
        # registerNode bumps nodesVersion once per Node delegate built from the snapshot.
        self.assertGreaterEqual(r["nodeItems"], len(self.snap["nodes"]))
        self.assertEqual(r["frame"], [900, 600])

    def test_js_containers_reach_variant_slots(self):
        self.assertEqual(self.runs[0]["jsCalls"], {"disconnectWires": "ok", "moveNodes": "ok", "bundleTip": "ok"})

    def test_pan_during_smooth_zoom_does_not_jump(self):
        r = self.runs[0]
        self.assertEqual(r["zoomAfterPan"], 2.0)
        self.assertAlmostEqual(r["panJump"], 0.0, places=2)

    def test_signal_arguments_reach_qml(self):
        r = self.runs[0]
        self.assertEqual(r["view"], [11.0, 22.0, 1.5])
        self.assertEqual(r["wireCount"], 1)
        self.assertEqual(r["lead"], self.snap["lead"])

    def test_connection_focus_signal_and_escape(self):
        r = self.runs[0]
        self.assertEqual(set(r['connectionFocus']['nodes']), {n['id'] for n in self.snap['nodes'][:2]})
        self.assertEqual(r['connectionFocus']['wires'], [self.snap['wires'][0]['id']])
        self.assertTrue(r['focusCleared'])

    def test_keyboard_and_lazy_mouse_gestures(self):
        env = dict(os.environ)
        env.pop('QT_QPA_PLATFORM', None)
        proc = subprocess.run([sys.executable, os.path.join(HERE, '_hotkey_probe.py'), self.path],
                              env=env, capture_output=True, text=True, timeout=60)
        line = next((s for s in proc.stdout.splitlines() if s.startswith('NODEX_KEYS ')), None)
        self.assertIsNotNone(line, (proc.stdout + proc.stderr)[-3000:])
        result = json.loads(line[len('NODEX_KEYS '):])
        self.assertEqual(result['warnings'], [])
        self.assertEqual(_qt_noise(result['qtMessages']), [])
        self.assertEqual(result['keyboard'], [['copy'], ['paste', 700, 450], ['duplicate'],
                                              ['link', False], ['link', True]])
        self.assertEqual(result['host'], [], result)
        a, b = [n['id'] for n in self.snap['nodes'][:2]]
        self.assertEqual(result['gestures'], [['lazy', a, b, False], ['lazy', a, b, True]])
        self.assertEqual(result['cancelled'], [])
        self.assertTrue(result['typing'])
        self.assertEqual(result['typingCalls'], [])
        self.assertTrue(result['fanoutStarted'], result)
        self.assertEqual(result['fanoutCancelled'], [])
        self.assertEqual(len(result['fanout']), 1, result)
        call = result['fanout'][0]
        self.assertEqual(call[:3], ['fanout', result['fanoutSource']['nid'], result['fanoutSource']['key']])
        actual = [(t['nid'], t['key']) for t in call[3]]
        self.assertEqual(len(actual), len(set(actual)))
        self.assertTrue({(t['nid'], t['key']) for t in result['fanoutExpected']}.issubset(set(actual)), result)
        self.assertEqual(call[3], result['fanoutPreview'])

    def test_shaders_compile_on_d3d11_and_opengl(self):
        # The probe needs the real `windows` platform (offscreen never compiles a shader), so a
        # desktop session. A shader missing its HLSL keeps `status` Compiled on D3D11 and only
        # shows as a pipeline message and an effect that draws nothing; a bad .qsb is `Error`.
        # Only the first instance of a shader reports Compiled: the others hit Qt's shader
        # cache and stay Uncompiled.
        for backend, api in (("d3d11", "Direct3D11"), ("opengl", "OpenGL")):
            env = dict(os.environ, QSG_RHI_BACKEND=backend)
            proc = subprocess.run([sys.executable, os.path.join(HERE, "_shader_probe.py"), self.path],
                                  env=env, capture_output=True, text=True, timeout=60)
            line = next((s for s in proc.stdout.splitlines() if s.startswith("NODEX_SHADERS ")), None)
            self.assertIsNotNone(line, (proc.stdout + proc.stderr)[-3000:])
            r = json.loads(line[len("NODEX_SHADERS "):])
            self.assertEqual(r["api"], api, r)
            self.assertEqual(r["errors"], [], r)
            self.assertEqual(r["qtMessages"], [], r)
            for name in ("gridShader", "greekShader"):
                states = [s["status"] for s in r["status"][name]]
                self.assertIn("Compiled", states, (backend, name, r["status"][name]))
                self.assertEqual(set(states) - {"Compiled", "Uncompiled"}, set(),
                                 (backend, name, r["status"][name]))
                self.assertTrue(r["draws"][name], (backend, name))

    def test_inbetween_context_menu_attribute_choice_and_cancel(self):
        proc = subprocess.run([sys.executable, os.path.join(HERE, '_inbetween_probe.py')],
                              capture_output=True, text=True, timeout=30)
        line = next((s for s in proc.stdout.splitlines() if s.startswith('NODEX_INBETWEEN ')), None)
        self.assertIsNotNone(line, (proc.stdout + proc.stderr)[-3000:])
        result = json.loads(line[len('NODEX_INBETWEEN '):])
        self.assertEqual(result['labels'], ['multiplyDivide'])
        self.assertEqual(result['searches'], ['Search...'])
        self.assertEqual(result['direct'], [['wire', 'multiplyDivide', 'input1.input1X', 'output.outputX']])
        self.assertEqual(result['groupFirst'], 'Search...')
        self.assertEqual(result['initialContexts'], [['a.outputX', 'b.input1X']])
        self.assertEqual(result['contexts'], [['a.outputX', 'b.input1X'], ['a.outputX', 'b.input1X'],
                                              ['a.outputY', 'b.input1Y']])
        self.assertEqual(len(result['groupedConnections']), 2)
        self.assertEqual(result['accepted'], [['wire', 'multiplyDivide', 'input2.input2X', 'output.outputY']])
        self.assertEqual(result['afterCancel'], result['accepted'])
        bypass_line = next((s for s in proc.stdout.splitlines() if s.startswith('NODEX_BYPASS_MENU ')), None)
        self.assertIsNotNone(bypass_line, (proc.stdout + proc.stderr)[-3000:])
        bypass = json.loads(bypass_line[len('NODEX_BYPASS_MENU '):])
        self.assertTrue(bypass['enabled'])
        self.assertEqual(bypass['deleted'], ['a'])
        self.assertTrue(bypass['disabled'])
        self.assertIn('ambiguous', bypass['reason'])


if __name__ == "__main__":
    unittest.main()
