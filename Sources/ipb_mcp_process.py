"""Host process ownership and persistent, per-device MCP isolation (POSIX only).

No argv or full environment is logged/persisted. Markers are examined in memory.
Manual CLI/mirror and servers using different canonical state roots are outside this lock.
"""
import asyncio
from contextlib import asynccontextmanager
import ctypes
import errno
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
import weakref

MARKER = "IPB_MCP_REQUEST_NONCE"
MAX_STDOUT = 2 * 1024 * 1024
MAX_STDERR = 64 * 1024
GRACE_SECONDS = 22.0  # backend cleanup <=18.5s, with scheduling/IO headroom
spawn_cli = subprocess.Popen


def table():
    """Return only process identities, not commands. start distinguishes PID reuse."""
    rows = {}
    if sys.platform.startswith("linux"):
        boot = next(float(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines()
                    if line.startswith('btime '))
        hz = os.sysconf('SC_CLK_TCK')
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat().st_uid != os.getuid():
                    continue
                fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
                if fields[0] == 'Z':
                    continue
                pid = int(entry.name)
                rows[pid] = {"pid": pid, "ppid": int(fields[1]), "pgid": int(fields[2]),
                             "start": fields[19], "born": boot + int(fields[19]) / hz}
            except (FileNotFoundError, ProcessLookupError):
                continue
    elif sys.platform == "darwin":
        raw = subprocess.run(['/bin/ps', '-axo', 'uid=,pid=,ppid=,pgid=,lstart=,stat='],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=2,
                             env={**os.environ, 'LC_ALL': 'C'}, check=True).stdout.decode()
        for line in raw.splitlines():
            fields = line.split()
            if len(fields) != 10 or int(fields[0]) != os.getuid() or fields[9].startswith('Z'):
                continue
            start = ' '.join(fields[4:9])
            pid = int(fields[1])
            rows[pid] = {"pid": pid, "ppid": int(fields[2]), "pgid": int(fields[3]),
                         "start": start, "born": time.mktime(time.strptime(start, '%a %b %d %H:%M:%S %Y'))}
    else:
        raise OSError("process ownership unavailable on this host")
    return rows


def has_marker(pid, nonce):
    """Read this one marker only; never return argv/environment to callers."""
    expected = (MARKER + '=' + nonce).encode()
    if sys.platform.startswith('linux'):
        return expected in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
    # Darwin KERN_PROCARGS2: argc, executable\0, padding, argc argv strings, env.
    # This is a host kernel interface, not a private iOS protocol claim.
    libc = ctypes.CDLL(None, use_errno=True)
    mib = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2
    size = ctypes.c_size_t(1024 * 1024)
    buf = ctypes.create_string_buffer(size.value)
    if libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0) != 0:
        code = ctypes.get_errno()
        if code in (errno.ESRCH, errno.ENOENT):
            raise ProcessLookupError(pid)
        raise OSError(code, 'request marker inspection unavailable')
    raw = buf.raw[:size.value]
    if len(raw) < 4:
        raise OSError('request marker inspection incomplete')
    argc = int.from_bytes(raw[:4], sys.byteorder, signed=True)
    offset = raw.find(b'\0', 4)
    if not 0 <= argc <= 65536 or offset < 0:
        raise OSError('request marker inspection incomplete')
    while offset < len(raw) and raw[offset] == 0:
        offset += 1
    for _ in range(argc):
        end = raw.find(b'\0', offset)
        if end < 0:
            raise OSError('request marker inspection incomplete')
        offset = end + 1
    return expected in raw[offset:].split(b'\0')


class Owner:
    def __init__(self, nonce, since):
        self.nonce, self.since = nonce, since
        self.known = {}

    def scan(self):
        try:
            rows = table()
        except (OSError, ValueError, subprocess.SubprocessError):
            return {}, False
        owned, complete = {}, True
        for pid, row in rows.items():
            if pid == os.getpid():
                continue
            if self.known.get(pid, {}).get('start') == row['start']:
                owned[pid] = row
            elif row['born'] >= self.since - 1:
                try:
                    if has_marker(pid, self.nonce):
                        owned[pid] = row
                except (FileNotFoundError, ProcessLookupError):
                    pass
                except OSError:
                    # Darwin may report EINVAL for a PID that exited after ps.
                    # Only independent disappearance/identity evidence makes that
                    # harmless; a live unreadable process still fails closed.
                    try:
                        current = table().get(pid)
                        if current and current['start'] == row['start']:
                            complete = False
                    except (OSError, ValueError, subprocess.SubprocessError):
                        complete = False
        # Retain observed descendants even if a helper drops environment on exec.
        changed = True
        while changed:
            changed = False
            for pid, row in rows.items():
                if pid not in owned and row['ppid'] in owned:
                    owned[pid] = row
                    changed = True
        self.known.update(owned)
        return owned, complete

    def send(self, rows, sig):
        """PID+start+nonce recheck before signalling; never signal a shared daemon."""
        sent = set()
        try:
            current = table()
        except (OSError, ValueError, subprocess.SubprocessError):
            return sent
        for pid, row in rows.items():
            if current.get(pid, {}).get('start') == row['start']:
                try:
                    if not has_marker(pid, self.nonce):
                        continue
                    os.kill(pid, sig)
                    sent.add(pid)
                except ProcessLookupError:
                    pass
                except OSError:
                    pass
        return sent


class DeviceState:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.locks = weakref.WeakValueDictionary()

    def load(self, device):
        path = self.root / (device + '.json')
        try:
            state = json.loads(path.read_text())
            if not isinstance(state, dict) or state.get('version') != 1:
                raise ValueError('invalid state')
            return state
        except FileNotFoundError:
            return {"version": 1, "quarantine": None, "active": None}
        except (OSError, ValueError):
            return {"version": 1, "quarantine": {"mode": "orphanPossible", "reason": "unreadable-state"},
                    "active": None}

    def save(self, device, state):
        target = self.root / (device + '.json')
        temp = self.root / ('.' + uuid.uuid4().hex + '.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'w') as out:
                json.dump(state, out, separators=(',', ':'))
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, target)
            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temp.unlink(missing_ok=True)

    @asynccontextmanager
    async def locked(self, device, cancel, deadline):
        lock = self.locks.setdefault(device, asyncio.Lock())
        while lock.locked():
            if cancel.is_set() or time.monotonic() >= deadline:
                raise TimeoutError('device-lock-wait-ended')
            await asyncio.sleep(0.02)
        await lock.acquire()
        fd = None
        try:
            fd = os.open(self.root / (device + '.lock'),
                         os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if cancel.is_set() or time.monotonic() >= deadline:
                        raise TimeoutError('device-lock-wait-ended')
                    await asyncio.sleep(0.02)
            state = self.load(device)
            if state.get('active'):
                # flock release is not proof that a crashed server's CLI died.
                state['quarantine'] = {"mode": "orphanPossible", "reason": "unfinished-intent",
                                       "intent": state['active']}
                state['active'] = None
                self.save(device, state)
            yield state
        finally:
            if fd is not None:
                os.close(fd)
            lock.release()


async def run_cli(cli, argv, cancel, intent_saved, spawned, *, timeout=60, grace=GRACE_SECONDS):
    """One spawn, bounded IO, one TERM round, shielded by caller from repeated cancellation.

    A force kill is always quarantined: process disappearance cannot prove remote cleanup.
    """
    nonce, since = uuid.uuid4().hex, time.time()
    intent = {"nonce": nonce, "created": since, "pid": None, "pgid": None, "start": None}
    intent_saved(intent)  # durable write MUST precede spawn
    if cancel.is_set():
        return None, '', 'cancelled-before-spawn', True, False
    owner = Owner(nonce, since)
    _, inspection_ready = owner.scan()
    if not inspection_ready:
        # Fail before launching any CLI when the host cannot inspect ownership.
        # No descendant exists yet, so this is not an orphan quarantine.
        return None, '', 'ownership-unavailable-before-spawn', True, False
    process = None
    output = [bytearray(), bytearray()]
    streams = {}
    reason = None
    forced = False
    complete = False
    try:
        process = spawn_cli([cli, *argv], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True, close_fds=True,
                                   env={**os.environ, MARKER: nonce, 'IPB_ERROR_FORMAT': 'json'})
        try:
            row = table().get(process.pid)
        except (OSError, ValueError, subprocess.SubprocessError):
            row = None
        if row:
            owner.known[process.pid] = row
        intent.update(pid=process.pid, pgid=process.pid, start=row['start'] if row else None)
        spawned(intent)
        for index, stream in enumerate((process.stdout, process.stderr)):
            os.set_blocking(stream.fileno(), False)
            streams[stream.fileno()] = (index, stream)
        deadline = time.monotonic() + timeout
        term_deadline = None
        quiet_scans = 0
        term_sent = False
        exit_seen = None
        while True:
            for fd, (index, stream) in list(streams.items()):
                try:
                    data = os.read(fd, 65536)
                except BlockingIOError:
                    continue
                if not data:
                    del streams[fd]
                    continue
                limit = MAX_STDOUT if index == 0 else MAX_STDERR
                output[index].extend(data[:max(0, limit - len(output[index]))])
                if len(output[index]) >= limit:
                    reason = reason or 'cli-output-limit'
            code = process.poll()  # independent of pipe EOF and surviving grandchildren
            owned, complete = owner.scan()
            if code is None and process.pid not in owned:
                complete = False
            if code is not None and not owned and complete and not streams:
                quiet_scans += 1
                if quiet_scans >= 2:
                    break
            else:
                quiet_scans = 0
            now = time.monotonic()
            if code is not None and exit_seen is None:
                exit_seen = now
            if cancel.is_set():
                reason = reason or 'cancelled'
            if now >= deadline:
                reason = reason or 'cli-timeout'
            # A final data read and waitpid can race pipe EOF. Allow a bounded
            # drain interval before classifying a genuinely surviving descendant.
            if code is not None and now - exit_seen >= .15 and (owned or streams):
                reason = reason or 'descendants-after-cli-exit'
            if reason and not term_sent:
                # Signal the outer request group ONCE, allowing AX finally to own
                # its independent input/text session. If leader already exited,
                # signal only individually proven surviving request processes.
                root_group = {pid: row for pid, row in owned.items() if row['pgid'] == process.pid}
                sent = owner.send(root_group or owned, signal.SIGTERM)
                if process.pid not in sent and process.poll() is None:
                    # A live unreaped direct child is owned even when host process
                    # inspection is denied. This does not prove descendant cleanup.
                    process.send_signal(signal.SIGTERM)
                term_sent, term_deadline = True, now + grace
            if term_sent and now >= term_deadline:
                if owned or code is None or streams or not complete:
                    forced = True
                    owner.send(owned, signal.SIGKILL)
                    if process.poll() is None:
                        process.kill()
                # Do not wait for pipe EOF from an unknown/escaped child.
                end = time.monotonic() + 1
                while process.poll() is None and time.monotonic() < end:
                    await asyncio.sleep(0.02)
                break
            await asyncio.sleep(0.02)
    except OSError:
        reason = 'cli-spawn-failed' if process is None else 'cli-io-or-state-failed'
        if process is None:
            complete = True
        if process is not None:
            owned, complete = owner.scan()
            owner.send(owned, signal.SIGKILL)
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            forced = True
    finally:
        if process is not None:
            process.stdout.close()
            process.stderr.close()
            if process.poll() is not None:
                process.wait()
    try:
        stdout = output[0].decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        stdout, reason = '', 'invalid-cli-utf8'
    # stderr may contain user input from native tools. Never reflect/persist it.
    return (process.returncode if process else None, stdout, reason, complete, forced)
