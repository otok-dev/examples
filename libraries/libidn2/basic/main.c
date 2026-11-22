/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <idn2.h>

int main(void)
{
    /* "münchen.example" in UTF-8 */
    char const name[] = "m\xc3\xbcnchen.example";
    char *ascii = NULL, *back = NULL;
    int result = idn2_to_ascii_8z(name, &ascii, IDN2_NONTRANSITIONAL);
    if (result != IDN2_OK) {
        printf("idn2_to_ascii_8z: %s\n", idn2_strerror(result));
        return 1;
    }
    if (strcmp(ascii, "xn--mnchen-3ya.example") != 0) {
        printf("the ASCII form is %s\n", ascii);
        return 1;
    }
    result = idn2_to_unicode_8z8z(ascii, &back, 0);
    if (result != IDN2_OK || strcmp(back, name) != 0) {
        printf("idn2_to_unicode_8z8z: %s\n", idn2_strerror(result));
        return 1;
    }
    /* a label UTS #46 refuses */
    char *refused = NULL;
    if (idn2_to_ascii_8z("a\xe2\x80\x8e" "b.example", &refused, IDN2_NONTRANSITIONAL) == IDN2_OK) {
        printf("a left-to-right mark was taken: %s\n", refused);
        return 1;
    }
    printf("libidn2 %s: %s\n", idn2_check_version(NULL), ascii);
    idn2_free(ascii);
    idn2_free(back);
    puts("ok");
    return 0;
}
