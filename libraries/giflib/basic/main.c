/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <gif_lib.h>

enum { W = 32, H = 32 };

/* the GIF in memory: written by write_bytes, read by read_bytes */
struct memory {
    GifByteType data[4096];
    int size, at;
};

static int write_bytes(GifFileType *gif, GifByteType const *bytes, int n)
{
    struct memory *m = gif->UserData;
    if (m->size + n > (int)sizeof m->data)
        return 0;
    memcpy(m->data + m->size, bytes, n);
    m->size += n;
    return n;
}

static int read_bytes(GifFileType *gif, GifByteType *bytes, int n)
{
    struct memory *m = gif->UserData;
    if (n > m->size - m->at)
        n = m->size - m->at;
    memcpy(bytes, m->data + m->at, n);
    m->at += n;
    return n;
}

int main(void)
{
    static struct memory m;
    GifColorType const palette[4] = { { 230, 230, 230 }, { 40, 200, 60 }, { 220, 40, 40 }, { 40, 60, 220 } };
    GifByteType pixels[H][W];
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x)
            pixels[y][x] = (GifByteType)((y / 16) * 2 + x / 16); /* four quadrants, one palette entry each */

    int error = 0;
    GifFileType *out = EGifOpen(&m, write_bytes, &error);
    if (!out) {
        printf("EGifOpen: %s\n", GifErrorString(error));
        return 1;
    }
    ColorMapObject *map = GifMakeMapObject(4, palette);
    if (EGifPutScreenDesc(out, W, H, 2, 0, map) != GIF_OK || EGifPutImageDesc(out, 0, 0, W, H, false, NULL) != GIF_OK) {
        printf("EGifPutScreenDesc/EGifPutImageDesc: %s\n", GifErrorString(out->Error));
        return 1;
    }
    for (int y = 0; y < H; ++y)
        if (EGifPutLine(out, pixels[y], W) != GIF_OK) {
            printf("EGifPutLine: %s\n", GifErrorString(out->Error));
            return 1;
        }
    GifFreeMapObject(map);
    if (EGifCloseFile(out, &error) != GIF_OK) {
        printf("EGifCloseFile: %s\n", GifErrorString(error));
        return 1;
    }

    GifFileType *in = DGifOpen(&m, read_bytes, &error);
    if (!in || DGifSlurp(in) != GIF_OK) {
        printf("DGifOpen/DGifSlurp: %s\n", GifErrorString(in ? in->Error : error));
        return 1;
    }
    if (in->SWidth != W || in->SHeight != H || in->ImageCount != 1 || !in->SColorMap || in->SColorMap->ColorCount != 4) {
        puts("the GIF came back with another size, image count or palette");
        return 1;
    }
    if (memcmp(in->SavedImages[0].RasterBits, pixels, sizeof pixels) != 0 || memcmp(in->SColorMap->Colors, palette, sizeof palette) != 0) {
        puts("the pixels or the palette came back changed");
        return 1;
    }
    DGifCloseFile(in, &error);
    printf("giflib %d.%d.%d: %dx%d in %d bytes\n", GIFLIB_MAJOR, GIFLIB_MINOR, GIFLIB_RELEASE, W, H, m.size);
    puts("ok");
    return 0;
}
