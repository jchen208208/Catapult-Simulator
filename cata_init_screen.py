import asyncio
import math
import os
import random
import pygame
from catapult import WIDTH, HEIGHT

_HAND_CHARS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789 .,"
)

DARK_GREEN      = (18,  45,  18)
GRID_MAJOR      = (48,  83,  48)
GRID_MID        = (32,  65,  32)
GRID_MINOR      = (24,  54,  24)
GROUND_GREEN_TOP= (55, 100,  40)
GROUND_BROWN    = (65,  45,  25)
CHALK           = (230, 225, 210)
CHALK_DIM       = (170, 165, 150)
CHALK_MUTED     = (190, 200, 180)
WOOD_LIGHT      = (195, 145,  70)
WOOD_MID        = (165, 115,  50)
WOOD_DARK       = (130,  85,  30)
WOOD_OUTLINE    = ( 80,  45,  15)
METAL           = (100, 100, 110)
METAL_DARK      = ( 60,  60,  70)
ROPE            = (155, 125,  60)

# Ball needs to grow until it covers the full screen diagonal
# sqrt(1100² + 620²) / 2 ≈ 631 — use 681 to be safe
SCREEN_COVER_RADIUS = 681


def _try_font(name, size):
    path = pygame.font.match_font(name)
    if path is not None:
        try:
            f = pygame.font.Font(path, size)
            test = f.render("\u00b2", True, (255, 255, 255))
            if any(test.get_at((x, y))[0] > 0
                   for x in range(test.get_width())
                   for y in range(test.get_height())):
                return f
        except Exception:
            pass
    return pygame.font.Font(None, size)


class InitScreen:
    def __init__(self, screen):
        self.screen = screen
        self.clock  = pygame.time.Clock()

        self.time         = 0.0
        self.show_prompt  = True
        self.prompt_timer = 0.0
        self.state        = "idle"

        # Shake
        self.shake_x         = 0
        self.shake_y         = 0
        self.shake_intensity = 0.0

        # Arm — swings from 0° (rest/horizontal) to +90° (fired/vertical up)
        self.fire_progress = 0.0      # 0.0 = rest, 1.0 = fully fired

        # Projectile
        self.proj_growth   = 0.0      # grows from 0 to SCREEN_COVER_RADIUS
        self.proj_visible  = False    # shown while ball is in bucket
        self.proj_launched = False    # ball has left the bucket

        # Fade out
        self.alpha = 255
        self.done  = False

        self.font_title    = _try_font("Didot",      56)
        self.font_subtitle = _try_font("Georgia",    22)
        self.font_byline   = _try_font("Georgia",    17)
        self.font_prompt   = _try_font("Chalkboard", 26)

        _hand_path = os.path.join(
            os.path.dirname(__file__), "cata_assets", "handwriting.ttf"
        )
        hand_sizes = [26, 34, 42]
        try:
            hand_fonts = [pygame.font.Font(_hand_path, s) for s in hand_sizes]
        except FileNotFoundError:
            hand_fonts = [pygame.font.Font(None, s) for s in hand_sizes]
        self.hand_fonts    = hand_fonts
        self.fallback_fonts= [pygame.font.Font(None, s) for s in hand_sizes]

        self.scattered_eqs = self._generate_side_eqs()
        for eq in self.scattered_eqs:
            fi   = eq["font_i"]
            surf = self._render_with_fallback(
                eq["text"],
                self.hand_fonts[fi],
                self.fallback_fonts[fi],
                eq["color"],
            )
            big     = pygame.transform.scale(surf, (surf.get_width()*2, surf.get_height()*2))
            big_rot = pygame.transform.rotate(big, eq["angle"])
            final   = pygame.transform.smoothscale(
                big_rot, (big_rot.get_width()//2, big_rot.get_height()//2)
            )
            eq["surface"] = final

    # ── equation helpers ──────────────────────────────────────────────────

    @staticmethod
    def _generate_side_eqs():
        random.seed(42)
        entries = [
            "y = v0 sin(\u03b8) t \u2013 \u00bd g t\u00b2",
            "KE = \u00bd m v\u00b2",
            "PE = m g h",
            "F_D = \u00bd \u03c1 v\u00b2 C_D A",
            "R = v0\u00b2 sin(2\u03b8) / g",
            "x = v0 cos(\u03b8) t",
            "F = m a",
            "\u0394x = v0 t + \u00bd a t\u00b2",
            "v\u00b2 = v0\u00b2 + 2 a \u0394x",
            "H = v0\u00b2 sin\u00b2(\u03b8) / 2g",
            "E = KE + PE",
            "g = 9.81 m/s\u00b2",
        ]
        left_positions  = [(180, 200), (310, 330), (200, 450)]
        right_positions = [(810, 200), (910, 330), (840, 450)]
        colors = [CHALK, CHALK_DIM, CHALK_MUTED]
        eqs = []
        for idx, (x, y) in enumerate(left_positions + right_positions):
            text = entries[idx % len(entries)]
            ox = random.randint(-8, 8)
            oy = random.randint(-8, 8)
            eqs.append({
                "text":   text,
                "x":      x + ox,
                "y":      y + oy,
                "angle":  random.randint(-30, 30),
                "color":  colors[idx % 3],
                "font_i": 1,
            })
        return eqs

    def _render_with_fallback(self, text, hand_font, fallback_font, color):
        """Render text using hand_font; fall back per-character if needed."""
        segments = []
        i = 0
        while i < len(text):
            # find run of hand-renderable chars
            j = i
            while j < len(text) and text[j] in _HAND_CHARS:
                j += 1
            if j > i:
                segments.append(hand_font.render(text[i:j], True, color))
                i = j
                continue
            # single non-hand char → fallback font
            segments.append(fallback_font.render(text[i], True, color))
            i += 1

        if not segments:
            return pygame.Surface((0, 0), pygame.SRCALPHA)

        total_width = sum(s.get_width()  for s in segments)
        max_height  = max(s.get_height() for s in segments)
        combined    = pygame.Surface((total_width, max_height), pygame.SRCALPHA)
        x = 0
        for surf in segments:
            y_off = (max_height - surf.get_height()) // 2
            combined.blit(surf, (x, y_off))
            x += surf.get_width()
        return combined

    # ── events / update ───────────────────────────────────────────────────

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if self.state == "idle":
                    self.state           = "launching"
                    self.shake_intensity = 15.0
                    self.fire_progress   = 0.0
                    self.proj_visible    = False
                    self.proj_launched   = False
                    self.proj_growth     = 0.0

    def update(self, dt):
        self.time         += dt
        self.prompt_timer += dt

        if self.prompt_timer >= 0.4:
            self.show_prompt  = not self.show_prompt
            self.prompt_timer = 0.0

        if self.state == "launching":
            # ── shake decays ──────────────────────────────────────────
            self.shake_intensity = max(0.0, self.shake_intensity - 0.5)
            if self.shake_intensity > 0:
                si = int(self.shake_intensity)
                self.shake_x = random.randint(-si, si)
                self.shake_y = random.randint(-si, si)
            else:
                self.shake_x = self.shake_y = 0

            # ── arm fires: 0° → 90° ──────────────────────────────────
            fire_speed = 5.0
            self.fire_progress = min(1.0, self.fire_progress + fire_speed * dt)

            # Show ball in bucket while arm swings
            if not self.proj_launched:
                self.proj_visible = True

            if self.fire_progress >= 1.0 and not self.proj_launched:
                self.proj_launched = True

            if self.proj_launched:
                self.proj_growth = min(
                    SCREEN_COVER_RADIUS,
                    self.proj_growth + 40
                )

            if self.proj_growth >= SCREEN_COVER_RADIUS * 0.5:
                self.state = "transitioning"

        if self.state == "transitioning":
            if self.proj_launched:
                self.proj_growth = min(
                    SCREEN_COVER_RADIUS,
                    self.proj_growth + 40
                )
            self.alpha = max(0, self.alpha - 15)
            if self.alpha <= 0:
                self.done = True

    # ── drawing ───────────────────────────────────────────────────────────

    def draw_graphing_paper(self):
        self.screen.fill(DARK_GREEN)
        for x in range(0, WIDTH, 20):
            c, w = (GRID_MAJOR, 2) if x % 100 == 0 else \
                   (GRID_MID,   1) if x % 50  == 0 else \
                   (GRID_MINOR, 1)
            pygame.draw.line(self.screen, c, (x, 0), (x, HEIGHT), w)
        for y in range(0, HEIGHT, 20):
            c, w = (GRID_MAJOR, 2) if y % 100 == 0 else \
                   (GRID_MID,   1) if y % 50  == 0 else \
                   (GRID_MINOR, 1)
            pygame.draw.line(self.screen, c, (0, y), (WIDTH, y), w)

    def draw_ground(self):
        gy = HEIGHT - 110
        pygame.draw.rect(self.screen, GROUND_GREEN_TOP, (0, gy,      WIDTH, 18))
        pygame.draw.rect(self.screen, GROUND_BROWN,     (0, gy + 18, WIDTH, 92))
        pygame.draw.line(self.screen, CHALK_DIM,        (0, gy), (WIDTH, gy), 2)
        rng = random.Random(7)
        for i in range(0, WIDTH, 28):
            h = rng.randint(4, 10)
            pygame.draw.line(
                self.screen, GROUND_GREEN_TOP,
                (i, gy), (i + rng.randint(-4, 4), gy - h), 1
            )

    def draw_scattered_equations(self):
        for eq in self.scattered_eqs:
            rect = eq["surface"].get_rect(center=(eq["x"], eq["y"]))
            self.screen.blit(eq["surface"], rect)

    def draw_title(self):
        t  = self.font_title.render("Catapult Simulator", True, CHALK)
        r  = t.get_rect(center=(WIDTH//2 + self.shake_x, 45 + self.shake_y))
        self.screen.blit(t, r)

        st = self.font_subtitle.render("Physics and Projectile Motion", True, CHALK_DIM)
        sr = st.get_rect(center=(WIDTH//2 + self.shake_x, 98 + self.shake_y))
        self.screen.blit(st, sr)

        by = self.font_byline.render("by Jayden Chen", True, CHALK_DIM)
        br = by.get_rect(center=(WIDTH//2 + self.shake_x, 124 + self.shake_y))
        self.screen.blit(by, br)

    def draw_prompt(self):
        if self.show_prompt and self.state == "idle":
            t  = self.font_prompt.render("Press SPACE to enter", True, CHALK)
            r  = t.get_rect(center=(WIDTH//2, HEIGHT - 45))
            self.screen.blit(t, r)
            for dx in (-210, 210):
                arr = self.font_prompt.render(">>", True, CHALK_DIM)
                ar  = arr.get_rect(midright=(WIDTH//2 + dx, HEIGHT - 45))
                self.screen.blit(arr, ar)

    def draw_front_catapult(self, cx, cy, scale=1.0):
        """
        Draw a catapult facing the viewer (front-on view like the reference image).

        The arm swings in the plane of the screen — straight up through the
        centre of the frame. We fake the 3-D swing illusion by changing
        the arm's apparent height and width:

          arm_norm = -1.0  →  loaded:  arm is a wide, short ellipse
                               (arm pointing straight AT the viewer —
                                fully foreshortened, looks like a disc)
          arm_norm =  0.0  →  mid:     arm is a medium rectangle
          arm_norm = +1.0  →  fired:   arm is a tall, narrow rectangle
                               (arm pointing straight UP)

        The x centre of the arm never moves — giving the correct illusion
        that it's swinging in depth, not sideways.
        """
        s   = scale
        sx  = cx + self.shake_x
        sy  = cy + self.shake_y

        # ── key measurements ──────────────────────────────────────────
        w_r         = int(22 * s)    # wheel radius
        w_sep       = int(58 * s)    # wheel x offset from centre
        base_w      = int(130 * s)   # chassis beam width
        base_h      = int(14 * s)
        post_w      = int(12 * s)    # vertical A-frame post width
        post_h      = int(95 * s)    # vertical A-frame post height
        post_sep    = int(48 * s)    # how far left/right the posts sit
        crossbar_w  = int(110 * s)   # horizontal bar connecting posts at top
        crossbar_h  = int(12 * s)
        hub_r       = int(7  * s)    # pivot hub radius

        base_top_y  = sy - base_h                  # top of chassis beam
        post_bot_y  = base_top_y                   # posts sit on chassis
        post_top_y  = post_bot_y - post_h           # top of posts
        cross_y     = post_top_y - crossbar_h       # crossbar sits on post tops
        pivot_y     = cross_y + crossbar_h // 2     # arm pivot point y

        # ── wheels ────────────────────────────────────────────────────
        wheel_y = sy - w_r + 4
        for wx in (sx - w_sep, sx + w_sep):
            pygame.draw.circle(self.screen, WOOD_DARK,    (wx, wheel_y), w_r)
            pygame.draw.circle(self.screen, WOOD_MID,     (wx, wheel_y), w_r - 5)
            pygame.draw.circle(self.screen, WOOD_OUTLINE, (wx, wheel_y), w_r, 2)
            for a in range(0, 360, 45):
                rad = math.radians(a)
                ex  = wx + int(math.cos(rad) * (w_r - 7))
                ey  = wheel_y + int(math.sin(rad) * (w_r - 7))
                pygame.draw.line(self.screen, WOOD_OUTLINE, (wx, wheel_y), (ex, ey), 2)
            pygame.draw.circle(self.screen, METAL,      (wx, wheel_y), 5)
            pygame.draw.circle(self.screen, METAL_DARK, (wx, wheel_y), 5, 1)

        # ── chassis base beam ─────────────────────────────────────────
        base_r = pygame.Rect(sx - base_w//2, base_top_y, base_w, base_h)
        pygame.draw.rect(self.screen, WOOD_MID,     base_r)
        pygame.draw.rect(self.screen, WOOD_OUTLINE, base_r, 2)
        # wood grain lines
        for i in range(3):
            gx = sx - base_w//2 + base_w * (i+1)//4
            pygame.draw.line(self.screen, WOOD_DARK,
                             (gx, base_top_y + 3),
                             (gx, base_top_y + base_h - 3), 1)

        # ── A-frame vertical posts (two, one each side) ───────────────
        for px_off in (-post_sep, post_sep):
            pr = pygame.Rect(sx + px_off - post_w//2, post_top_y, post_w, post_h)
            pygame.draw.rect(self.screen, WOOD_LIGHT,   pr)
            pygame.draw.rect(self.screen, WOOD_OUTLINE, pr, 2)
            # grain
            pygame.draw.line(self.screen, WOOD_MID,
                             (sx + px_off, post_top_y + 8),
                             (sx + px_off, post_top_y + post_h - 8), 1)

        # ── horizontal crossbar connecting post tops ───────────────────
        cb_r = pygame.Rect(sx - crossbar_w//2, cross_y, crossbar_w, crossbar_h)
        pygame.draw.rect(self.screen, WOOD_DARK,    cb_r)
        pygame.draw.rect(self.screen, WOOD_OUTLINE, cb_r, 2)

        # ── rope bundle / torsion spring around vertical centre post ───
        # This is the coiled rope that powers the arm (visible in your image)
        rope_top_y  = pivot_y - int(18 * s)
        rope_bot_y  = base_top_y
        rope_mid_x  = sx
        rope_w      = int(10 * s)
        # background rope column
        pygame.draw.rect(self.screen, ROPE,
                         pygame.Rect(rope_mid_x - rope_w//2,
                                     rope_top_y,
                                     rope_w,
                                     rope_bot_y - rope_top_y))
        # coil bands
        coil_color = tuple(max(0, c - 30) for c in ROPE)
        coil_steps = int((rope_bot_y - rope_top_y) / (4 * s))
        for i in range(coil_steps):
            cy2 = rope_top_y + i * int(4 * s)
            pygame.draw.ellipse(
                self.screen, coil_color,
                pygame.Rect(rope_mid_x - rope_w//2 - 2, cy2, rope_w + 4, int(4 * s))
            )
        # two ropes extending upward from the bundle to the arm pivot
        rope_spread = int(14 * s)
        pygame.draw.line(self.screen, ROPE,
                         (rope_mid_x - rope_spread, rope_top_y),
                         (sx - int(3*s), pivot_y), 2)
        pygame.draw.line(self.screen, ROPE,
                         (rope_mid_x + rope_spread, rope_top_y),
                         (sx + int(3*s), pivot_y), 2)

        # ── pivot hub ─────────────────────────────────────────────────
        pygame.draw.circle(self.screen, METAL,      (sx, pivot_y), hub_r)
        pygame.draw.circle(self.screen, METAL_DARK, (sx, pivot_y), hub_r, 2)

        # ── ARM — front-on swing illusion ─────────────────────────────
        #
        # arm_norm:  -1 = loaded (arm below pivot, pointing at viewer)
        #             0 = horizontal (mid swing)
        #            +1 = fired (arm straight up, pointing away from viewer)
        #
        # To fake 3-D swing with no sideways movement:
        #   - Visual HEIGHT of arm  =  full arm length × |sin(angle)|
        #     (when horizontal the apparent height is zero — you'd see it
        #      edge-on; when vertical it's full height)
        #   - Visual WIDTH of arm   =  arm length × cos(angle)  for foreshortening
        #     but we cap it so it always looks like a plank not a dot
        #
        # Swing from 0° (rest/horizontal) to +90° (fired, perpendicular to ground)
        full_arm_len  = int(105 * s)  # slightly longer
        arm_angle_deg = self.fire_progress * 90.0     # 0° → +90°
        arm_angle_rad = math.radians(arm_angle_deg)

        # Height: 0 at rest (arm points at viewer = edge-on), full when upright
        apparent_h = int(abs(math.sin(arm_angle_rad)) * full_arm_len)
        apparent_h = max(int(4 * s), apparent_h)

        # Width: widest when horizontal (cross-section toward viewer), narrowest when upright
        max_arm_w  = int(18 * s)
        min_arm_w  = int(6  * s)
        w_factor   = abs(math.cos(arm_angle_rad))
        apparent_w = int(min_arm_w + (max_arm_w - min_arm_w) * w_factor)

        # Arm centred at the pivot point
        arm_centre_x = sx
        arm_centre_y = pivot_y

        # Basket at the tip of the arm
        #   0° (rest)   → arm points AT viewer → basket at pivot (hidden behind arm)
        #   +90° (fired)→ arm points UP        → basket at top
        basket_cx = arm_centre_x
        basket_cy = pivot_y - int(math.sin(arm_angle_rad) * full_arm_len * 0.5) - int(6 * s)

        bucket_w = max(int(10*s), apparent_w + int(8*s))
        bucket_h = max(int(8*s), int(12*s) - int(self.fire_progress * 5 * s))

        # ── Ball in bucket (behind arm) during load and early fire ──
        if self.proj_visible and not self.proj_launched:
            in_bucket_r = max(6, int(bucket_w * 0.35))
            c = (80, 50, 30)
            pygame.draw.circle(self.screen, c, (basket_cx, basket_cy), in_bucket_r)
            pygame.draw.circle(self.screen, WOOD_OUTLINE, (basket_cx, basket_cy), in_bucket_r, 1)

        arm_rect = pygame.Rect(
            arm_centre_x - apparent_w // 2,
            arm_centre_y - apparent_h // 2,
            apparent_w,
            apparent_h,
        )
        pygame.draw.rect(self.screen, WOOD_LIGHT,   arm_rect, border_radius=3)
        pygame.draw.rect(self.screen, WOOD_OUTLINE, arm_rect, 2, border_radius=3)

        # ── Bucket at the tip ─────────────────────────────────────────
        # Bowl inner recess (dark)
        inner_r = pygame.Rect(basket_cx - bucket_w//2,
                              basket_cy - bucket_h//4,
                              bucket_w, bucket_h // 2)
        pygame.draw.ellipse(self.screen, (40, 22, 12), inner_r)
        # Bowl outer body
        outer_r = pygame.Rect(basket_cx - bucket_w//2,
                              basket_cy - bucket_h//2,
                              bucket_w, bucket_h)
        pygame.draw.ellipse(self.screen, WOOD_DARK, outer_r)
        pygame.draw.ellipse(self.screen, WOOD_OUTLINE, outer_r, 2)
        # Rim highlight (front edge)
        pygame.draw.line(self.screen, WOOD_LIGHT,
                         (basket_cx - bucket_w//2 + 2, basket_cy),
                         (basket_cx + bucket_w//2 - 2, basket_cy), 2)

        # ── Launched projectile ────────────────────────────────────────
        if self.proj_launched:
            proj_r = int(10 * s) + int(self.proj_growth)

            prog = min(1.0, self.proj_growth / SCREEN_COVER_RADIUS)
            px = prog * prog * (3 - 2 * prog)

            proj_x = int(basket_cx + (WIDTH  // 2 - basket_cx) * px)
            proj_y = int(basket_cy + (HEIGHT // 2 - basket_cy) * px)

            # Fully opaque black sphere — solid fill with subtle shading
            # Base fill (solid black)
            pygame.draw.circle(self.screen, (0, 0, 0), (proj_x, proj_y), proj_r)

            # Subtle shading rings (barely visible depth, centered)
            for ring in range(proj_r, 0, -1):
                t = ring / proj_r
                v = int(t * 40)
                pygame.draw.circle(self.screen, (v, v, v), (proj_x, proj_y), ring)

            # Thin rim edge
            pygame.draw.circle(self.screen, (60, 60, 65),
                               (proj_x, proj_y), proj_r, 2)

            # Glossy specular highlight (top-left)
            if proj_r > 15:
                hl_x = proj_x - int(proj_r * 0.35)
                hl_y = proj_y - int(proj_r * 0.35)
                hl_r = max(3, proj_r // 5)
                pygame.draw.circle(self.screen, (160, 170, 200),
                                   (hl_x, hl_y), hl_r + 2)
                pygame.draw.circle(self.screen, (220, 225, 245),
                                   (hl_x, hl_y), hl_r)
                pygame.draw.circle(self.screen, (255, 255, 255),
                                   (hl_x, hl_y), max(2, hl_r // 2))

    # ── composite draw ────────────────────────────────────────────────────

    def draw(self):
        self.draw_graphing_paper()
        self.draw_scattered_equations()
        self.draw_ground()
        self.draw_title()
        self.draw_front_catapult(WIDTH // 2, HEIGHT - 170, 1.6)
        self.draw_prompt()

        # Fade overlay
        if self.alpha < 255:
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 255 - self.alpha))
            self.screen.blit(ov, (0, 0))

    # ── async run ─────────────────────────────────────────────────────────

    async def run(self):
        while not self.done:
            dt = self.clock.tick(60) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
            await asyncio.sleep(0)