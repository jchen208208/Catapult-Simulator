# The machine itself, plus the background it stands in front of.

import pygame
import math
import random

WIDTH, HEIGHT = 1100, 620
FPS = 60
GROUND_Y = HEIGHT - 100

SKY_TOP        = (135, 185, 235)
SKY_BOTTOM     = (195, 225, 250)
HILL_FAR       = (120, 160, 100)
HILL_MID       = ( 90, 135,  75)
GROUND_TOP     = (100, 145,  65) # grass
GROUND_BOTTOM  = ( 75, 110,  45) # soil under it
CLOUD_COL      = (255, 255, 255)

# timber and iron
WOOD_LIGHT     = (205, 155,  80)
WOOD_MID       = (175, 125,  60)
WOOD_DARK      = (140,  95,  40)
WOOD_OUTLINE   = ( 90,  55,  20)
METAL          = (100, 100, 110)
METAL_DARK     = ( 60,  60,  70)
ROPE_COL       = (160, 130,  70)
HUD_COL        = (230, 230, 240)

ARM_MIN         = 80
ARM_MAX         = 200

# Angles are degrees off the positive x-axis, so 0 points right and 90 points straight up.
ARM_ANGLE_REST  = 120 # where it sits when you're not touching it
ARM_ANGLE_MIN   = 120 # can't be raised above rest
ARM_ANGLE_MAX   = 225 # as far back as you can drag it

DRAG_RADIUS = 24 # how close the mouse has to get to grab the handle or basket

SHAKE_START_ANGLE = 160 # starts straining here, early enough that you feel the pull-back
SHAKE_FREQUENCY   = 28
SHAKE_INTENSITY   = 6 # max displacement in px

# The projectile lets go at 90°, straight up.
# After that the arm overshoots and swings itself out like a damped spring until it settles back at rest.
RELEASE_ANGLE = 90

# α = -K·(θ − θ_rest) − D·ω
OSCILLATION_K = 40.0 # torsional spring constant, 1/s²
OSCILLATION_D = 3.0 # damping, 1/s
OSCILLATION_THRESHOLD_DEG = 2.0 # stop wobbling once it's this close to rest

random.seed(45) # same clouds every run

CLOUDS = [
    {
        "x": random.randint(100, WIDTH - 100),
        "y": random.randint(40, 160), # keep them up in the sky
        "r": random.randint(28, 55),
        "puffs": random.randint(3, 5) # each cloud is a few overlapping circles
    }
    for _ in range(6)
]

# One tile of hills, x=0 to x=WIDTH, repeated as the camera scrolls.
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

def get_ends(pivot, arm_len, angle_deg):
    """
    Both ends of the arm, returned as (load_end, throw_end).
    The basket end gets 70% of the length and the handle end the other 30%.
    """
    px, py = pivot
    
    rad = math.radians(angle_deg)
    
    throw_len = arm_len * 0.70
    load_len  = arm_len * 0.30
    
    # subtracting sin because pygame's y goes down and we want up
    throw_end = (
        px + math.cos(rad) * throw_len,
        py - math.sin(rad) * throw_len,
    )
    
    # handle end is just the same thing 180° round
    load_rad = math.radians(angle_deg + 180)
    load_end = (
        px + math.cos(load_rad) * load_len,
        py - math.sin(load_rad) * load_len,
    )
    
    return load_end, throw_end


def _draw_tiled_hills(surface, base_points, color, camera_x, parallax):
    """
    One hill layer, tiled sideways and scrolling at its own speed.
    parallax runs 0 to 1, where lower means further away and slower.
    Two tiles always cover the screen because a tile is exactly one screen wide.
    """
    dx = -int(camera_x * parallax)
    start_x = dx % WIDTH
    for tile_x in (start_x - WIDTH, start_x):
        pts = [(x + tile_x, y) for x, y in base_points]
        pygame.draw.polygon(surface, color, pts)


def draw_background(surface, camera_x=0):
    """
    Sky, hills, ground and clouds, back to front.

    Each layer moves at its own fraction of camera_x to fake depth.
    Clouds barely move at 15%, far hills 20%, mid hills 50%, and the ground goes 1:1.
    The sky is fixed and never scrolls at all.
    """
    for i in range(HEIGHT // 2):
        t = i / (HEIGHT // 2)
        r = int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * t)
        g = int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * t)
        b = int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * t)
        pygame.draw.line(surface, (r, g, b), (0, i), (WIDTH, i))

    pygame.draw.rect(surface, SKY_BOTTOM, (0, HEIGHT // 2, WIDTH, HEIGHT // 2))

    _draw_tiled_hills(surface, HILL_POINTS_FAR, HILL_FAR, camera_x, 0.20)
    _draw_tiled_hills(surface, HILL_POINTS_MID, HILL_MID, camera_x, 0.50)

    # tiled three across so it still covers the screen however far we've scrolled
    ground_x = -int(camera_x) % WIDTH
    for tile_x in (ground_x - WIDTH, ground_x, ground_x + WIDTH):
        pygame.draw.rect(surface, GROUND_TOP,
                         (tile_x, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
        pygame.draw.rect(surface, GROUND_BOTTOM,
                         (tile_x, GROUND_Y + 18, WIDTH, HEIGHT - GROUND_Y))

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
    A plank of the given thickness running between two points.
    """
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return # nothing to draw, and we're about to divide by it
    
    # normal to the line, which is what gives the plank its thickness
    nx = -dy / length
    ny =  dx / length
    half = thickness / 2
    
    # four corners, out along the normal from each end
    pts = [
        (x1 + nx * half, y1 + ny * half),
        (x2 + nx * half, y2 + ny * half),
        (x2 - nx * half, y2 - ny * half),
        (x1 - nx * half, y1 - ny * half),
    ]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, outline, pts, 2)


def _wheel(surface, cx, cy, radius):
    """
    Wooden wheel, spokes and a metal hub.
    """
    # outer rim
    pygame.draw.circle(surface, WOOD_MID,     (cx, cy), radius)
    pygame.draw.circle(surface, WOOD_OUTLINE, (cx, cy), radius, 3)
    
    inner = radius - 8
    pygame.draw.circle(surface, WOOD_DARK,    (cx, cy), inner)
    pygame.draw.circle(surface, WOOD_OUTLINE, (cx, cy), inner, 2)
    
    # eight spokes, one every 45°
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        sx = int(cx + math.cos(rad) * (inner - 2))
        sy = int(cy + math.sin(rad) * (inner - 2))
        pygame.draw.line(surface, WOOD_OUTLINE, (cx, cy), (sx, sy), 2)
    
    pygame.draw.circle(surface, METAL,      (cx, cy), 6)
    pygame.draw.circle(surface, METAL_DARK, (cx, cy), 6, 2)


def draw_catapult(surface, pivot, arm_len, angle_deg, hovering_handle, hovering_basket, shake_offset):
    """
    The whole machine: chassis, wheels, frame, arm, basket and handle.
    The two hovering flags just make the grab points light up.
    """
    px, py = pivot
    base_y    = GROUND_Y
    axle_y    = base_y - 18
    chassis_y = base_y - 10
    left_x    = px - 90 # wheel positions, relative to the pivot
    right_x   = px + 75
    wheel_r   = 22

    _plank(surface, left_x-10, chassis_y, right_x+10, chassis_y,
           20, WOOD_MID, WOOD_OUTLINE)

    _wheel(surface, left_x,  axle_y, wheel_r)
    _wheel(surface, right_x, axle_y, wheel_r)

    # axles poking out either side of the wheels
    pygame.draw.line(surface, METAL,
                     (left_x - wheel_r, axle_y),(left_x + wheel_r, axle_y), 5)
    pygame.draw.line(surface, METAL,
                     (right_x - wheel_r, axle_y),(right_x + wheel_r, axle_y), 5)

    # four beams up from the chassis to the pivot
    _plank(surface, left_x+10,  chassis_y-10, px-12, py, 10, WOOD_LIGHT, WOOD_OUTLINE)
    _plank(surface, left_x+38,  chassis_y-10, px-5,  py, 10, WOOD_LIGHT, WOOD_OUTLINE)
    _plank(surface, right_x-10, chassis_y-10, px+12, py, 10, WOOD_LIGHT, WOOD_OUTLINE)
    _plank(surface, right_x-38, chassis_y-10, px+5,  py, 10, WOOD_LIGHT, WOOD_OUTLINE)

    # brace across the middle
    brace_y = py + int((chassis_y - py) * 0.45)
    _plank(surface, left_x+18, brace_y, right_x-18, brace_y,
           9, WOOD_DARK, WOOD_OUTLINE)

    # centre post
    _plank(surface, px, py+5, px, chassis_y-5, 14, WOOD_MID, WOOD_OUTLINE)

    # pivot
    pygame.draw.circle(surface, METAL,      (px, py), 10)
    pygame.draw.circle(surface, METAL_DARK, (px, py), 10, 2)
    pygame.draw.circle(surface, METAL_DARK, (px, py), 4)

    load_end, throw_end = get_ends(pivot, arm_len, angle_deg)
    
    # shake goes on both ends so the arm moves as one piece
    lx = int(load_end[0])  + shake_offset
    ly = int(load_end[1])
    tx = int(throw_end[0]) + shake_offset
    ty = int(throw_end[1])

    _plank(surface, lx, ly, tx, ty, 12, WOOD_LIGHT, WOOD_OUTLINE)

    # basket on the throwing end, gold when you're hovering it
    cup_r = 16
    basket_color = (255, 220, 60) if hovering_basket else WOOD_MID
    pygame.draw.circle(surface, basket_color,     (tx, ty), cup_r)
    pygame.draw.circle(surface, WOOD_OUTLINE, (tx, ty), cup_r, 3)
    pygame.draw.circle(surface, WOOD_DARK,    (tx, ty), cup_r - 6)
    pygame.draw.circle(surface, WOOD_OUTLINE, (tx, ty), cup_r - 6, 2)

    # bit of rope hanging off the handle, purely decorative
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

    # the handle you drag to change the arm length
    handle_color = (255, 220, 60) if hovering_handle else (200, 160, 50)
    pygame.draw.circle(surface, handle_color, (lx, ly), 11)
    pygame.draw.circle(surface, WOOD_OUTLINE, (lx, ly), 11, 2)


class Catapult:
    """
    All the catapult's state and the logic that drives it.
    main.py makes one of these and calls handle_event(), update() and draw() every frame.
    """

    def __init__(self, pivot):
        self.pivot = pivot # the fixed point the arm turns around
        self.arm_length = 140
        self.arm_angle = ARM_ANGLE_REST

        self.dragging = False
        self.dragging_type = None # either "length" or "angle" depending on what you grabbed

        self.shake_offset = 0
        self.shake_timer = 0.0

        # Once you let go the arm swings itself out like a damped spring rather than snapping back.
        self.angular_vel = 0.0 # rad/s
        self.is_oscillating = False
        self.has_fired = False # goes True the frame the arm crosses RELEASE_ANGLE
        self.has_spawned = False # stops it firing twice on the same swing
        self.loaded_angle = ARM_ANGLE_REST # how far back it was pulled before release

        # written in update(), read in draw()
        self.hovering_handle = False
        self.hovering_basket = False

    def handle_event(self, event, mx, my, camera_x=0):
        """
        Handle one pygame event.

        The mouse position is passed in rather than read here, so main owns it.
        camera_x comes off the pivot so dragging still works once the machine has scrolled off to the left.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovering_handle:
                self.dragging = True
                self.dragging_type = "length"
                # kill any swing that's still going so the next release counts as a fresh shot
                self.is_oscillating = False
                self.angular_vel = 0.0
                self.has_fired = False
            elif self.hovering_basket:
                self.dragging = True
                self.dragging_type = "angle"
                # same reset as above
                self.is_oscillating = False
                self.angular_vel = 0.0
                self.has_fired = False

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            if self.dragging_type == "angle":
                self.is_oscillating = True
                self.has_fired = False
                self.has_spawned = False
                self.loaded_angle = self.arm_angle

                # Even a few degrees of pull has to carry the arm past 90° or nothing ever launches.
                # So work out how much velocity it's short by and just give it that.
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

            # atan2 gives -180 to 180, and we want 0 to 360
            if raw_angle < 0:
                raw_angle += 360

            if self.dragging_type == "length":
                # gets stiffer the further out you drag it, so the far end of the range is harder to reach
                load_ratio = (self.arm_length - ARM_MIN) / (ARM_MAX - ARM_MIN)
                load_ratio = max(0.0, min(1.0, load_ratio))
                resistance_factor = (load_ratio ** 2) * 0.85
                delta_len = (raw_len - self.arm_length) * (1.0 - resistance_factor)
                self.arm_length = max(ARM_MIN, min(ARM_MAX, self.arm_length + delta_len))

            elif self.dragging_type == "angle":
                self.arm_angle = max(ARM_ANGLE_MIN, min(ARM_ANGLE_MAX, raw_angle))

    def update(self, dt, mx, my, camera_x=0):
        """
        Hover detection, the strain shake, and the free swing after release.
        Called once a frame, before draw().
        """
        screen_pivot = (self.pivot[0] - camera_x, self.pivot[1])
        load_end, throw_end = get_ends(screen_pivot, self.arm_length, self.arm_angle)
        lx = int(load_end[0])
        ly = int(load_end[1])
        tx = int(throw_end[0])
        ty = int(throw_end[1])

        # hover checks run in screen space, hence taking the camera off the pivot above
        self.hovering_handle = math.hypot(mx - lx, my - ly) < DRAG_RADIUS
        self.hovering_basket = math.hypot(mx - tx, my - ty) < DRAG_RADIUS

        # only shakes while you're actually dragging it back past the threshold
        is_past_threshold = self.arm_angle > SHAKE_START_ANGLE
        if self.dragging and is_past_threshold:
            self.shake_timer += dt
            # how far past the threshold, 0 to 1
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

        # Free swing after release, as a damped harmonic oscillator: α = -K·(θ − θ_rest) − D·ω.
        # You let go at say 225° and the restoring force drags the arm back toward rest at 120°.
        # Inertia carries it straight past that, through the release angle at 90° and out to an overshoot on the far side.
        # Damping then eats the swing until it settles.
        if self.is_oscillating:
            theta_rest_rad = math.radians(ARM_ANGLE_REST)
            theta_rad = math.radians(self.arm_angle)

            alpha = ( -OSCILLATION_K * (theta_rad - theta_rest_rad)
                      - OSCILLATION_D * self.angular_vel )

            self.angular_vel += alpha * dt
            self.arm_angle += math.degrees(self.angular_vel * dt)

            # Fires the first time the arm crosses 90° on the way forward.
            # The angular_vel check is what stops the backswing setting it off again.
            if not self.has_fired and not self.has_spawned and self.arm_angle <= RELEASE_ANGLE and self.angular_vel <= 0:
                self.has_fired = True

            # small enough swing and slow enough, so call it done
            amplitude = abs(self.arm_angle - ARM_ANGLE_REST)
            if amplitude < OSCILLATION_THRESHOLD_DEG and abs(self.angular_vel) < 0.1:
                self.arm_angle = ARM_ANGLE_REST
                self.angular_vel = 0.0
                self.is_oscillating = False
                self.has_fired = False
                self.has_spawned = False

            # don't let the overshoot swing the arm through the frame
            if self.arm_angle < 45:
                self.arm_angle = 45.0
                self.angular_vel = 0.0
            elif self.arm_angle > ARM_ANGLE_MAX:
                self.arm_angle = ARM_ANGLE_MAX
                self.angular_vel = 0.0

    def draw(self, surface, font, camera_x=0):
        """
        The catapult is a world-space object, so it scrolls away off the left as the camera chases the projectile.
        """
        screen_pivot = (self.pivot[0] - camera_x, self.pivot[1])
        draw_catapult(
            surface, screen_pivot, self.arm_length, self.arm_angle,
            self.hovering_handle, self.hovering_basket, self.shake_offset
        )

    def get_launch_velocity(self):
        """
        Rough (vx, vy) in px/s straight off the arm length and angle.
        Nothing calls this, the real launch goes through cata_physics.launch_velocity instead.
        """
        speed = (self.arm_length / ARM_MAX) * 35 * 50 # 35 m/s at full extension, times px per metre
        launch_angle_rad = math.radians(self.arm_angle)
        vx = math.cos(launch_angle_rad) * speed
        vy = -math.sin(launch_angle_rad) * speed # negative because pygame's y is flipped
        return vx, vy
