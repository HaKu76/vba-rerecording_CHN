"""Recover UI text from the supplied localized PE without executing it.

Captions are migrated. The About dialog also restores the original translator
credit with room for an additional line; other source layouts and IDs win.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / '.local/reference/vba-v24m-svn480.LRC4-xp140/vba-v24m-svn480+LRC4.exe'


class Reader:
    def __init__(self, data, pos=0):
        self.data, self.pos = data, pos

    def unpack(self, fmt):
        result = struct.unpack_from('<' + fmt, self.data, self.pos)
        self.pos += struct.calcsize('<' + fmt)
        return result[0] if len(result) == 1 else result

    def align(self):
        self.pos = (self.pos + 3) & ~3

    def text(self):
        start = self.pos
        first = self.unpack('H')
        if first == 0xffff:
            return self.unpack('H')
        if first == 0:
            return ''
        while self.unpack('H'):
            pass
        return self.data[start:self.pos - 2].decode('utf-16le')


def resources(path):
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[pe:pe + 4] == b'PE\0\0'
    sections = struct.unpack_from('<H', data, pe + 6)[0]
    optsize = struct.unpack_from('<H', data, pe + 20)[0]
    opt = pe + 24
    assert struct.unpack_from('<H', data, opt)[0] == 0x10b
    rva = struct.unpack_from('<I', data, opt + 112)[0]
    table = []
    for i in range(sections):
        size, va, rawsize, offset = struct.unpack_from('<IIII', data, opt + optsize + i * 40 + 8)
        table.append((va, max(size, rawsize), offset))

    def filepos(address):
        for va, size, offset in table:
            if va <= address < va + size:
                return offset + address - va
        raise ValueError('RVA outside PE sections')

    base = filepos(rva)
    result = {}

    def walk(offset, keys):
        named, ids = struct.unpack_from('<HH', data, base + offset + 12)
        for i in range(named + ids):
            name, target = struct.unpack_from('<II', data, base + offset + 16 + i * 8)
            if name & 0x80000000:
                p = base + (name & 0x7fffffff)
                n = struct.unpack_from('<H', data, p)[0]
                name = data[p + 2:p + 2 + n * 2].decode('utf-16le')
            key = keys + (name,)
            if target & 0x80000000:
                walk(target & 0x7fffffff, key)
            else:
                address, size = struct.unpack_from('<II', data, base + target)
                p = filepos(address)
                result[key] = data[p:p + size]
    walk(0, ())
    return result


def dialog(data):
    r = Reader(data)
    extended = data[:4] == b'\x01\x00\xff\xff'
    if extended:
        _, _, _, _, style, count = r.unpack('HHIIIH')
    else:
        style, _, count = r.unpack('IIH')
    r.unpack('hhhh')
    r.text()  # menu
    r.text()  # window class
    caption = r.text()
    if style & 0x40:
        r.unpack('H')
        if extended:
            r.unpack('HBB')
        r.text()
    controls = []
    for _ in range(count):
        r.align()
        if extended:
            r.unpack('IIIhhhh')
            ident = r.unpack('I')
        else:
            r.unpack('IIhhhh')
            ident = r.unpack('H')
        cls, text = r.text(), r.text()
        extra = r.unpack('H')
        r.pos += extra
        controls.append({'id': ident, 'class': cls, 'text': text})
    return {'caption': caption, 'controls': controls}


def menu(data):
    r = Reader(data)
    version, offset = r.unpack('HH')
    assert version == 0, 'MENUEX is not supported'
    r.pos += offset
    items = []

    def level():
        while True:
            flags = r.unpack('H')
            popup = bool(flags & 0x10)
            ident = None if popup else r.unpack('H')
            text = r.text()
            items.append({'id': ident, 'text': text})
            if popup:
                level()
            if flags & 0x80:
                return
    level()
    return items


def extract(path):
    out = {'dialogs': {}, 'menus': {}, 'strings': {}}
    for (kind, ident, lang), data in resources(path).items():
        if kind == 5:
            out['dialogs'][str(ident)] = dialog(data)
        elif kind == 4:
            out['menus'][str(ident)] = menu(data)
        elif kind == 6:
            r = Reader(data)
            for i in range(16):
                n = r.unpack('H')
                value = data[r.pos:r.pos + n * 2].decode('utf-16le')
                r.pos += n * 2
                if value:
                    out['strings'][str((ident - 1) * 16 + i)] = value
    return out


QUOTED = r'"(?:""|\\.|[^"\\])*"'


def quote(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '""').replace('\r', '\\r').replace('\n', '\\n').replace('\t', '\\t') + '"'


def unquote(text):
    return re.sub(r'\\([nrt\\])|""', lambda m: {'n': '\n', 'r': '\r', 't': '\t', '\\': '\\'}.get(m[1], '"'), text[1:-1])


def supplement(source):
    ui = json.loads((ROOT / 'localization/zh-CN-ui.json').read_text(encoding='utf-8'))
    ui = {unquote('"' + k + '"'): unquote('"' + v + '"') for k, v in ui.items()}
    strings = json.loads((ROOT / 'localization/zh-CN-strings.json').read_text(encoding='utf-8'))
    counts = {'ui': 0, 'strings': 0, 'filters': 0}
    # Limit replacements to captions: CONTROL's second string is its class name.
    pattern = r'(^\s*(?:CAPTION|POPUP|MENUITEM|[LCR]TEXT|PUSHBUTTON|DEFPUSHBUTTON|GROUPBOX|CONTROL)\s+)(' + QUOTED + ')'
    def caption(m):
        value = ui.get(unquote(m[2]))
        if value is None:
            return m.group()
        counts['ui'] += 1
        return m[1] + quote(value)
    source = re.sub(pattern, caption, source, flags=re.M)
    source = re.sub(r'(MENUITEM\s+)(' + QUOTED + r')(,\s*ID_OPTIONS_LANGUAGE_ENGLISH\b)',
                    lambda m: m[1] + quote('简体中文（内置）(&C)') + m[3], source)
    fmt = r'%(?:[-+ #0]*)(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|ll|[hlLzjtI]*)(?:[diouxXeEfFgGaAcspn%])'
    def string(m):
        name = m[1].split()[0]
        before = unquote(m[2])
        value = strings.get(name)
        if value is None and name.startswith('IDS_FILTER_'):
            # Filter descriptions may be translated; glob syntax is byte-exact.
            labels = before.split('_')
            for i in range(0, len(labels) - 1, 2):
                labels[i] = labels[i].replace('All Files', '所有文件').replace('Archive Files', '压缩文件').replace('(uncompressed only)', '（仅未压缩文件）').replace('All Gameboy / Gameboy Advance', '所有 GB / GBA 游戏').replace('All GB / GBA', '所有 GB / GBA 游戏').replace('All Gameboy', '所有 GB 游戏').replace('Memory Dump', '内存转储').replace('Wave file', '声音文件').replace('AVI File', 'AVI 文件').replace('Skin INI File', '皮肤 INI 文件').replace('Movie', '录像').replace('Snapshot', '快照').replace('Code File', '代码文件').replace('Windows Palette', 'Windows 调色板').replace('PaintShop Palette', 'PaintShop 调色板').replace('Adobe Color Table', 'Adobe 颜色表')
            value = '_'.join(labels)
            assert before.split('_')[1::2] == value.split('_')[1::2]
            counts['filters'] += 1
        if value is None:
            return m.group()
        assert re.findall(fmt, before) == re.findall(fmt, value), name + ': changed printf arguments'
        counts['strings'] += 1
        return m[1] + quote(value)
    source = re.sub(r'(\bIDS_\w+\s+)(' + QUOTED + ')', string, source)
    return source, counts


def migrate(extracted, source):
    source = source.replace('\r\n', '\n')
    if re.search(r'^IDD_ABOUT DIALOGEX\b', source, re.M):
        # Caption replacement alone cannot recover a control absent upstream.
        credit = next(c['text'] for c in extracted['dialogs']['505']['controls']
                      if isinstance(c['text'], str) and c['text'].startswith('汉化：'))
        def about(match):
            block = match.group()
            if quote(credit) in block:
                return block
            block, resized = re.subn(r'^(IDD_ABOUT DIALOGEX 0, 0, 164, )101$', r'\g<1>115', block, flags=re.M)
            block, moved = re.subn(r'(,IDOK,56,)80(,50,14)', r'\g<1>94\2', block)
            if resized != 1 or moved != 1:
                raise ValueError('Review the About dialog layout before restoring its translator credit')
            return block[:-3] + '    CTEXT           ' + quote(credit) + ',IDC_STATIC,7,78,150,8\nEND'
        source = re.sub(r'^IDD_ABOUT DIALOGEX\b.*?^END$', about, source, flags=re.M | re.S)
    ids = {'IDC_STATIC': -1, 'IDOK': 1, 'IDCANCEL': 2, 'IDABORT': 3,
           'IDRETRY': 4, 'IDIGNORE': 5, 'IDYES': 6, 'IDNO': 7,
           'ID_FILE_OPEN': 0xe101, 'ID_FILE_CLOSE': 0xe102, 'ID_FILE_SAVE': 0xe103}
    ids.update({'ID_FILE_MRU_FILE' + str(i + 1): 0xe110 + i for i in range(16)})
    for name, number in re.findall(r'^#define\s+(\w+)\s+(-?\d+)\s*$', (ROOT / 'src/win32/resource.h').read_text(), re.M):
        ids[name] = int(number)

    def ident(name):
        return ids.get(name, int(name) if re.fullmatch('-?\d+', name) else None)

    changes, skipped = [], []

    def replace(match, text, context):
        old = match.group()
        new = quote(text)
        if old != new:
            changes.append({'context': context, 'source': old, 'translation': text})
        return new

    # Match the complete block, including nested menu BEGIN/END pairs.
    lines = source.splitlines(True)
    current, kind, depth, begun, menu_index, occurrences = None, None, 0, False, 0, {}
    output = []
    position = 0
    for line in lines:
        following_position = position + len(line)
        position = following_position
        decl = re.match(r'^(\w+)\s+(DIALOGEX|DIALOG|MENU)\b', line)
        if decl:
            current = str(ident(decl[1]) if ident(decl[1]) is not None else decl[1])
            kind = 'menus' if decl[2] == 'MENU' else 'dialogs'
            depth, begun, menu_index, occurrences = 0, False, 0, {}
        if current is not None:
            item = extracted[kind].get(current)
            if item and kind == 'dialogs':
                if line.startswith('CAPTION '):
                    line = re.sub(QUOTED, lambda m: replace(m, item['caption'], current + ':caption'), line, count=1)
                control = re.match(r'\s*(?:LTEXT|CTEXT|RTEXT|PUSHBUTTON|DEFPUSHBUTTON|CHECKBOX|AUTOCHECKBOX|RADIOBUTTON|AUTORADIOBUTTON|GROUPBOX|CONTROL|ICON)\s+(' + QUOTED + r'|\w+),\s*(\w+|-\d+)', line)
                if control:
                    cid = ident(control[2])
                    cid = cid & 0xffffffff if cid is not None else None
                    options = [c for c in item['controls'] if c['id'] in (cid, 0xffff if cid == 0xffffffff else cid)]
                    index = occurrences.get(cid, 0)
                    occurrences[cid] = index + 1
                    if control[1].startswith('"') and index < len(options) and isinstance(options[index]['text'], str):
                        line = re.sub(QUOTED, lambda m: replace(m, options[index]['text'], current + ':' + control[2]), line, count=1)
            elif item and kind == 'menus':
                entry = re.match(r'\s*(POPUP|MENUITEM)\s+(' + QUOTED + r'|SEPARATOR)(?:\s*,\s*(\w+))?', line)
                if entry:
                    target = None
                    if entry[1] == 'MENUITEM' and entry[2] != 'SEPARATOR':
                        matches = [e for e in item if e['id'] == ident(entry[3])]
                        if len(matches) == 1:
                            target = matches[0]
                    elif entry[1] == 'POPUP':
                        # Popup IDs are absent. Match by its first following command.
                        following = source[following_position:]
                        next_cmd = re.search(r'MENUITEM\s+' + QUOTED + r'\s*,\s*(\w+)', following)
                        command = ident(next_cmd[1]) if next_cmd else None
                        matches = []
                        for j, candidate in enumerate(item):
                            if candidate['id'] is None:
                                next_id = next((e['id'] for e in item[j + 1:] if e['id'] not in (None, 0)), None)
                                if next_id == command:
                                    matches.append(candidate)
                        if len(matches) == 1:
                            target = matches[0]
                        elif menu_index < len(item) and item[menu_index]['id'] is None:
                            target = item[menu_index]
                    if target is not None:
                        line = re.sub(QUOTED, lambda m: replace(m, target['text'], current + ':menu:' + str(menu_index)), line, count=1)
                    elif entry[2] != 'SEPARATOR':
                        skipped.append({'menu': current, 'index': menu_index, 'source': entry[0].strip()})
                    menu_index += 1
            if line.strip() == 'BEGIN':
                depth += 1
                begun = True
            elif line.strip() == 'END':
                depth -= 1
                if begun and depth == 0:
                    current = kind = None
        output.append(line)
    source = ''.join(output)
    # String table entries may wrap after their symbolic ID.
    pattern = r'(\b(?:IDS_\w+|ID_\w+)\s+)(' + QUOTED + ')'
    def string_entry(m):
        name = m[1].split()[0]
        value = extracted['strings'].get(str(ident(name)))
        if value is None:
            return m.group()
        return m[1] + re.sub(QUOTED, lambda q: replace(q, value, name), m[2], count=1)
    source = re.sub(pattern, string_entry, source)
    return source, changes, skipped


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true')
    p.add_argument('--reference-exe', type=Path, help='Optional original PE; otherwise use the committed reference-zh.json')
    args = p.parse_args()
    if args.reference_exe:
        reference = args.reference_exe.resolve()
        extracted = extract(reference)
        reference_name = reference.name
        reference_hash = hashlib.sha256(reference.read_bytes()).hexdigest()
    else:
        extracted = json.loads((ROOT / 'localization/reference-zh.json').read_text(encoding='utf-8'))
        previous = json.loads((ROOT / 'localization/migration-report.json').read_text(encoding='utf-8'))
        reference_name, reference_hash = previous['reference'], previous['sha256']
    changes, skipped, files = [], [], []
    supplemented = {'ui': 0, 'strings': 0, 'filters': 0}
    for relative in ('src/win32/vba.rc', 'src/win32/7zip/7zip.rc'):
        rc = ROOT / relative
        # Original source uses Windows-1252; migrated source is explicitly UTF-8.
        raw = rc.read_bytes()
        source = raw.decode('utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'cp1252')
        source, local_changes, local_skipped = migrate(extracted, source)
        source, local_counts = supplement(source)
        for entry in local_changes:
            entry['file'] = relative
        changes.extend(local_changes)
        skipped.extend(local_skipped)
        for key in supplemented:
            supplemented[key] += local_counts[key]
        source = source.replace('#pragma code_page(1252)', '#pragma code_page(65001)')
        source = source.replace('LANGUAGE LANG_ENGLISH, SUBLANG_ENGLISH_US', 'LANGUAGE LANG_CHINESE, SUBLANG_CHINESE_SIMPLIFIED')
        files.append((rc, source))
    report = {'reference': reference_name,
              'sha256': reference_hash,
              'counts': {k: len(v) for k, v in extracted.items()},
              'change_count': len(changes), 'menu_mismatches': skipped,
              'supplemented': supplemented}
    dest = ROOT / 'localization'
    dest.mkdir(exist_ok=True)
    (dest / 'reference-zh.json').write_text(json.dumps(extracted, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (dest / 'migration-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if args.apply:
        for rc, source in files:
            # Preserve the resource files' original Windows line endings.
            rc.write_bytes(b'\xef\xbb\xbf' + source.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
    print(json.dumps({'counts': report['counts'], 'changed': len(changes), 'supplemented': supplemented, 'menu_mismatches': len(skipped)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
