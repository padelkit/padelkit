from enum import Enum


class Landmark(str, Enum):
    """Standard landmark positions on a padel court.

    Landmarks are numbered 1-17 to match the camera-calibration convention
    used in the padelamix pipeline. Points 1-13 lie on the court floor
    (Z = 0). Points 14-17 are at the top of the back walls (Z = back_wall_height).

    Naming convention:
        - NEAR: the half-court with negative Y in the CENTERED system
          (Y = 0..10 in CORNER_BASED).
        - FAR:  the half-court with positive Y in the CENTERED system
          (Y = 10..20 in CORNER_BASED).
        - LEFT/RIGHT: from the perspective of a player on the NEAR side
          facing the net.
    """

    # --- Floor points (Z = 0) ---

    # Near back wall corners
    FLOOR_NEAR_LEFT = "floor_near_left"        # 1
    FLOOR_NEAR_RIGHT = "floor_near_right"       # 2

    # Near service line
    SERVICE_NEAR_LEFT = "service_near_left"     # 3
    SERVICE_NEAR_CENTER = "service_near_center" # 4
    SERVICE_NEAR_RIGHT = "service_near_right"   # 5

    # Net line
    NET_LEFT = "net_left"                       # 6
    CENTER = "center"                           # 7
    NET_RIGHT = "net_right"                     # 8

    # Far service line
    SERVICE_FAR_LEFT = "service_far_left"       # 9
    SERVICE_FAR_CENTER = "service_far_center"   # 10
    SERVICE_FAR_RIGHT = "service_far_right"     # 11

    # Far back wall corners
    FLOOR_FAR_LEFT = "floor_far_left"           # 12
    FLOOR_FAR_RIGHT = "floor_far_right"         # 13

    # --- Back wall top points (Z = back_wall_height, typically 4.0 m) ---

    WALL_TOP_NEAR_LEFT = "wall_top_near_left"   # 14
    WALL_TOP_NEAR_RIGHT = "wall_top_near_right" # 15
    WALL_TOP_FAR_LEFT = "wall_top_far_left"     # 16
    WALL_TOP_FAR_RIGHT = "wall_top_far_right"   # 17
