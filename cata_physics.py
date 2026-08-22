"""
All the actual maths: launch speed, air drag, flight, bounces and rolling.

The arm is a lever with the pivot 30% of the way along it from the counterweight end.
Pulling the arm back lifts the counterweight, and letting go drops it again, which is where the projectile gets its energy from.

Distances are in pixels at 50 px to the metre, time in seconds, mass in kg.
y grows downward because that's how pygame works.
"""
import math
from catapult import get_ends, GROUND_Y, ARM_ANGLE_REST, ARM_MAX

GRAVITY = 490.5 # 9.81 m/s² x 50 px/m
PIXELS_PER_METER = 50
AIR_DENSITY = 1.225 # kg/m³ at sea level
MIN_SPEED = 1.0 # px/s, anything slower counts as stopped

# Turn this up to make things stop sooner after they land.
# Each object's own friction_coeff gets multiplied by it.
GROUND_FRICTION_MULTIPLIER = 2.5

# Counterweight mass at the reference arm length, which is ARM_MAX at 200 px.
# Tuned so a full 105° pull on the longest arm throws a 1 kg object at about 1750 px/s, or 35 m/s.
CW_MASS_BASE = 66.0

# How much of the counterweight's energy actually reaches the projectile.
# The rest goes into moving the arm and the counterweight itself.
ENERGY_EFFICIENCY = 0.50


def compute_counterweight_mass(arm_length):
    """
    Counterweight mass in kg for a given arm length.
    Longer arm, heavier counterweight, and it scales linearly: M = M_base x (L / L_max).
    """
    return CW_MASS_BASE * (arm_length / ARM_MAX)


def compute_drop_height(arm_length, loaded_angle_deg, release_angle_deg):
    """
    How far the counterweight drops, in px, as the arm swings from loaded to release.

    It hangs off the short end of the arm, 30% of the length from the pivot and 180° opposite the throw end.
    So y_cw = pivot_y + 0.3·L·sin(θ), and the drop is just the difference between the two angles.
    Δh = 0.3·L·[sin(θ_release) − sin(θ_loaded)]

    Over the range that actually gets used, 90° to 225°, that always comes out positive.
    """
    short_len = 0.30 * arm_length
    drop = short_len * (math.sin(math.radians(release_angle_deg)) -
                        math.sin(math.radians(loaded_angle_deg)))
    return max(0.0, drop)


def launch_velocity(arm_length, loaded_angle_deg, release_angle_deg,
                    obj_mass, cw_mass=None):
    """
    Starting velocity (vx, vy) of the projectile in px/s.

    The counterweight falls Δh and loses M·g·Δh of potential energy.
    A fraction η of that turns into ½mv² in the projectile, so v = √(2ηMgΔh/m).
    It leaves tangent to the arm's arc, which at release angle φ points at φ − 90°.

    cw_mass is worked out from the arm length if you don't pass one in.
    """
    if cw_mass is None:
        cw_mass = compute_counterweight_mass(arm_length)

    drop = compute_drop_height(arm_length, loaded_angle_deg, release_angle_deg)

    dPE = cw_mass * GRAVITY * drop
    KE = dPE * ENERGY_EFFICIENCY
    speed = math.sqrt(2.0 * KE / obj_mass)

    # the tip moves on a circle, so it comes off 90° round from the arm itself
    launch_angle_rad = math.radians(release_angle_deg - 90.0)

    vx = math.cos(launch_angle_rad) * speed
    vy = -math.sin(launch_angle_rad) * speed # minus because pygame's y goes down and we want up

    return (vx, vy)


def compute_drag(vx, vy, drag_coeff, radius):
    """
    Drag force on a sphere, returned in pixel-consistent units (kg·px/s²).

    F = ½·Cd·ρ·A·v², pointing the opposite way to the velocity.
    Cd is about 0.47 for a smooth sphere, ρ is air density, and A is the cross-section, πr².

    The formula only works in SI, so this converts to metres, does the sum in newtons, then converts the answer back.
    That way the caller can use a = F/m directly in pixel space.
    """
    v_sq = vx * vx + vy * vy
    v = math.sqrt(v_sq)

    # about to divide by v, and at this speed there'd be no drag worth having anyway
    if v < 0.01:
        return (0.0, 0.0)

    radius_m = radius / PIXELS_PER_METER
    area_m2 = math.pi * radius_m * radius_m
    v_ms = v / PIXELS_PER_METER

    F_mag_N = 0.5 * drag_coeff * AIR_DENSITY * area_m2 * v_ms * v_ms
    F_mag = F_mag_N * PIXELS_PER_METER # 1 N is 1 kg·m/s², so scaling by px/m gives kg·px/s²

    # (vx/v, vy/v) is the unit velocity vector, negated so drag pulls the other way
    drag_x = -F_mag * (vx / v)
    drag_y = -F_mag * (vy / v)

    return (drag_x, drag_y)


def update_flight(x, y, vx, vy, obj_mass, drag_coeff, radius, dt):
    """
    One euler step in the air: gravity, then drag, then move.
    """
    vy += GRAVITY * dt

    drag_x, drag_y = compute_drag(vx, vy, drag_coeff, radius)
    ax = drag_x / obj_mass
    ay = drag_y / obj_mass

    vx += ax * dt
    vy += ay * dt

    x += vx * dt
    y += vy * dt

    return (x, y, vx, vy)


def update_spin(spin_angle, spin_rate, dt):
    """
    Move the spin angle on by ω·Δt and wrap it back into [0, 2π).
    Spin has no effect on the trajectory, it only exists so the sprite tumbles.
    """
    spin_angle += spin_rate * dt

    # otherwise the angle just grows forever
    spin_angle %= 2.0 * math.pi

    return spin_angle


def has_landed(y, radius):
    """
    True once the bottom of the sphere has reached the ground.
    """
    return y + radius >= GROUND_Y


def compute_bounce(vy, restitution):
    """
    Vertical velocity after a bounce: vy_after = −e·vy_before.
    e = 1 would bounce forever and e = 0 would stick to the ground, so everything here sits somewhere in between.
    """
    return -vy * restitution


def update_rolling(x, vx, spin_angle, spin_rate, obj_mass, radius, friction_coeff, dt):
    """
    Move the projectile along the ground for one timestep.

    There are two regimes.
    While the contact point is still slipping, kinetic friction (μ·m·g) slows the centre of mass down and spins the sphere up at the same time.
    Once it's rolling properly (v = ωr) all that's left is rolling resistance, which is far smaller.

    I = ⅖mr² for a solid sphere.
    """
    inertia = 0.4 * obj_mass * radius * radius

    # How fast the contact point is moving over the ground, v_cm − ω·r.
    # Spinning forward makes it slower than the centre, and past ω > v/r it goes backwards.
    contact_v = vx - spin_rate * radius

    if abs(contact_v) > 0.5:
        # Cap friction at whatever would bring contact_v to exactly zero this frame, so it can't overshoot.
        # F = |contact_v| / ((1/m + r²/I)·dt), and with I = ⅖mr² the bracket comes out to 3.5/m.
        friction_max = abs(contact_v) * obj_mass / (3.5 * dt)
        friction_mag = min(friction_coeff * GROUND_FRICTION_MULTIPLIER * obj_mass * GRAVITY, friction_max)
        friction_mag = max(friction_mag, 0.0)

        # friction always opposes the slip, so it pulls back on a forward slip and pushes forward on a backward one
        sign = 1.0 if contact_v > 0 else -1.0

        old_vx = vx
        old_spin = spin_rate

        vx -= sign * (friction_mag / obj_mass) * dt

        # same force acting as a torque: α = F·r/I
        spin_rate += sign * (friction_mag * radius / inertia) * dt

        # if friction pushed either one past zero, it overshot, so pin it at zero instead
        if vx * old_vx < 0:
            vx = 0.0
        if spin_rate * old_spin < 0:
            spin_rate = 0.0

    else:
        if abs(vx) > MIN_SPEED:
            # The 0.08 is just what gave a believable stopping distance, the object's own friction_coeff does the rest.
            roll_resist = 0.08 * friction_coeff * GROUND_FRICTION_MULTIPLIER * obj_mass * GRAVITY
            vx -= (vx / abs(vx)) * (roll_resist / obj_mass) * dt

            spin_rate = vx / radius # no slip means ω is locked to v/r

            if abs(vx) < MIN_SPEED:
                vx = 0.0
                spin_rate = 0.0
        else:
            vx = 0.0
            spin_rate = 0.0

    # x only, we're on the ground
    x += vx * dt

    spin_angle += spin_rate * dt
    spin_angle %= 2.0 * math.pi

    return (x, vx, spin_angle, spin_rate)


def has_stopped(vx, spin_rate):
    """
    True once it has stopped moving and stopped spinning.
    """
    return abs(vx) < MIN_SPEED and abs(spin_rate) < MIN_SPEED


def get_launch_point(pivot, arm_length, release_angle_deg):
    """
    Where the basket is, which is where the projectile starts from.
    """
    _, throw_end = get_ends(pivot, arm_length, release_angle_deg)
    return throw_end
