/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <libpsl.h>

int main(void)
{
    psl_ctx_t const *psl = psl_builtin();
    if (!psl) {
        puts("this libpsl has no built-in list");
        return 1;
    }
    struct { char const *domain, *registrable; int public_suffix; } const checks[] = {
        { "co.uk", NULL, 1 },
        { "www.example.co.uk", "example.co.uk", 0 },
        { "com", NULL, 1 },
        { "docs.example.com", "example.com", 0 },
        { "user.github.io", "user.github.io", 0 }, /* github.io is in the list's private part */
    };
    for (size_t i = 0; i < sizeof checks / sizeof checks[0]; ++i) {
        char const *registrable = psl_registrable_domain(psl, checks[i].domain);
        int const public_suffix = psl_is_public_suffix(psl, checks[i].domain);
        if (public_suffix != checks[i].public_suffix || (registrable == NULL) != (checks[i].registrable == NULL)
            || (registrable && strcmp(registrable, checks[i].registrable) != 0)) {
            printf("%s: public suffix %d, registrable domain %s\n", checks[i].domain, public_suffix, registrable ? registrable : "none");
            return 1;
        }
    }
    printf("libpsl %s: a list of %d rules from %s\n", psl_get_version(), psl_suffix_count(psl), psl_dist_filename());
    puts("ok");
    return 0;
}
