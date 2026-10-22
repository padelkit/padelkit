import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class BallProperties:
    """Physical and aerodynamic parameters of a regulation padel ball.

    Attributes:
        mass: Ball mass in kilograms (FIP regulation: ``0.056`` to ``0.0594`` kg).
        radius: Ball radius in meters (FIP regulation: ``0.03175`` to ``0.03385`` m).
        moment_of_inertia: Rotational inertia ``I`` in ``kg·m²``
            (approx. ``0.55 * mass * radius²`` for a hollow rubber core).
        fuzz_factor: Felt wear / fluffiness factor in ``[0.0, 1.0]``. Scales the
            base aerodynamic drag coefficient from ``0.50`` (new) to ``0.65`` (worn).
        pressure_psi: Internal gas pressure in PSI (regulation: ``10.0`` to ``11.0``).
    """

    mass: float = 0.058
    radius: float = 0.033
    moment_of_inertia: float = 3.47e-5
    fuzz_factor: float = 0.0
    pressure_psi: float = 11.0

    def __post_init__(self) -> None:
        if self.mass <= 0.0 or self.radius <= 0.0 or self.moment_of_inertia <= 0.0:
            raise ValueError(
                "Ball mass, radius, and moment_of_inertia must be strictly positive."
            )
        if not (0.0 <= self.fuzz_factor <= 1.0):
            raise ValueError("fuzz_factor must be in the range [0.0, 1.0].")

    @classmethod
    def fip_standard(cls) -> "BallProperties":
        """Returns a brand-new FIP regulation padel ball configuration."""
        return cls()

    @classmethod
    def worn(
        cls,
        fuzz_factor: float = 0.75,
        pressure_psi: float = 9.8,
    ) -> "BallProperties":
        """Returns a worn, fluffed padel ball with increased aerodynamic drag."""
        return cls(fuzz_factor=fuzz_factor, pressure_psi=pressure_psi)

    @classmethod
    def wet(cls, absorbed_water_g: float = 2.0) -> "BallProperties":
        """Returns a humid/wet padel ball with increased mass."""
        extra_kg = max(0.0, absorbed_water_g) / 1000.0
        new_mass = 0.058 + extra_kg
        new_moi = 0.55 * new_mass * (0.033**2)
        return cls(mass=new_mass, moment_of_inertia=new_moi, fuzz_factor=0.35)

    @property
    def cross_section_area(self) -> float:
        """Cross-sectional area ``pi * R²`` in ``m²``."""
        return math.pi * self.radius * self.radius

    @property
    def inertia_ratio(self) -> float:
        """Dimensionless moment of inertia factor ``alpha = I / (m * R²)``."""
        return self.moment_of_inertia / (self.mass * self.radius * self.radius)

    @property
    def drag_coefficient(self) -> float:
        """Base aerodynamic drag coefficient ``C_D = 0.50 + 0.15 * fuzz_factor``."""
        return 0.50 + 0.15 * self.fuzz_factor

    def to_dict(self) -> dict[str, Any]:
        """Serializes the ball properties to a plain dictionary."""
        return {
            "mass": self.mass,
            "radius": self.radius,
            "moment_of_inertia": self.moment_of_inertia,
            "fuzz_factor": self.fuzz_factor,
            "pressure_psi": self.pressure_psi,
            "cross_section_area": round(self.cross_section_area, 7),
            "drag_coefficient": round(self.drag_coefficient, 4),
        }


@dataclass(frozen=True)
class EnvironmentConditions:
    """Atmospheric and environmental conditions affecting ball flight.

    Attributes:
        gravity: Gravitational acceleration in ``m/s²`` (along ``-Z``).
        air_density: Ambient air density ``rho`` in ``kg/m³``.
        wind_velocity: 3D wind velocity vector ``(wx, wy, wz)`` in ``m/s``.
        spin_decay_rate: Exponential angular velocity decay rate ``k_spin``
            in ``1/s`` during free flight (negligible by default: ``0.001``).
    """

    gravity: float = 9.81
    air_density: float = 1.18
    wind_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    spin_decay_rate: float = 0.001

    def __post_init__(self) -> None:
        if self.gravity < 0.0 or self.air_density < 0.0:
            raise ValueError("gravity and air_density must be non-negative.")
        if len(self.wind_velocity) != 3:
            raise ValueError("wind_velocity must be a 3-element (wx, wy, wz) tuple.")

    @classmethod
    def standard(cls) -> "EnvironmentConditions":
        """Standard indoor/calm environment (21°C, ~650m altitude, no wind)."""
        return cls()

    @classmethod
    def from_atmosphere(
        cls,
        altitude_m: float = 0.0,
        temperature_c: float = 20.0,
        relative_humidity: float = 0.5,
        wind_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> "EnvironmentConditions":
        """Computes air density ``rho`` from altitude, temperature, and humidity.

        Uses the international barometric formula and ideal gas law for humid air.
        For example, Madrid (`altitude_m=650`, `temperature_c=25`) yields
        ``air_density ≈ 1.095 kg/m³`` compared to ``1.204 kg/m³`` at sea level.
        """
        temp_k = temperature_c + 273.15
        if temp_k <= 0.0:
            raise ValueError("temperature_c must be above absolute zero.")
        if not (0.0 <= relative_humidity <= 1.0):
            raise ValueError("relative_humidity must be in [0.0, 1.0].")

        # Barometric pressure (Pa) at altitude_m
        p_total = 101325.0 * ((1.0 - 2.25577e-5 * altitude_m) ** 5.25588)
        # Tetens saturation vapor pressure (Pa)
        p_sat = 610.78 * math.exp((17.27 * temperature_c) / (temperature_c + 237.3))
        p_vapor = relative_humidity * p_sat
        p_dry = max(0.0, p_total - p_vapor)

        r_dry = 287.058
        r_vapor = 461.495
        rho = (p_dry / (r_dry * temp_k)) + (p_vapor / (r_vapor * temp_k))
        return cls(
            gravity=9.81,
            air_density=round(rho, 5),
            wind_velocity=wind_velocity,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the environmental parameters to a plain dictionary."""
        return {
            "gravity": self.gravity,
            "air_density": self.air_density,
            "wind_velocity": list(self.wind_velocity),
            "spin_decay_rate": self.spin_decay_rate,
        }


@dataclass(frozen=True)
class SurfaceMaterials:
    """Coefficients of restitution (COR) and friction (``mu``) across court surfaces.

    Attributes:
        glass_cor: Normal restitution on tempered glass walls (default ``0.85``).
        glass_friction: Coulomb friction on tempered glass (default ``0.25``;
            low friction preserves slice/backspin and favors sliding).
        wall_cor: Normal restitution on concrete/masonry walls (default ``0.75``).
        wall_friction: Coulomb friction on concrete walls (default ``0.70``;
            high grip induces rolling).
        floor_cor: Normal restitution on artificial turf floor (default ``0.75``).
        floor_friction: Coulomb friction on artificial turf (default ``0.45``).
        fence_cor: Normal restitution on metallic wire mesh (default ``0.45``).
        fence_friction: Coulomb friction on metallic wire mesh (default ``0.50``).
        fence_randomness: Standard deviation of normal-vector angular perturbation
            on metallic fence impacts (``0.0`` for deterministic bounces).
        net_damping: Velocity retention factor on net mesh collision (default ``0.30``).
    """

    glass_cor: float = 0.85
    glass_friction: float = 0.25
    wall_cor: float = 0.75
    wall_friction: float = 0.70
    floor_cor: float = 0.75
    floor_friction: float = 0.45
    fence_cor: float = 0.45
    fence_friction: float = 0.50
    fence_randomness: float = 0.0
    net_damping: float = 0.30

    @classmethod
    def fip_standard(cls, fence_randomness: float = 0.0) -> "SurfaceMaterials":
        """Standard FIP court material coefficients."""
        return cls(fence_randomness=fence_randomness)

    @classmethod
    def fast_indoor(cls) -> "SurfaceMaterials":
        """Low-sand curled monofilament turf with fast, higher-bouncing response."""
        return cls(floor_cor=0.79, floor_friction=0.38, glass_cor=0.87)

    @classmethod
    def slow_sandy(cls) -> "SurfaceMaterials":
        """Heavy silica-sand outdoor turf with lower bounce and more skid."""
        return cls(floor_cor=0.71, floor_friction=0.52)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the surface materials to a plain dictionary."""
        return {
            "glass_cor": self.glass_cor,
            "glass_friction": self.glass_friction,
            "wall_cor": self.wall_cor,
            "wall_friction": self.wall_friction,
            "floor_cor": self.floor_cor,
            "floor_friction": self.floor_friction,
            "fence_cor": self.fence_cor,
            "fence_friction": self.fence_friction,
            "fence_randomness": self.fence_randomness,
            "net_damping": self.net_damping,
        }


@dataclass(frozen=True)
class BallState:
    """Instantaneous 9D kinematic state of the padel ball.

    Encapsulates 3D position ``(x, y, z)`` in meters, linear velocity
    ``(vx, vy, vz)`` in ``m/s``, and angular velocity ``(wx, wy, wz)`` in ``rad/s``.
    """

    position: tuple[float, float, float]
    velocity: tuple[float, float, float]
    angular_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if (
            len(self.position) != 3
            or len(self.velocity) != 3
            or len(self.angular_velocity) != 3
        ):
            raise ValueError(
                "position, velocity, and angular_velocity must be 3-tuples."
            )

    @classmethod
    def from_vector(cls, vec: np.ndarray | Sequence[float]) -> "BallState":
        """Constructs a :class:`BallState` from a 6D or 9D state vector."""
        arr = np.asarray(vec, dtype=np.float64).ravel()
        if arr.size == 6:
            return cls(
                position=(float(arr[0]), float(arr[1]), float(arr[2])),
                velocity=(float(arr[3]), float(arr[4]), float(arr[5])),
                angular_velocity=(0.0, 0.0, 0.0),
            )
        if arr.size == 9:
            return cls(
                position=(float(arr[0]), float(arr[1]), float(arr[2])),
                velocity=(float(arr[3]), float(arr[4]), float(arr[5])),
                angular_velocity=(float(arr[6]), float(arr[7]), float(arr[8])),
            )
        raise ValueError("State vector must have 6 or 9 elements.")

    @classmethod
    def from_shot(
        cls,
        position: tuple[float, float, float] | Sequence[float],
        velocity: tuple[float, float, float] | Sequence[float],
        topspin_rpm: float = 0.0,
        sidespin_rpm: float = 0.0,
    ) -> "BallState":
        """Creates a :class:`BallState` using intuitive RPM spin parameters.

        Args:
            position: Initial 3D ball position ``(x, y, z)`` in meters.
            velocity: Initial 3D linear velocity ``(vx, vy, vz)`` in ``m/s``.
            topspin_rpm: Spin rate in RPM around the horizontal axis perpendicular
                to the flight direction.
                - Positive values (e.g., ``+2500``) represent **topspin** (smash,
                  topspin lob), producing downward Magnus force.
                - Negative values (e.g., ``-2000``) represent **backspin / slice**
                  (bandeja, volley, serve), producing upward Magnus lift and low
                  skidding bounces off the glass.
            sidespin_rpm: Spin rate in RPM around the vertical ``+Z`` axis
                (e.g., for a *víbora* or side-sliced serve).
        """
        pos = (float(position[0]), float(position[1]), float(position[2]))
        vel = (float(velocity[0]), float(velocity[1]), float(velocity[2]))

        vx, vy, _ = vel
        horiz_norm = math.hypot(vx, vy)
        if horiz_norm > 1e-8:
            hx, hy = vx / horiz_norm, vy / horiz_norm
        else:
            hx, hy = 0.0, 1.0

        # Horizontal right vector = (hy, -hx, 0).
        # Topspin axis points along (-hy, hx, 0) so that (omega x v) points along -Z.
        omega_top_rad = (topspin_rpm * 2.0 * math.pi) / 60.0
        omega_side_rad = (sidespin_rpm * 2.0 * math.pi) / 60.0

        wx = -hy * omega_top_rad
        wy = hx * omega_top_rad
        wz = omega_side_rad
        return cls(
            position=pos,
            velocity=vel,
            angular_velocity=(wx, wy, wz),
        )

    @property
    def vector_9d(self) -> np.ndarray:
        """Returns the 9D state vector ``[x, y, z, vx, vy, vz, wx, wy, wz]``."""
        return np.array(
            [*self.position, *self.velocity, *self.angular_velocity],
            dtype=np.float64,
        )

    @property
    def speed(self) -> float:
        """Linear speed magnitude ``||v||`` in ``m/s``."""
        vx, vy, vz = self.velocity
        return math.sqrt(vx * vx + vy * vy + vz * vz)

    @property
    def speed_kmh(self) -> float:
        """Linear speed magnitude in ``km/h``."""
        return self.speed * 3.6

    @property
    def spin_rad_s(self) -> float:
        """Angular speed magnitude ``||omega||`` in ``rad/s``."""
        wx, wy, wz = self.angular_velocity
        return math.sqrt(wx * wx + wy * wy + wz * wz)

    @property
    def spin_rpm(self) -> float:
        """Angular speed magnitude in revolutions per minute (``RPM``)."""
        return (self.spin_rad_s * 60.0) / (2.0 * math.pi)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the ball state to a plain dictionary."""
        return {
            "position": list(self.position),
            "velocity": list(self.velocity),
            "angular_velocity": list(self.angular_velocity),
            "speed_ms": round(self.speed, 4),
            "speed_kmh": round(self.speed_kmh, 2),
            "spin_rpm": round(self.spin_rpm, 1),
        }
