import sys,re
# Minimal HID report-descriptor parser: prints Input fields per report ID with absolute bit offsets.
PAGES={0x01:"GenericDesktop",0x07:"Keyboard",0x09:"Button",0x0c:"Consumer",0x0d:"Digitizer",0xff00:"AppleVendor",0xff01:"AppleVendorKeyboard",0xff60:"AppleVendorMultitouch",0xffa0:"AppleVendorDisplay"}
DIG={0x01:"Digitizer",0x02:"Pen",0x04:"TouchScreen",0x22:"Finger",0x23:"DeviceSettings",0x30:"TipPressure",0x32:"InRange",0x33:"Touch",0x38:"Transducer Index",0x42:"TipSwitch",0x47:"TouchValid",0x48:"Width",0x49:"Height",0x51:"ContactIdentifier",0x54:"ContactCount",0x55:"ContactCountMaximum",0x56:"ScanTime",0x5b:"Cancel"}
GD={0x30:"X",0x31:"Y",0x32:"Z",0x38:"Wheel",0x39:"HatSwitch",0x02:"Mouse",0x04:"Joystick",0x05:"GamePad",0x06:"Keyboard",0x08:"Multi-axis",0x0e:"SystemMultiAxis"}
def name(page,usage):
    p=PAGES.get(page,hex(page))
    if page==0x0d: u=DIG.get(usage,hex(usage))
    elif page==0x01: u=GD.get(usage,hex(usage))
    else: u=hex(usage)
    return f"{p}/{u}"
def parse(b):
    i=0; g={}; usages=[]; umin=None; rid=0; off={}; depth=0
    while i<len(b):
        pre=b[i]; sz=pre&3; sz=4 if sz==3 else sz; typ=(pre>>2)&3; tag=pre>>4; i+=1
        val=int.from_bytes(b[i:i+sz],'little') if sz else 0; i+=sz
        if typ==1: # global
            if tag==0: g['page']=val
            elif tag==1: g['lmin']=val
            elif tag==2: g['lmax']=val
            elif tag==7: g['rsize']=val
            elif tag==8: rid=val; off.setdefault(rid,8)
            elif tag==9: g['rcount']=val
        elif typ==2: # local
            if tag==0: usages.append(val if val>0xffff else (g.get('page',0)<<16)|val)
            elif tag==1: umin=val
            elif tag==2:
                usages += [ (g.get('page',0)<<16)|u for u in range(umin,val+1)]
        elif typ==0: # main
            if tag==8: # Input
                off.setdefault(rid,8)
                rs=g.get('rsize',0); rc=g.get('rcount',0); const=val&1; var=(val>>1)&1
                if const or not usages:
                    print(f"  rid={rid:2d} bit {off[rid]:4d}..{off[rid]+rs*rc:4d}  {'PAD' if const else 'ARRAY'} {rc}x{rs}b" + ("" if const else f" usages={[name(u>>16,u&0xffff) for u in usages][:6]}"))
                else:
                    for k in range(rc):
                        u=usages[k] if k<len(usages) else usages[-1]
                        print(f"  rid={rid:2d} bit {off[rid]+k*rs:4d}..{off[rid]+(k+1)*rs:4d}  {name(u>>16,u&0xffff)}  ({rs}b, log {g.get('lmin',0)}..{g.get('lmax',0)})")
                off[rid]+=rs*rc; usages=[]
            elif tag==10: print(f"  {'  '*depth}collection {val} usage={[name(u>>16,u&0xffff) for u in usages]}"); depth+=1; usages=[]
            elif tag==12: depth-=1; usages=[]
            else: usages=[]
    for r,o in off.items(): print(f"  => report {r}: {o} bits = {o//8} bytes")
for line in open(sys.argv[1]):
    m=re.match(r'(\w+) descriptor (\d+) bytes: (.*)',line)
    if m:
        print(f"\n### {m.group(1)}"); parse(bytes.fromhex(m.group(3).replace(' ','')))
