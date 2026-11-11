# Prebuilt big-digit BoostDeck

The root ZIPs in this fork are built without the QNX toolchain. They reuse the Nov 7 prerelease payload and change only BoostDeck. ShiftDeck and MHD Maps are untouched.

## What changed in the prebuilt payload

- **Layout and art.** `make_layout_nov7.py` generates `BoostDeck.xml` and `BoostDeck_ALL_Images.zip`: segmented bars, a boost bar with a 0 to 35 psi scale and red 30 to 35 zone, gauge names and units, and big digit images.
- **Text data.** `patch_lib.py` rewrites string literals in `libBoostDeck.so` so each value prints alone with one decimal (rail pressure as a whole number). It also renames themes 0 and 1 to Ice Blue (default) and Orange.
- **Digit renderer.** `digits.c` is compiled for ARM and placed by `splice.py` over `bd_decode_did`, which the plugin never calls. The text update in `BoostDeck::refresh()` (0x2c9c to 0x2cc4) now calls it. It works like ShiftDeck's `digits()`: each character of the value becomes an image ID (57100+ small, 57120+ big) sent to image models 120 to 159.
- **Not included.** Battery voltage, because the collector does not read it.

## Rebuild

```sh
git show 20afc90^:NBT-Evo-Gauges-Windows-x64.zip > old.zip && unzip old.zip -d old
python3 carve_release.py "old/NBT Evo Gauge Installer.exe" payload
python3 make_layout_nov7.py layout && cp layout/* payload/BoostDeck/
python3 patch_lib.py payload/BoostDeck/libBoostDeck.so
clang --target=armv7a-none-eabi -marm -mfloat-abi=softfp -Os -fno-unroll-loops -ffreestanding \
  -fno-builtin -fno-stack-protector -fno-jump-tables -fno-unwind-tables -fno-asynchronous-unwind-tables \
  -c digits.c -o digits.o
ld.lld -m armelf -static --section-start=.text=0x3db0 --defsym=imgid_ctor=0x287c \
  --defsym=update_image=0x2618 -e boost_digits -o digits.elf digits.o
python3 splice.py payload/BoostDeck/libBoostDeck.so digits.elf
python3 emulate.py payload/BoostDeck/libBoostDeck.so
```

Copy `payload/` into `source/payload/` of commit `2d9990b` (the source that matches the Nov 7 payload), then build the installer with Go.

`carve_release.py` checks every recovered file against the installer's embedded file table. `emulate.py` runs the patched `refresh()` in an ARM emulator and prints the digit cells for sample values.

## Status

- Checked on a host: payload validation, Go installer tests, ARM emulation of the patched `refresh()`.
- Not yet tested on a car.

## Source build

The same layout and renderer are in the source tree for anyone with the QNX toolchain: `source/native/tools/make_bars.py` and `BoostDeck::drawValue()` in `source/native/src/plugin.cpp`. The source version keeps the Multicolor theme.

Font: Barlow Condensed, SIL Open Font License, in `source/native/tools/fonts/`.
