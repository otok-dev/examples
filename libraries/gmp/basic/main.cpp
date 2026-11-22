/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

// GMP's C functions and gmpxx's classes on numbers far beyond 64 bits: a Mersenne prime, 1000!, a square of 3^2000000
// (GMP's Toom and FFT multiplication, the assembly of the CPU) and the same kind of arithmetic with mpz_class.
#include <gmp.h>
#include <gmpxx.h>
#include <cstdio>

int main()
{
    int failures = 0;
    mpz_t m, a, b;
    mpz_inits(m, a, b, nullptr);

    mpz_ui_pow_ui(m, 2, 4423);
    mpz_sub_ui(m, m, 1);
    if (mpz_probab_prime_p(m, 25) == 0) { std::puts("2^4423-1 is prime, GMP says not"); ++failures; }
    mpz_sub_ui(m, m, 2);
    if (mpz_probab_prime_p(m, 25) != 0) { std::puts("2^4423-3 is not prime, GMP says it is"); ++failures; }

    mpz_fac_ui(m, 1000);
    if (mpz_sizeinbase(m, 10) != 2568) { std::puts("1000! has 2568 digits"); ++failures; }

    mpz_ui_pow_ui(a, 3, 2000000);
    mpz_mul(a, a, a);
    mpz_ui_pow_ui(b, 3, 4000000);
    if (mpz_cmp(a, b) != 0) { std::puts("(3^2000000)^2 differs from 3^4000000"); ++failures; }
    mpz_clears(m, a, b, nullptr);

    mpz_class x("123456789012345678901234567890");
    mpz_class y = x * x - 1;
    if (y.get_str() != "15241578753238836750495351562536198787501905199875019052099") {
        std::puts("gmpxx: x * x - 1 is wrong");
        ++failures;
    }
    mpq_class q(1, 3);
    q += mpq_class(1, 6);
    if (q != mpq_class(1, 2)) { std::puts("gmpxx: 1/3 + 1/6 is not 1/2"); ++failures; }

    std::printf("GMP %s\n", gmp_version);
    std::puts(failures ? "failed" : "ok");
    return failures;
}
