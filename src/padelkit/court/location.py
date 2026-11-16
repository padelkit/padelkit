from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CourtLocation:
    """Structured location of a padel court.

    All fields are optional, allowing partial information to be stored
    (e.g., only coordinates, or only club name and city).
    """

    club: str | None = None
    """Name of the sports club or venue."""
    city: str | None = None
    """City where the venue is located."""
    address: str | None = None
    """Street address of the venue."""
    country: str | None = None
    """Country name or ISO code."""
    latitude: float | None = None
    """WGS84 decimal latitude in degrees (`[-90.0, 90.0]`)."""
    longitude: float | None = None
    """WGS84 decimal longitude in degrees (`[-180.0, 180.0]`)."""

    def to_dict(self) -> dict[str, Any]:
        """Serializes the court location to a dictionary."""
        return {
            "club": self.club,
            "city": self.city,
            "address": self.address,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CourtLocation":
        """Reconstructs a `CourtLocation` instance from a dictionary."""
        return cls(
            club=data.get("club"),
            city=data.get("city"),
            address=data.get("address"),
            country=data.get("country"),
            latitude=float(data["latitude"])
            if data.get("latitude") is not None
            else None,
            longitude=float(data["longitude"])
            if data.get("longitude") is not None
            else None,
        )
