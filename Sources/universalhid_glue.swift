import Foundation
import Darwin

struct UHIDReportWords {
    var word0: UInt = 0
    var word1: UInt = 0
}

typealias UHIDHIDReport = UHIDReportWords
typealias UHIDDigitizerReport = UHIDReportWords
typealias UHIDDigitizerContact = UHIDReportWords
typealias UHIDDockSwipeReport = UHIDReportWords
typealias UHIDNavigationSwipeReport = UHIDReportWords

var retainedHIDReports: [UHIDHIDReport] = []

@_silgen_name("$s12UniversalHID9HIDReportV8bitCount2idACSi_AA8ReportIDVtcfC")
func uhidHIDReportInit(_ bitCount: Int, _ reportID: UInt8) -> UHIDHIDReport

@_silgen_name("$s12UniversalHID15DigitizerReportV7_reportAcA9HIDReportV_tcfC")
func uhidDigitizerReportInitUnderscore(_ report: UHIDHIDReport) -> UHIDDigitizerReport

@_silgen_name("$s12UniversalHID15DigitizerReportV6reportAA9HIDReportVvg")
func uhidDigitizerReportGetReport(_ report: UHIDDigitizerReport) -> UHIDHIDReport

@_silgen_name("$s12UniversalHID16DigitizerContactVACycfC")
func uhidDigitizerContactInit() -> UHIDDigitizerContact

@_silgen_name("$s12UniversalHID9HIDReportV4data10Foundation4DataVvg")
func uhidHIDReportData(_ report: UHIDHIDReport) -> Data

@_silgen_name("$s12UniversalHID9HIDReportV4dataAC10Foundation4DataV_tcfC")
func uhidHIDReportInitData(_ data: Data) -> UHIDHIDReport

@_silgen_name("$s12UniversalHID9HIDReportV16debugDescriptionSSvg")
func uhidHIDReportDebugDescription(_ report: UHIDHIDReport) -> String

@_silgen_name("$s12UniversalHID15DockSwipeReportV07initialE8BitCountSivgZ")
func uhidDockSwipeReportInitialBitCount() -> Int

@_silgen_name("$s12UniversalHID15DockSwipeReportV8reportIDAA0eG0VvgZ")
func uhidDockSwipeReportID() -> UInt8

@_silgen_name("$s12UniversalHID15DockSwipeReportV7_reportAcA9HIDReportV_tcfC")
func uhidDockSwipeReportInitUnderscore(_ report: UHIDHIDReport) -> UHIDDockSwipeReport

@_silgen_name("$s12UniversalHID15DockSwipeReportV6reportAA9HIDReportVvg")
func uhidDockSwipeReportGetReport(_ report: UHIDDockSwipeReport) -> UHIDHIDReport

@_silgen_name("$s12UniversalHID15DockSwipeReportVMa")
func uhidDockSwipeReportMetadata(_ request: Int) -> UnsafeRawPointer

@_silgen_name("$s12UniversalHID21NavigationSwipeReportV07initialE8BitCountSivgZ")
func uhidNavigationSwipeReportInitialBitCount() -> Int

@_silgen_name("$s12UniversalHID21NavigationSwipeReportV8reportIDAA0eG0VvgZ")
func uhidNavigationSwipeReportID() -> UInt8

@_silgen_name("$s12UniversalHID21NavigationSwipeReportV7_reportAcA9HIDReportV_tcfC")
func uhidNavigationSwipeReportInitUnderscore(_ report: UHIDHIDReport) -> UHIDNavigationSwipeReport

@_silgen_name("$s12UniversalHID21NavigationSwipeReportV6reportAA9HIDReportVvg")
func uhidNavigationSwipeReportGetReport(_ report: UHIDNavigationSwipeReport) -> UHIDHIDReport

@_silgen_name("$s12UniversalHID21NavigationSwipeReportVMa")
func uhidNavigationSwipeReportMetadata(_ request: Int) -> UnsafeRawPointer

@_silgen_name("uhid_digitizer_contact_set_index_abi")
func uhidDigitizerContactSetIndexABI(_ contact: UnsafeMutablePointer<UHIDDigitizerContact>, _ index: Int)

@_silgen_name("uhid_digitizer_contact_set_touch_abi")
func uhidDigitizerContactSetTouchABI(_ contact: UnsafeMutablePointer<UHIDDigitizerContact>, _ touch: UInt8)

@_silgen_name("uhid_digitizer_contact_set_range_abi")
func uhidDigitizerContactSetRangeABI(_ contact: UnsafeMutablePointer<UHIDDigitizerContact>, _ range: UInt8)

@_silgen_name("uhid_digitizer_contact_set_resting_abi")
func uhidDigitizerContactSetRestingABI(_ contact: UnsafeMutablePointer<UHIDDigitizerContact>, _ resting: UInt8)

@_silgen_name("uhid_digitizer_contact_set_x_abi")
func uhidDigitizerContactSetXABI(_ contact: UnsafeMutablePointer<UHIDDigitizerContact>, _ x: Double)

@_silgen_name("uhid_digitizer_contact_set_y_abi")
func uhidDigitizerContactSetYABI(_ contact: UnsafeMutablePointer<UHIDDigitizerContact>, _ y: Double)

@_silgen_name("uhid_digitizer_report_set_contact_count_abi")
func uhidDigitizerReportSetContactCountABI(_ report: UnsafeMutablePointer<UHIDDigitizerReport>, _ count: UInt8)

@_silgen_name("uhid_digitizer_report_set_contact_count_maximum_abi")
func uhidDigitizerReportSetContactCountMaximumABI(_ report: UnsafeMutablePointer<UHIDDigitizerReport>, _ count: UInt8)

@_silgen_name("uhid_digitizer_report_set_contact_abi")
func uhidDigitizerReportSetContactABI(_ report: UnsafeMutablePointer<UHIDDigitizerReport>, _ contact: UnsafePointer<UHIDDigitizerContact>, _ index: Int)

@_silgen_name("uhid_digitizer_report_set_contact_swipe_pending_abi")
func uhidDigitizerReportSetContactSwipePendingABI(_ report: UnsafeMutablePointer<UHIDDigitizerReport>, _ pending: UInt8, _ index: Int)

@_silgen_name("uhid_digitizer_report_set_contact_swipe_locked_abi")
func uhidDigitizerReportSetContactSwipeLockedABI(_ report: UnsafeMutablePointer<UHIDDigitizerReport>, _ locked: UInt8, _ index: Int)

@_silgen_name("uhid_digitizer_report_set_contact_swipe_up_abi")
func uhidDigitizerReportSetContactSwipeUpABI(_ report: UnsafeMutablePointer<UHIDDigitizerReport>, _ up: UInt8, _ index: Int)

@_silgen_name("uhid_fluid_set_phase_abi")
func uhidFluidSetPhaseABI(_ report: UnsafeMutableRawPointer, _ metadata: UnsafeRawPointer, _ witness: UnsafeRawPointer, _ phase: UInt8)

@_silgen_name("uhid_fluid_set_swipe_mask_abi")
func uhidFluidSetSwipeMaskABI(_ report: UnsafeMutableRawPointer, _ metadata: UnsafeRawPointer, _ witness: UnsafeRawPointer, _ swipeMask: UInt32)

@_silgen_name("uhid_fluid_set_gesture_motion_abi")
func uhidFluidSetGestureMotionABI(_ report: UnsafeMutableRawPointer, _ metadata: UnsafeRawPointer, _ witness: UnsafeRawPointer, _ gestureMotion: UInt16)

@_silgen_name("uhid_fluid_set_flavor_abi")
func uhidFluidSetFlavorABI(_ report: UnsafeMutableRawPointer, _ metadata: UnsafeRawPointer, _ witness: UnsafeRawPointer, _ flavor: UInt16)

@_silgen_name("uhid_fluid_set_progress_abi")
func uhidFluidSetProgressABI(_ report: UnsafeMutableRawPointer, _ metadata: UnsafeRawPointer, _ witness: UnsafeRawPointer, _ progress: Double)

@_silgen_name("uhid_fluid_set_x_abi")
func uhidFluidSetXABI(_ report: UnsafeMutableRawPointer, _ metadata: UnsafeRawPointer, _ witness: UnsafeRawPointer, _ x: Double)

@_silgen_name("uhid_fluid_set_y_abi")
func uhidFluidSetYABI(_ report: UnsafeMutableRawPointer, _ metadata: UnsafeRawPointer, _ witness: UnsafeRawPointer, _ y: Double)

let universalHIDFrameworkPath = "/Library/Developer/PrivateFrameworks/CoreDevice.framework/Frameworks/UniversalHID.framework/UniversalHID"
let universalHIDHandle = dlopen(universalHIDFrameworkPath, RTLD_NOW | RTLD_GLOBAL)

func universalHIDSymbol(_ name: String) -> UnsafeRawPointer {
    guard let handle = universalHIDHandle else {
        let message = dlerror().map { String(cString: $0) } ?? "unknown dlopen error"
        fatalError("Unable to open UniversalHID: \(message)")
    }
    guard let pointer = dlsym(handle, name) else {
        let message = dlerror().map { String(cString: $0) } ?? "unknown dlsym error"
        fatalError("Unable to resolve \(name): \(message)")
    }
    return UnsafeRawPointer(pointer)
}

let dockSwipeFluidWitness = universalHIDSymbol("$s12UniversalHID15DockSwipeReportVAA017FluidTouchGestureE8ProtocolAAWP")
let navigationSwipeFluidWitness = universalHIDSymbol("$s12UniversalHID21NavigationSwipeReportVAA017FluidTouchGestureE8ProtocolAAWP")

func makeDigitizerReportData(x: Double, y: Double, touching: Bool, inRange: Bool) -> Data {
    let digitizerReportID: UInt8 = 0x09
    let digitizerReportBitCount = 0x140

    let hidReport = uhidHIDReportInit(digitizerReportBitCount, digitizerReportID)
    var report = uhidDigitizerReportInitUnderscore(hidReport)
    var contact = uhidDigitizerContactInit()

    uhidDigitizerContactSetIndexABI(&contact, 0)
    uhidDigitizerContactSetTouchABI(&contact, touching ? 1 : 0)
    uhidDigitizerContactSetRangeABI(&contact, inRange ? 1 : 0)
    uhidDigitizerContactSetRestingABI(&contact, 0)
    uhidDigitizerContactSetXABI(&contact, x)
    uhidDigitizerContactSetYABI(&contact, y)

    uhidDigitizerReportSetContactABI(&report, &contact, 0)
    uhidDigitizerReportSetContactCountABI(&report, touching ? 1 : 0)
    uhidDigitizerReportSetContactCountMaximumABI(&report, 1)

    return uhidHIDReportData(uhidDigitizerReportGetReport(report))
}

func clampUnit(_ value: Double) -> Double {
    if value.isNaN || value < 0 {
        return 0
    }
    if value > 1 {
        return 1
    }
    return value
}

func scaledUInt16(_ value: Double) -> UInt16 {
    UInt16((clampUnit(value) * 65535.0).rounded())
}

func putUInt16LE(_ value: UInt16, into data: inout Data, at index: Int) {
    data[index] = UInt8(value & 0xff)
    data[index + 1] = UInt8((value >> 8) & 0xff)
}

func makeNavigationSwipeReportData(
    phase: UInt8,
    swipeMask: UInt8,
    gestureMotion: UInt8,
    flavor: UInt8,
    progress: Double,
    x: Double,
    y: Double
) -> Data {
    let hidReport = uhidHIDReportInit(uhidNavigationSwipeReportInitialBitCount(), uhidNavigationSwipeReportID())
    var report = uhidNavigationSwipeReportInitUnderscore(hidReport)
    let metadata = uhidNavigationSwipeReportMetadata(0)
    let witness = navigationSwipeFluidWitness

    withUnsafeMutablePointer(to: &report) { reportPointer in
        let rawReport = UnsafeMutableRawPointer(reportPointer)
        uhidFluidSetPhaseABI(rawReport, metadata, witness, phase)
        uhidFluidSetSwipeMaskABI(rawReport, metadata, witness, UInt32(swipeMask))
        uhidFluidSetGestureMotionABI(rawReport, metadata, witness, UInt16(gestureMotion))
        uhidFluidSetFlavorABI(rawReport, metadata, witness, UInt16(flavor))
        uhidFluidSetProgressABI(rawReport, metadata, witness, progress)
        uhidFluidSetXABI(rawReport, metadata, witness, x)
        uhidFluidSetYABI(rawReport, metadata, witness, y)
    }

    return uhidHIDReportData(uhidNavigationSwipeReportGetReport(report))
}

func makeDockSwipeReportData(
    phase: UInt8,
    swipeMask: UInt8,
    gestureMotion: UInt8,
    flavor: UInt8,
    progress: Double,
    x: Double,
    y: Double
) -> Data {
    let hidReport = uhidHIDReportInit(uhidDockSwipeReportInitialBitCount(), uhidDockSwipeReportID())
    var report = uhidDockSwipeReportInitUnderscore(hidReport)
    let metadata = uhidDockSwipeReportMetadata(0)
    let witness = dockSwipeFluidWitness

    withUnsafeMutablePointer(to: &report) { reportPointer in
        let rawReport = UnsafeMutableRawPointer(reportPointer)
        uhidFluidSetPhaseABI(rawReport, metadata, witness, phase)
        uhidFluidSetSwipeMaskABI(rawReport, metadata, witness, UInt32(swipeMask))
        uhidFluidSetGestureMotionABI(rawReport, metadata, witness, UInt16(gestureMotion))
        uhidFluidSetFlavorABI(rawReport, metadata, witness, UInt16(flavor))
        uhidFluidSetProgressABI(rawReport, metadata, witness, progress)
        uhidFluidSetXABI(rawReport, metadata, witness, x)
        uhidFluidSetYABI(rawReport, metadata, witness, y)
    }

    return uhidHIDReportData(uhidDockSwipeReportGetReport(report))
}

@_cdecl("uhid_make_digitizer_report")
public func uhidMakeDigitizerReport(
    _ x: Double,
    _ y: Double,
    _ touching: Int32,
    _ inRange: Int32,
    _ output: UnsafeMutablePointer<UInt8>?,
    _ outputCapacity: Int
) -> Int32 {
    let data = makeDigitizerReportData(x: x, y: y, touching: touching != 0, inRange: inRange != 0)
    guard let output else {
        return Int32(data.count)
    }
    guard outputCapacity >= data.count else {
        return -Int32(data.count)
    }
    data.withUnsafeBytes { bytes in
        if let base = bytes.baseAddress {
            output.initialize(from: base.assumingMemoryBound(to: UInt8.self), count: data.count)
        }
    }
    return Int32(data.count)
}

@_cdecl("uhid_make_digitizer_hid_report")
public func uhidMakeDigitizerHIDReport(
    _ x: Double,
    _ y: Double,
    _ touching: Int32,
    _ inRange: Int32,
    _ output: UnsafeMutableRawPointer?
) -> Int32 {
    let hidReport = uhidHIDReportInit(0x140, 0x09)
    var report = uhidDigitizerReportInitUnderscore(hidReport)
    var contact = uhidDigitizerContactInit()

    uhidDigitizerContactSetIndexABI(&contact, 0)
    uhidDigitizerContactSetTouchABI(&contact, touching != 0 ? 1 : 0)
    uhidDigitizerContactSetRangeABI(&contact, inRange != 0 ? 1 : 0)
    uhidDigitizerContactSetRestingABI(&contact, 0)
    uhidDigitizerContactSetXABI(&contact, x)
    uhidDigitizerContactSetYABI(&contact, y)

    uhidDigitizerReportSetContactABI(&report, &contact, 0)
    uhidDigitizerReportSetContactCountABI(&report, touching != 0 ? 1 : 0)
    uhidDigitizerReportSetContactCountMaximumABI(&report, 1)

    var finalReport = uhidDigitizerReportGetReport(report)
    retainedHIDReports.append(finalReport)
    if let output {
        withUnsafeBytes(of: &finalReport) { bytes in
            output.copyMemory(from: bytes.baseAddress!, byteCount: bytes.count)
        }
    }
    return Int32(MemoryLayout<UHIDHIDReport>.size)
}

@_cdecl("uhid_make_digitizer_swipe_hid_report")
public func uhidMakeDigitizerSwipeHIDReport(
    _ x: Double,
    _ y: Double,
    _ touching: Int32,
    _ inRange: Int32,
    _ swipePending: Int32,
    _ swipeLocked: Int32,
    _ swipeUp: Int32,
    _ output: UnsafeMutableRawPointer?
) -> Int32 {
    let hidReport = uhidHIDReportInit(0x140, 0x09)
    var report = uhidDigitizerReportInitUnderscore(hidReport)
    var contact = uhidDigitizerContactInit()

    uhidDigitizerContactSetIndexABI(&contact, 0)
    uhidDigitizerContactSetTouchABI(&contact, touching != 0 ? 1 : 0)
    uhidDigitizerContactSetRangeABI(&contact, inRange != 0 ? 1 : 0)
    uhidDigitizerContactSetRestingABI(&contact, 0)
    uhidDigitizerContactSetXABI(&contact, x)
    uhidDigitizerContactSetYABI(&contact, y)

    uhidDigitizerReportSetContactABI(&report, &contact, 0)
    uhidDigitizerReportSetContactSwipePendingABI(&report, swipePending != 0 ? 1 : 0, 0)
    uhidDigitizerReportSetContactSwipeLockedABI(&report, swipeLocked != 0 ? 1 : 0, 0)
    uhidDigitizerReportSetContactSwipeUpABI(&report, swipeUp != 0 ? 1 : 0, 0)
    uhidDigitizerReportSetContactCountABI(&report, touching != 0 ? 1 : 0)
    uhidDigitizerReportSetContactCountMaximumABI(&report, 1)

    var finalReport = uhidDigitizerReportGetReport(report)
    retainedHIDReports.append(finalReport)
    if let output {
        withUnsafeBytes(of: &finalReport) { bytes in
            output.copyMemory(from: bytes.baseAddress!, byteCount: bytes.count)
        }
    }
    return Int32(MemoryLayout<UHIDHIDReport>.size)
}

@_cdecl("uhid_make_navigation_swipe_hid_report")
public func uhidMakeNavigationSwipeHIDReport(
    _ phase: UInt32,
    _ swipeMask: UInt32,
    _ gestureMotion: UInt32,
    _ flavor: UInt32,
    _ progress: Double,
    _ x: Double,
    _ y: Double,
    _ output: UnsafeMutableRawPointer?
) -> Int32 {
    let data = makeNavigationSwipeReportData(
        phase: UInt8(truncatingIfNeeded: phase),
        swipeMask: UInt8(truncatingIfNeeded: swipeMask),
        gestureMotion: UInt8(truncatingIfNeeded: gestureMotion),
        flavor: UInt8(truncatingIfNeeded: flavor),
        progress: progress,
        x: x,
        y: y
    )
    var report = uhidHIDReportInitData(data)
    retainedHIDReports.append(report)
    if let output {
        withUnsafeBytes(of: &report) { bytes in
            output.copyMemory(from: bytes.baseAddress!, byteCount: bytes.count)
        }
    }
    return Int32(MemoryLayout<UHIDHIDReport>.size)
}

@_cdecl("uhid_make_dock_swipe_hid_report")
public func uhidMakeDockSwipeHIDReport(
    _ phase: UInt32,
    _ swipeMask: UInt32,
    _ gestureMotion: UInt32,
    _ flavor: UInt32,
    _ progress: Double,
    _ x: Double,
    _ y: Double,
    _ output: UnsafeMutableRawPointer?
) -> Int32 {
    let data = makeDockSwipeReportData(
        phase: UInt8(truncatingIfNeeded: phase),
        swipeMask: UInt8(truncatingIfNeeded: swipeMask),
        gestureMotion: UInt8(truncatingIfNeeded: gestureMotion),
        flavor: UInt8(truncatingIfNeeded: flavor),
        progress: progress,
        x: x,
        y: y
    )
    var report = uhidHIDReportInitData(data)
    retainedHIDReports.append(report)
    if let output {
        withUnsafeBytes(of: &report) { bytes in
            output.copyMemory(from: bytes.baseAddress!, byteCount: bytes.count)
        }
    }
    return Int32(MemoryLayout<UHIDHIDReport>.size)
}
