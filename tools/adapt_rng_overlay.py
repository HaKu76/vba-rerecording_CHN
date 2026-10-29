"""Adapt only the display boundary of the user's RNG script; back up first."""
import argparse
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('script', type=Path)
args = parser.parse_args()
path = args.script.resolve()
original = path.read_bytes()
source = original.decode('utf-8-sig')
assert '-- VBA_FUSION_RNG_OVERLAY' not in source, 'This script is already adapted'
translations = json.loads((ROOT / 'localization/rng-overlay-zh-CN.json').read_text(encoding='utf-8'))
quote = lambda s: json.dumps(s, ensure_ascii=False)
entries = ',\n'.join('  [%s] = %s' % (quote(k), quote(v)) for k, v in translations.items())
prefixes = ',\n'.join('  {%s, %s}' % (quote(k), quote(v)) for k, v in sorted(translations.items(), key=lambda item: -len(item[0])) if k.endswith(' '))
header = '''-- VBA_FUSION_RNG_OVERLAY
-- UTF-8 without BOM. Rendering only; RNG logic and English mode keys stay intact.
-- HD text layer: native 12px glyphs at 2x in a 3x canvas.
-- Keeps the old 8px layout; use 3x/6x display for an integer pixel scale.
local HUD_FONT_SIZE = 12
local HUD_OUTLINE_STYLE = 2 -- 0=off, 1=shadow, 2=thin, 3=full
local HUD_BACKGROUND = "clear" -- off; "#00000040" = 25% opacity, "#00000080" = 50%
local HUD_FONT_FACE = nil -- nil: bundled Fusion Pixel; e.g. "SimSun": system font
assert(type(gui.texthd) == "function" and (gui.texthdversion or 0) >= 2,
       "Please use VBA-rr-zh.exe; this script needs HD text revision 2")
local HUD_ZH_MODES = {
  ["None"] = "关闭", ["Capture"] = "捕获", ["100%% Catch"] = "必定捕获",
  ["Breeding"] = "孵蛋", ["Pandora"] = "潘多拉", ["TID Bot"] = "刷 TID",
  ["Pokemon Info"] = "宝可梦信息", ["Gift"] = "赠送", ["Party"] = "队伍",
  ["Party Stats"] = "队伍能力", ["Battle Party Stats"] = "战斗队伍能力",
  ["Box"] = "盒子", ["1st Floor Box Stats"] = "一楼盒子能力",
  ["2nd Floor Box Stats"] = "二楼盒子能力", ["DayCare Box Stats"] = "培育屋盒子能力"
}
local HUD_ZH_EXACT = {
%s
}
local HUD_ZH_PREFIXES = {
%s
}
local function hudText(x, y, value, foreground, outline)
  local text = tostring(value)
  if text:sub(1, 6) == "Mode: " then
    local key = text:sub(7)
    text = "模式：" .. (HUD_ZH_MODES[key] or key)
  elseif HUD_ZH_EXACT[text] then
    text = HUD_ZH_EXACT[text]
  else
    for _, pair in ipairs(HUD_ZH_PREFIXES) do
      if text:sub(1, #pair[1]) == pair[1] then
        text = pair[2] .. text:sub(#pair[1] + 1)
        break
      end
    end
  end
  -- Reserve the move PP column, the bottom IDs/help, and the right-hand panel.
  local width = math.max(0, 240 - x)
  local raw = tostring(value)
  if raw:sub(1, 6) == "Move: " then
    width = math.min(width, 84 - x)
  elseif x < 100 and y >= 120 then
    width = math.min(width, 98 - x)
  elseif x == 100 and y == 125 then
    width = 100
  elseif x == 100 and y == 152 then
    width = 98
  elseif x < 125 and y >= 10 and y <= 73 then
    width = math.min(width, 149 - x)
  end
  return gui.texthd(x, y, text, foreground, outline, HUD_FONT_SIZE, HUD_FONT_FACE,
                   HUD_OUTLINE_STYLE, HUD_BACKGROUND, math.max(0, width))
end

''' % (entries, prefixes)
count = source.count('gui.text(')
assert count > 50
newline = '\r\n' if b'\r\n' in original else '\n'
adapted = header.replace('\n', newline) + source.replace('gui.text(', 'hudText(')
# The original body is byte-identical after reversing the display-call rename.
assert adapted[len(header.replace('\n', newline)):].replace('hudText(', 'gui.text(') == source
backup = path.with_name(path.name + '.before-fusion-' + time.strftime('%Y%m%d-%H%M%S') + '.bak')
assert not backup.exists()
assert path.read_bytes() == original, 'Source changed during adaptation'
backup.write_bytes(original)
path.write_bytes(adapted.encode('utf-8'))
copy = ROOT / 'examples/lua/E_RNG_2.0-zh.lua'
copy.write_bytes(path.read_bytes())
record = {'script': str(path), 'backup': str(backup), 'gui_text_calls_adapted': count,
          'original_sha256': hashlib.sha256(original).hexdigest(),
          'modified_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
          'original_logic_preserved': True, 'runtime_validation': 'NOT_RUN_USER_REQUEST'}
(ROOT / '.local/history').mkdir(parents=True, exist_ok=True)
(ROOT / '.local/history/rng-script-change.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, ensure_ascii=False, indent=2))
