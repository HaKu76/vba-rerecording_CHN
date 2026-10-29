"""Package the compiled emulator and its exact source snapshot without running it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', default='v24.1-zh-HD2')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', args.version):
        parser.error('version must be a filename-safe release label')
    exe = ROOT / 'build/msvc/VBA2010/bin/VBA-rr-zh.exe'
    if not exe.is_file():
        parser.error('VBA-rr-zh.exe is missing; run tools/build_zh.ps1')
    snapshot = None
    if (ROOT / '.git').exists():
        names = sorted(set(git('ls-files', '-co', '--exclude-standard', '-z').decode('utf-8').split('\0')) - {''})
        base_commit = git('rev-parse', 'HEAD').decode().strip()
        dirty = bool(git('status', '--porcelain', '--untracked-files=normal').strip())
    else:
        snapshot = json.loads((ROOT / 'SOURCE-INFO.json').read_text(encoding='utf-8'))
        names = snapshot['files']
        base_commit, dirty = snapshot['source_base_commit'], snapshot['source_worktree_modified']
    sources = []
    for name in names:
        path = ROOT / name
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError('External source link: ' + name)
        sources.append((name, path))
    inventory = ''.join(sha256(path) + '  ' + name + '\n' for name, path in sources)
    inventory_hash = hashlib.sha256(inventory.encode('utf-8')).hexdigest()
    if snapshot and inventory_hash != snapshot['source_inventory_sha256']:
        dirty = True
    name = 'VBA-rr-' + args.version
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    binary_name, source_name = name + '-win32', name + '-source'
    binary_zip, source_zip = dist / (binary_name + '.zip'), dist / (source_name + '.zip')
    with tempfile.TemporaryDirectory(prefix='package-', dir=dist) as temp:
        stage = Path(temp) / binary_name
        stage.mkdir()
        for source, destination in (
            (exe, 'VBA-rr-zh.exe'),
            (ROOT / 'win32/lib/lua51.dll', 'lua51.dll'),
            (ROOT / 'win32/lib/lua5.1.dll', 'lua5.1.dll'),
            (ROOT / 'src/win32/7zip/7z/DOC/License.txt', 'documentation/licenses/7-Zip.txt'),
        ):
            target = stage / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        # Match the original distribution: EXE + two DLLs + documentation/.
        for filename in (
            'gpl.txt', 'License.txt', 'lua.txt', 'SFMTLicense.txt', 'TODO.txt',
            'unRarLicense.txt', 'VBArr-V21-changelog.txt', 'VBArr-V22-changelog.txt',
            'VBArr-V23-changelog.txt', 'VBArr-V23.5-changelog.txt',
            'README-zh-CN.txt', 'RELEASE-NOTES-zh-CN.txt',
        ):
            shutil.copy2(ROOT / 'documentation' / filename, stage / 'documentation' / filename)
        lua_header = (ROOT / 'src/lua/src/lua.h').read_text(encoding='utf-8')
        text = lua_header[lua_header.index('* Copyright (C) 1994-2008 Lua.org'):]
        text = text[:text.index('******************************************************************************/')]
        (stage / 'documentation/licenses/Lua.txt').write_text(text, encoding='utf-8')
        for pixels in (8, 12):
            shutil.copytree(ROOT / ('fonts/fusion-pixel/licenses-%dpx' % pixels), stage / ('documentation/licenses/fusion-pixel-%dpx' % pixels))
        shutil.copy2(ROOT / 'fonts/fusion-pixel/manifest.json', stage / 'documentation/licenses/font-manifest.json')
        info = {
            'release': args.version,
            'source_base_commit': base_commit,
            'source_worktree_modified': dirty,
            'source_archive': source_zip.name,
            'source_inventory_sha256': inventory_hash, 'source_file_count': len(sources),
            'architecture': 'x86', 'configuration': 'Release / V82XR',
            'toolset': 'v143', 'windows_sdk': '10.0.22621.0', 'emulator_core': 'v8',
            'lua_font': 'Fusion Pixel 8px/12px Monospaced zh-Hans 2026.10.25 (embedded)',
            'text_overlay': 'HD2; all text modes; offscreen composition; persistent paused HUD',
            'default_text_method': 0,
            'lua_runtime': 'Lua 5.1; repository-provided x86 lua51.dll + lua5.1.dll',
            'translation_credit': 'Hakuhiro/白希洛',
            'runtime_validation': 'NOT_RUN_USER_REQUEST', 'exe_sha256': sha256(exe),
        }
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            info['ci_run_url'] = '{}/{}/actions/runs/{}'.format(
                os.environ['GITHUB_SERVER_URL'], os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_RUN_ID'])
        (stage / 'documentation/build-info.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        with zipfile.ZipFile(binary_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    archive.write(path, binary_name + '/' + path.relative_to(stage).as_posix())
        with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative, path in sources:
                archive.write(path, source_name + '/' + relative)
            source_info = {
                'source_base_commit': base_commit, 'source_worktree_modified': dirty,
                'source_inventory_sha256': inventory_hash, 'files': [n for n, p in sources],
            }
            archive.writestr(source_name + '/SOURCE-INFO.json', json.dumps(source_info, ensure_ascii=False, indent=2) + '\n')
            archive.writestr(source_name + '/SOURCE-FILES.sha256', inventory)
        # Zip from the fresh whitelist, never from a user's runtime folder.
        # Preserve any local runtime files, while preventing obsolete files from
        # leaking into the new extracted distribution after its layout changes.
        runtime_dir = dist / binary_name
        if runtime_dir.exists():
            backup = ROOT / '.userdata/package-replaced' / (binary_name + '-' + str(time.time_ns()))
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(runtime_dir), str(backup))
            print('Previous runtime directory preserved: ' + str(backup))
        shutil.copytree(stage, runtime_dir)
    sums = ''.join(sha256(path) + '  ' + path.name + '\n' for path in (binary_zip, source_zip))
    (dist / 'SHA256SUMS.txt').write_text(sums, encoding='ascii')
    print('Binary: ' + str(binary_zip))
    print('Source: ' + str(source_zip))
    print('EXE SHA256: ' + sha256(exe))


if __name__ == '__main__':
    main()
