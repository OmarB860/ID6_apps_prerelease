"""Data-only patch for libBoostDeck.so (Nov 7 release, source 2d9990b).

Rewrites string literals in .rodata in place. Each new string fits in the
old slot and is NUL padded, so no code, offsets or symbols move.
"""
import hashlib
import sys

PATCHES = [
    # offset, original, replacement
    (0x46f4, b'%s%s   %.1f%s%s', b'%.0s%.0s%.1f'),     # most gauges: value only
    (0x4704, b'%s%s   %.0f%s%s', b'%.0s%.0s%.0f'),     # rail pressure
    (0x4714, b'%s   --', b'%.0s--'),                 # no data
    (0x471c, b'%s%s   %+.1f%s%s', b'%.0s%.0s%.1f'),    # boost
    (0x4828, b'BMW Orange', b'Ice Blue'),              # theme 0 (default)
    (0x4834, b'Blue', b'Orange'),                      # theme 1 (slot has 4 pad bytes)
]

path = sys.argv[1]
data = bytearray(open(path, 'rb').read())
print('before', hashlib.sha256(data).hexdigest())
for offset, old, new in PATCHES:
    slot = len(old) + 1
    while offset + slot < len(data) and data[offset + slot] == 0 and offset + slot < 0x4948:
        slot += 1
    assert data[offset:offset + len(old) + 1] == old + b'\0', hex(offset)
    assert len(new) + 1 <= slot, (new, slot)
    data[offset:offset + len(old) + 1] = b'\0' * (len(old) + 1)
    data[offset:offset + len(new)] = new
open(path, 'wb').write(data)
print('after ', hashlib.sha256(data).hexdigest())
