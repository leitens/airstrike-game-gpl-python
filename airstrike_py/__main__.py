from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .game import AirstrikeGame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Play the Python port of Airstrike.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to the Airstrike data directory. Defaults to ./data next to the sources.",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Start in fullscreen mode. F11 also toggles fullscreen while playing.",
    )
    parser.add_argument(
        "--nosound",
        action="store_true",
        help="Disable sound even if sound assets and an audio device are available.",
    )
    args = parser.parse_args(argv)

    game = AirstrikeGame(
        data_dir=args.data_dir,
        start_fullscreen=args.fullscreen,
        sound_enabled=not args.nosound,
    )
    return game.run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
