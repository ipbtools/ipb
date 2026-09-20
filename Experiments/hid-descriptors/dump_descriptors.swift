import Foundation
@_silgen_name("call_indirect_getter") func callIndirect(_ fn: UnsafeRawPointer, _ buf: UnsafeMutableRawPointer)
let h = dlopen("/Library/Developer/PrivateFrameworks/CoreDevice.framework/Frameworks/UniversalHID.framework/UniversalHID", RTLD_NOW)!
struct W { var a: UInt64; var b: UInt64 }
for name in CommandLine.arguments.dropFirst() {
    let sym = "$s12UniversalHID\(name)V10descriptorAA19HIDReportDescriptorVvgZ"
    guard let p = dlsym(h, sym) else { print(name, "dlsym failed"); continue }
    let buf = UnsafeMutableRawPointer.allocate(byteCount: 64, alignment: 16); buf.initializeMemory(as: UInt8.self, repeating: 0, count: 64)
    callIndirect(UnsafeRawPointer(p), buf)
    let w = buf.load(as: W.self)
    let d = unsafeBitCast(w, to: Data.self)
    if d.count > 0 && d.count < 4096 {
        print("\(name) descriptor \(d.count) bytes: " + d.map { String(format: "%02x", $0) }.joined(separator: " "))
    } else { print("\(name): words \(String(w.a, radix: 16)) \(String(w.b, radix: 16)) not a Data") }
}
