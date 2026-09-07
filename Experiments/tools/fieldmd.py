#!/usr/bin/env python3
"""Dump Swift __swift5_fieldmd field descriptors (enum cases / struct fields in declaration order) from an arm64 Mach-O."""
import struct, subprocess, sys, tempfile, os, re

path, wanted = sys.argv[1], sys.argv[2:]
tmp = tempfile.mktemp()
if subprocess.run(['lipo', path, '-thin', 'arm64', '-output', tmp], capture_output=True).returncode != 0:
    tmp = path
data = open(tmp, 'rb').read()
# segments: vmaddr -> fileoff
out = subprocess.run(['otool', '-l', tmp], capture_output=True, text=True).stdout
segs = []; sect = None
cur = {}
for line in out.splitlines():
    line = line.strip()
    if line.startswith('segname'): cur = {'segname': line.split()[1]}
    elif line.startswith('vmaddr') and 'segname' in cur: cur['vmaddr'] = int(line.split()[1], 16)
    elif line.startswith('fileoff') and 'segname' in cur:
        cur['fileoff'] = int(line.split()[1]); segs.append(cur); cur = {}
    if line.startswith('sectname'):
        sname = line.split()[1]
        if sname == '__swift5_fieldmd': sect = {}
    elif sect is not None and 'size' not in sect:
        if line.startswith('addr'): sect['addr'] = int(line.split()[1], 16)
        elif line.startswith('size'): sect['size'] = int(line.split()[1], 16)
def v2f(vm):
    for s in segs:
        if 'vmaddr' in s and s['vmaddr'] <= vm and vm < s['vmaddr'] + 0x40000000:
            best = s
    for s in sorted(segs, key=lambda s: s['vmaddr']):
        pass
    cand = [s for s in segs if s['vmaddr'] <= vm]
    s = max(cand, key=lambda s: s['vmaddr'])
    return vm - s['vmaddr'] + s['fileoff']
def cstr(vm):
    off = v2f(vm); end = data.index(b'\0', off); return data[off:end]
def ctx_name(vm):
    # context descriptor: flags u32 @0, parent rel @4, name rel @8
    parts = []
    depth = 0
    while vm and depth < 8:
        off = v2f(vm)
        if off < 0 or off + 12 > len(data): break
        flags, parent_rel, name_rel = struct.unpack_from('<Iii', data, off)
        if parent_rel & 1: parent_rel = 0  # indirect parent pointer: stop walking
        kind = flags & 0x1f
        if name_rel and kind in (0, 16, 17, 18, 19):
            try: parts.append(cstr(vm + 8 + name_rel).decode('ascii', 'replace'))
            except Exception: break
        if not parent_rel: break
        vm = vm + 4 + parent_rel; depth += 1
    return '.'.join(reversed(parts))
def mangled(vm):
    off = v2f(vm); s = ''
    while data[off] != 0:
        b = data[off]
        if b == 1:
            rel = struct.unpack_from('<i', data, off + 1)[0]
            s += ctx_name(vm + (off - v2f(vm)) + 1 + rel); off += 5; continue
        if b == 2:
            s += '<indirect>'; off += 5; continue
        if 3 <= b <= 0x1f:
            s += '<sym%d>' % b; off += 5; continue
        s += chr(b); off += 1
    return s
pos = sect['addr']; endpos = sect['addr'] + sect['size']
while pos < endpos:
    off = v2f(pos)
    tn_rel, sup_rel, kind, recsize, nfields = struct.unpack_from('<iiHHI', data, off)
    name = mangled(pos + tn_rel) if tn_rel else '?'
    pretty = re.sub(r'(\d+)', lambda m: '.', name)
    if any(w in name for w in wanted):
        print(f"{name} kind={kind} fields={nfields}")
        for i in range(nfields):
            foff = off + 16 + i * recsize; fvm = pos + 16 + i * recsize
            flags, ftn_rel, fn_rel = struct.unpack_from('<Iii', data, foff)
            fname = cstr(fvm + 8 + fn_rel).decode() if fn_rel else '?'
            ftype = mangled(fvm + 4 + ftn_rel) if ftn_rel else ''
            print(f"  [{i}] {fname}  {ftype}")
    pos += 16 + nfields * recsize
