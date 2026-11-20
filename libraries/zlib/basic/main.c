/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <zlib.h>

int main(void)
{
    char const text[] = "otok builds zlib from source; otok builds zlib from source; otok builds zlib from source";
    unsigned char packed[256];
    unsigned char unpacked[256];
    uLongf packed_size = sizeof packed;
    uLongf unpacked_size = sizeof unpacked;

    if (compress2(packed, &packed_size, (unsigned char const*)text, sizeof text, Z_BEST_COMPRESSION) != Z_OK) {
        puts("compress2 failed");
        return 1;
    }
    if (uncompress(unpacked, &unpacked_size, packed, packed_size) != Z_OK) {
        puts("uncompress failed");
        return 1;
    }
    if (unpacked_size != sizeof text || memcmp(unpacked, text, sizeof text) != 0) {
        puts("the text came back changed");
        return 1;
    }
    printf("zlib %s: %u bytes in %u\n", zlibVersion(), (unsigned)sizeof text, (unsigned)packed_size);
    puts("ok");
    return 0;
}
