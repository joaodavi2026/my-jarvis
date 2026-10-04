"""Dev tool: show how StorageManager sees this machine. Read-only unless --bind is given.

    python scripts/storage_check.py --internal-root <dir> [--bind <volume-guid>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "service" / "src"))

from jarvis.storage import StorageCategory, StorageManager, StorageUnavailable  # noqa: E402
from jarvis.storage.windows_volumes import WindowsVolumeProvider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--internal-root", type=Path, required=True, help="folder for the internal tier (SSD)")
    parser.add_argument("--bind", help="volume GUID to adopt as external storage (creates the runtime root)")
    args = parser.parse_args()

    manager = StorageManager(args.internal_root, WindowsVolumeProvider())
    manager.add_listener(lambda event: print(f"  event: {event.kind.value} {event.detail}"))
    status = manager.initialize()
    if args.bind:
        status = manager.bind(args.bind)

    print(f"mode: {status.mode.value}  reason: {status.reason.value if status.reason else '-'}  space: {status.space.value}")
    if status.detail:
        print(f"detail: {status.detail}")
    for volume in status.candidates:
        print(f"candidate: {volume.letter} {volume.label!r} guid={volume.guid} {volume.filesystem} {volume.media_type}")
    if status.volume:
        v = status.volume
        print(f"volume: {v.letter} {v.label!r} {v.filesystem} {v.media_type} "
              f"free={v.free_bytes / 2**30:.1f} GB of {v.total_bytes / 2**30:.1f} GB")
        if v.media_type == "HDD":
            print("note: mechanical HDD - loading large models from it will be slow")
    print(f"storage_root: {manager.storage_root}")
    for category in StorageCategory:
        try:
            print(f"  {category.value:16} {manager.get_path(category)}")
        except StorageUnavailable as exc:
            print(f"  {category.value:16} UNAVAILABLE ({exc.reason.value})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
