"""Generate deploy/files.js from the app source tree.

Reads the Streamlit entrypoint, pages, and importable `pykes_well_app` package
modules, and emits a JS module exporting them as a mapping from virtual-FS
paths to file contents. The mapping is consumed by deploy/index.html when
stlite mounts the app.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PKG = REPO_ROOT / "src" / "pykes_well_app"
STREAMLIT_APP = SRC_PKG / "streamlit_app"
OUTPUT = Path(__file__).resolve().parent / "files.js"


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


def main() -> None:
    files = collect_files()
    payload = json.dumps(files, indent=2, ensure_ascii=False)
    OUTPUT.write_text(f"export const files = {payload};\n")
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)} with {len(files)} files")


if __name__ == "__main__":
    main()
