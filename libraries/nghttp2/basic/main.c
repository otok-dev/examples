/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
/* nghttp2's API with ssize_t is deprecated, and MSVC has no ssize_t: a program on the newer functions (nghttp2_ssize,
   the ...2 and ...3 ones) hides the older ones */
#define NGHTTP2_NO_SSIZE_T
#include <nghttp2/nghttp2.h>

#define FIELD(NAME, VALUE) { (uint8_t *)NAME, (uint8_t *)VALUE, sizeof NAME - 1, sizeof VALUE - 1, NGHTTP2_NV_FLAG_NONE }

int main(void)
{
    nghttp2_nv fields[] = {
        FIELD(":method", "GET"), FIELD(":scheme", "https"), FIELD(":authority", "example.com"),
        FIELD(":path", "/index.html"), FIELD("user-agent", "otok-example"), FIELD("accept", "*/*"),
    };
    size_t const count = sizeof fields / sizeof fields[0];

    /* compress with HPACK */
    nghttp2_hd_deflater *deflater = NULL;
    if (nghttp2_hd_deflate_new(&deflater, 4096) != 0)
        return 1;
    uint8_t block[512];
    if (nghttp2_hd_deflate_bound(deflater, fields, count) > sizeof block)
        return 1;
    nghttp2_ssize const size = nghttp2_hd_deflate_hd2(deflater, block, sizeof block, fields, count);
    if (size < 0) {
        printf("nghttp2_hd_deflate_hd2: %s\n", nghttp2_strerror((int)size));
        return 1;
    }
    nghttp2_hd_deflate_del(deflater);

    /* inflate, field by field */
    nghttp2_hd_inflater *inflater = NULL;
    if (nghttp2_hd_inflate_new(&inflater) != 0)
        return 1;
    uint8_t const *in = block;
    size_t left = (size_t)size, seen = 0;
    for (;;) {
        nghttp2_nv field;
        int flags = 0;
        nghttp2_ssize const read = nghttp2_hd_inflate_hd3(inflater, &field, &flags, in, left, 1);
        if (read < 0) {
            printf("nghttp2_hd_inflate_hd3: %s\n", nghttp2_strerror((int)read));
            return 1;
        }
        in += read;
        left -= (size_t)read;
        if (flags & NGHTTP2_HD_INFLATE_EMIT) {
            if (seen >= count || field.namelen != fields[seen].namelen || field.valuelen != fields[seen].valuelen
                || memcmp(field.name, fields[seen].name, field.namelen) != 0 || memcmp(field.value, fields[seen].value, field.valuelen) != 0) {
                printf("field %u came back changed\n", (unsigned)seen);
                return 1;
            }
            ++seen;
        }
        if (flags & NGHTTP2_HD_INFLATE_FINAL) {
            nghttp2_hd_inflate_end_headers(inflater);
            break;
        }
        if (read == 0 && left == 0)
            break;
    }
    nghttp2_hd_inflate_del(inflater);
    if (seen != count) {
        printf("%u fields of %u came back\n", (unsigned)seen, (unsigned)count);
        return 1;
    }

    printf("nghttp2 %s: %u header fields in %d bytes of HPACK\n", nghttp2_version(0)->version_str, (unsigned)count, (int)size);
    puts("ok");
    return 0;
}
