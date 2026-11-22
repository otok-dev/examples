/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <nghttp3/nghttp3.h>

#define FIELD(NAME, VALUE) { (uint8_t *)NAME, (uint8_t *)VALUE, sizeof NAME - 1, sizeof VALUE - 1, NGHTTP3_NV_FLAG_NONE }

int main(void)
{
    nghttp3_nv fields[] = {
        FIELD(":method", "GET"), FIELD(":scheme", "https"), FIELD(":authority", "example.com"),
        FIELD(":path", "/index.html"), FIELD("user-agent", "otok-example"), FIELD("accept", "*/*"),
    };
    size_t const count = sizeof fields / sizeof fields[0];
    nghttp3_mem const *mem = nghttp3_mem_default();
    int64_t const stream = 0;

    /* encode with QPACK, without a dynamic table: the field section is the prefix and the representations */
    nghttp3_qpack_encoder *encoder = NULL;
    if (nghttp3_qpack_encoder_new(&encoder, 0, mem) != 0)
        return 1;
    nghttp3_buf prefix, body, encoder_stream;
    nghttp3_buf_init(&prefix);
    nghttp3_buf_init(&body);
    nghttp3_buf_init(&encoder_stream);
    int result = nghttp3_qpack_encoder_encode(encoder, &prefix, &body, &encoder_stream, stream, fields, count);
    if (result != 0) {
        printf("nghttp3_qpack_encoder_encode: %s\n", nghttp3_strerror(result));
        return 1;
    }
    uint8_t section[512];
    size_t const prefix_size = nghttp3_buf_len(&prefix), body_size = nghttp3_buf_len(&body), size = prefix_size + body_size;
    if (size > sizeof section || nghttp3_buf_len(&encoder_stream) != 0)
        return 1;
    memcpy(section, prefix.pos, prefix_size);
    memcpy(section + prefix_size, body.pos, body_size);
    nghttp3_buf_free(&prefix, mem);
    nghttp3_buf_free(&body, mem);
    nghttp3_buf_free(&encoder_stream, mem);
    nghttp3_qpack_encoder_del(encoder);

    /* decode, field by field */
    nghttp3_qpack_decoder *decoder = NULL;
    nghttp3_qpack_stream_context *context = NULL;
    if (nghttp3_qpack_decoder_new(&decoder, 0, 0, mem) != 0 || nghttp3_qpack_stream_context_new(&context, stream, mem) != 0)
        return 1;
    uint8_t const *in = section;
    size_t left = size, seen = 0;
    for (;;) {
        nghttp3_qpack_nv field;
        uint8_t flags = 0;
        nghttp3_ssize const read = nghttp3_qpack_decoder_read_request(decoder, context, &field, &flags, in, left, 1);
        if (read < 0) {
            printf("nghttp3_qpack_decoder_read_request: %s\n", nghttp3_strerror((int)read));
            return 1;
        }
        in += read;
        left -= (size_t)read;
        if (flags & NGHTTP3_QPACK_DECODE_FLAG_EMIT) {
            nghttp3_vec const name = nghttp3_rcbuf_get_buf(field.name), value = nghttp3_rcbuf_get_buf(field.value);
            if (seen >= count || name.len != fields[seen].namelen || value.len != fields[seen].valuelen
                || memcmp(name.base, fields[seen].name, name.len) != 0 || memcmp(value.base, fields[seen].value, value.len) != 0) {
                printf("field %u came back changed\n", (unsigned)seen);
                return 1;
            }
            nghttp3_rcbuf_decref(field.name);
            nghttp3_rcbuf_decref(field.value);
            ++seen;
        }
        if ((flags & NGHTTP3_QPACK_DECODE_FLAG_FINAL) || (flags & NGHTTP3_QPACK_DECODE_FLAG_BLOCKED) || (read == 0 && left == 0))
            break;
    }
    nghttp3_qpack_stream_context_del(context);
    nghttp3_qpack_decoder_del(decoder);
    if (seen != count) {
        printf("%u fields of %u came back\n", (unsigned)seen, (unsigned)count);
        return 1;
    }

    printf("nghttp3 %s: %u header fields in %u bytes of QPACK\n", nghttp3_version(0)->version_str, (unsigned)count, (unsigned)size);
    puts("ok");
    return 0;
}
