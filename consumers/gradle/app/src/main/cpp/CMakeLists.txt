# Otok examples (c) Alexander A Pototskiy
# SPDX-License-Identifier: 0BSD
#
# The native library of the Gradle consumer: the example's program as a shared object with glue.c, which NativeActivity
# loads. Gradle's CMake runs it for each ABI with -DCMAKE_PROJECT_TOP_LEVEL_INCLUDES=<output>/otok-provider.cmake and
# -DEXAMPLE_SETTINGS=<example.cmake> (gradle.properties, written by tools/check.py).
cmake_minimum_required(VERSION 3.28)
project(otok_example_app LANGUAGES C CXX)

include("${EXAMPLE_SETTINGS}")

if(EXAMPLE_PACKAGE)
    find_package(${EXAMPLE_PACKAGE} REQUIRED ${EXAMPLE_COMPONENTS})
else()
    find_package(Otok CONFIG REQUIRED PATHS "${EXAMPLE_OUTPUT}" NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
endif()

# Gradle packs the shared objects of the imported libraries the app links, and libc++_shared.so (otok-toml.md 4.11)
add_library(example SHARED ${EXAMPLE_SOURCES} glue.c)
if(EXAMPLE_C_STANDARD)
    set_target_properties(example PROPERTIES C_STANDARD ${EXAMPLE_C_STANDARD} C_STANDARD_REQUIRED ON)
endif()
if(EXAMPLE_CXX_STANDARD)
    set_target_properties(example PROPERTIES CXX_STANDARD ${EXAMPLE_CXX_STANDARD} CXX_STANDARD_REQUIRED ON)
endif()
target_link_libraries(example PRIVATE ${EXAMPLE_LINK} android log)
