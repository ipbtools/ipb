#!/usr/bin/env python3
"""Host-only CLI contract tests: no real device command or clipboard access."""
import json
import os
from pathlib import Path
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
if len(a)>4 and a[4]=='cd_paste': sys.exit(23 if mode=='paste-fail' else 0)
if a[:3]==['device','pasteboard','copy']:
    if mode=='copy-fail': sys.exit(1)
    (p/'clipboard').write_bytes(sys.stdin.buffer.read()); sys.exit(0)
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
print("device CLI contracts passed (host fixtures; no device)")
