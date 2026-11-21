// Otok examples (c) Alexander A Pototskiy
// SPDX-License-Identifier: 0BSD
//
// The Gradle consumer of the examples: an Android app whose native library, built by Gradle's CMake, links the
// libraries of otok's output (otok-toml.md 4.11). tools/check.py copies this directory and writes local.properties
// and the otok* properties of gradle.properties.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "otok-example"
include(":app")
