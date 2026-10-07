// wclick -- 往指定屏幕坐标合成一次鼠标点击 / 移动，或按一个虚拟键码
//
// 用途：Wine 里的 galgame 经常有「点一下跳过」「点 OK」这种前台交互，
// 用这个可以在不开 GUI 自动化框架的情况下把事件打到窗口上。
// 坐标是屏幕坐标、左上角原点、单位是点（不是像素）——直接拿 winlist
// 输出里的 @(x,y) 和 WxH 算就行。
//
// 编译：swiftc -O -o wclick wclick.swift
// 用法：
//   ./wclick 800 500            # 在 (800,500) 点一下
//   ./wclick 800 500 move       # 只移动光标
//   ./wclick 53 0 key           # 按虚拟键码 53（Esc）
//
// 常用虚拟键码：36 回车 / 49 空格 / 53 Esc / 51 退格 / 123-126 方向键
//
// 注意：这条路径对「窗口是不是前台」很敏感。事件是投递到屏幕坐标上的，
// 如果别的窗口盖在上面，点就落错了地方——先 `open -a` 或点一下标题栏把
// 目标窗口提到前面。

import CoreGraphics
import Foundation

let args = CommandLine.arguments
let mode = args.count > 3 ? args[3] : "click"

if mode == "key" {
    guard let code = UInt16(args[1]) else { exit(1) }
    let src = CGEventSource(stateID: .hidSystemState)
    CGEvent(keyboardEventSource: src, virtualKey: CGKeyCode(code), keyDown: true)?.post(tap: .cghidEventTap)
    usleep(60_000)
    CGEvent(keyboardEventSource: src, virtualKey: CGKeyCode(code), keyDown: false)?.post(tap: .cghidEventTap)
    print("key \(code)")
    exit(0)
}

guard args.count >= 3, let x = Double(args[1]), let y = Double(args[2]) else {
    FileHandle.standardError.write("usage: wclick <x> <y> [click|move]\n".data(using: .utf8)!)
    exit(1)
}

let pt = CGPoint(x: x, y: y)
let src = CGEventSource(stateID: .hidSystemState)
CGEvent(mouseEventSource: src, mouseType: .mouseMoved, mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
if mode == "move" { print("moved \(x),\(y)"); exit(0) }
usleep(250_000)
CGEvent(mouseEventSource: src, mouseType: .leftMouseDown, mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
usleep(120_000)
CGEvent(mouseEventSource: src, mouseType: .leftMouseUp, mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
usleep(120_000)
print("clicked \(x),\(y)")
