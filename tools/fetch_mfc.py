"""Fetch exact Microsoft MFC build packages from the installed VS catalog.

Uses bounded HTTP ranges because full-file responses can stall on this network.
Every complete package must match the catalog SHA-256 before extraction.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'build/dependencies/mfc'
IDS = ('Microsoft.VC.14.43.17.13.MFC.MBCS.base',)


def download(payload):
    target = DEST / payload['fileName']
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == payload['sha256']:
        return target
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(payload['url'], headers={'Range': 'bytes=0-0'})
    with opener.open(request, timeout=30) as response:
        assert response.status == 206, 'HTTP range support required'
        total = int(response.headers['Content-Range'].split('/')[-1])
        response.read()
    chunk_size = 262144
    parts = (total + chunk_size - 1) // chunk_size
    chunks = target.with_suffix('.parts')
    chunks.mkdir(parents=True, exist_ok=True)

    def get_part(index):
        start, end = index * chunk_size, min(total, (index + 1) * chunk_size) - 1
        path = chunks / str(index)
        if path.exists() and path.stat().st_size == end - start + 1:
            return path
        for attempt in range(3):
            try:
                local = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                req = urllib.request.Request(payload['url'], headers={'Range': 'bytes=%d-%d' % (start, end)})
                with local.open(req, timeout=30) as r:
                    assert r.status == 206
                    assert r.headers['Content-Range'].startswith('bytes %d-%d/' % (start, end))
                    data = r.read()
                assert len(data) == end - start + 1
                path.write_bytes(data)
                return path
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1)

    with ThreadPoolExecutor(max_workers=12) as pool:
        for count, task in enumerate(as_completed([pool.submit(get_part, i) for i in range(parts)]), 1):
            task.result()
            if count % 16 == 0 or count == parts:
                print('%s: %d/%d ranges' % (payload['fileName'], count, parts), flush=True)
    with target.open('wb') as output:
        for i in range(parts):
            output.write((chunks / str(i)).read_bytes())
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    assert actual == payload['sha256'], 'Microsoft catalog SHA-256 mismatch: ' + target.name
    print('Verified SHA-256: ' + actual, flush=True)
    return target


def main():
    catalogs = Path(os.environ['ProgramData']) / 'Microsoft/VisualStudio/Packages/_Instances'
    packages = {}
    for catalog in catalogs.glob('*/catalog.json'):
        data = json.loads(catalog.read_text(encoding='utf-8-sig'))
        for package in data.get('packages', []):
            if package['id'] in IDS and package['version'] == '14.43.34808':
                packages[package['id']] = package
    assert all(ident in packages for ident in IDS), 'Matching installed VS catalog was not found'
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = []
    for ident in IDS:
        payload = packages[ident]['payloads'][0]
        archive = download(payload)
        extracted = []
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                normalized = name.replace('\\', '/')
                marker = '/atlmfc/lib/x86/'
                if marker in normalized and normalized.endswith('.lib'):
                    filename = normalized.rsplit('/', 1)[-1]
                    assert filename not in ('.', '..') and ':' not in filename
                    target = DEST / 'lib/x86' / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(name))
                    extracted.append(filename)
        manifest.append({'package': ident, 'version': packages[ident]['version'],
                         'payload': payload, 'sha256_verified': True, 'libraries': extracted})
        print('Extracted: ' + ', '.join(extracted), flush=True)
    (DEST / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
