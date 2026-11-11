"""Run the patched BoostDeck::refresh() in an ARM emulator and record every model update."""
import re
import struct
import sys
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UcError
from unicorn.arm_const import *

lib = open(sys.argv[1], 'rb').read()
PLT = {0x24a4: 'updateModel(str)', 0x2534: 'String::~', 0x25e8: 'snprintf', 0x2618: 'updateModel(img)',
       0x2798: 'bd_is_fresh', 0x27bc: 'bd_mono_ms', 0x27e0: 'strcmp', 0x2804: 'bd_display_value',
       0x2864: 'String(char*)', 0x287c: 'ImageID(unsigned)', 0x28a0: 'strcpy'}
THIS, STACK, RET = 0x20000, 0x80000, 0x90000

mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
mu.mem_map(0, 0x10000)
mu.mem_write(0, lib[:0x4964])
mu.mem_write(0x5964, lib[0x4964:0x4964 + 0x47c])
mu.mem_map(THIS, 0x2000)
mu.mem_map(STACK - 0x10000, 0x10000)
mu.mem_map(RET, 0x1000)
mu.reg_write(UC_ARM_REG_C1_C0_2, mu.reg_read(UC_ARM_REG_C1_C0_2) | (0xf << 20))
mu.reg_write(UC_ARM_REG_FPEXC, 0x40000000)

calls = []


def cstr(addr):
    out = b''
    while True:
        c = mu.mem_read(addr, 1)
        if c == b'\0':
            return out.decode()
        out += bytes(c)
        addr += 1


def snprintf(r):
    buf, fmt = r[0], cstr(r[2])
    sp = mu.reg_read(UC_ARM_REG_SP)
    slots = [('r', r[3])]
    cursor = 0

    def word():
        nonlocal cursor
        if slots:
            return slots.pop()[1]
        v = struct.unpack('<I', mu.mem_read(sp + cursor, 4))[0]
        cursor += 4
        return v

    def double():
        nonlocal cursor
        slots.clear()
        cursor = (cursor + 7) & ~7
        v = struct.unpack('<d', mu.mem_read(sp + cursor, 8))[0]
        cursor += 8
        return v

    def sub(m):
        spec = m.group(0)
        if spec.endswith('s'):
            s = cstr(word())
            return s[:0] if spec == '%.0s' else s
        return spec % double()
    text = re.sub(r'%[-+.0-9]*[sfg]', sub, fmt)
    mu.mem_write(buf, text.encode() + b'\0')
    return len(text)


def hook(uc, address, size, state):
    if address == RET:
        uc.emu_stop()
        return
    name = PLT.get(address)
    if not name:
        return
    r = [uc.reg_read(getattr(__import__('unicorn.arm_const', fromlist=['x']), f'UC_ARM_REG_R{i}')) for i in range(4)]
    ret = 0
    if name == 'snprintf':
        ret = snprintf(r)
    elif name == 'bd_is_fresh':
        ret = 1
    elif name == 'bd_mono_ms':
        uc.reg_write(UC_ARM_REG_R1, 0)
        ret = 1100
    elif name == 'strcmp':
        a, b = cstr(r[0]), cstr(r[1])
        ret = 0 if a == b else 1
    elif name == 'strcpy':
        uc.mem_write(r[0], cstr(r[1]).encode() + b'\0')
        ret = r[0]
    elif name == 'bd_display_value':
        uc.reg_write(UC_ARM_REG_R1, r[3])
        ret = r[2]
    elif name == 'ImageID(unsigned)':
        uc.mem_write(r[0], struct.pack('<I', r[1]))
        ret = r[0]
    elif name == 'updateModel(img)':
        calls.append((r[1], struct.unpack('<I', uc.mem_read(r[2], 4))[0]))
    else:
        raise SystemExit(f'unexpected call: {name}')
    uc.reg_write(UC_ARM_REG_R0, ret & 0xffffffff)
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))


mu.hook_add(UC_HOOK_CODE, hook)


def refresh(values, received=True):
    calls.clear()
    if received:
        mu.mem_write(THIS + 0x1e0, struct.pack('<Q', 1000))
    else:
        mu.mem_write(THIS + 0x1e0, struct.pack('<Q', 0))
    for i, v in enumerate(values):
        mu.mem_write(THIS + 0x180 + 8 * i, struct.pack('<d', v))
    mu.reg_write(UC_ARM_REG_R0, THIS)
    mu.reg_write(UC_ARM_REG_SP, STACK - 0x100)
    mu.reg_write(UC_ARM_REG_LR, RET)
    try:
        mu.emu_start(0x29fc, RET, count=200000)
    except UcError as e:
        raise SystemExit(f'emulation fault at {mu.reg_read(UC_ARM_REG_PC):#x}: {e}')
    return list(calls)


SYMS = {**{57100 + i: str(i) for i in range(10)}, 57110: '.', 57111: '-', 57112: ' ',
        **{57120 + i: str(i) for i in range(10)}, 57130: '.', 57131: '-', 57132: ' '}


def render(updates):
    cells = {}
    for model, image in updates:
        if 120 <= model < 160:
            cells[model] = SYMS.get(image, '?')
    out = []
    for g in range(8):
        out.append(''.join(cells.get(120 + g * 5 + k, '_') for k in range(5)))
    return out


if __name__ == '__main__':
    names = ['boost', 'afr', 'timing', 'intake', 'trans', 'rail', 'oil', 'coolant']
    print('no data :', render(refresh([0] * 8, received=False)))
    for case in ([1.4, 14.4, 13.3, 102.0, 126.0, 2444.0, 56.0, 196.0],
                 [-9.46, 9.95, -12.5, 99.5, 199.6, 1207.4, 8.0, -5.6],
                 [18.44, 12.1, 0.0, 71.2, 100.4, 15.0, 33.6, 184.6]):
        updates = refresh(case)
        bars = [u for u in updates if 60 <= u[0] < 68]
        print('values  :', case)
        print('cells   :', render(updates), f'bars updated: {len(bars)}')
