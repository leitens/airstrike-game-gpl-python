from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
import random

import pygame

from .assets import Animation, AssetStore
from .config import PlaneTuning


WORLD = pygame.Rect(0, 0, 800, 600)
GROUND_Y = 536
MAX_PLANE_SPEED = 260


@dataclass
class InputState:
    thrust: bool = False
    turn_left: bool = False
    turn_right: bool = False
    fire: bool = False
    bomb: bool = False


class Entity:
    radius = 12
    damage = 1
    solid = True
    targetable = True

    def __init__(
        self,
        pos: pygame.Vector2,
        vel: pygame.Vector2 | None = None,
        animation: Animation | None = None,
    ) -> None:
        self.pos = pos
        self.vel = vel or pygame.Vector2()
        self.animation = animation
        self.age_ms = 0.0
        self.alive = True
        self.angle = 0.0
        self.health = 1

    def update(self, world: "GameWorld", dt: float) -> None:
        self.age_ms += dt * 1000
        self.pos += self.vel * dt

    def image(self) -> pygame.Surface | None:
        if self.animation is None:
            return None
        return self.animation.frame(self.age_ms)

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2) -> None:
        image = self.image()
        if image is None:
            return
        rect = image.get_rect(center=(round(self.pos.x - offset.x), round(self.pos.y - offset.y)))
        surface.blit(image, rect)

    def hit(self, damage: int, world: "GameWorld") -> None:
        self.health -= damage
        if self.health <= 0:
            self.alive = False
            world.explosion(self.pos)


class Effect(Entity):
    solid = False
    targetable = False

    def __init__(self, pos: pygame.Vector2, vel: pygame.Vector2, animation: Animation) -> None:
        super().__init__(pos, vel, animation)

    def update(self, world: "GameWorld", dt: float) -> None:
        super().update(world, dt)
        self.vel.y += world.gravity * 0.2
        if self.animation and self.animation.finished(self.age_ms):
            self.alive = False


class Projectile(Entity):
    radius = 3
    solid = False
    targetable = False

    def __init__(
        self,
        owner: int,
        pos: pygame.Vector2,
        vel: pygame.Vector2,
        animation: Animation,
        ttl_ms: int,
        damage: int,
    ) -> None:
        super().__init__(pos, vel, animation)
        self.owner = owner
        self.ttl_ms = ttl_ms
        self.damage = damage

    def update(self, world: "GameWorld", dt: float) -> None:
        super().update(world, dt)
        self.vel.y += world.gravity * 2.5
        if self.age_ms >= self.ttl_ms or not world.bounds.inflate(80, 80).collidepoint(self.pos):
            self.alive = False
        if world.is_solid_at(self.pos):
            self.alive = False
            world.puff(self.pos)


class Bomb(Entity):
    radius = 8
    solid = False
    targetable = False

    def __init__(self, owner: int, pos: pygame.Vector2, vel: pygame.Vector2, animation: Animation) -> None:
        super().__init__(pos, vel, animation)
        self.owner = owner
        self.damage = 20

    def update(self, world: "GameWorld", dt: float) -> None:
        super().update(world, dt)
        self.vel.y += world.gravity * 1.6
        if self.vel.length_squared() > 1:
            self.angle = -self.vel.angle_to(pygame.Vector2(1, 0))
        if world.is_solid_at(self.pos):
            self.alive = False
            world.explosion(self.pos)

    def image(self) -> pygame.Surface | None:
        image = super().image()
        if image is None:
            return None
        return pygame.transform.rotate(image, self.angle)


class Plane(Entity):
    radius = 22

    def __init__(
        self,
        player_id: int,
        name: str,
        pos: pygame.Vector2,
        color: str,
        assets: AssetStore,
        tuning: PlaneTuning,
        human: bool,
    ) -> None:
        super().__init__(pos, pygame.Vector2(), assets.animation(f"{color}plane.png", 48, 64, 100))
        self.player_id = player_id
        self.name = name
        self.color = color
        self.assets = assets
        self.tuning = tuning
        self.human = human
        self.heading = 180.0 if player_id == 0 else 0.0
        self.health = tuning.hitpoints
        self.max_health = tuning.hitpoints
        self.bombs = tuning.bombs
        self.fire_cooldown_ms = 0.0
        self.bomb_cooldown_ms = 0.0
        self.crashing = False
        self.animation = assets.animation(f"{color}plane.png", 48, 64, 100)
        self.wreck = assets.animation(f"{color}planewreck.png", 48, 64, 180)

    def reset(self, pos: pygame.Vector2) -> None:
        self.pos = pos.copy()
        self.vel = pygame.Vector2(-30 if self.player_id == 0 else 30, -20)
        self.heading = 180.0 if self.player_id == 0 else 0.0
        self.health = self.max_health
        self.bombs = self.tuning.bombs
        self.fire_cooldown_ms = 0
        self.bomb_cooldown_ms = 0
        self.crashing = False
        self.alive = True
        self.age_ms = 0
        self.animation = self.assets.animation(f"{self.color}plane.png", 48, 64, 100)

    def controls(self, world: "GameWorld") -> InputState:
        if self.human:
            return world.input_for(self.player_id)
        return self._ai_controls(world)

    def update(self, world: "GameWorld", dt: float) -> None:
        self.age_ms += dt * 1000
        self.fire_cooldown_ms = max(0.0, self.fire_cooldown_ms - dt * 1000)
        self.bomb_cooldown_ms = max(0.0, self.bomb_cooldown_ms - dt * 1000)

        control = self.controls(world)
        if not self.crashing:
            if control.turn_left:
                self.heading -= self.tuning.turn_amount * 1150 * dt
            if control.turn_right:
                self.heading += self.tuning.turn_amount * 1150 * dt
            if control.thrust:
                self.vel += self.forward() * (self.tuning.engine_strength * 900 * dt)
                world.smoke(self.pos - self.forward() * 20)
            if control.fire:
                self.fire(world)
            if control.bomb:
                self.drop_bomb(world)

        self.vel.y += world.gravity * 55 * dt
        self.vel *= max(0.0, 1.0 - 0.12 * dt)
        if self.vel.length_squared() > MAX_PLANE_SPEED * MAX_PLANE_SPEED:
            self.vel.scale_to_length(MAX_PLANE_SPEED)
        self.pos += self.vel * dt
        self._wrap_horizontal(world)

        if world.is_solid_at(self.pos + pygame.Vector2(0, self.radius * 0.8)):
            if self.vel.length() > 120 or self.crashing:
                self.health = 0
                self.alive = False
                world.explosion(self.pos)
            else:
                self.pos.y -= 3
                self.vel.y = -abs(self.vel.y) * 0.25

        if self.health <= 0 and not self.crashing:
            self.crashing = True
            self.animation = self.wreck
            world.fire(self.pos)
        if self.crashing:
            self.heading += 130 * dt
            if self.age_ms > 7000:
                self.alive = False
                world.explosion(self.pos)

    def _ai_controls(self, world: "GameWorld") -> InputState:
        enemy = world.enemy_of(self)
        if enemy is None:
            target = pygame.Vector2(400, 100)
        else:
            target = enemy.pos
        desired = target - self.pos
        if desired.length_squared() == 0:
            desired = pygame.Vector2(1, 0)
        signed = self.forward().cross(desired)
        aligned = abs(self.forward().normalize().dot(desired.normalize())) > 0.86
        speed = self.vel.length()
        return InputState(
            thrust=speed < 220 or self.pos.y > 430,
            turn_left=signed < -4,
            turn_right=signed > 4,
            fire=enemy is not None and aligned and desired.length_squared() < 90_000,
            bomb=enemy is not None and abs(desired.x) < 45 and desired.y > 20,
        )

    def _wrap_horizontal(self, world: "GameWorld") -> None:
        if self.pos.x < world.bounds.left - 20:
            self.pos.x = world.bounds.right + 20
        elif self.pos.x > world.bounds.right + 20:
            self.pos.x = world.bounds.left - 20
        self.pos.y = max(-80, min(world.bounds.bottom + 80, self.pos.y))

    def forward(self) -> pygame.Vector2:
        angle = radians(self.heading)
        return pygame.Vector2(cos(angle), sin(angle))

    def fire(self, world: "GameWorld") -> None:
        if self.fire_cooldown_ms > 0:
            return
        direction = self.forward()
        bullet = Projectile(
            owner=self.player_id,
            pos=self.pos + direction * 22,
            vel=self.vel + direction * 260,
            animation=self.assets.animation("bullet.png", 3, 1, world.config.bullet_ttl_ms),
            ttl_ms=world.config.bullet_ttl_ms,
            damage=world.config.bullet_damage,
        )
        world.add(bullet)
        world.play("shoot.wav")
        self.fire_cooldown_ms = self.tuning.bullet_delay_ms

    def drop_bomb(self, world: "GameWorld") -> None:
        if self.bomb_cooldown_ms > 0 or self.bombs <= 0:
            return
        self.bombs -= 1
        direction = self.forward()
        offset = direction.rotate(85) * 16
        bomb = Bomb(
            owner=self.player_id,
            pos=self.pos + offset,
            vel=self.vel + offset * 1.8,
            animation=self.assets.animation("bomb.png", 16, 64, 100),
        )
        world.add(bomb)
        self.bomb_cooldown_ms = self.tuning.bomb_delay_ms

    def hit(self, damage: int, world: "GameWorld") -> None:
        if not self.crashing:
            self.health -= damage
            world.puff(self.pos)

    def image(self) -> pygame.Surface | None:
        frame_index_age = ((self.heading % 360) / 360) * 6400
        if self.crashing:
            frame_index_age = self.age_ms
        image = self.animation.frame(frame_index_age)
        return image


class Ambient(Entity):
    radius = 28
    solid = False

    def __init__(
        self,
        pos: pygame.Vector2,
        vel: pygame.Vector2,
        animation: Animation,
        health: int = 20,
        *,
        targetable: bool = True,
    ) -> None:
        super().__init__(pos, vel, animation)
        self.health = health
        self.targetable = targetable

    def update(self, world: "GameWorld", dt: float) -> None:
        super().update(world, dt)
        margin = max(80, self.radius * 2)
        if self.pos.x < -margin:
            self.pos.x = world.bounds.right + margin
        if self.pos.x > world.bounds.right + margin:
            self.pos.x = -margin
        if self.pos.y > GROUND_Y:
            self.vel.y = -abs(self.vel.y)
        if self.pos.y < 30:
            self.vel.y = abs(self.vel.y)


class Balloon(Ambient):
    def hit(self, damage: int, world: "GameWorld") -> None:
        self.health -= damage
        self.vel.y *= -1
        if self.health <= 0:
            self.alive = False
            world.explosion(self.pos)


class Bouncer(Ambient):
    radius = 14

    def update(self, world: "GameWorld", dt: float) -> None:
        super().update(world, dt)
        self.vel.y += world.gravity * 30 * dt
        if self.pos.y > 500:
            self.pos.y = 500
            self.vel.y = -abs(self.vel.y) * 0.95


class GameWorldProtocol:
    bounds: pygame.Rect
    gravity: float


def random_bouncers(assets: AssetStore, count: int = 5) -> list[Bouncer]:
    anim = assets.animation("balloon-float.png", 32, 1, 100)
    return [
        Bouncer(
            pygame.Vector2(random.randint(80, 720), random.randint(130, 300)),
            pygame.Vector2(random.choice([-35, 35]), random.randint(-15, 15)),
            anim,
            health=6,
        )
        for _ in range(count)
    ]
