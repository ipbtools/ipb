#!/usr/bin/env python3
"""Update is a host-only command and must not resolve an attached phone."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[1]


def make_fixture(root: Path, *, homebrew: bool = False):
    root.mkdir()
    (root / "bin").mkdir()
    (root / "bin/ipb").write_bytes((SOURCE / "bin/ipb").read_bytes())
    (root / "bin/ipb").chmod(0o755)
    (root / "VERSION").write_text("0.0-test\n")
    if not homebrew:
        (root / ".git").mkdir()
    commands = root.parent / (root.name + "-commands")
    commands.mkdir()
    log = root.parent / (root.name + "-calls.jsonl")

    def stub(name, source):
        path = commands / name
        path.write_text("#!/usr/bin/env python3\n" + source)
        path.chmod(0o755)
        return path

    git = stub("git", """
import json, os, sys
with open(os.environ['CALL_LOG'], 'a') as f: f.write(json.dumps(['git', *sys.argv[1:]])+'\\n')
sys.exit(int(os.environ.get('GIT_RC', '0')))
""")
    make = stub("make", """
import json, os, sys
with open(os.environ['CALL_LOG'], 'a') as f: f.write(json.dumps(['make', *sys.argv[1:]])+'\\n')
sys.exit(int(os.environ.get('MAKE_RC', '0')))
""")
    devicectl = stub("devicectl", """
import json, os, sys
with open(os.environ['CALL_LOG'], 'a') as f: f.write(json.dumps(['devicectl', *sys.argv[1:]])+'\\n')
if '--json-output' in sys.argv:
    path=sys.argv[sys.argv.index('--json-output')+1]
    devices=[]
    for n in range(int(os.environ.get('DEVICES_COUNT', '3'))):
        devices.append({'identifier':f'00000000-0000-0000-0000-00000000000{n+1}',
          'deviceProperties':{'name':f'phone {n+1}'}, 'hardwareProperties':{'reality':'physical'},
          'connectionProperties':{'transportType':'wired','tunnelState':'connected'}})
    open(path,'w').write(json.dumps({'result':{'devices':devices}}))
""")
    brew = stub("brew", """
import json, os, sys
a=sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as f: f.write(json.dumps(['brew', *a])+'\\n')
if a[:2]==['list','--formula']: sys.exit(0)
if a[:2]==['list','--versions']: print('ipb HEAD-old'); sys.exit(0)
if a[:2]==['info','--json=v2']:
 print(json.dumps({'formulae':[{'urls':{'head':{'url':'https://example.invalid/ipb'}}}]})); sys.exit(0)
if a[:2]==['--prefix','ipb']: print(os.environ['BREW_PREFIX']); sys.exit(0)
if a and a[0]=='update': sys.exit(0)
if a and a[0]=='reinstall': sys.exit(int(os.environ.get('BREW_REINSTALL_RC','0')))
sys.exit(0)
""")
    stub("ipb", """
import json, os, sys
with open(os.environ['CALL_LOG'], 'a') as f: f.write(json.dumps(['PATH_ipb', *sys.argv[1:]])+'\\n')
print('ipb WRONG_COPY')
""")
    env = {**os.environ, "PATH": f"{commands}:{os.environ['PATH']}",
           "DEVICECTL": str(devicectl), "DEVELOPER_DIR": "/unused",
           "CALL_LOG": str(log), "GIT_CONFIG_NOSYSTEM": "1", "ZDOTDIR": str(commands)}
    (commands / ".zshenv").write_text("")
    return env, log


def run(root, env, *args, **extra):
    (root.parent / (root.name + "-calls.jsonl")).write_text("")
    result = subprocess.run([str(root / "bin/ipb"), *args], env={**env, **extra},
                            capture_output=True, text=True, timeout=15)
    log = root.parent / (root.name + "-calls.jsonl")
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    return result, calls


with tempfile.TemporaryDirectory(prefix="ipb-update-host-") as temp:
    base = Path(temp)
    source = base / "checkout"
    env, _ = make_fixture(source)
    for selector, extra in (([], {"DEVICE_ID": "", "DEVICES_COUNT": "0"}),
                            ([], {"DEVICE_ID": ""}),
                            ([], {"DEVICE_ID": "does-not-exist"}),
                            ([], {"DEVICE_ID": "ambiguous"}),
                            (["-s", "phone"], {}),
                            (["--device=not-a-phone"], {})):
        result, calls = run(source, env, *selector, "update", **extra)
        assert result.returncode == 0, (selector, result.returncode, result.stderr, calls)
        assert any(c[0] == "git" and c[1:] == ["-C", str(source.resolve()), "pull", "--ff-only"] for c in calls), calls
        assert any(c[0] == "make" and c[1:] == ["-C", str(source.resolve())] for c in calls), calls
        assert not any(c[0] == "devicectl" for c in calls), calls

    result, calls = run(source, env, "update", GIT_RC="7")
    assert result.returncode == 1 and "git pull failed" in result.stderr
    assert not any(c[0] == "make" or c[0] == "devicectl" for c in calls), calls

    homebrew = base / "homebrew"
    hb_env, _ = make_fixture(homebrew, homebrew=True)
    hb_env["BREW_PREFIX"] = str(homebrew)
    result, calls = run(homebrew, hb_env, "-s", "ambiguous", "update")
    assert result.returncode == 0, (result.returncode, result.stderr)
    assert "ipb 0.0-test" in result.stdout and "WRONG_COPY" not in result.stdout, result.stdout
    assert any(c[0] == "brew" and c[1:] == ["reinstall", "ipb"] for c in calls), calls
    assert not any(c[0] == "PATH_ipb" for c in calls), calls
    assert not any(c[0] == "devicectl" for c in calls), calls
    # Homebrew exposes an opt symlink while the executed wrapper resolves to its keg.
    opt = base / "brew-opt"
    opt.symlink_to(homebrew, target_is_directory=True)
    result, calls = run(homebrew, hb_env, "update", BREW_PREFIX=str(opt))
    assert result.returncode == 0, (result.returncode, result.stderr, calls)
    assert any(c[:2] == ["brew", "reinstall"] for c in calls), calls
    assert not any(c[0] == "devicectl" for c in calls), calls
    result, calls = run(homebrew, hb_env, "update", BREW_REINSTALL_RC="9")
    assert result.returncode == 1 and "brew reinstall failed" in result.stderr
    assert not any(c[0] == "devicectl" for c in calls), calls

    manual = base / "manual-prefix"
    manual_env, _ = make_fixture(manual, homebrew=True)
    keg = base / "other-brew-keg"
    keg.mkdir()
    manual_env["BREW_PREFIX"] = str(keg)
    result, calls = run(manual, manual_env, "update")
    assert result.returncode == 2 and "manual install" in result.stderr
    assert f'PREFIX="{manual.resolve()}"' in result.stderr
    assert not any(c[:2] == ["brew", "update"] or c[:2] == ["brew", "reinstall"] for c in calls), calls
    assert not any(c[0] == "devicectl" for c in calls), calls

print("update host-only contracts passed (source + Homebrew; no device calls)")
