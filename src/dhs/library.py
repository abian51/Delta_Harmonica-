from __future__ import annotations

import json
import os
from pathlib import Path
import re


def data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DeltaHarmonicaStudio"
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_song(name: str, settings: dict) -> Path:
    library = data_dir() / "library"
    library.mkdir(exist_ok=True)
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not safe_name:
        raise ValueError("song name is empty")
    path = library / f"{safe_name}.json"
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_songs() -> list[dict]:
    library = data_dir() / "library"
    library.mkdir(exist_ok=True)
    songs = []
    for path in sorted(library.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_record_path"] = str(path)
            songs.append(data)
        except (OSError, ValueError, TypeError):
            continue
    return songs


def delete_song(record_path: str | Path) -> None:
    target = Path(record_path).resolve()
    library = (data_dir() / "library").resolve()
    if target.parent != library or target.suffix.lower() != ".json":
        raise ValueError("record is outside the song library")
    target.unlink(missing_ok=True)
