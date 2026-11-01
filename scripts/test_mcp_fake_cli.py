#!/usr/bin/env python3
"""Private fake CLI for test_mcp.py. Contains no device or clipboard calls."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_mcp import snapshot

config = json.loads(Path(os.environ['MCP_FIXTURE_CONFIG']).read_text())
log = Path(config['log'])


def record(event, **fields):
    with log.open('a') as out:
        out.write(json.dumps({'event': event, 'pid': os.getpid(), 'time': time.monotonic(),
            'ppid': os.getppid(), 'pgid': os.getpgrp(), 'start': str(os.getpid())+'-fixture',
            'born': time.time(), 'nonce': os.environ.get('IPB_MCP_REQUEST_NONCE'), **fields})+'\n')


def term(_sig, _frame):
    record('term')
    if config.get('ignoreTerm'):
        return
    time.sleep(config.get('termDelay', 0))
    sys.exit(5)


signal.signal(signal.SIGTERM, term)
if '--child' in sys.argv:
    record('child', pgid=os.getpgrp())
    time.sleep(30)
    sys.exit(0)
if '--middle' in sys.argv:
    subprocess.Popen([sys.executable, __file__, '--child'], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sys.exit(0)

args = sys.argv[1:]
device = args[1] if args[:1] == ['-s'] else None
if device and config.get('requireDeviceCase'):
    assert device == config['requireDeviceCase'], 'fake enumeration UUID comparison is case-sensitive'
name = 'devices' if args == ['devices'] else args[2]
if name == 'ui':
    name = 'observe' if args[3] == '--deep' else args[3].replace('-', '_')
mode = config.get('perTool', {}).get(name, config.get('mode', 'success'))
record('start', device=device, tool=name)
if mode in ('detached-pipe', 'detached-eof', 'group-child', 'grandchild-eof'):
    child = subprocess.Popen([sys.executable, __file__, '--middle' if mode == 'grandchild-eof' else '--child'],
                             start_new_session=mode != 'group-child',
                             stdout=subprocess.DEVNULL if mode == 'detached-eof' else None,
                             stderr=subprocess.DEVNULL if mode == 'detached-eof' else None)
    # Synchronize fixture child startup; no PID assumptions in assertions.
    until = time.monotonic() + 3
    while time.monotonic() < until:
        if any(json.loads(line)['event'] == 'child' for line in log.read_text().splitlines()):
            break
        time.sleep(0.01)
    sys.exit(0)
if mode == 'sleep':
    time.sleep(30)
if mode == 'delay':
    time.sleep(config.get('delay', 0.15))
if mode == 'signal':
    os.kill(os.getpid(), signal.SIGKILL)
if mode == 'invalid':
    print('{broken')
    sys.exit(0)
if mode == 'flood':
    sys.stdout.write('x' * (3 * 1024 * 1024))
    sys.stdout.flush()
    time.sleep(30)
if mode == 'stderr':
    print('SYNTHETIC-PRIVATE-FIXTURE-TEXT', file=sys.stderr)
if mode.startswith('exit-'):
    sys.exit(int(mode[5:]))
if mode == 'receipt':
    assert os.environ.get('IPB_ERROR_FORMAT') == 'json'
    print(json.dumps({'kind': 'ipb.error', 'contractVersion': 1, 'operation': 'ui.'+name.replace('_', '-'),
        'phase': 'validation', 'exitCode': 1, 'error': {'type': 'ValueError', 'message': 'fake precondition'},
        'action': {'state': 'not-sent', 'native': 'unknown', 'childExitCode': None},
        'retrySafe': True, 'result': None}))
    sys.exit(1)
if name == 'devices':
    print('11111111-2222-3333-4444-555555555555\tFake\t27.0\twired\tconnected\tiPhone')
elif name == 'observe':
    raw = snapshot(device)
    if mode == 'incomplete':
        raw['snapshotId'] = None
    print(json.dumps(raw))
elif name in ('locate', 'wait', 'press', 'input', 'scroll_to_visible', 'alert_press'):
    raw = {'schemaVersion': 1, 'deviceIdentifier': device, 'atomic': False}
    if name == 'press' or name == 'alert_press':
        raw['action'] = {'nativeAccepted': True, 'effectVerified': False}
    if name == 'input':
        raw.update(action={'childExitCode': 0}, postconditionVerified=True)
    if name == 'scroll_to_visible':
        raw.update(nativeResult=False, postconditionVerified=True)
    if name == 'wait':
        raw.update(status='satisfied', snapshotId='wait-snapshot', matchCount=1)
    print(json.dumps(raw))
else:
    print('fake transport accepted')
record('end', device=device, tool=name)
