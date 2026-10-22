import math
from dataclasses import dataclass, field

import numpy as np

from ..court.court import Court
from ..court.enums import CoordinateSystem, EnclosureType, EnclosureVariant
from .enums import ContactRegime, SurfaceType
from .models import (
    BallProperties,
    BallState,
    EnvironmentConditions,
    SurfaceMaterials,
)
from .trajectory import BallTrajectory, BounceEvent


@dataclass
class BallPhysicsEngine:
    """High-fidelity 9D padel ball aerodynamics and contact physics engine.

    Integrates the 9-dimensional state ``[x, y, z, vx, vy, vz, wx, wy, wz]``
    using 4th-order Runge-Kutta (RK4) with:
    - Gravity and 3D wind relative airspeed.
    - Quadratic aerodynamic drag scaled by felt wear (``fuzz_factor``).
    - Spin-induced **Magnus lift** via the Spindt coefficient model.
    - Impulse-based 3D surface collisions (Floor, Back Glass/Wall, Side Stepped
      Glass/Wall, Metallic Wire Fence with optional stochastic normal noise,
      and Catenary Net) with exact **Sliding vs. Rolling** regime transition.
    """

    court: Court = field(default_factory=Court.fip_standard)
    ball: BallProperties = field(default_factory=BallProperties.fip_standard)
    environment: EnvironmentConditions = field(
        default_factory=EnvironmentConditions.standard
    )
    surfaces: SurfaceMaterials = field(default_factory=SurfaceMaterials.fip_standard)
    coordinate_system: CoordinateSystem = CoordinateSystem.CENTERED

    # ------------------------------------------------------------------ #
    # Aerodynamics (Free Flight Forces & Torque)
    # ------------------------------------------------------------------ #

    def compute_acceleration(
        self,
        state: BallState | np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Computes linear ``(m/s²)`` and angular ``(rad/s²)`` accelerations.

        Supports both a single 9D state ``(9,)`` and a batch of states ``(B, 9)``.
        """
        s = (
            state.vector_9d
            if isinstance(state, BallState)
            else np.asarray(state, dtype=np.float64)
        )
        single = s.ndim == 1
        if single:
            s = s[np.newaxis, :]

        vel = s[:, 3:6]
        ang_vel = s[:, 6:9]

        wind = np.asarray(self.environment.wind_velocity, dtype=np.float64)
        v_rel = vel - wind
        speed = np.linalg.norm(v_rel, axis=1, keepdims=True)
        speed_safe = np.maximum(speed, 1e-9)
        v_dir = v_rel / speed_safe

        # 1. Gravity
        f_grav = np.zeros_like(vel)
        f_grav[:, 2] = -self.ball.mass * self.environment.gravity

        # 2. Quadratic Aerodynamic Drag
        rho = self.environment.air_density
        area = self.ball.cross_section_area
        cd = self.ball.drag_coefficient
        f_drag_mag = 0.5 * rho * area * cd * (speed**2)
        f_drag = -f_drag_mag * v_dir

        # 3. Magnus Lift (Spindt model)
        omega = np.linalg.norm(ang_vel, axis=1, keepdims=True)
        omega_safe = np.maximum(omega, 1e-9)
        omega_dir = ang_vel / omega_safe

        spin_param = (self.ball.radius * omega) / speed_safe
        cl = np.where(
            omega > 1e-6,
            1.0 / (2.32 + 0.4 / (spin_param + 0.1)),
            0.0,
        )
        f_lift_mag = 0.5 * rho * area * cl * (speed**2)

        lift_raw = np.cross(omega_dir, v_dir)
        lift_norm = np.maximum(np.linalg.norm(lift_raw, axis=1, keepdims=True), 1e-9)
        lift_dir = lift_raw / lift_norm
        f_magnus = f_lift_mag * lift_dir

        acc_lin = (f_grav + f_drag + f_magnus) / self.ball.mass
        acc_ang = -self.environment.spin_decay_rate * ang_vel

        if single:
            return acc_lin[0], acc_ang[0]
        return acc_lin, acc_ang

    def _dynamics_9d(self, s: np.ndarray) -> np.ndarray:
        acc_lin, acc_ang = self.compute_acceleration(s)
        return np.concatenate([s[..., 3:6], acc_lin, acc_ang], axis=-1)

    # ------------------------------------------------------------------ #
    # 4th-Order Runge-Kutta (RK4) Integrator
    # ------------------------------------------------------------------ #

    def rk4_step(self, state_vec: np.ndarray, dt: float) -> np.ndarray:
        """Advances a 9D state vector ``(9,)`` or batch ``(B, 9)`` by ``dt`` via RK4."""
        s = np.asarray(state_vec, dtype=np.float64)
        k1 = self._dynamics_9d(s)
        k2 = self._dynamics_9d(s + 0.5 * dt * k1)
        k3 = self._dynamics_9d(s + 0.5 * dt * k2)
        k4 = self._dynamics_9d(s + dt * k3)
        return s + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

    # ------------------------------------------------------------------ #
    # Contact & Bounce Resolution (Sliding vs. Rolling)
    # ------------------------------------------------------------------ #

    def resolve_collision(
        self,
        state_vec: np.ndarray,
        normal: np.ndarray,
        cor: float,
        friction: float,
    ) -> tuple[np.ndarray, ContactRegime]:
        """Resolves an instantaneous 3D impact against a surface with unit ``normal``.

        Computes the tangential slip velocity of the ball's contact point,
        evaluates the Coulomb sliding threshold against the rolling grip impulse,
        and updates both linear velocity and angular velocity (spin).
        """
        s = np.asarray(state_vec, dtype=np.float64)
        n = np.asarray(normal, dtype=np.float64)
        n_norm = float(np.linalg.norm(n))
        if n_norm > 1e-9:
            n = n / n_norm

        vel = s[3:6]
        ang_vel = s[6:9]

        vn = float(np.dot(vel, n))
        vt = vel - vn * n

        # 1. Normal restitution impulse
        vn_new = -cor * vn
        j_n = self.ball.mass * (vn_new - vn)

        # 2. Tangential contact slip velocity: v_slip = vt + (omega x r_contact)
        r_vec = -self.ball.radius * n
        v_spin = np.cross(ang_vel, r_vec)
        v_slip = vt + v_spin
        slip_mag = float(np.linalg.norm(v_slip))

        # 3. Coulomb max friction vs. Rolling grip impulse
        j_max_friction = friction * abs(j_n)
        alpha = self.ball.inertia_ratio
        mass_rolling = self.ball.mass / (1.0 + 1.0 / alpha)
        j_rolling_vec = -mass_rolling * v_slip
        j_rolling_mag = float(np.linalg.norm(j_rolling_vec))

        if j_rolling_mag > j_max_friction and slip_mag > 1e-9:
            regime = ContactRegime.SLIDING
            j_t = -j_max_friction * (v_slip / slip_mag)
        else:
            regime = ContactRegime.ROLLING
            j_t = j_rolling_vec

        # 4. Update linear and angular velocities
        delta_v = (n * j_n + j_t) / self.ball.mass
        vel_new = vel + delta_v

        torque_impulse = np.cross(r_vec, j_t)
        delta_omega = torque_impulse / self.ball.moment_of_inertia
        ang_vel_new = ang_vel + delta_omega

        out = s.copy()
        out[3:6] = vel_new
        out[6:9] = ang_vel_new
        return out, regime

    # ------------------------------------------------------------------ #
    # Single Step with Court Geometry Collision Detection
    # ------------------------------------------------------------------ #

    def _court_bounds(self) -> tuple[float, float, float, float, float]:
        """Returns ``(x_min, x_max, y_min, y_max, net_y)`` in active coordinates."""
        w = self.court.width
        l_len = self.court.length
        if self.coordinate_system is CoordinateSystem.CORNER_BASED:
            return (0.0, w, 0.0, l_len, l_len / 2.0)
        return (-w / 2.0, w / 2.0, -l_len / 2.0, l_len / 2.0, 0.0)

    def _side_wall_heights_at_y(self, y_pos: float) -> tuple[float, float]:
        """Returns ``(solid_height_m, total_mesh_height_m)`` at length ``y_pos``."""
        _, _, y_min, y_max, _ = self._court_bounds()
        dist_from_back = min(abs(y_pos - y_min), abs(y_max - y_pos))

        is_wall = self.court.enclosure_type is EnclosureType.WALL
        if is_wall:
            if dist_from_back <= 2.0:
                solid_h = 3.0
            elif dist_from_back <= 4.0:
                solid_h = 2.0
            else:
                solid_h = 0.0
        else:
            solid_h = 3.0 if dist_from_back <= 4.0 else 0.0

        is_v2 = (
            self.court.enclosure_variant is EnclosureVariant.V2
            or self.court.dimensions.side_wall_height >= 4.0
        )
        if is_v2:
            total_h = 4.0
        else:
            total_h = 4.0 if dist_from_back <= 2.0 else 3.0

        return solid_h, total_h

    def _perturb_fence_normal(
        self,
        normal: np.ndarray,
        rng: np.random.Generator | None,
    ) -> np.ndarray:
        sigma = self.surfaces.fence_randomness
        if sigma <= 1e-6:
            return normal
        gen = rng if rng is not None else np.random.default_rng()
        noise = gen.normal(0.0, sigma, size=3)
        perturbed = normal + noise
        # Ensure perturbed normal still points into the court interior
        if float(np.dot(perturbed, normal)) <= 0.2:
            return normal
        return perturbed / np.linalg.norm(perturbed)

    def step(
        self,
        state: BallState | np.ndarray,
        dt: float = 1.0 / 240.0,
        timestamp: float = 0.0,
        rng: np.random.Generator | None = None,
    ) -> tuple[BallState, BounceEvent | None]:
        """Advances the ball by ``dt`` seconds and resolves any court collision."""
        s_in = (
            state.vector_9d
            if isinstance(state, BallState)
            else np.asarray(state, dtype=np.float64).copy()
        )
        s = self.rk4_step(s_in, dt)

        r = self.ball.radius
        x_min, x_max, y_min, y_max, net_y = self._court_bounds()
        is_wall = self.court.enclosure_type is EnclosureType.WALL
        solid_cor = self.surfaces.wall_cor if is_wall else self.surfaces.glass_cor
        solid_fric = (
            self.surfaces.wall_friction if is_wall else self.surfaces.glass_friction
        )

        bounce_event: BounceEvent | None = None
        t_next = timestamp + dt

        # 1. Floor collision (z <= R and vz < 0)
        if s[2] <= r and s[5] < 0.0:
            vel_before = (float(s[3]), float(s[4]), float(s[5]))
            ang_before = (float(s[6]), float(s[7]), float(s[8]))
            s, regime = self.resolve_collision(
                s,
                np.array([0.0, 0.0, 1.0]),
                self.surfaces.floor_cor,
                self.surfaces.floor_friction,
            )
            s[2] = max(float(s[2]), r)
            bounce_event = BounceEvent(
                timestamp=t_next,
                surface=SurfaceType.FLOOR,
                position=(float(s[0]), float(s[1]), float(s[2])),
                velocity_before=vel_before,
                velocity_after=(float(s[3]), float(s[4]), float(s[5])),
                angular_velocity_before=ang_before,
                angular_velocity_after=(float(s[6]), float(s[7]), float(s[8])),
                regime=regime,
            )

        # 2. Side walls (Left: x <= x_min + R, Right: x >= x_max - R)
        solid_side_h, total_side_h = self._side_wall_heights_at_y(float(s[1]))
        if s[2] <= total_side_h:
            is_solid = s[2] <= solid_side_h
            cor_s = solid_cor if is_solid else self.surfaces.fence_cor
            fric_s = solid_fric if is_solid else self.surfaces.fence_friction
            surf_type = (
                (SurfaceType.SIDE_WALL if is_wall else SurfaceType.SIDE_GLASS)
                if is_solid
                else SurfaceType.SIDE_FENCE
            )

            if s[0] <= x_min + r and s[3] < 0.0:
                vel_before = (float(s[3]), float(s[4]), float(s[5]))
                ang_before = (float(s[6]), float(s[7]), float(s[8]))
                normal = np.array([1.0, 0.0, 0.0])
                if not is_solid:
                    normal = self._perturb_fence_normal(normal, rng)
                s, regime = self.resolve_collision(s, normal, cor_s, fric_s)
                s[0] = max(float(s[0]), x_min + r)
                bounce_event = BounceEvent(
                    timestamp=t_next,
                    surface=surf_type,
                    position=(float(s[0]), float(s[1]), float(s[2])),
                    velocity_before=vel_before,
                    velocity_after=(float(s[3]), float(s[4]), float(s[5])),
                    angular_velocity_before=ang_before,
                    angular_velocity_after=(float(s[6]), float(s[7]), float(s[8])),
                    regime=regime,
                )
            elif s[0] >= x_max - r and s[3] > 0.0:
                vel_before = (float(s[3]), float(s[4]), float(s[5]))
                ang_before = (float(s[6]), float(s[7]), float(s[8]))
                normal = np.array([-1.0, 0.0, 0.0])
                if not is_solid:
                    normal = self._perturb_fence_normal(normal, rng)
                s, regime = self.resolve_collision(s, normal, cor_s, fric_s)
                s[0] = min(float(s[0]), x_max - r)
                bounce_event = BounceEvent(
                    timestamp=t_next,
                    surface=surf_type,
                    position=(float(s[0]), float(s[1]), float(s[2])),
                    velocity_before=vel_before,
                    velocity_after=(float(s[3]), float(s[4]), float(s[5])),
                    angular_velocity_before=ang_before,
                    angular_velocity_after=(float(s[6]), float(s[7]), float(s[8])),
                    regime=regime,
                )

        # 3. Back walls (Near: y <= y_min + R, Far: y >= y_max - R)
        back_h = self.court.dimensions.back_wall_height
        if s[2] <= back_h:
            is_solid_back = s[2] <= 3.0
            cor_b = solid_cor if is_solid_back else self.surfaces.fence_cor
            fric_b = solid_fric if is_solid_back else self.surfaces.fence_friction
            surf_back = (
                (SurfaceType.BACK_WALL if is_wall else SurfaceType.BACK_GLASS)
                if is_solid_back
                else SurfaceType.BACK_FENCE
            )

            if s[1] <= y_min + r and s[4] < 0.0:
                vel_before = (float(s[3]), float(s[4]), float(s[5]))
                ang_before = (float(s[6]), float(s[7]), float(s[8]))
                normal = np.array([0.0, 1.0, 0.0])
                if not is_solid_back:
                    normal = self._perturb_fence_normal(normal, rng)
                s, regime = self.resolve_collision(s, normal, cor_b, fric_b)
                s[1] = max(float(s[1]), y_min + r)
                bounce_event = BounceEvent(
                    timestamp=t_next,
                    surface=surf_back,
                    position=(float(s[0]), float(s[1]), float(s[2])),
                    velocity_before=vel_before,
                    velocity_after=(float(s[3]), float(s[4]), float(s[5])),
                    angular_velocity_before=ang_before,
                    angular_velocity_after=(float(s[6]), float(s[7]), float(s[8])),
                    regime=regime,
                )
            elif s[1] >= y_max - r and s[4] > 0.0:
                vel_before = (float(s[3]), float(s[4]), float(s[5]))
                ang_before = (float(s[6]), float(s[7]), float(s[8]))
                normal = np.array([0.0, -1.0, 0.0])
                if not is_solid_back:
                    normal = self._perturb_fence_normal(normal, rng)
                s, regime = self.resolve_collision(s, normal, cor_b, fric_b)
                s[1] = min(float(s[1]), y_max - r)
                bounce_event = BounceEvent(
                    timestamp=t_next,
                    surface=surf_back,
                    position=(float(s[0]), float(s[1]), float(s[2])),
                    velocity_before=vel_before,
                    velocity_after=(float(s[3]), float(s[4]), float(s[5])),
                    angular_velocity_before=ang_before,
                    angular_velocity_after=(float(s[6]), float(s[7]), float(s[8])),
                    regime=regime,
                )

        # 4. Catenary Net collision
        y_prev = float(s_in[1])
        y_curr = float(s[1])
        crossed_net = (y_prev - net_y) * (y_curr - net_y) <= 0.0 or (
            abs(y_curr - net_y) <= r
        )
        if crossed_net and x_min <= s[0] <= x_max:
            x_center = (x_min + x_max) / 2.0
            hw = max((x_max - x_min) / 2.0, 1e-6)
            u_norm = (float(s[0]) - x_center) / hw
            h_center = self.court.dimensions.net_height_center
            h_posts = self.court.dimensions.net_height_posts
            net_h_at_x = h_center + (h_posts - h_center) * (u_norm * u_norm)

            if s[2] <= net_h_at_x and abs(s[4]) > 1e-5:
                vel_before = (float(s[3]), float(s[4]), float(s[5]))
                ang_before = (float(s[6]), float(s[7]), float(s[8]))
                s[4] = -s[4] * self.surfaces.net_damping
                s[3] = s[3] * 0.7
                s[1] = net_y - r if y_prev < net_y else net_y + r
                bounce_event = BounceEvent(
                    timestamp=t_next,
                    surface=SurfaceType.NET,
                    position=(float(s[0]), float(s[1]), float(s[2])),
                    velocity_before=vel_before,
                    velocity_after=(float(s[3]), float(s[4]), float(s[5])),
                    angular_velocity_before=ang_before,
                    angular_velocity_after=(float(s[6]), float(s[7]), float(s[8])),
                    regime=ContactRegime.DAMPED,
                )

        return BallState.from_vector(s), bounce_event

    # ------------------------------------------------------------------ #
    # Full Trajectory & Vectorized Batch Simulation
    # ------------------------------------------------------------------ #

    def simulate(
        self,
        initial_state: BallState | np.ndarray,
        duration_s: float = 2.5,
        dt: float = 1.0 / 240.0,
        stop_on_second_floor_bounce: bool = False,
        seed: int | None = None,
    ) -> BallTrajectory:
        """Simulates a 3D ball trajectory and records all :class:`BounceEvent`s."""
        if duration_s <= 0.0 or dt <= 0.0:
            raise ValueError("duration_s and dt must be strictly positive.")

        curr = (
            initial_state
            if isinstance(initial_state, BallState)
            else BallState.from_vector(initial_state)
        )
        rng = np.random.default_rng(seed)

        num_steps = int(math.ceil(duration_s / dt))
        timestamps: list[float] = [0.0]
        states: list[np.ndarray] = [curr.vector_9d]
        bounces: list[BounceEvent] = []
        floor_bounces = 0

        t = 0.0
        for _ in range(num_steps):
            curr, b_ev = self.step(curr, dt=dt, timestamp=t, rng=rng)
            t += dt
            timestamps.append(round(t, 6))
            states.append(curr.vector_9d)

            if b_ev is not None:
                bounces.append(b_ev)
                if b_ev.surface is SurfaceType.FLOOR:
                    floor_bounces += 1
                    if stop_on_second_floor_bounce and floor_bounces >= 2:
                        break

        return BallTrajectory(
            timestamps=np.array(timestamps, dtype=np.float64),
            states=np.stack(states, axis=0),
            bounces=bounces,
            coordinate_system=self.coordinate_system,
        )

    def simulate_batch(
        self,
        initial_states: np.ndarray,
        num_steps: int,
        dt: float = 1.0 / 120.0,
    ) -> np.ndarray:
        """Vectorized batch simulation of ``B`` trajectories ``(B, 9)`` in parallel.

        Ideal for particle filters, Monte Carlo rollouts, and trajectory
        optimization without Python loops over individual particles.

        Returns:
            NumPy array of shape ``(B, num_steps + 1, 9)``.
        """
        s = np.asarray(initial_states, dtype=np.float64)
        if s.ndim != 2 or s.shape[1] not in (6, 9):
            raise ValueError("initial_states must have shape (B, 9) or (B, 6).")
        if s.shape[1] == 6:
            s = np.concatenate([s, np.zeros((s.shape[0], 3))], axis=1)

        b_size = s.shape[0]
        out = np.empty((b_size, num_steps + 1, 9), dtype=np.float64)
        out[:, 0, :] = s

        r = self.ball.radius
        x_min, x_max, y_min, y_max, _ = self._court_bounds()
        floor_cor = self.surfaces.floor_cor
        floor_fric = self.surfaces.floor_friction
        is_wall = self.court.enclosure_type is EnclosureType.WALL
        wall_cor = self.surfaces.wall_cor if is_wall else self.surfaces.glass_cor
        alpha = self.ball.inertia_ratio
        mass_roll_factor = 1.0 / (1.0 + 1.0 / alpha)

        curr = s.copy()
        for step_idx in range(1, num_steps + 1):
            curr = self.rk4_step(curr, dt)

            # Vectorized Floor Bounce (z <= R & vz < 0)
            hit_floor = (curr[:, 2] <= r) & (curr[:, 5] < 0.0)
            if np.any(hit_floor):
                vz_in = curr[hit_floor, 5:6]
                vz_out = -floor_cor * vz_in
                dv_n = vz_out - vz_in
                vt = curr[hit_floor, 3:5]
                w_xy = curr[hit_floor, 6:8]
                # r_vec = (0, 0, -R) => omega x r_vec = (-wy*R, wx*R, 0)
                v_spin_x = -w_xy[:, 1:2] * r
                v_spin_y = w_xy[:, 0:1] * r
                v_slip = vt + np.concatenate([v_spin_x, v_spin_y], axis=1)
                slip_norm = np.maximum(
                    np.linalg.norm(v_slip, axis=1, keepdims=True), 1e-9
                )
                dv_max = floor_fric * np.abs(dv_n)
                dv_roll = -mass_roll_factor * v_slip
                dv_roll_mag = np.linalg.norm(dv_roll, axis=1, keepdims=True)
                sliding = dv_roll_mag > dv_max
                dv_t = np.where(sliding, -dv_max * (v_slip / slip_norm), dv_roll)

                curr[hit_floor, 3:5] += dv_t
                curr[hit_floor, 5:6] = vz_out
                curr[hit_floor, 2] = np.maximum(curr[hit_floor, 2], r)
                # Torque impulse r_vec x J_t: delta_wx = (R * dv_ty) / (alpha * R^2)
                curr[hit_floor, 6:7] += dv_t[:, 1:2] / (alpha * r)
                curr[hit_floor, 7:8] -= dv_t[:, 0:1] / (alpha * r)

            # Vectorized Back & Side Wall Restitution
            hit_left = (curr[:, 0] <= x_min + r) & (curr[:, 3] < 0.0)
            curr[hit_left, 3] *= -wall_cor
            curr[hit_left, 0] = x_min + r

            hit_right = (curr[:, 0] >= x_max - r) & (curr[:, 3] > 0.0)
            curr[hit_right, 3] *= -wall_cor
            curr[hit_right, 0] = x_max - r

            hit_near = (curr[:, 1] <= y_min + r) & (curr[:, 4] < 0.0)
            curr[hit_near, 4] *= -wall_cor
            curr[hit_near, 1] = y_min + r

            hit_far = (curr[:, 1] >= y_max - r) & (curr[:, 4] > 0.0)
            curr[hit_far, 4] *= -wall_cor
            curr[hit_far, 1] = y_max - r

            out[:, step_idx, :] = curr

        return out
