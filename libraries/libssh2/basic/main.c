/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <libssh2.h>

static int list(LIBSSH2_SESSION *session, int method, char const *what)
{
    char const **algorithms = NULL;
    int const count = libssh2_session_supported_algs(session, method, &algorithms);
    if (count <= 0) {
        printf("no %s methods: %d\n", what, count);
        return 0;
    }
    printf("%s:", what);
    for (int i = 0; i < count; ++i)
        printf(" %s", algorithms[i]);
    putchar('\n');
    libssh2_free(session, (void *)algorithms);
    return count;
}

int main(void)
{
    if (libssh2_init(0) != 0) {
        puts("libssh2_init failed");
        return 1;
    }
    LIBSSH2_SESSION *session = libssh2_session_init();
    if (!session) {
        puts("libssh2_session_init failed");
        return 1;
    }
    /* the methods come from the crypto backend (OpenSSL) and zlib */
    if (!list(session, LIBSSH2_METHOD_KEX, "key exchange") || !list(session, LIBSSH2_METHOD_CRYPT_CS, "ciphers")
        || !list(session, LIBSSH2_METHOD_COMP_CS, "compression"))
        return 1;
    libssh2_session_free(session);
    libssh2_exit();

    printf("libssh2 %s\n", libssh2_version(0));
    puts("ok");
    return 0;
}
