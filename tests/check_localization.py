"""Static invariants plus checks of SDK-compiled resource-only DLLs, if present."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from restore_zh_resources import EXE, QUOTED, extract, unquote, migrate, supplement

BASELINE = '45263417f0936cf55c07dd1f934e8386f8d81af8'
base = subprocess.check_output(['git', 'show', BASELINE + ':src/win32/vba.rc'], cwd=ROOT).decode('cp1252')
current = (ROOT / 'src/win32/vba.rc').read_text(encoding='utf-8-sig')


def structure(source):
    source = re.sub(QUOTED, '"TEXT"', source)
    source = source.replace('LANGUAGE LANG_CHINESE, SUBLANG_CHINESE_SIMPLIFIED', 'LANGUAGE LANG_ENGLISH, SUBLANG_ENGLISH_US')
    source = source.replace('#pragma code_page(65001)', '#pragma code_page(1252)')
    return source.splitlines()


credit = '汉化：Hakuhiro/白希洛'
credit_line = '    CTEXT           "' + credit + '",IDC_STATIC,7,78,150,8\n'
assert current.count(credit_line) == 1, 'original translator credit is missing or duplicated'
# This is the only intentional layout delta from upstream: add the recovered
# credit, extend About by 14 dialog units, and move OK down by the same amount.
normalized = current.replace(credit_line, '')
normalized = normalized.replace('IDD_ABOUT DIALOGEX 0, 0, 164, 115', 'IDD_ABOUT DIALOGEX 0, 0, 164, 101', 1)
normalized = normalized.replace(',IDOK,56,94,50,14', ',IDOK,56,80,50,14', 1)
assert structure(base) == structure(normalized), 'resource layout/IDs/styles/shortcuts changed'
reference = json.loads((ROOT / 'localization/reference-zh.json').read_text(encoding='utf-8'))
assert credit in [c['text'] for c in reference['dialogs']['505']['controls']]
regenerated, _, _ = migrate(reference, base)
regenerated, _ = supplement(regenerated)
assert credit_line in regenerated, 'regeneration from upstream loses translator credit'
repeated, _, _ = migrate(reference, current)
repeated, _ = supplement(repeated)
assert repeated == current, 'resource regeneration is not idempotent'
base_zip = subprocess.check_output(['git', 'show', BASELINE + ':src/win32/7zip/7zip.rc'], cwd=ROOT).decode('cp1252')
current_zip = (ROOT / 'src/win32/7zip/7zip.rc').read_text(encoding='utf-8-sig')
assert structure(base_zip) == structure(current_zip), 'archive dialog structure changed'
fmt = r'%(?:[-+ #0]*)(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|ll|[hlLzjtI]*)(?:[diouxXeEfFgGaAcspn%])'
entries = lambda source: {k: unquote(v) for k, v in re.findall(r'\b(IDS_\w+)\s+(' + QUOTED + ')', source)}
english, chinese = entries(base), entries(current)
assert english.keys() == chinese.keys()
for name in english:
    assert re.findall(fmt, english[name]) == re.findall(fmt, chinese[name]), name
    if name.startswith('IDS_FILTER_'):
        assert english[name].split('_')[1::2] == chinese[name].split('_')[1::2], name
if EXE.exists():
    assert hashlib.sha256(EXE.read_bytes()).hexdigest() == '1a45b992fa5ebb6406ca2cd2aeb45a8b22c14024ddbab29a80719fd423cc7d82'
archive = EXE.parent.parent / (EXE.parent.name + '.zip')
if archive.exists():
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '0a1134631448aa3b452c34e11b138f049f9588a3c1af6da0fb638426334d00d4'
report = json.loads((ROOT / 'localization/migration-report.json').read_text(encoding='utf-8'))
assert not report['menu_mismatches']
print('PASS: resource IDs/layout/styles/accelerators, printf arguments, filter globs; optional original package hashes checked when present')

if '--prepare-rc' in sys.argv:
    dest = ROOT / 'build/checks'
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'original.rc').write_bytes(base.encode('cp1252'))
    (dest / 'original-7zip.rc').write_bytes(base_zip.encode('cp1252'))
    # An SDK-only stand-in used solely to check resources, never for production.
    definitions = '#include <winres.h>\n#define ID_FILE_OPEN 0xe101\n#define ID_FILE_CLOSE 0xe102\n#define ID_FILE_SAVE 0xe103\n'
    definitions += ''.join('#define ID_FILE_MRU_FILE%d %d\n' % (i + 1, 0xe110 + i) for i in range(16))
    (dest / 'afxres.h').write_text(definitions, encoding='ascii')

if '--compiled' in sys.argv:
    old = extract(ROOT / 'build/checks/original-resources.dll')
    new = extract(ROOT / 'build/checks/chinese-resources.dll')
    for kind in old:
        assert old[kind].keys() == new[kind].keys(), kind
    for name in old['dialogs']:
        a, b = old['dialogs'][name]['controls'], new['dialogs'][name]['controls']
        if name == '505':
            assert b[-1] == {'id': 0xffffffff, 'class': 130, 'text': credit}
            b = b[:-1]
        assert [(c['id'], c['class']) for c in a] == [(c['id'], c['class']) for c in b], name
    for name in old['menus']:
        assert [i['id'] for i in old['menus'][name]] == [i['id'] for i in new['menus'][name]], name
    for name, value in old['strings'].items():
        assert re.findall(fmt, value) == re.findall(fmt, new['strings'][name]), name
    assert any(d['caption'] == 'Lua脚本' for d in new['dialogs'].values())
    assert any(s == '错误' for s in new['strings'].values())
    print('PASS: compiled resource DLLs, %d dialogs, %d menus, %d strings' % (len(new['dialogs']), len(new['menus']), len(new['strings'])))
