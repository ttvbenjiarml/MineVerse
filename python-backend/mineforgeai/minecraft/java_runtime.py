from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class JavaInstallation:
    executable: str
    major: int
    raw_version: str
    source: str


@dataclass(slots=True)
class JavaCompatibility:
    requested_version: str
    effective_version: str
    required_major: int
    selected_major: int | None
    supported: bool
    auto_adjusted: bool
    message: str


VERSION_PATTERN = re.compile(r'"(?P<version>\d+(?:\.\d+){0,2})')

PLATFORM_TARGETS: dict[str, list[tuple[str, int]]] = {
    "paper": [("1.21.1", 21), ("1.20.6", 17), ("1.16.5", 8)],
    "fabric": [("1.20.1", 17), ("1.16.5", 8)],
}

FABRIC_VERSION_DATA: dict[str, dict[str, str]] = {
    "1.20.1": {
        "yarn_mappings": "1.20.1+build.10",
        "loader_version": "0.15.11",
        "fabric_version": "0.92.2+1.20.1",
    },
    "1.16.5": {
        "yarn_mappings": "1.16.5+build.10",
        "loader_version": "0.16.10",
        "fabric_version": "0.42.0+1.16",
    },
}


def _java_executable_name() -> str:
    return "java.exe" if os.name == "nt" else "java"


def _candidate_jdk_homes() -> list[tuple[Path, str]]:
    homes: list[tuple[Path, str]] = []

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        homes.append((Path(java_home), "JAVA_HOME"))

    for key, value in os.environ.items():
        if key.startswith("JAVA_HOME_") and value:
            homes.append((Path(value), key))

    system = platform.system()
    if os.name == "nt":
        roots = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Java",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Eclipse Adoptium",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Zulu",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "BellSoft",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "GraalVM",
            Path(os.environ.get("ProgramW6432", r"C:\Program Files")) / "Java",
        ]
    elif system == "Darwin":
        roots = [Path("/Library/Java/JavaVirtualMachines"), Path.home() / "Library" / "Java" / "JavaVirtualMachines"]
    else:
        roots = [Path("/usr/lib/jvm"), Path("/usr/java"), Path.home() / ".sdkman" / "candidates" / "java"]

    for root in roots:
        if not root.exists():
            continue
        for child in root.iterdir():
            if os.name == "nt":
                homes.append((child, str(root)))
            elif system == "Darwin":
                homes.append((child / "Contents" / "Home", str(root)))
            else:
                homes.append((child, str(root)))

    return homes


def _parse_java_major(version_output: str) -> tuple[int, str] | None:
    match = VERSION_PATTERN.search(version_output)
    if not match:
        return None
    raw = match.group("version")
    if raw.startswith("1."):
        major = int(raw.split(".")[1])
    else:
        major = int(raw.split(".")[0])
    return major, raw


def _probe_java(executable: str, source: str) -> JavaInstallation | None:
    try:
        result = subprocess.run([executable, "-version"], capture_output=True, text=True, check=False)
    except OSError:
        return None
    version_output = (result.stderr or result.stdout or "").strip()
    parsed = _parse_java_major(version_output)
    if not parsed:
        return None
    major, raw = parsed
    return JavaInstallation(executable=executable, major=major, raw_version=raw, source=source)


def detect_java_installations() -> list[JavaInstallation]:
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    path_java = shutil.which("java")
    if path_java:
        candidates.append((path_java, "PATH"))

    for home, source in _candidate_jdk_homes():
        candidates.append((str(home / "bin" / _java_executable_name()), source))

    installations: list[JavaInstallation] = []
    for executable, source in candidates:
        normalized = os.path.normcase(executable)
        if normalized in seen:
            continue
        seen.add(normalized)
        installation = _probe_java(executable, source)
        if installation is not None:
            installations.append(installation)

    unique: dict[tuple[int, str], JavaInstallation] = {}
    for item in installations:
        unique[(item.major, item.executable)] = item
    return sorted(unique.values(), key=lambda item: (item.major, item.executable))


def highest_java_major(installations: list[JavaInstallation] | None = None) -> int | None:
    installations = installations if installations is not None else detect_java_installations()
    if not installations:
        return None
    return max(item.major for item in installations)


def targets_for_platform(platform: str) -> list[tuple[str, int]]:
    return PLATFORM_TARGETS.get(platform, [("1.20.1", 17)])


def default_version_for(platform: str, installations: list[JavaInstallation] | None = None) -> str:
    highest = highest_java_major(installations)
    targets = targets_for_platform(platform)
    if highest is None:
        return targets[0][0]
    for version, required_major in targets:
        if highest >= required_major:
            return version
    return targets[-1][0]


def required_java_for(platform: str, version: str) -> int:
    for candidate_version, required_major in targets_for_platform(platform):
        if candidate_version == version:
            return required_major
    return targets_for_platform(platform)[0][1]


def select_java_compatibility(platform: str, version: str | None, installations: list[JavaInstallation] | None = None) -> JavaCompatibility:
    installations = installations if installations is not None else detect_java_installations()
    highest = highest_java_major(installations)
    targets = targets_for_platform(platform)
    requested_version = version or default_version_for(platform, installations)
    required = required_java_for(platform, requested_version)

    if highest is not None and highest >= required:
        return JavaCompatibility(
            requested_version=requested_version,
            effective_version=requested_version,
            required_major=required,
            selected_major=highest,
            supported=True,
            auto_adjusted=False,
            message=f"Detected Java {highest}. {platform.title()} {requested_version} requires Java {required}+ and can build with the current installation.",
        )

    fallback = None
    if highest is not None:
        for candidate_version, candidate_required in targets:
            if highest >= candidate_required:
                fallback = (candidate_version, candidate_required)
                break

    if fallback is not None:
        effective_version, effective_required = fallback
        return JavaCompatibility(
            requested_version=requested_version,
            effective_version=effective_version,
            required_major=effective_required,
            selected_major=highest,
            supported=True,
            auto_adjusted=effective_version != requested_version,
            message=(
                f"Detected Java {highest}. Requested {platform.title()} {requested_version} needs Java {required}+, "
                f"so MineForgeAI selected compatible target {effective_version} for Java {effective_required}+ instead."
            ) if effective_version != requested_version else f"Detected Java {highest}. {platform.title()} {effective_version} is compatible with the current installation.",
        )

    minimum_version, minimum_required = targets[-1]
    if highest is not None:
        return JavaCompatibility(
            requested_version=requested_version,
            effective_version=minimum_version,
            required_major=minimum_required,
            selected_major=highest,
            supported=False,
            auto_adjusted=minimum_version != requested_version,
            message=(
                f"Detected Java {highest}, but even the oldest built-in {platform.title()} target {minimum_version} needs Java {minimum_required}+. "
                f"Install a newer JDK to build generated {platform.title()} projects."
            ),
        )

    return JavaCompatibility(
        requested_version=requested_version,
        effective_version=minimum_version if version is None else requested_version,
        required_major=minimum_required if version is None else required,
        selected_major=None,
        supported=False,
        auto_adjusted=version is None,
        message=f"No Java runtime was detected. Install Java {minimum_required}+ for {platform.title()} support.",
    )


def fabric_version_data(version: str) -> dict[str, str]:
    return FABRIC_VERSION_DATA.get(version, FABRIC_VERSION_DATA["1.20.1"])


def installed_java_summary(installations: list[JavaInstallation] | None = None) -> str:
    installations = installations if installations is not None else detect_java_installations()
    if not installations:
        return "none detected"
    return ", ".join(f"Java {item.major} ({item.source})" for item in installations)
