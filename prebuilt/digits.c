/* Big-digit renderer spliced into libBoostDeck.so (replaces unused bd_decode_did).
   Called from BoostDeck::refresh() with the already formatted value text.
   Mirrors ShiftDeck's digits(): one image component per character cell. */
typedef struct { unsigned w[2]; } __attribute__((aligned(8))) ImageID;
extern void imgid_ctor(ImageID *self, unsigned id);
extern void update_image(void *app, unsigned model, const ImageID *image);

#define MODEL_BASE 120u   /* 5 image models per gauge: 120..159 */
#define SMALL 57100u      /* 0-9 digits, 10 '.', 11 '-', 12 blank */
#define BIG   57120u

static unsigned code(char c) {
    if (c >= '0' && c <= '9') return (unsigned)(c - '0');
    if (c == '.') return 10u;
    if (c == '-') return 11u;
    return 12u;
}

void boost_digits(void *app, unsigned gauge, const char *text) {
    char cell[5] = {' ', ' ', ' ', ' ', ' '};
    char whole[8];
    unsigned n = 0, dot = 0, has_dot = 0, k;
    while (text[n] && n < 15) {
        if (text[n] == '.' && !has_dot) { has_dot = 1; dot = n; }
        n++;
    }
    if (!has_dot) dot = n;
    unsigned w = dot > 6 ? 6 : dot;            /* integer part, sign included */
    for (k = 0; k < w; ++k) whole[k] = text[dot - w + k];
    whole[w] = 0;

    if (gauge <= 2) {                          /* boost, AFR, timing: "III.F" */
        if (has_dot) {
            for (k = 0; k < 3 && k < w; ++k) cell[2 - k] = whole[w - 1 - k];
            cell[3] = '.';
            cell[4] = text[dot + 1] ? text[dot + 1] : '0';
        } else {                               /* "--" while waiting for data */
            for (k = 0; k < 3 && k < w; ++k) cell[2 - k] = whole[w - 1 - k];
        }
    } else {                                   /* whole numbers, rounded, cells 1..4 */
        if (has_dot && text[dot + 1] >= '5' && text[dot + 1] <= '9') {
            int j = (int)w - 1;
            while (j >= 0 && whole[j] == '9') whole[j--] = '0';
            if (j >= 0 && whole[j] >= '0' && whole[j] <= '8') whole[j]++;
            else if (w < 6) {                  /* 99.5 -> 100, -9.5 -> -10 */
                unsigned at = (w && whole[0] == '-') ? 1u : 0u;
                for (k = w + 1; k > at; --k) whole[k] = whole[k - 1];
                whole[at] = '1';
                w++;
            }
        }
        for (k = 0; k < 4 && k < w; ++k) cell[4 - k] = whole[w - 1 - k];
    }
    unsigned base = gauge == 0 ? BIG : SMALL;
    for (k = 0; k < 5; ++k) {
        ImageID image;
        imgid_ctor(&image, base + code(cell[k]));
        update_image(app, MODEL_BASE + gauge * 5u + k, &image);
    }
}
