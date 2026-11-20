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
```

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
| `apple` | not yet: macOS, Mac Catalyst and the simulators (`simctl spawn`) | devices |
| `android` | not yet: the emulators | the other ABIs |

Options: `--index DIR` reads the index from a checkout of `otok-dev/index` or a view (`OTOK_INDEX_MIRROR`), so that a
run checks one commit of it; `--status DIR` keeps the lock of each passing run, and `--changed` skips the runs whose lock
is the same, which is how an index change finds what it touches (reverse dependencies and tool recipes included);
`--recipe LIBRARY=DIR` builds a library with a local recipe (`{target}` in `DIR` needs one `--target`); `--otok`,
`--cmake`, `--generator`; `--json FILE` writes the results.

## Status

Started 2026-11-20 (decisions 131 and 132 of otok's plan): the driver and the CMake consumer for `windows` and `linux`,
cases for zlib and libpng. Next: `apple` and `android`, SwiftPM, MSBuild and Gradle consumers for a few libraries, the
`basic` case of every library, CI on the build machines (never on pull requests) with the results in the branch
`status`.

## License

The examples are under the BSD Zero Clause License (`0BSD`): copy them freely.
