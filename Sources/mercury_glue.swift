import Foundation
import XPC
import Darwin
import ObjectiveC

struct MercuryXPCDictionary {
    var word0: UInt = 0
    var word1: UInt = 0
    var word2: UInt = 0
    var word3: UInt = 0
    var word4: UInt = 0
    var word5: UInt = 0
    var word6: UInt = 0
    var word7: UInt = 0
}

struct UHIDRequestWords {
    var word0: UInt64 = 0
    var word1: UInt64 = 0
    var word2: UInt64 = 0
    var word3: UInt64 = 0
}

var retainedCoreDeviceStrings: [String] = []

@_silgen_name("$s7Mercury19RemoteXPCConnectionC10unsafePeer4fromAA17XPCPeerConnection_pSo24OS_xpc_remote_connectionC_tFZ")
func mercuryUnsafePeer(_ connection: UnsafeMutableRawPointer?) -> AnyObject

@_silgen_name("$s7Mercury19RemoteXPCConnectionC10unsafePeer4from15forServiceNamedAA17XPCPeerConnection_pSo24OS_xpc_remote_connectionC_SStFZ")
func mercuryUnsafePeerForService(_ connection: UnsafeMutableRawPointer?, _ serviceName: String) -> AnyObject

@_silgen_name("$s7Mercury13XPCDictionaryVyACSo13OS_xpc_object_pcfC")
func mercuryXPCDictionary(_ object: xpc_object_t) -> MercuryXPCDictionary

@_silgen_name("$s7Mercury13XPCDictionaryV16debugDescriptionSSvg")
func mercuryXPCDictionaryDebugDescription(_ dictionary: MercuryXPCDictionary) -> String

@_silgen_name("mercury_xpc_connection_send_abi")
func mercuryXPCConnectionSendABI(_ connection: UnsafeMutableRawPointer, _ message: UnsafeRawPointer)

@_silgen_name("mercury_xpc_connection_send_sync_abi")
func mercuryXPCConnectionSendSyncABI(_ connection: UnsafeMutableRawPointer, _ message: UnsafeRawPointer, _ reply: UnsafeMutableRawPointer)

@_silgen_name("mercury_xpc_connection_send_value_abi")
func mercuryXPCConnectionSendValueABI(
    _ connection: UnsafeMutableRawPointer,
    _ value: UnsafeRawPointer,
    _ metadata: UnsafeRawPointer,
    _ decodableWitness: UnsafeRawPointer,
    _ encodableWitness: UnsafeRawPointer
) -> UnsafeRawPointer?

@_silgen_name("mercury_xpc_connection_send_sync_value_abi")
func mercuryXPCConnectionSendSyncValueABI(
    _ connection: UnsafeMutableRawPointer,
    _ value: UnsafeRawPointer,
    _ requestMetadata: UnsafeRawPointer,
    _ requestDecodableWitness: UnsafeRawPointer,
    _ requestEncodableWitness: UnsafeRawPointer,
    _ replyMetadata: UnsafeRawPointer,
    _ replyDecodableWitness: UnsafeRawPointer,
    _ replyEncodableWitness: UnsafeRawPointer,
    _ reply: UnsafeMutableRawPointer
) -> Int32

@_silgen_name("$s7Mercury13XPCDictionaryV14toNSDictionarySo0D0CSgyF")
func mercuryXPCDictionaryToNSDictionary(_ dictionary: MercuryXPCDictionary) -> NSDictionary?

@_silgen_name("uhid_request_description_abi")
func uhidRequestDescriptionABI(_ request: UnsafeRawPointer) -> String

@_silgen_name("uhid_connected_services_description_abi")
func uhidConnectedServicesDescriptionABI(_ connectedServices: UnsafeRawPointer) -> String

@_silgen_name("coredevice_universalhid_send_dispatch_abi")
func coredeviceUniversalHIDSendDispatchABI(
    _ service: UnsafeMutableRawPointer,
    _ witness: UnsafeRawPointer,
    _ report: UnsafeRawPointer,
    _ serviceID: UInt64
) -> Int32

@_silgen_name("coredevice_universalhid_reset_dispatch_abi")
func coredeviceUniversalHIDResetDispatchABI(
    _ service: UnsafeMutableRawPointer,
    _ witness: UnsafeRawPointer,
    _ serviceID: UInt64
) -> Int32

@_silgen_name("coredevice_universalhid_barrier_dispatch_abi")
func coredeviceUniversalHIDBarrierDispatchABI(
    _ service: UnsafeMutableRawPointer,
    _ witness: UnsafeRawPointer
) -> Int32

@_silgen_name("coredevice_hidbutton_custom_dispatch_abi")
func coredeviceHIDButtonCustomDispatchABI(
    _ button: UnsafeMutableRawPointer,
    _ witness: UnsafeRawPointer,
    _ usagePage: UInt64,
    _ usageCode: UInt64,
    _ state: UInt8
) -> Int32

@_silgen_name("coredevice_hidbutton_barrier_dispatch_abi")
func coredeviceHIDButtonBarrierDispatchABI(
    _ button: UnsafeMutableRawPointer,
    _ witness: UnsafeRawPointer
) -> Int32

@_silgen_name("coredevice_hiddigitizer_cgpoint_dispatch_abi")
func coredeviceHIDDigitizerCGPointDispatchABI(
    _ digitizer: UnsafeMutableRawPointer,
    _ witness: UnsafeRawPointer,
    _ pointOneX: Double,
    _ pointOneY: Double,
    _ pointTwoX: Double,
    _ pointTwoY: Double,
    _ pointTwoOptionalTag: UInt64,
    _ eventType: UInt64,
    _ edge: UInt64,
    _ targetLow: UInt64,
    _ targetHigh: UInt64
) -> Int32

typealias SwiftMetadataAccessor = @convention(c) () -> UnsafeRawPointer
typealias SwiftConformsToProtocol = @convention(c) (UnsafeRawPointer, UnsafeRawPointer) -> UnsafeRawPointer?

func dlsymRequired<T>(_ symbol: String, as type: T.Type) -> T {
    guard let pointer = dlsym(dlopen(nil, RTLD_NOW), symbol) else {
        fatalError("missing symbol \(symbol)")
    }
    return unsafeBitCast(pointer, to: type)
}

func metadataAndCodableWitnesses(_ metadataSymbol: String, label: String) -> (UnsafeRawPointer, UnsafeRawPointer, UnsafeRawPointer) {
    let metadataAccessor = dlsymRequired(
        metadataSymbol,
        as: SwiftMetadataAccessor.self
    )
    let conforms = dlsymRequired("swift_conformsToProtocol", as: SwiftConformsToProtocol.self)
    guard let decodableProtocol = dlsym(dlopen(nil, RTLD_NOW), "$sSeMp") else {
        fatalError("missing Swift.Decodable protocol descriptor")
    }
    guard let encodableProtocol = dlsym(dlopen(nil, RTLD_NOW), "$sSEMp") else {
        fatalError("missing Swift.Encodable protocol descriptor")
    }
    let metadata = metadataAccessor()
    guard let decodableWitness = conforms(metadata, decodableProtocol) else {
        fatalError("\(label) does not conform to Decodable")
    }
    guard let witness = conforms(metadata, encodableProtocol) else {
        fatalError("\(label) does not conform to Encodable")
    }
    return (metadata, decodableWitness, witness)
}

func uhidRequestMetadataAndCodableWitnesses() -> (UnsafeRawPointer, UnsafeRawPointer, UnsafeRawPointer) {
    metadataAndCodableWitnesses(
        "$s19CoreDeviceUtilities29DDIUniversalHIDServicePayloadO7RequestOMa",
        label: "DDIUniversalHIDServicePayload.Request"
    )
}

func uhidConnectedServicesMetadataAndCodableWitnesses() -> (UnsafeRawPointer, UnsafeRawPointer, UnsafeRawPointer) {
    metadataAndCodableWitnesses(
        "$s19CoreDeviceUtilities29DDIUniversalHIDServicePayloadO17ConnectedServicesVMa",
        label: "DDIUniversalHIDServicePayload.ConnectedServices"
    )
}

func makeUHIDSendRequest(data: Data, serviceID: UInt64) -> UHIDRequestWords {
    var request = UHIDRequestWords()
    withUnsafeMutableBytes(of: &request) { requestBytes in
        for index in requestBytes.indices {
            requestBytes[index] = 0
        }
        withUnsafeBytes(of: data) { dataBytes in
            requestBytes.copyBytes(from: dataBytes.prefix(16))
        }
        requestBytes.storeBytes(of: serviceID, toByteOffset: 16, as: UInt64.self)
        let dataWord1 = requestBytes.load(fromByteOffset: 8, as: UInt64.self)
        requestBytes.storeBytes(of: dataWord1 | 0x2000_0000_0000_0000, toByteOffset: 8, as: UInt64.self)
        requestBytes[24] = 0
    }
    return request
}

func makeUHIDConnectedServicesRequest() -> UHIDRequestWords {
    var request = UHIDRequestWords()
    withUnsafeMutableBytes(of: &request) { requestBytes in
        for index in requestBytes.indices {
            requestBytes[index] = 0
        }
        requestBytes[24] = 4
    }
    return request
}

func swiftProtocolWitness(for classObject: AnyClass, protocolSymbol: String) -> UnsafeRawPointer {
    let conforms = dlsymRequired("swift_conformsToProtocol", as: SwiftConformsToProtocol.self)
    guard let proto = dlsym(dlopen(nil, RTLD_NOW), protocolSymbol) else {
        fatalError("missing protocol descriptor \(protocolSymbol)")
    }
    let metadata = unsafeBitCast(classObject, to: UnsafeRawPointer.self)
    guard let witness = conforms(metadata, proto) else {
        fatalError("\(classObject) does not conform to \(protocolSymbol)")
    }
    return witness
}

func storePointer(_ base: UnsafeMutableRawPointer, offset: Int, _ value: UnsafeRawPointer?) {
    base.advanced(by: offset).storeBytes(of: UInt(bitPattern: value), as: UInt.self)
}

func storeString(_ base: UnsafeMutableRawPointer, offset: Int, _ value: inout String) {
    withUnsafeBytes(of: &value) { bytes in
        base.advanced(by: offset).copyMemory(from: bytes.baseAddress!, byteCount: min(bytes.count, 16))
    }
}

func makeDDIUniversalHIDService(_ connection: UnsafeMutableRawPointer?) -> (UnsafeMutableRawPointer, UnsafeRawPointer) {
    let serviceName = ProcessInfo.processInfo.environment["HIDCTL_MERCURY_SERVICE"] ?? "com.apple.coredevice.hid.universalhidservice"
    let featureIdentifier = ProcessInfo.processInfo.environment["HIDCTL_FEATURE_ID"] ?? "com.apple.coredevice.feature.remote.universalhidservice"

    let peer = mercuryUnsafePeerForService(connection, serviceName)
    guard let peerClass = object_getClass(peer) else {
        fatalError("unable to get Mercury peer class")
    }
    let peerWitness = swiftProtocolWitness(
        for: peerClass,
        protocolSymbol: "$s7Mercury17XPCPeerConnectionMp"
    )

    guard let hidxpcClass = objc_getClass("_TtC10CoreDevice13HIDXPCService") as? AnyClass else {
        fatalError("missing CoreDevice.HIDXPCService class")
    }
    guard let ddiClass = objc_getClass("_TtC10CoreDevice22DDIUniversalHIDService") as? AnyClass else {
        fatalError("missing CoreDevice.DDIUniversalHIDService class")
    }

    guard let hidxpcObject = class_createInstance(hidxpcClass, 0) else {
        fatalError("unable to create HIDXPCService")
    }
    guard let ddiObject = class_createInstance(ddiClass, 0) else {
        fatalError("unable to create DDIUniversalHIDService")
    }

    let peerPointer = Unmanaged.passRetained(peer).toOpaque()
    let hidxpcPointer = Unmanaged.passRetained(hidxpcObject as AnyObject).toOpaque()
    let ddiPointer = Unmanaged.passRetained(ddiObject as AnyObject).toOpaque()

    storePointer(hidxpcPointer, offset: 16, UnsafeRawPointer(peerPointer))
    storePointer(hidxpcPointer, offset: 24, peerWitness)
    var retainedFeatureIdentifier = featureIdentifier
    storeString(hidxpcPointer, offset: 32, &retainedFeatureIdentifier)
    retainedCoreDeviceStrings.append(retainedFeatureIdentifier)

    storePointer(ddiPointer, offset: 16, UnsafeRawPointer(hidxpcPointer))
    ddiPointer.advanced(by: 24).storeBytes(of: UInt(0), as: UInt.self)
    ddiPointer.advanced(by: 32).storeBytes(of: UInt(0), as: UInt.self)

    let ddiWitness = swiftProtocolWitness(
        for: ddiClass,
        protocolSymbol: "$s10CoreDevice19UniversalHIDServiceMp"
    )

    if ProcessInfo.processInfo.environment["HIDCTL_QUIET"] == nil {
        fputs("coredevice hid: peer=\(type(of: peer)) serviceName=\(serviceName) feature=\(featureIdentifier)\n", stderr)
        fputs("coredevice hid: peerWitness=\(peerWitness) ddiWitness=\(ddiWitness)\n", stderr)
    }
    return (ddiPointer, ddiWitness)
}

func makeIndigoHIDButton(_ connection: UnsafeMutableRawPointer?) -> (UnsafeMutableRawPointer, UnsafeRawPointer) {
    let serviceName = ProcessInfo.processInfo.environment["HIDCTL_BUTTON_MERCURY_SERVICE"]
    let featureIdentifier = ProcessInfo.processInfo.environment["HIDCTL_BUTTON_FEATURE_ID"] ?? "com.apple.coredevice.feature.remote.hid.button"

    let peer: AnyObject
    if let serviceName, !serviceName.isEmpty {
        peer = mercuryUnsafePeerForService(connection, serviceName)
    } else {
        peer = mercuryUnsafePeer(connection)
    }

    guard let peerClass = object_getClass(peer) else {
        fatalError("unable to get Mercury peer class")
    }
    let peerWitness = swiftProtocolWitness(
        for: peerClass,
        protocolSymbol: "$s7Mercury17XPCPeerConnectionMp"
    )

    guard let buttonClass = objc_getClass("_TtC10CoreDevice15IndigoHIDButton") as? AnyClass else {
        fatalError("missing CoreDevice.IndigoHIDButton class")
    }
    guard let buttonObject = class_createInstance(buttonClass, 0) else {
        fatalError("unable to create IndigoHIDButton")
    }

    let peerPointer = Unmanaged.passRetained(peer).toOpaque()
    let buttonPointer = Unmanaged.passRetained(buttonObject as AnyObject).toOpaque()

    storePointer(buttonPointer, offset: 16, UnsafeRawPointer(peerPointer))
    storePointer(buttonPointer, offset: 24, peerWitness)
    var retainedFeatureIdentifier = featureIdentifier
    storeString(buttonPointer, offset: 32, &retainedFeatureIdentifier)
    retainedCoreDeviceStrings.append(retainedFeatureIdentifier)

    let buttonWitness = swiftProtocolWitness(
        for: buttonClass,
        protocolSymbol: "$s10CoreDevice9HIDButtonMp"
    )

    if ProcessInfo.processInfo.environment["HIDCTL_QUIET"] == nil {
        fputs("coredevice button: peer=\(type(of: peer)) serviceName=\(serviceName ?? "<base>") feature=\(featureIdentifier)\n", stderr)
        fputs("coredevice button: peerWitness=\(peerWitness) buttonWitness=\(buttonWitness)\n", stderr)
    }
    return (buttonPointer, buttonWitness)
}

func makeIndigoHIDDigitizer(_ connection: UnsafeMutableRawPointer?) -> (UnsafeMutableRawPointer, UnsafeRawPointer) {
    let serviceName = ProcessInfo.processInfo.environment["HIDCTL_DIGITIZER_MERCURY_SERVICE"]
    let featureIdentifier = ProcessInfo.processInfo.environment["HIDCTL_DIGITIZER_FEATURE_ID"] ?? "com.apple.coredevice.feature.remote.hid.digitizer"

    let peer: AnyObject
    if let serviceName, !serviceName.isEmpty {
        peer = mercuryUnsafePeerForService(connection, serviceName)
    } else {
        peer = mercuryUnsafePeer(connection)
    }

    guard let peerClass = object_getClass(peer) else {
        fatalError("unable to get Mercury peer class")
    }
    let peerWitness = swiftProtocolWitness(
        for: peerClass,
        protocolSymbol: "$s7Mercury17XPCPeerConnectionMp"
    )

    guard let digitizerClass = objc_getClass("_TtC10CoreDevice18IndigoHIDDigitizer") as? AnyClass else {
        fatalError("missing CoreDevice.IndigoHIDDigitizer class")
    }
    guard let digitizerObject = class_createInstance(digitizerClass, 0) else {
        fatalError("unable to create IndigoHIDDigitizer")
    }

    let peerPointer = Unmanaged.passRetained(peer).toOpaque()
    let digitizerPointer = Unmanaged.passRetained(digitizerObject as AnyObject).toOpaque()

    storePointer(digitizerPointer, offset: 16, UnsafeRawPointer(peerPointer))
    storePointer(digitizerPointer, offset: 24, peerWitness)
    var retainedFeatureIdentifier = featureIdentifier
    storeString(digitizerPointer, offset: 32, &retainedFeatureIdentifier)
    retainedCoreDeviceStrings.append(retainedFeatureIdentifier)

    let digitizerWitness = swiftProtocolWitness(
        for: digitizerClass,
        protocolSymbol: "$s10CoreDevice12HIDDigitizerMp"
    )

    if ProcessInfo.processInfo.environment["HIDCTL_QUIET"] == nil {
        fputs("coredevice digitizer: peer=\(type(of: peer)) serviceName=\(serviceName ?? "<base>") feature=\(featureIdentifier)\n", stderr)
        fputs("coredevice digitizer: peerWitness=\(peerWitness) digitizerWitness=\(digitizerWitness)\n", stderr)
    }
    return (digitizerPointer, digitizerWitness)
}

@_cdecl("mercury_send_xpc_message")
public func mercurySendXPCMessage(_ connection: UnsafeMutableRawPointer?, _ message: xpc_object_t?) -> Int32 {
    guard let connection else {
        fputs("mercury: remote connection is null\n", stderr)
        return 2
    }
    guard let message else {
        fputs("mercury: message is null\n", stderr)
        return 2
    }

    fputs("mercury: entering unsafePeer\n", stderr)
    let serviceName = ProcessInfo.processInfo.environment["HIDCTL_MERCURY_SERVICE"] ?? "com.apple.coredevice.hid.universal"
    fputs("mercury typed: unsafePeer for service \(serviceName)\n", stderr)
    let peer = mercuryUnsafePeerForService(connection, serviceName)
    fputs("mercury: unsafePeer returned \(type(of: peer))\n", stderr)
    fputs("mercury: wrapping xpc dictionary\n", stderr)
    let dictionary = mercuryXPCDictionary(message)
    fputs(String(format: "mercury: wrapped dictionary words=%016llx %016llx\n", dictionary.word0, dictionary.word1), stderr)
    fputs("mercury: sending message\n", stderr)
    let peerPointer = Unmanaged.passUnretained(peer).toOpaque()
    withUnsafePointer(to: dictionary) { dictionaryPointer in
        mercuryXPCConnectionSendABI(peerPointer, UnsafeRawPointer(dictionaryPointer))
    }
    fputs("mercury: send returned\n", stderr)
    return 0
}

@_cdecl("mercury_send_xpc_message_sync")
public func mercurySendXPCMessageSync(_ connection: UnsafeMutableRawPointer?, _ message: xpc_object_t?) -> Int32 {
    guard let connection else {
        fputs("mercury sync: remote connection is null\n", stderr)
        return 2
    }
    guard let message else {
        fputs("mercury sync: message is null\n", stderr)
        return 2
    }

    fputs("mercury sync: entering unsafePeer\n", stderr)
    let serviceName = ProcessInfo.processInfo.environment["HIDCTL_MERCURY_SERVICE"] ?? "com.apple.coredevice.hid.universal"
    fputs("mercury typed: unsafePeer for service \(serviceName)\n", stderr)
    let peer = mercuryUnsafePeerForService(connection, serviceName)
    fputs("mercury sync: unsafePeer returned \(type(of: peer))\n", stderr)
    let dictionary = mercuryXPCDictionary(message)
    var reply = MercuryXPCDictionary()
    let peerPointer = Unmanaged.passUnretained(peer).toOpaque()
    fputs("mercury sync: sending message\n", stderr)
    withUnsafePointer(to: dictionary) { dictionaryPointer in
        withUnsafeMutablePointer(to: &reply) { replyPointer in
            mercuryXPCConnectionSendSyncABI(peerPointer, UnsafeRawPointer(dictionaryPointer), UnsafeMutableRawPointer(replyPointer))
        }
    }
    fputs(String(format: "mercury sync: reply words=%016llx %016llx\n", reply.word0, reply.word1), stderr)
    if let nsDictionary = mercuryXPCDictionaryToNSDictionary(reply) {
        fputs("mercury sync reply NSDictionary: \(nsDictionary)\n", stderr)
    } else {
        fputs("mercury sync reply NSDictionary: <nil>\n", stderr)
    }
    return 0
}

@_cdecl("mercury_send_uhid_request_value")
public func mercurySendUHIDRequestValue(
    _ connection: UnsafeMutableRawPointer?,
    _ bytes: UnsafePointer<UInt8>?,
    _ length: Int,
    _ serviceID: UInt64
) -> Int32 {
    guard let connection else {
        fputs("mercury typed: remote connection is null\n", stderr)
        return 2
    }
    guard let bytes, length >= 0 else {
        fputs("mercury typed: report bytes are null\n", stderr)
        return 2
    }

    let data = Data(bytes: bytes, count: length)
    var request = makeUHIDSendRequest(data: data, serviceID: serviceID)
    withUnsafePointer(to: &request) { requestPointer in
        fputs("mercury typed request: \(uhidRequestDescriptionABI(UnsafeRawPointer(requestPointer)))\n", stderr)
    }

    let serviceName = ProcessInfo.processInfo.environment["HIDCTL_MERCURY_SERVICE"] ?? "com.apple.coredevice.hid.universal"
    fputs("mercury typed: unsafePeer for service \(serviceName)\n", stderr)
    let peer = mercuryUnsafePeerForService(connection, serviceName)
    let peerPointer = Unmanaged.passUnretained(peer).toOpaque()
    let (metadata, decodableWitness, encodableWitness) = uhidRequestMetadataAndCodableWitnesses()
    let errorPointer = withUnsafePointer(to: &request) { requestPointer in
        mercuryXPCConnectionSendValueABI(
            peerPointer,
            UnsafeRawPointer(requestPointer),
            metadata,
            decodableWitness,
            encodableWitness
        )
    }
    if let errorPointer {
        fputs("mercury typed: send(value:) returned pointer \(errorPointer)\n", stderr)
        return 1
    }
    fputs("mercury typed: send(value:) returned\n", stderr)
    return 0
}

@_cdecl("coredevice_print_connected_services")
public func coredevicePrintConnectedServices(_ connection: UnsafeMutableRawPointer?) -> Int32 {
    guard let connection else {
        fputs("connected services: remote connection is null\n", stderr)
        return 2
    }

    var request = makeUHIDConnectedServicesRequest()
    if ProcessInfo.processInfo.environment["HIDCTL_QUIET"] == nil {
        withUnsafePointer(to: &request) { requestPointer in
            fputs("connected services request: \(uhidRequestDescriptionABI(UnsafeRawPointer(requestPointer)))\n", stderr)
        }
    }

    let serviceName = ProcessInfo.processInfo.environment["HIDCTL_MERCURY_SERVICE"] ?? "com.apple.coredevice.hid.universalhidservice"
    let peer = mercuryUnsafePeerForService(connection, serviceName)
    let peerPointer = Unmanaged.passUnretained(peer).toOpaque()
    let (requestMetadata, requestDecodableWitness, requestEncodableWitness) = uhidRequestMetadataAndCodableWitnesses()
    let (replyMetadata, replyDecodableWitness, replyEncodableWitness) = uhidConnectedServicesMetadataAndCodableWitnesses()

    var reply: UInt64 = 0
    let result = withUnsafePointer(to: &request) { requestPointer in
        withUnsafeMutablePointer(to: &reply) { replyPointer in
            mercuryXPCConnectionSendSyncValueABI(
                peerPointer,
                UnsafeRawPointer(requestPointer),
                requestMetadata,
                requestDecodableWitness,
                requestEncodableWitness,
                replyMetadata,
                replyDecodableWitness,
                replyEncodableWitness,
                UnsafeMutableRawPointer(replyPointer)
            )
        }
    }

    fputs(String(format: "connected services result=%d raw=%016llx\n", result, reply), stderr)
    if result == 0 {
        withUnsafePointer(to: &reply) { replyPointer in
            fputs("connected services: \(uhidConnectedServicesDescriptionABI(UnsafeRawPointer(replyPointer)))\n", stderr)
        }
    }
    return result
}

@_cdecl("coredevice_send_universalhid_hid_report")
public func coredeviceSendUniversalHIDReport(
    _ connection: UnsafeMutableRawPointer?,
    _ reportWords: UnsafeRawPointer?,
    _ serviceID: UInt64
) -> Int32 {
    guard let connection else {
        fputs("coredevice hid: remote connection is null\n", stderr)
        return 2
    }
    guard let reportWords else {
        fputs("coredevice hid: report is null\n", stderr)
        return 2
    }

    let (service, witness) = makeDDIUniversalHIDService(connection)
    let result = coredeviceUniversalHIDSendDispatchABI(service, witness, reportWords, serviceID)
    if ProcessInfo.processInfo.environment["HIDCTL_QUIET"] == nil {
        fputs("coredevice hid: send dispatch result=\(result)\n", stderr)
    }
    return result
}

@_cdecl("coredevice_reset_universalhid_gesture")
public func coredeviceResetUniversalHIDGesture(
    _ connection: UnsafeMutableRawPointer?,
    _ serviceID: UInt64
) -> Int32 {
    guard let connection else {
        fputs("coredevice hid reset: remote connection is null\n", stderr)
        return 2
    }

    let (service, witness) = makeDDIUniversalHIDService(connection)
    let result = coredeviceUniversalHIDResetDispatchABI(service, witness, serviceID)
    if ProcessInfo.processInfo.environment["HIDCTL_QUIET"] == nil {
        fputs("coredevice hid: reset dispatch result=\(result)\n", stderr)
    }
    return result
}

@_cdecl("coredevice_send_universalhid_barrier")
public func coredeviceSendUniversalHIDBarrier(_ connection: UnsafeMutableRawPointer?) -> Int32 {
    guard let connection else {
        fputs("coredevice hid barrier: remote connection is null\n", stderr)
        return 2
    }

    let (service, witness) = makeDDIUniversalHIDService(connection)
    let result = coredeviceUniversalHIDBarrierDispatchABI(service, witness)
    if ProcessInfo.processInfo.environment["HIDCTL_QUIET"] == nil {
        fputs("coredevice hid: barrier dispatch result=\(result)\n", stderr)
    }
    return result
}

@_cdecl("coredevice_send_hid_button_custom")
public func coredeviceSendHIDButtonCustom(
    _ connection: UnsafeMutableRawPointer?,
    _ usagePage: UInt64,
    _ usageCode: UInt64,
    _ state: UInt8
) -> Int32 {
    guard let connection else {
        fputs("coredevice button: remote connection is null\n", stderr)
        return 2
    }

    let (button, witness) = makeIndigoHIDButton(connection)
    let result = coredeviceHIDButtonCustomDispatchABI(button, witness, usagePage, usageCode, state)
    if ProcessInfo.processInfo.environment["HIDCTL_QUIET"] == nil {
        fputs("coredevice button: custom dispatch result=\(result) page=\(usagePage) code=\(usageCode) state=\(state)\n", stderr)
    }
    return result
}

@_cdecl("coredevice_send_hid_button_barrier")
public func coredeviceSendHIDButtonBarrier(_ connection: UnsafeMutableRawPointer?) -> Int32 {
    guard let connection else {
        fputs("coredevice button barrier: remote connection is null\n", stderr)
        return 2
    }

    let (button, witness) = makeIndigoHIDButton(connection)
    let result = coredeviceHIDButtonBarrierDispatchABI(button, witness)
    if ProcessInfo.processInfo.environment["HIDCTL_QUIET"] == nil {
        fputs("coredevice button: barrier dispatch result=\(result)\n", stderr)
    }
    return result
}

@_cdecl("coredevice_send_hid_digitizer_cgpoint")
public func coredeviceSendHIDDigitizerCGPoint(
    _ connection: UnsafeMutableRawPointer?,
    _ pointOneX: Double,
    _ pointOneY: Double,
    _ pointTwoX: Double,
    _ pointTwoY: Double,
    _ pointTwoOptionalTag: UInt64,
    _ eventType: UInt64,
    _ edge: UInt64,
    _ targetLow: UInt64,
    _ targetHigh: UInt64
) -> Int32 {
    guard let connection else {
        fputs("coredevice digitizer: remote connection is null\n", stderr)
        return 2
    }

    let (digitizer, witness) = makeIndigoHIDDigitizer(connection)
    let result = coredeviceHIDDigitizerCGPointDispatchABI(
        digitizer,
        witness,
        pointOneX,
        pointOneY,
        pointTwoX,
        pointTwoY,
        pointTwoOptionalTag,
        eventType,
        edge,
        targetLow,
        targetHigh
    )
    if ProcessInfo.processInfo.environment["HIDCTL_QUIET"] == nil {
        fputs("coredevice digitizer: cgpoint dispatch result=\(result) p1=(\(pointOneX),\(pointOneY)) tag=\(pointTwoOptionalTag) event=\(eventType) edge=\(edge) target=(\(targetLow),\(targetHigh))\n", stderr)
    }
    return result
}
