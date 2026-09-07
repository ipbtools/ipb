import json,sys,subprocess,bisect,re,glob,os
f=sys.argv[1] if len(sys.argv)>1 else max(glob.glob(os.path.expanduser('~/Library/Logs/DiagnosticReports/spike2*')),key=os.path.getmtime)
raw=open(f).read(); body=json.loads(raw.split('\n',1)[1])
imgs=body['usedImages']; th=[t for t in body['threads'] if t.get('triggered')][0]
print(os.path.basename(f), body['exception'].get('subtype'), body['exception'].get('type'))
tables={}
def table(path):
    if path in tables: return tables[path]
    out=subprocess.run(['nm','-n',path],capture_output=True,text=True).stdout
    syms=[]; active=True; seen=False
    for line in out.splitlines():
        if '(for architecture' in line: seen=True; active=('arm64)' in line and 'arm64e' not in line); continue
        if seen and not active: continue
        m=re.match(r'^([0-9a-f]+)\s+[Tt]\s+(\S+)$',line)
        if m: syms.append((int(m.group(1),16),m.group(2)))
    syms.sort(); tables[path]=syms; return syms
for fr in th['frames'][:14]:
    img=imgs[fr['imageIndex']]; name=img.get('name') or '?'; path=img.get('path','')
    sym=fr.get('symbol','')
    if not sym and path and os.path.exists(path):
        syms=table(path)
        if syms:
            i=bisect.bisect_right([a for a,_ in syms],fr['imageOffset'])-1
            addr,s=syms[max(i,0)]
            sym=subprocess.run(['xcrun','swift-demangle'],input=s,capture_output=True,text=True).stdout.strip()+f" +0x{fr['imageOffset']-addr:x}"
    print(f"  {name:28s} +0x{fr['imageOffset']:x} {sym[:150]}")
