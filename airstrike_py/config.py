from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shlex


@dataclass(frozen=True)
class GameConfig:
    width: int = 800
    height: int = 600
    gravity: float = 0.2
    nr_players: int = 1
    sound: bool = True
    max_score: int = 5
    raw: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "GameConfig":
        values: dict[str, str] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    parts = shlex.split(line, comments=True)
                except ValueError:
                    continue
                if len(parts) >= 2:
                    values[parts[0]] = " ".join(parts[1:])

        return cls(
            width=_int(values, "screen.width", 800),
            height=_int(values, "screen.height", 600),
            gravity=_float(values, "level.gravity", 0.2),
            nr_players=max(0, min(2, _int(values, "nr_players", 1))),
            sound=_int(values, "sound", 1) == 1,
            raw=values,
        )

    def plane(self, color: str) -> "PlaneTuning":
        prefix = f"{color}plane"
        return PlaneTuning(
            engine_strength=_float(self.raw, f"{prefix}.engine_strength", 0.3),
            turn_amount=_float(self.raw, f"{prefix}.turn_amount", 0.06),
            bullet_delay_ms=_int(self.raw, f"{prefix}.bullet_delay", 140),
            bomb_delay_ms=_int(self.raw, f"{prefix}.bomb_delay", 300),
            hitpoints=_int(self.raw, f"{prefix}.hitpoints", 15),
            bombs=_int(self.raw, f"{prefix}.nr_bombs", 5),
        )

    @property
    def bullet_ttl_ms(self) -> int:
        return _int(self.raw, "bullet.ttl", 1400)

    @property
    def bullet_damage(self) -> int:
        return _int(self.raw, "bullet.damage", 1)


@dataclass(frozen=True)
class PlaneTuning:
    engine_strength: float
    turn_amount: float
    bullet_delay_ms: int
    bomb_delay_ms: int
    hitpoints: int
    bombs: int


def _int(values: dict[str, str], key: str, default: int) -> int:
    try:
        return int(float(values.get(key, str(default))))
    except ValueError:
        return default


def _float(values: dict[str, str], key: str, default: float) -> float:
    try:
        return float(values.get(key, str(default)))
    except ValueError:
        return default
