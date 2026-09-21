#!/usr/bin/env swift
// iOS 27 Settings search smoke fixture only; not a general UI/action oracle.
import Foundation
import Vision
import ImageIO

guard CommandLine.arguments.count == 3 else {
    fputs("usage: assert_search_text.swift screenshot.png expected-text\n", stderr)
    exit(2)
}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["zh-Hans", "en-US"]
request.usesLanguageCorrection = false
func normalize(_ text: String) -> String {
    String(text.unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) }).lowercased()
}
do {
    try VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[1])).perform([request])
    // Vision y has a bottom-left origin. Restrict to the focused search field,
    // excluding the clipboard suggestion above the keyboard and any alert.
    let field = (request.results ?? []).filter {
        let topY = 1 - $0.boundingBox.midY
        return topY > 0.53 && topY < 0.61 && $0.boundingBox.midX < 0.8
    }.compactMap { $0.topCandidates(1).first?.string }.joined(separator: " ")
    let expected = CommandLine.arguments[2].split(separator: " ").map { normalize(String($0)) }
    guard !expected.isEmpty && expected.allSatisfy({ !$0.isEmpty && normalize(field).contains($0) }) else {
        fputs("focused search text absent; inspect screenshot for focus or paste permission prompt\n", stderr)
        exit(1)
    }
    print("search-field text verified (OCR ignores punctuation/emoji; inspect exact literal visually)")
} catch {
    fputs("search OCR failed: \(error)\n", stderr)
    exit(1)
}
