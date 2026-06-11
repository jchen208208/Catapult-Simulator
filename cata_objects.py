from dataclasses import dataclass

@dataclass
class ProjectileObject:
    name: str
    mass: float
    radius: int
    drag_coeff: float
    restitution: float
    friction_coeff: float
    color: tuple
    outline_color: tuple
    spin_factor: float
    display_scale: float = 1.0

OBJECTS: list[ProjectileObject] = [
    ProjectileObject(
        name="Boulder",
        mass=50.0,
        radius=18,
        drag_coeff=0.50,
        restitution=0.10,
        friction_coeff=0.80,
        color=(120, 115, 105),
        outline_color=(80, 75, 70),
        spin_factor=0.8,
        display_scale=1.5,
    ),
    ProjectileObject(
        name="Cannonball",
        mass=8.0,
        radius=10,
        drag_coeff=0.47,
        restitution=0.10,
        friction_coeff=0.30,
        color=(50, 50, 55),
        outline_color=(30, 30, 35),
        spin_factor=1.0,
        display_scale=2.7,
    ),
    ProjectileObject(
        name="Watermelon",
        mass=5.0,
        radius=16,
        drag_coeff=0.50,
        restitution=0.15,
        friction_coeff=0.50,
        color=(60, 140, 50),
        outline_color=(40, 100, 30),
        spin_factor=0.9,
        display_scale=1.7,
    ),
    ProjectileObject(
        name="Soccer Ball",
        mass=0.43,
        radius=14,
        drag_coeff=0.35,
        restitution=0.70,
        friction_coeff=0.30,
        color=(230, 230, 230),
        outline_color=(180, 180, 180),
        spin_factor=1.2,
        display_scale=1.9,
    ),
    ProjectileObject(
        name="Anvil",
        mass=100.0,
        radius=14,
        drag_coeff=1.20,
        restitution=0.05,
        friction_coeff=0.90,
        color=(90, 90, 100),
        outline_color=(55, 55, 65),
        spin_factor=0.3,
        display_scale=1.9,
    ),
    ProjectileObject(
        name="Pumpkin",
        mass=4.0,
        radius=15,
        drag_coeff=0.60,
        restitution=0.15,
        friction_coeff=0.60,
        color=(230, 120, 30),
        outline_color=(180, 80, 10),
        spin_factor=0.7,
        display_scale=1.8,
    ),
]