from __future__ import annotations

import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable

from .satcat import SatcatRecord

SPACE_TRACK_ROOT = "https://www.space-track.org"
LOGIN_PATH = "/ajaxauth/login"
GP_QUERY_PATH = "/basicspacedata/query/class/gp"
SATCAT_QUERY_PATH = "/basicspacedata/query/class/satcat"
USER_AGENT = "KeplerSet/0.2 (+HalloKepler replacement; Space-Track GP/SATCAT API)"


class SpaceTrackError(RuntimeError):
    pass


@dataclass(slots=True)
class QueryResult:
    data: bytes
    content_type: str
    request_url: str

    def text(self) -> str:
        return self.data.decode("utf-8-sig", errors="replace")


class SpaceTrackClient:
    """Minimal Space-Track session client using only the Python standard library."""

    def __init__(self, identity: str, password: str, timeout: int = 45) -> None:
        self.identity = identity.strip()
        self.password = password
        self.timeout = timeout
        if not self.identity:
            raise ValueError("Space-Track identity is required.")
        if not self.password:
            raise ValueError("Space-Track password is required.")

        self._cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookies)
        )
        self._authenticated = False

    def login(self) -> None:
        form = urllib.parse.urlencode(
            {"identity": self.identity, "password": self.password}
        ).encode("utf-8")
        request = urllib.request.Request(
            SPACE_TRACK_ROOT + LOGIN_PATH,
            data=form,
            method="POST",
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                body = response.read()
                final_url = response.geturl()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise SpaceTrackError(f"Space-Track login failed (HTTP {exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise SpaceTrackError(f"Space-Track login failed: {exc.reason}") from exc

        text = body.decode("utf-8", errors="replace").lower()
        if "failed" in text and "login" in text:
            raise SpaceTrackError("Space-Track rejected the supplied credentials.")
        if "login" in final_url.lower() and not self._cookies:
            raise SpaceTrackError("Space-Track did not establish an authenticated session.")
        self._authenticated = True

    @staticmethod
    def _encode_path_value(value: str, *, allow_commas: bool = False) -> str:
        safe = "," if allow_commas else ""
        return urllib.parse.quote(value, safe=safe)

    @classmethod
    def build_gp_query_url(
        cls,
        norad_ids: Iterable[int],
        output_format: str,
        order_by: str = "NORAD_CAT_ID asc",
        empty_result_show: bool = True,
    ) -> str:
        ids = [int(x) for x in norad_ids]
        if not ids:
            raise ValueError("At least one NORAD catalog ID is required.")
        if any(x <= 0 or x > 999_999_999 for x in ids):
            raise ValueError("NORAD catalog IDs must be between 1 and 999999999.")
        if output_format not in {"tle", "3le", "xml", "kvn", "json", "csv", "html"}:
            raise ValueError(f"Unsupported Space-Track GP output format: {output_format}")

        id_value = ",".join(str(x) for x in ids)
        parts = [
            SPACE_TRACK_ROOT + GP_QUERY_PATH,
            "NORAD_CAT_ID",
            cls._encode_path_value(id_value, allow_commas=True),
            "orderby",
            cls._encode_path_value(order_by),
            "format",
            output_format,
        ]
        if empty_result_show:
            parts.extend(["emptyresult", "show"])
        return "/".join(parts)

    @classmethod
    def build_satcat_query_url(cls, *, current_only: bool = True) -> str:
        parts = [SPACE_TRACK_ROOT + SATCAT_QUERY_PATH]
        if current_only:
            parts.extend(["CURRENT", "Y"])
        parts.extend(
            [
                "orderby",
                cls._encode_path_value("NORAD_CAT_ID asc"),
                "format",
                "json",
                "emptyresult",
                "show",
            ]
        )
        return "/".join(parts)

    def _get(self, url: str) -> QueryResult:
        if not self._authenticated:
            self.login()
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                data = response.read()
                content_type = response.headers.get_content_type()
                final_url = response.geturl()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise SpaceTrackError(
                f"Space-Track query failed (HTTP {exc.code}): {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise SpaceTrackError(f"Space-Track query failed: {exc.reason}") from exc

        sample = data[:4096].decode("utf-8", errors="ignore").lower()
        if "login to space-track" in sample or 'name="identity"' in sample:
            raise SpaceTrackError("Space-Track session expired or authentication failed.")
        return QueryResult(data=data, content_type=content_type, request_url=final_url)

    def fetch_gp(
        self,
        norad_ids: Iterable[int],
        output_format: str,
        order_by: str = "NORAD_CAT_ID asc",
        empty_result_show: bool = True,
    ) -> QueryResult:
        return self._get(
            self.build_gp_query_url(
                norad_ids,
                output_format,
                order_by=order_by,
                empty_result_show=empty_result_show,
            )
        )

    def fetch_gp_json(self, norad_ids: Iterable[int], **kwargs) -> list[dict]:
        result = self.fetch_gp(norad_ids, "json", **kwargs)
        return _decode_json_list(result, "GP")

    def fetch_satcat_current(self) -> tuple[list[SatcatRecord], QueryResult]:
        """Fetch current SATCAT in one request for local caching/search."""
        result = self._get(self.build_satcat_query_url(current_only=True))
        rows = _decode_json_list(result, "SATCAT")
        records: list[SatcatRecord] = []
        seen: set[int] = set()
        for row in rows:
            try:
                record = SatcatRecord.from_api(row)
            except (TypeError, ValueError):
                continue
            if record.norad_cat_id in seen:
                continue
            seen.add(record.norad_cat_id)
            records.append(record)
        records.sort(key=lambda item: item.norad_cat_id)
        return records, result


def _decode_json_list(result: QueryResult, label: str) -> list[dict]:
    try:
        value = json.loads(result.text())
    except json.JSONDecodeError as exc:
        raise SpaceTrackError(f"Space-Track returned invalid {label} JSON.") from exc
    if isinstance(value, dict):
        raise SpaceTrackError(f"Space-Track returned an unexpected response: {value}")
    if not isinstance(value, list):
        raise SpaceTrackError(f"Space-Track {label} JSON response was not a list.")
    return [x for x in value if isinstance(x, dict)]


def redact_space_track_url(url: str) -> str:
    """Future-proof log helper: query URLs currently contain no credentials."""
    return re.sub(r"(?i)(password|identity)/[^/]+", r"\1/[redacted]", url)
