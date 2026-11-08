from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CourtLocation:
    """Structured location of a padel court.

    All fields are optional, allowing partial information to be stored
    (e.g., only coordinates, or only club name and city).
    """

    club: str | None = None
    city: str | None = None
    address: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None

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
        """Reconstructs a :class:`CourtLocation` instance from a dictionary."""
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
