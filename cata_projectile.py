from __future__ import annotations

import math
import os
import pygame
from cata_physics import (
    update_flight, update_spin, has_landed,
    compute_bounce, update_rolling, has_stopped
)
from catapult import GROUND_Y


# Four states, in order: flying -> bouncing -> rolling -> stopped.
# This file owns the sprite loading, the state machine and the drawing.

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
    """Load one sprite by object name, or None if it isn't there."""
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
    """Load on first use and cache it after that, including the failures."""
    if name not in _IMAGES:
        _IMAGES[name] = _load_sprite(name)
    return _IMAGES[name]


def draw_object(surface, obj, cx, cy, spin_angle=0.0, scale=1.0):
    """
    Draw a projectile centred on (cx, cy), rotated by spin_angle.
    If the sprite didn't load you get a plain circle instead, which at least keeps the thing visible.
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
        fb_r = int(obj.radius * scale)
        pygame.draw.circle(surface, obj.color, (int(cx), int(cy)), fb_r)
        pygame.draw.circle(surface, obj.outline_color, (int(cx), int(cy)), fb_r, 2)


class Projectile:
    """
    One projectile, from the moment it leaves the basket until it stops.

    flying: in the air with gravity and drag on it.
    bouncing: just hit the ground and vy has been flipped, and it only sits here for a single frame.
    rolling: on the ground with friction slowing it down.
    stopped: done.
    """

    def __init__(self, obj, x, y, vx, vy):
        self.obj   = obj
        self.x     = float(x)
        self.y     = float(y)
        self.vx    = float(vx)
        self.vy    = float(vy) # positive is downward, pygame style

        self.spin_angle = 0.0

        # faster launch, faster tumble, scaled per object by spin_factor
        launch_speed    = math.hypot(vx, vy)
        self.spin_rate  = launch_speed * obj.spin_factor * 0.01

        self.trail      = []
        self.trail_max  = 200 # roughly 3.3 seconds of positions at 60fps
        self.trail_fade = 1.0

        self.state = "flying"

        self.bounce_count = 0
        self.max_bounces  = 3 # after this it stops bouncing and just rolls

    @property
    def stopped(self):
        return self.state == "stopped"

    def update(self, dt):
        """Step the physics forward by dt seconds, once per frame from main.py."""

        if self.state == "flying":
            self.trail.append((self.x, self.y))
            if len(self.trail) > self.trail_max:
                self.trail.pop(0)

            self.x, self.y, self.vx, self.vy = update_flight(
                self.x, self.y, self.vx, self.vy,
                self.obj.mass, self.obj.drag_coeff, self.obj.radius, dt
            )

            self.spin_angle = update_spin(self.spin_angle, self.spin_rate, dt)

            if has_landed(self.y, self.obj.radius):
                self.y = GROUND_Y - self.obj.radius # don't let it sink into the ground

                self.vy = compute_bounce(self.vy, self.obj.restitution)
                self.bounce_count += 1

                # 50 px/s is about 1 m/s, and below that you can't see the bounce anyway
                if abs(self.vy) < 50 or self.bounce_count >= self.max_bounces:
                    self.vy    = 0.0
                    self.state = "rolling"
                else:
                    self.state = "bouncing"

        elif self.state == "bouncing":
            # Sitting here for one frame lets the ground clamp and the flipped vy both settle before the next flight step.
            # That's what stopped it double-launching.
            if self.vy < 0:
                self.state = "flying"
            else:
                # vy isn't upward for some reason, so just roll
                self.vy    = 0.0
                self.state = "rolling"

        elif self.state == "rolling":
            self.trail_fade = max(0.0, self.trail_fade - 0.008) # fade the trail out now it's landed

            self.x, self.vx, self.spin_angle, self.spin_rate = update_rolling(
                self.x, self.vx, self.spin_angle, self.spin_rate,
                self.obj.mass, self.obj.radius, self.obj.friction_coeff, dt
            )

            if has_stopped(self.vx, self.spin_rate):
                self.state = "stopped"

        # nothing to do once it's stopped

    def draw(self, surface, camera_x):
        """
        Trail, then shadow, then the object itself.
        camera_x comes off every world x to get a screen x.
        """
        sx = self.x - camera_x
        sy = self.y

        # Oldest points are at the front of the list, so they end up smallest and dimmest.
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

        # shadow only while it's off the ground
        if self.state in ("flying", "bouncing"):
            height_above = GROUND_Y - self.y
            # full size on the ground, down to a fifth of that by 400px up
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

        draw_object(surface, self.obj, sx, sy, self.spin_angle)