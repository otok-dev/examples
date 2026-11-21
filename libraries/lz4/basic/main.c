/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <lz4.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    char const text[] = "otok builds LZ4 from source; otok builds LZ4 from source; otok builds LZ4 from source";
    char packed[LZ4_COMPRESSBOUND(sizeof text)];
    char unpacked[sizeof text];

    int const packed_size = LZ4_compress_default(text, packed, (int)sizeof text, (int)sizeof packed);
    if (packed_size <= 0) {
        puts("LZ4_compress_default failed");
        return 1;
    }
    int const unpacked_size = LZ4_decompress_safe(packed, unpacked, packed_size, (int)sizeof unpacked);
    if (unpacked_size != (int)sizeof text || memcmp(unpacked, text, sizeof text) != 0) {
        puts("the text came back changed");
        return 1;
    }
    printf("LZ4 %s: %u bytes in %d\n", LZ4_versionString(), (unsigned)sizeof text, packed_size);
    puts("ok");
    return 0;
}
