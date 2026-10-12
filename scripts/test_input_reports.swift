import Foundation

@main
struct InputReportTests {
    static func check(_ condition: @autoclosure () -> Bool, _ message: String) {
        if !condition() { fatalError(message) }
    }

    static func dataFromOutput(_ build: (UnsafeMutableRawPointer) -> Int32) -> [UInt8] {
        var words = UHIDReportWords()
        let result = withUnsafeMutableBytes(of: &words) { raw in
            build(raw.baseAddress!)
        }
        check(result == Int32(MemoryLayout<UHIDReportWords>.size), "builder returned \(result), expected report value size")
        return Array(uhidHIDReportData(words))
    }

    static func bit(_ data: [UInt8], _ index: Int) -> Bool {
        (data[index / 8] & (UInt8(1) << UInt8(index % 8))) != 0
    }

    static func assertSwipeFlags(_ data: [UInt8], direction: Int) {
        let fields = [434, 439, 444, 449]
        check(bit(data, 429), "edge report must set locked")
        check(!bit(data, 424), "edge report must not set pending")
        for field in fields {
            check(bit(data, field) == (direction == field), "unexpected swipe direction bit " + String(field) + " data=" + data[53..<58].map { String(format: "%02x", $0) }.joined())
        }
        check(!bit(data, 454), "edge report must not set cancel")
    }

    static func testDigitizer() {
        let ordinaryUp = dataFromOutput { output in
            uhidMakeDigitizerHIDReport(0.5, 0.5, 0, 0, output)
        }
        check(ordinaryUp.count == 58, "ordinary UP must be 58 bytes")
        check(ordinaryUp[0] == 9 && ordinaryUp[1] == 1, "ordinary report ID/contact count")
        check(ordinaryUp[2] == 1, "ordinary UP maximum remains 1")
        check(ordinaryUp[3] == 0, "ordinary UP touch/range must be clear")
        check(ordinaryUp[40] == 0, "ordinary identity must remain zero")
        check(ordinaryUp[45..<53].allSatisfy { $0 == 0 }, "ordinary timestamp must remain zero")
        for field in [424, 429, 434, 439, 444, 449, 454] {
            check(!bit(ordinaryUp, field), "ordinary UP has unexpected swipe bit \(field)")
        }
        check(ordinaryUp == makeDigitizerWireBytes(x: 0.5, y: 0.5, touching: false, inRange: false),
              "ordinary builder output differs from wire helper")

        for quarter in 0...3 {
            let data = dataFromOutput { output in
                uhidMakeEdgeTouchHIDReport(0.5, 0.99, 1, 1, Int32(quarter), output)
            }
            check(data.count == 58, "edge q\(quarter) must be 58 bytes")
            check(data[2] == 5, "edge q\(quarter) must use captured max contact count")
            check(data[40] == 2, "edge q\(quarter) must use captured identity")
            check(data[45..<53].contains(where: { $0 != 0 }), "edge q\(quarter) timestamp must be nonzero")
            assertSwipeFlags(data, direction: [434, 444, 439, 449][quarter])
            let up = dataFromOutput { output in
                uhidMakeEdgeTouchHIDReport(0.5, 0.99, 0, 0, Int32(quarter), output)
            }
            check(up.count == 58 && up[1] == 1 && up[3] == 2, "edge lift must describe the released contact")
            assertSwipeFlags(up, direction: [434, 444, 439, 449][quarter])
            var expected = makeDigitizerWireBytes(x: 0.5, y: 0.99, touching: true, inRange: true,
                                                  edgeQuarter: quarter)
            expected.replaceSubrange(45..<53, with: data[45..<53])
            check(data == expected, "edge q\(quarter) differs from wire helper")
        }
    }

    static func testKeyboard() {
        let heldSets: [[UInt32]] = [[0xe3], [0xe3, 0x19], [0x19], []]
        for usages in heldSets {
            let first = usages.first ?? 0
            let second = usages.dropFirst().first ?? 0
            let data = dataFromOutput { output in
                uhidMakeKeyboardPairHIDReport(first, second, output)
            }
            check(data.count == 39, "keyboard \(usages) must be 39 bytes")
            var actual: [UInt32] = []
            for usage in 1...0xe7 where bit(data, usage + 8) { actual.append(UInt32(usage)) }
            check(actual == usages.sorted(), "keyboard held set \(actual) != \(usages.sorted())")
        }
    }

    static func main() {
        testDigitizer()
        testKeyboard()
        print("input report host tests: PASS (digitizer 58B ordinary/edge, swipe bits, keyboard held sets)")
    }
}
