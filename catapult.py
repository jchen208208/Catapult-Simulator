import pygame
import math
import random

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Screen dimensions
WIDTH, HEIGHT = 1100, 620
FPS = 60  # Frames per second
GROUND_Y = HEIGHT - 100  # Y position of the ground

# Color definitions (RGB tuples)
SKY_TOP        = (135, 185, 235)    # Top of sky gradient (light blue)
SKY_BOTTOM     = (195, 225, 250)    # Bottom of sky gradient (pale blue)
HILL_FAR       = (120, 160, 100)   # Distant hills (muted green)
HILL_MID       = ( 90, 135,  75)   # Mid-distance hills (darker green)
GROUND_TOP     = (100, 145,  65)   # Top layer of ground (grass green)
GROUND_BOTTOM  = ( 75, 110,  45)   # Bottom layer of ground (dark soil)
CLOUD_COL      = (255, 255, 255)   # Cloud color (white)

# Catapult wood and metal colors
WOOD_LIGHT     = (205, 155,  80)   # Light wood (birch/pine)
WOOD_MID       = (175, 125,  60)   # Medium wood (oak)
WOOD_DARK      = (140,  95,  40)   # Dark wood (walnut)
WOOD_OUTLINE   = ( 90,  55,  20)   # Wood outline (dark brown)
METAL          = (100, 100, 110)   # Metal axle (steel gray)
METAL_DARK     = ( 60,  60,  70)   # Dark metal (worn steel)
ROPE_COL       = (160, 130,  70)   # Rope color (hemp/jute)
HUD_COL        = (230, 230, 240)   # HUD text color (off-white)

# Arm length limits (in pixels)
ARM_MIN         = 80   # Minimum arm length
ARM_MAX         = 200  # Maximum arm length

# Angle limits for the arm (in degrees, measured from positive x-axis)
# 0° = pointing right, 90° = pointing up, 180° = pointing left, 270° = pointing down
ARM_ANGLE_REST  = 120  # Starting/rest position (pointing up-left)
ARM_ANGLE_MIN   = 120  # Minimum angle (cannot go above/rest position)
ARM_ANGLE_MAX   = 225  # Maximum angle (can drag down to 225°)

# Dragging and interaction settings
DRAG_RADIUS = 24   # Radius for detecting mouse hover over handle/basket (pixels)

# Shake animation settings
SHAKE_START_ANGLE = 160  # Angle at which shaking begins (earlier start for more visual feedback when pulling back)
SHAKE_FREQUENCY   = 28   # How fast the shake oscillates (higher = faster shake)
SHAKE_INTENSITY   = 6    # Maximum shake displacement in pixels

# Release and post-launch oscillation
# When the arm swings forward it releases the projectile at 90° (pointing straight up).
# After release the arm overshoots and oscillates like a damped harmonic oscillator
# until it settles back at the rest position (120°).
RELEASE_ANGLE = 90               # Angle (in degrees) at which the projectile is launched

# Damped harmonic oscillator constants (in rad/s² units).
# The arm behaves as a torsional spring with restoring acceleration:
#   α = -K · (θ − θ_rest) − D · ω
# and small oscillation amplitude threshold at which it locks to rest.
OSCILLATION_K = 40.0             # Restoring "spring" constant (1/s²)
OSCILLATION_D = 3.0              # Damping coefficient (1/s)
OSCILLATION_THRESHOLD_DEG = 2.0  # Amplitude below which oscillation stops (°)

# ==============================================================================
# CLOUD GENERATION
# ==============================================================================

# Seed for reproducible cloud positions
random.seed(45)

# Generate random clouds with positions and sizes
CLOUDS = [
    {
        "x": random.randint(100, WIDTH - 100),  # Random x position
        "y": random.randint(40, 160),           # Random y position (sky area)
        "r": random.randint(28, 55),             # Cloud radius
        "puffs": random.randint(3, 5)            # Number of "puffs" in each cloud
    }
    for _ in range(6)

    # Generates 6 random clouds for the background. The _ variable is a convention meaning the loop variable isn't used - it just repeats the iteration 6 times to create 6 cloud dictionaries with random positions, sizes, and puff counts.
]

# Hill profile definitions for parallax background tiling.
# Each list defines one tile (x=0 to x=WIDTH) that repeats as the camera scrolls.
HILL_POINTS_FAR = [
    (0, GROUND_Y-60), (120, GROUND_Y-130), (280, GROUND_Y-90),
    (450, GROUND_Y-160), (620, GROUND_Y-110), (800, GROUND_Y-175),
    (950, GROUND_Y-100), (WIDTH, GROUND_Y-80), (WIDTH, GROUND_Y), (0, GROUND_Y),
]
HILL_POINTS_MID = [
    (0, GROUND_Y-20), (80, GROUND_Y-70), (200, GROUND_Y-40),
    (350, GROUND_Y-95), (500, GROUND_Y-55), (680, GROUND_Y-110),
    (820, GROUND_Y-60), (1000, GROUND_Y-85), (WIDTH, GROUND_Y-30),
    (WIDTH, GROUND_Y), (0, GROUND_Y),
]

# ==============================================================================
# MATHEMATICAL HELPER FUNCTIONS
# ==============================================================================

def get_ends(pivot, arm_len, angle_deg):
    """
    Calculate the positions of both ends of the catapult arm.
    
    Args:
        pivot: Tuple (x, y) - the pivot point position
        arm_len: Float - total length of the arm
        angle_deg: Float - angle of the arm in degrees (0 = right, 90 = up, 180 = left)
    
    Returns:
        Tuple of two (x, y) tuples: (load_end, throw_end)
        - load_end: The counterweight/handle end (30% of arm length)
        - throw_end: The basket/projectile end (70% of arm length)
    """
    px, py = pivot  # Extract pivot coordinates
    
    # Convert angle from degrees to radians for math functions
    rad = math.radians(angle_deg)
    
    # Calculate lengths for each end (70% basket, 30% handle)
    throw_len = arm_len * 0.70  # Basket end is 70% of arm
    load_len  = arm_len * 0.30  # Handle end is 30% of arm
    
    # Calculate basket end position using trigonometry
    # math.cos gives x component, math.sin gives y component
    # In pygame, y increases downward, so we subtract sin to go upward
    throw_end = (
        px + math.cos(rad) * throw_len,
        py - math.sin(rad) * throw_len,
    )
    
    # Calculate handle end position (opposite direction, 180° offset)
    load_rad = math.radians(angle_deg + 180)
    load_end = (
        px + math.cos(load_rad) * load_len,
        py - math.sin(load_rad) * load_len,
    )
    
    return load_end, throw_end


# ==============================================================================
# DRAWING FUNCTIONS
# ==============================================================================

def _draw_tiled_hills(surface, base_points, color, camera_x, parallax):
    """
    Draw a tiled hill profile that scrolls with parallax.

    base_points defines one tile spanning x=0 to x=WIDTH.
    parallax (0.0–1.0) controls how much the layer moves relative to camera_x.
    Two tiles are always enough to cover the viewport because the tile
    width equals the screen width.
    """
    dx = -int(camera_x * parallax)
    start_x = dx % WIDTH
    for tile_x in (start_x - WIDTH, start_x):
        pts = [(x + tile_x, y) for x, y in base_points]
        pygame.draw.polygon(surface, color, pts)


def draw_background(surface, camera_x=0):
    """
    Draw the sky, hills, ground, and clouds with parallax scrolling.

    camera_x is the horizontal scroll offset in world pixels.  Each layer
    moves at a different fraction of camera_x to create depth:
      - Far hills:   20 %  (distant — barely moves)
      - Mid hills:   50 %  (intermediate)
      - Clouds:      15 %  (drifting in the sky)
      - Ground:     100 %  (moves 1:1 with the camera)
    The sky gradient is fixed and never scrolls.
    """
    # Sky gradient — drawn once, never scrolls with the camera
    for i in range(HEIGHT // 2):
        t = i / (HEIGHT // 2)
        r = int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * t)
        g = int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * t)
        b = int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * t)
        pygame.draw.line(surface, (r, g, b), (0, i), (WIDTH, i))

    pygame.draw.rect(surface, SKY_BOTTOM, (0, HEIGHT // 2, WIDTH, HEIGHT // 2))

    # Parallax hills — tiled profiles scroll at different rates
    _draw_tiled_hills(surface, HILL_POINTS_FAR, HILL_FAR, camera_x, 0.20)
    _draw_tiled_hills(surface, HILL_POINTS_MID, HILL_MID, camera_x, 0.50)

    # Ground — tiled so it always covers the screen at any scroll distance
    ground_x = -int(camera_x) % WIDTH
    for tile_x in (ground_x - WIDTH, ground_x, ground_x + WIDTH):
        pygame.draw.rect(surface, GROUND_TOP,
                         (tile_x, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
        pygame.draw.rect(surface, GROUND_BOTTOM,
                         (tile_x, GROUND_Y + 18, WIDTH, HEIGHT - GROUND_Y))

    # Clouds with parallax — drift slowly across the sky
    cloud_offset = -int(camera_x * 0.15)
    for c in CLOUDS:
        cx = c["x"] + cloud_offset
        cy, r = c["y"], c["r"]
        puffs = c["puffs"]
        for p in range(puffs):
            ox = int((p - puffs / 2) * r * 0.8)
            oy = -int(math.sin(p / puffs * math.pi) * r * 0.4)
            pygame.draw.circle(surface, CLOUD_COL, (cx + ox, cy + oy), r)


def _plank(surface, x1, y1, x2, y2, thickness, color, outline):
    """
    Draw a rotated plank/board between two points.
    
    Args:
        surface: Pygame surface to draw on
        x1, y1: Start point coordinates
        x2, y2: End point coordinates
        thickness: Width of the plank in pixels
        color: Fill color (RGB tuple)
        outline: Outline color (RGB tuple)
    """
    dx = x2 - x1  # Delta x between points
    dy = y2 - y1  # Delta y between points
    length = math.hypot(dx, dy)  # Calculate length using Pythagorean theorem
    if length == 0:
        return  # Avoid division by zero
    
    # Calculate normal vector (perpendicular to the line)
    nx = -dy / length
    ny =  dx / length
    half = thickness / 2
    
    # Create four corners of the plank rectangle
    pts = [
        (x1 + nx * half, y1 + ny * half),
        (x2 + nx * half, y2 + ny * half),
        (x2 - nx * half, y2 - ny * half),
        (x1 - nx * half, y1 - ny * half),
    ]
    pygame.draw.polygon(surface, color, pts)  # Fill the plank
    pygame.draw.polygon(surface, outline, pts, 2)  # Draw outline


def _wheel(surface, cx, cy, radius):
    """
    Draw a wooden wheel with spokes and metal hub.
    
    Args:
        surface: Pygame surface to draw on
        cx, cy: Center coordinates of the wheel
        radius: Radius of the wheel in pixels
    """
    # Main wheel body
    pygame.draw.circle(surface, WOOD_MID,     (cx, cy), radius)
    pygame.draw.circle(surface, WOOD_OUTLINE, (cx, cy), radius, 3)
    
    # Inner circle (darker wood)
    inner = radius - 8
    pygame.draw.circle(surface, WOOD_DARK,    (cx, cy), inner)
    pygame.draw.circle(surface, WOOD_OUTLINE, (cx, cy), inner, 2)
    
    # Draw spokes (8 spokes at 45° intervals)
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        sx = int(cx + math.cos(rad) * (inner - 2))
        sy = int(cy + math.sin(rad) * (inner - 2))
        pygame.draw.line(surface, WOOD_OUTLINE, (cx, cy), (sx, sy), 2)
    
    # Draw metal hub in center
    pygame.draw.circle(surface, METAL,      (cx, cy), 6)
    pygame.draw.circle(surface, METAL_DARK, (cx, cy), 6, 2)


def draw_catapult(surface, pivot, arm_len, angle_deg, hovering_handle, hovering_basket, shake_offset):
    """
    Draw the complete catapult including base, arm, basket, and handle.
    
    Args:
        surface: Pygame surface to draw on
        pivot: Tuple (x, y) - position of the arm's pivot point
        arm_len: Float - length of the catapult arm
        angle_deg: Float - current angle of the arm in degrees
        hovering_handle: Bool - whether mouse is hovering over the handle
        hovering_basket: Bool - whether mouse is hovering over the basket
        shake_offset: Int - horizontal shake displacement (0 if not shaking)
    """
    px, py = pivot
    base_y    = GROUND_Y
    axle_y    = base_y - 18     # Y position of wheel axles
    chassis_y = base_y - 10     # Y position of chassis top
    left_x    = px - 90         # Left wheel position (relative to pivot)
    right_x   = px + 75         # Right wheel position
    wheel_r   = 22              # Wheel radius

    # Draw main chassis plank (horizontal base)
    _plank(surface, left_x-10, chassis_y, right_x+10, chassis_y,
           20, WOOD_MID, WOOD_OUTLINE)

    # Draw two wheels
    _wheel(surface, left_x,  axle_y, wheel_r)
    _wheel(surface, right_x, axle_y, wheel_r)

    # Draw metal axle lines
    pygame.draw.line(surface, METAL,
                     (left_x - wheel_r, axle_y),(left_x + wheel_r, axle_y), 5)
    pygame.draw.line(surface, METAL,
                     (right_x - wheel_r, axle_y),(right_x + wheel_r, axle_y), 5)

    # Draw support beams (four planks connecting chassis to pivot)
    _plank(surface, left_x+10,  chassis_y-10, px-12, py, 10, WOOD_LIGHT, WOOD_OUTLINE)
    _plank(surface, left_x+38,  chassis_y-10, px-5,  py, 10, WOOD_LIGHT, WOOD_OUTLINE)
    _plank(surface, right_x-10, chassis_y-10, px+12, py, 10, WOOD_LIGHT, WOOD_OUTLINE)
    _plank(surface, right_x-38, chassis_y-10, px+5,  py, 10, WOOD_LIGHT, WOOD_OUTLINE)

    # Draw horizontal brace (reinforcement between support beams)
    brace_y = py + int((chassis_y - py) * 0.45)
    _plank(surface, left_x+18, brace_y, right_x-18, brace_y,
           9, WOOD_DARK, WOOD_OUTLINE)

    # Draw vertical post (central support)
    _plank(surface, px, py+5, px, chassis_y-5, 14, WOOD_MID, WOOD_OUTLINE)

    # Draw pivot point (metal axle)
    pygame.draw.circle(surface, METAL,      (px, py), 10)
    pygame.draw.circle(surface, METAL_DARK, (px, py), 10, 2)
    pygame.draw.circle(surface, METAL_DARK, (px, py), 4)

    # Calculate arm end positions
    load_end, throw_end = get_ends(pivot, arm_len, angle_deg)
    
    # Apply shake offset to BOTH ends (basket and handle)
    # The arm should shake as a whole, not just one end
    lx = int(load_end[0])  + shake_offset
    ly = int(load_end[1])
    tx = int(throw_end[0]) + shake_offset
    ty = int(throw_end[1])

    # Draw the arm plank
    _plank(surface, lx, ly, tx, ty, 12, WOOD_LIGHT, WOOD_OUTLINE)

    # Draw the basket (cup at the throwing end)
    cup_r = 16
    basket_color = (255, 220, 60) if hovering_basket else WOOD_MID
    pygame.draw.circle(surface, basket_color,     (tx, ty), cup_r)
    pygame.draw.circle(surface, WOOD_OUTLINE, (tx, ty), cup_r, 3)
    pygame.draw.circle(surface, WOOD_DARK,    (tx, ty), cup_r - 6)
    pygame.draw.circle(surface, WOOD_OUTLINE, (tx, ty), cup_r - 6, 2)

    # Draw rope hanging from handle (visual decoration)
    rope_len = 30
    steps    = 8
    for i in range(steps):
        t0  = i / steps
        t1  = (i + 0.6) / steps
        rx0 = lx + math.sin(t0 * math.pi * 3) * 3
        ry0 = ly + t0 * rope_len
        rx1 = lx + math.sin(t1 * math.pi * 3) * 3
        ry1 = ly + t1 * rope_len
        pygame.draw.line(surface, ROPE_COL,
                         (int(rx0), int(ry0)), (int(rx1), int(ry1)), 2)

    # Draw the handle (gold circle at load end)
    handle_color = (255, 220, 60) if hovering_handle else (200, 160, 50)
    pygame.draw.circle(surface, handle_color, (lx, ly), 11)
    pygame.draw.circle(surface, WOOD_OUTLINE, (lx, ly), 11, 2)


# ==============================================================================
# CATAPULT STATE CLASS
# ==============================================================================

class Catapult:
    """
    Owns all catapult state and logic.
    main.py creates one instance, then calls handle_event(), update(), and draw()
    once per frame.
    """

    def __init__(self, pivot):
        # pivot: (x, y) tuple — the fixed point the arm rotates around
        self.pivot = pivot
        self.arm_length = 140  # current arm length in pixels
        self.arm_angle = ARM_ANGLE_REST  # current arm angle in degrees

        self.dragging = False  # is the user holding a drag point?
        self.dragging_type = None  # "length" | "angle" | None

        self.shake_offset = 0  # horizontal pixel shake applied to arm
        self.shake_timer = 0.0  # seconds elapsed while shaking

        # Post-launch oscillation state.
        # After the user releases the mouse, the arm swings like a damped
        # harmonic oscillator instead of snapping instantly to rest.
        self.angular_vel = 0.0  # angular velocity of the arm (rad/s)
        self.is_oscillating = False  # whether the arm is in free swing
        self.has_fired = False  # set to True when the arm crosses RELEASE_ANGLE
        self.has_spawned = False  # True once the projectile has been created this oscillation
        self.loaded_angle = ARM_ANGLE_REST  # angle the arm was pulled back to before release

        # hover state — updated every frame in update(), read in draw()
        self.hovering_handle = False
        self.hovering_basket = False

    # ------------------------------------------------------------------
    def handle_event(self, event, mx, my, camera_x=0):
        """
        Process a single pygame event.
        mx, my: current mouse position (passed in from main so we don't
                call pygame.mouse.get_pos() inside here — cleaner separation).
        camera_x: horizontal world scroll offset — subtracted from the
                  pivot so mouse interactions work when the catapult has
                  scrolled partially off-screen.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovering_handle:
                self.dragging = True
                self.dragging_type = "length"
                # Stop any ongoing post-launch oscillation and reset fired flag
                # so the next release triggers a fresh launch.
                self.is_oscillating = False
                self.angular_vel = 0.0
                self.has_fired = False
            elif self.hovering_basket:
                self.dragging = True
                self.dragging_type = "angle"
                # Same reset as above when grabbing the basket.
                self.is_oscillating = False
                self.angular_vel = 0.0
                self.has_fired = False

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            if self.dragging_type == "angle":
                self.is_oscillating = True
                self.has_fired = False
                self.has_spawned = False
                self.loaded_angle = self.arm_angle

                # Give the arm enough initial velocity so it always swings
                # past RELEASE_ANGLE (90°) during the first oscillation,
                # even when pulled back only a few degrees from rest.
                disp_rad = math.radians(self.arm_angle - ARM_ANGLE_REST)
                need_rad = math.radians(ARM_ANGLE_REST - RELEASE_ANGLE)
                deficit = max(0.0, need_rad * need_rad - disp_rad * disp_rad)
                self.angular_vel = -2.5 * math.sqrt(OSCILLATION_K * deficit)

            self.dragging = False
            self.dragging_type = None

        elif event.type == pygame.MOUSEMOTION and self.dragging:
            screen_pivot_x = self.pivot[0] - camera_x
            px, py_pivot = screen_pivot_x, self.pivot[1]
            dx = mx - px
            dy = py_pivot - my  # flip y so up = positive

            raw_len = math.hypot(dx, dy)
            raw_angle = math.degrees(math.atan2(dy, dx))

            # atan2 returns -180 to 180 — convert negatives to 180-360 range
            if raw_angle < 0:
                raw_angle += 360

            if self.dragging_type == "length":
                # Resistance: gets progressively harder as arm extends
                load_ratio = (self.arm_length - ARM_MIN) / (ARM_MAX - ARM_MIN)
                load_ratio = max(0.0, min(1.0, load_ratio))
                resistance_factor = (load_ratio ** 2) * 0.85
                delta_len = (raw_len - self.arm_length) * (1.0 - resistance_factor)
                self.arm_length = max(ARM_MIN, min(ARM_MAX, self.arm_length + delta_len))

            elif self.dragging_type == "angle":
                # Clamp angle so user can only drag into the loaded range
                self.arm_angle = max(ARM_ANGLE_MIN, min(ARM_ANGLE_MAX, raw_angle))

    # ------------------------------------------------------------------
    def update(self, dt, mx, my, camera_x=0):
        """
        Called once per frame before draw().
        dt: seconds since last frame.
        mx, my: current mouse position.
        camera_x: horizontal world scroll offset — used for hover detection
                  so the mouse interacts with the screen-space arm ends.
        Updates hover detection and shake animation.
        """
        screen_pivot = (self.pivot[0] - camera_x, self.pivot[1])
        load_end, throw_end = get_ends(screen_pivot, self.arm_length, self.arm_angle)
        lx = int(load_end[0])
        ly = int(load_end[1])
        tx = int(throw_end[0])
        ty = int(throw_end[1])

        # Update hover flags — is the mouse close enough to either grab point?
        self.hovering_handle = math.hypot(mx - lx, my - ly) < DRAG_RADIUS
        self.hovering_basket = math.hypot(mx - tx, my - ty) < DRAG_RADIUS

        # Shake: only active while dragging the angle past the shake threshold
        is_past_threshold = self.arm_angle > SHAKE_START_ANGLE
        if self.dragging and is_past_threshold:
            self.shake_timer += dt
            # How far past the threshold are we? 0.0 to 1.0
            normalized = (
                    (self.arm_angle - SHAKE_START_ANGLE)
                    / (ARM_ANGLE_MAX - SHAKE_START_ANGLE)
            )
            intensity = max(0.3, min(1.0, normalized))
            self.shake_offset = int(
                math.sin(self.shake_timer * SHAKE_FREQUENCY) * intensity * SHAKE_INTENSITY
            )
        else:
            self.shake_offset = 0
            self.shake_timer = 0.0

        # Post-launch oscillation: damped harmonic oscillator.
        # When the user releases the mouse the arm is at the pulled-back
        # angle (e.g. 225°) and starts swinging forward.  The restoring
        # acceleration pulls it toward the rest angle (120°), but inertia
        # carries it past that point — past the release angle (90°) and
        # to an overshoot peak on the other side.  Damping then gradually
        # reduces the swing until the arm settles at the rest position.
        #
        # Physics:
        #   α = -K · (θ − θ_rest) − D · ω
        # where K is the torsional stiffness and D is the damping factor.
        # Spring-mass-damper system — the arm behaves like a pendulum
        # with a built-in restoring torque.
        if self.is_oscillating:
            theta_rest_rad = math.radians(ARM_ANGLE_REST)
            theta_rad = math.radians(self.arm_angle)

            # Restoring angular acceleration proportional to displacement
            # from rest (like Hooke's law for rotation).
            # Damping proportional to angular velocity.
            alpha = ( -OSCILLATION_K * (theta_rad - theta_rest_rad)
                      - OSCILLATION_D * self.angular_vel )

            # Euler integration of rotational motion.
            self.angular_vel += alpha * dt
            self.arm_angle += math.degrees(self.angular_vel * dt)

            # The first time the arm swings past the release angle (90°)
            # going from a loaded angle toward smaller values, we flag
            # has_fired so the main loop can call the physics launch.
            # The angular_vel check ensures it only triggers on the forward
            # swing, not when the arm passes 90° on the backswing.
            # has_spawned prevents re-triggering after the projectile has
            # already been created this oscillation.
            if not self.has_fired and not self.has_spawned and self.arm_angle <= RELEASE_ANGLE and self.angular_vel <= 0:
                self.has_fired = True

            # Once the oscillation amplitude and angular velocity are
            # both small enough, lock the arm smoothly at rest.
            amplitude = abs(self.arm_angle - ARM_ANGLE_REST)
            if amplitude < OSCILLATION_THRESHOLD_DEG and abs(self.angular_vel) < 0.1:
                self.arm_angle = ARM_ANGLE_REST
                self.angular_vel = 0.0
                self.is_oscillating = False
                self.has_fired = False
                self.has_spawned = False

            # Mild angular bounds so the arm never rotates past the
            # horizontal on the overshoot side or past the max loaded
            # position on the pull-back side.
            if self.arm_angle < 45:
                self.arm_angle = 45.0
                self.angular_vel = 0.0
            elif self.arm_angle > ARM_ANGLE_MAX:
                self.arm_angle = ARM_ANGLE_MAX
                self.angular_vel = 0.0

    # ------------------------------------------------------------------
    def draw(self, surface, font, camera_x=0):
        """
        Draw the catapult and HUD onto surface.
        font is passed in from main (main owns all pygame resources).
        camera_x: horizontal world scroll offset — the catapult is a
                  world-space object, so it scrolls off-screen as the
                  camera follows the projectile.
        """
        screen_pivot = (self.pivot[0] - camera_x, self.pivot[1])
        draw_catapult(
            surface, screen_pivot, self.arm_length, self.arm_angle,
            self.hovering_handle, self.hovering_basket, self.shake_offset
        )

    # ------------------------------------------------------------------
    def get_launch_velocity(self):
        """
        Returns the (vx, vy) launch velocity in pixels/second.
        Called by main.py at the moment of firing (not wired up yet).
        Speed scales with arm length; angle comes from the throw end direction.
        """
        speed = (self.arm_length / ARM_MAX) * 35 * 50  # 35 m/s max * pixels_per_metre
        launch_angle_rad = math.radians(self.arm_angle)
        vx = math.cos(launch_angle_rad) * speed
        vy = -math.sin(launch_angle_rad) * speed  # negative because pygame y is flipped
        return vx, vy
