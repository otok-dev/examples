/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <openjpeg.h>

enum { W = 32, H = 32 };

/* the codestream in memory, behind the functions of an opj_stream_t */
struct memory {
    unsigned char *data;
    size_t size, capacity, at;
};

static OPJ_SIZE_T read_fn(void *buffer, OPJ_SIZE_T n, void *user)
{
    struct memory *m = user;
    if (m->at >= m->size)
        return (OPJ_SIZE_T)-1;
    if (n > m->size - m->at)
        n = m->size - m->at;
    memcpy(buffer, m->data + m->at, n);
    m->at += n;
    return n;
}

static OPJ_SIZE_T write_fn(void *buffer, OPJ_SIZE_T n, void *user)
{
    struct memory *m = user;
    if (m->at + n > m->capacity) {
        size_t capacity = m->capacity ? m->capacity * 2 : 4096;
        while (capacity < m->at + n)
            capacity *= 2;
        unsigned char *data = realloc(m->data, capacity);
        if (!data)
            return (OPJ_SIZE_T)-1;
        m->data = data;
        m->capacity = capacity;
    }
    memcpy(m->data + m->at, buffer, n);
    m->at += n;
    if (m->at > m->size)
        m->size = m->at;
    return n;
}

static OPJ_OFF_T skip_fn(OPJ_OFF_T n, void *user)
{
    struct memory *m = user;
    m->at += (size_t)n;
    return n;
}

static OPJ_BOOL seek_fn(OPJ_OFF_T at, void *user)
{
    ((struct memory *)user)->at = (size_t)at;
    return OPJ_TRUE;
}

static void error_fn(char const *message, void *user)
{
    (void)user;
    printf("openjpeg: %s", message);
}

static opj_stream_t *memory_stream(struct memory *m, OPJ_BOOL input)
{
    opj_stream_t *stream = opj_stream_create(OPJ_J2K_STREAM_CHUNK_SIZE, input);
    opj_stream_set_user_data(stream, m, NULL);
    if (input) {
        opj_stream_set_user_data_length(stream, m->size);
        opj_stream_set_read_function(stream, read_fn);
    } else {
        opj_stream_set_write_function(stream, write_fn);
    }
    opj_stream_set_skip_function(stream, skip_fn);
    opj_stream_set_seek_function(stream, seek_fn);
    m->at = 0;
    return stream;
}

int main(void)
{
    opj_image_cmptparm_t components[3];
    memset(components, 0, sizeof components);
    for (int c = 0; c < 3; ++c) {
        components[c].dx = components[c].dy = 1;
        components[c].w = W;
        components[c].h = H;
        components[c].prec = 8;
    }
    static OPJ_INT32 samples[3][W * H];
    for (int i = 0; i < W * H; ++i) {
        samples[0][i] = (i % W) * 8;
        samples[1][i] = (i / W) * 8;
        samples[2][i] = ((i % W) ^ (i / W)) * 8;
    }
    opj_image_t *image = opj_image_create(3, components, OPJ_CLRSPC_SRGB);
    image->x1 = W;
    image->y1 = H;
    /* the encoder of a single tile works in the image's own buffers: it gets a copy of the samples */
    for (int c = 0; c < 3; ++c)
        memcpy(image->comps[c].data, samples[c], sizeof samples[c]);

    /* encode: the default parameters are one lossless layer with the reversible wavelet */
    opj_cparameters_t parameters;
    opj_set_default_encoder_parameters(&parameters);
    opj_codec_t *encoder = opj_create_compress(OPJ_CODEC_J2K);
    opj_set_error_handler(encoder, error_fn, NULL);
    struct memory m = { 0 };
    opj_stream_t *out = memory_stream(&m, OPJ_FALSE);
    if (!opj_setup_encoder(encoder, &parameters, image) || !opj_start_compress(encoder, image, out) || !opj_encode(encoder, out)
        || !opj_end_compress(encoder, out))
        return 1;
    opj_stream_destroy(out);
    opj_destroy_codec(encoder);
    opj_image_destroy(image);

    /* decode */
    opj_dparameters_t decoding;
    opj_set_default_decoder_parameters(&decoding);
    opj_codec_t *decoder = opj_create_decompress(OPJ_CODEC_J2K);
    opj_set_error_handler(decoder, error_fn, NULL);
    opj_stream_t *in = memory_stream(&m, OPJ_TRUE);
    opj_image_t *back = NULL;
    if (!opj_setup_decoder(decoder, &decoding) || !opj_read_header(in, decoder, &back) || !opj_decode(decoder, in, back)
        || !opj_end_decompress(decoder, in))
        return 1;
    opj_stream_destroy(in);
    opj_destroy_codec(decoder);

    if (back->numcomps != 3 || back->comps[0].w != W || back->comps[0].h != H) {
        printf("decoded %u components of %ux%u\n", back->numcomps, back->comps[0].w, back->comps[0].h);
        return 1;
    }
    for (int c = 0; c < 3; ++c)
        if (memcmp(back->comps[c].data, samples[c], sizeof samples[c]) != 0) {
            printf("component %d came back changed\n", c);
            return 1;
        }
    opj_image_destroy(back);
    printf("OpenJPEG %s: %dx%d RGB, lossless, in %u bytes\n", opj_version(), W, H, (unsigned)m.size);
    free(m.data);
    puts("ok");
    return 0;
}
