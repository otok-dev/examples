/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <webp/decode.h>
#include <webp/encode.h>

enum { W = 32, H = 32 };

int main(void)
{
    static uint8_t image[H][W][4];
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x) {
            image[y][x][0] = (uint8_t)(x * 8);
            image[y][x][1] = (uint8_t)(y * 8);
            image[y][x][2] = (uint8_t)((x ^ y) * 8);
            image[y][x][3] = (uint8_t)(x < 16 ? 255 : 128);
        }

    uint8_t *webp = NULL;
    size_t const size = WebPEncodeLosslessRGBA(&image[0][0][0], W, H, W * 4, &webp);
    if (size == 0) {
        puts("WebPEncodeLosslessRGBA failed");
        return 1;
    }
    int width = 0, height = 0;
    uint8_t *back = WebPDecodeRGBA(webp, size, &width, &height);
    if (!back || width != W || height != H) {
        printf("WebPDecodeRGBA gave %dx%d\n", width, height);
        return 1;
    }
    if (memcmp(back, image, sizeof image) != 0) {
        puts("the lossless image came back changed");
        return 1;
    }
    WebPFree(back);
    WebPFree(webp);
    int const version = WebPGetDecoderVersion();
    printf("libwebp %d.%d.%d: %dx%d RGBA in %u bytes\n", version >> 16, (version >> 8) & 0xff, version & 0xff, W, H, (unsigned)size);
    puts("ok");
    return 0;
}
