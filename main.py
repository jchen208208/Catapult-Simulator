import asyncio
import pygame
from catapult import (
    Catapult, draw_background, get_ends,
    WIDTH, HEIGHT, FPS, GROUND_Y, RELEASE_ANGLE, ARM_ANGLE_REST
)
from cata_physics import launch_velocity, get_launch_point
from cata_projectile import Projectile, draw_object
from cata_objects import OBJECTS
from cataui import UI


async def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    try:
        pygame.display.set_caption("Catapult Simulator")
    except Exception:
        pass
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 18)
    font_large = pygame.font.Font(None, 24)

    catapult = Catapult(pivot=(240, GROUND_Y - 75))
    ui = UI(font, font_large)
    projectile = None
    camera_x = 0.0
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        mx, my = pygame.mouse.get_pos()

        # ── Events ────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            catapult.handle_event(event, mx, my, camera_x)
            ui.handle_event(event)

            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                selected_obj = ui.get_selected_object()
                if (selected_obj and not catapult.is_oscillating
                        and catapult.arm_angle > ARM_ANGLE_REST):
                    catapult.loaded_angle = catapult.arm_angle
                    catapult.is_oscillating = True
                    catapult.angular_vel = 0.0
                    catapult.has_fired = False

            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                projectile = None
                camera_x = 0.0
                catapult.arm_angle = ARM_ANGLE_REST
                catapult.arm_length = 140
                catapult.is_oscillating = False
                catapult.angular_vel = 0.0
                catapult.has_fired = False
                catapult.has_spawned = False
                catapult.dragging = False
                catapult.dragging_type = None
                catapult.shake_offset = 0
                catapult.shake_timer = 0.0
                catapult.hovering_handle = False
                catapult.hovering_basket = False

        # ── Update ────────────────────────────────────────────────────────
        catapult.update(dt, mx, my, camera_x)

        if catapult.has_fired and ui.get_selected_object() and projectile is None:
            px, py = get_launch_point(
                catapult.pivot, catapult.arm_length, RELEASE_ANGLE
            )
            vx, vy = launch_velocity(
                catapult.arm_length, catapult.loaded_angle, RELEASE_ANGLE,
                ui.get_selected_object().mass
            )
            projectile = Projectile(ui.get_selected_object(), px, py, vx, vy)
            catapult.has_fired = False
            catapult.has_spawned = True

        if projectile:
            projectile.update(dt)

        ui.update(projectile, catapult, dt)

        # ── Camera ────────────────────────────────────────────────────────
        if projectile and projectile.state in ("flying", "rolling"):
            if projectile.x > WIDTH * 0.4:
                target_x = projectile.x - WIDTH * 0.4
                camera_x += (target_x - camera_x) * 0.08

        # ── Draw ──────────────────────────────────────────────────────────
        draw_background(screen, camera_x)

        catapult.draw(screen, font, camera_x)

        selected_obj = ui.get_selected_object()
        if selected_obj and projectile is None:
            basket_pivot = (catapult.pivot[0] - camera_x, catapult.pivot[1])
            _, basket_end = get_ends(
                basket_pivot, catapult.arm_length, catapult.arm_angle
            )
            draw_object(screen, selected_obj,
                        basket_end[0] + catapult.shake_offset, basket_end[1])

        if projectile:
            projectile.draw(screen, camera_x)

        ui.draw(screen, projectile, catapult, camera_x)

        pygame.display.flip()

        # ── Required by pygbag for web export ─────────────────────────────
        await asyncio.sleep(0)

    pygame.quit()


asyncio.run(main())