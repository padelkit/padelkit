from dataclasses import dataclass


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
