"""BoostDeck layout modeled on the reference photo.

Dynamic parts (driven by the unchanged native code): one value label and one
bar image per gauge. Everything else (names, units, M stripe, psi scale, red
zone, divider) lives in one static image layer drawn underneath.
For the Nov 7 prebuilt payload (8 themes). Pair with patch_lib.py and splice.py.
"""
import sys
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from PIL import Image, ImageDraw, ImageFont

OUT = Path(sys.argv[1])
FONTS = Path(__file__).resolve().parents[1] / 'source' / 'native' / 'tools' / 'fonts'
font = lambda size, weight='SemiBold': ImageFont.truetype(str(FONTS / f'BarlowCondensed-{weight}.ttf'), size)

# Theme order must match the patched kColorNames in libBoostDeck.so.
THEMES = (
    ('Ice Blue', '#6ccff6', '#a9e6ff'), ('Orange', '#ff6a1f', '#ffa070'), ('Green', '#5fdc8c', '#a6f0c2'),
    ('White', '#e3e9ee', '#ffffff'), ('Purple', '#a77bff', '#cdb4ff'), ('Pink', '#ff6cba', '#ffb0da'),
    ('Cyan', '#28e6dc', '#9cf6f0'), ('Red', '#ff4848', '#ff9a9a'),
)
GAUGES, STEPS, FIRST = 8, 32, 55000
LAYER_ID = 57000

# Bar art geometry (drawn at the boost bar's on-screen size, scaled down for the rest)
BW, BH = 745, 65
SEGMENTS, GAP, SLANT = 14, 9, 16
USABLE = BW - SLANT
SEG = (USABLE - GAP * (SEGMENTS - 1)) / SEGMENTS
EMPTY = (150, 172, 192, 92)   # translucent so the red zone underneath shows through

# 1280x480 layout in the plugin's coordinate space
LAYER = (40, 20, 1100, 420)
BOOST_BAR = (375, 57, BW, BH)
ROWS = (197, 252, 307, 362)
COLUMNS = {   # name x, value box (x, w), unit x, bar (x, w)
    0: (97, (262, 96), 362, (398, 205)),
    1: (646, (806, 92), 902, (925, 197)),
}
SMALL_H = 18
# Big-digit cells driven by the spliced digit renderer (models 120 + gauge*5 + cell)
DIGIT_MODEL = 120
SMALL_ID, BIG_ID = 57100, 57120          # +0..9 digits, +10 '.', +11 '-', +12 blank
SMALL_CELL, SMALL_DOT, SMALL_H_DIG = 23, 10, 40
BIG_CELL, BIG_DOT, BIG_H_DIG = 48, 20, 84
BOOST_RIGHT, BOOST_TOP = 370, 50
VALUE_RIGHT = {0: 357, 1: 897}
DECIMAL = {0, 1, 2}                      # boost, AFR, timing show one decimal
DIGIT_COLOR = '#f5f8fb'
# gauge index -> (column, row, name, unit); native order: Boost, AFR, Timing, Intake, Trans, Rail, Oil, Coolant
PLACEMENT = {
    1: (0, 0, 'AFR', ''), 2: (0, 1, 'TIMING', 'DEG'), 5: (0, 2, 'RAIL', 'PSI'), 6: (0, 3, 'OIL', 'PSI'),
    3: (1, 0, 'INTAKE', '°F'), 7: (1, 1, 'COOLANT', '°F'), 4: (1, 2, 'TRANS', '°F'),
}
NAME, DIM, LINE, REDZONE = '#d6dde4', '#9fb0bf', '#55707f', (196, 46, 54, 255)


def seg_x(s):
    return s * (SEG + GAP)


def para(draw, a, b, top, bottom, fill, slant=SLANT, dx=0, dy=0):
    draw.polygon([(dx + a + slant, dy + top), (dx + b + slant, dy + top), (dx + b, dy + bottom), (dx + a, dy + bottom)], fill=fill)


def bar(step, fill, light):
    image = Image.new('RGBA', (BW, BH))
    draw = ImageDraw.Draw(image)
    pos = USABLE * step / STEPS
    for s in range(SEGMENTS):
        a, b = seg_x(s), seg_x(s) + SEG
        para(draw, a, b, 0, BH - 1, EMPTY)
        if step and pos > a:
            end = min(b, pos)
            para(draw, a, end, 0, BH - 1, fill)
            band = BH * 0.22                           # lighter top edge, same slant
            shift = SLANT * (1 - band / (BH - 1))
            draw.polygon([(a + SLANT, 0), (end + SLANT, 0), (end + shift, band), (a + shift, band)], fill=light)
    if step:
        m = max(0.0, min(USABLE - 6, pos - 3))
        para(draw, m, m + 6, 0, BH - 1, '#ffffff')
    return image


def text(draw, xy, value, size, color=NAME, weight='SemiBold', anchor='ls'):
    draw.text(xy, value, font=font(size, weight), fill=color, anchor=anchor)


def layer():
    lx, ly, w, h = LAYER
    image = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(image)
    at = lambda x, y: (x - lx, y - ly)
    # boost header
    text(d, at(97, 57), 'BOOST', 21)
    sx, sy = at(160, 43)
    for i, color in enumerate(('#5fb3e6', '#2c4f9e', '#d1313c')):
        d.polygon([(sx + i * 11 + 4, sy), (sx + i * 11 + 13, sy), (sx + i * 11 + 9, sy + 11), (sx + i * 11, sy + 11)], fill=color)
    text(d, at(97, 132), 'PSI', 15, DIM)
    # red zone under the last two boost segments
    bx, by = at(BOOST_BAR[0], BOOST_BAR[1])
    for s in (12, 13):
        para(d, seg_x(s), seg_x(s) + SEG, 0, BH - 1, REDZONE, dx=bx, dy=by)
    # psi scale aligned to the segment bottoms
    tick_y = by + BH + 6
    for half in range(15):
        psi = half * 2.5
        x = bx + USABLE * psi / 35
        major = half % 2 == 0
        color = '#ff4a4f' if psi >= 30 else '#c9d3dc'
        d.rectangle((x - 1, tick_y, x, tick_y + (9 if major else 5)), fill=color)
        if major:
            text(d, (x, tick_y + 26), str(int(psi)), 15, color, anchor='ms')
    # divider
    d.rectangle((*at(95, 160), *at(1122, 161)), fill=LINE)
    # gauge rows
    for _, (col, row, name, unit) in PLACEMENT.items():
        name_x, (vx, vw), unit_x, _ = COLUMNS[col]
        cy = ROWS[row]
        text(d, at(name_x, cy + 8), name, 21)
        if unit:
            text(d, at(VALUE_RIGHT[col] + 3, cy + 15), unit, 13, DIM, 'Medium')
    return image


def digit_cells(gauge):
    """Screen boxes for the cells the renderer fills, right aligned like the photo."""
    if gauge == 0:
        wide, dot, height, right, top = BIG_CELL, BIG_DOT, BIG_H_DIG, BOOST_RIGHT, BOOST_TOP
    else:
        col, row = PLACEMENT[gauge][:2]
        wide, dot, height, right = SMALL_CELL, SMALL_DOT, SMALL_H_DIG, VALUE_RIGHT[col]
        top = ROWS[row] - height // 2
    widths = [wide, wide, wide, dot, wide] if gauge in DECIMAL else [0, wide, wide, wide, wide]
    boxes, x = [], right
    for cell in range(4, -1, -1):
        x -= widths[cell]
        if widths[cell]:
            boxes.append((cell, (x, top, widths[cell], height)))
    return sorted(boxes)


def glyph(char, width, height, size):
    image = Image.new('RGBA', (width, height))
    if char != ' ':
        d = ImageDraw.Draw(image)
        d.text((width / 2, height - height * 0.08), char, font=font(size, 'SemiBold'), fill=DIGIT_COLOR, anchor='ms')
    return image


def props(component, box, image=False):
    x, y, w, h = box
    p = ET.SubElement(component, 'properties')
    for prop, value in [(20, x), (21, y), (9, w), (10, h)] + ([(2, 'false'), (3, 'true')] if image else []):
        ET.SubElement(p, 'property', id=str(prop), value=str(value))


def layout():
    root = ET.Element('pluginApps')
    app = ET.SubElement(root, 'pluginApp', applicationType='VehicleInformation', applicationWeight='210', text='BoostDeck')
    entry = ET.SubElement(app, 'entryButton', id='1', action='10')
    ET.SubElement(ET.SubElement(entry, 'properties'), 'property', id='23', value='2')
    actions = ET.SubElement(app, 'actions')
    for identifier, target in ((10, 100), (31, 104)):
        ET.SubElement(actions, 'hmiAction', id=str(identifier), target=str(target))
    for identifier in range(40, 40 + len(THEMES)):
        ET.SubElement(actions, 'raAction', id=str(identifier))
    models = ET.SubElement(app, 'models')
    states = ET.SubElement(app, 'hmiStates')
    gauges = ET.SubElement(states, 'hmiState', id='100', text='BoostDeck')
    ET.SubElement(ET.SubElement(gauges, 'optionComponents'), 'button', id='33', action='31', text='Gauge color')
    content = ET.SubElement(gauges, 'components')
    for i in range(GAUGES):
        ET.SubElement(models, 'raDataModel', id=str(50 + i), modelType='Richtext')
        ET.SubElement(models, 'imageIdModel', id=str(60 + i), imageId=str(FIRST))
    ET.SubElement(models, 'imageIdModel', id='70', imageId=str(LAYER_ID))
    for i in range(GAUGES):
        blank = (BIG_ID if i == 0 else SMALL_ID) + 12
        for cell in range(5):
            ET.SubElement(models, 'imageIdModel', id=str(DIGIT_MODEL + i * 5 + cell), imageId=str(blank))
    props(ET.SubElement(content, 'image', id='210', model='70'), LAYER, True)
    props(ET.SubElement(content, 'image', id='200', model='60'), BOOST_BAR, True)
    for cell, box in digit_cells(0):
        props(ET.SubElement(content, 'image', id=str(400 + cell), model=str(DIGIT_MODEL + cell)), box, True)
    for i, (col, row, _, _) in sorted(PLACEMENT.items()):
        _, (vx, vw), _, (bx, bw) = COLUMNS[col]
        cy = ROWS[row]
        props(ET.SubElement(content, 'image', id=str(200 + i), model=str(60 + i)), (bx, cy - SMALL_H // 2, bw, SMALL_H), True)
        for cell, box in digit_cells(i):
            props(ET.SubElement(content, 'image', id=str(400 + i * 5 + cell), model=str(DIGIT_MODEL + i * 5 + cell)), box, True)
    ET.SubElement(models, 'raDataModel', id='110', modelType='Richtext')
    picker = ET.SubElement(states, 'hmiState', id='104', parentId='100', text='Gauge color')
    content = ET.SubElement(picker, 'components')
    ET.SubElement(content, 'label', id='389', model='110')
    for i, (name, _, _) in enumerate(THEMES):
        ET.SubElement(content, 'button', id=str(390 + i), action=str(40 + i), text=name)
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(OUT / 'BoostDeck.xml', encoding='utf-8', xml_declaration=True)


def png(image):
    data = BytesIO()
    image.save(data, format='PNG', optimize=True)
    return data.getvalue()


def assets():
    with ZipFile(OUT / 'BoostDeck_ALL_Images.zip', 'w', compression=ZIP_DEFLATED) as archive:
        for theme, (_, fill, light) in enumerate(THEMES):
            for step in range(STEPS + 1):
                if theme and not step:
                    continue
                archive.writestr(ZipInfo(f'{FIRST + theme * STEPS + step}.png'), png(bar(step, fill, light)), ZIP_DEFLATED)
        archive.writestr(ZipInfo(f'{LAYER_ID}.png'), png(layer()), ZIP_DEFLATED)
        for base, wide, dot, height, size in ((SMALL_ID, SMALL_CELL, SMALL_DOT, SMALL_H_DIG, 46),
                                              (BIG_ID, BIG_CELL, BIG_DOT, BIG_H_DIG, 104)):
            for code, char in enumerate('0123456789.- '):
                width = dot if char == '.' else wide
                archive.writestr(ZipInfo(f'{base + code}.png'), png(glyph(char, width, height, size)), ZIP_DEFLATED)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    layout()
    assets()
    print('wrote', OUT)
