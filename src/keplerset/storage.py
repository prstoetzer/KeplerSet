from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ElementSetProfile
from .satcat import SatcatRecord

APP_DIR_NAME = "KeplerSet"
SETTINGS_FILE_NAME = "settings.json"
PROFILES_FILE_NAME = "profiles.json"
SATCAT_CACHE_FILE_NAME = "satcat-cache.json"


def app_data_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("APPDATA")
        if root:
            return Path(root) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / APP_DIR_NAME
    return Path.home() / ".config" / APP_DIR_NAME


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_settings() -> dict[str, Any]:
    return _read_json(app_data_dir() / SETTINGS_FILE_NAME, {})


def save_settings(settings: dict[str, Any]) -> None:
    # Deliberately never persist a Space-Track password.
    settings = dict(settings)
    settings.pop("password", None)
    _write_json(app_data_dir() / SETTINGS_FILE_NAME, settings)


def load_profiles() -> list[ElementSetProfile]:
    raw = _read_json(app_data_dir() / PROFILES_FILE_NAME, [])
    if not isinstance(raw, list):
        return []
    profiles: list[ElementSetProfile] = []
    for item in raw:
        if isinstance(item, dict):
            try:
                profiles.append(ElementSetProfile.from_dict(item))
            except (TypeError, ValueError, KeyError):
                continue
    return profiles


def save_profiles(profiles: list[ElementSetProfile]) -> None:
    _write_json(app_data_dir() / PROFILES_FILE_NAME, [p.to_dict() for p in profiles])


def load_satcat_cache() -> tuple[list[SatcatRecord], dict[str, Any]]:
    raw = _read_json(app_data_dir() / SATCAT_CACHE_FILE_NAME, {})
    if not isinstance(raw, dict):
        return [], {}
    records: list[SatcatRecord] = []
    for item in raw.get("records", []):
        if isinstance(item, dict):
            try:
                records.append(SatcatRecord.from_dict(item))
            except (TypeError, ValueError, KeyError):
                continue
    metadata = {
        "fetched_at": str(raw.get("fetched_at", "")),
        "source_url": str(raw.get("source_url", "")),
        "record_count": len(records),
    }
    return records, metadata


def save_satcat_cache(records: list[SatcatRecord], source_url: str) -> None:
    _write_json(
        app_data_dir() / SATCAT_CACHE_FILE_NAME,
        {
            "schema": 1,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_url": source_url,
            "records": [record.to_dict() for record in records],
        },
    )
