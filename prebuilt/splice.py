"""Splice the digit renderer into libBoostDeck.so and hook it from refresh()."""
import sys
from elftools.elf.elffile import ELFFile
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

lib, cave_elf = sys.argv[1], sys.argv[2]
CAVE, CAVE_LIMIT = 0x3db0, 0x40b0          # bd_decode_did: not referenced by the plugin
HOOK, HOOK_END = 0x2c9c, 0x2cc8            # label text update in refresh()

data = bytearray(open(lib, 'rb').read())
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
original = [f'{i.mnemonic} {i.op_str}' for i in md.disasm(bytes(data[HOOK:HOOK_END]), HOOK)]
expected = ['add sl, sp, #0xd4', 'mov r1, r8', 'mov r0, sl', 'add r7, r7, #4', 'bl #0x2864',
            'add r1, r4, #0x32', 'mov r2, sl', 'mov r0, r6', 'bl #0x24a4', 'mov r0, sl', 'bl #0x2534']
assert original == expected, original

text = ELFFile(open(cave_elf, 'rb')).get_section_by_name('.text')
assert text['sh_addr'] == CAVE
code = text.data()
assert CAVE + len(code) <= CAVE_LIMIT, len(code)
data[CAVE:CAVE_LIMIT] = code + b'\x00' * (CAVE_LIMIT - CAVE - len(code))

ks = Ks(KS_ARCH_ARM, KS_MODE_ARM)
hook, _ = ks.asm('mov r0, r6; mov r1, r4; mov r2, r8; add r7, r7, #4; bl 0x%x; '
                 'nop; nop; nop; nop; nop; nop' % CAVE, HOOK)
assert len(hook) == HOOK_END - HOOK
data[HOOK:HOOK_END] = bytes(hook)
open(lib, 'wb').write(data)
for i in md.disasm(bytes(data[HOOK:HOOK_END]), HOOK):
    print(f'{i.address:x}: {i.mnemonic} {i.op_str}')
print(f'cave {len(code)} of {CAVE_LIMIT - CAVE} bytes')
