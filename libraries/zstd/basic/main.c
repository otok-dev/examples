/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <zstd.h>

int main(void)
{
    char const text[] = "otok builds Zstandard from source; otok builds Zstandard from source; otok builds Zstandard";
    char packed[ZSTD_COMPRESSBOUND(sizeof text)];
    char unpacked[sizeof text];

    size_t const packed_size = ZSTD_compress(packed, sizeof packed, text, sizeof text, 19);
    if (ZSTD_isError(packed_size)) {
        printf("ZSTD_compress: %s\n", ZSTD_getErrorName(packed_size));
        return 1;
    }
    size_t const unpacked_size = ZSTD_decompress(unpacked, sizeof unpacked, packed, packed_size);
    if (ZSTD_isError(unpacked_size)) {
        printf("ZSTD_decompress: %s\n", ZSTD_getErrorName(unpacked_size));
        return 1;
    }
    if (unpacked_size != sizeof text || memcmp(unpacked, text, sizeof text) != 0) {
        puts("the text came back changed");
        return 1;
    }
    printf("Zstandard %s: %u bytes in %u\n", ZSTD_versionString(), (unsigned)sizeof text, (unsigned)packed_size);
    puts("ok");
    return 0;
}
