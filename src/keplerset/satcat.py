from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(slots=True)
class SatcatRecord:
    norad_cat_id: int
    object_name: str = ""
    object_id: str = ""
    object_type: str = ""
    country: str = ""
    launch: str = ""
    decay: str = ""
    period: float | None = None
    inclination: float | None = None
    apogee: int | None = None
    perigee: int | None = None
    current: str = "Y"

    @property
    def on_orbit(self) -> bool:
        return not self.decay.strip()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_api(cls, value: dict[str, Any]) -> "SatcatRecord":
        cat_raw = value.get("NORAD_CAT_ID", value.get("OBJECT_NUMBER"))
        if cat_raw in (None, ""):
            raise ValueError("SATCAT record is missing NORAD_CAT_ID")
        return cls(
            norad_cat_id=int(cat_raw),
            object_name=str(value.get("OBJECT_NAME") or value.get("SATNAME") or "").strip(),
            object_id=str(value.get("OBJECT_ID") or value.get("INTLDES") or "").strip(),
            object_type=str(value.get("OBJECT_TYPE") or "").strip(),
            country=str(value.get("COUNTRY") or "").strip(),
            launch=str(value.get("LAUNCH") or "").strip(),
            decay=str(value.get("DECAY") or "").strip(),
            period=_optional_float(value.get("PERIOD")),
            inclination=_optional_float(value.get("INCLINATION")),
            apogee=_optional_int(value.get("APOGEE")),
            perigee=_optional_int(value.get("PERIGEE")),
            current=str(value.get("CURRENT") or "Y").strip().upper(),
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SatcatRecord":
        return cls(
            norad_cat_id=int(value["norad_cat_id"]),
            object_name=str(value.get("object_name", "")),
            object_id=str(value.get("object_id", "")),
            object_type=str(value.get("object_type", "")),
            country=str(value.get("country", "")),
            launch=str(value.get("launch", "")),
            decay=str(value.get("decay", "")),
            period=_optional_float(value.get("period")),
            inclination=_optional_float(value.get("inclination")),
            apogee=_optional_int(value.get("apogee")),
            perigee=_optional_int(value.get("perigee")),
            current=str(value.get("current", "Y")),
        )


@dataclass(slots=True)
class SatcatSearch:
    text: str = ""
    object_type: str = ""
    country: str = ""
    on_orbit_only: bool = True
    launch_year_from: int | None = None
    launch_year_to: int | None = None
    inclination_min: float | None = None
    inclination_max: float | None = None
    period_min: float | None = None
    period_max: float | None = None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _launch_year(value: str) -> int | None:
    if len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


def search_satcat(
    records: Iterable[SatcatRecord],
    criteria: SatcatSearch,
    *,
    limit: int | None = 2000,
) -> list[SatcatRecord]:
    """Filter a cached SATCAT locally without issuing additional API queries."""
    text = criteria.text.strip().casefold()
    country = criteria.country.strip().casefold()
    object_type = criteria.object_type.strip().casefold()
    matches: list[SatcatRecord] = []

    for record in records:
        if criteria.on_orbit_only and not record.on_orbit:
            continue
        if object_type and object_type != "all" and record.object_type.casefold() != object_type:
            continue
        if country and country not in record.country.casefold():
            continue

        year = _launch_year(record.launch)
        if criteria.launch_year_from is not None and (year is None or year < criteria.launch_year_from):
            continue
        if criteria.launch_year_to is not None and (year is None or year > criteria.launch_year_to):
            continue

        if criteria.inclination_min is not None and (
            record.inclination is None or record.inclination < criteria.inclination_min
        ):
            continue
        if criteria.inclination_max is not None and (
            record.inclination is None or record.inclination > criteria.inclination_max
        ):
            continue
        if criteria.period_min is not None and (
            record.period is None or record.period < criteria.period_min
        ):
            continue
        if criteria.period_max is not None and (
            record.period is None or record.period > criteria.period_max
        ):
            continue

        if text:
            haystack = " ".join(
                (
                    str(record.norad_cat_id),
                    record.object_name,
                    record.object_id,
                    record.object_type,
                    record.country,
                )
            ).casefold()
            if text not in haystack:
                continue

        matches.append(record)

    # Numeric searches are most naturally catalog-number searches. Otherwise
    # present names alphabetically while using NORAD ID as a stable tiebreaker.
    if text.isdigit():
        needle = int(text)
        matches.sort(key=lambda r: (r.norad_cat_id != needle, r.norad_cat_id))
    else:
        matches.sort(key=lambda r: (r.object_name.casefold(), r.norad_cat_id))

    return matches if limit is None else matches[: max(0, limit)]
