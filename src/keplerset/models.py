from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_FORMATS: dict[str, str] = {
    "tle": "TLE (2-line, Space-Track native)",
    "3le": "3LE (name + 2-line, Space-Track native)",
    "xml": "CCSDS OMM XML",
    "kvn": "CCSDS OMM KVN",
    "json": "JSON",
    "csv": "CSV",
    "html": "HTML",
}

DEFAULT_EXTENSIONS: dict[str, str] = {
    "tle": ".tle",
    "3le": ".txt",
    "xml": ".xml",
    "kvn": ".kvn",
    "json": ".json",
    "csv": ".csv",
    "html": ".html",
}


@dataclass(slots=True)
class SatelliteEntry:
    norad_cat_id: int
    alias: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SatelliteEntry":
        return cls(
            norad_cat_id=int(value["norad_cat_id"]),
            alias=str(value.get("alias", "")).strip(),
        )


@dataclass(slots=True)
class ElementSetProfile:
    name: str = "New Set"
    format: str = "3le"
    output_path: str = "elements.txt"
    satellites: list[SatelliteEntry] = field(default_factory=list)
    apply_aliases: bool = True
    order_by: str = "NORAD_CAT_ID asc"
    empty_result_show: bool = True

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Profile name cannot be empty.")
        if self.format not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {self.format}")
        if not self.satellites:
            raise ValueError("The element set has no satellites.")
        seen: set[int] = set()
        for sat in self.satellites:
            if sat.norad_cat_id <= 0 or sat.norad_cat_id > 999_999_999:
                raise ValueError(f"Invalid NORAD catalog ID: {sat.norad_cat_id}")
            if self.format in {"tle", "3le"} and sat.norad_cat_id > 339_999:
                raise ValueError(
                    f"NORAD {sat.norad_cat_id} cannot be represented by legacy TLE/3LE. "
                    "Choose XML, KVN, JSON, CSV, or HTML for expanded catalog IDs above 339999."
                )
            if sat.norad_cat_id in seen:
                raise ValueError(f"Duplicate NORAD catalog ID: {sat.norad_cat_id}")
            seen.add(sat.norad_cat_id)

    def normalized_output_path(self, base_dir: Path | None = None) -> Path:
        path = Path(self.output_path).expanduser()
        if not path.suffix:
            path = path.with_suffix(DEFAULT_EXTENSIONS[self.format])
        if not path.is_absolute() and base_dir is not None:
            path = base_dir / path
        return path

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "format": self.format,
            "output_path": self.output_path,
            "satellites": [asdict(s) for s in self.satellites],
            "apply_aliases": self.apply_aliases,
            "order_by": self.order_by,
            "empty_result_show": self.empty_result_show,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ElementSetProfile":
        return cls(
            name=str(value.get("name", "New Set")),
            format=str(value.get("format", "3le")),
            output_path=str(value.get("output_path", "elements.txt")),
            satellites=[SatelliteEntry.from_dict(x) for x in value.get("satellites", [])],
            apply_aliases=bool(value.get("apply_aliases", True)),
            order_by=str(value.get("order_by", "NORAD_CAT_ID asc")),
            empty_result_show=bool(value.get("empty_result_show", True)),
        )
