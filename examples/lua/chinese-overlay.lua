-- Save as UTF-8 WITHOUT BOM. Requires the source-built Chinese edition.
-- Original GB/GBA coordinates; native 12px HD font keeps an 8px footprint.
assert(gui.texthd and (gui.texthdversion or 0) >= 2, "Use VBA-rr-zh.exe")
while true do
    gui.text(4, 2, "ASCII HUD remains 4px wide")
    gui.texthd(4, 14, "高清细边：生命 100", "white", "black", 12, nil, 2, "#000000D0", 232)
    gui.texthd(4, 26, "无描边：帧数 " .. emu.framecount(), "yellow", "clear", 12, nil, 0)
    gui.texthd(4, 38, "阴影：方向键 / A / B", "cyan", "black", 12, nil, 1)
    gui.texthd(4, 50, "完整描边：中文与数字 123", "white", "black", 12, nil, 3)
    emu.frameadvance()
end
