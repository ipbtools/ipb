#!/usr/bin/env python3
"""MCP host fixtures only. Never runs ipb/devicectl or accesses a clipboard/phone."""
import asyncio
import copy
import ctypes
import json
import os
from pathlib import Path
import signal
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Sources'))
import ipb_mcp_adapter as adapter
import ipb_mcp
import ipb_mcp_process as processes
import test_mcp_host

DEVICE = '11111111-2222-3333-4444-555555555555'
OTHER = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'


def snapshot(device=DEVICE):
    return {'schemaVersion': 2, 'snapshotId': 'fixture-snapshot', 'deviceIdentifier': device,
            'scope': 'application-accessibility',
            'application': {'pid': 42, 'selection': 'explicit-pid'}, 'nodeCount': 2,
            'uniqueElementCount': 2, 'hierarchySource': 'AXUserTestingSnapshot',
            'attributePolicy': 'native-snapshot', 'stateScope': 'native-snapshot',
            'coordinateSpace': 'device-logical-points', 'displayFrame': None,
            'atomic': False, 'rootStable': True, 'rootStabilityScope': 'application-identity',
            'cleanup': {'subscriptionStop': 'acknowledged', 'connectionClosed': True, 'tunnelClosed': True},
            'nodes': [{'id': 'n0', 'parentId': None, 'depth': 0, 'children': ['n1']},
                      {'id': 'n1', 'parentId': 'n0', 'depth': 1, 'children': [], 'label': 'Seven',
                       'visible': False, 'frameUnavailable': 'CGRectNull',
                       'nativeAttributes': {'5003': 'UILabel'}}]}


class AdapterTests(unittest.TestCase):
    def test_actual_python_error_receipts_keep_state_and_retained_result(self):
        from test_interface_contract import invoke
        fixtures = json.loads((Path(__file__).resolve().parents[1] /
                               'docs/contracts/ax-default-v050.golden.json').read_text())
        checked = 0
        for case in fixtures['cases']:
            observed = invoke(case, fixtures['results'], 'json')
            if observed['code'] == 0:
                continue
            receipt = json.loads(observed['stdout'])
            operation = receipt['operation']
            if operation == 'unknown':
                continue
            name = 'observe' if operation == 'ui.dump' else operation[3:].replace('-', '_')
            with self.subTest(case=case['name']):
                result = adapter.adapt(name, DEVICE, observed['code'], observed['stdout'])
                self.assertEqual(result['receipt'], receipt)
                self.assertEqual(result['result'], receipt['result'])
                self.assertEqual(result['action'], receipt['action'])
                self.assertFalse(result['ok'])
            checked += 1
        self.assertGreater(checked, 0)

    def test_schema_and_argv_for_each_tool(self):
        cases = {
            'devices': {}, 'observe': {'device': DEVICE, 'pid': 42},
            'locate': {'device': DEVICE, 'identifier': 'Seven'},
            'wait': {'device': DEVICE, 'label': 'Seven', 'timeout': 15, 'waitFor': 'absent'},
            'press': {'device': DEVICE, 'label': 'Seven', 'className': 'UILabel'},
            'input': {'device': DEVICE, 'identifier': 'field', 'text': 'literal $(never-run) 中文\n', 'replaceAll': True},
            'scroll_to_visible': {'device': DEVICE, 'value': 'seven'},
            'alert_press': {'device': DEVICE, 'pid': 42, 'alertLabel': 'Paste?', 'label': 'Allow'},
            'home': {'device': DEVICE}, 'launch': {'device': DEVICE, 'bundleId': 'com.example.fixture'},
            'tap': {'device': DEVICE, 'x': 0, 'y': 1},
            'swipe': {'device': DEVICE, 'x1': 0, 'y1': 1, 'x2': 1, 'y2': 0, 'duration': 2}}
        self.assertEqual(set(cases), {t['name'] for t in adapter.TOOLS})
        for name, args in cases.items():
            with self.subTest(name=name):
                argv = adapter.command(name, args)
                self.assertIsInstance(argv, list)
                if name != 'devices':
                    self.assertEqual(argv[:2], ['-s', DEVICE])
        self.assertEqual(adapter.command('observe', cases['observe']),
                         ['-s', DEVICE, 'ui', '--deep', '--json', '--pid', '42'])
        self.assertIn('literal $(never-run) 中文\n', adapter.command('input', cases['input']))
        self.assertIn('--class', adapter.command('press', cases['press']))
        self.assertNotIn('--full-state', adapter.command('observe', cases['observe']))
        press = next(t for t in adapter.TOOLS if t['name'] == 'press')
        self.assertEqual(press['inputSchema']['anyOf'], [{'required': [key]} for key in adapter.SELECTORS])

    def test_reject_invalid_arguments_before_spawn(self):
        invalid = [('observe', {}), ('observe', {'device': '11111111'}),
                   ('observe', {'device': 'phone'}), ('observe', {'device': DEVICE, 'pid': True}),
                   ('observe', {'device': DEVICE, 'point': [0, 0]}),
                   ('press', {'device': DEVICE}), ('press', {'device': DEVICE, 'id': 'n1'}),
                   ('press', {'device': DEVICE, 'label': ''}),
                   ('press', {'device': DEVICE, 'label': 'bad\0arg'}),
                   ('press', {'device': DEVICE, 'label': '\ud800'}),
                   ('wait', {'device': DEVICE, 'label': 'Seven', 'timeout': 16}),
                   ('wait', {'device': DEVICE, 'label': 'Seven', 'timeout': float('nan')}),
                   ('input', {'device': DEVICE, 'identifier': 'field', 'text': 'x', 'replaceAll': False}),
                   ('input', {'device': DEVICE, 'identifier': 'field', 'text': '', 'replaceAll': True}),
                   ('tap', {'device': DEVICE, 'x': 1.01, 'y': 0}),
                   ('tap', {'device': DEVICE, 'x': False, 'y': 0}),
                   ('launch', {'device': DEVICE, 'bundleId': '--terminate-existing'}),
                   ('text', {'device': DEVICE, 'text': 'x'})]
        for name, args in invalid:
            with self.subTest(name=name, args=repr(args)):
                with self.assertRaises(ValueError):
                    adapter.command(name, args)

    def test_complete_compact_observe_preserves_false_and_unavailable(self):
        raw = snapshot()
        original = copy.deepcopy(raw)
        out = adapter.adapt('observe', DEVICE, 0, json.dumps(raw))
        self.assertTrue(out['ok'])
        node = out['result']['nodes'][1]
        self.assertIs(node['visible'], False)
        self.assertEqual(node['frameUnavailable'], 'CGRectNull')
        self.assertNotIn('hittable', node)
        self.assertNotIn('type', node)
        self.assertNotIn('enabled', node)
        self.assertEqual(out['businessVerified'], 'unknown')
        self.assertEqual(raw, original)

    def test_reject_partial_wrong_device_and_bad_graph(self):
        mutations = [lambda r: r.update(snapshotId=None), lambda r: r.update(deviceIdentifier=OTHER),
                     lambda r: r.update(nodeCount=3), lambda r: r.update(schemaVersion=1),
                     lambda r: r.update(rootStable=False),
                     lambda r: r['cleanup'].update(tunnelClosed=False),
                     lambda r: r['nodes'][0].update(children=['missing']),
                     lambda r: r['nodes'][1].update(children=['n0']),
                     lambda r: r['nodes'][1].update(parentId=None)]
        for mutate in mutations:
            raw = snapshot()
            mutate(raw)
            out = adapter.adapt('observe', DEVICE, 0, json.dumps(raw))
            self.assertFalse(out['ok'])
            self.assertEqual(out['error'], 'invalid-native-observation')

    def test_devices_tsv_contract(self):
        out = adapter.adapt('devices', None, 0, DEVICE+'\tFixture\t27.0 24A437\twired\tconnected\tiPhone\n')
        self.assertTrue(out['ok'])
        self.assertEqual(out['result']['devices'][0]['deviceIdentifier'], DEVICE)
        self.assertFalse(adapter.adapt('devices', None, 0, 'not a TSV')['ok'])
        self.assertEqual(adapter.adapt('devices', None, 0, '')['result']['devices'], [])

    def test_v050_family_mapping_and_abnormal_termination(self):
        for name in adapter.AX_ACTIONS:
            for code in (1, 2, 3, 5):
                out = adapter.adapt(name, DEVICE, code, '')
                self.assertEqual(out['action']['state'], 'unknown')
                self.assertFalse(out['retrySafe'])
            for code in (-15, -9, 129, 137, 143, 6, 77):
                out = adapter.adapt(name, DEVICE, code, '')
                self.assertEqual(out['action']['state'], 'unknown')
                self.assertFalse(out['retrySafe'])
            for raw in ('{broken', '[]', '{"kind":"future.error"}'):
                out = adapter.adapt(name, DEVICE, 1, raw)
                self.assertEqual(out['action']['state'], 'unknown')
            self.assertEqual(adapter.adapt(name, DEVICE, 1, '', interrupted='cancelled')['action']['state'], 'unknown')
        self.assertEqual(adapter.adapt('launch', DEVICE, 2, '')['action']['state'], 'unknown')
        self.assertEqual(adapter.adapt('tap', DEVICE, 3, '')['action']['state'], 'not-sent')
        self.assertEqual(adapter.adapt('tap', DEVICE, 1, '')['action']['state'], 'unknown')

    def test_native_and_child_results_are_not_business_success(self):
        for name, details, state in (
                ('press', {'action': {'nativeAccepted': True, 'effectVerified': False}}, 'accepted'),
                ('alert_press', {'action': {'nativeAccepted': False}}, 'refused'),
                ('scroll_to_visible', {'nativeResult': False, 'postconditionVerified': True}, 'native-false'),
                ('scroll_to_visible', {'nativeResult': True, 'postconditionVerified': False}, 'native-true'),
                ('input', {'action': {'childExitCode': 0}, 'postconditionVerified': False}, 'child-exited-zero'),
                ('input', {'action': {'childExitCode': 9}}, 'child-exited-nonzero')):
            raw = {'schemaVersion': 1, 'deviceIdentifier': DEVICE, **details}
            out = adapter.adapt(name, DEVICE, 6, json.dumps(raw))
            self.assertEqual(out['action']['state'], state)
            self.assertEqual(out['result'], raw)
            self.assertFalse(out['ok'])
            self.assertFalse(out['retrySafe'])
            self.assertEqual(out['businessVerified'], 'unknown')
        success = adapter.adapt('press', DEVICE, 0, json.dumps(
            {'schemaVersion': 1, 'deviceIdentifier': DEVICE, 'action': {'nativeAccepted': True, 'effectVerified': False}}))
        self.assertTrue(success['ok'])
        self.assertFalse(success['result']['action']['effectVerified'])
        for code in (-15, 137):
            raw = {'schemaVersion': 1, 'deviceIdentifier': DEVICE, 'action': {'childExitCode': code}}
            out = adapter.adapt('input', DEVICE, 6, json.dumps(raw))
            self.assertEqual(out['action']['state'], 'unknown')
            self.assertEqual(out['action']['childExitCode'], code)

    def test_frozen_receipt_consumption_and_version_guard(self):
        path = Path(__file__).resolve().parents[1]/'docs/contracts/ipb-error-v1.example.json'
        receipt = json.loads(path.read_text())
        receipt['result'] = {'native': 'retained'}
        out = adapter.adapt('press', DEVICE, 6, json.dumps(receipt))
        self.assertEqual(out['receipt'], receipt)
        self.assertEqual(out['result'], {'native': 'retained'})
        self.assertEqual(out['action']['state'], 'submitted')
        for key, value in (('contractVersion', 2), ('contractVersion', True),
                           ('kind', 'other'), ('operation', 'ui.input'), ('exitCode', 1)):
            invalid = {**receipt, key: value}
            out = adapter.adapt('press', DEVICE, 6, json.dumps(invalid))
            self.assertIsNone(out['receipt'])
            self.assertEqual(out['action']['state'], 'unknown')
        for state in ('child-exited-zero', 'child-exited-nonzero', 'native-true', 'native-false'):
            raw = {**receipt, 'action': {'state': state, 'native': 'unknown', 'childExitCode': 0}}
            self.assertEqual(adapter.adapt('press', DEVICE, 6, json.dumps(raw))['action']['state'], state)
        unknown = {**receipt, 'action': {'state': 'future', 'native': 'unknown', 'childExitCode': None}}
        self.assertEqual(adapter.adapt('press', DEVICE, 6, json.dumps(unknown))['action']['state'], 'unknown')
        before = {**receipt, 'exitCode': 1, 'phase': 'future', 'retrySafe': True,
                  'action': {'state': 'not-sent', 'native': 'future', 'childExitCode': None}}
        out = adapter.adapt('press', DEVICE, 1, json.dumps(before))
        self.assertTrue(out['retrySafe'])
        self.assertEqual(out['phase'], 'unknown')
        self.assertEqual(out['action']['native'], 'unknown')

    def test_read_receipt_retains_complete_native_result(self):
        receipt = {'kind': 'ipb.error', 'contractVersion': 1, 'operation': 'ui.dump', 'phase': 'unknown',
                   'exitCode': 1, 'error': {'type': 'ReadError', 'message': 'failed'}, 'action': None,
                   'retrySafe': True, 'result': snapshot()}
        out = adapter.adapt('observe', DEVICE, 1, json.dumps(receipt))
        self.assertIsNone(out['action'])
        self.assertEqual(out['result'], snapshot())
        self.assertFalse(out['ok'])

    def test_json_limits(self):
        for raw in ('{"x":NaN}', '{"x":1e9999}', '{"x":1,"x":2}'):
            with self.assertRaises(ValueError):
                adapter.loads(raw)


class InspectorTests(unittest.TestCase):
    def test_real_process_ownership_and_detached_cleanup(self):
        """Exercise the production inspector, not the cooperating fixture table."""
        async def exercise():
            with tempfile.TemporaryDirectory(prefix='ipb-real-mcp-') as directory:
                root = Path(directory)
                cli = root / 'fake-cli'
                cli.write_text('#!' + sys.executable + '\n' + '''import os, signal, subprocess, sys, time
from pathlib import Path
mode, ready = sys.argv[1:]
if mode == 'child':
    signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
    Path(ready).write_text(str(os.getpid()))
    time.sleep(30)
elif mode == 'success':
    print('fake result')
else:
    child = subprocess.Popen([sys.executable, __file__, 'child', ready], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def stop(*args):
        child.terminate()
        child.wait(timeout=2)
        sys.exit(5)
    signal.signal(signal.SIGTERM, stop)
    while not Path(ready).exists(): time.sleep(.01)
    if mode == 'detached': sys.exit(0)
    time.sleep(30)
''')
                cli.chmod(0o700)
                for mode in ('success', 'cancel', 'detached'):
                    ready = root / mode
                    cancel = asyncio.Event()
                    intents = []
                    task = asyncio.create_task(processes.run_cli(str(cli), [mode, str(ready)],
                        cancel, intents.append, intents.append, timeout=5, grace=2))
                    if mode == 'cancel':
                        for _ in range(200):
                            if ready.exists() or task.done(): break
                            await asyncio.sleep(.01)
                        if not ready.exists():
                            cancel.set()
                            outcome = await asyncio.wait_for(task, 10)
                            self.fail('fake child did not start: ' + str(outcome[2]))
                        cancel.set()
                    code, stdout, reason, complete, forced = await asyncio.wait_for(task, 10)
                    self.assertTrue(complete, (mode, reason))
                    self.assertFalse(forced, (mode, reason))
                    self.assertEqual(code, 5 if mode == 'cancel' else 0, (mode, reason))
                    self.assertEqual(reason, {'success': None, 'cancel': 'cancelled',
                                             'detached': 'descendants-after-cli-exit'}[mode])
                    owned, inspected = processes.Owner(intents[0]['nonce'], intents[0]['created']).scan()
                    self.assertTrue(inspected)
                    self.assertEqual(owned, {})
        asyncio.run(exercise())

    def test_exited_inspection_target_does_not_hide_live_permission_failure(self):
        row = {'pid': 1234, 'ppid': 1, 'pgid': 1234, 'start': 'identity', 'born': time.time()}
        for current, expected in (({}, True), ({1234: row}, False)):
            with self.subTest(alive=bool(current)), \
                 patch.object(processes, 'table', side_effect=[{1234: row}, current]), \
                 patch.object(processes, 'has_marker', side_effect=OSError(22, 'process arguments unavailable')):
                owned, complete = processes.Owner('request', row['born']).scan()
                self.assertEqual(owned, {})
                self.assertIs(complete, expected)

    def test_source_and_installed_launcher_are_host_only(self):
        root = Path(__file__).resolve().parents[1]
        requests = [ProtocolTests.init_message(self),
                    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
        with tempfile.TemporaryDirectory(prefix='ipb-mcp-install-') as directory:
            prefix = Path(directory)
            (prefix / 'bin').mkdir()
            (prefix / 'libexec').mkdir()
            shutil.copyfile(root / 'bin/ipb', prefix / 'bin/ipb')
            (prefix / 'bin/ipb').chmod(0o700)
            for module in ('ipb_mcp.py', 'ipb_mcp_adapter.py', 'ipb_mcp_process.py'):
                shutil.copyfile(root / 'Sources' / module, prefix / 'libexec' / module)
            unexpected = prefix / 'unexpected'
            trap = prefix / 'device-trap'
            trap.write_text('#!/bin/sh\ntouch "' + str(unexpected) + '"\nexit 99\n')
            trap.chmod(0o700)
            env = {**os.environ, 'DEVICE_ID': 'no-device-selection', 'DEVICECTL': str(trap),
                   'IPB_HELPER': str(trap), 'IPB_MCP_PYTHON': sys.executable,
                   'PYTHONDONTWRITEBYTECODE': '1'}
            for cli in (root / 'bin/ipb', prefix / 'bin/ipb'):
                result = subprocess.run([str(cli), 'mcp', '--state-dir', str(prefix / 'state')],
                    input=''.join(json.dumps(request) + '\n' for request in requests),
                    text=True, capture_output=True, env=env, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                messages = [json.loads(line) for line in result.stdout.splitlines()]
                self.assertEqual([message['id'] for message in messages], [1, 2])
                self.assertEqual(messages[1]['result']['tools'], adapter.TOOLS)
            self.assertFalse(unexpected.exists())

    def test_darwin_metadata_parser_uses_no_argv(self):
        row = f'{os.getuid()} 1234 1 1234 Tue Oct 27 12:00:00 2026 S\n'
        row += f'{os.getuid()} 1235 1 1235 Tue Oct 27 12:00:00 2026 Z\n'
        with patch.object(processes.sys, 'platform', 'darwin'), patch.object(processes.subprocess, 'run') as run:
            run.return_value.stdout = row.encode()
            result = processes.table()
        self.assertEqual(list(result), [1234])
        self.assertNotIn('argv', result[1234])
        self.assertEqual(run.call_args.args[0], ['/bin/ps', '-axo', 'uid=,pid=,ppid=,pgid=,lstart=,stat='])

    def test_darwin_marker_parser_skips_argv_and_only_returns_boolean(self):
        raw = struct.pack('i', 2) + b'/bin/python\0\0python\0secret-argument\0'
        raw += b'OTHER=secret-environment\0IPB_MCP_REQUEST_NONCE=our-nonce\0'
        class Libc:
            def sysctl(self, mib, length, buf, size, new, newlen):
                ctypes.memmove(buf, raw, len(raw))
                ctypes.cast(size, ctypes.POINTER(ctypes.c_size_t))[0] = len(raw)
                return 0
        with patch.object(processes.sys, 'platform', 'darwin'), patch.object(processes.ctypes, 'CDLL', return_value=Libc()):
            self.assertIs(processes.has_marker(1234, 'our-nonce'), True)
            self.assertIs(processes.has_marker(1234, 'secret-argument'), False)
            self.assertIs(processes.has_marker(1234, 'secret-environment'), False)


class FixtureCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 1
        self.temp = tempfile.TemporaryDirectory(prefix='ipb-mcp-test-')
        self.root = Path(self.temp.name)
        self.config_path = self.root/'config.json'
        self.log = self.root/'events.jsonl'
        self.log.touch()
        self.fixture = self.root/'fake-ipb'
        source = Path(__file__).with_name('test_mcp_fake_cli.py').resolve()
        self.fixture.write_text('#!'+sys.executable+'\nimport runpy\nrunpy.run_path('+repr(str(source))+', run_name="__main__")\n')
        self.fixture.chmod(0o700)
        self.config = {'log': str(self.log), 'mode': 'success'}
        self.configure()
        self.env = patch.dict(os.environ, {'MCP_FIXTURE_CONFIG': str(self.config_path),
                                          'PYTHONDONTWRITEBYTECODE': '1'})
        self.env.start()
        self.inspector = patch.multiple(processes, table=test_mcp_host.table, has_marker=test_mcp_host.has_marker)
        self.inspector.start()
        original = processes.spawn_cli
        def spawn(*args, **kwargs):
            process = original(*args, **kwargs)
            until = time.monotonic()+1
            while time.monotonic() < until and process.poll() is None:
                if any(e['pid'] == process.pid and e['event'] == 'start' for e in self.events()):
                    break
                time.sleep(.005)
            return process
        self.factory = patch.object(processes, 'spawn_cli', spawn)
        self.factory.start()
        self.servers = []
        self.bridge = ipb_mcp.Bridge(str(self.fixture), self.root/'state', timeout=2, grace=0.25)

    def configure(self, **fields):
        self.config.update(fields)
        self.config_path.write_text(json.dumps(self.config))

    def events(self):
        return [json.loads(line) for line in self.log.read_text().splitlines() if line]

    async def until(self, predicate, timeout=5):
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            if predicate():
                return
            await asyncio.sleep(0.02)
        self.fail('fixture synchronization timed out')

    async def asyncTearDown(self):
        for process in self.servers:
            if process.returncode is None:
                process.kill()
                await process.wait()
        # Only fixture-owned processes recorded under this private temp path.
        # Test crash/force scenarios may deliberately leave a fixture child alive.
        for event in self.events():
            if event['event'] not in ('start', 'child'):
                continue
            try:
                if processes.has_marker(event['pid'], self.nonce_for(event['pid'])):
                    os.kill(event['pid'], signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        self.env.stop()
        self.factory.stop()
        self.inspector.stop()
        self.temp.cleanup()

    def nonce_for(self, pid):
        # Only inspect our persisted request marker, never argv/user environments.
        for path in (self.root/'state').glob('*.json'):
            state = json.loads(path.read_text())
            active = state.get('active') or (state.get('quarantine') or {}).get('intent') or {}
            if active.get('nonce'):
                return active['nonce']
        return 'not-this-request'

    async def call(self, name='press', **args):
        return await self.bridge.call(name, {'device': DEVICE, **({'identifier': 'Seven'} if name in
            ('press', 'input', 'locate', 'wait', 'scroll_to_visible') else {}), **args}, asyncio.Event())


class ProcessTests(FixtureCase):
    async def test_fake_success_and_no_business_upgrade(self):
        for name in ('observe', 'locate', 'wait', 'press', 'scroll_to_visible', 'home', 'tap', 'swipe', 'alert_press', 'input'):
            args = {'tap': {'x': 0.5, 'y': 0.5},
                    'swipe': {'x1': 0, 'y1': 0, 'x2': 1, 'y2': 1},
                    'alert_press': {'pid': 42, 'alertLabel': 'Paste?', 'label': 'Allow'},
                    'input': {'text': 'synthetic input', 'replaceAll': True}}.get(name, {})
            with self.subTest(name=name):
                out = await self.call(name, **args)
                self.assertTrue(out['ok'], out)
                self.assertEqual(out['businessVerified'], 'unknown')
                self.assertIsNone(out['isolation'])
        out = await self.bridge.call('devices', {}, asyncio.Event())
        self.assertTrue(out['ok'])
        self.assertEqual(out['result']['devices'][0]['name'], 'Fake')

    async def test_same_device_serial_and_different_device_concurrent(self):
        self.configure(mode='delay', delay=0.2)
        for devices in ((DEVICE, DEVICE), (DEVICE, OTHER)):
            self.log.write_text('')
            results = await asyncio.gather(*(self.bridge.call('observe', {'device': device}, asyncio.Event())
                                             for device in devices))
            self.assertTrue(all(result['ok'] for result in results), results)
            events = self.events()
            kinds = [event['event'] for event in events]
            if devices[0] == devices[1]:
                self.assertEqual(kinds, ['start', 'end', 'start', 'end'])
            else:
                self.assertEqual(kinds[:2], ['start', 'start'])

    async def test_cancel_once_grace_keeps_lock_until_reaped_and_requires_observe(self):
        self.configure(mode='sleep', termDelay=0.12)
        cancel = asyncio.Event()
        first = asyncio.create_task(self.bridge.call('input', {'device': DEVICE, 'identifier': 'field',
            'text': 'synthetic-private', 'replaceAll': True}, cancel))
        await self.until(lambda: any(e['event'] == 'start' for e in self.events()))
        cancel.set()
        # Repeated cancellation is the same event, not repeated task.cancel/SIGTERM.
        cancel.set()
        out = await first
        self.assertFalse(out['ok'])
        self.assertEqual(out['isolation'], 'observeRequired', out)
        self.assertEqual(sum(e['event'] == 'term' for e in self.events()), 1)
        blocked = await self.call('home')
        self.assertEqual(blocked['error'], 'device-quarantined')
        self.configure(mode='success')
        observed = await self.call('observe')
        self.assertTrue(observed['ok'], observed)
        self.assertIsNone(observed['isolation'])
        self.assertTrue((await self.call('home'))['ok'])
        state = (self.root/'state'/f'{DEVICE}.json').read_text()
        self.assertNotIn('synthetic-private', state)
        self.assertNotIn('argv', state)

    async def test_lock_wait_cancel_does_not_spawn(self):
        self.configure(mode='delay', delay=0.3)
        first = asyncio.create_task(self.call('observe'))
        await self.until(lambda: len(self.events()) == 1)
        cancel = asyncio.Event()
        waiting = asyncio.create_task(self.bridge.call('home', {'device': DEVICE}, cancel))
        await asyncio.sleep(0.04)
        cancel.set()
        out = await waiting
        self.assertEqual(out['action']['state'], 'not-sent')
        await first
        self.assertEqual(sum(e['event'] == 'start' for e in self.events()), 1)

    async def test_outer_exit_independent_session_child_and_pipe_eof(self):
        for mode in ('detached-pipe', 'detached-eof', 'group-child', 'grandchild-eof'):
            with self.subTest(mode=mode):
                self.log.write_text('')
                self.configure(mode=mode)
                out = await self.call('input', text='fixture', replaceAll=True)
                self.assertFalse(out['ok'])
                self.assertEqual(out['error'], 'descendants-after-cli-exit')
                self.assertEqual(out['isolation'], 'observeRequired', out)
                events = self.events()
                child = next(e for e in events if e['event'] == 'child')
                outer = next(e for e in events if e['event'] == 'start')
                if mode != 'group-child':
                    self.assertNotEqual(child['pgid'], outer['pid'])
                if mode == 'grandchild-eof':
                    self.assertNotEqual(child['ppid'], outer['pid'])
                self.assertEqual(sum(e['event'] == 'term' and e['pid'] == child['pid'] for e in events), 1)
                self.configure(mode='success')
                self.assertIsNone((await self.call('observe'))['isolation'])

    async def test_force_kill_persists_quarantine_across_restart_and_observe(self):
        self.configure(mode='detached-eof', ignoreTerm=True)
        out = await self.call('input', text='fixture', replaceAll=True)
        self.assertEqual(out['isolation'], 'orphanPossible', out)
        self.assertEqual(sum(e['event'] == 'term' for e in self.events()), 1)
        self.configure(mode='success')
        self.bridge = ipb_mcp.Bridge(str(self.fixture), self.root/'state', timeout=2, grace=.25)
        observed = await self.call('observe')
        self.assertFalse(observed['ok'], observed)
        self.assertEqual(observed['error'], 'device-quarantined')
        self.assertEqual(observed['isolation'], 'orphanPossible')
        self.assertEqual((await self.call('press'))['error'], 'device-quarantined')
        state = self.bridge.state.load(DEVICE)
        state['quarantine']['intent']['created'] = 0  # expiry must not clear it
        self.bridge.state.save(DEVICE, state)
        self.assertEqual((await self.call('home'))['isolation'], 'orphanPossible')

    async def test_timeout_and_bad_output_never_replay(self):
        for mode in ('signal', 'invalid', 'exit-6', 'flood', 'sleep'):
            with self.subTest(mode=mode):
                # Each scenario has its own state root; never self-unquarantine.
                self.bridge = ipb_mcp.Bridge(str(self.fixture), self.root/('state-'+mode), timeout=.35, grace=.25)
                self.configure(mode=mode)
                before = sum(e['event'] == 'start' for e in self.events())
                out = await self.call('press')
                self.assertFalse(out['ok'])
                self.assertEqual(out['action']['state'], 'unknown')
                self.assertFalse(out['retrySafe'])
                self.assertEqual(sum(e['event'] == 'start' for e in self.events()), before+1)
                self.assertIn(out['isolation'], ('observeRequired', 'orphanPossible'))

    async def test_incomplete_observe_cannot_clear_observe_required(self):
        state = {'version': 1, 'active': None, 'quarantine': {'mode': 'observeRequired', 'reason': 'test'}}
        self.bridge.state.save(DEVICE, state)
        self.configure(mode='incomplete')
        out = await self.call('observe')
        self.assertFalse(out['ok'])
        self.assertEqual(out['isolation'], 'observeRequired')

    async def test_spawn_intent_is_durable_and_unfinished_intent_survives_restart(self):
        observed = []
        def pre_spawn(intent):
            observed.append(dict(intent))
            self.bridge.state.save(DEVICE, {'version': 1, 'active': intent, 'quarantine': None})
        def post_spawn(intent):
            state = self.bridge.state.load(DEVICE)
            self.assertIsNone(state['active']['pid'])
            self.assertEqual(state['active']['nonce'], intent['nonce'])
            self.assertIsNotNone(intent['pid'])
            self.assertIsNotNone(intent['start'])
            observed.append(dict(intent))
        await processes.run_cli(str(self.fixture), ['devices'], asyncio.Event(), pre_spawn, post_spawn,
                                timeout=2, grace=.25)
        self.assertEqual(len(observed), 2)
        # Pre-spawn intent alone is deliberately unresolved after crash.
        self.configure(mode='success')
        self.assertEqual((await self.call('home'))['isolation'], 'orphanPossible')
        self.assertEqual((await self.call('observe'))['isolation'], 'orphanPossible')

    async def test_unrelated_process_and_pid_reuse_not_signalled(self):
        owner = processes.Owner('our-nonce', time.time())
        row = {'pid': 12345, 'ppid': 1, 'pgid': 12345, 'start': 'old', 'born': 0}
        owner.known[row['pid']] = row
        current = {12345: {**row, 'start': 'new'}}
        with patch.object(processes, 'table', return_value=current), patch.object(processes.os, 'kill') as kill:
            owner.send({12345: row}, signal.SIGTERM)
            kill.assert_not_called()

    async def test_ownership_inspection_failure_is_persistent_unknown(self):
        original = processes.Owner.scan
        calls = 0
        def scan(owner):
            nonlocal calls
            calls += 1
            return original(owner) if calls == 1 else ({}, False)
        with patch.object(processes.Owner, 'scan', scan):
            out = await self.call('home')
        self.assertFalse(out['ok'])
        self.assertEqual(out['isolation'], 'orphanPossible')

    async def test_failed_ownership_preflight_never_spawns_or_quarantines(self):
        with patch.object(processes.Owner, 'scan', return_value=({}, False)):
            out = await self.call('input', text='fixture', replaceAll=True)
        self.assertEqual(out['action']['state'], 'not-sent')
        self.assertEqual(out['error'], 'ownership-unavailable-before-spawn')
        self.assertIsNone(out['isolation'])
        self.assertEqual(self.events(), [])

    async def test_spawn_failure_is_proven_not_sent(self):
        self.bridge.cli = str(self.root/'missing-cli')
        out = await self.call('press')
        self.assertEqual(out['action']['state'], 'not-sent')
        self.assertTrue(out['retrySafe'])
        self.assertIsNone(out['isolation'])

    async def test_stderr_is_not_echoed_and_does_not_prove_submission(self):
        self.configure(mode='stderr')
        out = await self.call('press')
        self.assertNotIn('SYNTHETIC-PRIVATE-FIXTURE-TEXT', json.dumps(out))

    async def test_opt_in_receipt_is_used_without_quarantine_or_retry(self):
        self.configure(mode='receipt')
        out = await self.call('press')
        self.assertFalse(out['ok'])
        self.assertEqual(out['action']['state'], 'not-sent')
        self.assertTrue(out['retrySafe'])
        self.assertEqual(out['phase'], 'validation')
        self.assertIsNone(out['isolation'])
        self.assertEqual(sum(e['event'] == 'start' for e in self.events()), 1)

    async def test_enumeration_also_persists_intent_before_spawn(self):
        original = processes.spawn_cli
        def spawn(*args, **kwargs):
            state = self.bridge.state.load('inventory')
            self.assertIsNotNone(state['active']['nonce'])
            self.assertIsNone(state['active']['pid'])
            return original(*args, **kwargs)
        with patch.object(processes, 'spawn_cli', spawn):
            out = await self.bridge.call('devices', {}, asyncio.Event())
        self.assertTrue(out['ok'], out)
        self.assertIsNone(self.bridge.state.load('inventory')['active'])

    async def test_observed_uuid_case_is_preserved_for_legacy_cli_and_lock_is_canonical(self):
        observed = OTHER.upper()
        self.configure(requireDeviceCase=observed)
        out = await self.bridge.call('observe', {'device': observed}, asyncio.Event())
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['result']['deviceIdentifier'], observed)
        self.assertTrue((self.root/'state'/f'{OTHER}.json').exists())
        # APFS may be case-insensitive; inspect stored names rather than alias existence.
        self.assertIn(f'{OTHER}.json', [path.name for path in (self.root/'state').iterdir()])
        self.assertNotIn(f'{observed}.json', [path.name for path in (self.root/'state').iterdir()])


class ProtocolTests(FixtureCase):
    def init_message(self):
        return {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                'params': {'protocolVersion': '2025-11-25', 'capabilities': {},
                           'clientInfo': {'name': 'host-fixture', 'version': '1'}}}

    async def test_protocol_lifecycle_methods_and_notifications(self):
        output = []
        server = ipb_mcp.Server(self.bridge, output.append)
        await server.accept({'jsonrpc': '2.0', 'id': 0, 'method': 'tools/list'})
        self.assertEqual(output.pop()['error']['code'], -32600)
        await server.accept(self.init_message())
        self.assertEqual(output.pop()['result']['protocolVersion'], ipb_mcp.PROTOCOL_VERSION)
        await server.accept({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        await server.accept({'jsonrpc': '2.0', 'method': 'unknown/notification'})
        await server.accept({'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {'requestId': []}})
        self.assertEqual(output, [])
        await server.accept({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
        self.assertEqual(len(output.pop()['result']['tools']), len(adapter.TOOLS))
        await server.accept({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list',
                             'params': {'_meta': {'progressToken': 'ignored'}}})
        self.assertEqual(len(output.pop()['result']['tools']), len(adapter.TOOLS))
        await server.accept({'jsonrpc': '2.0', 'id': 3, 'method': 'resources/list'})
        self.assertEqual(output.pop()['error']['code'], -32601)
        await server.accept({'jsonrpc': '2.0', 'id': 4, 'method': 'ping'})
        self.assertEqual(output.pop()['result'], {})

    async def test_only_supported_version_is_returned_for_negotiation(self):
        output = []
        server = ipb_mcp.Server(self.bridge, output.append)
        request = self.init_message()
        request['params']['protocolVersion'] = '2024-11-05'
        await server.accept(request)
        self.assertEqual(output.pop()['result']['protocolVersion'], '2025-11-25')
        await server.accept({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
        self.assertEqual(output.pop()['error']['code'], -32600)

    async def test_invalid_requests_schemas_and_inflight_bound(self):
        output = []
        server = ipb_mcp.Server(self.bridge, output.append)
        await server.accept(self.init_message())
        await server.accept({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        output.clear()
        for value in ([], {'jsonrpc': '2.0', 'id': None, 'method': 'ping'},
                      {'jsonrpc': '2.0', 'id': True, 'method': 'ping'},
                      {'jsonrpc': '1.0', 'id': 3, 'method': 'ping'}):
            await server.accept(value)
            self.assertEqual(output.pop()['error']['code'], -32600)
        for params in ({'name': 'text', 'arguments': {}}, {'name': 'observe', 'arguments': {'device': 'short'}},
                       {'name': 'press', 'arguments': {'device': DEVICE}}, {'name': 'home', 'arguments': [], 'extra': 1}):
            await server.accept({'jsonrpc': '2.0', 'id': 9, 'method': 'tools/call', 'params': params})
            self.assertEqual(output.pop()['error']['code'], -32602)
        self.assertEqual(self.events(), [])
        server.pending = {key: (None, asyncio.Event()) for key in range(20, 20+ipb_mcp.MAX_REQUESTS)}
        await server.accept({'jsonrpc': '2.0', 'id': 10, 'method': 'tools/call',
                             'params': {'name': 'observe', 'arguments': {'device': DEVICE}}})
        self.assertEqual(output.pop()['error']['code'], -32000)

    async def start_server(self, state_root=None):
        source = str(Path(__file__).resolve().parents[1]/'Sources')
        scripts = str(Path(__file__).resolve().parent)
        harness = ('import sys; sys.path[:0]='+repr([source, scripts])+'; '
                   'import ipb_mcp_process, test_mcp_host; test_mcp_host.install(ipb_mcp_process); '
                   'import ipb_mcp; sys.exit(ipb_mcp.main())')
        process = await asyncio.create_subprocess_exec(sys.executable, '-c', harness,
            '--cli', str(self.fixture), '--state-dir', str(state_root or self.root/'state'),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self.servers.append(process)
        await self.send(process, self.init_message())
        reply = await self.receive(process)
        self.assertEqual(reply['id'], 1)
        await self.send(process, {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        return process

    async def send(self, process, message):
        process.stdin.write((json.dumps(message)+'\n').encode())
        await process.stdin.drain()

    async def receive(self, process):
        line = await asyncio.wait_for(process.stdout.readline(), 5)
        self.assertTrue(line)
        return json.loads(line)

    async def stop(self, process):
        process.stdin.close()
        code = await asyncio.wait_for(process.wait(), 5)
        self.assertEqual(code, 0, (await process.stderr.read()).decode())

    async def test_real_stdio_parse_errors_version_negotiation_and_tools_call(self):
        process = await self.start_server()
        process.stdin.write(b'{bad\n')
        await process.stdin.drain()
        self.assertEqual((await self.receive(process))['error']['code'], -32700)
        await self.send(process, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                                 'params': {'name': 'observe', 'arguments': {'device': DEVICE}}})
        reply = await self.receive(process)
        envelope = json.loads(reply['result']['content'][0]['text'])
        self.assertFalse(reply['result']['isError'])
        self.assertEqual(envelope['result']['idsScope'], 'this-observation-only')
        await self.stop(process)

    async def test_cross_server_flock_same_canonical_root(self):
        self.configure(mode='delay', delay=.3)
        first = await self.start_server()
        alias = self.root/'state-alias'
        alias.symlink_to(self.root/'state', target_is_directory=True)
        second = await self.start_server(alias)
        message = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                   'params': {'name': 'observe', 'arguments': {'device': DEVICE}}}
        await asyncio.gather(self.send(first, message), self.send(second, message))
        replies = await asyncio.gather(self.receive(first), self.receive(second))
        self.assertTrue(all(not reply['result']['isError'] for reply in replies), replies)
        self.assertEqual([e['event'] for e in self.events()], ['start', 'end', 'start', 'end'])
        await self.stop(first)
        await self.stop(second)

    async def test_stdio_cancel_not_replied_repeated_and_shutdown_cleans(self):
        self.configure(mode='sleep')
        process = await self.start_server()
        await self.send(process, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                                 'params': {'name': 'press', 'arguments': {'device': DEVICE, 'identifier': 'Seven'}}})
        await self.until(lambda: any(e['event'] == 'start' for e in self.events()))
        for _ in range(3):
            await self.send(process, {'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {'requestId': 2}})
        await self.send(process, {'jsonrpc': '2.0', 'id': 3, 'method': 'ping'})
        self.assertEqual((await self.receive(process))['id'], 3)
        await self.stop(process)
        self.assertEqual(await process.stdout.read(), b'')
        self.assertEqual(sum(e['event'] == 'term' for e in self.events()), 1)
        self.assertEqual(self.bridge.state.load(DEVICE)['quarantine']['mode'], 'observeRequired')

    async def test_server_crash_leaves_intent_and_new_server_cannot_mutate(self):
        self.configure(mode='sleep')
        first = await self.start_server()
        await self.send(first, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                               'params': {'name': 'input', 'arguments': {'device': DEVICE,
                                   'identifier': 'field', 'text': 'sensitive-fixture', 'replaceAll': True}}})
        await self.until(lambda: any(e['event'] == 'start' for e in self.events()))
        first.kill()
        await first.wait()
        second = await self.start_server()
        await self.send(second, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                                'params': {'name': 'home', 'arguments': {'device': DEVICE}}})
        reply = json.loads((await self.receive(second))['result']['content'][0]['text'])
        self.assertEqual(reply['isolation'], 'orphanPossible')
        self.assertEqual(reply['error'], 'device-quarantined')
        self.assertEqual(sum(e['event'] == 'start' for e in self.events()), 1)
        self.assertNotIn('sensitive-fixture', json.dumps(self.bridge.state.load(DEVICE)))
        await self.stop(second)

    async def test_stdio_frame_size_bound(self):
        process = await self.start_server()
        process.stdin.write(b'x'*(ipb_mcp.MAX_MESSAGE+1)+b'\n')
        await process.stdin.drain()
        self.assertEqual((await self.receive(process))['error']['code'], -32700)
        self.assertEqual(await asyncio.wait_for(process.wait(), 5), 0)

    async def test_stdio_output_backpressure_does_not_hang_shutdown(self):
        process = await self.start_server()
        for request_id in range(10, 80):
            process.stdin.write((json.dumps({'jsonrpc': '2.0', 'id': request_id, 'method': 'tools/list'})+'\n').encode())
        await process.stdin.drain()
        # Deliberately do not read stdout while its bounded writer/queue stops.
        await self.until(lambda: process.returncode is not None, timeout=8)
        await process.stdout.read()
        self.assertEqual(await process.wait(), 0)


if __name__ == '__main__':
    unittest.main()
