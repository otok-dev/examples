/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <curl/curl.h>

int main(void)
{
    if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
        puts("curl_global_init failed");
        return 1;
    }
    curl_version_info_data const *info = curl_version_info(CURLVERSION_NOW);
    /* curl_version() names libpsl's version, which libcurl asks psl_get_version() for: its code reaches libpsl */
    char const *version = curl_version();
    char const *psl = strstr(version, "libpsl/");
    if (!(info->features & CURL_VERSION_PSL) || !psl) {
        printf("features 0x%x, %s\n", (unsigned)info->features, version);
        return 1;
    }
    CURL *easy = curl_easy_init();
    /* cookies on: curl refuses those set for a public suffix (co.uk) through libpsl */
    if (!easy || curl_easy_setopt(easy, CURLOPT_COOKIEFILE, "") != CURLE_OK)
        return 1;
    curl_easy_cleanup(easy);

    printf("libcurl %s with %.*s\n", info->version, (int)strcspn(psl, " "), psl);
    curl_global_cleanup();
    puts("ok");
    return 0;
}
