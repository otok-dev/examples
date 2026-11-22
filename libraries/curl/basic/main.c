/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD */

#include <stdio.h>
#include <string.h>
#include <curl/curl.h>

static int part(CURLU *url, CURLUPart which, char const *expected)
{
    char *value = NULL;
    CURLUcode const result = curl_url_get(url, which, &value, 0);
    int const same = result == CURLUE_OK && strcmp(value, expected) == 0;
    if (!same)
        printf("part %d: %s, not %s\n", (int)which, result == CURLUE_OK ? value : curl_url_strerror(result), expected);
    curl_free(value);
    return same;
}

int main(void)
{
    if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
        puts("curl_global_init failed");
        return 1;
    }
    curl_version_info_data const *info = curl_version_info(CURLVERSION_NOW);
    /* the recipes' defaults: TLS (Mbed TLS, or OpenSSL on Apple) and zlib */
    if (!(info->features & CURL_VERSION_SSL) || !info->ssl_version || !(info->features & CURL_VERSION_LIBZ)) {
        printf("features 0x%x, TLS %s\n", (unsigned)info->features, info->ssl_version ? info->ssl_version : "none");
        return 1;
    }

    /* the URL API */
    CURLU *url = curl_url();
    if (curl_url_set(url, CURLUPART_URL, "https://user@example.com:8443/a/../path%20x?q=1#top", 0) != CURLUE_OK)
        return 1;
    if (!part(url, CURLUPART_SCHEME, "https") || !part(url, CURLUPART_HOST, "example.com") || !part(url, CURLUPART_PORT, "8443")
        || !part(url, CURLUPART_PATH, "/path%20x") || !part(url, CURLUPART_QUERY, "q=1") || !part(url, CURLUPART_USER, "user"))
        return 1;
    curl_url_cleanup(url);

    /* an easy handle, its escaping and its options */
    CURL *easy = curl_easy_init();
    if (!easy || curl_easy_setopt(easy, CURLOPT_URL, "https://example.com/") != CURLE_OK)
        return 1;
    char *escaped = curl_easy_escape(easy, "a b&c", 0);
    if (!escaped || strcmp(escaped, "a%20b%26c") != 0) {
        printf("escaped: %s\n", escaped ? escaped : "nothing");
        return 1;
    }
    curl_free(escaped);
    curl_easy_cleanup(easy);
    curl_global_cleanup();

    printf("libcurl %s with %s\n", info->version, info->ssl_version);
    puts("ok");
    return 0;
}
