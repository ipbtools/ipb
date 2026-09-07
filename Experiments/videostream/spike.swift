// Stage-1 spike: drive Apple's CoreDevice client from our own process via @_silgen_name shims.
// Evidence only (AGENTS.md rule 2); not part of the product.
import Foundation
setbuf(stdout, nil)

typealias RegisterBundle = @convention(c) (AnyObject) -> Void
typealias InitServices = @convention(c) () -> Void

final class DeviceManagerShim {
    @_silgen_name("$s10CoreDevice0B7ManagerC6sharedACvgZ")
    static func shared() -> DeviceManagerShim
    @_silgen_name("$s10CoreDevice0B7ManagerC10allDevicesSayAA06RemoteB0CGyF")
    func allDevices() -> [RemoteDeviceShim]
}
final class RemoteDeviceShim {
    @_silgen_name("$s10CoreDevice06RemoteB0C11descriptionSSvg")
    func describe() -> String
    @_silgen_name("$s10CoreDevice06RemoteB0C26registerConnectionProvideryyF")
    func registerConnectionProvider()
    @_silgen_name("$s10CoreDevice06RemoteB0C19listUsageAssertionsSayAA0E20AssertionInformationVGyYaKF")
    func listUsageAssertions() async throws -> [AnyObject]
}

let cd = dlopen("/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/CoreDevice", RTLD_NOW)
precondition(cd != nil, "CoreDevice failed to load")
let addBundle = unsafeBitCast(dlsym(cd, "_coredevice_xpc_add_bundle"), to: RegisterBundle.self)
let initServices = unsafeBitCast(dlsym(cd, "_coredevice_xpc_init_services"), to: InitServices.self)
addBundle(Bundle(path: "/Library/Developer/PrivateFrameworks/CoreDevice.framework")!)
initServices()

let manager = DeviceManagerShim.shared()
print("DeviceManager.shared =", Unmanaged.passUnretained(manager).toOpaque())
// DeviceManager checks in asynchronously and may deliver events on the main queue: pump the run loop.
func pump(_ seconds: Double) { RunLoop.main.run(until: Date(timeIntervalSinceNow: seconds)) }
let wanted = ProcessInfo.processInfo.environment["SPIKE_DEVICE"] ?? ""
var devices: [RemoteDeviceShim] = []
for tick in 1...20 {
    pump(0.5)
    devices = manager.allDevices()
    if let d = devices.first(where: { wanted.isEmpty ? true : $0.describe().contains(wanted) }), d.describe().contains("(Connected") { print("connected after \(Double(tick) * 0.5)s"); break }
}
print("allDevices count =", devices.count)
for d in devices { print("  ", d.describe()) }

// ---- stage 2: MediaStreamSupport.supportInfo through Apple's client (captures the wire envelope) ----
struct SupportInfo168 { var w: (UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64, UInt64) }
struct MediaStreamSupportShim {
    var device: RemoteDeviceShim
    @_silgen_name("$s28CoreDeviceMediaStreamSupport0cdE0V6deviceAC0aB006RemoteB0C_tcfC")
    init(device: RemoteDeviceShim)
    // Generic result => address-only => passed as an explicit @out buffer (x0), matching the real getter.
    @_silgen_name("$s28CoreDeviceMediaStreamSupport0cdE0V11supportInfo0aB00bcD0V0eG8ResponseVvg")
    func supportInfo<T>() async throws -> T
}
func describeAs(_ typeName: String, _ value: SupportInfo168) -> String {
    guard let t = _typeByName(typeName) else { return "<type \(typeName) absent>" }
    func open<T>(_: T.Type) -> String { var v = value; return withUnsafePointer(to: &v) { String(reflecting: $0.withMemoryRebound(to: T.self, capacity: 1) { $0.pointee }) } }
    return _openExistential(t, do: open)
}
let mss = dlopen("/Library/Developer/PrivateFrameworks/CoreDevice.framework/Versions/A/Frameworks/CoreDeviceMediaStreamSupport.framework/Versions/A/CoreDeviceMediaStreamSupport", RTLD_NOW)
precondition(mss != nil, "CoreDeviceMediaStreamSupport failed to load")
if let device = devices.first(where: { wanted.isEmpty ? true : $0.describe().contains(wanted) }) {
    print("== stage 2 on", device.describe())
    if ProcessInfo.processInfo.environment["SPIKE_ASSERT"] == "1" {
        var d2 = false
        Task { do { let a = try await device.listUsageAssertions(); print("listUsageAssertions ->", a.count, "entries") } catch { print("listUsageAssertions error:", error) }; d2 = true }
        let dl = Date(timeIntervalSinceNow: 20); while !d2 && Date() < dl { pump(0.2) }
        if !d2 { print("listUsageAssertions: timeout") }
        exit(0)
    }
    if ProcessInfo.processInfo.environment["SPIKE_REGISTER"] != "0" { device.registerConnectionProvider(); print("registerConnectionProvider() called"); pump(1.0) }
    let support = MediaStreamSupportShim(device: device)
    var done = false
    Task {
        do {
            let info: SupportInfo168 = try await support.supportInfo()
            print("supportInfo =", describeAs("10CoreDevice17DeviceMediaStreamV19SupportInfoResponseV", info))
        } catch { print("supportInfo error:", error) }
        done = true
    }
    let deadline = Date(timeIntervalSinceNow: 25)
    while !done && Date() < deadline { pump(0.2) }
    if !done { print("supportInfo: timeout") }
}
