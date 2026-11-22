# Otok examples (c) Alexander A Pototskiy
# SPDX-License-Identifier: 0BSD
"""Build and run the examples of otok-dev/examples (README.md).

Each case (libraries/<library>/<case>/) is an otok project as a user would write it, otok.toml, with the sources of a
program and example.toml saying how the program is built and checked. For each case and linkage the driver copies
otok.toml into a work directory (adding a profile that sets the linkage, unless otok.toml sets it), resolves it
(`otok update --no-build`) and installs it; then for each target table this machine built it configures, builds and
runs the CMake consumer of consumers/cmake in each configuration and architecture. Each run reaches a level:
resolved, installed, configured, linked, ran.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEVELS = ["failed", "resolved", "installed", "configured", "linked", "ran"]
TARGETS = ["apple", "android", "windows", "linux"]
CONSUMED = {"windows", "linux", "apple", "android"}  # targets whose consumers the driver builds so far (README.md, "Status")
PROFILE = "otok-examples"
ONLY_TARGETS: set[str] = set()  # the targets of --target: the other tables leave the copies of otok.toml


@dataclasses.dataclass
class Case:
    library: str
    name: str
    directory: Path
    example: dict    # example.toml
    manifest: dict   # otok.toml, as read
    text: str        # otok.toml, as written

    @property
    def id(self) -> str:
        return f"{self.library}/{self.name}"

    def tables(self) -> dict[str, dict]:
        return {t: self.manifest[t] for t in TARGETS if t in self.manifest}

    def linkages(self) -> list[str | None]:
        """None: as otok.toml says (a table of it sets `linkage`); otherwise both, or those example.toml names."""
        if any("linkage" in table for table in self.tables().values()):
            return [None]
        return self.example.get("example", {}).get("linkage", ["static", "dynamic"])


@dataclasses.dataclass
class Run:
    case: str
    linkage: str
    target: str = ""
    level: str = "failed"
    status: str = "failed"  # passed, failed, unsupported, unchanged, skipped
    configurations: dict = dataclasses.field(default_factory=dict)  # "<arch>/<configuration>" -> level
    message: str = ""
    log: str = ""
    seconds: float = 0.0


# --- helpers --------------------------------------------------------------------------------------------------------


def toml_string(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def cmake_list(values) -> str:
    return '"' + ";".join(str(v).replace("\\", "/") for v in values) + '"'


def write_if_changed(path: Path, text: str) -> None:
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8", newline="\n")


def machine_arch() -> str:
    return {"amd64": "x86_64", "x86_64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower(), platform.machine())


def clean_run_environment() -> dict:
    """The program runs from its build directory with nothing added to the search paths of libraries."""
    env = dict(os.environ)
    for name in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
        env.pop(name, None)
    return env


class Tools:
    def __init__(self, args):
        self.otok = args.otok or shutil.which("otok") or sys.exit("otok is not on PATH; give --otok")
        self.cmake = args.cmake or shutil.which("cmake") or find_visual_studio_cmake() or sys.exit("cmake is not on PATH; give --cmake")
        self.generator = args.generator
        self.android = AndroidDevice(args.android_sdk, args.avd, args.device)
        self.env = dict(os.environ)
        if args.index:
            # the index at one commit: a checkout of otok-dev/index or a view (config.md 2)
            self.env["OTOK_INDEX_MIRROR"] = str(Path(args.index).resolve())

    def run(self, command: list, cwd: Path, log: Path, env: dict | None = None) -> subprocess.CompletedProcess:
        with open(log, "a", encoding="utf-8") as out:
            out.write(f"\n$ {' '.join(str(c) for c in command)}\n")
            out.flush()
            result = subprocess.run([str(c) for c in command], cwd=cwd, env=env or self.env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            out.write(result.stdout)
            out.write(f"[exit {result.returncode}]\n")
        return result


def find_visual_studio_cmake() -> str | None:
    if platform.system() != "Windows":
        return None
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if not vswhere.exists():
        return None
    found = subprocess.run([str(vswhere), "-latest", "-products", "*", "-find", r"Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"],
                           stdout=subprocess.PIPE, text=True)
    lines = found.stdout.splitlines()
    return lines[0] if lines else None


# --- cases ----------------------------------------------------------------------------------------------------------


def load_cases(selected: list[str]) -> list[Case]:
    cases = []
    for file in sorted((ROOT / "libraries").glob("*/*/otok.toml")):
        directory = file.parent
        library, name = directory.parent.name, directory.name
        if selected and library not in selected and f"{library}/{name}" not in selected:
            continue
        text = file.read_text(encoding="utf-8")
        example_file = directory / "example.toml"
        example = tomllib.loads(example_file.read_text(encoding="utf-8")) if example_file.exists() else {}
        cases.append(Case(library, name, directory, example, tomllib.loads(text), text))
    return cases


def project_manifest(case: Case, linkage: str | None, local_recipes: dict[str, str], excluded: set[str] | None = None) -> str:
    """otok.toml of the case as it is, with what the run adds after it: the profile of the linkage and the recipes of
    --recipe; without the tables of `excluded` (targets whose recipe has not the linkage) and, with --target, of the other
    targets."""
    text = case.text if case.text.endswith("\n") else case.text + "\n"
    tables = list(case.tables())
    # the tables of targets not checked leave the copy: this machine would build them for nothing, and a recipe of
    # --recipe naming {target} is one target's
    dropped = (excluded or set()) | ({t for t in tables if t not in ONLY_TARGETS} if ONLY_TARGETS else set())
    for target in dropped:
        text = re.sub(r"^\[" + target + r"\]\n(?:(?!\[).*\n|\n)*", "", text, flags=re.M)
    tables = [t for t in tables if t not in dropped]
    added = []
    for library, directory in local_recipes.items():
        recipe = "{ path = " + toml_string(Path(directory).resolve().as_posix()) + " }"
        deps = case.manifest.get("deps", {})
        if library in deps:
            # the line of its recipe in the case's own table, which a profile cannot change (otok-toml.md 8)
            # the lines alone ([^\n]*): the keys after them (options, linkage) stay
            pattern = re.compile(r"(\[deps\." + re.escape(library) + r"\][^\[]*?)^recipe\s*=[^\n]*\n(?:^version\s*=[^\n]*\n)?", re.M)
            text, n = pattern.subn(lambda m: m.group(1) + f"recipe = {recipe}\n", text, count=1)
            if n != 1:
                sys.exit(f"{case.id}: cannot replace the recipe of [deps.{library}] in otok.toml for --recipe")
        else:
            added.append(f"[deps.{library}]\nrecipe = {recipe}\n")
    if linkage:
        # sub-tables: the case may have tables of this profile too (`[profile.otok-examples.deps.zlib]`)
        added.append("".join(f"[profile.{PROFILE}.{t}]\nlinkage = {toml_string(linkage)}\n" for t in tables))
    if added:
        text += "\n# Added by tools/check.py for this run.\n" + "\n".join(added)
    return text


def consumer_settings(case: Case, output: Path) -> str:
    example = case.example.get("example", {})
    consumer = case.example.get("consumer", {})
    sources = [case.directory / s for s in example.get("sources", [])] or sorted(
        p for p in case.directory.iterdir() if p.suffix in (".c", ".cpp", ".cc", ".cxx"))
    lines = [
        "# Generated by otok-dev/examples tools/check.py; do not edit.",
        f"set(EXAMPLE_SOURCES {cmake_list(sources)})",
        f"set(EXAMPLE_PACKAGE {cmake_list([consumer['package']] if 'package' in consumer else [])})",
        f"set(EXAMPLE_COMPONENTS {cmake_list(['COMPONENTS', *consumer['components']] if consumer.get('components') else [])})",
        f"set(EXAMPLE_LINK {cmake_list(consumer.get('link', []))})",
        f"set(EXAMPLE_C_STANDARD {cmake_list([consumer['c-standard']] if 'c-standard' in consumer else [])})",
        f"set(EXAMPLE_CXX_STANDARD {cmake_list([consumer['cxx-standard']] if 'cxx-standard' in consumer else [])})",
        f"set(EXAMPLE_OUTPUT {cmake_list([output.as_posix()])})",
    ]
    return "\n".join(lines) + "\n"


# --- one case in one linkage ----------------------------------------------------------------------------------------


def check_case(tools: Tools, case: Case, linkage: str | None, targets: list[str], work: Path, status_dir: Path | None,
               changed_only: bool, local_recipes: dict[str, str]) -> list[Run]:
    started = time.monotonic()
    label = linkage or "as-written"
    project = work / case.library / case.name / label
    project.mkdir(parents=True, exist_ok=True)
    log = project / "check.log"
    log.write_text("", encoding="utf-8")
    # the profile of the linkage, and that of the case's otok.toml (a profile's `deps.<library>`, otok-toml.md 8)
    profile = ["--profile", PROFILE] if linkage or PROFILE in case.manifest.get("profile", {}) else []
    unsupported: list[Run] = []

    def whole(status: str, level: str, message: str) -> list[Run]:
        return unsupported + [Run(case.id, label, "", level, status, {}, message, str(log), round(time.monotonic() - started, 1))]

    def exclude(target: str, library: str, kind: str) -> bool:
        """The target "unsupported": its tables leave the copy. False when nothing else is left to check."""
        excluded.add(target)
        whose = library if library == case.library else f"{library} (a dependency of {case.library})"
        unsupported.append(Run(case.id, label, target, "failed", "unsupported", {},
                               f"the recipe of {whose} builds no {kind} libraries for {target}", str(log)))
        return bool([t for t in case.tables() if t not in excluded and (not ONLY_TARGETS or t in ONLY_TARGETS)])

    # resolve: the lock, compared with that of the last passing run. The linkage of the target tables is a preference
    # (otok-toml.md 5, otok 0.5.29): a recipe without it builds the other; a linkage the case's otok.toml
    # chooses for a library is still refused, and its target is "unsupported" and leaves the copy.
    # The recipes of --recipe: of the case's library and of its [deps] at once; the others only once the lock shows them
    # in the case's graph, which a [deps] entry added for nothing would change (a second holder of a static library)
    excluded: set[str] = set()
    recipes = {l: d for l, d in local_recipes.items() if l == case.library or l in case.manifest.get("deps", {})}
    while True:
        write_if_changed(project / "otok.toml", project_manifest(case, linkage, recipes, excluded))
        resolved = tools.run([tools.otok, "update", "--no-build", *profile], project, log)
        if resolved.returncode == 0:
            graph = set(re.findall(r'^library = "([^"]+)"', (project / "otok.lock").read_text(encoding="utf-8"), re.M))
            more = {l: d for l, d in local_recipes.items() if l not in recipes and l in graph}
            if not more:
                break
            recipes.update(more)
            continue
        refused = re.search(r"cannot be built as (static|dynamic) libraries for '([^']+)'.*?\[deps\.([^\]]+)\]", resolved.stdout)
        target = target_of_platform(refused.group(2)) if refused else None
        if not refused or not target or target in excluded:
            return whole("failed", "failed", "otok update --no-build failed")
        if not exclude(target, refused.group(3), refused.group(1)):
            return unsupported
    lock = (project / "otok.lock").read_text(encoding="utf-8")
    stored = status_dir / "locks" / case.library / case.name / f"{label}.lock" if status_dir else None
    if changed_only and stored and stored.exists() and stored.read_text(encoding="utf-8") == lock:
        return whole("unchanged", "resolved", "otok.lock is that of the last passing run")

    # install: a static library falling back inside a dynamic one that the case also names in [deps] is a second copy,
    # an error of otok (otok-toml.md 5); its target is "unsupported" as the case is written
    while True:
        installed = tools.run([tools.otok, "install", *profile], project, log)
        if installed.returncode == 0:
            break
        copies = re.search(r"'([^']+)' is static as the target table falls back \(its recipe builds no (static|dynamic) library for '([^']+)'\)",
                           installed.stdout)
        if not copies or copies.group(3) in excluded:
            return whole("failed", "resolved", "otok install failed")
        if not exclude(copies.group(3), copies.group(1), copies.group(2)):
            return unsupported
        write_if_changed(project / "otok.toml", project_manifest(case, linkage, recipes, excluded))
    # a dynamic library exporting the static libraries inside it, which otok should have hidden (otok-toml.md 5.2): a
    # warning of otok install, a failure of the case
    exported = re.search(r"^warning: (the dynamic library .* exports symbols of the static libraries inside it: [^;]*)", installed.stdout, re.M)
    if exported:
        return whole("failed", "installed", exported.group(1))
    skipped = dict(re.findall(r"^note: not building for '([^']+)': (.*)$", installed.stdout, re.M))
    # the target tables as otok reads them, the profile applied: output, platforms, architectures, configurations; and the
    # linkage each library got
    metadata = subprocess.run([tools.otok, "metadata", *profile], cwd=project, env=tools.env, stdout=subprocess.PIPE, text=True,
                              encoding="utf-8", errors="replace")
    document = json.loads(metadata.stdout) if metadata.returncode == 0 else {}
    tables = {t["name"]: t for t in document.get("targets", [])}
    # the case's library in another linkage than the one asked: the example does not check what it says. Its
    # dependencies falling back are the fallback's purpose, not the case's concern.
    fallbacks = {o["target"]: (o["linkage"], o["linkage-fallback"]) for p in document.get("packages", []) if p["library"] == case.library and not p["tool"]
                 for o in p["outputs"] if o.get("linkage-fallback")}

    runs = list(unsupported)
    for target in case.tables():
        if target not in targets or target in excluded:
            continue
        run = Run(case.id, label, target, "installed", "failed", log=str(log))
        runs.append(run)
        if target in skipped:
            run.status, run.message = "skipped", skipped[target]
            continue
        if target in fallbacks:
            got, why = fallbacks[target]
            run.status, run.message = "unsupported", f"{case.library} is {got} here: {why}"
            continue
        if target not in CONSUMED:
            run.status, run.message = "skipped", "the driver builds no consumer of this target yet"
            continue
        if target not in tables:
            run.message = "otok metadata failed"
            continue
        check_consumer(tools, case, project / f"consumer-{target}", target, tables[target], run, log)
    for run in runs:
        run.seconds = round(time.monotonic() - started, 1)
    if stored and runs and all(r.status in ("passed", "skipped", "unsupported") for r in runs) and any(r.status == "passed" for r in runs):
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_text(lock, encoding="utf-8", newline="\n")
    return runs or whole("skipped", "installed", "none of the case's target tables is one this machine builds")


def target_of_platform(name: str) -> str | None:
    """The target of a platform as otok names it ('iossim' is Apple's)."""
    if name in ("android", "windows", "linux"):
        return name
    return "apple" if name in APPLE_PLATFORMS or name == "catalyst" else None


# Apple's platforms in CMake: CMAKE_SYSTEM_NAME, the SDK, the deployment key of otok.toml and the simulator's runtime
# family (None: a device, whose programs only link). CMake has no Mac Catalyst (otok-toml.md 4).
APPLE_PLATFORMS = {
    "macosx": ("Darwin", "macosx", "macos", None),
    "ios": ("iOS", "iphoneos", "ios", None),
    "iossim": ("iOS", "iphonesimulator", "ios", "iOS"),
    "tvos": ("tvOS", "appletvos", "tvos", None),
    "tvossim": ("tvOS", "appletvsimulator", "tvos", "tvOS"),
    "watchos": ("watchOS", "watchos", "watchos", None),
    "watchossim": ("watchOS", "watchsimulator", "watchos", "watchOS"),
    "xros": ("visionOS", "xros", "visionos", None),
    "xrossim": ("visionOS", "xrsimulator", "visionos", "xrOS"),
}


def check_consumer(tools: Tools, case: Case, base: Path, target: str, table: dict, run: Run, log: Path) -> None:
    """Configure, build and run the CMake consumer of one target table (as `otok metadata` gives it) in each
    configuration, platform and architecture."""
    output = Path(table["output"])
    source = base / "source"
    source.mkdir(parents=True, exist_ok=True)
    write_if_changed(source / "CMakeLists.txt", (ROOT / "consumers/cmake/CMakeLists.txt").read_text(encoding="utf-8"))
    write_if_changed(source / "example.cmake", consumer_settings(case, output))
    configurations = [c for c in ["debug", "release"] if c in table["configurations"]]
    provider = (output / "otok-provider.cmake").as_posix()
    example = case.example.get("example", {})
    arguments = [str(a).replace("{case}", case.directory.as_posix()) for a in example.get("args", [])]
    expect = example.get("expect", "ok")
    expected: dict[str, str] = {}  # "<platform or arch>/<configuration>" -> the level it must reach

    def configure(build: Path, extra: list) -> bool:
        shutil.rmtree(build, ignore_errors=True)
        command = [tools.cmake, "-S", source, "-B", build, f"-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES={provider}", *extra]
        if tools.generator:
            command += ["-G", tools.generator]
        return tools.run(command, source, log).returncode == 0

    def build_and_run(build: Path, configuration: str, program: Path, runs: bool, launcher: list | None = None) -> str:
        if tools.run([tools.cmake, "--build", build, "--config", configuration.capitalize()], source, log).returncode != 0:
            return "configured"
        if not runs:
            return "linked"
        result = tools.run([*(launcher or []), program, *arguments], program.parent, log, env=clean_run_environment())
        last = result.stdout.strip().splitlines()[-1:] if result.stdout.strip() else []
        if result.returncode != 0 or last != [expect]:
            return "linked"
        foreign = foreign_libraries(program, output, log)
        if foreign:
            with open(log, "a", encoding="utf-8") as out:
                out.write("loaded from elsewhere than the output or the program's directory: " + ", ".join(foreign) + "\n")
            return "linked"
        return "ran"

    def record(key: str, wanted: str, reached: str) -> None:
        expected[key] = wanted
        run.configurations[key] = reached

    exe = ".exe" if platform.system() == "Windows" else ""
    if target == "windows":
        # the Visual Studio generator, one build directory per architecture; the machine's runs, the other links
        for arch in table["architectures"].get("windows", ["x86_64"]):
            build = base / arch
            configured = configure(build, ["-A", "ARM64" if arch == "arm64" else "x64"])
            for c in configurations:
                runs = arch == machine_arch()
                record(f"{arch}/{c}", "ran" if runs else "linked",
                       build_and_run(build, c, build / c.capitalize() / f"example{exe}", runs) if configured else "installed")
        if "msbuild" in consumers(case):
            check_msbuild(tools, case, base.parent / "msbuild-windows", output, table, configurations, arguments, expect, log, record)
    elif target == "android":
        check_android(tools, base, source, provider, output, table, configurations, arguments, expect, table.get("linkage", "static"),
                      log, record)
        if "gradle" in consumers(case):
            check_gradle(tools, case, base.parent / "gradle-android", source / "example.cmake", provider, output, table, configurations,
                         expect, table.get("linkage", "static"), log, record)
        if tools.android.problem:
            # an emulator that would have run the programs, but did not come up: a failure, not a run that only links
            record("emulator", "ran", "installed")
            run.message = tools.android.problem
    elif target == "apple":
        # one build per platform with all its architectures: the program runs the machine's slice, on macOS itself and on
        # a simulator through simctl; a device's, or one without the machine's architecture, only links
        for p in table["platforms"]:
            if p == "catalyst":
                for c in configurations:
                    record(f"{p}/{c}", "ran" if machine_arch() in table["architectures"].get(p, []) else "linked",
                           check_catalyst(tools, base / p, source, provider, table, arguments, expect, log))
                continue
            if p not in APPLE_PLATFORMS:
                run.message = (run.message + "; " if run.message else "") + f"{p}: CMake builds no consumer for it"
                continue
            system, sdk, deployment, family = APPLE_PLATFORMS[p]
            arches = table["architectures"].get(p, [])
            runnable = machine_arch() in arches and (p == "macosx" or family is not None)
            launcher = simulator_launcher(tools, family, log) if family and runnable else None
            if family and runnable and launcher is None:
                runnable = False
            extra = [f"-DCMAKE_SYSTEM_NAME={system}", f"-DCMAKE_OSX_SYSROOT={sdk}", f"-DCMAKE_OSX_ARCHITECTURES={';'.join(arches)}",
                     "-DCMAKE_BUILD_TYPE=Release"]
            if deployment in table.get("deployment", {}):
                extra.append(f"-DCMAKE_OSX_DEPLOYMENT_TARGET={table['deployment'][deployment]}")
            build = base / p
            # CMake makes an executable a bundle on the platforms other than macOS
            program = build / "example" if p == "macosx" else build / "example.app" / "example"
            for c in configurations:
                record(f"{p}/{c}", "ran" if runnable else "linked",
                       build_and_run(build, c, program, runnable, launcher) if configure(build, extra) else "installed")
        if "swiftpm" in consumers(case) and "macosx" in table["platforms"]:
            check_swiftpm(tools, case, base.parent / "swiftpm-apple", output, table, arguments, expect, log, record)
    else:
        for c in configurations:
            build = base / c
            record(f"{machine_arch()}/{c}", "ran",
                   build_and_run(build, c, build / f"example{exe}", True) if configure(build, [f"-DCMAKE_BUILD_TYPE={c.capitalize()}"]) else "installed")

    short = [k for k, level in run.configurations.items() if LEVELS.index(level) < LEVELS.index(expected[k])]
    run.level = min(run.configurations.values(), key=LEVELS.index) if run.configurations else "installed"
    if run.configurations and not short:
        run.status = "passed"
    else:
        problem = f"{', '.join(short)}: stopped at {run.configurations[short[0]]}" if short else "nothing was built"
        run.message = problem + ("; " + run.message if run.message else "")


def consumers(case: Case) -> list[str]:
    """The consumers a case is built with: CMake always; MSBuild, SwiftPM and Gradle for the cases that ask for them."""
    return case.example.get("consumer", {}).get("consumers", ["cmake"])


def products(case: Case) -> list[str]:
    """The products of otok.toml's libraries the program links, for the consumers that name products."""
    found = case.example.get("consumer", {}).get("products")
    if not found:
        sys.exit(f"{case.id}: [consumer] 'products' is needed by the consumers {consumers(case)}")
    return found


def find_msbuild() -> str | None:
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
    if not vswhere.exists():
        return None
    found = subprocess.run([str(vswhere), "-latest", "-products", "*", "-find", r"MSBuild\**\Bin\MSBuild.exe"], stdout=subprocess.PIPE, text=True)
    lines = found.stdout.splitlines()
    return lines[0] if lines else None


def check_msbuild(tools: Tools, case: Case, build: Path, output: Path, table: dict, configurations: list, arguments: list, expect: str,
                  log: Path, record) -> None:
    """A project of Visual Studio importing otok.props and otok.targets (consumers/msbuild), built by MSBuild for each
    architecture and configuration; the machine's architecture runs, with the DLLs OtokCopyDlls put beside it."""
    from xml.sax.saxutils import escape
    msbuild = find_msbuild()
    shutil.rmtree(build, ignore_errors=True)
    build.mkdir(parents=True)
    example = case.example.get("example", {})
    sources = [case.directory / s for s in example.get("sources", [])] or sorted(
        p for p in case.directory.iterdir() if p.suffix in (".c", ".cpp", ".cc", ".cxx"))
    text = (ROOT / "consumers/msbuild/example.vcxproj.in").read_text(encoding="utf-8")
    text = text.replace("@OUTPUT@", escape(str(output).replace("/", "\\") + "\\")).replace("@PRODUCTS@", escape(";".join(products(case))))
    text = text.replace("@SOURCES@", "\n".join(f'    <ClCompile Include="{escape(str(s))}" />' for s in sources))
    project = build / "example.vcxproj"
    project.write_text(text, encoding="utf-8", newline="\r\n")
    for arch in table["architectures"].get("windows", ["x86_64"]):
        msbuild_platform = "ARM64" if arch == "arm64" else "x64"
        for c in configurations:
            key = f"msbuild/{arch}/{c}"
            runs = arch == machine_arch()
            if not msbuild:
                record(key, "linked", "installed")
                continue
            built = tools.run([msbuild, project, "/nologo", "/v:minimal", f"/p:Configuration={c.capitalize()}", f"/p:Platform={msbuild_platform}"],
                              build, log)
            if built.returncode != 0:
                record(key, "ran" if runs else "linked", "configured")
                continue
            if not runs:
                record(key, "linked", "linked")
                continue
            program = build / "out" / msbuild_platform / c.capitalize() / "example.exe"
            result = tools.run([program, *arguments], program.parent, log, env=clean_run_environment())
            last = result.stdout.strip().splitlines()[-1:] if result.stdout.strip() else []
            record(key, "ran", "ran" if result.returncode == 0 and last == [expect] else "linked")


def check_swiftpm(tools: Tools, case: Case, build: Path, output: Path, table: dict, arguments: list, expect: str, log: Path,
                  record) -> None:
    """A package depending on Package.swift of the output (otok-toml.md 4), built by `swift build` for macOS: the case's
    C program as an executable target, and its Swift program (swift-sources) importing the products' modules."""
    shutil.rmtree(build, ignore_errors=True)
    example = case.example.get("example", {})
    consumer = case.example.get("consumer", {})
    sources = [case.directory / s for s in example.get("sources", [])] or sorted(
        p for p in case.directory.iterdir() if p.suffix in (".c", ".cpp", ".cc", ".cxx"))
    targets = {"example": sources}
    if consumer.get("swift-sources"):
        targets["example-swift"] = [case.directory / s for s in consumer["swift-sources"]]
    for name, files in targets.items():
        (build / "Sources" / name).mkdir(parents=True)
        for f in files:
            shutil.copyfile(f, build / "Sources" / name / f.name)
    identity = output.name  # a package of a path is known by its directory's name
    dependencies = ", ".join(f'.product(name: "{p}", package: "{identity}")' for p in products(case))
    macos = table.get("deployment", {}).get("macos", "12.0")
    executables = "".join(f'        .executableTarget(name: "{name}", dependencies: [{dependencies}]),\n' for name in targets)
    (build / "Package.swift").write_text(
        "// swift-tools-version:5.9\n// Generated by otok-dev/examples tools/check.py; do not edit.\n\nimport PackageDescription\n\n"
        f'let package = Package(\n    name: "Example",\n    platforms: [.macOS("{macos}")],\n'
        f'    dependencies: [.package(path: "{output.as_posix()}")],\n    targets: [\n{executables}    ]\n)\n',
        encoding="utf-8", newline="\n")
    built = tools.run(["xcrun", "swift", "build", "-c", "release", "--package-path", build], build, log)
    for name in targets:
        key = f"swiftpm/{name}"
        if built.returncode != 0:
            record(key, "ran", "configured")
            continue
        program = build / ".build" / "release" / name
        result = tools.run([program, *arguments], build, log, env=clean_run_environment())
        last = result.stdout.strip().splitlines()[-1:] if result.stdout.strip() else []
        record(key, "ran", "ran" if result.returncode == 0 and last == [expect] else "linked")


def find_java_home(sdk: Path | None) -> str | None:
    """JAVA_HOME, or the JetBrains runtime of Android Studio beside the SDK (its usual places)."""
    if os.environ.get("JAVA_HOME"):
        return os.environ["JAVA_HOME"]
    candidates = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Android" / "Android Studio" / "jbr",
                  Path("/Applications/Android Studio.app/Contents/jbr/Contents/Home")]
    if sdk:
        candidates.insert(0, sdk.parent / "Android Studio" / "jbr")
    return next((str(c) for c in candidates if c.is_dir()), None)


def check_gradle(tools: Tools, case: Case, build: Path, source_settings: Path, provider: str, output: Path, table: dict,
                 configurations: list, expect: str, linkage: str, log: Path, record) -> None:
    """The Android app of consumers/gradle, built by Gradle in debug and release: the native library of each ABI in the
    APK, with the shared objects of the output it loads and libc++_shared.so when the libraries are dynamic; the app
    run on the emulator's ABIs, its output read from the log."""
    import zipfile
    shutil.rmtree(build, ignore_errors=True)
    shutil.copytree(ROOT / "consumers" / "gradle", build)
    device = tools.android
    ndk = (table.get("toolchain") or {}).get("ndk", "")
    cmake_dir = Path(tools.cmake).parent.parent  # Gradle's CMake: the one of the run, Ninja from PATH
    abis = table["architectures"].get("android", [])
    arguments = [f"-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES={provider}", f"-DEXAMPLE_SETTINGS={source_settings.as_posix()}"]
    if linkage == "dynamic":
        arguments.append("-DANDROID_STL=c++_shared")
    (build / "local.properties").write_text(
        f"sdk.dir={str(device.sdk).replace(chr(92), '/') if device.sdk else ''}\ncmake.dir={cmake_dir.as_posix()}\n", encoding="utf-8")
    with open(build / "gradle.properties", "a", encoding="utf-8") as f:
        f.write(f"otokNdk={Path(ndk).as_posix()}\notokNdkVersion={(table.get('toolchain') or {}).get('revision', '')}\notokMinSdk={table.get('deployment', {}).get('android', '24')}\n"
                f"otokAbis={','.join(abis)}\notokCmakeArgs={';'.join(arguments)}\n")
    env = dict(tools.env)
    java = find_java_home(device.sdk)
    if java:
        env["JAVA_HOME"] = java
    gradlew = build / ("gradlew.bat" if platform.system() == "Windows" else "gradlew")
    if platform.system() != "Windows":
        gradlew.chmod(0o755)
    tasks = [f"assemble{c.capitalize()}" for c in configurations]
    built = tools.run([gradlew, "--no-daemon", "--console=plain", *tasks], build, log, env=env)
    runs_on = device.abis if device.prepare(log) else []
    for c in configurations:
        apk = build / "app" / "build" / "outputs" / "apk" / c / f"app-{c}.apk"
        names = set(zipfile.ZipFile(apk).namelist()) if built.returncode == 0 and apk.exists() else set()
        lib = "debug/lib" if c == "debug" else "lib"
        for abi in abis:
            key = f"gradle/{abi}/{c}"
            runnable = abi in runs_on
            # what the APK must carry: the app's library, the output's shared objects, the C++ runtime they use
            wanted = {f"lib/{abi}/libexample.so"} | {f"lib/{abi}/{p.name}" for p in output.glob(f"*/{lib}/{abi}/*.so")}
            if linkage == "dynamic":
                wanted.add(f"lib/{abi}/libc++_shared.so")
            if not names or not wanted <= names:
                if names:
                    with open(log, "a", encoding="utf-8") as out:
                        out.write(f"{apk.name} lacks for {abi}: {', '.join(sorted(wanted - names))}\n")
                record(key, "ran" if runnable else "linked", "configured")
                continue
            if not runnable:
                record(key, "linked", "linked")
                continue
            record(key, "ran", run_apk(tools, device, apk, abi, expect, log))


def run_apk(tools: Tools, device: AndroidDevice, apk: Path, abi: str, expect: str, log: Path) -> str:
    """Installs the app for the ABI, starts its NativeActivity and reads what glue.c logs."""
    adb = [device.adb(), "-s", device.serial]
    tools.run([*adb, "uninstall", "org.otok.example"], ROOT, log)
    if tools.run([*adb, "install", "-r", "--abi", abi, apk], ROOT, log).returncode != 0:
        return "linked"
    tools.run([*adb, "logcat", "-c"], ROOT, log)
    tools.run([*adb, "shell", "am", "start", "-W", "-n", "org.otok.example/android.app.NativeActivity"], ROOT, log)
    lines: list[str] = []
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        logged = subprocess.run([*adb, "logcat", "-d", "-v", "raw", "-s", "otok-example:I"], stdout=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace").stdout
        lines = [line for line in logged.splitlines() if line and not line.startswith("-")]
        if any(line.startswith("exit=") for line in lines):
            break
        time.sleep(1)
    with open(log, "a", encoding="utf-8") as out:
        out.write("logged by the app:\n" + "".join(f"  {line}\n" for line in lines))
    tools.run([*adb, "uninstall", "org.otok.example"], ROOT, log)
    output = [line for line in lines if not line.startswith("exit=")]
    return "ran" if "exit=0" in lines and output[-1:] == [expect] else "linked"


def check_catalyst(tools: Tools, build: Path, source: Path, provider: str, table: dict, arguments: list, expect: str, log: Path) -> str:
    """Mac Catalyst, which CMake has not: the Xcode generator for iOS with SUPPORTS_MACCATALYST, built by xcodebuild for
    the destination of Mac Catalyst. The XCFrameworks are in the link phase (otok-config.cmake sets KNOWN_LOCATION for
    the Xcode generator), so Xcode picks their slices of Mac Catalyst."""
    shutil.rmtree(build, ignore_errors=True)
    deployment = table.get("deployment", {})
    version = deployment.get("catalyst", deployment.get("ios"))
    configure = [tools.cmake, "-S", source, "-B", build, "-G", "Xcode", f"-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES={provider}",
                 "-DCMAKE_SYSTEM_NAME=iOS", "-DCMAKE_OSX_SYSROOT=iphoneos", "-DCMAKE_XCODE_GENERATE_SCHEME=ON",
                 "-DCMAKE_XCODE_ATTRIBUTE_SUPPORTS_MACCATALYST=YES", "-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY=-",
                 # signed ad hoc, a program of the hardened runtime loads no framework signed apart from it ("different Team
                 # IDs"); an app signed by its team has its embedded frameworks signed again with it when Xcode copies them
                 "-DCMAKE_XCODE_ATTRIBUTE_ENABLE_HARDENED_RUNTIME=NO"]
    if version:
        configure.append(f"-DCMAKE_OSX_DEPLOYMENT_TARGET={version}")
    if tools.run(configure, source, log).returncode != 0:
        return "installed"
    built = tools.run(["xcodebuild", "-project", build / "otok_example.xcodeproj", "-scheme", "example", "-configuration", "Release",
                       "-destination", "generic/platform=macOS,variant=Mac Catalyst", f"SYMROOT={build / 'xcode'}"], build, log)
    if built.returncode != 0:
        return "configured"
    program = build / "Release-maccatalyst" / "example.app" / "Contents" / "MacOS" / "example"
    if machine_arch() not in table["architectures"].get("catalyst", []):
        return "linked"
    result = tools.run([program, *arguments], program.parent, log, env=clean_run_environment())
    last = result.stdout.strip().splitlines()[-1:] if result.stdout.strip() else []
    return "ran" if result.returncode == 0 and last == [expect] else "linked"


_simulators: dict[str, list | None] = {}


def simulator_launcher(tools: Tools, family: str, log: Path) -> list | None:
    """`xcrun simctl spawn <device>` on a booted simulator of the family (iOS, tvOS, watchOS, xrOS), or on one of its
    newest runtime, booted for it; None when the machine has none."""
    if family in _simulators:
        return _simulators[family]
    listed = subprocess.run(["xcrun", "simctl", "list", "devices", "available", "-j"], stdout=subprocess.PIPE, text=True)
    devices = []
    for runtime, entries in json.loads(listed.stdout or "{}").get("devices", {}).items():
        m = re.search(r"SimRuntime\." + family + r"-(\d+)-(\d+)", runtime)
        if m:
            devices += [((e["state"] == "Booted", int(m.group(1)), int(m.group(2))), e["udid"]) for e in entries]
    if not devices:
        _simulators[family] = None
        return None
    (booted, *_), udid = max(devices)
    if not booted:
        tools.run(["xcrun", "simctl", "boot", udid], ROOT, log)
        tools.run(["xcrun", "simctl", "bootstatus", udid, "-b"], ROOT, log)
    _simulators[family] = ["xcrun", "simctl", "spawn", udid]
    return _simulators[family]


def foreign_libraries(program: Path, output: Path, log: Path) -> list[str]:
    """On Linux, the shared objects of the output that the program loads neither from the output nor from beside itself
    (the system's zlib for that of the output, through a library whose RUNPATH does not reach it). Elsewhere nothing:
    Windows loads DLLs beside the program first, and Apple's install names are absolute (@rpath of the frameworks)."""
    if platform.system() != "Linux":
        return []
    ours = {p.name for p in output.glob("*/lib/*.so*")} | {p.name for p in output.glob("*/debug/lib/*.so*")}
    if not ours:
        return []
    result = subprocess.run(["ldd", str(program)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=clean_run_environment())
    with open(log, "a", encoding="utf-8") as out:
        out.write(f"\n$ ldd {program}\n{result.stdout}")
    foreign = []
    for line in result.stdout.splitlines():
        m = re.match(r"\s*(\S+) => (\S+)", line)
        if not m or m.group(1) not in ours:
            continue
        # from the output, or from beside the program, where otok_copy_runtime_dlls puts them (otok-toml.md 4.11)
        found = Path(m.group(2)).resolve()
        if not (found.is_relative_to(output.resolve()) or found.parent == program.resolve().parent):
            foreign.append(f"{m.group(1)} from {m.group(2)}")
    return foreign


# --- Android ----------------------------------------------------------------------------------------------------------

NDK_TRIPLES = {"arm64-v8a": "aarch64-linux-android", "armeabi-v7a": "arm-linux-androideabi", "x86": "i686-linux-android",
               "x86_64": "x86_64-linux-android"}


class AndroidDevice:
    """A device for running programs: an emulator adb sees, or one of the SDK started for the run (headless) and stopped
    at its end. A phone on USB only when --device names it: the run writes into its /data/local/tmp."""

    def __init__(self, sdk: str | None, avd: str | None, serial: str | None):
        self.sdk = Path(sdk) if sdk else find_android_sdk()
        self.avd = avd
        self.wanted = serial
        self.serial: str | None = None
        self.abis: list[str] = []
        self.started: subprocess.Popen | None = None
        self.tried = False
        self.problem = ""  # an emulator there, but not usable: what runs on it fails instead of only linking

    def adb(self) -> str:
        return str(self.sdk / "platform-tools" / ("adb.exe" if platform.system() == "Windows" else "adb")) if self.sdk else "adb"

    def prepare(self, log: Path) -> bool:
        if self.tried:
            return self.serial is not None
        self.tried = True
        if not self.sdk or not Path(self.adb()).exists():
            return False
        serials = self._devices()
        if not serials and self.wanted:
            return False
        if not serials:
            emulator = self.sdk / "emulator" / ("emulator.exe" if platform.system() == "Windows" else "emulator")
            avds = subprocess.run([str(emulator), "-list-avds"], stdout=subprocess.PIPE, text=True).stdout.split() if emulator.exists() else []
            avd = self.avd or (avds[-1] if avds else None)
            if not avd:
                return False
            with open(log, "a", encoding="utf-8") as out:
                out.write(f"\n$ {emulator} -avd {avd} -no-window -no-audio -no-boot-anim -no-snapshot-save\n")
            self.started = subprocess.Popen([str(emulator), "-avd", avd, "-no-window", "-no-audio", "-no-boot-anim", "-no-snapshot-save"],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline and not serials:
                time.sleep(2)
                serials = self._devices()
            if not serials:
                self.problem = f"the emulator {avd} did not come up for adb (an image of Google Play may ask to authorize adb on its screen)"
                return False
        self.serial = serials[0]
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            booted = self._shell("getprop sys.boot_completed").stdout.strip()
            if booted == "1":
                break
            time.sleep(2)
        else:
            self.problem = f"{self.serial} did not finish booting"
            self.serial = None
            return False
        self.abis = self._shell("getprop ro.product.cpu.abilist").stdout.strip().split(",")
        # an emulator translating ARM (native bridge) runs those programs in a namespace of its own, which takes no
        # LD_LIBRARY_PATH: the ABIs of its own processor alone run, the translated ones only link
        if self._shell("getprop ro.dalvik.vm.native.bridge").stdout.strip() not in ("", "0"):
            family = "x86" if self.abis and self.abis[0].startswith("x86") else "arm"
            self.abis = [a for a in self.abis if a.startswith("x86") == (family == "x86")]
        return True

    def _devices(self) -> list[str]:
        listed = subprocess.run([self.adb(), "devices"], stdout=subprocess.PIPE, text=True).stdout.splitlines()[1:]
        serials = [line.split()[0] for line in listed if line.strip().endswith("device")]
        if self.wanted:
            return [s for s in serials if s == self.wanted]
        return [s for s in serials if s.startswith("emulator-")]

    def _shell(self, command: str) -> subprocess.CompletedProcess:
        return subprocess.run([self.adb(), "-s", self.serial, "shell", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace")

    def run(self, tools: Tools, program: Path, libraries: list[Path], arguments: list, log: Path) -> subprocess.CompletedProcess:
        """The program and the shared objects it loads in one directory, as an app's are in its native library
        directory, run from there."""
        remote = "/data/local/tmp/otok-examples"
        tools.run([self.adb(), "-s", self.serial, "shell", f"rm -rf {remote} && mkdir -p {remote}"], ROOT, log)
        for f in [program, *libraries]:
            tools.run([self.adb(), "-s", self.serial, "push", f, f"{remote}/{f.name}"], ROOT, log)
        command = f"cd {remote} && chmod 755 {program.name} && LD_LIBRARY_PATH={remote} ./{program.name}"
        command += "".join(" " + shlex_quote(a) for a in arguments)
        return tools.run([self.adb(), "-s", self.serial, "shell", command], ROOT, log)

    def stop(self) -> None:
        if self.started:
            subprocess.run([self.adb(), "-s", self.serial or "emulator-5554", "emu", "kill"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                self.started.wait(60)
            except subprocess.TimeoutExpired:
                self.started.kill()


def shlex_quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def find_android_sdk() -> Path | None:
    for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(name):
            return Path(os.environ[name])
    for candidate in (Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk", Path.home() / "Library" / "Android" / "sdk",
                      Path.home() / "Android" / "Sdk"):
        if candidate.is_dir():
            return candidate
    return None


def check_android(tools: Tools, base: Path, source: Path, provider: str, output: Path, table: dict, configurations: list,
                  arguments: list, expect: str, linkage: str, log: Path, record) -> None:
    """The NDK's toolchain file per ABI and configuration with Ninja; the ABIs of the device (an emulator) run there."""
    ndk = Path((table.get("toolchain") or {}).get("ndk", ""))
    toolchain = ndk / "build" / "cmake" / "android.toolchain.cmake"
    api = table.get("deployment", {}).get("android", "24")
    device = tools.android
    runs_on = device.abis if device.prepare(log) else []
    for abi in table["architectures"].get("android", []):
        for c in configurations:
            key = f"{abi}/{c}"
            runnable = abi in runs_on
            build = base / f"{abi}-{c}"
            shutil.rmtree(build, ignore_errors=True)
            configure = [tools.cmake, "-S", source, "-B", build, "-G", "Ninja", f"-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES={provider}",
                         f"-DCMAKE_TOOLCHAIN_FILE={toolchain.as_posix()}", f"-DANDROID_ABI={abi}", f"-DANDROID_PLATFORM=android-{api}",
                         f"-DCMAKE_BUILD_TYPE={c.capitalize()}"]
            if linkage == "dynamic":
                configure.append("-DANDROID_STL=c++_shared")  # what dynamic libraries of stl = "shared" need (otok-toml.md 4.7)
            if tools.run(configure, source, log).returncode != 0:
                record(key, "ran" if runnable else "linked", "installed")
                continue
            if tools.run([tools.cmake, "--build", build], source, log).returncode != 0:
                record(key, "ran" if runnable else "linked", "configured")
                continue
            if not runnable:
                record(key, "linked", "linked")
                continue
            lib = "debug/lib" if c == "debug" else "lib"
            libraries = sorted(output.glob(f"*/{lib}/{abi}/*.so"))
            if linkage == "dynamic":
                libraries += sorted(ndk.glob(f"toolchains/llvm/prebuilt/*/sysroot/usr/lib/{NDK_TRIPLES[abi]}/libc++_shared.so"))[:1]
            result = device.run(tools, build / "example", libraries, arguments, log)
            last = result.stdout.strip().splitlines()[-1:] if result.stdout.strip() else []
            record(key, "ran", "ran" if result.returncode == 0 and last == [expect] else "linked")


# --- main -----------------------------------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cases", nargs="*", metavar="LIBRARY[/CASE]", help="the cases to check (default: all)")
    parser.add_argument("--target", action="append", choices=TARGETS, help="only this target (repeatable)")
    parser.add_argument("--linkage", action="append", choices=["static", "dynamic"], help="only this linkage (repeatable)")
    parser.add_argument("--index", help="read the index from this checkout of otok-dev/index or view (OTOK_INDEX_MIRROR)")
    parser.add_argument("--otok", help="the otok program (default: otok of PATH)")
    parser.add_argument("--cmake", help="the cmake program (default: cmake of PATH, or Visual Studio's on Windows)")
    parser.add_argument("--generator", help="CMake generator of the consumers (default: CMake's)")
    parser.add_argument("--work", default=str(ROOT / "build"), help="where the projects are copied to (default: build/)")
    parser.add_argument("--status", help="directory of the locks of passing runs (the branch 'status')")
    parser.add_argument("--changed", action="store_true", help="with --status: skip runs whose lock is that of their last passing run")
    parser.add_argument("--json", help="write the results to this file")
    parser.add_argument("--android-sdk", help="the Android SDK, for adb and the emulator (default: ANDROID_HOME, ANDROID_SDK_ROOT or its usual place)")
    parser.add_argument("--avd", help="the emulator to start when adb sees no device (default: the last of emulator -list-avds)")
    parser.add_argument("--device", help="run on this device of adb (a phone on USB) instead of an emulator")
    parser.add_argument("--recipe", action="append", default=[], metavar="LIBRARY=DIR",
                        help="build LIBRARY with the recipe in DIR, where {target} stands for the target (a fix not yet published)")
    args = parser.parse_args()
    if args.changed and not args.status:
        parser.error("--changed needs --status")
    local_recipes = {}
    for item in args.recipe:
        library, _, directory = item.partition("=")
        if not directory:
            parser.error(f"--recipe {item}: LIBRARY=DIR expected")
        if "{target}" in directory:
            # one target per run then: the recipe of each target is its own directory
            if not args.target or len(args.target) != 1:
                parser.error(f"--recipe {item}: {{target}} needs exactly one --target")
            directory = directory.replace("{target}", args.target[0])
        local_recipes[library] = directory

    global ONLY_TARGETS
    ONLY_TARGETS = set(args.target or [])
    tools = Tools(args)
    work = Path(args.work).resolve()
    status_dir = Path(args.status).resolve() if args.status else None
    targets = args.target or TARGETS
    cases = load_cases(args.cases)
    if not cases:
        print("no case matches", file=sys.stderr)
        return 2

    runs: list[Run] = []
    for case in cases:
        if ONLY_TARGETS and not ONLY_TARGETS & set(case.tables()):
            continue  # none of the case's targets is checked
        for linkage in case.linkages():
            if linkage and args.linkage and linkage not in args.linkage:
                continue
            print(f"{case.id} {linkage or 'as written'} ...", flush=True)
            for run in check_case(tools, case, linkage, targets, work, status_dir, args.changed, local_recipes):
                runs.append(run)
                detail = " ".join(f"{c}:{level}" for c, level in run.configurations.items())
                print(f"  {run.target or '-'}: {run.status} ({run.level}) {detail} {run.message} [{run.seconds}s]".rstrip(), flush=True)
                if run.status == "failed":
                    print(f"  log: {run.log}", flush=True)

    tools.android.stop()
    if args.json:
        Path(args.json).write_text(json.dumps([dataclasses.asdict(r) for r in runs], indent=2) + "\n", encoding="utf-8")
    counts = {s: sum(1 for r in runs if r.status == s) for s in ("passed", "failed", "unsupported", "unchanged", "skipped")}
    print(", ".join(f"{n} {s}" for s, n in counts.items() if n) or "nothing to check")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
