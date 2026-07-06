from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import warnings

import pygame
from PIL import Image


MAGENTA = (255, 0, 255)


@dataclass
class Animation:
    frames: list[pygame.Surface]
    frame_ms: int
    loop: bool = True

    def frame(self, age_ms: float) -> pygame.Surface:
        if not self.frames:
            raise ValueError("Animation has no frames")
        index = int(age_ms // self.frame_ms)
        if self.loop:
            index %= len(self.frames)
        else:
            index = min(index, len(self.frames) - 1)
        return self.frames[index]

    def finished(self, age_ms: float) -> bool:
        return not self.loop and age_ms >= self.frame_ms * len(self.frames)


class AssetStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._images: dict[str, pygame.Surface] = {}
        self._animations: dict[tuple[str, int, int, int, bool], Animation] = {}
        self._sounds: dict[str, Any | None] = {}

    def image(self, name: str, *, colorkey: bool = True) -> pygame.Surface:
        if name not in self._images:
            path = self.data_dir / name
            surface = self._load_image(path)
            if colorkey:
                surface.set_colorkey(MAGENTA)
            self._images[name] = surface
        return self._images[name]

    def _load_image(self, path: Path) -> pygame.Surface:
        try:
            return pygame.image.load(path).convert_alpha()
        except pygame.error:
            image = Image.open(path).convert("RGBA")
            raw = image.tobytes()
            size = image.size
            return pygame.image.frombuffer(raw, size, "RGBA").copy().convert_alpha()

    def animation(
        self,
        name: str,
        frame_width: int,
        frame_count: int | None = None,
        frame_ms: int = 100,
        *,
        loop: bool = True,
    ) -> Animation:
        key = (name, frame_width, frame_count or -1, frame_ms, loop)
        if key in self._animations:
            return self._animations[key]

        sheet = self.image(name)
        if frame_count is None:
            frame_count = max(1, sheet.get_width() // frame_width)
        frames: list[pygame.Surface] = []
        for index in range(frame_count):
            rect = pygame.Rect(index * frame_width, 0, frame_width, sheet.get_height())
            frame = pygame.Surface(rect.size, pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), rect)
            frame = _with_magenta_transparent(frame)
            frames.append(frame)

        animation = Animation(frames=frames, frame_ms=frame_ms, loop=loop)
        self._animations[key] = animation
        return animation

    def sound(self, name: str) -> Any | None:
        if name in self._sounds:
            return self._sounds[name]
        path = self.data_dir / "sound" / name
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                mixer = pygame.mixer
                sound = mixer.Sound(path)
        except (AttributeError, ModuleNotFoundError, NotImplementedError, pygame.error):
            sound = None
        self._sounds[name] = sound
        return sound


def _with_magenta_transparent(surface: pygame.Surface) -> pygame.Surface:
    converted = surface.convert_alpha()
    width, height = converted.get_size()
    for y in range(height):
        for x in range(width):
            r, g, b, a = converted.get_at((x, y))
            if (r, g, b) == MAGENTA:
                converted.set_at((x, y), (r, g, b, 0))
            else:
                converted.set_at((x, y), (r, g, b, a))
    return converted
