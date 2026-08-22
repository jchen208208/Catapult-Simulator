import pygame
import math
from cata_physics import launch_velocity, PIXELS_PER_METER
from cata_objects import OBJECTS
from catapult import ARM_MIN, ARM_MAX, ARM_ANGLE_REST, ARM_ANGLE_MAX, WIDTH, HEIGHT, RELEASE_ANGLE, GROUND_Y
from cata_projectile import draw_object


class UI:
    """
    Everything drawn on top of the world: the stats panel, the object picker and the controls reminder.
    All of it is screen space, so nothing here cares about the camera.
    """

    _OBJECT_COUNT = len(OBJECTS)

    def __init__(self, font, font_large):
        self.font = font
        self.font_large = font_large

        self.selected_index = 0

        # These four get filled in as the throw happens, then frozen into final_stats at the end.
        self.launch_x = 0.0
        self.flight_timer = 0.0
        self.max_height = 0.0
        self.impact_speed = 0.0

        # distance, max_height, flight_time and impact_speed, set once it stops. None until then.
        self.final_stats = None

        self._hovered_index = None
        self._prev_state = None # last frame's projectile state, used to spot the transitions
        self._has_been_flying = False

        # picker circles go down the right-hand side, worked out once here
        picker_x = WIDTH - 65
        picker_start_y = 90
        picker_spacing = 78
        self._picker_pos = [
            (picker_x, picker_start_y + i * picker_spacing)
            for i in range(self._OBJECT_COUNT)
        ]

    def handle_event(self, event):
        """Handle one pygame event. Always returns None, the caller doesn't need anything back."""
        # 1 to 6 pick an object straight off
        if event.type == pygame.KEYDOWN:
            if pygame.K_1 <= event.key <= pygame.K_6:
                idx = event.key - pygame.K_1
                if idx < self._OBJECT_COUNT:
                    self.selected_index = idx
                return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            # circular hit test, 30 px radius
            for i, (cx, cy) in enumerate(self._picker_pos):
                dx = mx - cx
                dy = my - cy
                if dx * dx + dy * dy < 30 * 30:
                    self.selected_index = i
                    return None

        return None

    def update(self, projectile, catapult, dt):
        """Hover detection, flight tracking, and spotting the moment it lands so the stats can be frozen."""
        mx, my = pygame.mouse.get_pos()
        self._hovered_index = None
        for i, (cx, cy) in enumerate(self._picker_pos):
            dx = mx - cx
            dy = my - cy
            if dx * dx + dy * dy < 30 * 30:
                self._hovered_index = i
                break

        if projectile is None:
            # nothing in the air, so clear everything ready for the next shot
            self.final_stats = None
            self._prev_state = None
            self._has_been_flying = False
            return

        # note where it started, the first frame it's actually flying
        if not self._has_been_flying and projectile.state == "flying":
            self._has_been_flying = True
            self.launch_x = projectile.x
            self.flight_timer = 0.0
            self.max_height = 0.0

        if self._has_been_flying:
            self.flight_timer += dt
            height_m = (GROUND_Y - projectile.y) / PIXELS_PER_METER
            if height_m > self.max_height:
                self.max_height = height_m

        # the frame it settles into a roll is what counts as the impact
        if (self._prev_state in ("flying", "bouncing")
                and projectile.state == "rolling"):
            self.impact_speed = math.hypot(projectile.vx, projectile.vy)

        # and once it stops, freeze the numbers so the panel can keep showing them
        if (self._prev_state == "rolling"
                and projectile.state == "stopped"):
            self.final_stats = {
                "distance": (projectile.x - self.launch_x) / PIXELS_PER_METER,
                "max_height": self.max_height,
                "flight_time": self.flight_timer,
                "impact_speed": self.impact_speed,
            }

        self._prev_state = projectile.state

    def draw(self, surface, projectile, catapult, camera_x):
        """
        The panel in the top left switches between four modes depending on what the projectile is doing.
        Picker and controls go on top of it.
        """
        if projectile and projectile.state in ("flying", "bouncing"):
            self._draw_flight_telemetry(surface, projectile)
        elif projectile and projectile.state == "rolling":
            self._draw_rolling_telemetry(surface, projectile)
        elif self.final_stats:
            self._draw_stopped_stats(surface, self.final_stats)
        elif projectile is None and (catapult.dragging
                                     or catapult.is_oscillating):
            # still aiming, so show what the shot would look like
            self._draw_launch_stats(surface, catapult)

        # picker only shows when nothing's happening, otherwise it's in the way
        if (projectile is None and not catapult.dragging
                and not catapult.is_oscillating):
            self._draw_picker(surface)

        self._draw_controls(surface)



    def get_selected_object(self):
        """Whichever object is currently highlighted in the picker."""
        return OBJECTS[self.selected_index]

    @staticmethod
    def _lighten(color, factor):
        """Blend a colour toward white."""
        return tuple(min(255, int(c + (255 - c) * factor)) for c in color)

    @staticmethod
    def _draw_hud_box(surface, lines, x, y, font, line_height=24,
                      pad_x=12, pad_y=10, color=(220, 235, 255),
                      label_color=(140, 160, 185)):
        """
        Rounded translucent box with a list of text lines in it.
        Anything with a colon in it gets split so the label and the value can be different colours.
        """
        box_w = max(font.size(l)[0] for l in lines) + pad_x * 2
        box_h = len(lines) * line_height + pad_y * 2
        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 140), bg.get_rect(), border_radius=10)
        surface.blit(bg, (x, y))
        for i, line in enumerate(lines):
            parts = line.split(':', 1)
            if len(parts) == 2:
                lbl = font.render(parts[0] + ':', True, label_color)
                val = font.render(parts[1], True, color)
                x_pos = x + pad_x
                surface.blit(lbl, (x_pos, y + pad_y + i * line_height))
                surface.blit(val, (x_pos + lbl.get_width(), y + pad_y + i * line_height))
            else:
                r = font.render(line, True, color)
                surface.blit(r, (x + pad_x, y + pad_y + i * line_height))

    def _draw_launch_stats(self, surface, catapult):
        """Live preview while the arm is being dragged back."""
        obj = OBJECTS[self.selected_index]

        # arm length and pull-back, both as a percentage of their range
        arm_load = ((catapult.arm_length - ARM_MIN)
                    / (ARM_MAX - ARM_MIN) * 100)
        arm_load = max(0.0, min(100.0, arm_load))

        pull = ((catapult.arm_angle - ARM_ANGLE_REST)
                / (ARM_ANGLE_MAX - ARM_ANGLE_REST) * 100)
        pull = max(0.0, min(100.0, pull))

        # what it'd launch at if you let go right now
        try:
            vx, vy = launch_velocity(
                catapult.arm_length, catapult.arm_angle, RELEASE_ANGLE,
                obj.mass,
            )
            est_speed = math.hypot(vx, vy) / PIXELS_PER_METER
        except (ValueError, ZeroDivisionError):
            est_speed = 0.0

        lines = [
            f"Arm load    : {arm_load:3.0f} %",
            f"Pull angle  : {pull:3.0f} %",
            f"Est. speed  : {est_speed:5.1f} m/s",
            f"Object      : {obj.name}",
            f"Mass        : {obj.mass:5.1f} kg",
        ]
        self._draw_hud_box(surface, lines, 10, 10, self.font)

    def _draw_flight_telemetry(self, surface, projectile):
        """Live numbers while it's in the air."""
        vx_ms = projectile.vx / PIXELS_PER_METER
        vy_ms = projectile.vy / PIXELS_PER_METER
        speed_ms = math.hypot(projectile.vx, projectile.vy) / PIXELS_PER_METER
        height_m = (GROUND_Y - projectile.y) / PIXELS_PER_METER
        dist_m = (projectile.x - self.launch_x) / PIXELS_PER_METER

        lines = [
            f"Speed   : {speed_ms:6.1f} m/s",
            f"Horiz.  : {vx_ms:6.1f} m/s",
            f"Vert.   : {vy_ms:6.1f} m/s",
            f"Height  : {height_m:6.1f} m",
            f"Distance: {dist_m:6.1f} m",
        ]
        self._draw_hud_box(surface, lines, 10, 10, self.font)

    def _draw_rolling_telemetry(self, surface, projectile):
        """Same again, but for while it's rolling along the ground."""
        speed_ms = math.hypot(projectile.vx, projectile.vy) / PIXELS_PER_METER
        dist_m = (projectile.x - self.launch_x) / PIXELS_PER_METER

        lines = [
            f"Roll speed: {speed_ms:6.1f} m/s",
            f"Distance  : {dist_m:6.1f} m",
            f"Max height: {self.max_height:6.1f} m",
            f"Flight t. : {self.flight_timer:6.1f} s",
        ]
        self._draw_hud_box(surface, lines, 10, 10, self.font,
                           color=(200, 220, 255))

    def _draw_stopped_stats(self, surface, stats):
        """The final card, once everything has come to a stop."""
        label_col = (140, 160, 185)
        value_col = (220, 235, 255)
        rows = [
            (self.font_large, "  STOPPED", (255, 220, 80)),
            (self.font, f"Total distance: {stats['distance']:6.1f} m", None),
            (self.font, f"Max height    : {stats['max_height']:6.1f} m", None),
            (self.font, f"Flight time   : {stats['flight_time']:6.1f} s", None),
            (self.font, f"Impact speed  : {stats['impact_speed'] / PIXELS_PER_METER:6.1f} m/s", None),
        ]
        line_h = [22, 22, 22, 22, 22]
        box_w = max(r[0].size(r[1])[0] for r in rows) + 16
        box_h = sum(line_h[:len(rows)]) + 14
        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 140), bg.get_rect(), border_radius=10)
        surface.blit(bg, (10, 10))
        y = 12
        for i, (f, text, clr) in enumerate(rows):
            if clr:
                r = f.render(text, True, clr)
                surface.blit(r, (14, y + 2))
            else:
                parts = text.split(':', 1)
                if len(parts) == 2:
                    lbl = self.font.render(parts[0] + ':', True, label_col)
                    val = self.font.render(parts[1], True, value_col)
                    surface.blit(lbl, (14, y + 2))
                    surface.blit(val, (14 + lbl.get_width(), y + 2))
                else:
                    r = self.font.render(text, True, value_col)
                    surface.blit(r, (14, y + 2))
            y += line_h[i]

    def _draw_picker(self, surface):
        """The clickable object circles down the right-hand side."""
        # panel behind them, sized off the biggest object so nothing overhangs
        max_dr = max(o.radius * o.display_scale for o in OBJECTS) * 1.3
        cx = self._picker_pos[0][0]
        box_x = int(cx) - 60
        box_y = int(self._picker_pos[0][1] - max_dr - 16)
        box_w = 120
        box_h = int(self._picker_pos[-1][1] - self._picker_pos[0][1] + (max_dr + 16) * 2 + 30)
        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (15, 15, 25, 110), bg.get_rect(), border_radius=12)
        surface.blit(bg, (box_x, box_y))

        for i, obj in enumerate(OBJECTS):
            cx, cy = self._picker_pos[i]
            hovered = i == self._hovered_index
            selected = i == self.selected_index

            scale = 1.3 if hovered else 1.0
            display_r = int(obj.radius * scale * obj.display_scale)
            outline_raw = (
                self._lighten(obj.outline_color, 0.25) if hovered
                else obj.outline_color
            )
            outline = (255, 255, 200) if selected else outline_raw

            draw_object(surface, obj, cx, cy, scale=scale)
            pygame.draw.circle(
                surface, outline, (cx, cy),
                display_r, 3 if selected else 2,
            )
            label = self.font.render(obj.name, True, (230, 230, 240))
            label_rect = label.get_rect(
                center=(cx, cy + display_r + 12),
            )
            surface.blit(label, label_rect)

    def _draw_controls(self, surface):
        """Keyboard shortcuts, bottom left."""
        lines = [
            "SPACE \u2192 fire",
            "R     \u2192 reset",
            "1-6   \u2192 select",
        ]
        x, y = 10, HEIGHT - 80
        key_col = (255, 210, 100)
        desc_col = (170, 185, 200)
        pad = 10
        lh = 22
        box_w = max(self.font.size(l)[0] for l in lines) + pad * 2
        box_h = len(lines) * lh + pad * 2
        bg = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 120), bg.get_rect(), border_radius=8)
        surface.blit(bg, (x, y))
        for i, line in enumerate(lines):
            parts = line.split('\u2192', 1)
            if len(parts) == 2:
                k = self.font.render(parts[0].strip(), True, key_col)
                d = self.font.render('\u2192 ' + parts[1].strip(), True, desc_col)
                x_pos = x + pad
                surface.blit(k, (x_pos, y + pad + i * lh))
                surface.blit(d, (x_pos + k.get_width(), y + pad + i * lh))
            else:
                r = self.font.render(line, True, desc_col)
                surface.blit(r, (x + pad, y + pad + i * lh))


