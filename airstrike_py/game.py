from __future__ import annotations

import random
import warnings
from pathlib import Path

import pygame

from .assets import AssetStore
from .config import GameConfig
from .entities import (
    Ambient,
    Balloon,
    Bomb,
    Effect,
    Entity,
    InputState,
    Plane,
    Projectile,
    WORLD,
    random_bouncers,
)
from .text import BitmapFont


class GameWorld:
    def __init__(
        self,
        config: GameConfig,
        assets: AssetStore,
        *,
        sound_enabled: bool,
    ) -> None:
        self.config = config
        self.assets = assets
        self.bounds = WORLD.copy()
        self.gravity = config.gravity
        self.entities: list[Entity] = []
        self.planes: list[Plane] = []
        self.scores = [0, 0]
        self.round_message = ""
        self.round_message_ms = 0.0
        self._keys: pygame.key.ScancodeWrapper | None = None
        self.sound_enabled = sound_enabled

        self.bg_mask: pygame.Surface | None = None
        try:
            self.bg_mask = assets.image("bgmask.png", colorkey=False)
        except pygame.error:
            self.bg_mask = None

        self.new_match()

    def new_match(self) -> None:
        random.seed(23)
        self.entities.clear()
        self.planes.clear()
        self.scores = [0, 0]
        self._spawn_scenery()
        self.spawn_planes()

    def _spawn_scenery(self) -> None:
        cloud = self.assets.animation("cloud.png", 240, 1, 1000)
        self.add(
            Ambient(
                pygame.Vector2(420, 78),
                pygame.Vector2(13, 0),
                cloud,
                999,
                targetable=False,
            )
        )
        self.add(
            Ambient(
                pygame.Vector2(20, 150),
                pygame.Vector2(9, 0),
                cloud,
                999,
                targetable=False,
            )
        )
        self.add(
            Ambient(
                pygame.Vector2(70, 210),
                pygame.Vector2(18, 0),
                self.assets.animation("zeppelin-right.png", 96, 1, 1000),
                55,
            )
        )
        self.add(Balloon(pygame.Vector2(110, 160), pygame.Vector2(8, 5), self.assets.animation("airballoon.png", 64, 8, 140), 10))
        self.entities.extend(random_bouncers(self.assets, 5))

    def spawn_planes(self) -> None:
        starts = [pygame.Vector2(700, 500), pygame.Vector2(40, 310)]
        colors = ["blue", "red"]
        names = ["Blue Baron", "Red Baron"]
        for player_id in range(2):
            human = player_id < self.config.nr_players
            plane = Plane(
                player_id=player_id,
                name=names[player_id],
                pos=starts[player_id].copy(),
                color=colors[player_id],
                assets=self.assets,
                tuning=self.config.plane(colors[player_id]),
                human=human,
            )
            plane.reset(starts[player_id])
            self.planes.append(plane)
            self.add(plane)
        if self.config.nr_players == 1:
            self.planes[1].human = False
        elif self.config.nr_players == 0:
            self.planes[0].human = False
            self.planes[1].human = False

    def add(self, entity: Entity) -> None:
        self.entities.append(entity)

    def set_keys(self, keys: pygame.key.ScancodeWrapper) -> None:
        self._keys = keys

    def input_for(self, player_id: int) -> InputState:
        keys = self._keys
        if keys is None:
            return InputState()
        if player_id == 0:
            return InputState(
                thrust=keys[pygame.K_UP] or keys[pygame.K_COMMA],
                turn_left=keys[pygame.K_LEFT],
                turn_right=keys[pygame.K_RIGHT],
                fire=keys[pygame.K_z],
                bomb=keys[pygame.K_RSHIFT] or keys[pygame.K_SPACE],
            )
        return InputState(
            thrust=keys[pygame.K_w] or keys[pygame.K_LCTRL],
            turn_left=keys[pygame.K_a],
            turn_right=keys[pygame.K_d],
            fire=keys[pygame.K_LSHIFT],
            bomb=keys[pygame.K_TAB],
        )

    def update(self, dt: float) -> None:
        for entity in list(self.entities):
            entity.update(self, dt)

        self._collide_projectiles()
        self._collide_solids()
        self.entities = [entity for entity in self.entities if entity.alive]
        self._scorekeeper()
        if self.round_message_ms > 0:
            self.round_message_ms = max(0, self.round_message_ms - dt * 1000)

    def _collide_projectiles(self) -> None:
        projectiles = [e for e in self.entities if isinstance(e, (Projectile, Bomb)) and e.alive]
        targets = [e for e in self.entities if e.targetable and e.alive]
        for projectile in projectiles:
            for target in targets:
                if target is projectile:
                    continue
                if isinstance(target, Plane) and target.player_id == projectile.owner:
                    continue
                if projectile.pos.distance_squared_to(target.pos) <= (projectile.radius + target.radius) ** 2:
                    target.hit(projectile.damage, self)
                    projectile.alive = False
                    if isinstance(projectile, Bomb):
                        self.explosion(projectile.pos)
                    else:
                        self.puff(projectile.pos)
                    break

    def _collide_solids(self) -> None:
        solids = [e for e in self.entities if e.solid and e.alive and not isinstance(e, (Projectile, Bomb))]
        for index, left in enumerate(solids):
            for right in solids[index + 1 :]:
                delta = right.pos - left.pos
                distance_sq = delta.length_squared()
                min_dist = left.radius + right.radius
                if distance_sq == 0 or distance_sq > min_dist * min_dist:
                    continue
                normal = delta.normalize()
                overlap = min_dist - distance_sq**0.5
                left.pos -= normal * overlap * 0.5
                right.pos += normal * overlap * 0.5
                left.vel, right.vel = right.vel * 0.65, left.vel * 0.65
                if isinstance(left, Plane):
                    left.hit(2, self)
                if isinstance(right, Plane):
                    right.hit(2, self)
                self.puff((left.pos + right.pos) * 0.5)

    def _scorekeeper(self) -> None:
        for plane in self.planes:
            if plane.alive:
                continue
            opponent = 1 - plane.player_id
            self.scores[opponent] += 1
            if self.scores[opponent] >= self.config.max_score:
                self.round_message = f"{self.planes[opponent].name} wins!"
                self.round_message_ms = 2600
                self.new_match()
                return
            self.round_message = f"{self.planes[opponent].name} scores"
            self.round_message_ms = 1600
            replacement = Plane(
                player_id=plane.player_id,
                name=plane.name,
                pos=pygame.Vector2(700, 500) if plane.player_id == 0 else pygame.Vector2(40, 310),
                color=plane.color,
                assets=self.assets,
                tuning=plane.tuning,
                human=plane.human,
            )
            replacement.reset(replacement.pos)
            self.planes[plane.player_id] = replacement
            self.add(replacement)

    def is_solid_at(self, point: pygame.Vector2) -> bool:
        x, y = round(point.x), round(point.y)
        if x < 0 or x >= self.bounds.width or y >= self.bounds.height:
            return True
        if y < 0:
            return False
        if self.bg_mask is None:
            return y >= GROUND_Y
        color = self.bg_mask.get_at((x, y))[:3]
        return color != (255, 0, 255)

    def enemy_of(self, plane: Plane) -> Plane | None:
        enemy = self.planes[1 - plane.player_id]
        return enemy if enemy.alive else None

    def smoke(self, pos: pygame.Vector2) -> None:
        if random.random() > 0.35:
            return
        self.add(
            Effect(
                pos.copy(),
                pygame.Vector2(random.uniform(-4, 4), random.uniform(-14, -7)),
                self.assets.animation("whitesmoke.png", 16, 32, 60, loop=False),
            )
        )

    def puff(self, pos: pygame.Vector2) -> None:
        self.add(Effect(pos.copy(), pygame.Vector2(0, -12), self.assets.animation("sdust-grow.png", 12, 8, 35, loop=False)))

    def fire(self, pos: pygame.Vector2) -> None:
        self.add(Effect(pos.copy(), pygame.Vector2(0, -10), self.assets.animation("fire.png", 24, 16, 45, loop=False)))

    def explosion(self, pos: pygame.Vector2) -> None:
        self.add(Effect(pos.copy(), pygame.Vector2(0, -20), self.assets.animation("firebomb.png", 48, 32, 30, loop=False)))
        self.play("splat3a.wav")

    def play(self, sound_name: str) -> None:
        if not self.sound_enabled:
            return
        sound = self.assets.sound(sound_name)
        if sound is not None:
            sound.play()


class AirstrikeGame:
    def __init__(
        self,
        data_dir: Path | None = None,
        *,
        start_fullscreen: bool = False,
        sound_enabled: bool = True,
    ) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.data_dir = data_dir or self.root / "data"
        self.config = GameConfig.from_file(self.root / "airstrikerc")
        self.start_fullscreen = start_fullscreen
        self.requested_sound = sound_enabled and self.config.sound
        self.screen: pygame.Surface | None = None
        self.fullscreen = start_fullscreen
        self.paused = False
        self.show_help = False
        self.clock: pygame.time.Clock | None = None
        self.assets: AssetStore | None = None
        self.world: GameWorld | None = None
        self.font: BitmapFont | None = None
        self.big_font: BitmapFont | None = None

    def run(self) -> int:
        pygame.init()
        sound_enabled = self._init_sound()
        pygame.display.set_caption("Airstrike Python")
        self.screen = self._set_display(self.fullscreen)
        self.clock = pygame.time.Clock()
        self.font = BitmapFont(scale=2)
        self.big_font = BitmapFont(scale=5, spacing=2)
        self.assets = AssetStore(self.data_dir)
        self.world = GameWorld(self.config, self.assets, sound_enabled=sound_enabled)

        running = True
        while running:
            dt = self.clock.tick(60) / 1000
            running = self._events()
            keys = pygame.key.get_pressed()
            self.world.set_keys(keys)
            if not self.paused:
                self.world.update(min(dt, 1 / 20))
            self._draw()
        pygame.quit()
        return 0

    def _init_sound(self) -> bool:
        if not self.requested_sound:
            return False
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                mixer = pygame.mixer
                mixer.init()
        except (AttributeError, ModuleNotFoundError, NotImplementedError, pygame.error):
            return False
        return True

    def _set_display(self, fullscreen: bool) -> pygame.Surface:
        flags = pygame.SCALED | pygame.DOUBLEBUF
        if fullscreen:
            flags |= pygame.FULLSCREEN
        return pygame.display.set_mode((self.config.width, self.config.height), flags)

    def _events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                elif event.key == pygame.K_F1:
                    self.show_help = not self.show_help
                elif event.key == pygame.K_n and self.paused and self.world:
                    self.world.new_match()
                elif event.key == pygame.K_q and self.paused:
                    return False
        return True

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        self.screen = self._set_display(self.fullscreen)

    def _draw(self) -> None:
        assert self.screen is not None
        assert self.assets is not None
        assert self.world is not None
        bg = self.assets.image("bg.png", colorkey=False)
        self.screen.blit(bg, (0, 0))
        for entity in sorted(self.world.entities, key=_draw_order):
            entity.draw(self.screen, pygame.Vector2())
        self._draw_ui(self.screen, self.world)
        if self.paused:
            self._draw_pause(self.screen)
        pygame.display.flip()

    def _draw_ui(self, surface: pygame.Surface, world: GameWorld) -> None:
        assert self.font is not None
        assert self.big_font is not None
        left = world.planes[1]
        right = world.planes[0]
        self._draw_plane_status(surface, left, (18, 548), align_left=True)
        self._draw_plane_status(surface, right, (782, 548), align_left=False)

        score = self.big_font.render(f"{world.scores[1]:02d}-{world.scores[0]:02d}", True, (32, 28, 20))
        surface.blit(score, score.get_rect(center=(400, 558)))
        label = self.font.render("SCORE", True, (32, 28, 20))
        surface.blit(label, label.get_rect(center=(400, 586)))

        if world.round_message and world.round_message_ms > 0:
            text = self.big_font.render(world.round_message, True, (255, 245, 210))
            shadow = self.big_font.render(world.round_message, True, (40, 25, 20))
            rect = text.get_rect(center=(400, 210))
            surface.blit(shadow, rect.move(2, 2))
            surface.blit(text, rect)

        if self.show_help and not self.paused:
            self._draw_help(surface)

    def _draw_plane_status(
        self,
        surface: pygame.Surface,
        plane: Plane,
        pos: tuple[int, int],
        *,
        align_left: bool,
    ) -> None:
        assert self.font is not None
        name = self.font.render(plane.name, True, (30, 25, 18))
        stats = self.font.render(f"{plane.bombs} bombs  hp {max(0, plane.health):02d}", True, (30, 25, 18))
        if align_left:
            surface.blit(name, name.get_rect(topleft=pos))
            surface.blit(stats, stats.get_rect(topleft=(pos[0], pos[1] + 20)))
        else:
            surface.blit(name, name.get_rect(topright=pos))
            surface.blit(stats, stats.get_rect(topright=(pos[0], pos[1] + 20)))

    def _draw_help(self, surface: pygame.Surface) -> None:
        assert self.font is not None
        lines = [
            "F1 help  F11 fullscreen  Esc pause",
            "Blue: arrows/up thrust, Z fire, RShift/space bomb",
            "Red: A/D turn, W/LCtrl thrust, LShift fire, Tab bomb",
        ]
        y = 10
        for line in lines:
            text = self.font.render(line, True, (250, 244, 215))
            shadow = self.font.render(line, True, (40, 35, 25))
            surface.blit(shadow, (11, y + 1))
            surface.blit(text, (10, y))
            y += 20

    def _draw_pause(self, surface: pygame.Surface) -> None:
        assert self.font is not None
        assert self.big_font is not None
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 115))
        surface.blit(overlay, (0, 0))
        lines = [
            ("Airstrike", self.big_font),
            ("Esc resume   F11 fullscreen   N new match   Q quit", self.font),
        ]
        y = 240
        for line, font in lines:
            text = font.render(line, True, (255, 246, 220))
            surface.blit(text, text.get_rect(center=(400, y)))
            y += 44


def _draw_order(entity: Entity) -> int:
    if isinstance(entity, Effect):
        return 2
    if isinstance(entity, Projectile):
        return 3
    if isinstance(entity, Plane):
        return 4
    return 1
