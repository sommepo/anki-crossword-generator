"""Build a clean, installable .ankiaddon archive from the source package."""

from __future__ import annotations

from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "anki_jp_crossword_generator"
DIST = ROOT / "dist"


def version() -> str:
    namespace: dict[str, str] = {}
    exec((PACKAGE / "version.py").read_text(encoding="utf-8"), namespace)
    return namespace["ADDON_VERSION"]


def main() -> None:
    if not PACKAGE.is_dir():
        raise SystemExit("Could not find the add-on package directory.")
    DIST.mkdir(exist_ok=True)
    output = DIST / f"anki-crossword-generator-{version()}.ankiaddon"
    temporary = output.with_suffix(".zip")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in PACKAGE.rglob("*"):
            if not source.is_file() or "__pycache__" in source.parts:
                continue
            archive.write(source, source.relative_to(PACKAGE))
    if output.exists():
        output.unlink()
    shutil.move(str(temporary), str(output))
    print(output)


if __name__ == "__main__":
    main()
