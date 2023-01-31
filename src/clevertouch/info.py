"""Data classes for homes and users"""
from __future__ import annotations
from typing import Any, Optional


class HomeInfo:
    """Provides information about a home."""

    def __init__(
        self, *, home_id: Optional[str] = None, data: Optional[dict[str, Any]] = None
    ) -> None:
        if home_id is not None:
            assert data is None
            self.home_id = home_id
        elif data is not None:
            self.home_id = HomeInfo.get_id(data)
            self.update(data)
        else:
            raise Exception("Neither home_id nor data is set")

    def update(self, data: dict[str, Any]):
        """Update home info from API data."""
        assert self.get_id(data) == self.home_id
        self.label = data["label"]
        if "zones" in data:
            self.zones = {
                zone.id_local: zone
                for zone in [
                    ZoneInfo(zone_data) for zone_data in data["zones"].values()
                ]
            }
        else:
            self.zones = {}

    @classmethod
    def get_id(cls, data: dict[str, Any]):
        """Get home id from API data"""
        return data["smarthome_id"]


class ZoneInfo:
    """Contains information about a zone in a home"""

    def __init__(self, data: dict[str, Any]) -> None:
        self.id_local: str = data["num_zone"]
        self.label: str = data["zone_label"]

    @classmethod
    def get_id(cls, data: dict[str, Any]):
        """Get a local zone id from API data"""
        return data["num_zone"]
