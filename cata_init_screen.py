import asyncio
import math
import random
import pygame
from catapult import WIDTH, HEIGHT

DARK_GREEN = (18, 45, 18)
GRID_MAJOR = (48, 83, 48)
GRID_MID = (32, 65, 32)
GRID_MINOR = (24, 54, 24)
GROUND_GREEN_TOP = (55, 100, 40)
GROUND_BROWN = (65, 45, 25)
CHALK = (230, 225, 210)
CHALK_DIM = (170, 165, 150)
CHALK_MUTED = (190, 200, 180)
WOOD_LIGHT = (195, 145, 70)
WOOD_MID = (165, 115, 50)
WOOD_DARK = (130, 85, 30)
WOOD_OUTLINE = (80, 45, 15)
METAL = (100, 100, 110)
METAL_DARK = (60, 60, 70)
ROPE = (155, 125, 60)


def _try_font(name, size):
    path = pygame.font.match_font(name)
    if path is not None:
        try:
            f = pygame.font.Font(path, size)
            # verify ² character renders
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
        self.clock = pygame.time.Clock()

        self.time = 0.0
        self.show_prompt = True
        self.prompt_timer = 0.0
        self.state = "idle"
        self.shake_x = 0
        self.shake_y = 0
        self.shake_intensity = 0.0
        self.proj_growth = 0.0
        self.arm_swing = 0.0
        self.alpha = 255
        self.done = False

        self.font_title = _try_font("Didot", 56)
        self.font_subtitle = _try_font("Georgia", 22)
        self.font_byline = _try_font("Georgia", 17)
        self.font_prompt = _try_font("Chalkboard", 26)
        self.font_hand_lg = _try_font("Chalkboard", 24)
        self.font_hand_md = _try_font("Chalkboard", 20)
        self.font_hand_sm = _try_font("Chalkboard", 17)

        self.scattered_eqs = self._generate_side_eqs()

    # ------------------------------------------------------------------

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

        # 3 on left, 3 on right — well clear of catapult (x ~400-710)
        left_positions  = [(120, 210), (260, 320), (170, 430)]
        right_positions = [(830, 210), (960, 320), (890, 430)]

        colors = [CHALK, CHALK_DIM, CHALK_MUTED]
        eqs = []

        for idx, (x, y) in enumerate(left_positions + right_positions):
            text = entries[idx % len(entries)]
            ox = random.randint(-8, 8)
            oy = random.randint(-8, 8)
            eqs.append({
                "text": text,
                "x": x + ox,
                "y": y + oy,
                "angle": random.randint(-30, 30),
                "color": colors[idx % 3],
                "font_i": 1,
            })

        return eqs

        return eqs

    # ------------------------------------------------------------------
    # Events / Update
    # ------------------------------------------------------------------

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if self.state == "idle":
                    self.state = "launching"
                    self.shake_intensity = 15.0

    def update(self, dt):
        self.time += dt
        self.prompt_timer += dt

        if self.prompt_timer >= 0.4:
            self.show_prompt = not self.show_prompt
            self.prompt_timer = 0.0

        if self.state == "launching":
            self.shake_intensity = max(0.0, self.shake_intensity - 0.5)
            if self.shake_intensity > 0:
                si = int(self.shake_intensity)
                self.shake_x = random.randint(-si, si)
                self.shake_y = random.randint(-si, si)

            self.proj_growth = min(220, self.proj_growth + 7)
            self.arm_swing = min(55, self.arm_swing + 1.2)

            if self.proj_growth >= 220:
                self.state = "transitioning"

        if self.state == "transitioning":
            self.alpha = max(0, self.alpha - 5)
            if self.alpha <= 0:
                self.done = True

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_graphing_paper(self):
        self.screen.fill(DARK_GREEN)

        for x in range(0, WIDTH, 20):
            if x % 100 == 0:
                c, w = GRID_MAJOR, 2
            elif x % 50 == 0:
                c, w = GRID_MID, 1
            else:
                c, w = GRID_MINOR, 1
            pygame.draw.line(self.screen, c, (x, 0), (x, HEIGHT), w)

        for y in range(0, HEIGHT, 20):
            if y % 100 == 0:
                c, w = GRID_MAJOR, 2
            elif y % 50 == 0:
                c, w = GRID_MID, 1
            else:
                c, w = GRID_MINOR, 1
            pygame.draw.line(self.screen, c, (0, y), (WIDTH, y), w)

    def draw_ground(self):
        gy = HEIGHT - 110
        pygame.draw.rect(self.screen, GROUND_GREEN_TOP, (0, gy, WIDTH, 18))
        pygame.draw.rect(self.screen, GROUND_BROWN, (0, gy + 18, WIDTH, 92))
        pygame.draw.line(self.screen, CHALK_DIM, (0, gy), (WIDTH, gy), 2)

        for i in range(0, WIDTH, 28):
            h = random.randint(4, 10)
            pygame.draw.line(self.screen, (50, 120, 50), (i, gy), (i, gy - h), 2)

    def draw_scattered_equations(self):
        fonts = [self.font_hand_sm, self.font_hand_md, self.font_hand_lg]

        for eq in self.scattered_eqs:
            font = fonts[eq["font_i"]]
            surf = font.render(eq["text"], True, eq["color"])
            rotated = pygame.transform.rotate(surf, eq["angle"])
            rect = rotated.get_rect(center=(eq["x"], eq["y"]))
            self.screen.blit(rotated, rect)

    def draw_title(self):
        t = self.font_title.render("Catapult Simulator", True, CHALK)
        r = t.get_rect(center=(WIDTH // 2 + self.shake_x, 45 + self.shake_y))
        self.screen.blit(t, r)

        st = self.font_subtitle.render(
            "Physics and Projectile Motion", True, CHALK_DIM
        )
        sr = st.get_rect(center=(WIDTH // 2 + self.shake_x, 98 + self.shake_y))
        self.screen.blit(st, sr)

        by = self.font_byline.render("by Jayden Chen", True, CHALK_DIM)
        br = by.get_rect(center=(WIDTH // 2 + self.shake_x, 124 + self.shake_y))
        self.screen.blit(by, br)

    def draw_prompt(self):
        if self.show_prompt and self.state == "idle":
            t = self.font_prompt.render("Press SPACE to enter", True, CHALK)
            r = t.get_rect(center=(WIDTH // 2, HEIGHT - 45))
            self.screen.blit(t, r)

            for dx in (-210, 210):
                arr = self.font_prompt.render(">>", True, CHALK_DIM)
                ar = arr.get_rect(midright=(WIDTH // 2 + dx, HEIGHT - 45))
                self.screen.blit(arr, ar)

    # ------------------------------------------------------------------
    # Catapult
    # ------------------------------------------------------------------

    def draw_front_catapult(self, cx, cy, scale=1.0):
        s = scale
        w_r = int(22 * s)
        w_sep = int(55 * s)
        base_w = int(120 * s)
        base_h = int(12 * s)
        sup_h = int(85 * s)
        sup_bot_sep = int(35 * s)
        sup_top_sep = int(6 * s)
        arm_len = int(55 * s)

        sx = cx + self.shake_x
        sy = cy + self.shake_y

        # Wheels
        for wx in (sx - w_sep, sx + w_sep):
            pygame.draw.circle(self.screen, WOOD_DARK, (wx, sy), w_r)
            pygame.draw.circle(self.screen, WOOD_MID, (wx, sy), w_r - 4)
            pygame.draw.circle(self.screen, WOOD_OUTLINE, (wx, sy), w_r, 2)
            for a in range(0, 360, 45):
                rad = math.radians(a)
                ex = wx + int(math.cos(rad) * (w_r - 6))
                ey = sy + int(math.sin(rad) * (w_r - 6))
                pygame.draw.line(self.screen, WOOD_OUTLINE, (wx, sy), (ex, ey), 2)
            pygame.draw.circle(self.screen, METAL, (wx, sy), 5)
            pygame.draw.circle(self.screen, METAL_DARK, (wx, sy), 5, 1)

        # Base beam
        base_r = pygame.Rect(sx - base_w // 2, sy - base_h - 3, base_w, base_h)
        pygame.draw.rect(self.screen, WOOD_MID, base_r)
        pygame.draw.rect(self.screen, WOOD_OUTLINE, base_r, 2)

        # A-frame supports
        def _support(bot_x, top_x):
            return [
                (bot_x - 4, sy - base_h - 3),
                (bot_x + 4, sy - base_h - 3),
                (top_x + 4, sy - base_h - 3 - sup_h),
                (top_x - 4, sy - base_h - 3 - sup_h),
            ]

        left = _support(sx - sup_bot_sep, sx - sup_top_sep)
        right = _support(sx + sup_bot_sep, sx + sup_top_sep)
        for pts in (left, right):
            pygame.draw.polygon(self.screen, WOOD_LIGHT, pts)
            pygame.draw.polygon(self.screen, WOOD_OUTLINE, pts, 2)

        # Crossbar
        cross_y = sy - base_h - 3 - sup_h - 6
        cross_r = pygame.Rect(sx - 10, cross_y, 20, 8)
        pygame.draw.rect(self.screen, WOOD_DARK, cross_r)
        pygame.draw.rect(self.screen, WOOD_OUTLINE, cross_r, 2)

        hub_y = cross_y + 4

        # Arm pivots at crossbar, swings from loaded (up) to fired (forward)
        sw_norm = min(1.0, self.arm_swing / 55.0)
        start_a = -math.pi / 2
        end_a = math.pi * 22 / 180
        cur_a = start_a + (end_a - start_a) * sw_norm

        arm_top_x, arm_top_y = sx, cross_y - 2
        arm_bot_x = arm_top_x + arm_len * math.cos(cur_a)
        arm_bot_y = arm_top_y + arm_len * math.sin(cur_a)

        taper_top = int(3 * s)
        taper_bot = int(7 * s + sw_norm * 8 * s)
        arm_pts = [
            (arm_top_x - taper_top, arm_top_y),
            (arm_top_x + taper_top, arm_top_y),
            (arm_bot_x + taper_bot, arm_bot_y),
            (arm_bot_x - taper_bot, arm_bot_y),
        ]
        pygame.draw.polygon(self.screen, WOOD_LIGHT, arm_pts)
        pygame.draw.polygon(self.screen, WOOD_OUTLINE, arm_pts, 2)

        # crossbar hub
        pygame.draw.circle(self.screen, METAL, (sx, hub_y + 4), 4)
        pygame.draw.circle(self.screen, METAL_DARK, (sx, hub_y + 4), 4, 1)

        # Rope from arm to basket
        b_cx, b_cy = arm_bot_x, arm_bot_y + 10
        pygame.draw.line(self.screen, ROPE,
                         (arm_bot_x - 6, arm_bot_y),
                         (b_cx - 8, b_cy), 2)
        pygame.draw.line(self.screen, ROPE,
                         (arm_bot_x + 6, arm_bot_y),
                         (b_cx + 8, b_cy), 2)

        # Basket
        basket_r = pygame.Rect(b_cx - 14, b_cy - 5, 28, 10)
        pygame.draw.ellipse(self.screen, WOOD_DARK, basket_r)
        pygame.draw.ellipse(self.screen, WOOD_OUTLINE, basket_r, 2)

        # Projectile
        proj_r = int(10 * s) + int(self.proj_growth)
        proj_x = b_cx - int(self.proj_growth * 0.30)
        proj_y = b_cy - int(self.proj_growth * 0.18)

        # Glow behind projectile during launch
        if self.state in ("launching", "transitioning") and proj_r > 5:
            glow = pygame.Surface(
                (proj_r * 2 + 28, proj_r * 2 + 28), pygame.SRCALPHA
            )
            for i in range(4, 0, -1):
                r = proj_r + i * 5
                a = max(0, 55 - i * 12)
                pygame.draw.circle(
                    glow, (255, 200, 50, a),
                    (proj_r + 14, proj_r + 14), r,
                )
            self.screen.blit(
                glow,
                (int(proj_x - proj_r - 14), int(proj_y - proj_r - 14)),
            )

        # Opaque projectile with solid shading
        dark = (90, 50, 30)
        mid = (140, 80, 50)
        light = (180, 115, 80)

        for r in range(proj_r, 0, -2):
            t = r / proj_r
            cr = int(dark[0] + (light[0] - dark[0]) * t)
            cg = int(dark[1] + (light[1] - dark[1]) * t)
            cb = int(dark[2] + (light[2] - dark[2]) * t)
            pygame.draw.circle(self.screen, (cr, cg, cb),
                               (int(proj_x), int(proj_y)), r)

        outline_r = max(1, proj_r - 1)
        pygame.draw.circle(self.screen, WOOD_OUTLINE,
                           (int(proj_x), int(proj_y)), outline_r, 2)

        # Gloss highlight (transparent overlay)
        if proj_r > 6:
            gloss = pygame.Surface((proj_r * 2, proj_r * 2), pygame.SRCALPHA)
            hl_r = max(3, proj_r // 3)
            hl_ox = proj_r - proj_r // 4
            hl_oy = proj_r - proj_r // 4
            for i in range(3, 0, -1):
                r = hl_r + i * 2
                a = max(0, 55 - i * 16)
                pygame.draw.circle(gloss, (255, 255, 255, a),
                                   (hl_ox, hl_oy), r)
            self.screen.blit(gloss,
                             (int(proj_x - proj_r), int(proj_y - proj_r)))

    # ------------------------------------------------------------------
    # Composite draw
    # ------------------------------------------------------------------

    def draw(self):
        self.draw_graphing_paper()
        self.draw_scattered_equations()
        self.draw_ground()
        self.draw_title()

        self.draw_front_catapult(WIDTH // 2, HEIGHT - 200, 1.6)

        self.draw_prompt()

        if self.alpha < 255:
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 255 - self.alpha))
            self.screen.blit(ov, (0, 0))

    # ------------------------------------------------------------------

    async def run(self):
        while not self.done:
            dt = self.clock.tick(60) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
            await asyncio.sleep(0)
