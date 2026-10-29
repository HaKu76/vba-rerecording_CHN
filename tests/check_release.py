"""Validate packaged artifacts and PE resources; never execute the emulator."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from restore_zh_resources import extract, resources


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', default='v24.1-zh-HD2')
    version = parser.parse_args().version
    prefix = 'VBA-rr-' + version
    binary_root, source_root = prefix + '-win32/', prefix + '-source/'
    binary_path = ROOT / 'dist' / (binary_root[:-1] + '.zip')
    source_path = ROOT / 'dist' / (source_root[:-1] + '.zip')
    expected_sums = ''.join(digest(p.read_bytes()) + '  ' + p.name + '\n'
                            for p in (binary_path, source_path))
    assert (ROOT / 'dist/SHA256SUMS.txt').read_text(encoding='ascii') == expected_sums
    with zipfile.ZipFile(binary_path) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist())), 'duplicate ZIP members'
        assert all(n.startswith(binary_root) for n in archive.namelist()), 'binary ZIP root'
        files = {n[len(binary_root):]: archive.read(n) for n in archive.namelist()}
        top = {n.split('/')[0] for n in files}
        assert top == {'VBA-rr-zh.exe', 'lua51.dll', 'lua5.1.dll', 'documentation'}, top
        forbidden = {'.lua', '.sav', '.sgm', '.gba', '.gb', '.gbc', '.ini', '.log'}
        assert not [n for n in files if Path(n).suffix.lower() in forbidden], 'test scripts or runtime data in release'
        for dll in ('lua51.dll', 'lua5.1.dll'):
            assert files[dll] == (ROOT / 'win32/lib' / dll).read_bytes(), dll
        info = json.loads(files['documentation/build-info.json'])
        assert info['release'] == version
        assert info['source_archive'] == source_path.name
        assert info['exe_sha256'] == digest(files['VBA-rr-zh.exe'])
        with tempfile.TemporaryDirectory(prefix='vba-release-check-') as temp:
            pe_path = Path(temp) / 'VBA-rr-zh.exe'
            pe_path.write_bytes(files['VBA-rr-zh.exe'])
            about = extract(pe_path)['dialogs']['505']
            assert '汉化：Hakuhiro/白希洛' in [c['text'] for c in about['controls']], 'compiled About credit'
            embedded = resources(pe_path)
            for pixels, ident in ((8, 43530), (12, 43531)):
                font = (ROOT / ('fonts/fusion-pixel/fusion-pixel-%dpx-monospaced-zh_hans.otf' % pixels)).read_bytes()
                assert any(kind == 10 and rid == ident and data == font
                           for (kind, rid, lang), data in embedded.items()), 'embedded font %d' % pixels
    with zipfile.ZipFile(source_path) as archive:
        snapshot = json.loads(archive.read(source_root + 'SOURCE-INFO.json'))
        inventory = archive.read(source_root + 'SOURCE-FILES.sha256')
        assert digest(inventory) == snapshot['source_inventory_sha256'] == info['source_inventory_sha256']
        assert snapshot['source_base_commit'] == info['source_base_commit']
        entries = inventory.decode('utf-8').splitlines()
        assert len(entries) == len(snapshot['files']) == info['source_file_count']
        for line, name in zip(entries, snapshot['files']):
            checksum, listed_name = line.split('  ', 1)
            assert name == listed_name
            assert digest(archive.read(source_root + name)) == checksum, name
        assert source_root + '.github/workflows/windows-release.yml' in archive.namelist()
    print('PASS: release layout, no Lua scripts/runtime data, Lua DLLs, compiled credit/fonts, source inventory and ZIP hashes')


if __name__ == '__main__':
    main()
