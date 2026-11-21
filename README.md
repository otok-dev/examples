# otok examples

Small programs that use the libraries of the otok index the way a project would: each one depends on a library through
otok, finds it with CMake under its usual name, makes a call that means something, checks the result and prints `ok`.
They are two things at once:

- a demonstration of using a library through otok, to copy from: the `otok.toml` of a case is the file a project
  would write, with the recipe, the version, the options and the flags the example is built with;
- regression tests of what otok delivers to a consumer (`otok publish` checks that a recipe builds; these check that
  the result links and runs): the link settings of products, the CMake names and the provider, the DLLs and shared
  objects beside a program, the configurations and architectures of each target.

## Layout

```
libraries/<library>/<case>/
  otok.toml         the project: target tables, [deps.<library>] with its options and flags
  example.toml      how the program is built and checked
  main.c, ...       its sources
consumers/cmake/    the CMake project every case is built with
consumers/msbuild/  a project of Visual Studio with otok.props and otok.targets
consumers/gradle/   an Android app whose native library Gradle's CMake builds (NativeActivity, glue.c)
tools/check.py      the driver
```

Each library has the case `basic`, the demonstration: the library as its recipe builds it by default, used for what it
is mostly used for. Other cases are added beside it when something was found broken and fixed (an option, compile
flags, a linkage, a combination of libraries): the case is named after what it checks and says where it comes from, so
that the fix stays checked.

## `otok.toml`

An ordinary manifest (otok's `docs/formats/otok-toml.md`). It has a table for each target the case covers, each with an
`output` of its own (`Otok/<target>`), since the outputs of two targets must not overlap; the targets a machine does not
build are skipped there. A table that sets `linkage` fixes it; otherwise the case is checked static and dynamic, through
a profile the driver adds to its copy of the file.

## `example.toml`

```toml
[example]
description = "Encode a small RGBA image to PNG in memory and decode it again."
issue = "https://github.com/otok-dev/recipes/issues/12"   # where the case comes from, for regression cases
sources = ["main.c"]           # default: every .c, .cpp, .cc and .cxx of the directory
args = ["{case}/data/a.png"]   # arguments of the program; {case} is the directory of the case
expect = "ok"                  # the last line the program prints (default "ok")
linkage = ["static"]           # narrows the linkages checked when otok.toml sets none (default: both)

[consumer]
package = "PNG"                # find_package(PNG); without it find_package(Otok) and otok::<product> targets
components = []                # COMPONENTS of find_package
link = ["PNG::PNG"]            # what the program links
c-standard = 11                # C_STANDARD / CXX_STANDARD of the program
cxx-standard = 17
consumers = ["cmake", "msbuild", "swiftpm", "gradle"]   # default ["cmake"]: the others for a few libraries
products = ["PNG"]             # otok's products the program links, for MSBuild (OtokProducts) and SwiftPM
swift-sources = ["main.swift"] # SwiftPM: a Swift program importing the products' modules, beside the C one
```

## The other consumers

CMake checks every case; the others check otok's files for their build systems on the cases that name them, built from
the same sources:

| Consumer | Where | What |
|---|---|---|
| `msbuild` | Windows | `consumers/msbuild/example.vcxproj.in` with the output's `otok.props` and `otok.targets` and `OtokProducts`, built by the MSBuild of Visual Studio for x64 and ARM64 in Debug and Release; the machine's architecture runs, with the DLLs `OtokCopyDlls` put beside it |
| `swiftpm` | macOS | a package depending on the output's `Package.swift` with an executable target of the C sources and one of `swift-sources`, both on the products, built by `swift build -c release` and run |
| `gradle` | Android | `consumers/gradle` (AGP 9.5.1, the Gradle wrapper 9.8.0): the C sources and `glue.c` as the app's native library, built by Gradle's CMake (the one of the run, `cmake.dir`) with the NDK of `otok metadata` for every ABI in debug and release; the APK must carry the app's library, the output's shared objects of each ABI and `libc++_shared.so` when the libraries are dynamic; on the emulator's ABIs the app is installed and started, and `glue.c` logs the program's output (tag `otok-example`). Java: `JAVA_HOME` or Android Studio's runtime |

## Running

```sh
python3 tools/check.py                       # every case, both linkages, the targets this machine builds
python3 tools/check.py libpng zlib/basic --linkage dynamic
python3 tools/check.py libpng --target linux --recipe 'libpng=../recipes/recipes/libpng/1.6/{target}'   # a fix not yet published
```

For each case and linkage the driver copies `otok.toml` into `build/<library>/<case>/<linkage>/`, adding after it what
the run needs (the profile of the linkage, the recipes of `--recipe`), resolves it with `otok update --no-build` and
installs it. For each target table this machine built, it configures the consumer with
`-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES=<output>/otok-provider.cmake`, builds it in each configuration and architecture and
runs what this machine can run, from its build directory, without any change of the search paths of libraries. A run
reaches one of the levels `resolved`, `installed`, `configured`, `linked`, `ran`; the log of every step is `check.log`
of the copy.

| Target | Runs | Links only |
|---|---|---|
| `windows` | the machine's architecture, Debug and Release (Visual Studio generator) | the other architecture |
| `linux` | the machine's architecture, Debug and Release; `ldd` must find the output's shared objects in the output or beside the program | |
| `apple` | macOS (the machine's architecture: a fat program runs its slice), the simulators through `xcrun simctl spawn` on a booted device or one of the newest runtime, booted for it; one Release build per platform with all its architectures (Ninja); Mac Catalyst, which CMake has not, with the Xcode generator for iOS with `SUPPORTS_MACCATALYST`, built by `xcodebuild` for its destination (signed ad hoc, without the hardened runtime) | devices, a platform without the machine's architecture |
| `android` | the ABIs of an emulator's own processor (x86_64 on a PC), Debug and Release: the emulator adb sees, or the last AVD of the SDK started headless for the run and stopped after it; the program, the output's shared objects of its ABI and `libc++_shared.so` pushed into one directory (as an app's native libraries are) and run there; a phone on USB only with `--device` | the other ABIs, and those an emulator translates (its namespace takes no `LD_LIBRARY_PATH`) |

Options: `--index DIR` reads the index from a checkout of `otok-dev/index` or a view (`OTOK_INDEX_MIRROR`), so that a
run checks one commit of it; `--status DIR` keeps the lock of each passing run, and `--changed` skips the runs whose lock
is the same, which is how an index change finds what it touches (reverse dependencies and tool recipes included);
`--recipe LIBRARY=DIR` builds a library with a local recipe (`{target}` in `DIR` needs one `--target`); `--otok`,
`--cmake`, `--generator`; `--android-sdk`, `--avd`, `--device SERIAL` (a phone on USB: the run writes into its
`/data/local/tmp/otok-examples`); `--json FILE` writes the results. An emulator that is there but does not come up for
adb (an image of Google Play may wait for adb to be authorized on its screen) fails the Android runs rather than
leaving them linked only; its data partition must have room for the app.

## Status

Started 2026-11-20 (decisions 131 to 134 of otok's plan): the driver and the CMake consumer for every target (`windows`,
`linux`, `apple` on all ten platforms, `android`), the MSBuild, SwiftPM and Gradle consumers. `basic` cases so far:
zlib, libpng; compression: bzip2, lz4, lzma, zstd, brotli; images: libjpeg-turbo, giflib, libwebp, libtiff, openjpeg,
libavif, dav1d. Next: the `basic` case of every other library, CI on the build machines (never on pull requests) with
the results in the branch `status`.

## License

The examples are under the BSD Zero Clause License (`0BSD`): copy them freely.
