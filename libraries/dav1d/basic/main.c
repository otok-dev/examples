/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <dav1d/dav1d.h>

/* one AV1 frame, 32x32 of four quadrants: light grey, green (top), red, blue (bottom); the OBUs of the image item of
   libraries/libavif/basic's AVIF */
static unsigned char const frame_obu[] = {
    0x12, 0x00, 0x0a, 0x09, 0x18, 0x11, 0x3f, 0xf6, 0x88, 0x08, 0x68, 0x34, 0x20, 0x32, 0x50, 0x12,
    0x07, 0xf7, 0xf6, 0xa9, 0x00, 0x82, 0x08, 0x3e, 0x40, 0x00, 0x00, 0xc4, 0xe1, 0x9d, 0x57, 0xd0,
    0x49, 0x72, 0x8c, 0x94, 0x9c, 0x44, 0x85, 0x89, 0xc2, 0x6f, 0x60, 0xf8, 0xf8, 0xe3, 0x33, 0x53,
    0x69, 0xa6, 0xc2, 0xd9, 0x2f, 0x56, 0x1b, 0x4a, 0x74, 0x30, 0x2f, 0x50, 0x69, 0xcb, 0xfc, 0x9f,
    0xff, 0x50, 0xcc, 0x03, 0x8c, 0x03, 0x73, 0x22, 0xd6, 0xd7, 0x8f, 0x79, 0xe3, 0x5b, 0xa4, 0xe8,
    0xf4, 0x6b, 0x11, 0xf9, 0x9e, 0x61, 0x33, 0x5b, 0x63, 0x9d, 0x3f, 0x0b, 0x10, 0x23, 0xb0,
};

int main(void)
{
    Dav1dSettings settings;
    dav1d_default_settings(&settings);
    settings.n_threads = 1;
    settings.max_frame_delay = 1;
    Dav1dContext *context = NULL;
    if (dav1d_open(&context, &settings) < 0) {
        puts("dav1d_open failed");
        return 1;
    }

    Dav1dData data;
    memcpy(dav1d_data_create(&data, sizeof frame_obu), frame_obu, sizeof frame_obu);
    Dav1dPicture picture;
    memset(&picture, 0, sizeof picture);
    int result = DAV1D_ERR(EAGAIN);
    for (int attempt = 0; attempt < 16 && result == DAV1D_ERR(EAGAIN); ++attempt) {
        if (data.sz > 0 && (result = dav1d_send_data(context, &data)) < 0 && result != DAV1D_ERR(EAGAIN))
            break;
        result = dav1d_get_picture(context, &picture);
    }
    if (result < 0) {
        printf("dav1d gave no picture: %d\n", result);
        return 1;
    }
    if (picture.p.w != 32 || picture.p.h != 32 || picture.p.bpc != 8) {
        printf("decoded %dx%d of %d bits\n", picture.p.w, picture.p.h, picture.p.bpc);
        return 1;
    }
    /* the luma of the quadrants' middles: grey > green > red > blue */
    int luma[4];
    for (int q = 0; q < 4; ++q)
        luma[q] = ((unsigned char const *)picture.data[0])[((q / 2) * 16 + 8) * picture.stride[0] + (q % 2) * 16 + 8];
    if (!(luma[0] > luma[1] + 10 && luma[1] > luma[2] + 10 && luma[2] > luma[3] + 10)) {
        printf("luma of the quadrants: %d %d %d %d\n", luma[0], luma[1], luma[2], luma[3]);
        return 1;
    }
    dav1d_picture_unref(&picture);
    if (data.sz > 0)
        dav1d_data_unref(&data);
    dav1d_close(&context);
    printf("dav1d %s: %u bytes to 32x32, luma %d %d %d %d\n", dav1d_version(), (unsigned)sizeof frame_obu, luma[0], luma[1], luma[2], luma[3]);
    puts("ok");
    return 0;
}
