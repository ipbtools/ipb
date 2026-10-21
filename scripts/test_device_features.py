#!/usr/bin/env python3
"""Host-only CLI contract tests: no real device command or clipboard access."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEVICE = "00000000-0000-0000-0000-000000000001"
with tempfile.TemporaryDirectory(prefix="ipb-features-") as tmp:
    directory = Path(tmp)
    stub = directory / "stub"
    stub.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p=Path(os.environ['IPB_TEST_DIR']); a=sys.argv[1:]; mode=os.environ.get('IPB_TEST_MODE','')
with (p/'calls').open('a') as f: f.write(json.dumps(a)+'\\n')
if len(a)>4 and a[4]=='cd_connected_descriptors_async_raw':
    if mode=='discovery-fail': sys.exit(3)
    print('connectedDescriptor[0] serviceID:512 string:"CoreDevice keyboard"'); sys.exit(0)
if len(a)>4 and a[4] in ('cd_paste','cd_replace_paste'):
    if a[4]=='cd_paste': sys.exit(23 if mode=='paste-fail' else 0)
    sys.exit(29 if mode=='replace-fail' else 0)
if a[:3]==['device','pasteboard','copy']:
    if mode=='copy-fail': sys.exit(1)
    (p/'clipboard').write_bytes(sys.stdin.buffer.read()); sys.exit(0)
if a[:2]==['list','devices']:
    Path(a[a.index('--json-output')+1]).write_text(json.dumps({'result':{'devices':[{'identifier':'00000000-0000-0000-0000-000000000001','hardwareProperties':{'udid':'00008110-0000000000000000'}}]}}))
    sys.exit(0)
if a[:2]==['device','info']:
    if mode=='query-fail': sys.exit(17)
    result={'displays':[{'displayId':1,'primary':True}], 'orientation':{'currentDeviceOrientation':'portrait'}, 'backlightState':'activeOn'}
    if a[2]=='details': result={'capabilities':[{'featureIdentifier':'com.apple.coredevice.feature.startaudiooutput','name':'Start Audio Output'}]}
    Path(a[a.index('--json-output')+1]).write_text('broken json' if mode=='bad-json' else json.dumps({'result':result}))
    sys.exit(0)
sys.exit(2)
''')
    stub.chmod(0o755)
    env = {**os.environ, "DEVICECTL": str(stub), "IPB_HELPER": str(stub),
           "DEVELOPER_DIR": "/unused", "IPB_TEST_DIR": tmp}
    # The public explicit fallback must not mask discovery failure in this fixture.
    env.pop("UHID_SERVICE_FALLBACK", None)

    def run(*args, mode="", expected=0):
        (directory / "calls").write_text("")
        (directory / "clipboard").unlink(missing_ok=True)
        result = subprocess.run([str(ROOT / "bin/ipb"), "-s", DEVICE, *args],
                                env={**env, "IPB_TEST_MODE": mode}, capture_output=True, text=True, timeout=10)
        assert result.returncode == expected, (args, mode, result.returncode, result.stderr)
        calls = [json.loads(line) for line in (directory / "calls").read_text().splitlines()]
        return result, calls

    for mode, code in (("discovery-fail", 3), ("copy-fail", 1)):
        _, calls = run("text", "must not paste", mode=mode, expected=code)
        assert not any("cd_paste" in call for call in calls)
        assert not (directory / "clipboard").exists()
    _, calls = run("text", "do not replay", mode="paste-fail", expected=23)
    assert sum("cd_paste" in call for call in calls) == 1
    value = "中文🙂 A1!\nsecond line\n"
    _, calls = run("text", value)
    assert (directory / "clipboard").read_bytes() == value.encode()
    assert sum(call[:3] == ["device", "pasteboard", "copy"] for call in calls) == 1
    assert sum("cd_paste" in call for call in calls) == 1

    # Replacement is explicit, carries arbitrary text only as clipboard data,
    # and submits one replace-paste transaction after that copy succeeds.
    injected = directory / "INJECTED"
    replacement = f"中文🙂 $(touch {injected}); 'quoted'\nsecond line\n"
    result, calls = run("text", "--replace-all", replacement)
    action_calls = [call for call in calls if "cd_replace_paste" in call]
    copies = [index for index, call in enumerate(calls) if call[:3] == ["device", "pasteboard", "copy"]]
    assert len(copies) == 1 and len(action_calls) == 1
    assert copies[0] < calls.index(action_calls[0])
    assert (directory / "clipboard").read_bytes() == replacement.encode()
    assert not injected.exists()
    assert result.returncode == 0
    assert not any("touch" in str(call) for call in calls)

    # Preserve the old single-argument literal form even when the data resembles
    # the new option; option interpretation requires the following text argument.
    _, calls = run("text", "--replace-all")
    assert (directory / "clipboard").read_bytes() == b"--replace-all"
    assert sum("cd_paste" in call for call in calls) == 1
    assert not any("cd_replace_paste" in call for call in calls)

    for mode, code in (("discovery-fail", 3), ("copy-fail", 1)):
        result, calls = run("text", "--replace-all", "must not replace", mode=mode, expected=code)
        assert not any("cd_replace_paste" in call for call in calls)
        assert not (directory / "clipboard").exists()
        if mode == "copy-fail":
            assert "paste was not sent" in result.stderr

    result, calls = run("text", "--replace-all", "already copied", mode="replace-fail", expected=29)
    assert (directory / "clipboard").read_bytes() == b"already copied"
    assert sum("cd_replace_paste" in call for call in calls) == 1
    assert result.stderr.count("clipboard was written") == 1
    assert "do not blindly retry" in result.stderr
    _, calls = run("text", "", expected=2)
    assert not calls
    for command in ("displays", "capabilities"):
        result, _ = run(command, "--json")
        payload = json.loads(result.stdout)
        assert payload["schemaVersion"] == 1 and payload["deviceIdentifier"] == DEVICE
        assert command in payload
        result, _ = run(command, "--json", mode="bad-json", expected=1)
        assert not result.stdout
        result, _ = run(command, "--json", mode="query-fail", expected=17)
        assert not result.stdout
        _, calls = run(command, "--unknown", expected=2)
        assert not calls
    payload = json.loads(run("capabilities", "--json")[0].stdout)
    assert [c["featureIdentifier"] for c in payload["capabilities"]] == ["com.apple.coredevice.feature.startaudiooutput"]

    # ui input must call the exact wrapper entry point selected by the caller,
    # for both a source checkout and an installed layout. A fake interpreter
    # captures the environment before any AX backend or device service runs.
    fake_python = directory / "fake-python"
    fake_python.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
Path(os.environ['IPB_TEST_CAPTURE']).write_text(json.dumps({
    'argv': sys.argv[1:], 'cli': os.environ.get('IPB_AX_CLI')}))
''')
    fake_python.chmod(0o755)
    installed_root = directory / "installed"
    (installed_root / "bin").mkdir(parents=True)
    (installed_root / "libexec").mkdir()
    shutil.copy2(ROOT / "bin/ipb", installed_root / "bin/ipb")
    (installed_root / "libexec/ipb-ax.py").write_text("# fake installed entry\n")
    for label, wrapper, expected_script in (
        ("source", ROOT / "bin/ipb", ROOT / "Sources/ipb_ax.py"),
        ("installed", installed_root / "bin/ipb", installed_root / "libexec/ipb-ax.py"),
    ):
        capture = directory / f"input-{label}.json"
        result = subprocess.run(
            [str(wrapper), "-s", DEVICE, "ui", "input", "--class", "UISearchBarTextField",
             "--text", "Battery", "--replace-all", "--json"],
            env={**env, "IPB_AX_PYTHON": str(fake_python), "IPB_TEST_CAPTURE": str(capture)},
            capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, (label, result.returncode, result.stderr)
        observed = json.loads(capture.read_text())
        assert observed["cli"] == str(wrapper.resolve()), (label, observed)
        assert observed["argv"][0] == str(expected_script.resolve()), (label, observed)
print("device CLI contracts passed (host fixtures; no device)")
