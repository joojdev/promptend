import sys
from dataclasses import dataclass
from pathlib import Path

PRESETS_DIR = Path("config/personalities")


@dataclass(frozen=True)
class PersonalitySource:
    path: Path
    preset: str | None


def available_presets(directory: Path = PRESETS_DIR) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.md") if p.is_file())


def _fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def resolve_personality(settings, presets_dir: Path = PRESETS_DIR) -> PersonalitySource:
    """Turn PERSONALITY / PERSONALITY_PATH into the personality file to load.

    A non-empty PERSONALITY_PATH wins; otherwise PERSONALITY names a preset in presets_dir.
    Existence of a custom path is checked later by load_harness.
    """
    custom = settings.personality_path.strip()
    if custom:
        return PersonalitySource(path=Path(custom), preset=None)

    name = settings.personality.strip().lower()
    available = available_presets(presets_dir)
    if not available:
        _fail(f"no personality presets found in {presets_dir.as_posix()}/")
    if any(part in name for part in ("/", "\\", "..")) or name not in available:
        _fail(f"unknown personality preset '{name}'. Available presets: {', '.join(available)}")
    return PersonalitySource(path=presets_dir / f"{name}.md", preset=name)
