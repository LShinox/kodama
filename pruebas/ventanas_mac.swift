// (c) 2026 LShinox - PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). See LICENSE.txt.
// Prints, as JSON, the windows that belong to one process (by PID) and the screens, so the screenshot job can prove WHERE the pet's window is
// (layer = window level, bounds in points) even when macOS does not let the runner capture app windows. Read-only; needs no permission.
// Usage: swift ventanas_mac.swift <pid>
import AppKit
import CoreGraphics
import Foundation

let pid = Int32(CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "0") ?? 0
var out: [String: Any] = [:]
var wins: [[String: Any]] = []
if let lista = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]] {
    for w in lista where (w[kCGWindowOwnerPID as String] as? Int32) == pid {
        wins.append([
            "layer": w[kCGWindowLayer as String] ?? -1,
            "bounds": w[kCGWindowBounds as String] ?? [:],
            "onscreen": w[kCGWindowIsOnscreen as String] ?? false,
            "alpha": w[kCGWindowAlpha as String] ?? 1,
        ])
    }
}
out["windows"] = wins
var screens: [[String: Any]] = []
for s in NSScreen.screens {
    var d: [String: Any] = ["frame": [s.frame.origin.x, s.frame.origin.y, s.frame.size.width, s.frame.size.height]]
    if #available(macOS 12.0, *) {
        d["safeTop"] = s.safeAreaInsets.top
        d["auxLeft"] = (s.auxiliaryTopLeftArea?.size.width ?? 0)
        d["auxRight"] = (s.auxiliaryTopRightArea?.size.width ?? 0)
    }
    screens.append(d)
}
out["screens"] = screens
if let data = try? JSONSerialization.data(withJSONObject: out, options: [.sortedKeys]), let txt = String(data: data, encoding: .utf8) { print(txt) }
