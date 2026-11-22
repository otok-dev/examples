/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tiffio.h>

enum { W = 32, H = 32 };

/* the TIFF in memory, behind the procedures of TIFFClientOpen */
struct memory {
    unsigned char *data;
    toff_t size, capacity, at;
};

static tmsize_t read_proc(thandle_t handle, void *buffer, tmsize_t n)
{
    struct memory *m = handle;
    toff_t const left = m->at < m->size ? m->size - m->at : 0;
    if ((toff_t)n > left)
        n = (tmsize_t)left;
    memcpy(buffer, m->data + m->at, (size_t)n);
    m->at += n;
    return n;
}

static tmsize_t write_proc(thandle_t handle, void *buffer, tmsize_t n)
{
    struct memory *m = handle;
    if (m->at + n > m->capacity) {
        toff_t capacity = m->capacity ? m->capacity * 2 : 4096;
        while (capacity < m->at + n)
            capacity *= 2;
        unsigned char *data = realloc(m->data, (size_t)capacity);
        if (!data)
            return -1;
        memset(data + m->capacity, 0, (size_t)(capacity - m->capacity));
        m->data = data;
        m->capacity = capacity;
    }
    memcpy(m->data + m->at, buffer, (size_t)n);
    m->at += n;
    if (m->at > m->size)
        m->size = m->at;
    return n;
}

static toff_t seek_proc(thandle_t handle, toff_t offset, int whence)
{
    struct memory *m = handle;
    m->at = (whence == SEEK_SET ? 0 : whence == SEEK_CUR ? m->at : m->size) + offset;
    return m->at;
}

static int close_proc(thandle_t handle) { (void)handle; return 0; }
static toff_t size_proc(thandle_t handle) { return ((struct memory *)handle)->size; }
static int map_proc(thandle_t handle, void **base, toff_t *size) { (void)handle, (void)base, (void)size; return 0; }
static void unmap_proc(thandle_t handle, void *base, toff_t size) { (void)handle, (void)base, (void)size; }

static TIFF *open_memory(struct memory *m, char const *mode)
{
    m->at = 0;
    return TIFFClientOpen("memory", mode, m, read_proc, write_proc, seek_proc, close_proc, size_proc, map_proc, unmap_proc);
}

int main(void)
{
    static unsigned char image[H][W][3], back[H][W][3];
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x) {
            image[y][x][0] = (unsigned char)(x * 8);
            image[y][x][1] = (unsigned char)(y * 8);
            image[y][x][2] = (unsigned char)((x + y) * 4);
        }
    if (!TIFFIsCODECConfigured(COMPRESSION_LZMA)) {
        puts("this libtiff has no LZMA codec");
        return 1;
    }

    struct memory m = { 0 };
    TIFF *out = open_memory(&m, "w");
    if (!out)
        return 1;
    TIFFSetField(out, TIFFTAG_IMAGEWIDTH, W);
    TIFFSetField(out, TIFFTAG_IMAGELENGTH, H);
    TIFFSetField(out, TIFFTAG_BITSPERSAMPLE, 8);
    TIFFSetField(out, TIFFTAG_SAMPLESPERPIXEL, 3);
    TIFFSetField(out, TIFFTAG_PHOTOMETRIC, PHOTOMETRIC_RGB);
    TIFFSetField(out, TIFFTAG_PLANARCONFIG, PLANARCONFIG_CONTIG);
    TIFFSetField(out, TIFFTAG_COMPRESSION, COMPRESSION_LZMA);
    TIFFSetField(out, TIFFTAG_ROWSPERSTRIP, H);
    for (int y = 0; y < H; ++y)
        if (TIFFWriteScanline(out, image[y], y, 0) != 1)
            return 1;
    TIFFClose(out);

    TIFF *in = open_memory(&m, "r");
    if (!in)
        return 1;
    uint32_t width = 0, height = 0;
    uint16_t compression = 0;
    TIFFGetField(in, TIFFTAG_IMAGEWIDTH, &width);
    TIFFGetField(in, TIFFTAG_IMAGELENGTH, &height);
    TIFFGetField(in, TIFFTAG_COMPRESSION, &compression);
    if (width != W || height != H || compression != COMPRESSION_LZMA) {
        printf("read %ux%u with compression %u\n", (unsigned)width, (unsigned)height, (unsigned)compression);
        return 1;
    }
    for (int y = 0; y < H; ++y)
        if (TIFFReadScanline(in, back[y], y, 0) != 1)
            return 1;
    TIFFClose(in);
    if (memcmp(image, back, sizeof image) != 0) {
        puts("the image came back changed");
        return 1;
    }
    free(m.data);

    char const *version = TIFFGetVersion(); /* "LIBTIFF, Version 4.7.1\nCopyright ..." */
    printf("%.*s: %dx%d RGB, LZMA, in %u bytes\n", (int)strcspn(version, "\n"), version, W, H, (unsigned)m.size);
    puts("ok");
    return 0;
}
