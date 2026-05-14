from dataclasses import dataclass

from .dimensions import CourtDimensions
from .landmarks import Landmark


@dataclass(frozen=True)
class PadelCourt:
    """Represents a padel court and its coordinate system."""
    dimensions: CourtDimensions

    @classmethod
    def fip_standard(cls) -> "PadelCourt":
        """Creates a standard FIP padel court."""
        return cls(dimensions=CourtDimensions.fip_standard())

    @property
    def length(self) -> float:
        """Total length of the court in meters."""
        return self.dimensions.length

    @property
    def width(self) -> float:
        """Total width of the court in meters."""
        return self.dimensions.width

    def landmarks_2d(self) -> dict[str, tuple[float, float]]:
        """
        Returns a dictionary of all standard 2D landmarks.
        Coordinates are (X, Y) in meters, with origin (0,0) at the center of the court.
        X is width (left to right), Y is length (bottom to top).
        """
        half_width = self.width / 2
        half_length = self.length / 2
        service_line_y = half_length - self.dimensions.service_line_distance_from_back

        return {
            Landmark.CENTER.value: (0.0, 0.0),
            
            Landmark.TOP_LEFT.value: (-half_width, half_length),
            Landmark.TOP_RIGHT.value: (half_width, half_length),
            Landmark.BOTTOM_LEFT.value: (-half_width, -half_length),
            Landmark.BOTTOM_RIGHT.value: (half_width, -half_length),
            
            Landmark.NET_CENTER.value: (0.0, 0.0),
            Landmark.NET_LEFT.value: (-half_width, 0.0),
            Landmark.NET_RIGHT.value: (half_width, 0.0),
            
            Landmark.SERVICE_INTERSECTION_TOP.value: (0.0, service_line_y),
            Landmark.SERVICE_INTERSECTION_BOTTOM.value: (0.0, -service_line_y),
        }

    def point(self, name: str) -> tuple[float, float]:
        """
        Returns the (X, Y) coordinates of a specific landmark.
        
        Args:
            name: The name of the landmark (e.g., "center").
            
        Raises:
            ValueError: If the landmark name is not found.
        """
        landmarks = self.landmarks_2d()
        if name not in landmarks:
            raise ValueError(
                f"Unknown landmark: {name}. Available: {list(landmarks.keys())}"
            )
        return landmarks[name]
