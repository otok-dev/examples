/* Otok examples (c) Alexander A Pototskiy
   SPDX-License-Identifier: 0BSD

   NativeActivity's entry: runs the example's main() with its standard output caught in a pipe, logs each line under the
   tag otok-example and then "exit=<code>", and finishes the activity. tools/check.py reads the log. */

#include <android/log.h>
#include <android/native_activity.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(void);

#define TAG "otok-example"

void ANativeActivity_onCreate(ANativeActivity* activity, void* saved_state, size_t saved_state_size)
{
    (void)saved_state;
    (void)saved_state_size;
    int fds[2];
    int const saved = dup(STDOUT_FILENO);
    if (pipe(fds) != 0) {
        __android_log_print(ANDROID_LOG_ERROR, TAG, "exit=pipe");
        ANativeActivity_finish(activity);
        return;
    }
    fflush(stdout);
    dup2(fds[1], STDOUT_FILENO);
    int const code = main();
    fflush(stdout);
    dup2(saved, STDOUT_FILENO);
    close(fds[1]);

    char text[65536];
    size_t length = 0;
    ssize_t n;
    while (length < sizeof text - 1 && (n = read(fds[0], text + length, sizeof text - 1 - length)) > 0) length += (size_t)n;
    close(fds[0]);
    text[length] = '\0';
    for (char* line = strtok(text, "\n"); line; line = strtok(NULL, "\n")) __android_log_print(ANDROID_LOG_INFO, TAG, "%s", line);
    __android_log_print(ANDROID_LOG_INFO, TAG, "exit=%d", code);
    ANativeActivity_finish(activity);
}
