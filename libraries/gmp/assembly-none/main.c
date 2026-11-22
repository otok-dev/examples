/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

/* GMP's C functions from C, the library built without assembly: a Mersenne prime, 1000! and a square of 3^2000000. */
#include <gmp.h>
#include <stdio.h>

int main(void)
{
    int failures = 0;
    mpz_t m, a, b;
    mpz_inits(m, a, b, NULL);

    mpz_ui_pow_ui(m, 2, 4423);
    mpz_sub_ui(m, m, 1);
    if (mpz_probab_prime_p(m, 25) == 0) { puts("2^4423-1 is prime, GMP says not"); ++failures; }
    mpz_sub_ui(m, m, 2);
    if (mpz_probab_prime_p(m, 25) != 0) { puts("2^4423-3 is not prime, GMP says it is"); ++failures; }

    mpz_fac_ui(m, 1000);
    if (mpz_sizeinbase(m, 10) != 2568) { puts("1000! has 2568 digits"); ++failures; }

    mpz_ui_pow_ui(a, 3, 2000000);
    mpz_mul(a, a, a);
    mpz_ui_pow_ui(b, 3, 4000000);
    if (mpz_cmp(a, b) != 0) { puts("(3^2000000)^2 differs from 3^4000000"); ++failures; }
    mpz_clears(m, a, b, NULL);

    printf("GMP %s\n", gmp_version);
    puts(failures ? "failed" : "ok");
    return failures;
}
