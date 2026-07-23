"""Library functions for interfacing with external Grafana dashboards"""

from typing import Any, Literal

import httpx

from ..settings import settings


def get_grafana_link(bps_run_name: str, from_epoch_ms: int, to_epoch_ms: int | Literal["now"]) -> httpx.URL:
    """Generate a Grafana link for a bps run"""
    url = f"{settings.grafana_base_url}/{settings.grafana_campaign_history}"

    request = httpx.Request(
        method="get",
        url=url,
        params={
            "orgId": 1,
            "var-bps_run": bps_run_name,
            "from": from_epoch_ms,
            "to": to_epoch_ms,
            "timezone": "utc",
        },
    )

    return request.url


def get_grafana_link_for_node(node: dict[str, Any]) -> httpx.URL | None:
    """..."""
    if (bps_run_name := node["metadata"].get("bps", {}).get("Run Name")) is None:
        return None
    fromtime: int = node["metadata"].get("crtime")
    totime: int | Literal["now"] = node["metadata"].get("mtime", "now")

    fromtime_ms = fromtime * 1000
    totime_ms = totime * 1000 if isinstance(totime, int) else totime

    return get_grafana_link(bps_run_name, fromtime_ms, totime_ms)
