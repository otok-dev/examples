/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h> /* before jpeglib.h, which uses FILE */
#include <stdlib.h>
#include <jpeglib.h>

enum { W = 32, H = 32 };

/* four quadrants: top-left, top-right, bottom-left, bottom-right */
static unsigned char const colors[4][3] = { { 230, 230, 230 }, { 40, 200, 60 }, { 220, 40, 40 }, { 40, 60, 220 } };

static int near(int a, int b) { return a - b <= 16 && b - a <= 16; }

int main(void)
{
    static unsigned char image[H][W][3], back[H][W][3];
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x)
            for (int c = 0; c < 3; ++c)
                image[y][x][c] = colors[(y / 16) * 2 + x / 16][c];

    /* compress into a buffer libjpeg allocates */
    struct jpeg_error_mgr errors;
    struct jpeg_compress_struct out;
    out.err = jpeg_std_error(&errors); /* errors print and exit */
    jpeg_create_compress(&out);
    unsigned char *jpeg = NULL;
    unsigned long size = 0;
    jpeg_mem_dest(&out, &jpeg, &size);
    out.image_width = W;
    out.image_height = H;
    out.input_components = 3;
    out.in_color_space = JCS_RGB;
    jpeg_set_defaults(&out);
    jpeg_set_quality(&out, 95, TRUE);
    jpeg_start_compress(&out, TRUE);
    while (out.next_scanline < H) {
        JSAMPROW row = image[out.next_scanline][0];
        jpeg_write_scanlines(&out, &row, 1);
    }
    jpeg_finish_compress(&out);
    jpeg_destroy_compress(&out);

    /* decompress it again */
    struct jpeg_decompress_struct in;
    in.err = jpeg_std_error(&errors);
    jpeg_create_decompress(&in);
    jpeg_mem_src(&in, jpeg, size);
    jpeg_read_header(&in, TRUE);
    in.out_color_space = JCS_RGB;
    jpeg_start_decompress(&in);
    if (in.output_width != W || in.output_height != H || in.output_components != 3) {
        printf("decoded %ux%u with %d components\n", in.output_width, in.output_height, in.output_components);
        return 1;
    }
    while (in.output_scanline < H) {
        JSAMPROW row = back[in.output_scanline][0];
        jpeg_read_scanlines(&in, &row, 1);
    }
    jpeg_finish_decompress(&in);
    jpeg_destroy_decompress(&in);
    free(jpeg);

    /* JPEG is lossy: the middle of each quadrant comes back close to its colour */
    for (int q = 0; q < 4; ++q) {
        unsigned char const *pixel = back[(q / 2) * 16 + 8][(q % 2) * 16 + 8];
        if (!near(pixel[0], colors[q][0]) || !near(pixel[1], colors[q][1]) || !near(pixel[2], colors[q][2])) {
            printf("quadrant %d came back as %d,%d,%d\n", q, pixel[0], pixel[1], pixel[2]);
            return 1;
        }
    }
    printf("libjpeg API %d: %dx%d RGB in %lu bytes\n", JPEG_LIB_VERSION, W, H, size);
    puts("ok");
    return 0;
}
