"""Fixture process inspector for sandboxes denying ps/sysctl. Never used by product.

Identity comes only from the cooperating fake CLI's private log. This tests orchestration,
not Darwin process enumeration. Production inspector needs separate host acceptance.
"""
import json
import os
from pathlib import Path
import time


def events():
    config = json.loads(Path(os.environ['MCP_FIXTURE_CONFIG']).read_text())
    return [json.loads(line) for line in Path(config['log']).read_text().splitlines() if line]


def table():
    rows = {}
    for event in events():
        if event['event'] not in ('start', 'child'):
            continue
        try:
            os.kill(event['pid'], 0)
        except ProcessLookupError:
            continue
        rows[event['pid']] = {key: event[key] for key in ('pid', 'ppid', 'pgid', 'start', 'born')}
    return rows


def has_marker(pid, nonce):
    return any(e['pid'] == pid and e.get('nonce') == nonce for e in events())


def install(module):
    original = module.spawn_cli
    def spawn(*args, **kwargs):
        process = original(*args, **kwargs)
        until = time.monotonic() + 1
        while time.monotonic() < until and process.poll() is None:
            if any(e['pid'] == process.pid and e['event'] == 'start' for e in events()):
                break
            time.sleep(.005)
        return process
    module.table, module.has_marker, module.spawn_cli = table, has_marker, spawn
