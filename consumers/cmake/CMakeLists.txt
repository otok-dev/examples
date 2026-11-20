# Otok examples (c) Alexander A Pototskiy
# SPDX-License-Identifier: 0BSD
#
# The CMake consumer of every example. tools/check.py generates example.cmake beside it with the sources, the
# package and the targets of the case and the output of its target table; the project is configured with the provider
# of that output, as a project moving to otok would be (otok-toml.md 4.12):
#
#   cmake -S . -B build -DCMAKE_PROJECT_TOP_LEVEL_INCLUDES=Otok/otok-provider.cmake
cmake_minimum_required(VERSION 3.28)
project(otok_example LANGUAGES C CXX)

include("${CMAKE_CURRENT_SOURCE_DIR}/example.cmake")

# The packages before the targets that link them: with the Xcode generator otok-config.cmake puts the XCFrameworks into
# the link phase of the targets created after it, so that Xcode picks the slice of what it builds (Mac Catalyst too).
if(EXAMPLE_PACKAGE)
    # the library's usual CMake name, answered by otok's provider
    find_package(${EXAMPLE_PACKAGE} REQUIRED ${EXAMPLE_COMPONENTS})
else()
    # a library without CMake names: otok's own targets, otok::<product>
    find_package(Otok CONFIG REQUIRED PATHS "${EXAMPLE_OUTPUT}" NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
endif()

add_executable(example ${EXAMPLE_SOURCES})
if(EXAMPLE_C_STANDARD)
    set_target_properties(example PROPERTIES C_STANDARD ${EXAMPLE_C_STANDARD} C_STANDARD_REQUIRED ON)
endif()
if(EXAMPLE_CXX_STANDARD)
    set_target_properties(example PROPERTIES CXX_STANDARD ${EXAMPLE_CXX_STANDARD} CXX_STANDARD_REQUIRED ON)
endif()
target_link_libraries(example PRIVATE ${EXAMPLE_LINK})

# the DLLs beside the program on Windows, the shared objects on Linux; nothing elsewhere
otok_copy_runtime_dlls(example)
# Apple: the frameworks of dynamic libraries (otok-toml.md 4.10)
if(COMMAND otok_embed_frameworks)
    otok_embed_frameworks(example)
endif()
