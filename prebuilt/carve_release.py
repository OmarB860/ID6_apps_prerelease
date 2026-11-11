"""Recover the Nov 7 app payload from the prerelease Windows installer.

Usage: python3 carve_release.py "NBT Evo Gauge Installer.exe" OUT_DIR
Get the exe from the upstream history: git show 20afc90^:NBT-Evo-Gauges-Windows-x64.zip
Each recovered file is checked against the installer's own embedded file table.
"""
import io
import re
import struct
import sys
import zipfile
from pathlib import Path

exe = Path(sys.argv[1]).read_bytes()
out = Path(sys.argv[2])


def elf_end(offset):
    shoff, = struct.unpack_from('<I', exe, offset + 32)
    shentsize, shnum = struct.unpack_from('<HH', exe, offset + 46)
    end = shoff + shentsize * shnum
    for i in range(shnum):
        entry = offset + shoff + i * shentsize
        kind, = struct.unpack_from('<I', exe, entry + 4)
        start, size = struct.unpack_from('<II', exe, entry + 16)
        if kind != 8:
            end = max(end, start + size)
    return end


elves = []
for match in re.finditer(rb'\x7fELF\x01\x01\x01', exe):
    if struct.unpack_from('<H', exe, match.start() + 18)[0] == 40:
        elves.append(exe[match.start():match.start() + elf_end(match.start())])


def pick(test):
    found = [e for e in elves if test(e)]
    assert len(found) == 1, len(found)
    return found[0]


shared = lambda e: struct.unpack_from('<H', e, 16)[0] == 3
files = {
    'BoostDeck/libBoostDeck.so': pick(lambda e: shared(e) and b'_ZN9BoostDeck' in e),
    'ShiftDeck/libShiftDeck.so': pick(lambda e: shared(e) and b'ShiftDeck' in e and b'_ZN9BoostDeck' not in e),
    'MhdMaps/libMhdMaps.so': pick(lambda e: shared(e) and b'MhdMaps' in e and b'ShiftDeck' not in e),
    'BoostDeck/boostdeck-collector-qnx': pick(lambda e: not shared(e) and b'340i candidate' in e),
    'MhdMaps/mhd-maps-qnx': pick(lambda e: not shared(e) and b'Map result unknown' in e),
    'tools/gaugedeck-fileops': pick(lambda e: b'gaugedeck-fileops' in e),
}
files['ShiftDeck/shift-deck-qnx'] = pick(
    lambda e: not shared(e) and e not in files.values() and b'NBG3 %lu' in e)

for app in ('BoostDeck', 'ShiftDeck', 'MhdMaps'):
    m = re.search(rb'<\?xml[^>]*\?>\s*<plugin>\s*<name>' + app.encode() + rb'</name>[\s\S]*?</plugin>', exe)
    files[f'{app}/{app}.manifest'] = exe[m.start():m.end() + (exe[m.end():m.end() + 1] == b'\n')]
    text = {'MhdMaps': b'MHD Maps'}.get(app, app.encode())
    m = re.search(rb"<\?xml version=.1\.0. encoding=.utf-8.\?>\s*<pluginApps>\s*<pluginApp [^>]*text=\"" + text + rb'"[\s\S]*?</pluginApps>', exe)
    files[f'{app}/{app}.xml'] = m.group(0)

for m in re.finditer(rb'PK\x05\x06', exe):
    end = m.start()
    size, offset = struct.unpack_from('<II', exe, end + 12)
    comment, = struct.unpack_from('<H', exe, end + 20)
    start = end - size - offset
    blob = exe[start:end + 22 + comment]
    try:
        names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
    except zipfile.BadZipFile:
        continue
    app = {'55000.png': 'BoostDeck', '55800.png': 'ShiftDeck', '56000.png': 'MhdMaps'}.get(names[0])
    if app:
        files[f'{app}/{app}_ALL_Images.zip'] = blob

table = {struct.unpack_from('<Q', exe, i)[0] for i in range(8, len(exe) - 8, 8)
         if 0x140000000 <= struct.unpack_from('<Q', exe, i - 8)[0] < 0x150000000}
for name, blob in sorted(files.items()):
    match = len(blob) in table
    (out / name).parent.mkdir(parents=True, exist_ok=True)
    (out / name).write_bytes(blob)
    print(f'{name:40s} {len(blob):7d} bytes  embed table match: {match}')
    assert match, name
