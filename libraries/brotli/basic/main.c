/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <brotli/decode.h>
#include <brotli/encode.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    uint8_t const text[] = "otok builds Brotli from source; otok builds Brotli from source; otok builds Brotli from source";
    uint8_t packed[512];
    uint8_t unpacked[512];
    size_t packed_size = sizeof packed;
    size_t unpacked_size = sizeof unpacked;

    if (!BrotliEncoderCompress(BROTLI_MAX_QUALITY, BROTLI_DEFAULT_WINDOW, BROTLI_MODE_TEXT, sizeof text, text, &packed_size, packed)) {
        puts("BrotliEncoderCompress failed");
        return 1;
    }
    if (BrotliDecoderDecompress(packed_size, packed, &unpacked_size, unpacked) != BROTLI_DECODER_RESULT_SUCCESS) {
        puts("BrotliDecoderDecompress failed");
        return 1;
    }
    if (unpacked_size != sizeof text || memcmp(unpacked, text, sizeof text) != 0) {
        puts("the text came back changed");
        return 1;
    }
    uint32_t const v = BrotliDecoderVersion();
    printf("Brotli %u.%u.%u: %u bytes in %u\n", v >> 24, (v >> 12) & 0xFFF, v & 0xFFF, (unsigned)sizeof text, (unsigned)packed_size);
    puts("ok");
    return 0;
}
