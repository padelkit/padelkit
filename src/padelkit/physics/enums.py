from enum import Enum


class SurfaceType(str, Enum):
    """Court surfaces involved in ball contact and bounce events."""

    FLOOR = "floor"
    BACK_GLASS = "back_glass"
    SIDE_GLASS = "side_glass"
    BACK_WALL = "back_wall"
    SIDE_WALL = "side_wall"
    BACK_FENCE = "back_fence"
    SIDE_FENCE = "side_fence"
    NET = "net"


class ContactRegime(str, Enum):
    """Tangential contact friction regime during a ball bounce.

    Attributes:
        SLIDING: Tangential slip velocity exceeds the Coulomb friction impulse
            limit ``mu * |J_n|``; the ball skids throughout the impact.
        ROLLING: Friction is sufficient to arrest slip during impact; the ball
            grips the surface and exits in rolling coupling.
        DAMPED: Inelastic net mesh collision with velocity damping.
    """

    SLIDING = "sliding"
    ROLLING = "rolling"
    DAMPED = "damped"
