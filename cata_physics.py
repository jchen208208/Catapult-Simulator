"""
Physics simulation for the catapult projectile.
Handles launch velocity (counterweight-based), drag (air resistance),
flight, bounce, and rolling.

Physical model (counterweight trebuchet):
  The arm is a lever with the pivot at 30 % of its length from the
  counterweight end.  When the arm is pulled back to the *loaded angle*
  the counterweight is raised; when released it falls, converting
  gravitational potential energy into projectile kinetic energy.

All spatial units are in pixels; time in seconds; mass in kg.
The pixel↔meter conversion factor is PIXELS_PER_METER (50 px/m).
"""
import math
from catapult import get_ends, GROUND_Y, ARM_ANGLE_REST, ARM_MAX

# Gravity acceleration in pixels/second².
# 9.81 m/s² × 50 px/m = 490.5 px/s²
GRAVITY = 490.5

# Conversion factor: how many pixels fit into one metre.
# Used to translate between pixel-space and real-world SI units.
PIXELS_PER_METER = 50

# Density of air at sea level, 15 °C, in kg/m³.
# Used in the drag-force equation.
AIR_DENSITY = 1.225

# Speed threshold below which the projectile is considered "stopped" (px/s).
MIN_SPEED = 1.0

# Global multiplier for ground friction during rolling.
# Increase to make objects stop sooner after landing.
# Each object's friction_coeff is multiplied by this value.
GROUND_FRICTION_MULTIPLIER = 2.5

# Counterweight mass at the reference arm length (ARM_MAX = 200 px).
# Calibrated so that at max arm and full 105° pull-back the launch speed
# reaches ≈ 1750 px/s (35 m/s) for a 1 kg projectile.
CW_MASS_BASE = 66.0

# Fraction of the counterweight's gravitational PE that ends up as
# projectile KE.  The rest goes into arm motion, counterweight KE,
# friction, etc.
ENERGY_EFFICIENCY = 0.50


def compute_counterweight_mass(arm_length):
    """
    Return the mass (kg) of the counterweight for a given arm length.

    Longer arms require heavier counterweights because they move a larger
    mass and store more energy.  Mass scales linearly with arm length:
        M = M_base × (L / L_max)
    Linear scaling is a reasonable first-order model — the cross-sectional
    dimensions of the counterweight package grow proportionally to the
    arm length.
    """
    return CW_MASS_BASE * (arm_length / ARM_MAX)


def compute_drop_height(arm_length, loaded_angle_deg, release_angle_deg):
    """
    Return the vertical distance (px) the counterweight falls as the arm
    swings from the loaded angle to the release angle.

    Geometry:
      The counterweight is attached to the *short end* of the arm, which
      is 30 % of the total arm length from the pivot (at the angle
      opposite the throw end, i.e. θ + 180°).
      Its y-coordinate (Pygame, y-down) is:
          y_cw = pivot_y + 0.3·L·sin(θ)
      The drop height is the difference in y_cw between the two angles:
          Δh = y_cw(release) − y_cw(loaded)
             = 0.3·L·[sin(θ_release) − sin(θ_loaded)]
      Since θ_loaded > θ_release (the arm swings forward), and for
       angles in the relevant range (90°–225°) the sine decreases,
      sin(θ_release) − sin(θ_loaded) > 0, so Δh > 0 — the counterweight
      falls.
    """
    short_len = 0.30 * arm_length
    drop = short_len * (math.sin(math.radians(release_angle_deg)) -
                        math.sin(math.radians(loaded_angle_deg)))
    return max(0.0, drop)


def launch_velocity(arm_length, loaded_angle_deg, release_angle_deg,
                    obj_mass, cw_mass=None):
    """
    Compute the initial velocity (vx, vy) of the projectile in px/s.

    Physics model (counterweight catapult):
      The counterweight of mass M falls a vertical distance Δh, losing
      gravitational potential energy:
          ΔPE = M · g · Δh
      A fraction η of this energy is transferred to the projectile:
          ½ m v² = η · ΔPE
      →  v = √(2 η M g Δh / m)

      The velocity direction is tangential to the arm's rotation arc.
      At release angle φ the tip velocity points at φ − 90° (perpendicular
      to the arm, in the direction of swing).

    Parameters:
      arm_length:        total arm length in pixels
      loaded_angle_deg:  angle the arm was pulled back to (e.g. 225°)
       release_angle_deg: angle at which the projectile releases (e.g. 90°)
      obj_mass:          projectile mass in kg
      cw_mass:           counterweight mass in kg (auto-computed if None)
    """
    if cw_mass is None:
        cw_mass = compute_counterweight_mass(arm_length)

    drop = compute_drop_height(arm_length, loaded_angle_deg, release_angle_deg)

    # Gravitational potential energy lost by the counterweight (J in
    # pixel-consistent units: kg · px²/s²).
    dPE = cw_mass * GRAVITY * drop

    # Kinetic energy transferred to the projectile.
    KE = dPE * ENERGY_EFFICIENCY

    # Launch speed from kinetic energy:  v = √(2 KE / m)
    speed = math.sqrt(2.0 * KE / obj_mass)

    # The throw-end of the arm moves on a circle.
    # When the arm is at angle φ, the tangential velocity of the tip
    # (direction of release) is at φ − 90° in our coordinate system
    # (0° = right, 90° = up).
    launch_angle_rad = math.radians(release_angle_deg - 90.0)

    # Decompose speed into x and y components.
    # cos for x, sin for y.  The minus sign on vy flips the y-axis
    # because Pygame's y increases downward but we want +y = up.
    vx = math.cos(launch_angle_rad) * speed
    vy = -math.sin(launch_angle_rad) * speed

    return (vx, vy)


def compute_drag(vx, vy, drag_coeff, radius):
    """
    Compute the drag force vector on a spherical projectile (px·kg/s²).

    Physics (quadratic drag / air resistance):
      The drag force on a sphere moving through a fluid is:
          F_drag = ½ · Cd · ρ · A · v²   (opposite to velocity)
      where:
        Cd = drag coefficient (dimensionless, ~0.47 for a smooth sphere)
        ρ  = air density (kg/m³)
        A  = cross-sectional area of the sphere = π r²  (m²)
        v  = speed (m/s)

      The implementation:
        1. Convert pixel quantities to SI: radius → metres, v → m/s.
        2. Compute the scalar drag magnitude in Newtons.
        3. Multiply by PIXELS_PER_METER to obtain a force in
           pixel-consistent units (kg·px/s²), which allows the caller
           to use a = F/m directly in pixel space.
        4. Project onto the unit vector opposite to (vx, vy).
    """
    # Squared speed and speed in pixel units (px/s).
    v_sq = vx * vx + vy * vy
    v = math.sqrt(v_sq)

    # Avoid division by zero when velocity is essentially zero.
    if v < 0.01:
        return (0.0, 0.0)

    # Convert radius from pixels to metres for the SI formula.
    radius_m = radius / PIXELS_PER_METER

    # Cross-sectional area of the sphere in m²: A = π r²
    area_m2 = math.pi * radius_m * radius_m

    # Convert speed from px/s to m/s.
    v_ms = v / PIXELS_PER_METER

    # Drag magnitude in Newtons:  ½ · Cd · ρ · A · v²
    F_mag_N = 0.5 * drag_coeff * AIR_DENSITY * area_m2 * v_ms * v_ms

    # Convert force from Newtons to pixel-consistent units (kg·px/s²).
    # 1 N = 1 kg·m/s² → multiply by PPM to get kg·px/s².
    F_mag = F_mag_N * PIXELS_PER_METER

    # The drag direction is opposite to the velocity vector.
    # Unit vector of velocity = (vx/v, vy/v); negate it.
    drag_x = -F_mag * (vx / v)
    drag_y = -F_mag * (vy / v)

    return (drag_x, drag_y)


def update_flight(x, y, vx, vy, obj_mass, drag_coeff, radius, dt):
    """
    Advance the projectile state by one timestep dt (seconds).

    Applies:
      1. Gravity (constant downward acceleration GRAVITY in px/s²).
      2. Drag (velocity-dependent deceleration from air resistance).
      3. Euler integration to update position from velocity.

    Newton's Second Law:  ΣF = m a
      - Gravity:  F_g = m · g  (downward, so added to vy, which
                  already carries a minus sign for Pygame's y-down).
      - Drag: returned by compute_drag() in kg·px/s².
      - Acceleration from drag:  a = F_drag / m  (px/s²).
    """
    # Apply gravity:  Δvy = g · Δt  (g = +490.5 px/s², downward).
    vy += GRAVITY * dt

    # Obtain drag force vector (kg·px/s²) from the drag model.
    drag_x, drag_y = compute_drag(vx, vy, drag_coeff, radius)

    # Newton's Second Law: acceleration = force / mass (px/s²).
    ax = drag_x / obj_mass
    ay = drag_y / obj_mass

    # Update velocity:  v_new = v_old + a · Δt
    vx += ax * dt
    vy += ay * dt

    # Update position:  pos_new = pos_old + v · Δt
    x += vx * dt
    y += vy * dt

    return (x, y, vx, vy)


def update_spin(spin_angle, spin_rate, dt):
    """
    Advance the projectile's spin angle (radians) by dt seconds.

    spin_rate is the angular velocity (rad/s).
    The new angle = old angle + ω · Δt, wrapped to [0, 2π).
    Spin does not affect the flight trajectory in this model — it is
    purely a visual parameter tracked for the rolling phase.
    """
    spin_angle += spin_rate * dt

    # Normalise to the range [0, 2π) so the angle doesn't grow without bound.
    spin_angle %= 2.0 * math.pi

    return spin_angle


def has_landed(y, radius):
    """
    Return True when the projectile has reached the ground plane.

    The projectile is a sphere of radius `radius` centred at (x, y).
    Its lowest point is at y + radius (Pygame y increases downward).
    GROUND_Y is the y-coordinate of the ground surface.
    Landing occurs when y + radius >= GROUND_Y.
    """
    return y + radius >= GROUND_Y


def compute_bounce(vy, restitution):
    """
    Compute the post-bounce vertical velocity.

    Physics:
      When a bouncing ball hits the ground, the vertical component of
      velocity reverses direction and is reduced by the coefficient of
      restitution e (0 ≤ e ≤ 1).
        vy_after = −e · vy_before
      e = 1  → perfectly elastic (full energy, no loss)
      e = 0  → perfectly inelastic (sticks to ground)
    The negative sign flips the direction (downward → upward).
    """
    return -vy * restitution


def update_rolling(x, vx, spin_angle, spin_rate, obj_mass, radius, friction_coeff, dt):
    """
    Advance the projectile during the ground-rolling phase.

    Two regimes:
      A) Slipping (|v_contact| > 0.5):
         The contact point of the sphere moves relative to the ground.
         Kinetic friction opposes this slip:
           F_friction = μ_k · m · g
         This force:
           • decelerates the centre-of-mass (linear motion)
           • exerts a torque that changes the spin rate
         For a solid sphere the moment of inertia is  I = ⅖ m r².

      B) Pure rolling (|v_contact| ≤ 0.5):
         The sphere rolls without slipping (v = ω r).
         Only rolling resistance (much smaller than sliding friction)
         acts to gradually bring it to rest:
           F_roll = μ_roll · m · g    (μ_roll = 0.01 here)
    """
    # Moment of inertia of a uniform solid sphere:  I = ⅖ m r²
    inertia = 0.4 * obj_mass * radius * radius

    # Velocity of the sphere's contact point relative to the ground.
    # For a sphere of radius r:  v_contact = v_cm − ω · r
    # When spinning forward (ω > 0) the contact point moves slower
    # than the centre; when ω > v/r the contact point reverses.
    contact_v = vx - spin_rate * radius

    # ── Regime A: slipping ──────────────────────────────────────────────
    if abs(contact_v) > 0.5:
        # Max friction that would just bring contact_v to zero (no overshoot).
        #   F_needed = |contact_v| / ((1/m + r²/I) · dt)
        #   I = ⅖ m r²  →  1/m + r²/I = 1/m + r²/(⅖ m r²) = 1/m + 2.5/m = 3.5/m
        friction_max = abs(contact_v) * obj_mass / (3.5 * dt)
        friction_mag = min(friction_coeff * GROUND_FRICTION_MULTIPLIER * obj_mass * GRAVITY, friction_max)
        friction_mag = max(friction_mag, 0.0)

        # Sign of the friction: opposes the slip direction.
        # contact_v > 0 → slip forward → friction pulls backward.
        # contact_v < 0 → slip backward → friction pushes forward.
        sign = 1.0 if contact_v > 0 else -1.0

        # Save pre-friction values to detect sign flips.
        old_vx = vx
        old_spin = spin_rate

        # Linear deceleration:  a = F / m  (px/s²), opposite to slip.
        # Δv = a · Δt = (F/m) · Δt
        vx -= sign * (friction_mag / obj_mass) * dt

        # Angular acceleration from friction torque:
        # τ = F · r   →   α = τ / I = F·r / (⅖ m r²) = (5F) / (2 m r)
        # Δω = α · Δt
        spin_rate += sign * (friction_mag * radius / inertia) * dt

        # Prevent overshoot: if friction would flip the sign of either
        # vx or spin_rate past zero, clamp to zero.
        if vx * old_vx < 0:
            vx = 0.0
        if spin_rate * old_spin < 0:
            spin_rate = 0.0

    # ── Regime B: pure rolling ──────────────────────────────────────────
    else:
        if abs(vx) > MIN_SPEED:
            # Rolling resistance — proportional to surface roughness.
            # friction_coeff captures how rough the object is; the 0.08
            # base multiplier gives a believable stopping distance.
            roll_resist = 0.08 * friction_coeff * GROUND_FRICTION_MULTIPLIER * obj_mass * GRAVITY
            vx -= (vx / abs(vx)) * (roll_resist / obj_mass) * dt

            # In pure rolling the angular velocity is locked to vx:
            # ω = v / r   (no slip condition)
            spin_rate = vx / radius

            # If rolling resistance has slowed us below the threshold
            # we stop completely.
            if abs(vx) < MIN_SPEED:
                vx = 0.0
                spin_rate = 0.0
        else:
            # Already below the speed threshold — stationary.
            vx = 0.0
            spin_rate = 0.0

    # Advance position (x only — we're already on the ground).
    x += vx * dt

    # Advance spin angle for visual tracking.
    spin_angle += spin_rate * dt
    spin_angle %= 2.0 * math.pi

    return (x, vx, spin_angle, spin_rate)


def has_stopped(vx, spin_rate):
    """
    Return True if both linear and angular motion are below threshold.

    The projectile is considered at rest when both its centre-of-mass
    speed and its spin rate fall below MIN_SPEED (= 1.0 px/s, 1.0 rad/s).
    """
    return abs(vx) < MIN_SPEED and abs(spin_rate) < MIN_SPEED


def get_launch_point(pivot, arm_length, release_angle_deg):
    """
    Return the (x, y) pixel position of the catapult's throw-end basket
    at the specified arm configuration.

    This is the point from which the projectile begins its flight.
    Delegates to the get_ends() helper imported from catapult.py.
    """
    # get_ends returns (load_end, throw_end); we discard load_end.
    _, throw_end = get_ends(pivot, arm_length, release_angle_deg)
    return throw_end
