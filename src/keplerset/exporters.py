from __future__ import annotations

import re
from pathlib import Path

from .models import ElementSetProfile
from .paths import atomic_write_bytes


def _alias_map(profile: ElementSetProfile) -> dict[int, str]:
    return {
        s.norad_cat_id: s.alias.strip()
        for s in profile.satellites
        if s.alias.strip()
    }


def apply_3le_aliases(text: str, profile: ElementSetProfile) -> str:
    """Replace 3LE line 0 names while preserving Space-Track line 1/2 verbatim.

    A 3LE stream is interpreted as triples: line 0, line 1, line 2. The NORAD
    ID is taken from line 1. Alpha-5 catalog numbers are decoded so aliases
    also work for the expanded catalog.
    """
    if not profile.apply_aliases:
        return text
    aliases = _alias_map(profile)
    if not aliases:
        return text

    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        if i + 2 < len(lines) and lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            line0, line1, line2 = lines[i], lines[i + 1], lines[i + 2]
            cat = decode_tle_catalog_field(line1[2:7])
            alias = aliases.get(cat)
            out.extend([alias[:24] if alias else line0, line1, line2])
            i += 3
        else:
            out.append(lines[i])
            i += 1
    suffix = "\r\n" if text.endswith(("\n", "\r")) else ""
    return "\r\n".join(out) + suffix


_ALPHA5_PREFIX = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def decode_tle_catalog_field(field: str) -> int:
    value = field.strip().upper()
    if not value:
        raise ValueError("Empty TLE catalog field")
    if value[0].isdigit():
        return int(value)
    prefix = value[0]
    if prefix not in _ALPHA5_PREFIX:
        raise ValueError(f"Invalid Alpha-5 prefix: {prefix}")
    prefix_value = 10 + _ALPHA5_PREFIX.index(prefix)
    return prefix_value * 10_000 + int(value[1:])


def write_native_result(profile: ElementSetProfile, data: bytes, output_path: Path) -> None:
    if profile.format == "3le" and profile.apply_aliases:
        text = data.decode("utf-8-sig", errors="replace")
        text = apply_3le_aliases(text, profile)
        atomic_write_bytes(output_path, text.encode("utf-8"))
    else:
        atomic_write_bytes(output_path, data)


def parse_satellite_list(text: str) -> list[tuple[int, str]]:
    """Parse pasted HalloKepler-style list data.

    Accepted lines include:
      25544 ISS
      25544,ISS
      25544;ISS
      25544\tISS
    Blank lines and lines beginning with # are ignored.
    """
    rows: list[tuple[int, str]] = []
    seen: set[int] = set()
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(\d{1,9})(?:\s*[,;\t]\s*|\s+)?(.*)$", line)
        if not match:
            raise ValueError(f"Line {lineno}: expected a numeric NORAD ID followed by an optional alias.")
        cat = int(match.group(1))
        alias = match.group(2).strip()
        if cat <= 0 or cat > 999_999_999:
            raise ValueError(f"Line {lineno}: NORAD ID out of range: {cat}")
        if cat in seen:
            raise ValueError(f"Line {lineno}: duplicate NORAD ID: {cat}")
        seen.add(cat)
        rows.append((cat, alias))
    return rows
