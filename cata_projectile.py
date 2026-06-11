from __future__ import annotations

import math
import os
import pygame
from cata_physics import (
    update_flight, update_spin, has_landed,
    compute_bounce, update_rolling, has_stopped
)
from catapult import GROUND_Y


# ==============================================================================
# SPRITE IMAGE LOADING
# ==============================================================================

_SPRITE_FILES = {
    "Boulder":    "cata_rock_sprite.png",
    "Cannonball": "cata_cannonball_sprite.png",
    "Watermelon": "cata_watermelon_sprite.png",
    "Soccer Ball":"cata_soccerball_sprite.png",
    "Anvil":      "cata_anvil_sprite.png",
    "Pumpkin":    "cata_pumpkin_sprite.png",
}

_IMAGES = {}  # dict[str, pygame.Surface | None]

def _load_sprite(name: str) -> pygame.Surface | None:
    """Load a single sprite image by object name. Returns None on failure."""
    filename = _SPRITE_FILES.get(name)
    if not filename:
        return None
    path = os.path.join(os.path.dirname(__file__), "cata_assets", filename)
    try:
        img = pygame.image.load(path)
        if img.get_bytesize() == 4:
            img = img.convert_alpha()
        else:
            img = img.convert()
        return img
    except (pygame.error, FileNotFoundError):
        return None

def _get_sprite(name: str) -> pygame.Surface | None:
    """Lazy-load and return the sprite for *name*."""
    if name not in _IMAGES:
        _IMAGES[name] = _load_sprite(name)
    return _IMAGES[name]


# ==============================================================================
# OBJECT DRAWING — sprite-based
# ==============================================================================

def draw_object(surface, obj, cx, cy, spin_angle=0.0, scale=1.0):
    """
    Draw any projectile object centred at screen position (cx, cy).
    Uses pre-loaded sprite images with rotation. Falls back to a plain
    circle when a sprite is missing or fails to load.
    """
    r = int(obj.radius * scale * obj.display_scale)
    img = _get_sprite(obj.name)

    if img is not None:
        size = max(1, r * 2)
        scaled = pygame.transform.smoothscale(img, (size, size))
        if spin_angle != 0.0:
            rotated = pygame.transform.rotate(scaled, -math.degrees(spin_angle))
        else:
            rotated = scaled
        rect = rotated.get_rect(center=(int(cx), int(cy)))
        surface.blit(rotated, rect)
    else:
        # fallback — plain circle
        fb_r = int(obj.radius * scale)
        pygame.draw.circle(surface, obj.color, (int(cx), int(cy)), fb_r)
        pygame.draw.circle(surface, obj.outline_color, (int(cx), int(cy)), fb_r, 2)


# ==============================================================================
# PROJECTILE CLASS
# ==============================================================================

class Projectile:
    """
    Owns one projectile's full lifecycle:
        spawn → flying → bouncing → rolling → stopped

    State machine:
        "flying"   — airborne, gravity + drag applied every frame
        "bouncing" — just hit the ground, vy has been flipped,
                     this state lasts exactly ONE frame to let vy resolve
                     before deciding whether to fly again or roll
        "rolling"  — on the ground, friction decelerating it
        "stopped"  — fully at rest
    """

    def __init__(self, obj, x, y, vx, vy):
        self.obj   = obj        # ProjectileObject — mass, drag, color etc.
        self.x     = float(x)  # world x position in pixels
        self.y     = float(y)  # world y position in pixels
        self.vx    = float(vx) # horizontal velocity px/s
        self.vy    = float(vy) # vertical velocity px/s (+ve = downward in pygame)

        # Spin angle in radians — purely visual
        self.spin_angle = 0.0

        # Spin rate: proportional to launch speed.
        # obj.spin_factor controls how fast each object visually tumbles.
        launch_speed    = math.hypot(vx, vy)
        self.spin_rate  = launch_speed * obj.spin_factor * 0.01

        # Trail: list of (world_x, world_y) recorded each flying frame
        self.trail      = []
        self.trail_max  = 200    # keep last 200 positions (~3.3 seconds at 60fps)
        self.trail_fade = 1.0    # global trail fade — decreases during rolling

        # State machine — one of: "flying", "bouncing", "rolling", "stopped"
        self.state = "flying"

        # Bounce limiter — after max_bounces, skip straight to rolling
        # regardless of remaining vy
        self.bounce_count = 0
        self.max_bounces  = 3

    # ── convenience property ──────────────────────────────────────────────
    @property
    def stopped(self):
        return self.state == "stopped"

    # ── update ────────────────────────────────────────────────────────────
    def update(self, dt):
        """Advance physics by dt seconds. Called once per frame by main.py."""

        if self.state == "flying":
            # 1. Record current position to trail before moving
            self.trail.append((self.x, self.y))
            if len(self.trail) > self.trail_max:
                self.trail.pop(0)   # drop oldest point

            # 2. Apply gravity + drag, update position
            self.x, self.y, self.vx, self.vy = update_flight(
                self.x, self.y, self.vx, self.vy,
                self.obj.mass, self.obj.drag_coeff, self.obj.radius, dt
            )

            # 3. Advance visual spin
            self.spin_angle = update_spin(self.spin_angle, self.spin_rate, dt)

            # 4. Check for ground contact
            if has_landed(self.y, self.obj.radius):
                # Clamp to ground so object never sinks below surface
                self.y = GROUND_Y - self.obj.radius

                # Apply bounce: flip vy and reduce by restitution
                self.vy = compute_bounce(self.vy, self.obj.restitution)
                self.bounce_count += 1

                # Decide whether to bounce again or start rolling.
                # 50 px/s ≈ 1 m/s — below this the bounce is invisible.
                if abs(self.vy) < 50 or self.bounce_count >= self.max_bounces:
                    # bounce too weak or used all bounces → roll
                    self.vy    = 0.0
                    self.state = "rolling"
                else:
                    # Still enough vy to go airborne again.
                    # Use "bouncing" for ONE frame so the position clamp
                    # and velocity flip are both applied before the next
                    # flying update — prevents the double-launch bug.
                    self.state = "bouncing"

        elif self.state == "bouncing":
            # This state exists purely as a one-frame buffer.
            # vy was already flipped last frame. Now we just check:
            # if vy is upward (negative in pygame) → go back to flying.
            # This gives the physics one settled frame before resuming flight.
            if self.vy < 0:
                self.state = "flying"
            else:
                # vy somehow not upward — just roll
                self.vy    = 0.0
                self.state = "rolling"

        elif self.state == "rolling":
            # Fade the trail as the object rolls
            self.trail_fade = max(0.0, self.trail_fade - 0.008)

            # Apply ground friction, advance position and spin
            self.x, self.vx, self.spin_angle, self.spin_rate = update_rolling(
                self.x, self.vx, self.spin_angle, self.spin_rate,
                self.obj.mass, self.obj.radius, self.obj.friction_coeff, dt
            )

            # Check if both linear and angular motion have stopped
            if has_stopped(self.vx, self.spin_rate):
                self.state = "stopped"

        # "stopped" → nothing to update

    # ── draw ──────────────────────────────────────────────────────────────
    def draw(self, surface, camera_x):
        """
        Draw trail, shadow, and object onto surface.
        camera_x is subtracted from all world x positions to get screen x.
        """
        # Screen x of the object's center
        sx = self.x - camera_x
        sy = self.y

        # ── Trail ─────────────────────────────────────────────────────────
        # Oldest points are at the front of the list (index 0), newest at back.
        # The trail_fade multiplier dims the whole trail during rolling.
        trail_len = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            t = i / max(trail_len, 1)
            r = int(self.obj.radius * t * 0.25)
            if r < 1:
                continue
            fade = self.trail_fade * (0.10 + t * 0.60)
            c = tuple(int(ch * fade) for ch in self.obj.color)
            pygame.draw.circle(surface, c,
                               (int(tx - camera_x), int(ty)), r)

        # ── Ground shadow (only while airborne) ───────────────────────────
        if self.state in ("flying", "bouncing"):
            height_above = GROUND_Y - self.y
            # shadow_scale: 1.0 when on ground, shrinks to 0.2 at height 400px
            shadow_scale = max(0.2, 1.0 - height_above / 400.0)
            sw = int(self.obj.radius * 2.2 * shadow_scale)
            sh = int(self.obj.radius * 0.45 * shadow_scale)
            if sw > 1 and sh > 1:
                shadow_rect = pygame.Rect(
                    int(sx - sw / 2),
                    GROUND_Y - sh // 2,
                    sw, sh
                )
                pygame.draw.ellipse(surface, (20, 25, 15), shadow_rect)

        # ── Object ────────────────────────────────────────────────────────
        draw_object(surface, self.obj, sx, sy, self.spin_angle)