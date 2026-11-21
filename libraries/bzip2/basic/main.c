/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <bzlib.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    char text[] = "otok builds bzip2 from source; otok builds bzip2 from source; otok builds bzip2 from source";
    char packed[512];
    char unpacked[512];
    unsigned packed_size = sizeof packed;
    unsigned unpacked_size = sizeof unpacked;

    int rc = BZ2_bzBuffToBuffCompress(packed, &packed_size, text, sizeof text, 9, 0, 0);
    if (rc != BZ_OK) {
        printf("BZ2_bzBuffToBuffCompress: %d\n", rc);
        return 1;
    }
    rc = BZ2_bzBuffToBuffDecompress(unpacked, &unpacked_size, packed, packed_size, 0, 0);
    if (rc != BZ_OK) {
        printf("BZ2_bzBuffToBuffDecompress: %d\n", rc);
        return 1;
    }
    if (unpacked_size != sizeof text || memcmp(unpacked, text, sizeof text) != 0) {
        puts("the text came back changed");
        return 1;
    }
    printf("bzip2 %s: %u bytes in %u\n", BZ2_bzlibVersion(), (unsigned)sizeof text, packed_size);
    puts("ok");
    return 0;
}
