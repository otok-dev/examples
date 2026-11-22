/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <mbedtls/build_info.h>
#include <mbedtls/ssl.h>
#include <psa/crypto.h>

int main(void)
{
    if (psa_crypto_init() != PSA_SUCCESS) {
        puts("psa_crypto_init failed");
        return 1;
    }

    /* TF-PSA-Crypto: SHA-256 of "abc" (FIPS 180-2, appendix B.1) */
    static unsigned char const expected[32] = {
        0xba, 0x78, 0x16, 0xbf, 0x8f, 0x01, 0xcf, 0xea, 0x41, 0x41, 0x40, 0xde, 0x5d, 0xae, 0x22, 0x23,
        0xb0, 0x03, 0x61, 0xa3, 0x96, 0x17, 0x7a, 0x9c, 0xb4, 0x10, 0xff, 0x61, 0xf2, 0x00, 0x15, 0xad,
    };
    unsigned char digest[PSA_HASH_MAX_SIZE];
    size_t size = 0;
    if (psa_hash_compute(PSA_ALG_SHA_256, (uint8_t const *)"abc", 3, digest, sizeof digest, &size) != PSA_SUCCESS
        || size != sizeof expected || memcmp(digest, expected, size) != 0) {
        puts("SHA-256 of 'abc' is wrong");
        return 1;
    }

    /* Mbed TLS: a TLS client configuration and a context set up from it */
    mbedtls_ssl_config config;
    mbedtls_ssl_context ssl;
    mbedtls_ssl_config_init(&config);
    mbedtls_ssl_init(&ssl);
    int result = mbedtls_ssl_config_defaults(&config, MBEDTLS_SSL_IS_CLIENT, MBEDTLS_SSL_TRANSPORT_STREAM, MBEDTLS_SSL_PRESET_DEFAULT);
    if (result == 0)
        result = mbedtls_ssl_setup(&ssl, &config);
    if (result == 0)
        result = mbedtls_ssl_set_hostname(&ssl, "example.com");
    if (result != 0) {
        printf("setting up TLS failed: -0x%04x\n", (unsigned)-result);
        return 1;
    }
    mbedtls_ssl_free(&ssl);
    mbedtls_ssl_config_free(&config);
    mbedtls_psa_crypto_free();

    printf("Mbed TLS %s: SHA-256 and a TLS client configuration\n", MBEDTLS_VERSION_STRING);
    puts("ok");
    return 0;
}
