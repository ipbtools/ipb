#!/usr/bin/env python3
"""Bounded stdio MCP front end for ipb; no phone Runner or network listener."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time

from ipb_mcp_adapter import TOOLS, READS, adapt, command, loads
from ipb_mcp_process import DeviceState, run_cli

PROTOCOL_VERSION = '2025-11-25'
MAX_MESSAGE = 65536
MAX_REQUESTS = 16
MAX_RESPONSE = 8 * 1024 * 1024


def error_result(name, device, error, *, not_sent=True, quarantine=None):
    return {"kind": "ipb.mcp.result", "envelopeVersion": 1, "tool": name,
            "deviceIdentifier": device, "ok": False, "cliExitCode": None, "error": error,
            "action": None if name in READS else
                {"state": "not-sent" if not_sent else "unknown", "native": "unknown", "childExitCode": None},
            "retrySafe": name in READS or (not_sent and quarantine is None),
            "businessVerified": "unknown", "phase": "unknown", "result": None, "receipt": None,
            "isolation": quarantine}


class Bridge:
    def __init__(self, cli, state_root, *, timeout=60, grace=22):
        self.cli = str(Path(cli).resolve())
        self.state = DeviceState(state_root)
        self.timeout, self.grace = timeout, grace

    async def call(self, name, arguments, cancel):
        argv = command(name, arguments)  # validation completes before locks or spawn
        device = arguments.get('device', '').lower() or None
        read = name in READS
        deadline = time.monotonic() + self.timeout
        # Enumeration has its own global intent/lock, never a selected-device lock.
        # Even this read-only CLI must leave a durable record if the server crashes.
        state_key = device or 'inventory'
        try:
            async with self.state.locked(state_key, cancel, deadline) as state:
                if cancel.is_set():
                    return error_result(name, device, 'cancelled-before-spawn')
                quarantine = state.get('quarantine')
                if quarantine and (not read or quarantine['mode'] == 'orphanPossible'):
                    return error_result(name, device, 'device-quarantined', quarantine=quarantine['mode'])

                def persist(intent):
                    # No selectors/text, argv, clipboard, pairing or environment.
                    state['active'] = {**intent, 'tool': name, 'modifying': not read}
                    self.state.save(state_key, state)

                outcome = await run_cli(self.cli, argv, cancel, persist, persist,
                                        timeout=max(0, deadline - time.monotonic()), grace=self.grace)
                code, stdout, reason, complete, forced = outcome
                result = adapt(name, device, code, stdout, interrupted=reason,
                               requested_profile=arguments.get('nativeProfile', 'full')
                               if name == 'observe' else 'full')
                if reason in ('cancelled-before-spawn', 'cli-spawn-failed', 'ownership-unavailable-before-spawn'):
                    result = error_result(name, device, reason)
                intent = state.get('active')
                if forced or not complete:
                    state['quarantine'] = {"mode": "orphanPossible", "reason": reason or 'ownership-unproven',
                                           "intent": intent}
                elif not read and (not result['ok'] or result['action']['state'] == 'unknown'):
                    if result['action']['state'] != 'not-sent':
                        state['quarantine'] = {"mode": "observeRequired", "reason": reason or 'action-outcome',
                                               "intent": intent}
                elif (name == 'observe' and result['ok'] and state.get('quarantine', {})
                      and state['quarantine']['mode'] == 'observeRequired'):
                    state['quarantine'] = None
                state['active'] = None
                self.state.save(state_key, state)
                result['isolation'] = state['quarantine']['mode'] if state['quarantine'] else None
                return result
        except TimeoutError:
            return error_result(name, device, 'cancelled-in-lock-wait' if cancel.is_set() else 'device-lock-timeout')


class Server:
    def __init__(self, bridge, emit):
        self.bridge, self.emit = bridge, emit
        self.initialized = False
        self.ready = False
        self.pending = {}

    def rpc_error(self, request_id, code, message):
        self.emit({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})

    def response(self, request_id, result):
        self.emit({"jsonrpc": "2.0", "id": request_id, "result": result})

    async def accept(self, value):
        if not isinstance(value, dict):
            self.rpc_error(None, -32600, 'Invalid Request; batches unsupported')
            return
        notification = 'id' not in value
        request_id = value.get('id')
        valid_id = type(request_id) in (str, int) and (type(request_id) is not str or 0 < len(request_id) <= 128)
        if (value.get('jsonrpc') != '2.0' or not isinstance(value.get('method'), str)
                or (not notification and not valid_id)):
            # Invalid notifications receive no response; malformed request has null ID.
            if not notification:
                self.rpc_error(None, -32600, 'Invalid Request')
            return
        method, params = value['method'], value.get('params', {})
        if notification:
            if method == 'notifications/initialized' and self.initialized and isinstance(params, dict):
                self.ready = True
            elif method == 'notifications/cancelled' and isinstance(params, dict):
                target = params.get('requestId')
                if type(target) in (str, int) and target in self.pending:
                    self.pending[target][1].set()  # never task.cancel() AX cleanup
            return
        if request_id in self.pending:
            self.rpc_error(request_id, -32600, 'Request ID already in progress')
            return
        if not isinstance(params, dict):
            self.rpc_error(request_id, -32602, 'params must be an object')
            return
        if method == 'initialize':
            if self.initialized:
                self.rpc_error(request_id, -32600, 'Already initialized')
            elif (not isinstance(params.get('protocolVersion'), str)
                  or not isinstance(params.get('capabilities'), dict)
                  or not isinstance(params.get('clientInfo'), dict)
                  or not all(isinstance(params['clientInfo'].get(key), str) for key in ('name', 'version'))):
                self.rpc_error(request_id, -32602, 'Invalid initialize parameters')
            else:
                # MCP version negotiation: return the only supported revision.
                self.initialized = True
                self.response(request_id, {"protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "ipb-mcp", "version": "0.1.0"},
                    "instructions": "Full CoreDevice UUID required. No automatic action replay. "
                                    "Only MCP servers sharing one canonical state root are locked; "
                                    "manual CLI/mirror are outside isolation. Business success is unknown."})
            return
        if method == 'ping':
            self.response(request_id, {})
            return
        if method not in ('tools/list', 'tools/call'):
            self.rpc_error(request_id, -32601, 'Method not found')
            return
        if not self.ready:
            self.rpc_error(request_id, -32600, 'Initialize and send notifications/initialized first')
            return
        if method == 'tools/list':
            if params.keys() - {'_meta'} or ('_meta' in params and not isinstance(params['_meta'], dict)):
                self.rpc_error(request_id, -32602, 'No cursor or list parameters supported')
            else:
                self.response(request_id, {'tools': TOOLS})
            return
        if params.keys() - {'name', 'arguments', '_meta'} or not isinstance(params.get('name'), str):
            self.rpc_error(request_id, -32602, 'Invalid tools/call parameters')
            return
        try:
            command(params['name'], params.get('arguments', {}))
        except (ValueError, TypeError, OverflowError):
            self.rpc_error(request_id, -32602, 'Invalid tool name or arguments; see tools/list')
            return
        if len(self.pending) >= MAX_REQUESTS:
            self.rpc_error(request_id, -32000, 'Too many in-flight requests')
            return
        cancel = asyncio.Event()
        task = asyncio.create_task(self.execute(request_id, params, cancel))
        self.pending[request_id] = (task, cancel)

    async def execute(self, request_id, params, cancel):
        try:
            try:
                result = await self.bridge.call(params['name'], params.get('arguments', {}), cancel)
            except Exception:
                # Persisted active intent survives errors/crashes. Never echo exception
                # text: native exceptions can contain argv/user input.
                result = error_result(params['name'], params.get('arguments', {}).get('device'),
                                      'host-adapter-error', not_sent=False, quarantine='unknown')
            if not cancel.is_set():
                self.response(request_id, {"content": [{"type": "text", "text": json.dumps(
                    result, ensure_ascii=False, allow_nan=False, separators=(',', ':'))}],
                    "isError": not result['ok']})
        finally:
            self.pending.pop(request_id, None)

    async def shutdown(self):
        tasks = list(self.pending.values())
        for _, cancel in tasks:
            cancel.set()
        if tasks:
            await asyncio.gather(*(task for task, _ in tasks))


async def serve(bridge):
    queue = asyncio.Queue(maxsize=MAX_REQUESTS)
    stopping = asyncio.Event()

    def emit(value):
        data = (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n').encode()
        if len(data) > MAX_RESPONSE:
            stopping.set()
            return
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            stopping.set()

    async def write_output():
        fd = sys.stdout.fileno()
        os.set_blocking(fd, False)
        try:
            while True:
                data = await queue.get()
                if data is None:
                    return
                view = memoryview(data)
                async with asyncio.timeout(5):
                    while view:
                        try:
                            written = os.write(fd, view)
                            if written == 0:
                                raise BrokenPipeError()
                            view = view[written:]
                        except BlockingIOError:
                            await asyncio.sleep(.02)
        except (OSError, TimeoutError):
            stopping.set()

    server = Server(bridge, emit)
    writer_task = asyncio.create_task(write_output())
    reader = asyncio.StreamReader(limit=MAX_MESSAGE)
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_running_loop()
    transport, _ = await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopping.set)
    try:
        while not stopping.is_set():
            read_task = asyncio.create_task(reader.readline())
            stop_task = asyncio.create_task(stopping.wait())
            done, pending = await asyncio.wait((read_task, stop_task), return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            if stopping.is_set():
                break
            try:
                line = read_task.result()
            except ValueError:  # oversized frame: stop rather than drain indefinitely
                server.rpc_error(None, -32700, 'Message exceeds 65536-byte limit')
                break
            if not line:
                break
            try:
                value = loads(line.decode('utf-8'))
            except (ValueError, UnicodeError, RecursionError):
                server.rpc_error(None, -32700, 'Parse error')
                continue
            await server.accept(value)
    finally:
        transport.close()
        await server.shutdown()
        if not writer_task.done():
            try:
                queue.put_nowait(None)
                await asyncio.wait_for(writer_task, 6)
            except (asyncio.QueueFull, TimeoutError):
                writer_task.cancel()
        await asyncio.gather(writer_task, return_exceptions=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', default=shutil.which('ipb'), help='ipb executable; no shell command string')
    parser.add_argument('--state-dir', default=str(Path(os.environ.get('XDG_STATE_HOME',
                        str(Path.home() / '.local/state'))) / 'ipb/mcp'),
                        help='shared canonical state/lock directory; different roots are not mutually protected')
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error('Python 3.11+ required')
    if not args.cli or not Path(args.cli).is_file() or not os.access(args.cli, os.X_OK):
        parser.error('--cli must name an existing executable')
    try:
        asyncio.run(serve(Bridge(args.cli, args.state_dir)))
    except (OSError, BrokenPipeError):
        print('ipb-mcp: host transport/state failure; inspect persistent device state before reuse', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
