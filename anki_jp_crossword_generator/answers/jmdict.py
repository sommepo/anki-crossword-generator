"""Local JMdict index and optional downloader for Native answer backfill.

Dictionary data is never bundled with the add-on.  A user explicitly requests
the one-time download from jmdict-simplified; later lookups are entirely local.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

GITHUB_API_LATEST = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"
USER_AGENT = "AnkiCrosswordGenerator/0.5"


class JmdictIndex:
    """In-memory index over an English-only jmdict-simplified JSON file."""

    def __init__(self) -> None:
        self.by_kanji: dict[str, list[dict[str, Any]]] = {}
        self.by_kana: dict[str, list[dict[str, Any]]] = {}
        self.word_count = 0

    @property
    def ready(self) -> bool:
        return self.word_count > 0

    def clear(self) -> None:
        self.by_kanji.clear()
        self.by_kana.clear()
        self.word_count = 0

    def load_json_file(self, path: Path) -> None:
        """Load a downloaded jmdict-simplified English JSON export."""
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        words = data.get("words") if isinstance(data, dict) else None
        if not isinstance(words, list):
            raise ValueError("Unrecognised JMdict JSON (missing words[])")
        self.clear()
        for entry in words:
            if not isinstance(entry, dict):
                continue
            for item in entry.get("kanji") or []:
                if isinstance(item, dict) and (text := str(item.get("text") or "").strip()):
                    self.by_kanji.setdefault(text, []).append(entry)
            for item in entry.get("kana") or []:
                if isinstance(item, dict) and (text := str(item.get("text") or "").strip()):
                    self.by_kana.setdefault(text, []).append(entry)
            self.word_count += 1

    def lookup_glosses(
        self,
        word: str,
        reading: str = "",
        *,
        max_glosses: int = 8,
        prefer_common: bool = False,
    ) -> str:
        """Return a comma-separated English gloss list for one Japanese word."""
        candidates = list(self.by_kanji.get((word or "").strip()) or [])
        if not candidates:
            candidates = list(self.by_kana.get((word or "").strip()) or [])
        if not candidates and reading:
            candidates = list(self.by_kana.get(reading.strip()) or [])
        if not candidates:
            return ""
        if reading:
            matched = [entry for entry in candidates if _has_reading(entry, reading)]
            if matched:
                candidates = matched
        if prefer_common:
            common = [entry for entry in candidates if _is_common(entry, word)]
            if common:
                candidates = common
        return ", ".join(_collect_glosses(candidates[0], max_glosses))


def data_dir(addon_dir: Path) -> Path:
    """Return the add-on's unbundled, user-managed dictionary directory."""
    path = addon_dir / "user_files"
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_local_json(addon_dir: Path) -> Path | None:
    """Find the most recent downloaded English JMdict JSON file."""
    matches = sorted(data_dir(addon_dir).glob("jmdict-eng*.json"))
    return matches[-1] if matches else None


def download_jmdict(addon_dir: Path, progress: Callable[[str], None] | None = None) -> Path:
    """Download and extract the current English JMdict JSON release."""
    if progress:
        progress("Finding the latest JMdict release…")
    request = Request(GITHUB_API_LATEST, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS source
        release = json.loads(response.read().decode("utf-8"))
    url = next(
        (
            str(asset["browser_download_url"])
            for asset in release.get("assets") or []
            if str(asset.get("name") or "").startswith("jmdict-eng-")
            and str(asset.get("name") or "").endswith(".json.zip")
            and "common" not in str(asset.get("name") or "")
            and "examples" not in str(asset.get("name") or "")
        ),
        "",
    )
    if not url:
        raise RuntimeError("Could not find the English JMdict JSON download")
    folder = data_dir(addon_dir)
    archive = folder / "jmdict-eng-download.zip"
    if progress:
        progress("Downloading JMdict (English)…")
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response, archive.open("wb") as output:  # noqa: S310
        while chunk := response.read(262_144):
            output.write(chunk)
    if progress:
        progress("Extracting dictionary…")
    try:
        with zipfile.ZipFile(archive) as zip_file:
            for name in zip_file.namelist():
                filename = Path(name).name
                if filename.startswith("jmdict-eng-") and filename.endswith(".json"):
                    result = folder / filename
                    with zip_file.open(name) as source, result.open("wb") as output:
                        output.write(source.read())
                    return result
    finally:
        archive.unlink(missing_ok=True)
    raise RuntimeError("The JMdict download did not contain an English JSON file")


def _has_reading(entry: dict[str, Any], reading: str) -> bool:
    return any(str(item.get("text") or "") == reading for item in entry.get("kana") or [] if isinstance(item, dict))


def _is_common(entry: dict[str, Any], word: str) -> bool:
    for key in ("kanji", "kana"):
        if any(str(item.get("text") or "") == word and item.get("common") for item in entry.get(key) or [] if isinstance(item, dict)):
            return True
    return False


def _collect_glosses(entry: dict[str, Any], maximum: int) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for sense in entry.get("sense") or []:
        if not isinstance(sense, dict):
            continue
        for gloss in sense.get("gloss") or []:
            text = str(gloss.get("text") or "").strip() if isinstance(gloss, dict) else str(gloss or "").strip()
            language = str(gloss.get("lang") or gloss.get("langCode") or "eng") if isinstance(gloss, dict) else "eng"
            if not text or language not in {"", "eng", "en"} or text.casefold() in seen:
                continue
            seen.add(text.casefold())
            output.append(text)
            if len(output) >= maximum:
                return output
    return output
