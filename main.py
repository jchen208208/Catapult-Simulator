import pygame
from catapult import (
    Catapult, draw_background, get_ends,
    WIDTH, HEIGHT, FPS, GROUND_Y, RELEASE_ANGLE, ARM_ANGLE_REST
)
from cata_physics import launch_velocity, get_launch_point
from cata_projectile import Projectile, draw_object
from cata_objects import OBJECTS
from cataui import UI


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Catapult Simulator")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 14)
    font_large = pygame.font.SysFont("Arial", 18, bold=True)

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

        # Spawn a projectile immediately when the arm is released
        # (has_fired is set in catapult's MOUSEBUTTONUP handler).
        if catapult.has_fired and ui.get_selected_object() and projectile is None:
            # Projectile always releases at the top of the arc (90°)
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
            # Keep the stopped projectile on screen so the HUD
            # continues to display final stats.
            # Pressing R clears everything.

        # Let the UI track flight state and detect landing.
        ui.update(projectile, catapult, dt)

        # ── Camera ────────────────────────────────────────────────────────
        if projectile and projectile.state in ("flying", "rolling"):
            if projectile.x > WIDTH * 0.4:
                target_x = projectile.x - WIDTH * 0.4
                camera_x += (target_x - camera_x) * 0.08

        # ── Draw ──────────────────────────────────────────────────────────
        draw_background(screen, camera_x)

        catapult.draw(screen, font, camera_x)

        # Draw selected object on top of the basket so it visibly sits inside
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

        # All UI elements — HUD panels, picker, controls, fire button
        ui.draw(screen, projectile, catapult, camera_x)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
