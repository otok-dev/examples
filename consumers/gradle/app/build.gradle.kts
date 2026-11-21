// Otok examples (c) Alexander A Pototskiy
// SPDX-License-Identifier: 0BSD
//
// The app's native library is the example's program built as a shared object (src/main/cpp/CMakeLists.txt), run by
// NativeActivity. What the run decides comes from gradle.properties, written by tools/check.py:
//   otokNdk        the NDK the libraries were built with (otok metadata's toolchain), and otokNdkVersion its revision
//   otokMinSdk     the deployment API level of [android]
//   otokAbis       the ABIs of [android], comma separated
//   otokCmakeArgs  the arguments of Gradle's CMake, ';' separated: the provider of the output, the example's settings
plugins {
    id("com.android.application")
}

fun property(name: String) = providers.gradleProperty(name).get()

android {
    namespace = "org.otok.example"
    compileSdk = 35
    ndkPath = property("otokNdk")
    ndkVersion = property("otokNdkVersion")

    defaultConfig {
        applicationId = "org.otok.example"
        minSdk = property("otokMinSdk").toInt()
        targetSdk = 35
        ndk {
            abiFilters += property("otokAbis").split(",")
        }
        externalNativeBuild {
            cmake {
                arguments += property("otokCmakeArgs").split(";")
            }
        }
    }

    buildTypes {
        release {
            // installable on an emulator: signed with the debug key
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
        }
    }
}
