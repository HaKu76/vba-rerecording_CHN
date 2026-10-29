from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = (root / 'src/common/lua-engine.cpp').read_text(encoding='utf-8')
start = source.index('#if (defined(WIN32) && !defined(SDL))\nstruct LuaUTF8Plot')
end = source.index('// gui.texthd has', start)
dest = root / 'build/checks'
dest.mkdir(parents=True, exist_ok=True)
(dest / 'lua_utf8_entry.inc').write_text(source[start:end], encoding='utf-8')
for name in ('lua51.dll', 'lua5.1.dll'):
    shutil.copy2(root / 'win32/lib' / name, dest / name)
