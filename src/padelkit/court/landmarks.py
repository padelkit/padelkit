from enum import Enum


class Landmark(str, Enum):
    """Basic 2D landmarks on a padel court."""
    CENTER = "center"
    
    # Corners
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    
    # Net
    NET_CENTER = "net_center"
    NET_LEFT = "net_left"
    NET_RIGHT = "net_right"
    
    # Service intersections (simplified)
    SERVICE_INTERSECTION_TOP = "service_intersection_top"
    SERVICE_INTERSECTION_BOTTOM = "service_intersection_bottom"
