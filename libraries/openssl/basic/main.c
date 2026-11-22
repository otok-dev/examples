/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/ssl.h>

int main(void)
{
    /* libcrypto: SHA-256 of "abc" (FIPS 180-2, appendix B.1) */
    static unsigned char const expected[32] = {
        0xba, 0x78, 0x16, 0xbf, 0x8f, 0x01, 0xcf, 0xea, 0x41, 0x41, 0x40, 0xde, 0x5d, 0xae, 0x22, 0x23,
        0xb0, 0x03, 0x61, 0xa3, 0x96, 0x17, 0x7a, 0x9c, 0xb4, 0x10, 0xff, 0x61, 0xf2, 0x00, 0x15, 0xad,
    };
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int size = 0;
    if (!EVP_Digest("abc", 3, digest, &size, EVP_sha256(), NULL) || size != sizeof expected || memcmp(digest, expected, size) != 0) {
        puts("SHA-256 of 'abc' is wrong");
        return 1;
    }

    /* libssl: a TLS client context that verifies its peers */
    SSL_CTX *context = SSL_CTX_new(TLS_client_method());
    if (!context || !SSL_CTX_set_min_proto_version(context, TLS1_2_VERSION)) {
        puts("SSL_CTX_new failed");
        return 1;
    }
    SSL_CTX_set_verify(context, SSL_VERIFY_PEER, NULL);
    SSL *ssl = SSL_new(context);
    if (!ssl || !SSL_set_tlsext_host_name(ssl, "example.com")) {
        puts("SSL_new failed");
        return 1;
    }
    SSL_free(ssl);
    SSL_CTX_free(context);

    printf("%s: SHA-256 and a TLS client context\n", OpenSSL_version(OPENSSL_VERSION));
    puts("ok");
    return 0;
}
