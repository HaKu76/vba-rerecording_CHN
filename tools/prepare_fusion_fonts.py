"""Restore the two unmodified font programs from pinned upstream WOFF2 assets."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build/dependencies/font-tools'))
from fontTools.ttLib import TTFont

DEST = ROOT / 'fonts/fusion-pixel'
DEST.mkdir(parents=True, exist_ok=True)
SOURCES = {
    8: '4759ac0335c892486621581ba66437934a8496271061f14c5cbb5622528b4bad',
    12: '010223860f2dc625d672377917a3d585da698ce67e947418b603f6410591556c',
}
manifest = []
for pixels, expected in SOURCES.items():
    name = 'fusion-pixel-font-%dpx-monospaced-otf.woff2-v2026.10.25.zip' % pixels
    archive = ROOT / 'build/dependencies/fusion-pixel' / name
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
    with zipfile.ZipFile(archive) as z:
        for member in z.namelist():
            if member == 'OFL.txt' or member.startswith('LICENSES/'):
                dest = DEST / ('licenses-%dpx' % pixels) / member
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(member))
        filename = 'fusion-pixel-%dpx-monospaced-zh_hans.otf' % pixels
        packed = ROOT / 'build/dependencies/fusion-pixel' / (filename + '.woff2')
        packed.write_bytes(z.read(filename + '.woff2'))
    font = TTFont(packed)
    family = font['name'].getDebugName(1)
    font.flavor = None  # WOFF2 transport decompression, no glyph or name edits.
    target = DEST / filename
    font.save(target, reorderTables=False)
    manifest.append({'release': '2026.10.25', 'language': 'zh-Hans', 'pixels': pixels,
                     'family': family, 'filename': filename,
                     'upstream_url': 'https://github.com/TakWolf/fusion-pixel-font/releases/download/2026.10.25/' + name,
                     'upstream_zip_sha256': expected,
                     'font_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    print(filename, repr(family), target.stat().st_size, flush=True)
(DEST / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
