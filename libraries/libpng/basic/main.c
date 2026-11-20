/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <png.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { width = 16, height = 8 };

int main(void)
{
    unsigned char pixels[width * height * 4];
    for (int i = 0; i < width * height; ++i) {
        pixels[i * 4 + 0] = (unsigned char)(i * 3);
        pixels[i * 4 + 1] = (unsigned char)(255 - i);
        pixels[i * 4 + 2] = (unsigned char)(i * 7);
        pixels[i * 4 + 3] = 255;
    }

    png_image image;
    memset(&image, 0, sizeof image);
    image.version = PNG_IMAGE_VERSION;
    image.width = width;
    image.height = height;
    image.format = PNG_FORMAT_RGBA;

    /* the size first, then the PNG itself */
    png_alloc_size_t size = 0;
    if (!png_image_write_to_memory(&image, NULL, &size, 0, pixels, 0, NULL)) {
        printf("png_image_write_to_memory: %s\n", image.message);
        return 1;
    }
    void* png = malloc(size);
    if (!png || !png_image_write_to_memory(&image, png, &size, 0, pixels, 0, NULL)) {
        printf("png_image_write_to_memory: %s\n", image.message);
        return 1;
    }

    png_image read;
    memset(&read, 0, sizeof read);
    read.version = PNG_IMAGE_VERSION;
    unsigned char back[width * height * 4];
    if (!png_image_begin_read_from_memory(&read, png, size)) {
        printf("png_image_begin_read_from_memory: %s\n", read.message);
        return 1;
    }
    read.format = PNG_FORMAT_RGBA;
    if (read.width != width || read.height != height || !png_image_finish_read(&read, NULL, back, 0, NULL)) {
        printf("png_image_finish_read: %s\n", read.message);
        return 1;
    }
    if (memcmp(back, pixels, sizeof pixels) != 0) {
        puts("the pixels came back changed");
        return 1;
    }
    /* zlib is libpng's alone: the program does not call it, so a dynamic libpng must find it by itself */
    printf("libpng %s: %ux%u in %u bytes\n", png_get_libpng_ver(NULL), (unsigned)width, (unsigned)height, (unsigned)size);
    free(png);
    puts("ok");
    return 0;
}
