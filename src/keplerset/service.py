from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .exporters import write_native_result
from .models import ElementSetProfile
from .paths import preflight_output_path
from .spacetrack import QueryResult, SpaceTrackClient


@dataclass(slots=True)
class ExportOutcome:
    output_path: Path
    bytes_written: int
    request_url: str
    content_type: str


def export_profile(
    profile: ElementSetProfile,
    identity: str,
    password: str,
    *,
    base_dir: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> ExportOutcome:
    profile.validate()
    log = progress or (lambda _msg: None)

    candidate = profile.normalized_output_path(base_dir)
    log(f"Checking export destination {candidate}…")
    output = preflight_output_path(candidate)

    log("Authenticating with Space-Track…")
    client = SpaceTrackClient(identity, password)
    ids = [sat.norad_cat_id for sat in profile.satellites]
    log(f"Requesting {len(ids)} object(s) as {profile.format.upper()} from GP…")
    result: QueryResult = client.fetch_gp(
        ids,
        profile.format,
        order_by=profile.order_by,
        empty_result_show=profile.empty_result_show,
    )
    log(f"Writing {output}…")
    write_native_result(profile, result.data, output)
    size = output.stat().st_size
    log(f"Done: {size:,} bytes written.")
    return ExportOutcome(
        output_path=output,
        bytes_written=size,
        request_url=result.request_url,
        content_type=result.content_type,
    )
