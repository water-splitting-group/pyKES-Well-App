"""Generate deploy/files.js from the app source tree.

Reads the Streamlit entrypoint, pages, and importable `pykes_well_app` package
modules and emits a JS module exporting them as a mapping from virtual-FS paths
to file contents, alongside the requirement list stlite installs in the browser.
Both exports are consumed by deploy/index.html when stlite mounts the app.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PKG = REPO_ROOT / "src" / "pykes_well_app"
STREAMLIT_APP = SRC_PKG / "streamlit_app"
PYPROJECT = REPO_ROOT / "pyproject.toml"
LOCK_FILE = REPO_ROOT / "uv.lock"
OUTPUT = Path(__file__).resolve().parent / "files.js"

# -----------------------------------------------------------------------------
# Version pinning for the browser runtime
# -----------------------------------------------------------------------------

# micropip fetches these from PyPI at page load, so the app must request exactly
# the version it was developed against - the one uv.lock resolves. A pin that
# lags the source raises ModuleNotFoundError for modules added since.
PINNED_PACKAGES = ("pykes",)

# Everything else (numpy, pandas, scipy) ships with pyodide: requested by bare
# name, the bundled build is used instead of a second copy from PyPI.

# Start of a PEP 508 version specifier, extra, or environment marker; the
# distribution name is whatever precedes it.
DEPENDENCY_NAME_PATTERN = re.compile(r"[\s<>=!~\[;(]")


def collect_files() -> dict[str, str]:
    files: dict[str, str] = {}

    files["Home.py"] = (STREAMLIT_APP / "Home.py").read_text()

    for page in sorted((STREAMLIT_APP / "pages").glob("*.py")):
        if page.name == "__init__.py":
            continue
        files[f"pages/{page.name}"] = page.read_text()

    for module in sorted(SRC_PKG.rglob("*.py")):
        rel = module.relative_to(SRC_PKG.parent)
        if rel.parts[1] == "streamlit_app":
            continue
        files[str(rel)] = module.read_text()

    return files


def read_dependency_names() -> list[str]:
    """Read the distribution names declared in `[project].dependencies`.

    Returns
    -------
    list of str
        Dependency names in declaration order, specifiers stripped.
    """
    dependencies = tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]

    return [DEPENDENCY_NAME_PATTERN.split(dependency, maxsplit=1)[0] for dependency in dependencies]


def read_locked_version(package_name: str) -> str:
    """Read the version `uv.lock` resolves for a package.

    Parameters
    ----------
    package_name : str
        Distribution name as it appears in the lock file.

    Returns
    -------
    str
        The single resolved version.
    """
    locked_packages = tomllib.loads(LOCK_FILE.read_text())["package"]
    versions = {entry["version"] for entry in locked_packages if entry["name"] == package_name}

    # Environment-dependent resolutions (one entry per Python-version marker)
    # would make the pin ambiguous, so require a unique version.
    if len(versions) != 1:
        raise ValueError(
            f"{package_name} resolves to {sorted(versions)} in {LOCK_FILE.name}, expected exactly one version"
        )

    return versions.pop()


def collect_requirements() -> list[str]:
    """Build the stlite requirement list from the project's dependencies.

    Returns
    -------
    list of str
        Requirement strings, pinned to the locked version for
        `PINNED_PACKAGES` and bare names otherwise.
    """
    return [
        f"{name}=={read_locked_version(name)}" if name in PINNED_PACKAGES else name
        for name in read_dependency_names()
    ]


def main() -> None:
    files = collect_files()
    requirements = collect_requirements()

    OUTPUT.write_text(
        f"export const files = {json.dumps(files, indent=2, ensure_ascii=False)};\n\n"
        f"export const requirements = {json.dumps(requirements, indent=2)};\n"
    )
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)} with {len(files)} files, requirements: {requirements}")


if __name__ == "__main__":
    main()
