from __future__ import annotations

import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
OUT = ROOT / "mineverse_dist.zip"


def add_dir(zf: zipfile.ZipFile, src: Path, arc_root: str) -> None:
    for p in src.rglob("*"):
        if p.is_file():
            arcname = Path(arc_root) / p.relative_to(src)
            zf.write(p, arcname.as_posix())


def main():
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # three top-level scripts
        for name in ("config.py", "train.py", "start_bot.py"):
            p = ROOT / name
            if p.exists():
                zf.write(p, name)
        # include python-backend under backend/
        pb = ROOT / "python-backend"
        if pb.exists():
            add_dir(zf, pb, "backend/python-backend")
        # include lib-node and bin so CLI can be distributed
        for name in ("lib-node", "bin"):
            p = ROOT / name
            if p.exists():
                add_dir(zf, p, f"backend/{name}")
        # include package.json
        pj = ROOT / "package.json"
        if pj.exists():
            zf.write(pj, "backend/package.json")

    print(f"Created distribution archive: {OUT}")


if __name__ == "__main__":
    main()
