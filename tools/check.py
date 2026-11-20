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
CONSUMED = {"windows", "linux", "apple"}  # targets whose consumers the driver builds so far (README.md, "Status")
PROFILE = "otok-examples"


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


def project_manifest(case: Case, linkage: str | None, local_recipes: dict[str, str]) -> str:
    """otok.toml of the case as it is, with what the run adds after it: the profile of the linkage and the recipes of
    --recipe."""
    text = case.text if case.text.endswith("\n") else case.text + "\n"
    added = []
    for library, directory in local_recipes.items():
        recipe = "{ path = " + toml_string(Path(directory).resolve().as_posix()) + " }"
        deps = case.manifest.get("deps", {})
        if library in deps:
            # the line of its recipe in the case's own table, which a profile cannot change (otok-toml.md 8)
            pattern = re.compile(r"(\[deps\." + re.escape(library) + r"\][^\[]*?)^recipe\s*=.*$\n(?:^version\s*=.*$\n)?", re.M | re.S)
            text, n = pattern.subn(lambda m: m.group(1) + f"recipe = {recipe}\n", text, count=1)
            if n != 1:
                sys.exit(f"{case.id}: cannot replace the recipe of [deps.{library}] in otok.toml for --recipe")
        else:
            added.append(f"[deps.{library}]\nrecipe = {recipe}\n")
    if linkage:
        added.append(f"[profile.{PROFILE}]\n" + "".join(f"{t} = {{ linkage = {toml_string(linkage)} }}\n" for t in case.tables()))
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
    write_if_changed(project / "otok.toml", project_manifest(case, linkage, local_recipes))
    profile = ["--profile", PROFILE] if linkage else []

    def whole(status: str, level: str, message: str) -> list[Run]:
        return [Run(case.id, label, "", level, status, {}, message, str(log), round(time.monotonic() - started, 1))]

    # resolve: the lock, compared with that of the last passing run
    resolved = tools.run([tools.otok, "update", "--no-build", *profile], project, log)
    if resolved.returncode != 0:
        refused = re.search(r"cannot be built as (static|dynamic) libraries", resolved.stdout)
        if refused and f"[deps.{case.library}]" in resolved.stdout:
            return whole("unsupported", "failed", f"the recipe of {case.library} builds no {refused.group(1)} libraries for a target of the case")
        return whole("failed", "failed", "otok update --no-build failed")
    lock = (project / "otok.lock").read_text(encoding="utf-8")
    stored = status_dir / "locks" / case.library / case.name / f"{label}.lock" if status_dir else None
    if changed_only and stored and stored.exists() and stored.read_text(encoding="utf-8") == lock:
        return whole("unchanged", "resolved", "otok.lock is that of the last passing run")

    installed = tools.run([tools.otok, "install", *profile], project, log)
    if installed.returncode != 0:
        return whole("failed", "resolved", "otok install failed")
    skipped = dict(re.findall(r"^note: not building for '([^']+)': (.*)$", installed.stdout, re.M))
    # the target tables as otok reads them, the profile applied: output, platforms, architectures, configurations
    metadata = subprocess.run([tools.otok, "metadata", *profile], cwd=project, env=tools.env, stdout=subprocess.PIPE, text=True,
                              encoding="utf-8", errors="replace")
    tables = {t["name"]: t for t in json.loads(metadata.stdout)["targets"]} if metadata.returncode == 0 else {}

    runs = []
    for target in case.tables():
        if target not in targets:
            continue
        run = Run(case.id, label, target, "installed", "failed", log=str(log))
        runs.append(run)
        if target in skipped:
            run.status, run.message = "skipped", skipped[target]
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
    if stored and runs and all(r.status in ("passed", "skipped") for r in runs) and any(r.status == "passed" for r in runs):
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_text(lock, encoding="utf-8", newline="\n")
    return runs or whole("skipped", "installed", "none of the case's target tables is one this machine builds")


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

    if args.json:
        Path(args.json).write_text(json.dumps([dataclasses.asdict(r) for r in runs], indent=2) + "\n", encoding="utf-8")
    counts = {s: sum(1 for r in runs if r.status == s) for s in ("passed", "failed", "unsupported", "unchanged", "skipped")}
    print(", ".join(f"{n} {s}" for s, n in counts.items() if n) or "nothing to check")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
