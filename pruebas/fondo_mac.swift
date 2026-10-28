// (c) 2026 LShinox - PolyForm Noncommercial 1.0.0 (SPDX: PolyForm-Noncommercial-1.0.0). See LICENSE.txt.
// FALLBACK for the screenshot job: if setting the wallpaper with osascript is not allowed on the runner, this paints a solid light-gray window at the
// desktop level (below every app window, above the real wallpaper) so the black island shape is visible in the screenshots. It is just a window of its own,
// started and stopped by the job (by PID). Usage: fondo_mac <r> <g> <b>   (0-255)
import AppKit

let a = CommandLine.arguments
func v(_ i: Int, _ d: Double) -> CGFloat { CGFloat(i < a.count ? (Double(a[i]) ?? d) : d) / 255.0 }
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
var wins: [NSWindow] = []
for s in NSScreen.screens {
    let w = NSWindow(contentRect: s.frame, styleMask: .borderless, backing: .buffered, defer: false)
    w.backgroundColor = NSColor(calibratedRed: v(1, 230), green: v(2, 230), blue: v(3, 232), alpha: 1)
    w.level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.desktopWindow)) + 1)
    w.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle]
    w.ignoresMouseEvents = true
    w.hasShadow = false
    w.isReleasedWhenClosed = false
    w.orderFrontRegardless()
    wins.append(w)
}
app.run()
