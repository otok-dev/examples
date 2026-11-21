/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <lzma.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    uint8_t const text[] = "otok builds XZ Utils from source; otok builds XZ Utils from source; otok builds XZ Utils";
    uint8_t packed[1024];
    uint8_t unpacked[1024];
    size_t packed_size = 0;
    size_t unpacked_size = 0;
    size_t in = 0;

    lzma_ret rc = lzma_easy_buffer_encode(6, LZMA_CHECK_CRC64, NULL, text, sizeof text, packed, &packed_size, sizeof packed);
    if (rc != LZMA_OK) {
        printf("lzma_easy_buffer_encode: %d\n", (int)rc);
        return 1;
    }
    uint64_t memory = UINT64_MAX;
    rc = lzma_stream_buffer_decode(&memory, 0, NULL, packed, &in, packed_size, unpacked, &unpacked_size, sizeof unpacked);
    if (rc != LZMA_OK) {
        printf("lzma_stream_buffer_decode: %d\n", (int)rc);
        return 1;
    }
    if (unpacked_size != sizeof text || memcmp(unpacked, text, sizeof text) != 0) {
        puts("the text came back changed");
        return 1;
    }
    printf("liblzma %s: %u bytes in %u (.xz)\n", lzma_version_string(), (unsigned)sizeof text, (unsigned)packed_size);
    puts("ok");
    return 0;
}
