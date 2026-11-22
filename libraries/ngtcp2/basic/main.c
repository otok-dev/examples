/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <ngtcp2/ngtcp2.h>
#include <ngtcp2/ngtcp2_crypto.h>
#include <ngtcp2/ngtcp2_crypto_ossl.h>

int main(void)
{
    /* the crypto helper on OpenSSL */
    if (ngtcp2_crypto_ossl_init() != 0) {
        puts("ngtcp2_crypto_ossl_init failed");
        return 1;
    }

    /* QUIC transport parameters (RFC 9000, 18) through their encoding and back */
    ngtcp2_transport_params params, back;
    ngtcp2_transport_params_default(&params);
    params.initial_max_streams_bidi = 100;
    params.initial_max_streams_uni = 3;
    params.initial_max_data = 1 << 20;
    params.initial_max_stream_data_bidi_local = 1 << 18;
    params.max_idle_timeout = 30 * NGTCP2_SECONDS;
    params.initial_scid_present = 1;
    params.initial_scid.datalen = 8;
    memcpy(params.initial_scid.data, "otok-cid", 8);

    uint8_t encoded[256];
    ngtcp2_ssize const size = ngtcp2_transport_params_encode(encoded, sizeof encoded, &params);
    if (size < 0) {
        printf("ngtcp2_transport_params_encode: %s\n", ngtcp2_strerror((int)size));
        return 1;
    }
    int const result = ngtcp2_transport_params_decode(&back, encoded, (size_t)size);
    if (result != 0) {
        printf("ngtcp2_transport_params_decode: %s\n", ngtcp2_strerror(result));
        return 1;
    }
    if (back.initial_max_streams_bidi != 100 || back.initial_max_streams_uni != 3 || back.initial_max_data != 1 << 20
        || back.initial_max_stream_data_bidi_local != 1 << 18 || back.max_idle_timeout != 30 * NGTCP2_SECONDS
        || !back.initial_scid_present || back.initial_scid.datalen != 8 || memcmp(back.initial_scid.data, "otok-cid", 8) != 0) {
        puts("the transport parameters came back changed");
        return 1;
    }

    printf("ngtcp2 %s: transport parameters in %d bytes\n", ngtcp2_version(0)->version_str, (int)size);
    puts("ok");
    return 0;
}
